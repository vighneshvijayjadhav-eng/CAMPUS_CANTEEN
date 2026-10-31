from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.errors import DomainError
from app.modules.menu.models import Canteen, Station
from app.modules.orders.models import Order, OrderLine, PickupCredential
from app.modules.orders.pickup import code_digest, lookup
from app.modules.orders.service import StaffScope

KEY = "test-only-long-key-never-for-production"


def test_lookup_is_read_only_scoped_and_does_not_expire():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add(Canteen(id="coe", slug="coe", name="COE"))
        db.add(Station(id="juice", canteen_id="coe", name="Juice"))
        db.add(
            Order(
                id="order",
                canteen_id="coe",
                student_id="student",
                state="PAID_ACTIVE",
                total_paise=5000,
                payment_verified_at=datetime.now(UTC) - timedelta(days=2),
            )
        )
        db.add(
            OrderLine(
                id="line",
                canteen_id="coe",
                order_id="order",
                station_id="juice",
                station_name="Juice",
                name="Juice",
                variant_label="Small",
                unit_price_paise=5000,
                quantity=1,
            )
        )
        db.add(
            PickupCredential(
                order_id="order", canteen_id="coe", digest=code_digest(KEY, "coe", "001234")
            )
        )
        db.commit()
        scope = StaffScope("actor", "session", "coe", "juice", "station")
        assert lookup(db, scope, "001234", KEY)["lines"][0]["remaining"] == 1
        assert db.get(OrderLine, "line").fulfilled == 0
        assert db.get(PickupCredential, "order").active
        for actor in [
            StaffScope("a", "s", "ioit", "juice", "station"),
            StaffScope("a", "s", "coe", "snacks", "station"),
        ]:
            with pytest.raises(DomainError, match="PICKUP_NOT_FOUND"):
                lookup(db, actor, "001234", KEY)
        db.get(PickupCredential, "order").active = False
        db.flush()
        with pytest.raises(DomainError, match="PICKUP_NOT_FOUND"):
            lookup(db, scope, "001234", KEY)


@pytest.mark.parametrize("code", ["12345", "1234567", "abcdef", "１２３４５６"])
def test_pickup_is_six_ascii_digits(code):
    with pytest.raises(DomainError):
        code_digest(KEY, "coe", code)
