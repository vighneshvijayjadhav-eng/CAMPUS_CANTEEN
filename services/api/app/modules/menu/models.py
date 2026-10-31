from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def identifier():
    return str(uuid4())


class SeedSource(Base):
    __tablename__ = "seed_sources"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    sha256: Mapped[str] = mapped_column(String(64))


class Institute(Base):
    __tablename__ = "institutes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)


class Canteen(Base):
    __tablename__ = "canteens"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    institute_id: Mapped[str | None] = mapped_column(ForeignKey("institutes.id"), index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    operating: Mapped[bool] = mapped_column(Boolean, default=False)


class Station(Base):
    __tablename__ = "canteen_stations"
    __table_args__ = (UniqueConstraint("canteen_id", "id"), UniqueConstraint("canteen_id", "name"))
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        UniqueConstraint("canteen_id", "id"),
        UniqueConstraint("canteen_id", "source_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    category: Mapped[str] = mapped_column(String(120))
    name: Mapped[str] = mapped_column(String(160))
    source_id: Mapped[str | None] = mapped_column(String(160))
    source_sheet: Mapped[str | None] = mapped_column(String(80))
    source_row: Mapped[int | None]
    source_sha256: Mapped[str | None] = mapped_column(String(64))
    archived: Mapped[bool] = mapped_column(Boolean, default=False)


class MenuVariant(Base):
    __tablename__ = "menu_variants"
    __table_args__ = (
        ForeignKeyConstraint(["canteen_id", "item_id"], ["menu_items.canteen_id", "menu_items.id"]),
        ForeignKeyConstraint(
            ["canteen_id", "station_id"], ["canteen_stations.canteen_id", "canteen_stations.id"]
        ),
        UniqueConstraint("item_id", "source_column"),
        UniqueConstraint("canteen_id", "id"),
        CheckConstraint("price_paise IS NULL OR price_paise > 0"),
        CheckConstraint(
            "NOT available OR (verified AND price_paise IS NOT NULL AND station_id IS NOT NULL)"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    item_id: Mapped[str] = mapped_column(String(36))
    label: Mapped[str] = mapped_column(String(80))
    price_paise: Mapped[int | None]
    source_column: Mapped[str | None] = mapped_column(String(8))
    source_value: Mapped[str | None] = mapped_column(String(80))
    station_id: Mapped[str | None] = mapped_column(String(36))
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    available: Mapped[bool] = mapped_column(Boolean, default=False)
