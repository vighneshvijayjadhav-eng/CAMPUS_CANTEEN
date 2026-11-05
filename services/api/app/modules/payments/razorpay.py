"""Razorpay REST adapter (Orders + Payments APIs, webhook and checkout signatures).

Only server-side calls are made here. The Android app opens Razorpay Checkout with the public
key_id and provider order id; nothing it reports is trusted until verified below.
"""

import hashlib
import hmac
from dataclasses import dataclass

import httpx

from app.core.errors import DomainError

API_BASE = "https://api.razorpay.com/v1"


@dataclass(frozen=True)
class ProviderPayment:
    id: str
    order_id: str | None
    amount_paise: int
    currency: str
    status: str  # created | authorized | captured | failed | refunded
    error: str | None = None


@dataclass(frozen=True)
class ProviderRefund:
    id: str
    payment_id: str
    amount_paise: int
    status: str  # pending | processed | failed
    receipt: str | None = None


def refund_from(entity):
    return ProviderRefund(
        id=entity["id"],
        payment_id=entity["payment_id"],
        amount_paise=int(entity["amount"]),
        status=entity["status"],
        receipt=entity.get("receipt"),
    )


def signature(secret, message):
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def payment_from(entity):
    return ProviderPayment(
        id=entity["id"],
        order_id=entity.get("order_id"),
        amount_paise=int(entity["amount"]),
        currency=entity.get("currency", "INR"),
        status=entity["status"],
        error=entity.get("error_description") or entity.get("error_code"),
    )


class RazorpayProvider:
    def __init__(self, key_id, key_secret, webhook_secret, client=None, base_url=API_BASE):
        self.key_id = key_id
        self._key_secret = key_secret
        self._webhook_secret = webhook_secret
        self._base_url = base_url
        self._client = client

    def _request(self, method, path, **kwargs):
        client = self._client or httpx.Client(timeout=10)
        try:
            response = client.request(
                method,
                f"{self._base_url}{path}",
                auth=(self.key_id, self._key_secret),
                **kwargs,
            )
        except httpx.HTTPError as error:
            raise DomainError("PAYMENT_PROVIDER_UNAVAILABLE", 503) from error
        finally:
            if self._client is None:
                client.close()
        if response.status_code >= 500:
            raise DomainError("PAYMENT_PROVIDER_UNAVAILABLE", 503)
        if response.status_code >= 400:
            raise DomainError("PAYMENT_PROVIDER_REJECTED", 502)
        return response.json()

    def create_order(self, amount_paise, receipt, notes):
        body = {"amount": amount_paise, "currency": "INR", "receipt": receipt, "notes": notes}
        order = self._request("POST", "/orders", json=body)
        if int(order["amount"]) != amount_paise or order.get("currency") != "INR":
            raise DomainError("PAYMENT_PROVIDER_REJECTED", 502)
        return order["id"]

    def fetch_payment(self, payment_id):
        return payment_from(self._request("GET", f"/payments/{payment_id}"))

    def order_payments(self, provider_order_id):
        data = self._request("GET", f"/orders/{provider_order_id}/payments")
        return [payment_from(item) for item in data.get("items", [])]

    def create_refund(self, payment_id, amount_paise, receipt, notes):
        body = {"amount": amount_paise, "speed": "normal", "receipt": receipt, "notes": notes}
        return refund_from(self._request("POST", f"/payments/{payment_id}/refund", json=body))

    def fetch_refund(self, refund_id):
        return refund_from(self._request("GET", f"/refunds/{refund_id}"))

    def payment_refunds(self, payment_id):
        data = self._request("GET", f"/payments/{payment_id}/refunds")
        return [refund_from(item) for item in data.get("items", [])]

    def verify_checkout_signature(self, provider_order_id, payment_id, value):
        expected = signature(self._key_secret, f"{provider_order_id}|{payment_id}".encode())
        return hmac.compare_digest(expected, value or "")

    def verify_webhook(self, body, value):
        return hmac.compare_digest(signature(self._webhook_secret, body), value or "")


def provider_factory(settings):
    """Build a provider for a merchant account from server-held secrets."""

    credentials = getattr(settings, "razorpay_credentials", None) or {}
    allow_live = getattr(settings, "allow_live_payments", False)

    def build(account):
        if (account.mode == "live" or account.key_id.startswith("rzp_live_")) and not allow_live:
            raise DomainError("LIVE_PAYMENTS_DISABLED", 503)
        credential = credentials.get(account.key_id)
        if credential is None:
            raise DomainError("MERCHANT_NOT_CONFIGURED", 503)
        return RazorpayProvider(
            account.key_id,
            credential.key_secret.get_secret_value(),
            credential.webhook_secret.get_secret_value(),
        )

    return build
