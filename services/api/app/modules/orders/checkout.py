from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.carts.models import CartLine
from app.modules.carts.service import active_cart, orderable_variant
from app.modules.menu.models import Canteen, MenuItem, Station
from app.modules.menu.schedule import require_open
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.service import instant, lines_for, server_now
from app.modules.reviews.service import reviews_by_line


def existing_checkout(db, student_id, request_id):
    return db.scalar(
        select(Order).where(Order.student_id == student_id, Order.checkout_request_id == request_id)
    )


def checkout(db, student_id, request_id, expected_total_paise):
    """Freeze the student's cart into an immutable PAYMENT_PENDING order.

    Caller owns the transaction. The cart row lock serializes concurrent checkouts by the same
    student; (student_id, checkout_request_id) is unique, so a retried request returns the
    order it already created instead of charging twice.
    """
    cart = active_cart(db, student_id, lock=True)
    previous = existing_checkout(db, student_id, request_id)
    if previous:
        if previous.total_paise != expected_total_paise:
            raise DomainError("IDEMPOTENCY_CONFLICT")
        return previous
    rows = (
        list(db.scalars(select(CartLine).where(CartLine.cart_id == cart.id).order_by(CartLine.id)))
        if cart
        else []
    )
    if not rows:
        raise DomainError("CART_EMPTY")
    now = server_now(db)
    canteen = require_open(db, cart.canteen_id, now)

    snapshots = []
    total = 0
    for row in rows:
        try:
            variant, variant_canteen = orderable_variant(db, row.variant_id)
        except DomainError as error:
            raise DomainError("CART_ITEM_UNAVAILABLE") from error
        if variant_canteen.id != canteen.id:
            raise DomainError("CART_CANTEEN_CONFLICT")
        item = db.get(MenuItem, variant.item_id)
        if item is None or item.archived:
            raise DomainError("CART_ITEM_UNAVAILABLE")
        station = db.get(Station, variant.station_id)
        total += variant.price_paise * row.quantity
        snapshots.append((row, variant, item, station))
    if total != expected_total_paise:
        # The student confirmed a different amount than the server would charge.
        raise DomainError("PRICE_CHANGED")

    order = Order(
        canteen_id=canteen.id,
        student_id=student_id,
        state="PAYMENT_PENDING",
        total_paise=total,
        created_at=now,
        checkout_request_id=request_id,
    )
    db.add(order)
    db.flush()
    for row, variant, item, station in snapshots:
        db.add(
            OrderLine(
                canteen_id=canteen.id,
                order_id=order.id,
                station_id=station.id,
                station_name=station.name,
                variant_id=variant.id,
                name=item.name,
                variant_label=variant.label,
                unit_price_paise=variant.price_paise,
                quantity=row.quantity,
            )
        )
        db.delete(row)
    db.flush()
    return order


STUDENT_STATES = {
    "PAYMENT_PENDING": "Awaiting payment",
    "PAID_ACTIVE": "Paid, ready for pickup",
    "PARTIALLY_COLLECTED": "Partly collected",
    "COLLECTED": "Collected",
    "CANCELLED": "Cancelled",
}


def student_orders(db, student_id, limit=50):
    orders = list(
        db.scalars(
            select(Order)
            .where(Order.student_id == student_id)
            .order_by(Order.created_at.desc(), Order.id)
            .limit(limit)
        )
    )
    names = {
        canteen.id: canteen.name
        for canteen in db.scalars(
            select(Canteen).where(Canteen.id.in_({order.canteen_id for order in orders}))
        )
    }
    return [
        {
            "id": order.id,
            "canteen_id": order.canteen_id,
            "canteen_name": names.get(order.canteen_id),
            "state": order.state,
            "state_label": STUDENT_STATES.get(order.state, order.state),
            "total_paise": order.total_paise,
            "created_at": instant(order.created_at),
            "refund_status": order.refund_status,
            "exception_status": order.exception_status,
        }
        for order in orders
    ]


def student_order_detail(db, student_id, order_id):
    order = db.scalar(select(Order).where(Order.id == order_id, Order.student_id == student_id))
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", 404)
    canteen = db.get(Canteen, order.canteen_id)
    lines = lines_for(db, order.id)
    reviews = reviews_by_line(db, [line.id for line in lines])
    stations = {}
    for line in lines:
        remaining = line.quantity - line.fulfilled
        if remaining:
            stations[line.station_name] = stations.get(line.station_name, 0) + remaining
    return {
        "id": order.id,
        "canteen_id": order.canteen_id,
        "canteen_name": canteen.name if canteen else None,
        "state": order.state,
        "state_label": STUDENT_STATES.get(order.state, order.state),
        "total_paise": order.total_paise,
        "created_at": instant(order.created_at),
        "payment_verified_at": instant(order.payment_verified_at)
        if order.payment_verified_at
        else None,
        "refund_status": order.refund_status,
        "exception_status": order.exception_status,
        # The pickup code is only issued after verified payment (payments phase).
        "pickup_code": None,
        "remaining_by_station": [
            {"station": name, "remaining": count} for name, count in sorted(stations.items())
        ],
        "lines": [
            {
                "id": line.id,
                "name": line.name,
                "variant": line.variant_label,
                "station": line.station_name,
                "unit_price_paise": line.unit_price_paise,
                "quantity": line.quantity,
                "line_total_paise": line.unit_price_paise * line.quantity,
                "fulfilled": line.fulfilled,
                "remaining": line.quantity - line.fulfilled,
                # Reviewable once at least one unit was handed over.
                "reviewable": line.fulfilled > 0 and line.variant_id is not None,
                "review_id": reviews[line.id].id if line.id in reviews else None,
            }
            for line in lines
        ],
    }
