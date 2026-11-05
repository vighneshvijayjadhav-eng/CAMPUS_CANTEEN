"""Canteen sales reporting. All money is integer paise; periods use India time.

- gross: payments captured for orders (CAPTURED attempts), by capture time
- refunds: completed (Razorpay-confirmed) refunds of cancelled orders, by completion time
- net: gross - refunds
- other_refunds: completed refunds of money that never became a sale (duplicate or
  wrong-amount payments); shown separately so totals reconcile with the gateway
Item-wise sales cover paid orders in the range that were not cancelled.
"""

from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.menu.schedule import CANTEEN_TZ
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.service import instant
from app.modules.payments.models import PaymentAttempt, Refund

MAX_DAYS = 366
ORDER_REASONS = ("STUDENT_CANCELLED", "STAFF_CANCELLED")


def period_key(moment, group):
    local = instant(moment).astimezone(CANTEEN_TZ).date()
    if group == "day":
        return local.isoformat()
    if group == "week":
        monday = local - timedelta(days=local.weekday())
        return monday.isoformat()  # week starting Monday
    return local.strftime("%Y-%m")


def bounds(start, end):
    if end < start:
        raise DomainError("INVALID_DATE_RANGE", 422)
    if (end - start).days + 1 > MAX_DAYS:
        raise DomainError("DATE_RANGE_TOO_LONG", 422)
    # Compare in UTC, the form timestamps are stored in.
    begin = datetime.combine(start, time.min, CANTEEN_TZ).astimezone(UTC)
    finish = datetime.combine(end + timedelta(days=1), time.min, CANTEEN_TZ).astimezone(UTC)
    return begin, finish


def sales_report(db, canteen_id, start: date, end: date, group="day"):
    begin, finish = bounds(start, end)
    periods = {}

    def bucket(key):
        return periods.setdefault(
            key,
            {
                "period": key,
                "orders": 0,
                "gross_paise": 0,
                "refunds_paise": 0,
                "other_refunds_paise": 0,
            },
        )

    for attempt in db.scalars(
        select(PaymentAttempt).where(
            PaymentAttempt.canteen_id == canteen_id,
            PaymentAttempt.status == "CAPTURED",
            PaymentAttempt.captured_at >= begin,
            PaymentAttempt.captured_at < finish,
        )
    ):
        row = bucket(period_key(attempt.captured_at, group))
        row["orders"] += 1
        row["gross_paise"] += attempt.amount_paise

    for refund in db.scalars(
        select(Refund).where(
            Refund.canteen_id == canteen_id,
            Refund.status == "PROCESSED",
            Refund.processed_at >= begin,
            Refund.processed_at < finish,
        )
    ):
        row = bucket(period_key(refund.processed_at, group))
        field = "refunds_paise" if refund.reason in ORDER_REASONS else "other_refunds_paise"
        row[field] += refund.amount_paise

    rows = sorted(periods.values(), key=lambda row: row["period"])
    for row in rows:
        row["net_paise"] = row["gross_paise"] - row["refunds_paise"]

    items = {}
    for line in db.scalars(
        select(OrderLine)
        .join(Order, Order.id == OrderLine.order_id)
        .where(
            Order.canteen_id == canteen_id,
            Order.payment_verified_at >= begin,
            Order.payment_verified_at < finish,
            Order.state != "CANCELLED",
        )
    ):
        key = (line.name, line.variant_label)
        entry = items.setdefault(
            key,
            {"item": line.name, "variant": line.variant_label, "quantity": 0, "revenue_paise": 0},
        )
        entry["quantity"] += line.quantity
        entry["revenue_paise"] += line.quantity * line.unit_price_paise

    totals = {
        field: sum(row[field] for row in rows)
        for field in ("orders", "gross_paise", "refunds_paise", "other_refunds_paise", "net_paise")
    }
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "group": group,
        "timezone": "Asia/Kolkata",
        "periods": rows,
        "totals": totals,
        "items": sorted(
            items.values(), key=lambda e: (-e["revenue_paise"], e["item"], e["variant"])
        ),
    }
