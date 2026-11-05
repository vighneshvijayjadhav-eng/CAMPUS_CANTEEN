"""Payment lifecycle. An order becomes PAID_ACTIVE only from a provider-verified capture:
a signature-checked webhook, or a server-side payment fetch after a signature-checked
checkout callback, or reconciliation polling. Client claims alone never activate an order.
"""

import hashlib
import json
from datetime import timedelta

from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.notifications.service import notify as notify_student
from app.modules.orders.models import Order
from app.modules.orders.pickup import issue_code
from app.modules.orders.service import lines_for, locked_order, notify
from app.modules.payments.models import MerchantAccount, PaymentAttempt, PaymentWebhookEvent
from app.modules.payments.razorpay import payment_from
from app.modules.payments.refunds import handle_refund_event, refund_for_mismatch


def active_merchant(db, canteen_id):
    account = db.scalar(
        select(MerchantAccount).where(
            MerchantAccount.canteen_id == canteen_id, MerchantAccount.active.is_(True)
        )
    )
    if account is None:
        raise DomainError("PAYMENTS_NOT_CONFIGURED", 503)
    return account


def checkout_params(attempt, account, order):
    return {
        "order_id": order.id,
        "provider": account.provider,
        "key_id": account.key_id,
        "provider_order_id": attempt.provider_order_id,
        "amount_paise": attempt.amount_paise,
        "currency": attempt.currency,
        "merchant_name": account.display_name,
        "mode": account.mode,
    }


def start_payment(db, providers, student_id, order_id, now):
    """Return gateway checkout parameters, reusing an open attempt for the same account."""
    order = locked_order(db, order_id, student_id=student_id)
    if order.state != "PAYMENT_PENDING":
        raise DomainError("ORDER_NOT_PAYABLE")
    account = active_merchant(db, order.canteen_id)
    attempt = db.scalar(
        select(PaymentAttempt)
        .where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.merchant_account_id == account.id,
            PaymentAttempt.status == "CREATED",
            PaymentAttempt.amount_paise == order.total_paise,
        )
        .order_by(PaymentAttempt.created_at.desc())
    )
    if attempt is None:
        provider = providers(account)
        provider_order_id = provider.create_order(
            order.total_paise,
            receipt=order.id,
            notes={"order_id": order.id, "canteen_id": order.canteen_id},
        )
        attempt = PaymentAttempt(
            canteen_id=order.canteen_id,
            order_id=order.id,
            merchant_account_id=account.id,
            provider_order_id=provider_order_id,
            amount_paise=order.total_paise,
            currency="INR",
            status="CREATED",
            created_at=now,
        )
        db.add(attempt)
        db.flush()
    return checkout_params(attempt, account, order)


def apply_capture(db, attempt, payment, now, pickup_key):
    """Apply a provider-verified payment to its attempt. Idempotent; caller owns the transaction.

    Returns the attempt status after processing.
    """
    order = locked_order(db, attempt.order_id)
    attempt = db.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.id == attempt.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if payment.order_id != attempt.provider_order_id:
        raise DomainError("PAYMENT_ORDER_MISMATCH")
    if attempt.status != "CREATED":
        # Already processed (replayed webhook, retried callback or reconciliation overlap).
        return attempt.status
    if payment.status != "captured":
        if payment.status == "failed":
            attempt.failure_reason = (payment.error or "failed")[:160]
            db.flush()
        return attempt.status
    attempt.provider_payment_id = payment.id
    attempt.captured_at = now
    if payment.amount_paise != attempt.amount_paise or payment.currency != attempt.currency:
        attempt.status = "AMOUNT_MISMATCH"
    elif order.state == "PAYMENT_PENDING" and order.total_paise == attempt.amount_paise:
        attempt.status = "CAPTURED"
        order.state = "PAID_ACTIVE"
        order.payment_verified_at = now
        issue_code(db, order, pickup_key)
        notify(db, order, lines_for(db, order.id), "PAID")
        notify_student(db, order, "PAYMENT_CONFIRMED", now)
    else:
        # Money arrived for an order that is already paid, cancelled or otherwise not payable.
        attempt.status = "CAPTURED_UNAPPLIED"
    db.flush()
    if attempt.status in ("AMOUNT_MISMATCH", "CAPTURED_UNAPPLIED"):
        # Queued here, sent to Razorpay by refund reconciliation.
        refund_for_mismatch(db, attempt, payment, now)
        notify_student(db, order, "EXTRA_PAYMENT_REFUND", now, payment.amount_paise)
    return attempt.status


def confirm_checkout(db, providers, student_id, order_id, body, now, pickup_key):
    """Handle the app's post-checkout callback. The signature proves the ids came from
    Razorpay; the payment state itself is fetched from Razorpay, not taken from the app."""
    order = db.scalar(select(Order).where(Order.id == order_id, Order.student_id == student_id))
    if order is None:
        raise DomainError("ORDER_NOT_FOUND", 404)
    attempt = db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.order_id == order.id,
            PaymentAttempt.provider_order_id == body["provider_order_id"],
        )
    )
    if attempt is None:
        raise DomainError("PAYMENT_NOT_FOUND", 404)
    provider = providers(db.get(MerchantAccount, attempt.merchant_account_id))
    if not provider.verify_checkout_signature(
        attempt.provider_order_id, body["provider_payment_id"], body["signature"]
    ):
        raise DomainError("PAYMENT_SIGNATURE_INVALID", 400)
    payment = provider.fetch_payment(body["provider_payment_id"])
    return apply_capture(db, attempt, payment, now, pickup_key)


def handle_webhook(db, providers, merchant_account_id, body, header_signature, event_id, now, key):
    account = db.get(MerchantAccount, merchant_account_id)
    if account is None:
        raise DomainError("MERCHANT_NOT_FOUND", 404)
    provider = providers(account)
    if not provider.verify_webhook(body, header_signature):
        raise DomainError("WEBHOOK_SIGNATURE_INVALID", 400)
    payload = json.loads(body)
    event_type = str(payload.get("event", ""))[:80]
    body_digest = hashlib.sha256(body).hexdigest()
    event_id = (event_id or body_digest)[:120]
    if db.get(PaymentWebhookEvent, (account.id, event_id)):
        return "DUPLICATE"
    db.add(
        PaymentWebhookEvent(
            merchant_account_id=account.id,
            provider_event_id=event_id,
            event_type=event_type,
            body_sha256=body_digest,
            received_at=now,
        )
    )
    db.flush()
    if event_type in ("refund.created", "refund.processed", "refund.failed"):
        refund_entity = payload.get("payload", {}).get("refund", {}).get("entity")
        if not refund_entity:
            return "IGNORED"
        return handle_refund_event(db, account, event_type, refund_entity, now)
    entity = payload.get("payload", {}).get("payment", {}).get("entity")
    if event_type not in ("payment.captured", "payment.failed", "order.paid") or not entity:
        return "IGNORED"
    payment = payment_from(entity)
    attempt = db.scalar(
        select(PaymentAttempt).where(
            PaymentAttempt.merchant_account_id == account.id,
            PaymentAttempt.provider_order_id == payment.order_id,
        )
    )
    if attempt is None:
        return "IGNORED"
    return apply_capture(db, attempt, payment, now, key)


def stale_attempts(db, now, older_than=timedelta(minutes=2), limit=100):
    return list(
        db.scalars(
            select(PaymentAttempt)
            .where(
                PaymentAttempt.status == "CREATED",
                PaymentAttempt.created_at <= now - older_than,
            )
            .order_by(PaymentAttempt.created_at)
            .limit(limit)
        )
    )


def reconcile_attempt(db, providers, attempt, now, pickup_key):
    """Poll the provider for one open attempt, for when a webhook was missed."""
    provider = providers(db.get(MerchantAccount, attempt.merchant_account_id))
    payments = provider.order_payments(attempt.provider_order_id)
    captured = next((payment for payment in payments if payment.status == "captured"), None)
    if captured is None:
        return attempt.status
    return apply_capture(db, attempt, captured, now, pickup_key)


def payment_summary(db, order_id):
    attempt = db.scalar(
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order_id)
        .order_by(PaymentAttempt.created_at.desc())
    )
    if attempt is None:
        return None
    return {
        "status": attempt.status,
        "provider_payment_id": attempt.provider_payment_id,
        "amount_paise": attempt.amount_paise,
        "failure_reason": attempt.failure_reason,
    }
