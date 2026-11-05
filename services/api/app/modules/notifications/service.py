from sqlalchemy import func, select, update

from app.modules.menu.models import Canteen
from app.modules.notifications.models import StudentNotification


def rupees(paise):
    return f"₹{paise // 100}" + (f".{paise % 100:02d}" if paise % 100 else "")


MESSAGES = {
    "PAYMENT_CONFIRMED": (
        "Payment confirmed",
        "{canteen}: {amount} paid. Show your pickup code at the counter.",
    ),
    "ORDER_PARTLY_COLLECTED": (
        "Partly collected",
        "{canteen}: some items handed over. Use the same code for the rest.",
    ),
    "ORDER_COLLECTED": ("Order collected", "{canteen}: everything has been handed over. Enjoy!"),
    "ORDER_CANCELLED": (
        "Order cancelled",
        "{canteen}: your order was cancelled. Any payment is being refunded.",
    ),
    "ORDER_CANCELLED_BY_CANTEEN": (
        "Cancelled by the canteen",
        "{canteen} cancelled your order. {amount} is being refunded.",
    ),
    "CANCELLATION_REVIEW": (
        "Cancellation under review",
        "{canteen}: some items were already handed over, so staff will contact you.",
    ),
    "EXTRA_PAYMENT_REFUND": (
        "Extra payment will be refunded",
        "{canteen}: we received a payment we couldn't use. It is being refunded.",
    ),
    "REFUND_COMPLETED": ("Refund completed", "{amount} has been refunded to your payment method."),
    "REFUND_FAILED": (
        "Refund problem",
        "A refund of {amount} failed. The canteen will contact you.",
    ),
}


def notify(db, order, kind, now, amount_paise=None):
    """Add an inbox entry for the order's student. Caller owns the transaction."""
    title, template = MESSAGES[kind]
    canteen = db.get(Canteen, order.canteen_id)
    db.add(
        StudentNotification(
            student_id=order.student_id,
            order_id=order.id,
            kind=kind,
            title=title,
            body=template.format(
                canteen=canteen.name if canteen else "Canteen",
                amount=rupees(amount_paise if amount_paise is not None else order.total_paise),
            )[:300],
            created_at=now,
        )
    )


def inbox(db, student_id, limit=50):
    rows = db.scalars(
        select(StudentNotification)
        .where(StudentNotification.student_id == student_id)
        .order_by(StudentNotification.id.desc())
        .limit(limit)
    )
    unread = db.scalar(
        select(func.count())
        .select_from(StudentNotification)
        .where(
            StudentNotification.student_id == student_id,
            StudentNotification.read_at.is_(None),
        )
    )
    return {
        "unread": unread,
        "items": [
            {
                "id": row.id,
                "order_id": row.order_id,
                "kind": row.kind,
                "title": row.title,
                "body": row.body,
                "created_at": row.created_at,
                "read": row.read_at is not None,
            }
            for row in rows
        ],
    }


def mark_all_read(db, student_id, now):
    db.execute(
        update(StudentNotification)
        .where(
            StudentNotification.student_id == student_id,
            StudentNotification.read_at.is_(None),
        )
        .values(read_at=now)
    )
