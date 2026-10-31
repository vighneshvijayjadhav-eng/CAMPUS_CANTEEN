"""Read the authoritative workbook; insert missing source rows without updating staff data."""

import argparse
import hashlib
import json
import os
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook
from sqlalchemy import select

from app.core.db import connect, session_for
from app.modules.menu.models import Canteen, MenuItem, MenuVariant, SeedSource

SHEETS = {"ioit": "IOIT Canteen", "coe": "COE Canteen"}


def price_paise(value):
    if isinstance(value, bool) or not isinstance(value, (int, float, Decimal)):
        return None
    amount = Decimal(str(value)) * 100
    if not amount.is_finite() or amount <= 0 or amount != amount.to_integral_value():
        raise ValueError(f"Invalid numeric price: {value}")
    return int(amount)


def read_menu(path: Path):
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    workbook = load_workbook(path, read_only=True, data_only=False)
    menus = {}
    try:
        for slug, sheet_name in SHEETS.items():
            sheet = workbook[sheet_name]
            expected = (
                ("Category", "Item", "Price (₹)")
                if slug == "ioit"
                else ("Subcategory", "Item", "Jumbo Price (₹)", "Small Price (₹)")
            )
            if tuple(cell.value for cell in sheet[2]) != expected:
                raise ValueError(f"Unexpected source columns in {sheet_name}")
            items = []
            for row_number, row in enumerate(sheet.iter_rows(min_row=3, values_only=True), 3):
                if not any(value is not None for value in row):
                    continue
                category, name, *prices = row
                if not isinstance(category, str) or not isinstance(name, str):
                    raise ValueError(f"Missing category/name: {sheet_name}:{row_number}")
                variants = []
                for index, raw in enumerate(prices):
                    # A dash means that size is not offered, never a free product.
                    if index == 1 and raw in (None, "", "-", "—"):
                        continue
                    variants.append(
                        {
                            "label": "Regular"
                            if slug == "ioit"
                            else ("Jumbo / standard (confirm label)" if index == 0 else "Small"),
                            "price_paise": price_paise(raw),
                            "source_column": chr(ord("C") + index),
                            "source_value": str(raw) if raw is not None else None,
                        }
                    )
                items.append(
                    {
                        "source_id": f"aissms-menu-v1:{slug}:{row_number}",
                        "source_sheet": sheet_name,
                        "source_row": row_number,
                        "source_sha256": digest,
                        "category": category,
                        "name": name,
                        "variants": variants,
                    }
                )
            menus[slug] = items
    finally:
        workbook.close()
    return menus


def compare_draft(menus, draft_path: Path):
    draft = json.loads(draft_path.read_text(encoding="utf-8"))["menus"]

    def comparable(rows):
        return [
            (
                r["source_sheet"],
                r["source_row"],
                r["category"],
                r["name"],
                [(v["label"], v["price_paise"]) for v in r["variants"]],
            )
            for r in rows
        ]

    if set(draft) != set(menus) or any(
        comparable(menus[key]) != comparable(draft[key]) for key in menus
    ):
        raise ValueError("Draft transcription differs from authoritative workbook")


def seed_menu(db, menus):
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy import text

        db.execute(text("SELECT pg_advisory_xact_lock(1840182026)"))
    hashes = {row["source_sha256"] for rows in menus.values() for row in rows}
    if len(hashes) != 1:
        raise ValueError("Seed requires one nonempty authoritative workbook")
    digest = hashes.pop()
    source = db.get(SeedSource, "aissms-menu-v1")
    if source and source.sha256 != digest:
        raise ValueError("Workbook changed; review source IDs before importing a new revision")
    if source is None:
        db.add(SeedSource(id="aissms-menu-v1", sha256=digest))
    inserted = 0
    for slug, rows in menus.items():
        canteen = db.scalar(select(Canteen).where(Canteen.slug == slug))
        if canteen is None:
            canteen = Canteen(
                slug=slug,
                name=("IOIT Canteen (P.R. Enterprises)" if slug == "ioit" else "COE Canteen"),
            )
            db.add(canteen)
            db.flush()
        for row in rows:
            existing = db.scalar(
                select(MenuItem.id).where(
                    MenuItem.canteen_id == canteen.id, MenuItem.source_id == row["source_id"]
                )
            )
            if existing:
                continue
            item = MenuItem(
                canteen_id=canteen.id, **{k: v for k, v in row.items() if k != "variants"}
            )
            db.add(item)
            db.flush()
            for variant in row["variants"]:
                db.add(MenuVariant(canteen_id=canteen.id, item_id=item.id, **variant))
            inserted += 1
    db.flush()
    return inserted


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--compare-draft", type=Path)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    menus = read_menu(args.workbook)
    if args.compare_draft:
        compare_draft(menus, args.compare_draft)
    if not args.check_only:
        engine = connect(os.environ["DATABASE_URL"])
        with session_for(engine) as db, db.begin():
            print(f"Inserted {seed_menu(db, menus)} items; existing rows unchanged.")
    print(
        {
            slug: {"items": len(rows), "variants": sum(len(r["variants"]) for r in rows)}
            for slug, rows in menus.items()
        }
    )


if __name__ == "__main__":
    main()
