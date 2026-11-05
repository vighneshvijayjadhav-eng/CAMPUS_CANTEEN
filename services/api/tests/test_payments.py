"""Payment lifecycle tests. The real Razorpay adapter runs against an in-memory fake of the
Razorpay REST API; signatures are computed with real HMAC. No network or merchant is used."""

import json
from datetime import UTC, datetime, timedelta
from itertools import count
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr, ValidationError
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session
from test_api import ORIGIN, PASSWORD, LocalClient

from app.core.config import RazorpayCredential, Settings
from app.core.db import Base
from app.core.errors import DomainError
from app.main import create_app
from app.modules.identity.models import StaffAccount
from app.modules.identity.service import hasher
from app.modules.menu.models import Canteen, Institute, MenuItem, MenuVariant, Station
from app.modules.orders.models import Order, PickupCredential, QueueEvent
from app.modules.orders.pickup import lookup
from app.modules.orders.service import StaffScope, confirm_line, lines_for
from app.modules.payments.models import MerchantAccount, PaymentAttempt
from app.modules.payments.razorpay import RazorpayProvider, provider_factory, signature
from app.modules.payments.service import reconcile_attempt, stale_attempts
from app.modules.reviews.media import LocalMediaStorage

KEY_ID = "rzp_test_fakeKey123"
KEY_SECRET = "test-only-razorpay-key-secret"
WEBHOOK_SECRET = "test-only-webhook-secret"
PICKUP_KEY = "test-only-key" * 4


class FakeRazorpay:
    """Minimal stand-in for the Razorpay Orders/Payments REST endpoints."""

    def __init__(self):
        self.orders, self.payments, self.refunds, self.ids = {}, {}, {}, count(1)
        self.refund_mode = "pending"  # pending | processed | reject | down

    def handle(self, request):
        if request.headers.get("authorization") != httpx.BasicAuth(KEY_ID, KEY_SECRET)._auth_header:
            return httpx.Response(401, json={"error": {"code": "BAD_REQUEST_ERROR"}})
        path = request.url.path.removeprefix("/v1")
        if request.method == "POST" and path == "/orders":
            body = json.loads(request.content)
            order_id = f"order_Fake{next(self.ids)}"
            self.orders[order_id] = {"id": order_id, "amount": body["amount"], "currency": "INR"}
            return httpx.Response(200, json=self.orders[order_id])
        if request.method == "POST" and path.endswith("/refund"):
            if self.refund_mode == "down":
                return httpx.Response(503)
            if self.refund_mode == "reject":
                return httpx.Response(400, json={"error": {"code": "BAD_REQUEST_ERROR"}})
            body = json.loads(request.content)
            payment_id = path.split("/")[2]
            refunded = sum(
                r["amount"] for r in self.refunds.values() if r["payment_id"] == payment_id
            )
            if refunded + body["amount"] > self.payments[payment_id]["amount"]:
                return httpx.Response(400, json={"error": {"code": "BAD_REQUEST_ERROR"}})
            refund_id = f"rfnd_Fake{next(self.ids)}"
            self.refunds[refund_id] = {
                "id": refund_id,
                "entity": "refund",
                "payment_id": payment_id,
                "amount": body["amount"],
                "receipt": body.get("receipt"),
                "status": "processed" if self.refund_mode == "processed" else "pending",
            }
            return httpx.Response(200, json=self.refunds[refund_id])
        if path.startswith("/refunds/"):
            refund = self.refunds.get(path.removeprefix("/refunds/"))
            return httpx.Response(200, json=refund) if refund else httpx.Response(404)
        if path.startswith("/payments/") and path.endswith("/refunds"):
            payment_id = path.split("/")[2]
            items = [r for r in self.refunds.values() if r["payment_id"] == payment_id]
            return httpx.Response(200, json={"items": items})
        if path.startswith("/payments/"):
            payment = self.payments.get(path.removeprefix("/payments/"))
            return httpx.Response(200, json=payment) if payment else httpx.Response(404)
        if path.startswith("/orders/") and path.endswith("/payments"):
            order_id = path.split("/")[2]
            items = [p for p in self.payments.values() if p["order_id"] == order_id]
            return httpx.Response(200, json={"items": items})
        return httpx.Response(404)

    def pay(self, provider_order_id, amount=None, status="captured"):
        payment_id = f"pay_Fake{next(self.ids)}"
        self.payments[payment_id] = {
            "id": payment_id,
            "order_id": provider_order_id,
            "amount": amount if amount is not None else self.orders[provider_order_id]["amount"],
            "currency": "INR",
            "status": status,
            "error_description": "Bank declined" if status == "failed" else None,
        }
        return payment_id

    def refund_webhook(self, event_name, refund_id):
        body = json.dumps(
            {
                "entity": "event",
                "event": event_name,
                "payload": {"refund": {"entity": self.refunds[refund_id]}},
            }
        ).encode()
        return body, signature(WEBHOOK_SECRET, body)

    def checkout_signature(self, provider_order_id, payment_id):
        return signature(KEY_SECRET, f"{provider_order_id}|{payment_id}".encode())

    def webhook(self, event_name, payment_id):
        body = json.dumps(
            {
                "entity": "event",
                "event": event_name,
                "payload": {"payment": {"entity": self.payments[payment_id]}},
            }
        ).encode()
        return body, signature(WEBHOOK_SECRET, body)


@pytest.fixture
def pay_setup(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path / 'pay.db'}", connect_args={"check_same_thread": False}
    )
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    ids = {
        key: str(uuid4()) for key in ["institute", "coe", "juice", "item", "variant", "merchant"]
    }
    with Session(engine) as db, db.begin():
        db.add(Institute(id=ids["institute"], slug="coe", name="COE", approved=True))
        db.flush()
        db.add(
            Canteen(
                id=ids["coe"],
                institute_id=ids["institute"],
                slug="coe",
                name="COE Canteen",
                approved=True,
                operating=True,
            )
        )
        db.flush()
        db.add(Station(id=ids["juice"], canteen_id=ids["coe"], name="Juice"))
        db.add(MenuItem(id=ids["item"], canteen_id=ids["coe"], name="Coffee", category="Drinks"))
        db.flush()
        db.add(
            MenuVariant(
                id=ids["variant"],
                canteen_id=ids["coe"],
                item_id=ids["item"],
                label="Regular",
                price_paise=4000,
                station_id=ids["juice"],
                verified=True,
                available=True,
            )
        )
        for username, role, station in [("admin", "admin", None), ("juice", "station", "juice")]:
            db.add(
                StaffAccount(
                    username=username,
                    password_hash=hasher.hash(PASSWORD),
                    canteen_id=ids["coe"],
                    role=role,
                    station_id=ids[station] if station else None,
                )
            )
        db.add(
            MerchantAccount(
                id=ids["merchant"],
                canteen_id=ids["coe"],
                provider="razorpay",
                key_id=KEY_ID,
                mode="test",
                display_name="COE Canteen",
                active=True,
                created_at=datetime.now(UTC),
            )
        )
    fake = FakeRazorpay()

    def providers(account):
        client = httpx.Client(transport=httpx.MockTransport(fake.handle))
        return RazorpayProvider(account.key_id, KEY_SECRET, WEBHOOK_SECRET, client=client)

    settings = SimpleNamespace(
        web_origin=ORIGIN, environment="local", pickup_hmac_key=SecretStr(PICKUP_KEY)
    )
    claims = {"sub": "google-student", "email": "s@gmail.com", "name": "S", "picture": None}
    client = LocalClient(
        create_app(
            settings,
            engine,
            google_verifier=lambda _: claims,
            payment_providers=providers,
            media_storage=LocalMediaStorage(tmp_path / "media"),
        )
    )
    login = client.post("/api/v1/auth/google", json={"id_token": "a" * 20, "device_name": "Phone"})
    client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"
    yield SimpleNamespace(
        client=client,
        engine=engine,
        ids=ids,
        fake=fake,
        providers=providers,
        settings=settings,
        media=tmp_path / "media",
    )
    engine.dispose()


def place_order(s, quantity=2):
    s.client.request(
        "PUT", f"/api/v1/student/cart/lines/{s.ids['variant']}", json={"quantity": quantity}
    )
    response = s.client.post(
        "/api/v1/student/checkout",
        json={"request_id": str(uuid4()), "expected_total_paise": 4000 * quantity},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def start(s, order_id):
    response = s.client.post(f"/api/v1/student/orders/{order_id}/payment")
    assert response.status_code == 200, response.text
    return response.json()


def confirm(s, order_id, provider_order_id, payment_id, sig=None):
    return s.client.post(
        f"/api/v1/student/orders/{order_id}/payment/confirm",
        json={
            "provider_order_id": provider_order_id,
            "provider_payment_id": payment_id,
            "signature": sig or s.fake.checkout_signature(provider_order_id, payment_id),
        },
    )


def webhook(s, body, sig, event_id=None):
    headers = {"X-Razorpay-Signature": sig}
    if event_id:
        headers["X-Razorpay-Event-Id"] = event_id
    return s.client.post(
        f"/api/v1/payments/razorpay/webhooks/{s.ids['merchant']}", content=body, headers=headers
    )


def order_state(s, order_id):
    with Session(s.engine) as db:
        return db.get(Order, order_id).state


def test_checkout_callback_activates_order_and_issues_code(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    assert params["key_id"] == KEY_ID and params["amount_paise"] == 8000
    assert params["mode"] == "test"
    assert start(s, order_id)["provider_order_id"] == params["provider_order_id"]
    payment_id = s.fake.pay(params["provider_order_id"])
    result = confirm(s, order_id, params["provider_order_id"], payment_id)
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["payment_status"] == "CAPTURED"
    order = body["order"]
    assert order["state"] == "PAID_ACTIVE" and order["payment_verified_at"]
    code = order["pickup_code"]
    assert len(code) == 6 and code.isdecimal()
    assert order["payment"]["provider_payment_id"] == payment_id
    with Session(s.engine) as db:
        scope = StaffScope("staff", "device", s.ids["coe"], s.ids["juice"], "station")
        assert lookup(db, scope, code, PICKUP_KEY)["id"] == order_id
        assert [e.kind for e in db.scalars(select(QueueEvent))] == ["PAID"]
        credential = db.get(PickupCredential, order_id)
        assert code not in credential.encrypted_code and code not in credential.digest
    # Retried callback is a no-op and keeps the same code.
    again = confirm(s, order_id, params["provider_order_id"], payment_id).json()
    assert again["payment_status"] == "CAPTURED" and again["order"]["pickup_code"] == code
    assert s.client.post(f"/api/v1/student/orders/{order_id}/payment").json() == {
        "error": "ORDER_NOT_PAYABLE"
    }


def test_code_disappears_once_fully_collected(pay_setup):
    s = pay_setup
    order_id = place_order(s, quantity=1)
    params = start(s, order_id)
    confirm(s, order_id, params["provider_order_id"], s.fake.pay(params["provider_order_id"]))
    with Session(s.engine) as db, db.begin():
        line = lines_for(db, order_id)[0]
        scope = StaffScope("staff", "device", s.ids["coe"], s.ids["juice"], "station")
        confirm_line(db, scope, order_id, line.id, 1, 0, str(uuid4()))
    detail = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert detail["state"] == "COLLECTED" and detail["pickup_code"] is None


def test_forged_callback_signature_is_rejected(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    payment_id = s.fake.pay(params["provider_order_id"])
    forged = confirm(s, order_id, params["provider_order_id"], payment_id, sig="0" * 64)
    assert forged.status_code == 400
    assert forged.json() == {"error": "PAYMENT_SIGNATURE_INVALID"}
    assert order_state(s, order_id) == "PAYMENT_PENDING"


def test_authorized_payment_waits_for_captured_webhook(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    payment_id = s.fake.pay(params["provider_order_id"], status="authorized")
    assert confirm(s, order_id, params["provider_order_id"], payment_id).json()[
        "payment_status"
    ] == ("CREATED")
    assert order_state(s, order_id) == "PAYMENT_PENDING"
    s.fake.payments[payment_id]["status"] = "captured"
    body, sig = s.fake.webhook("payment.captured", payment_id)
    assert webhook(s, body, sig, "evt_1").json() == {"result": "CAPTURED"}
    assert order_state(s, order_id) == "PAID_ACTIVE"


def test_webhook_replay_and_bad_signature(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    body, sig = s.fake.webhook("payment.captured", s.fake.pay(params["provider_order_id"]))
    bad = webhook(s, body, "f" * 64, "evt_bad")
    assert bad.status_code == 400 and bad.json() == {"error": "WEBHOOK_SIGNATURE_INVALID"}
    assert order_state(s, order_id) == "PAYMENT_PENDING"
    assert webhook(s, body, sig, "evt_2").json() == {"result": "CAPTURED"}
    assert webhook(s, body, sig, "evt_2").json() == {"result": "DUPLICATE"}
    # Without an event id header the body digest is the replay key.
    assert webhook(s, body, sig).json() == {"result": "CAPTURED"}
    assert webhook(s, body, sig).json() == {"result": "DUPLICATE"}
    with Session(s.engine) as db:
        assert len(db.scalars(select(QueueEvent)).all()) == 1


def test_amount_mismatch_never_activates(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    body, sig = s.fake.webhook(
        "payment.captured", s.fake.pay(params["provider_order_id"], amount=100)
    )
    assert webhook(s, body, sig, "evt_3").json() == {"result": "AMOUNT_MISMATCH"}
    assert order_state(s, order_id) == "PAYMENT_PENDING"


def test_failed_payment_keeps_attempt_open_for_retry(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    failed = s.fake.pay(params["provider_order_id"], status="failed")
    body, sig = s.fake.webhook("payment.failed", failed)
    assert webhook(s, body, sig, "evt_4").json() == {"result": "CREATED"}
    detail = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert detail["payment"]["failure_reason"] == "Bank declined"
    retry = s.fake.pay(params["provider_order_id"])
    assert confirm(s, order_id, params["provider_order_id"], retry).json()["payment_status"] == (
        "CAPTURED"
    )


def test_second_capture_for_paid_order_is_flagged_for_refund(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    confirm(s, order_id, params["provider_order_id"], s.fake.pay(params["provider_order_id"]))
    code = s.client.get(f"/api/v1/student/orders/{order_id}").json()["pickup_code"]
    with Session(s.engine) as db, db.begin():
        db.add(
            PaymentAttempt(
                canteen_id=s.ids["coe"],
                order_id=order_id,
                merchant_account_id=s.ids["merchant"],
                provider_order_id="order_Second",
                amount_paise=8000,
                status="CREATED",
                created_at=datetime.now(UTC),
            )
        )
    s.fake.orders["order_Second"] = {"id": "order_Second", "amount": 8000, "currency": "INR"}
    body, sig = s.fake.webhook("payment.captured", s.fake.pay("order_Second"))
    assert webhook(s, body, sig, "evt_5").json() == {"result": "CAPTURED_UNAPPLIED"}
    detail = s.client.get(f"/api/v1/student/orders/{order_id}").json()
    assert detail["state"] == "PAID_ACTIVE" and detail["pickup_code"] == code


def test_reconciliation_recovers_a_missed_webhook(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    params = start(s, order_id)
    s.fake.pay(params["provider_order_id"])
    later = datetime.now(UTC) + timedelta(minutes=5)
    with Session(s.engine) as db, db.begin():
        attempts = stale_attempts(db, later)
        assert [a.provider_order_id for a in attempts] == [params["provider_order_id"]]
        assert reconcile_attempt(db, s.providers, attempts[0], later, PICKUP_KEY) == "CAPTURED"
    assert order_state(s, order_id) == "PAID_ACTIVE"


def test_other_students_and_unconfigured_canteens(pay_setup):
    s = pay_setup
    order_id = place_order(s)
    stranger = s.client.post(
        f"/api/v1/student/orders/{order_id}/payment", headers={"Authorization": "Bearer nope"}
    )
    assert stranger.status_code == 401
    with Session(s.engine) as db, db.begin():
        db.get(MerchantAccount, s.ids["merchant"]).active = False
    unconfigured = s.client.post(f"/api/v1/student/orders/{order_id}/payment")
    assert unconfigured.status_code == 503
    assert unconfigured.json() == {"error": "PAYMENTS_NOT_CONFIGURED"}


def account(key_id, mode="test"):
    return SimpleNamespace(key_id=key_id, mode=mode)


def test_provider_factory_blocks_live_keys_and_missing_secrets():
    credentials = {
        KEY_ID: RazorpayCredential(key_secret=KEY_SECRET, webhook_secret=WEBHOOK_SECRET),
        "rzp_live_real": RazorpayCredential(key_secret="x", webhook_secret="y"),
    }
    build = provider_factory(SimpleNamespace(razorpay_credentials=credentials))
    assert build(account(KEY_ID)).key_id == KEY_ID
    with pytest.raises(DomainError, match="LIVE_PAYMENTS_DISABLED"):
        build(account("rzp_live_real", "live"))
    with pytest.raises(DomainError, match="LIVE_PAYMENTS_DISABLED"):
        build(account("rzp_live_real", "test"))
    with pytest.raises(DomainError, match="MERCHANT_NOT_CONFIGURED"):
        build(account("rzp_test_unknown"))


def test_live_payments_flag_requires_production():
    base = {
        "database_url": "postgresql+psycopg://u:p@localhost/db",
        "pickup_hmac_key": "x" * 32,
    }
    with pytest.raises(ValidationError, match="Live payments"):
        Settings(_env_file=None, allow_live_payments=True, **base)
    parsed = Settings(
        _env_file=None,
        razorpay_credentials={KEY_ID: {"key_secret": "a", "webhook_secret": "b"}},
        **base,
    )
    assert parsed.razorpay_credentials[KEY_ID].key_secret.get_secret_value() == "a"


def test_single_account_env_shorthand_is_merged():
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        pickup_hmac_key="x" * 32,
        razorpay_key_id=KEY_ID,
        razorpay_key_secret="s",
        razorpay_webhook_secret="w",
    )
    assert settings.razorpay_credentials[KEY_ID].webhook_secret.get_secret_value() == "w"
    empty = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@localhost/db",
        pickup_hmac_key="x" * 32,
        razorpay_key_id=KEY_ID,
        razorpay_key_secret="",
        razorpay_webhook_secret="",
    )
    assert empty.razorpay_credentials == {}
