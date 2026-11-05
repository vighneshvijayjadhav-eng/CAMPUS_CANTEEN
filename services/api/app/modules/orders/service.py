from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, text

from app.core.errors import DomainError
from app.modules.orders.models import (
    FulfillmentEvent,
    Order,
    OrderException,
    OrderLine,
    PickupCredential,
    QueueEvent,
)


@dataclass(frozen=True)
class StaffScope:
    actor_id: str
    session_id: str
    canteen_id: str
    station_id: str | None
    role: str

    def permits(self, line):
        return line.canteen_id == self.canteen_id and (
            self.role == "admin" or (self.role == "station" and self.station_id == line.station_id)
        )


def server_now(db):
    if db.bind.dialect.name == "postgresql":
        return db.scalar(text("SELECT clock_timestamp()"))
    # SQLite is only used by unit tests; production configuration requires PostgreSQL.
    return datetime.now(UTC)


def instant(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value


def locked_order(db, order_id, canteen_id=None, student_id=None):
    query = select(Order).where(Order.id == order_id)
    if canteen_id is not None:
        query = query.where(Order.canteen_id == canteen_id)
    if student_id is not None:
        query = query.where(Order.student_id == student_id)
    order = db.scalar(query.with_for_update().execution_options(populate_existing=True))
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", 404)
    return order


def lines_for(db, order_id):
    return list(
        db.scalars(
            select(OrderLine)
            .where(OrderLine.order_id == order_id)
            .execution_options(populate_existing=True)
        )
    )


def notify(db, order, lines, kind):
    for station_id in {line.station_id for line in lines}:
        db.add(
            QueueEvent(
                canteen_id=order.canteen_id, station_id=station_id, order_id=order.id, kind=kind
            )
        )


def deactivate(db, order_id):
    credential = db.get(PickupCredential, order_id)
    if credential:
        credential.active = False
        credential.encrypted_code = None


def confirm_line(db, scope, order_id, line_id, quantity, expected_fulfilled, request_id):
    """Caller owns the transaction. All order mutations acquire this same parent lock."""
    order = locked_order(db, order_id, canteen_id=scope.canteen_id)
    lines = lines_for(db, order_id)
    line = next((line for line in lines if line.id == line_id), None)
    if line is None or not scope.permits(line):
        raise DomainError("LINE_NOT_FOUND", 404)
    event = db.scalar(
        select(FulfillmentEvent).where(
            FulfillmentEvent.order_id == order_id, FulfillmentEvent.request_id == request_id
        )
    )
    if event:
        if (
            event.line_id,
            event.quantity,
            event.expected_fulfilled,
            event.actor_id,
            event.session_id,
        ) != (line_id, quantity, expected_fulfilled, scope.actor_id, scope.session_id):
            raise DomainError("IDEMPOTENCY_CONFLICT")
        return order
    if order.state not in ("PAID_ACTIVE", "PARTIALLY_COLLECTED") or not order.payment_verified_at:
        raise DomainError("ORDER_NOT_COLLECTABLE")
    if type(quantity) is not int or quantity <= 0 or type(expected_fulfilled) is not int:
        raise DomainError("INVALID_QUANTITY", 422)
    if line.fulfilled != expected_fulfilled:
        raise DomainError("STALE_FULFILLMENT")
    if quantity > line.quantity - line.fulfilled:
        raise DomainError("QUANTITY_EXCEEDS_REMAINING")
    line.fulfilled += quantity
    db.add(
        FulfillmentEvent(
            order_id=order_id,
            line_id=line_id,
            request_id=request_id,
            actor_id=scope.actor_id,
            session_id=scope.session_id,
            quantity=quantity,
            expected_fulfilled=expected_fulfilled,
            occurred_at=server_now(db),
        )
    )
    order.state = (
        "COLLECTED"
        if all(row.fulfilled == row.quantity for row in lines)
        else "PARTIALLY_COLLECTED"
    )
    if order.state == "COLLECTED":
        deactivate(db, order_id)
    notify(db, order, lines, "FULFILLMENT_UPDATED")
    db.flush()
    return order


def cancel_order(db, student_id, order_id):
    order = locked_order(db, order_id, student_id=student_id)
    if order.state == "CANCELLED":
        return order
    if order.state == "PAYMENT_PENDING":
        # Abandoned before payment: nothing to refund. A capture arriving later is refunded.
        order.state = "CANCELLED"
        db.flush()
        return order
    if order.state not in ("PAID_ACTIVE", "PARTIALLY_COLLECTED") or not order.payment_verified_at:
        raise DomainError("ORDER_NOT_CANCELLABLE")
    now = server_now(db)
    if now >= instant(order.payment_verified_at) + timedelta(minutes=5):
        raise DomainError("CANCELLATION_WINDOW_CLOSED")
    lines = lines_for(db, order_id)
    if any(line.fulfilled for line in lines):
        if not db.get(OrderException, order_id):
            db.add(
                OrderException(
                    order_id=order_id,
                    requested_by=student_id,
                    reason="CANCELLATION_AFTER_PARTIAL_HANDOVER",
                    created_at=now,
                )
            )
        order.exception_status = "STAFF_REVIEW_REQUIRED"
        # No financial adjustment is allowed until the partial-refund policy is approved.
        notify(db, order, lines, "EXCEPTION_REQUESTED")
    else:
        order.state = "CANCELLED"
        order.refund_status = "REQUESTED"
        deactivate(db, order_id)
        notify(db, order, lines, "CANCELLED")
    db.flush()
    return order


def staff_cancel_order(db, scope, order_id):
    """Admin cancellation of a paid order with nothing handed over (e.g. at closing time after
    contacting the student). Partly collected orders stay in the exception workflow."""
    if scope.role != "admin":
        raise DomainError("ADMIN_REQUIRED", 403)
    order = locked_order(db, order_id, canteen_id=scope.canteen_id)
    if order.state == "CANCELLED":
        return order
    if order.state == "PARTIALLY_COLLECTED":
        raise DomainError("PARTIAL_REFUND_POLICY_REQUIRED")
    if order.state != "PAID_ACTIVE" or not order.payment_verified_at:
        raise DomainError("ORDER_NOT_CANCELLABLE")
    lines = lines_for(db, order_id)
    if any(line.fulfilled for line in lines):
        raise DomainError("PARTIAL_REFUND_POLICY_REQUIRED")
    order.state = "CANCELLED"
    order.refund_status = "REQUESTED"
    deactivate(db, order_id)
    notify(db, order, lines, "CANCELLED")
    db.flush()
    return order


def order_view(db, order, scope=None):
    lines = lines_for(db, order.id)
    if scope:
        lines = [line for line in lines if scope.permits(line)]
    return {
        "id": order.id,
        "state": order.state,
        "exception_status": order.exception_status,
        "refund_status": order.refund_status,
        "lines": [
            {
                "id": line.id,
                "name": line.name,
                "variant": line.variant_label,
                "station_id": line.station_id,
                "station": line.station_name,
                "quantity": line.quantity,
                "fulfilled": line.fulfilled,
                "remaining": line.quantity - line.fulfilled,
            }
            for line in lines
        ],
    }


def active_queue(db, scope):
    query = (
        select(Order)
        .join(OrderLine, OrderLine.order_id == Order.id)
        .where(
            Order.canteen_id == scope.canteen_id,
            Order.state.in_(["PAID_ACTIVE", "PARTIALLY_COLLECTED"]),
            Order.payment_verified_at.is_not(None),
            OrderLine.fulfilled < OrderLine.quantity,
        )
    )
    if scope.role != "admin":
        if scope.role != "station" or scope.station_id is None:
            raise DomainError("FORBIDDEN", 403)
        query = query.where(OrderLine.station_id == scope.station_id)
    return [
        order_view(db, order, scope)
        for order in db.scalars(query.distinct().order_by(Order.payment_verified_at, Order.id))
    ]
