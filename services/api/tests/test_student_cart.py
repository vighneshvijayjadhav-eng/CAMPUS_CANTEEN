import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.errors import DomainError
from app.modules.carts.service import clear, set_line, view
from app.modules.identity.models import Student
from app.modules.menu.models import Canteen, Institute, MenuItem, MenuVariant, Station


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        institute = Institute(id="coe-institute", slug="coe", name="COE", approved=True)
        db.add(institute)
        db.flush()
        db.add_all(
            [
                Student(
                    id="student",
                    google_sub="subject",
                    email="student@example.test",
                    display_name="Student",
                ),
                Canteen(
                    id="coe",
                    institute_id=institute.id,
                    slug="coe-canteen",
                    name="COE Canteen",
                    approved=True,
                    operating=True,
                ),
                Canteen(
                    id="ioit",
                    institute_id=institute.id,
                    slug="ioit-canteen",
                    name="IOIT Canteen",
                    approved=True,
                    operating=True,
                ),
                Station(id="juice", canteen_id="coe", name="Juice"),
                Station(id="snacks", canteen_id="ioit", name="Snacks"),
                MenuItem(id="coffee", canteen_id="coe", name="Coffee", category="Beverages"),
                MenuItem(id="sandwich", canteen_id="ioit", name="Sandwich", category="Snacks"),
            ]
        )
        db.flush()
        db.add_all(
            [
                MenuVariant(
                    id="coffee-regular",
                    canteen_id="coe",
                    item_id="coffee",
                    label="Regular",
                    price_paise=4000,
                    station_id="juice",
                    verified=True,
                    available=True,
                ),
                MenuVariant(
                    id="sandwich-regular",
                    canteen_id="ioit",
                    item_id="sandwich",
                    label="Regular",
                    price_paise=5000,
                    station_id="snacks",
                    verified=True,
                    available=True,
                ),
            ]
        )
        db.commit()
        yield db


def test_one_canteen_cart_with_authoritative_totals(db):
    set_line(db, "student", "coffee-regular", 2)
    cart = view(db, "student")
    assert cart["canteen_id"] == "coe"
    assert cart["total_paise"] == 8000
    assert cart["lines"] == [
        {
            "variant_id": "coffee-regular",
            "item_name": "Coffee",
            "variant": "Regular",
            "quantity": 2,
            "unit_price_paise": 4000,
            "line_total_paise": 8000,
            "orderable": True,
        }
    ]
    with pytest.raises(DomainError, match="CART_CANTEEN_CONFLICT"):
        set_line(db, "student", "sandwich-regular", 1)
    set_line(db, "student", "coffee-regular", 0)
    set_line(db, "student", "sandwich-regular", 1)
    assert view(db, "student")["canteen_id"] == "ioit"


@pytest.mark.parametrize("quantity", [-1, 100, True, 1.5])
def test_cart_rejects_invalid_quantities(db, quantity):
    with pytest.raises(DomainError, match="INVALID_QUANTITY"):
        set_line(db, "student", "coffee-regular", quantity)


def test_cart_rechecks_availability_and_station(db):
    variant = db.get(MenuVariant, "coffee-regular")
    variant.available = False
    db.flush()
    with pytest.raises(DomainError, match="MENU_VARIANT_UNAVAILABLE"):
        set_line(db, "student", "coffee-regular", 1)
    variant.available = True
    db.get(Station, "juice").active = False
    db.flush()
    with pytest.raises(DomainError, match="MENU_VARIANT_UNAVAILABLE"):
        set_line(db, "student", "coffee-regular", 1)


def test_cart_view_marks_an_inactive_station_unorderable(db):
    set_line(db, "student", "coffee-regular", 1)
    db.get(Station, "juice").active = False
    db.flush()
    assert view(db, "student")["lines"][0]["orderable"] is False


def test_clear_cart_preserves_no_purchasable_data(db):
    set_line(db, "student", "coffee-regular", 1)
    clear(db, "student")
    assert view(db, "student") == {"canteen_id": "coe", "lines": [], "total_paise": 0}
