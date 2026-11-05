"""Refund lifecycle: REQUESTED (recorded, not yet accepted by Razorpay) -> PENDING (accepted)
-> PROCESSED (Razorpay confirms the money is returned) or FAILED.

A refund row is written in the same transaction as the decision (cancellation, duplicate
capture). Submission to Razorpay is best-effort in that request and retried by reconciliation.
Each submission sends the refund row id as Razorpay `receipt`, and reconciliation adopts an
existing Razorpay refund with that receipt before creating another, so retries never refund
twice. Razorpay also rejects refunds above the captured amount.
"""

from datetime import timedelta

from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.orders.models import Order
from app.modules.orders.service import cancel_order, staff_cancel_order
from app.modules.payments.models import MerchantAccount, PaymentAttempt, Refund
from app.modules.payments.razorpay import refund_from

ORDER_REFUND_REASONS = ("STUDENT_CANCELLED", "STAFF_CANCELLED")
ORDER_REFUND_STATUS = {
    "REQUESTED": "REQUESTED",
    "PENDING": "PENDING",
    "PROCESSED": "REFUNDED",
    "FAILED": "FAILED",
}
PROVIDER_STATUS = {"pending": "PENDING", "created": "PENDING", "processed": "PROCESSED"}


def captured_attempt(db, order_id):
    return db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == order_id, PaymentAttempt.status == "CAPTURED"
        )
    )


def open_refund(db, attempt_id):
    return db.scalar(
        select(Refund).where(Refund.payment_attempt_id == attempt_id, Refund.status != "FAILED")
    )


def sync_order(db, refund):
    if refund.reason in ORDER_REFUND_REASONS:
        order = db.get(Order, refund.order_id)
        order.refund_status = ORDER_REFUND_STATUS[refund.status]


def request_refund(db, attempt, reason, actor_kind, actor_id, now, note=None):
    """Record a full refund of a captured attempt. Idempotent per attempt."""
    if attempt.provider_payment_id is None or attempt.status not in (
        "CAPTURED",
        "CAPTURED_UNAPPLIED",
        "AMOUNT_MISMATCH",
    ):
        raise DomainError("PAYMENT_NOT_REFUNDABLE")
    existing = open_refund(db, attempt.id)
    if existing:
        return existing
    payment_amount = attempt.amount_paise
    refund = Refund(
        canteen_id=attempt.canteen_id,
        order_id=attempt.order_id,
        payment_attempt_id=attempt.id,
        merchant_account_id=attempt.merchant_account_id,
        amount_paise=payment_amount,
        reason=reason,
        note=note,
        status="REQUESTED",
        requested_by_kind=actor_kind,
        requested_by=actor_id,
        created_at=now,
        submit_attempts=0,
    )
    db.add(refund)
    db.flush()
    sync_order(db, refund)
    db.flush()
    return refund


def refund_for_mismatch(db, attempt, payment, now):
    """Money that cannot be applied to an order is returned automatically. For an amount
    mismatch the refund is the amount Razorpay actually captured."""
    refund = request_refund(
        db,
        attempt,
        "AMOUNT_MISMATCH" if attempt.status == "AMOUNT_MISMATCH" else "DUPLICATE_PAYMENT",
        "system",
        "payments",
        now,
    )
    refund.amount_paise = payment.amount_paise
    db.flush()
    return refund


def apply_provider_refund(db, refund, provider_refund, now):
    if provider_refund.amount_paise != refund.amount_paise:
        refund.last_error = "Provider refund amount differs"
        db.flush()
        return refund
    if refund.provider_refund_id is None:
        refund.provider_refund_id = provider_refund.id
        refund.submitted_at = refund.submitted_at or now
    if refund.status in ("PROCESSED", "FAILED"):
        return refund  # terminal; never regress
    status = PROVIDER_STATUS.get(provider_refund.status)
    if provider_refund.status == "failed":
        status = "FAILED"
    if status:
        refund.status = status
        if status == "PROCESSED":
            refund.processed_at = now
        sync_order(db, refund)
    db.flush()
    return refund


def locked_refund(db, refund_id):
    refund = db.scalar(
        select(Refund)
        .where(Refund.id == refund_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if refund is None:
        raise DomainError("REFUND_NOT_FOUND", 404)
    return refund


def submit_refund(db, providers, refund_id, now):
    """Send a REQUESTED refund to Razorpay. Provider outages leave it REQUESTED for retry;
    a provider rejection marks it FAILED for an admin to review."""
    refund = locked_refund(db, refund_id)
    if refund.status != "REQUESTED":
        return refund
    attempt = db.get(PaymentAttempt, refund.payment_attempt_id)
    refund.submit_attempts += 1
    try:
        provider = providers(db.get(MerchantAccount, refund.merchant_account_id))
        earlier = next(
            (
                item
                for item in provider.payment_refunds(attempt.provider_payment_id)
                if item.receipt == refund.id
            ),
            None,
        )
        provider_refund = earlier or provider.create_refund(
            attempt.provider_payment_id,
            refund.amount_paise,
            receipt=refund.id,
            notes={"order_id": refund.order_id, "reason": refund.reason},
        )
    except DomainError as error:
        refund.last_error = error.code
        if error.code == "PAYMENT_PROVIDER_REJECTED":
            refund.status = "FAILED"
            sync_order(db, refund)
        db.flush()
        return refund
    refund.last_error = None
    refund.submitted_at = now
    return apply_provider_refund(db, refund, provider_refund, now)


def handle_refund_event(db, account, event_type, entity, now):
    provider_refund = refund_from(entity)
    refund = db.scalar(
        select(Refund).where(
            Refund.merchant_account_id == account.id,
            Refund.provider_refund_id == provider_refund.id,
        )
    )
    if refund is None and provider_refund.receipt:
        refund = db.get(Refund, provider_refund.receipt)
        if refund is not None and refund.merchant_account_id != account.id:
            refund = None
    if refund is None:
        return "IGNORED"
    refund = locked_refund(db, refund.id)
    apply_provider_refund(db, refund, provider_refund, now)
    return f"REFUND_{refund.status}"


def reconcile_refunds(db, providers, now, older_than=timedelta(minutes=2), limit=100):
    """Retry unsubmitted refunds and poll accepted ones. Caller commits."""
    results = {}
    rows = db.scalars(
        select(Refund)
        .where(
            Refund.status.in_(["REQUESTED", "PENDING"]),
            Refund.created_at <= now - older_than,
        )
        .order_by(Refund.created_at)
        .limit(limit)
    )
    for refund_id, status, provider_refund_id, account_id in [
        (r.id, r.status, r.provider_refund_id, r.merchant_account_id) for r in rows
    ]:
        if status == "REQUESTED":
            results[refund_id] = submit_refund(db, providers, refund_id, now).status
            continue
        provider = providers(db.get(MerchantAccount, account_id))
        refund = locked_refund(db, refund_id)
        try:
            apply_provider_refund(db, refund, provider.fetch_refund(provider_refund_id), now)
        except DomainError as error:
            refund.last_error = error.code
        results[refund_id] = refund.status
    return results


def refund_view(refund):
    return {
        "id": refund.id,
        "order_id": refund.order_id,
        "amount_paise": refund.amount_paise,
        "reason": refund.reason,
        "note": refund.note,
        "status": refund.status,
        "provider_refund_id": refund.provider_refund_id,
        "requested_by_kind": refund.requested_by_kind,
        "created_at": refund.created_at,
        "processed_at": refund.processed_at,
        "last_error": refund.last_error,
    }


def order_refunds(db, order_id):
    return [
        refund_view(refund)
        for refund in db.scalars(
            select(Refund).where(Refund.order_id == order_id).order_by(Refund.created_at)
        )
    ]


def retry_refund(db, providers, scope, refund_id, now):
    """Admin retry of a FAILED refund for their own canteen: a new row, the old one kept."""
    if scope.role != "admin":
        raise DomainError("ADMIN_REQUIRED", 403)
    failed = db.scalar(
        select(Refund).where(Refund.id == refund_id, Refund.canteen_id == scope.canteen_id)
    )
    if failed is None:
        raise DomainError("REFUND_NOT_FOUND", 404)
    if failed.status != "FAILED":
        raise DomainError("REFUND_NOT_RETRYABLE")
    attempt = db.get(PaymentAttempt, failed.payment_attempt_id)
    refund = request_refund(
        db, attempt, failed.reason, "staff", scope.actor_id, now, note=failed.note
    )
    refund.amount_paise = failed.amount_paise
    db.flush()
    return submit_refund(db, providers, refund.id, now)


def cancel_with_refund(db, providers, student_id, order_id, now):
    """Student cancellation (five-minute rule in cancel_order) plus the matching refund."""
    order = cancel_order(db, student_id, order_id)
    return refund_cancelled(db, providers, order, "student", student_id, now)


def staff_cancel_with_refund(db, providers, scope, order_id, note, now):
    order = staff_cancel_order(db, scope, order_id)
    return refund_cancelled(db, providers, order, "staff", scope.actor_id, now, note)


def refund_cancelled(db, providers, order, actor_kind, actor_id, now, note=None):
    attempt = captured_attempt(db, order.id) if order.state == "CANCELLED" else None
    if attempt is None:
        return order, None
    reason = "STUDENT_CANCELLED" if actor_kind == "student" else "STAFF_CANCELLED"
    refund = request_refund(db, attempt, reason, actor_kind, actor_id, now, note=note)
    refund = submit_refund(db, providers, refund.id, now)
    return order, refund
