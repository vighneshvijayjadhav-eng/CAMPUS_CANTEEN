"""Real PostgreSQL race tests. Never substitute SQLite for these checks."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.errors import DomainError
from app.modules.menu.models import Canteen, Station
from app.modules.orders.models import FulfillmentEvent, Order, OrderLine, PickupCredential
from app.modules.orders.service import StaffScope, cancel_order, confirm_line
from app.modules.payments import models as payment_models  # noqa: F401  (register tables)

pytestmark = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL required for PostgreSQL race tests",
)


@pytest.fixture
def pg():
    url = os.environ["TEST_DATABASE_URL"]
    if not url.startswith("postgresql+psycopg://"):
        pytest.fail("Race tests require PostgreSQL")
    schema = "test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db, db.begin():
            db.add(Canteen(id="coe", slug="coe", name="COE"))
            db.flush()
            db.add(Station(id="juice", canteen_id="coe", name="Juice"))
            db.flush()
            db.add(
                Order(
                    id="order",
                    canteen_id="coe",
                    student_id="student",
                    total_paise=10000,
                    state="PAID_ACTIVE",
                    payment_verified_at=datetime.now(UTC),
                )
            )
            db.flush()
            db.add(
                OrderLine(
                    id="line",
                    canteen_id="coe",
                    order_id="order",
                    station_id="juice",
                    station_name="Juice",
                    name="Juice",
                    variant_label="Jumbo",
                    unit_price_paise=5000,
                    quantity=2,
                )
            )
            db.add(PickupCredential(order_id="order", canteen_id="coe", digest="digest"))
        yield engine
    finally:
        engine.dispose()
        # Only the randomly named schema created by this test is removed.
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def race(engine, left, right):
    barrier = Barrier(2)

    def run(action):
        with Session(engine) as db:
            barrier.wait(timeout=10)
            try:
                with db.begin():
                    action(db)
                return "ok"
            except DomainError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run, action) for action in (left, right)]
        return [future.result(timeout=20) for future in futures]


def handover(db, request_id, quantity=1):
    return confirm_line(
        db,
        StaffScope("staff", "device", "coe", "juice", "station"),
        "order",
        "line",
        quantity,
        0,
        request_id,
    )


def test_two_devices_cannot_collect_same_units(pg):
    results = race(
        pg, lambda db: handover(db, "request-one"), lambda db: handover(db, "request-two")
    )
    assert sorted(results) == ["STALE_FULFILLMENT", "ok"]
    with Session(pg) as db:
        assert db.get(OrderLine, "line").fulfilled == 1
        assert len(db.scalars(select(FulfillmentEvent)).all()) == 1


def test_same_request_retry_is_idempotent_under_concurrency(pg):
    assert race(pg, lambda db: handover(db, "same"), lambda db: handover(db, "same")) == [
        "ok",
        "ok",
    ]
    with Session(pg) as db:
        assert db.get(OrderLine, "line").fulfilled == 1


def test_cancel_racing_full_collection_has_one_winner(pg):
    results = race(
        pg, lambda db: handover(db, "collect", 2), lambda db: cancel_order(db, "student", "order")
    )
    assert results.count("ok") == 1
    with Session(pg) as db:
        order = db.get(Order, "order")
        assert order.state in ("CANCELLED", "COLLECTED")
        assert not db.get(PickupCredential, "order").active
        assert db.get(OrderLine, "line").fulfilled == (2 if order.state == "COLLECTED" else 0)
        assert order.refund_status == ("REQUESTED" if order.state == "CANCELLED" else None)


@pytest.fixture
def pg_cart(pg):
    from app.modules.carts.models import Cart, CartLine
    from app.modules.identity.models import Student
    from app.modules.menu.models import Institute, MenuItem, MenuVariant

    with Session(pg) as db, db.begin():
        db.add(Institute(id="institute", slug="coe-institute", name="COE", approved=True))
        db.flush()
        canteen = db.get(Canteen, "coe")
        canteen.institute_id, canteen.approved, canteen.operating = "institute", True, True
        db.add(Student(id="buyer", google_sub="sub", email="buyer@example.test", display_name="B"))
        db.add(MenuItem(id="coffee", canteen_id="coe", name="Coffee", category="Beverages"))
        db.flush()
        db.add(
            MenuVariant(
                id="coffee-regular",
                canteen_id="coe",
                item_id="coffee",
                label="Regular",
                price_paise=4000,
                station_id="juice",
                verified=True,
                available=True,
            )
        )
        db.add(Cart(id="cart", student_id="buyer", canteen_id="coe"))
        db.flush()
        db.add(CartLine(cart_id="cart", canteen_id="coe", variant_id="coffee-regular", quantity=2))
    return pg


def test_double_submitted_checkout_creates_one_order(pg_cart):
    from app.modules.orders.checkout import checkout

    request_id = str(uuid4())
    results = race(
        pg_cart,
        lambda db: checkout(db, "buyer", request_id, 8000),
        lambda db: checkout(db, "buyer", request_id, 8000),
    )
    assert results == ["ok", "ok"]
    with Session(pg_cart) as db:
        orders = db.scalars(select(Order).where(Order.student_id == "buyer")).all()
        assert len(orders) == 1 and orders[0].total_paise == 8000


def test_two_different_checkouts_of_one_cart_create_one_order(pg_cart):
    from app.modules.orders.checkout import checkout

    results = race(
        pg_cart,
        lambda db: checkout(db, "buyer", str(uuid4()), 8000),
        lambda db: checkout(db, "buyer", str(uuid4()), 8000),
    )
    assert sorted(results) == ["CART_EMPTY", "ok"]
    with Session(pg_cart) as db:
        assert len(db.scalars(select(Order).where(Order.student_id == "buyer")).all()) == 1


def test_callback_and_webhook_racing_activate_once(pg):
    from app.modules.payments.models import MerchantAccount, PaymentAttempt
    from app.modules.payments.razorpay import ProviderPayment
    from app.modules.payments.service import apply_capture

    with Session(pg) as db, db.begin():
        db.add(
            MerchantAccount(
                id="merchant",
                canteen_id="coe",
                provider="razorpay",
                key_id="rzp_test_race",
                mode="test",
                display_name="COE",
                active=True,
                created_at=datetime.now(UTC),
            )
        )
        db.add(Order(id="unpaid", canteen_id="coe", student_id="s", total_paise=5000))
        db.flush()
        db.add(
            OrderLine(
                id="unpaid-line",
                canteen_id="coe",
                order_id="unpaid",
                station_id="juice",
                station_name="Juice",
                name="Juice",
                variant_label="Small",
                unit_price_paise=5000,
                quantity=1,
            )
        )
        db.add(
            PaymentAttempt(
                id="attempt",
                canteen_id="coe",
                order_id="unpaid",
                merchant_account_id="merchant",
                provider_order_id="order_Race",
                amount_paise=5000,
                created_at=datetime.now(UTC),
            )
        )
    payment = ProviderPayment("pay_Race", "order_Race", 5000, "INR", "captured")

    def capture(db):
        attempt = db.get(PaymentAttempt, "attempt")
        apply_capture(db, attempt, payment, datetime.now(UTC), "k" * 32)

    assert race(pg, capture, capture) == ["ok", "ok"]
    with Session(pg) as db:
        assert db.get(Order, "unpaid").state == "PAID_ACTIVE"
        assert db.get(PaymentAttempt, "attempt").status == "CAPTURED"
        assert db.get(PickupCredential, "unpaid").active
