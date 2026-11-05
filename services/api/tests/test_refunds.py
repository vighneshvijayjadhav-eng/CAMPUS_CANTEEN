"""Cancellation and refund tests against the fake Razorpay API (see test_payments)."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_api import ORIGIN, PASSWORD
from test_payments import confirm, order_state, place_order, start, webhook

from app.modules.orders.models import Order
from app.modules.orders.service import StaffScope, confirm_line, lines_for
from app.modules.payments.models import Refund
from app.modules.payments.refunds import reconcile_refunds, retry_refund

LATER = timedelta(minutes=5)


def paid_order(s, quantity=2):
    order_id = place_order(s, quantity)
    params = start(s, order_id)
    payment_id = s.fake.pay(params["provider_order_id"])
    assert confirm(s, order_id, params["provider_order_id"], payment_id).status_code == 200
    return order_id, params, payment_id


def cancel(s, order_id):
    return s.client.post(f"/api/v1/student/orders/{order_id}/cancel")


def refunds(s, order_id=None):
    with Session(s.engine) as db:
        query = select(Refund).order_by(Refund.created_at)
        if order_id:
            query = query.where(Refund.order_id == order_id)
        return db.scalars(query).all()


def reconcile(s):
    with Session(s.engine) as db, db.begin():
        return reconcile_refunds(db, s.providers, datetime.now(UTC) + LATER)


def staff_login(s, username="admin"):
    response = s.client.post(
        "/api/v1/auth/staff/login",
        headers={"Origin": ORIGIN},
        json={"username": username, "password": PASSWORD, "device_name": "Counter"},
    )
    assert response.status_code == 200, response.text


def test_student_cancel_refunds_and_webhook_confirms(pay_setup):
    s = pay_setup
    order_id, _, payment_id = paid_order(s)
    response = cancel(s, order_id)
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["state"] == "CANCELLED" and detail["pickup_code"] is None
    assert detail["refund_status"] == "PENDING"
    [refund] = detail["refunds"]
    assert (refund["status"], refund["reason"], refund["amount_paise"]) == (
        "PENDING",
        "STUDENT_CANCELLED",
        8000,
    )
    [provider_refund] = s.fake.refunds.values()
    assert provider_refund["payment_id"] == payment_id
    assert provider_refund["receipt"] == refund["id"]
    # Cancelling again changes nothing and never refunds twice.
    assert cancel(s, order_id).json()["refunds"] == detail["refunds"]
    assert len(s.fake.refunds) == 1
    provider_refund["status"] = "processed"
    body, sig = s.fake.refund_webhook("refund.processed", provider_refund["id"])
    assert webhook(s, body, sig, "evt_r1").json() == {"result": "REFUND_PROCESSED"}
    assert webhook(s, body, sig, "evt_r1").json() == {"result": "DUPLICATE"}
    final = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert final["refund_status"] == "REFUNDED"
    assert final["refunds"][0]["status"] == "PROCESSED"
    # A late failed event cannot undo a processed refund.
    provider_refund["status"] = "failed"
    body, sig = s.fake.refund_webhook("refund.failed", provider_refund["id"])
    assert webhook(s, body, sig, "evt_r2").json() == {"result": "REFUND_PROCESSED"}


def test_cancellation_window_is_five_minutes(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    with Session(s.engine) as db, db.begin():
        db.get(Order, order_id).payment_verified_at = datetime.now(UTC) - timedelta(minutes=6)
    response = cancel(s, order_id)
    assert response.json() == {"error": "CANCELLATION_WINDOW_CLOSED"}
    assert order_state(s, order_id) == "PAID_ACTIVE" and refunds(s) == []


def test_refund_survives_provider_outage_and_is_polled_to_completion(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    s.fake.refund_mode = "down"
    detail = cancel(s, order_id).json()
    assert detail["state"] == "CANCELLED" and detail["refund_status"] == "REQUESTED"
    assert detail["refunds"][0]["last_error"] == "PAYMENT_PROVIDER_UNAVAILABLE"
    s.fake.refund_mode = "pending"
    [(refund_id, status)] = reconcile(s).items()
    assert status == "PENDING"
    next(iter(s.fake.refunds.values()))["status"] = "processed"
    assert reconcile(s) == {refund_id: "PROCESSED"}
    assert s.client.get(f"/api/v1/student/orders/{order_id}").json()["refund_status"] == (
        "REFUNDED"
    )
    assert reconcile(s) == {}


def test_reconciliation_adopts_a_refund_razorpay_already_made(pay_setup):
    s = pay_setup
    order_id, _, payment_id = paid_order(s)
    s.fake.refund_mode = "down"
    refund_id = cancel(s, order_id).json()["refunds"][0]["id"]
    # Razorpay accepted an earlier submission whose response was lost.
    s.fake.refunds["rfnd_Lost"] = {
        "id": "rfnd_Lost",
        "payment_id": payment_id,
        "amount": 8000,
        "receipt": refund_id,
        "status": "pending",
    }
    s.fake.refund_mode = "pending"
    assert reconcile(s) == {refund_id: "PENDING"}
    assert len(s.fake.refunds) == 1
    assert refunds(s)[0].provider_refund_id == "rfnd_Lost"


def test_rejected_refund_fails_visibly_and_admin_can_retry(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    s.fake.refund_mode = "reject"
    detail = cancel(s, order_id).json()
    assert detail["refund_status"] == "FAILED"
    failed_id = detail["refunds"][0]["id"]
    s.fake.refund_mode = "pending"
    staff_login(s, "juice")
    denied = s.client.post(f"/api/v1/staff/refunds/{failed_id}/retry", headers={"Origin": ORIGIN})
    assert denied.status_code == 403
    staff_login(s)
    listing = s.client.get("/api/v1/staff/refunds").json()
    assert [row["status"] for row in listing] == ["FAILED"]
    retried = s.client.post(f"/api/v1/staff/refunds/{failed_id}/retry", headers={"Origin": ORIGIN})
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "PENDING"
    assert [r.status for r in refunds(s, order_id)] == ["FAILED", "PENDING"]
    with Session(s.engine) as db, db.begin():
        scope = StaffScope("admin", "session", s.ids["coe"], None, "admin")
        try:
            retry_refund(db, s.providers, scope, failed_id, datetime.now(UTC))
        except Exception as error:  # the open refund blocks a second retry
            assert getattr(error, "code", None) == "REFUND_NOT_RETRYABLE"


def test_abandoned_order_paid_late_is_refunded(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    assert cancel(s, order_id).json()["state"] == "CANCELLED"
    body, sig = s.fake.webhook("payment.captured", s.fake.pay(params["provider_order_id"]))
    assert webhook(s, body, sig, "evt_late").json() == {"result": "CAPTURED_UNAPPLIED"}
    [refund] = refunds(s, order_id)
    assert (refund.reason, refund.status, refund.requested_by_kind) == (
        "DUPLICATE_PAYMENT",
        "REQUESTED",
        "system",
    )
    assert reconcile(s) == {refund.id: "PENDING"}
    detail = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert detail["state"] == "CANCELLED" and detail["refund_status"] is None


def test_wrong_amount_capture_refunds_what_was_captured(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    body, sig = s.fake.webhook(
        "payment.captured", s.fake.pay(params["provider_order_id"], amount=100)
    )
    assert webhook(s, body, sig, "evt_amt").json() == {"result": "AMOUNT_MISMATCH"}
    [refund] = refunds(s, order_id)
    assert (refund.reason, refund.amount_paise) == ("AMOUNT_MISMATCH", 100)
    assert order_state(s, order_id) == "PAYMENT_PENDING"


def test_admin_cancel_and_refund_only_before_any_handover(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    staff_login(s, "juice")
    path = f"/api/v1/staff/orders/{order_id}/cancel"
    note = {"note": "Closing time; student agreed by phone"}
    assert s.client.post(path, headers={"Origin": ORIGIN}, json=note).status_code == 403
    staff_login(s)
    assert s.client.post(path, headers={"Origin": ORIGIN}, json={"note": " "}).status_code == 422
    response = s.client.post(path, headers={"Origin": ORIGIN}, json=note)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["state"] == "CANCELLED" and body["refund_status"] == "PENDING"
    assert body["refund"]["reason"] == "STAFF_CANCELLED"
    assert body["refund"]["note"] == note["note"]

    partial_id, *_ = paid_order(s)
    with Session(s.engine) as db, db.begin():
        line = lines_for(db, partial_id)[0]
        scope = StaffScope("staff", "device", s.ids["coe"], s.ids["juice"], "station")
        confirm_line(db, scope, partial_id, line.id, 1, 0, str(uuid4()))
    blocked = s.client.post(
        f"/api/v1/staff/orders/{partial_id}/cancel", headers={"Origin": ORIGIN}, json=note
    )
    assert blocked.json() == {"error": "PARTIAL_REFUND_POLICY_REQUIRED"}
    # A student cancelling a partly collected order gets staff review, not a refund.
    detail = cancel(s, partial_id).json()
    assert detail["state"] == "PARTIALLY_COLLECTED"
    assert detail["exception_status"] == "STAFF_REVIEW_REQUIRED"
    assert detail["refunds"] == []
