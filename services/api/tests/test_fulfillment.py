from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.errors import DomainError
from app.modules.menu.models import Canteen, Station
from app.modules.orders import service
from app.modules.orders.models import (
    FulfillmentEvent,
    Order,
    OrderException,
    OrderLine,
    PickupCredential,
)
from app.modules.orders.service import StaffScope, active_queue, cancel_order, confirm_line

NOW = datetime(2026, 10, 18, 12, tzinfo=UTC)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    monkeypatch.setattr(service, "server_now", lambda _: NOW)
    with Session(engine, expire_on_commit=False) as db:
        db.add_all(
            [
                Canteen(id="coe", slug="coe", name="COE"),
                Canteen(id="ioit", slug="ioit", name="IOIT"),
            ]
        )
        db.flush()
        for name in ["juice", "snacks", "meals"]:
            db.add(Station(id=name, canteen_id="coe", name=name))
        db.flush()
        db.add(
            Order(
                id="order",
                canteen_id="coe",
                student_id="student",
                total_paise=30000,
                state="PAID_ACTIVE",
                payment_verified_at=NOW,
            )
        )
        db.flush()
        for name in ["juice", "snacks", "meals"]:
            db.add(
                OrderLine(
                    id=name,
                    canteen_id="coe",
                    order_id="order",
                    station_id=name,
                    station_name=name,
                    name=name,
                    variant_label="Regular",
                    unit_price_paise=5000,
                    quantity=2,
                )
            )
        db.add(
            PickupCredential(
                order_id="order", canteen_id="coe", digest="digest", encrypted_code="encrypted"
            )
        )
        db.commit()
        yield db


def scope(station="juice", canteen="coe", role="station"):
    return StaffScope("actor", "device", canteen, station, role)


def confirm(db, station="juice", quantity=2, expected=0, request=None, actor=None):
    return confirm_line(
        db, actor or scope(station), "order", station, quantity, expected, request or str(uuid4())
    )


def test_three_queues_one_credential_partial_and_full_collection(db):
    for station in ["juice", "snacks", "meals"]:
        queue = active_queue(db, scope(station))
        assert [line["id"] for line in queue[0]["lines"]] == [station]
    assert len(active_queue(db, scope(role="admin"))[0]["lines"]) == 3
    assert active_queue(db, scope(canteen="ioit")) == []
    assert confirm(db).state == "PARTIALLY_COLLECTED"
    assert active_queue(db, scope()) == []
    assert db.get(PickupCredential, "order").active
    order = db.get(Order, "order")
    order.payment_verified_at = NOW - timedelta(hours=8)
    db.flush()
    confirm(db, "snacks")
    assert confirm(db, "meals").state == "COLLECTED"
    assert not db.get(PickupCredential, "order").active
    assert db.get(PickupCredential, "order").encrypted_code is None
    assert len(db.scalars(select(FulfillmentEvent)).all()) == 3
    with pytest.raises(DomainError, match="ORDER_NOT_COLLECTABLE"):
        confirm(db, "meals", expected=2)


def test_admin_confirms_only_selected_quantity(db):
    confirm(db, "snacks", quantity=1, actor=scope(role="admin"))
    assert db.get(OrderLine, "snacks").fulfilled == 1
    assert db.get(OrderLine, "juice").fulfilled == 0
    assert db.get(OrderLine, "meals").fulfilled == 0


def test_station_and_tenant_denial(db):
    with pytest.raises(DomainError, match="LINE_NOT_FOUND"):
        confirm(db, "snacks", actor=scope())
    with pytest.raises(DomainError, match="ORDER_NOT_FOUND"):
        confirm(db, actor=scope(canteen="ioit"))
    assert db.get(OrderLine, "snacks").fulfilled == 0


def test_retry_and_stale_device_cannot_double_handover(db):
    request = str(uuid4())
    confirm(db, quantity=1, request=request)
    confirm(db, quantity=1, request=request)
    assert db.get(OrderLine, "juice").fulfilled == 1
    with pytest.raises(DomainError, match="STALE_FULFILLMENT"):
        confirm(db, quantity=1)
    with pytest.raises(DomainError, match="IDEMPOTENCY_CONFLICT"):
        confirm(db, quantity=2, request=request)
    confirm(db, quantity=1, expected=1)
    assert db.get(OrderLine, "juice").fulfilled == 2


@pytest.mark.parametrize("quantity", [0, -1, True, 1.5, 3])
def test_invalid_quantity(db, quantity):
    with pytest.raises(DomainError):
        confirm(db, quantity=quantity)
    assert db.get(OrderLine, "juice").fulfilled == 0


@pytest.mark.parametrize("age,allowed", [(299, True), (300, False), (301, False)])
def test_cancellation_cutoff(db, age, allowed):
    db.get(Order, "order").payment_verified_at = NOW - timedelta(seconds=age)
    db.flush()
    if allowed:
        order = cancel_order(db, "student", "order")
        assert order.state == "CANCELLED" and order.refund_status == "REQUESTED"
        assert not db.get(PickupCredential, "order").active
        assert active_queue(db, scope(role="admin")) == []
        with pytest.raises(DomainError, match="ORDER_NOT_COLLECTABLE"):
            confirm(db)
    else:
        with pytest.raises(DomainError, match="CANCELLATION_WINDOW_CLOSED"):
            cancel_order(db, "student", "order")


def test_partial_cancellation_records_exception_without_refund(db):
    confirm(db, quantity=1)
    order = cancel_order(db, "student", "order")
    assert order.state == "PARTIALLY_COLLECTED"
    assert order.exception_status == "STAFF_REVIEW_REQUIRED"
    assert order.refund_status is None
    assert db.get(PickupCredential, "order").active
    assert db.get(OrderException, "order").requested_by == "student"
    cancel_order(db, "student", "order")
    assert len(db.scalars(select(OrderException)).all()) == 1


def test_other_student_cannot_cancel(db):
    with pytest.raises(DomainError, match="ORDER_NOT_FOUND"):
        cancel_order(db, "other", "order")


def test_unverified_payment_cannot_enter_queue_or_be_collected(db):
    db.get(Order, "order").payment_verified_at = None
    db.flush()
    assert active_queue(db, scope()) == []
    with pytest.raises(DomainError, match="ORDER_NOT_COLLECTABLE"):
        confirm(db)
