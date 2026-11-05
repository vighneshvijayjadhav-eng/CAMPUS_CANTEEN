"""CI restore drill: insert a small, internally consistent set of orders, payments and a refund
into DATABASE_URL (after migrations and seed), so the dump/restore check has real rows."""

import os
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.db import connect, session_for
from app.modules.identity.models import Student
from app.modules.menu.models import Canteen, MenuVariant, Station
from app.modules.orders.models import Order, OrderLine
from app.modules.payments.models import MerchantAccount, PaymentAttempt, Refund

now = datetime.now(UTC)
with session_for(connect(os.environ["DATABASE_URL"])) as db, db.begin():
    canteen = db.scalar(select(Canteen).where(Canteen.slug == "coe"))
    station = Station(canteen_id=canteen.id, name="Drill station")
    student = Student(google_sub="drill", email="drill@example.test", display_name="Drill")
    db.add_all([station, student])
    db.flush()
    variant = db.scalar(select(MenuVariant).where(MenuVariant.canteen_id == canteen.id).limit(1))
    account = MerchantAccount(
        canteen_id=canteen.id,
        provider="razorpay",
        key_id="rzp_test_drill",
        mode="test",
        display_name="Drill",
        active=False,
        created_at=now,
    )
    db.add(account)
    db.flush()
    for n, state in enumerate(["COLLECTED", "CANCELLED", "PAID_ACTIVE"]):
        order = Order(
            canteen_id=canteen.id,
            student_id=student.id,
            state=state,
            total_paise=5000,
            payment_verified_at=now,
            created_at=now,
            refund_status="REFUNDED" if state == "CANCELLED" else None,
        )
        db.add(order)
        db.flush()
        db.add(
            OrderLine(
                canteen_id=canteen.id,
                order_id=order.id,
                station_id=station.id,
                station_name=station.name,
                variant_id=variant.id,
                name="Drill item",
                variant_label="Regular",
                unit_price_paise=2500,
                quantity=2,
                fulfilled=2 if state == "COLLECTED" else 0,
            )
        )
        attempt = PaymentAttempt(
            canteen_id=canteen.id,
            order_id=order.id,
            merchant_account_id=account.id,
            provider_order_id=f"order_Drill{n}",
            provider_payment_id=f"pay_Drill{n}",
            amount_paise=5000,
            status="CAPTURED",
            created_at=now,
            captured_at=now,
        )
        db.add(attempt)
        db.flush()
        if state == "CANCELLED":
            db.add(
                Refund(
                    canteen_id=canteen.id,
                    order_id=order.id,
                    payment_attempt_id=attempt.id,
                    merchant_account_id=account.id,
                    amount_paise=5000,
                    reason="STUDENT_CANCELLED",
                    status="PROCESSED",
                    provider_refund_id="rfnd_Drill",
                    requested_by_kind="student",
                    requested_by=student.id,
                    created_at=now,
                    processed_at=now,
                    submit_attempts=1,
                )
            )
print("drill data inserted")
