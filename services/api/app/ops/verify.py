"""Database integrity check for restore drills and scheduled production checks.

    DATABASE_URL=... python -m app.ops.verify        # exit code 1 if any check fails

Read-only. Reports counts and the ids of offending rows, never personal data.
"""

import os
import sys
from pathlib import Path

from sqlalchemy import func, select

from app.core.db import connect, session_for
from app.modules.orders.models import Order, OrderLine, PickupCredential
from app.modules.payments.models import PaymentAttempt, Refund
from app.modules.reviews.models import Review

ACTIVE = ("PAID_ACTIVE", "PARTIALLY_COLLECTED")


def migration_problems(connection):
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory

    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    head = ScriptDirectory.from_config(config).get_current_head()
    current = MigrationContext.configure(connection).get_current_revision()
    return [] if current == head else [f"schema at {current}, expected {head}"]


def check(db, check_migrations=True):
    problems = {}

    def fail(name, ids):
        ids = sorted(ids)
        if ids:
            problems[name] = ids[:20] + ([f"... {len(ids) - 20} more"] if len(ids) > 20 else [])

    if check_migrations:
        fail("migrations", migration_problems(db.connection()))

    line_totals = dict(
        db.execute(
            select(
                OrderLine.order_id, func.sum(OrderLine.unit_price_paise * OrderLine.quantity)
            ).group_by(OrderLine.order_id)
        ).all()
    )
    orders = list(db.scalars(select(Order)))
    fail("order_total_mismatch", [o.id for o in orders if line_totals.get(o.id) != o.total_paise])

    incomplete = set(
        db.scalars(select(OrderLine.order_id).where(OrderLine.fulfilled < OrderLine.quantity))
    )
    fail(
        "collected_with_open_lines",
        [o.id for o in orders if o.state == "COLLECTED" and o.id in incomplete],
    )

    state = {o.id: o.state for o in orders}
    active_codes = db.scalars(
        select(PickupCredential.order_id).where(PickupCredential.active.is_(True))
    )
    fail(
        "active_code_on_closed_order", [oid for oid in active_codes if state.get(oid) not in ACTIVE]
    )

    captured = {}
    for attempt in db.scalars(select(PaymentAttempt).where(PaymentAttempt.status == "CAPTURED")):
        captured.setdefault(attempt.order_id, []).append(attempt)
    paid = [o for o in orders if o.payment_verified_at is not None]
    fail(
        "paid_order_payment_mismatch",
        [
            o.id
            for o in paid
            if len(captured.get(o.id, [])) != 1 or captured[o.id][0].amount_paise != o.total_paise
        ],
    )
    fail(
        "capture_without_paid_order",
        [oid for oid in captured if state.get(oid) is None or oid not in {o.id for o in paid}],
    )

    refunded = dict(
        db.execute(
            select(Refund.payment_attempt_id, func.sum(Refund.amount_paise))
            .where(Refund.status != "FAILED")
            .group_by(Refund.payment_attempt_id)
        ).all()
    )
    amounts = dict(db.execute(select(PaymentAttempt.id, PaymentAttempt.amount_paise)).all())
    fail(
        "refund_exceeds_payment", [a for a, total in refunded.items() if total > amounts.get(a, 0)]
    )

    counts = {
        "orders": len(orders),
        "order_lines": db.scalar(select(func.count()).select_from(OrderLine)),
        "captured_payments": sum(len(v) for v in captured.values()),
        "refunds": db.scalar(select(func.count()).select_from(Refund)),
        "reviews": db.scalar(select(func.count()).select_from(Review)),
    }
    return counts, problems


def main():
    engine = connect(os.environ["DATABASE_URL"])
    with session_for(engine) as db:
        counts, problems = check(db)
    print("counts:", counts)
    if problems:
        for name, ids in problems.items():
            print(f"FAIL {name}: {ids}")
        sys.exit(1)
    print("OK: all integrity checks passed")


if __name__ == "__main__":
    main()
