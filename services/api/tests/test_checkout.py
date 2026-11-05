from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

import app.modules.orders.checkout as checkout_module
from app.core.db import Base
from app.core.errors import DomainError
from app.modules.carts.service import set_line, view
from app.modules.identity.models import Student
from app.modules.menu.models import Canteen, Institute, MenuItem, MenuVariant, Station
from app.modules.menu.schedule import closed_reason, replace_hours
from app.modules.orders.checkout import checkout, student_order_detail, student_orders
from app.modules.orders.models import Order, OrderLine
from app.modules.orders.service import StaffScope, active_queue

# Thursday 5 Nov 2026, 06:30 UTC = 12:00 IST.
NOON_IST = datetime(2026, 11, 5, 6, 30, tzinfo=UTC)
REQUEST = "11111111-1111-4111-8111-111111111111"


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    clock = {"now": NOON_IST}
    monkeypatch.setattr(checkout_module, "server_now", lambda _: clock["now"])
    with Session(engine) as db:
        db.add(Institute(id="coe-institute", slug="coe", name="COE", approved=True))
        db.flush()
        db.add_all(
            [
                Student(id="student", google_sub="s1", email="a@example.test", display_name="A"),
                Student(id="other", google_sub="s2", email="b@example.test", display_name="B"),
                Canteen(
                    id="coe",
                    institute_id="coe-institute",
                    slug="coe-canteen",
                    name="COE Canteen",
                    approved=True,
                    operating=True,
                ),
                Station(id="juice", canteen_id="coe", name="Juice"),
                Station(id="snacks", canteen_id="coe", name="Snacks"),
                MenuItem(id="coffee", canteen_id="coe", name="Coffee", category="Beverages"),
                MenuItem(id="samosa", canteen_id="coe", name="Samosa", category="Snacks"),
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
                    id="samosa-plate",
                    canteen_id="coe",
                    item_id="samosa",
                    label="Plate",
                    price_paise=2500,
                    station_id="snacks",
                    verified=True,
                    available=True,
                ),
            ]
        )
        db.commit()
        yield db, clock


def fill_cart(db):
    set_line(db, "student", "coffee-regular", 2)
    set_line(db, "student", "samosa-plate", 1)
    return view(db, "student")["total_paise"]


def order_count(db):
    return db.scalar(select(func.count()).select_from(Order))


def test_checkout_freezes_cart_into_pending_order(db):
    session, _ = db
    total = fill_cart(session)
    assert total == 10500
    order = checkout(session, "student", REQUEST, total)
    assert order.state == "PAYMENT_PENDING"
    assert order.total_paise == 10500
    assert order.payment_verified_at is None
    lines = {
        line.variant_id: line
        for line in session.scalars(select(OrderLine).where(OrderLine.order_id == order.id))
    }
    assert lines["coffee-regular"].unit_price_paise == 4000
    assert lines["coffee-regular"].quantity == 2
    assert lines["coffee-regular"].station_name == "Juice"
    assert lines["samosa-plate"].station_id == "snacks"
    assert view(session, "student")["lines"] == []
    # Unpaid orders never reach a station queue.
    admin = StaffScope("admin", "session", "coe", None, "admin")
    assert active_queue(session, admin) == []


def test_order_snapshot_is_immutable_after_menu_edits(db):
    session, _ = db
    order = checkout(session, "student", REQUEST, fill_cart(session))
    variant = session.get(MenuVariant, "coffee-regular")
    variant.price_paise = 9900
    variant.label = "Renamed"
    session.get(Station, "juice").name = "Beverages"
    session.flush()
    detail = student_order_detail(session, "student", order.id)
    coffee = next(line for line in detail["lines"] if line["name"] == "Coffee")
    assert (coffee["unit_price_paise"], coffee["variant"], coffee["station"]) == (
        4000,
        "Regular",
        "Juice",
    )
    assert detail["total_paise"] == 10500


def test_retried_checkout_is_idempotent(db):
    session, _ = db
    total = fill_cart(session)
    first = checkout(session, "student", REQUEST, total)
    again = checkout(session, "student", REQUEST, total)
    assert again.id == first.id
    assert order_count(session) == 1
    with pytest.raises(DomainError, match="IDEMPOTENCY_CONFLICT"):
        checkout(session, "student", REQUEST, total + 100)


def test_price_change_before_checkout_is_rejected_and_cart_kept(db):
    session, _ = db
    total = fill_cart(session)
    session.get(MenuVariant, "coffee-regular").price_paise = 4500
    session.flush()
    with pytest.raises(DomainError, match="PRICE_CHANGED"):
        checkout(session, "student", REQUEST, total)
    assert order_count(session) == 0
    assert view(session, "student")["total_paise"] == 11500
    assert checkout(session, "student", REQUEST, 11500).total_paise == 11500


@pytest.mark.parametrize(
    "change",
    [
        lambda s: setattr(s.get(MenuVariant, "samosa-plate"), "available", False),
        lambda s: setattr(s.get(Station, "snacks"), "active", False),
        lambda s: setattr(s.get(MenuItem, "samosa"), "archived", True),
    ],
)
def test_unavailable_item_blocks_checkout(db, change):
    session, _ = db
    total = fill_cart(session)
    change(session)
    session.flush()
    with pytest.raises(DomainError, match="CART_ITEM_UNAVAILABLE"):
        checkout(session, "student", REQUEST, total)
    assert order_count(session) == 0


def test_empty_cart_cannot_check_out(db):
    session, _ = db
    with pytest.raises(DomainError, match="CART_EMPTY"):
        checkout(session, "student", REQUEST, 100)


def test_non_operating_canteen_rejects_checkout(db):
    session, _ = db
    total = fill_cart(session)
    session.get(Canteen, "coe").operating = False
    session.flush()
    with pytest.raises(DomainError, match="CANTEEN_NOT_OPERATING"):
        checkout(session, "student", REQUEST, total)


def test_weekly_hours_use_india_time(db):
    session, clock = db
    canteen = session.get(Canteen, "coe")
    assert closed_reason(session, canteen, NOON_IST) is None  # no hours: switch only
    # Thursday (weekday 3) 08:00-17:00 IST.
    replace_hours(session, "coe", [{"weekday": 3, "opens": "08:00", "closes": "17:00"}])
    assert closed_reason(session, canteen, NOON_IST) is None
    # 17:00 IST is 11:30 UTC: closing time is exclusive.
    assert closed_reason(session, canteen, NOON_IST.replace(hour=11, minute=30)) == (
        "CANTEEN_CLOSED"
    )
    # 07:59 IST is 02:29 UTC.
    assert closed_reason(session, canteen, NOON_IST.replace(hour=2, minute=29)) == (
        "CANTEEN_CLOSED"
    )
    # Friday has no window once any hours exist.
    assert closed_reason(session, canteen, datetime(2026, 11, 6, 6, 30, tzinfo=UTC)) == (
        "CANTEEN_CLOSED"
    )
    total = fill_cart(session)
    clock["now"] = NOON_IST.replace(hour=12)  # 17:30 IST
    with pytest.raises(DomainError, match="CANTEEN_CLOSED"):
        checkout(session, "student", REQUEST, total)


@pytest.mark.parametrize(
    "windows,error",
    [
        (
            [
                {"weekday": 1, "opens": "08:00", "closes": "10:00"},
                {"weekday": 1, "opens": "11:00", "closes": "12:00"},
            ],
            "DUPLICATE_WEEKDAY",
        ),
        ([{"weekday": 1, "opens": "10:00", "closes": "09:00"}], "INVALID_HOURS"),
    ],
)
def test_hours_validation(db, windows, error):
    session, _ = db
    with pytest.raises(DomainError, match=error):
        replace_hours(session, "coe", windows)


def test_students_only_see_their_own_orders(db):
    session, _ = db
    order = checkout(session, "student", REQUEST, fill_cart(session))
    history = student_orders(session, "student")
    assert [row["id"] for row in history] == [order.id]
    assert history[0]["canteen_name"] == "COE Canteen"
    assert history[0]["state_label"] == "Awaiting payment"
    assert student_orders(session, "other") == []
    with pytest.raises(DomainError, match="ORDER_NOT_FOUND"):
        student_order_detail(session, "other", order.id)
    detail = student_order_detail(session, "student", order.id)
    assert detail["pickup_code"] is None
    assert detail["remaining_by_station"] == [
        {"station": "Juice", "remaining": 2},
        {"station": "Snacks", "remaining": 1},
    ]
