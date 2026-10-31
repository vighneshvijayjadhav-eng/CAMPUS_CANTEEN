from uuid import UUID

from fastapi import APIRouter
from pydantic import Field
from sqlalchemy import select

from app.core.errors import DomainError
from app.core.http import DB, STAFF, Input, admin
from app.modules.menu.models import Canteen, MenuItem, MenuVariant, Station


class StationInput(Input):
    name: str = Field(min_length=1, max_length=80, pattern=r"\S")
    active: bool = True


class VariantInput(Input):
    label: str = Field(min_length=1, max_length=80)
    price_paise: int | None = Field(default=None, gt=0, le=10000000, strict=True)
    station_id: UUID | None = None
    verified: bool = False
    available: bool = False


class ItemInput(Input):
    name: str = Field(min_length=1, max_length=160)
    category: str = Field(min_length=1, max_length=120)
    archived: bool = False


def create_router(settings, engine):
    router = APIRouter()

    @router.get("/api/v1/canteens")
    def canteens(db: DB):
        return [
            {
                "id": c.id,
                "slug": c.slug,
                "name": c.name,
                "approved": c.approved,
                "operating": c.operating,
            }
            for c in db.scalars(select(Canteen).order_by(Canteen.slug))
        ]

    def menu_rows(db, canteen_id):
        items = list(
            db.scalars(
                select(MenuItem)
                .where(MenuItem.canteen_id == canteen_id)
                .order_by(MenuItem.category, MenuItem.name)
            )
        )
        variants = list(db.scalars(select(MenuVariant).where(MenuVariant.canteen_id == canteen_id)))
        return [
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "archived": item.archived,
                "source_sheet": item.source_sheet,
                "source_row": item.source_row,
                "variants": [
                    {
                        "id": v.id,
                        "label": v.label,
                        "price_paise": v.price_paise,
                        "station_id": v.station_id,
                        "verified": v.verified,
                        "available": v.available,
                    }
                    for v in variants
                    if v.item_id == item.id
                ],
            }
            for item in items
        ]

    @router.get("/api/v1/canteens/{canteen_id}/menu")
    def public_menu(canteen_id: UUID, db: DB):
        return [item for item in menu_rows(db, str(canteen_id)) if not item["archived"]]

    @router.get("/api/v1/staff/menu")
    def staff_menu(db: DB, scope: STAFF):
        admin(scope)
        return menu_rows(db, scope.canteen_id)

    @router.post("/api/v1/staff/menu")
    def add_item(body: ItemInput, db: DB, scope: STAFF):
        admin(scope)
        item = MenuItem(canteen_id=scope.canteen_id, **body.model_dump())
        db.add(item)
        db.flush()
        return {"id": item.id}

    @router.patch("/api/v1/staff/menu/{item_id}")
    def edit_item(item_id: UUID, body: ItemInput, db: DB, scope: STAFF):
        admin(scope)
        item = db.get(MenuItem, str(item_id))
        if not item or item.canteen_id != scope.canteen_id:
            raise DomainError("ITEM_NOT_FOUND", 404)
        for key, value in body.model_dump().items():
            setattr(item, key, value)
        return {"id": item.id}

    def variant_values(body, db, scope):
        values = body.model_dump()
        values["station_id"] = str(body.station_id) if body.station_id else None
        if body.station_id:
            station = db.get(Station, str(body.station_id))
            if not station or station.canteen_id != scope.canteen_id or not station.active:
                raise DomainError("STATION_NOT_FOUND", 404)
        if body.available and (not body.verified or not body.price_paise or not body.station_id):
            raise DomainError("VERIFY_PRICE_AND_STATION_FIRST", 422)
        return values

    @router.post("/api/v1/staff/menu/{item_id}/variants")
    def add_variant(item_id: UUID, body: VariantInput, db: DB, scope: STAFF):
        admin(scope)
        item = db.get(MenuItem, str(item_id))
        if not item or item.canteen_id != scope.canteen_id:
            raise DomainError("ITEM_NOT_FOUND", 404)
        variant = MenuVariant(
            canteen_id=scope.canteen_id, item_id=item.id, **variant_values(body, db, scope)
        )
        db.add(variant)
        db.flush()
        return {"id": variant.id}

    @router.patch("/api/v1/staff/variants/{variant_id}")
    def edit_variant(variant_id: UUID, body: VariantInput, db: DB, scope: STAFF):
        admin(scope)
        variant = db.get(MenuVariant, str(variant_id))
        if not variant or variant.canteen_id != scope.canteen_id:
            raise DomainError("VARIANT_NOT_FOUND", 404)
        for key, value in variant_values(body, db, scope).items():
            setattr(variant, key, value)
        return {"id": variant.id}

    @router.get("/api/v1/staff/stations")
    def stations(db: DB, scope: STAFF):
        query = select(Station).where(Station.canteen_id == scope.canteen_id)
        if scope.role != "admin":
            query = query.where(Station.id == scope.station_id)
        return [{"id": s.id, "name": s.name, "active": s.active} for s in db.scalars(query)]

    @router.post("/api/v1/staff/stations")
    def add_station(body: StationInput, db: DB, scope: STAFF):
        admin(scope)
        station = Station(canteen_id=scope.canteen_id, name=body.name.strip(), active=body.active)
        db.add(station)
        db.flush()
        return {"id": station.id}

    @router.patch("/api/v1/staff/stations/{station_id}")
    def edit_station(station_id: UUID, body: StationInput, db: DB, scope: STAFF):
        admin(scope)
        station = db.get(Station, str(station_id))
        if not station or station.canteen_id != scope.canteen_id:
            raise DomainError("STATION_NOT_FOUND", 404)
        station.name, station.active = body.name.strip(), body.active
        return {"id": station.id}

    return router
