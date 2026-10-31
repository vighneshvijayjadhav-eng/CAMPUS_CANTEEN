from pathlib import Path

import pytest
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app.core.db import Base
from app.modules.menu.models import Canteen, Institute, MenuItem, MenuVariant
from app.modules.menu.seed import compare_draft, price_paise, read_menu, seed_menu

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_workbook_and_draft():
    menus = read_menu(ROOT / "data/AISSMS_Canteen_Menu.xlsx")
    compare_draft(menus, ROOT / "data/menu_seed_draft.json")
    assert {key: len(rows) for key, rows in menus.items()} == {"ioit": 85, "coe": 42}
    assert sum(len(r["variants"]) for r in menus["coe"]) == 60
    unknown = [r["name"] for r in menus["ioit"] if r["variants"][0]["price_paise"] is None]
    assert len(unknown) == 5


def test_seed_preserves_staff_edits(db):
    menus = read_menu(ROOT / "data/AISSMS_Canteen_Menu.xlsx")
    assert seed_menu(db, menus) == 127
    assert len(db.scalars(select(Canteen)).all()) == 2
    assert len(db.scalars(select(Institute)).all()) == 2
    assert all(canteen.institute_id for canteen in db.scalars(select(Canteen)))
    variants = db.scalars(select(MenuVariant)).all()
    assert len(variants) == 145
    assert all(not v.available and not v.verified and v.station_id is None for v in variants)
    item = db.scalar(select(MenuItem))
    item.name = "Staff edited name"
    item.archived = True
    variants[0].price_paise = 12300
    db.commit()
    assert seed_menu(db, menus) == 0
    assert item.name == "Staff edited name" and item.archived
    assert variants[0].price_paise == 12300


@pytest.mark.parametrize("value", [None, "Verify", "—", "40", True])
def test_unknown_prices_are_never_zero(value):
    assert price_paise(value) is None


@pytest.mark.parametrize("value", [0, -1, 1.001, float("inf")])
def test_invalid_numeric_prices_fail(value):
    with pytest.raises(ValueError):
        price_paise(value)


def test_decimal_price():
    assert price_paise(12.50) == 1250
