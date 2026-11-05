"""In-app notifications and sales reports (uses pay_setup from conftest)."""

from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_api import ORIGIN
from test_refunds import cancel, paid_order, staff_login

from app.modules.notifications.service import inbox
from app.modules.orders.models import Order
from app.modules.orders.service import StaffScope, confirm_line, lines_for
from app.modules.payments.models import PaymentAttempt, Refund
from app.modules.reports.service import sales_report


def kinds(s):
    return [item["kind"] for item in s.client.get("/api/v1/student/notifications").json()["items"]]


def hand_over(s, order_id, quantity):
    with Session(s.engine) as db, db.begin():
        line = lines_for(db, order_id)[0]
        scope = StaffScope("staff", "device", s.ids["coe"], s.ids["juice"], "station")
        confirm_line(db, scope, order_id, line.id, quantity, line.fulfilled, str(uuid4()))


def test_order_lifecycle_fills_the_inbox(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s, quantity=2)
    hand_over(s, order_id, 1)
    hand_over(s, order_id, 1)
    assert kinds(s) == ["ORDER_COLLECTED", "ORDER_PARTLY_COLLECTED", "PAYMENT_CONFIRMED"]
    box = s.client.get("/api/v1/student/notifications").json()
    assert box["unread"] == 3
    assert (
        box["items"][-1]["body"] == "COE Canteen: ₹80 paid. Show your pickup code at the counter."
    )
    assert all(item["order_id"] == order_id for item in box["items"])
    after = s.client.post("/api/v1/student/notifications/read").json()
    assert after["unread"] == 0 and all(item["read"] for item in after["items"])
    with Session(s.engine) as db:
        assert inbox(db, "someone-else") == {"unread": 0, "items": []}


def test_cancellation_and_refund_notifications(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    cancel(s, order_id)
    [provider_refund] = s.fake.refunds.values()
    provider_refund["status"] = "processed"
    body, sig = s.fake.refund_webhook("refund.processed", provider_refund["id"])
    s.client.post(
        f"/api/v1/payments/razorpay/webhooks/{s.ids['merchant']}",
        content=body,
        headers={"X-Razorpay-Signature": sig, "X-Razorpay-Event-Id": "evt_n1"},
    )
    assert kinds(s)[:2] == ["REFUND_COMPLETED", "ORDER_CANCELLED"]

    staff_order, *_ = paid_order(s)
    s.fake.refund_mode = "reject"
    s.fake.reject_message = "The refund amount provided is greater than amount captured"
    staff_login(s)
    s.client.post(
        f"/api/v1/staff/orders/{staff_order}/cancel",
        headers={"Origin": ORIGIN},
        json={"note": "Closing time"},
    )
    assert kinds(s)[:2] == ["REFUND_FAILED", "ORDER_CANCELLED_BY_CANTEEN"]


def set_times(s, order_id, paid_at, refunded_at=None):
    with Session(s.engine) as db, db.begin():
        db.get(Order, order_id).payment_verified_at = paid_at
        for attempt in db.scalars(
            select(PaymentAttempt).where(PaymentAttempt.order_id == order_id)
        ):
            attempt.captured_at = paid_at
        for refund in db.scalars(select(Refund).where(Refund.order_id == order_id)):
            refund.status, refund.processed_at = "PROCESSED", refunded_at


def test_sales_report_uses_india_days_and_separates_refunds(pay_setup):
    s = pay_setup
    kept, *_ = paid_order(s, quantity=2)  # ₹80
    late, *_ = paid_order(s, quantity=1)  # ₹40
    refunded, *_ = paid_order(s, quantity=3)  # ₹120, cancelled and refunded
    cancel(s, refunded)
    set_times(s, kept, datetime(2026, 11, 5, 6, 30, tzinfo=UTC))  # 12:00 IST on 5 Nov
    set_times(s, late, datetime(2026, 11, 5, 19, 0, tzinfo=UTC))  # 00:30 IST on 6 Nov
    set_times(
        s,
        refunded,
        datetime(2026, 11, 5, 7, 0, tzinfo=UTC),
        datetime(2026, 11, 6, 5, 0, tzinfo=UTC),
    )
    with Session(s.engine) as db:
        report = sales_report(db, s.ids["coe"], date(2026, 11, 5), date(2026, 11, 6), "day")
    assert report["periods"] == [
        {
            "period": "2026-11-05",
            "orders": 2,
            "gross_paise": 20000,
            "refunds_paise": 0,
            "other_refunds_paise": 0,
            "net_paise": 20000,
        },
        {
            "period": "2026-11-06",
            "orders": 1,
            "gross_paise": 4000,
            "refunds_paise": 12000,
            "other_refunds_paise": 0,
            "net_paise": -8000,
        },
    ]
    assert report["totals"]["net_paise"] == 12000
    # Cancelled orders are not item sales.
    assert report["items"] == [
        {"item": "Coffee", "variant": "Regular", "quantity": 3, "revenue_paise": 12000}
    ]
    with Session(s.engine) as db:
        only_fifth = sales_report(db, s.ids["coe"], date(2026, 11, 5), date(2026, 11, 5), "day")
        monthly = sales_report(db, s.ids["coe"], date(2026, 11, 1), date(2026, 11, 30), "month")
        weekly = sales_report(db, s.ids["coe"], date(2026, 11, 1), date(2026, 11, 30), "week")
    assert [p["period"] for p in only_fifth["periods"]] == ["2026-11-05"]
    assert [p["period"] for p in monthly["periods"]] == ["2026-11"]
    assert [p["period"] for p in weekly["periods"]] == ["2026-11-02"]  # Monday of that week


def test_report_endpoint_validates_and_is_admin_only(pay_setup):
    s = pay_setup
    staff_login(s, "juice")
    url = "/api/v1/staff/reports/sales?start=2026-11-01&end=2026-11-30"
    assert s.client.get(url).status_code == 403
    staff_login(s)
    assert s.client.get(url).json()["totals"]["orders"] == 0
    backwards = s.client.get("/api/v1/staff/reports/sales?start=2026-11-30&end=2026-11-01")
    assert backwards.json() == {"error": "INVALID_DATE_RANGE"}
    too_long = s.client.get("/api/v1/staff/reports/sales?start=2025-01-01&end=2026-11-30")
    assert too_long.json() == {"error": "DATE_RANGE_TOO_LONG"}
    assert s.client.get(url + "&group=year").status_code == 422
