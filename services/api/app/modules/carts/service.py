from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.carts.models import Cart, CartLine
from app.modules.menu.models import Canteen, MenuItem, MenuVariant, Station


def active_cart(db, student_id, lock=False):
    query = select(Cart).where(Cart.student_id == student_id)
    if lock:
        query = query.with_for_update()
    return db.scalar(query)


def orderable_variant(db, variant_id):
    variant = db.get(MenuVariant, variant_id)
    if not variant:
        raise DomainError("MENU_VARIANT_NOT_FOUND", 404)
    canteen = db.get(Canteen, variant.canteen_id)
    station = db.get(Station, variant.station_id) if variant.station_id else None
    if (
        not canteen
        or not canteen.approved
        or not variant.verified
        or not variant.available
        or not variant.price_paise
        or not station
        or not station.active
    ):
        raise DomainError("MENU_VARIANT_UNAVAILABLE")
    return variant, canteen


def set_line(db, student_id, variant_id, quantity):
    if type(quantity) is not int or not 0 <= quantity <= 99:
        raise DomainError("INVALID_QUANTITY", 422)
    variant, canteen = orderable_variant(db, variant_id)
    cart = active_cart(db, student_id, lock=True)
    if cart and cart.canteen_id != canteen.id:
        has_lines = db.scalar(select(CartLine.id).where(CartLine.cart_id == cart.id))
        if has_lines:
            raise DomainError("CART_CANTEEN_CONFLICT")
        cart.canteen_id = canteen.id
    if cart is None:
        if quantity == 0:
            return None
        cart = Cart(student_id=student_id, canteen_id=canteen.id)
        db.add(cart)
        db.flush()
    line = db.scalar(
        select(CartLine).where(CartLine.cart_id == cart.id, CartLine.variant_id == variant.id)
    )
    if quantity == 0:
        if line:
            db.delete(line)
        db.flush()
        return cart
    if line:
        line.quantity = quantity
    else:
        db.add(
            CartLine(
                cart_id=cart.id,
                canteen_id=cart.canteen_id,
                variant_id=variant.id,
                quantity=quantity,
            )
        )
    db.flush()
    return cart


def clear(db, student_id):
    cart = active_cart(db, student_id, lock=True)
    if cart:
        for line in db.scalars(select(CartLine).where(CartLine.cart_id == cart.id)):
            db.delete(line)
    db.flush()


def view(db, student_id):
    cart = active_cart(db, student_id)
    if not cart:
        return {"canteen_id": None, "lines": [], "total_paise": 0}
    rows = list(db.scalars(select(CartLine).where(CartLine.cart_id == cart.id)))
    variants = {
        variant.id: variant
        for variant in db.scalars(
            select(MenuVariant).where(MenuVariant.id.in_([row.variant_id for row in rows]))
        )
    }
    items = {
        item.id: item
        for item in db.scalars(select(MenuItem).where(MenuItem.canteen_id == cart.canteen_id))
    }
    stations = {
        station.id: station
        for station in db.scalars(select(Station).where(Station.canteen_id == cart.canteen_id))
    }
    canteen = db.get(Canteen, cart.canteen_id)
    lines = []
    total = 0
    for row in rows:
        variant = variants[row.variant_id]
        item = items[variant.item_id]
        price = variant.price_paise
        line_total = price * row.quantity if price else None
        if line_total is not None:
            total += line_total
        lines.append(
            {
                "variant_id": variant.id,
                "item_name": item.name,
                "variant": variant.label,
                "quantity": row.quantity,
                "unit_price_paise": price,
                "line_total_paise": line_total,
                "orderable": bool(
                    canteen
                    and canteen.approved
                    and variant.verified
                    and variant.available
                    and price
                    and (station := stations.get(variant.station_id))
                    and station.active
                ),
            }
        )
    return {"canteen_id": cart.canteen_id, "lines": lines, "total_paise": total}
