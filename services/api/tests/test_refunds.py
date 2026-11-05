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


def at(when):
    return datetime.now(UTC) + when


def reconcile_at(s, moment):
    with Session(s.engine) as db, db.begin():
        return reconcile_refunds(db, s.providers, moment)


def test_temporary_rejection_is_retried_until_it_succeeds(pay_setup):
    """Seen in the Razorpay sandbox: refunds above the merchant balance are refused with
    "invalid request sent". They must wait and retry, not fail."""
    s = pay_setup
    order_id, *_ = paid_order(s)
    s.fake.refund_mode = "reject"
    detail = cancel(s, order_id).json()
    [refund] = detail["refunds"]
    assert detail["state"] == "CANCELLED" and detail["refund_status"] == "REQUESTED"
    assert refund["retrying"] is True and refund["next_attempt_at"]
    assert (
        refund["last_error"] == "PAYMENT_PROVIDER_REJECTED: BAD_REQUEST_ERROR: invalid request sent"
    )
    assert "REFUND_FAILED" not in [
        n["kind"] for n in s.client.get("/api/v1/student/notifications").json()["items"]
    ]
    # Not due yet: nothing is sent before the backoff time.
    assert reconcile_at(s, at(timedelta(minutes=1))) == {}
    # Still refused at the first retry: rescheduled further out, still REQUESTED.
    assert reconcile_at(s, at(timedelta(minutes=6))) == {refund["id"]: "REQUESTED"}
    with Session(s.engine) as db:
        row = db.get(Refund, refund["id"])
        assert row.submit_attempts == 2 and row.next_attempt_at is not None
    # Balance arrives (settlement): the next due retry succeeds on the same row.
    s.fake.refund_mode = "pending"
    assert reconcile_at(s, at(timedelta(hours=1))) == {refund["id"]: "PENDING"}
    assert len(s.fake.refunds) == 1
    final = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert final["refund_status"] == "PENDING" and final["refunds"][0]["retrying"] is False


def test_admin_can_retry_a_waiting_refund_now(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    s.fake.refund_mode = "reject"
    refund_id = cancel(s, order_id).json()["refunds"][0]["id"]
    s.fake.refund_mode = "pending"
    staff_login(s, "juice")
    denied = s.client.post(f"/api/v1/staff/refunds/{refund_id}/retry", headers={"Origin": ORIGIN})
    assert denied.status_code == 403
    staff_login(s)
    listing = s.client.get("/api/v1/staff/refunds").json()
    assert listing[0]["retrying"] is True and listing[0]["retry_until"]
    retried = s.client.post(f"/api/v1/staff/refunds/{refund_id}/retry", headers={"Origin": ORIGIN})
    assert retried.status_code == 200, retried.text
    assert retried.json()["id"] == refund_id and retried.json()["status"] == "PENDING"
    assert [r.status for r in refunds(s, order_id)] == ["PENDING"]


def test_refund_still_refused_after_the_window_fails_and_notifies(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    s.fake.refund_mode = "reject"
    refund_id = cancel(s, order_id).json()["refunds"][0]["id"]
    assert reconcile_at(s, at(timedelta(days=5))) == {refund_id: "FAILED"}
    detail = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert detail["refund_status"] == "FAILED"
    kinds = [n["kind"] for n in s.client.get("/api/v1/student/notifications").json()["items"]]
    assert kinds.count("REFUND_FAILED") == 1
    # A failed refund can still be retried by an admin as a new row; the old row is kept.
    s.fake.refund_mode = "pending"
    with Session(s.engine) as db, db.begin():
        scope = StaffScope("admin", "session", s.ids["coe"], None, "admin")
        assert (
            retry_refund(db, s.providers, scope, refund_id, datetime.now(UTC)).status == "PENDING"
        )
    assert [r.status for r in refunds(s, order_id)] == ["FAILED", "PENDING"]


def test_permanent_rejection_fails_at_once(pay_setup):
    s = pay_setup
    order_id, *_ = paid_order(s)
    s.fake.refund_mode = "reject"
    s.fake.reject_message = "The refund amount provided is greater than amount captured"
    [refund] = cancel(s, order_id).json()["refunds"]
    assert refund["status"] == "FAILED" and refund["retrying"] is False
    assert refund["next_attempt_at"] is None


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
