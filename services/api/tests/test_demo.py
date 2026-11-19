from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine, event, func, select
from sqlalchemy.orm import Session

from app.core.config import RazorpayCredential, Settings
from app.core.db import Base
from app.modules.identity.models import StaffAccount, Student
from app.modules.menu.models import Canteen, MenuItem, MenuVariant, Station
from app.modules.menu.seed import read_menu, seed_menu
from app.modules.orders.models import Order
from app.modules.payments.models import MerchantAccount
from app.modules.reviews.models import Review
from app.ops.demo import counter_for, demo_history, setup_canteens, setup_payments
from app.ops.verify import check

ROOT = Path(__file__).resolve().parents[3]
BASE = {"pickup_hmac_key": "x" * 32}


@pytest.mark.parametrize(
    "url",
    ["postgres://u:p@host/db?sslmode=require", "postgresql://u:p@host/db?sslmode=require"],
)
def test_hosted_postgres_urls_get_the_psycopg_driver(url):
    settings = Settings(_env_file=None, database_url=url, **BASE)
    assert settings.database_url == "postgresql+psycopg://u:p@host/db?sslmode=require"


def test_counter_mapping():
    assert counter_for("Juice & Beverages", "Limbu Soda") == "Beverages"
    assert counter_for("Regular Menu", "Chai") == "Beverages"
    assert counter_for("Extras", "Lassi") == "Beverages"
    assert counter_for("South Indian", "Masala Dosa") == "Meals"
    assert counter_for("Chaat", "Bhel") == "Snacks"


@pytest.fixture
def seeded():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        seed_menu(db, read_menu(ROOT / "data/AISSMS_Canteen_Menu.xlsx"))
        db.commit()
        yield db


def settings_with_key():
    credential = RazorpayCredential(key_secret="s", webhook_secret="w")
    return SimpleNamespace(
        razorpay_key_id="rzp_test_demo", razorpay_credentials={"rzp_test_demo": credential}
    )


def test_demo_setup_is_complete_and_idempotent(seeded):
    db = seeded
    summary = setup_canteens(db, "demo-password-long")
    assert setup_payments(db, settings_with_key(), summary["coe"][0]).startswith(
        "Razorpay test key active"
    )
    assert demo_history(db, summary).startswith("Added")
    db.commit()
    for canteen in db.scalars(select(Canteen)):
        assert canteen.approved and canteen.operating
        names = {
            s.name for s in db.scalars(select(Station).where(Station.canteen_id == canteen.id))
        }
        assert names == {"Snacks", "Beverages", "Meals"}
    variants = db.scalars(select(MenuVariant)).all()
    assert all(v.station_id and v.verified for v in variants)
    unavailable = {db.get(MenuItem, v.item_id).name for v in variants if not v.available}
    assert unavailable == {"Club Sandwich", "Paneer Pulao"}
    usernames = set(db.scalars(select(StaffAccount.username)))
    assert {"coe-admin", "coe-snacks", "coe-beverages", "coe-meals", "ioit-admin"} <= usernames
    assert db.scalar(
        select(MerchantAccount).where(MerchantAccount.key_id == "rzp_test_demo")
    ).active
    orders = db.scalar(select(func.count()).select_from(Order))
    reviews = db.scalar(select(func.count()).select_from(Review))
    assert orders > 20 and reviews > 0
    assert all(s.email.endswith("@demo.invalid") for s in db.scalars(select(Student)))
    _, problems = check(db, check_migrations=False)
    assert problems == {}
    # A second start changes nothing.
    summary = setup_canteens(db, "another-password-long")
    setup_payments(db, settings_with_key(), summary["coe"][0])
    assert demo_history(db, summary) == "Demo history already present"
    db.commit()
    assert db.scalar(select(func.count()).select_from(Order)) == orders
    assert db.scalar(select(func.count()).select_from(StaffAccount)) == len(usernames)


def test_demo_without_razorpay_keys_says_so(seeded):
    summary = setup_canteens(seeded, "demo-password-long")
    no_keys = SimpleNamespace(razorpay_key_id=None, razorpay_credentials={})
    assert "not configured" in setup_payments(seeded, no_keys, summary["coe"][0])
