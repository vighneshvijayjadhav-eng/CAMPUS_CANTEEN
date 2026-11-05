from datetime import date
from typing import Literal

from fastapi import APIRouter

from app.core.http import DB, STAFF, admin
from app.modules.reports.service import sales_report


def create_router(settings, engine):
    router = APIRouter()

    @router.get("/api/v1/staff/reports/sales")
    def sales(
        start: date,
        end: date,
        db: DB,
        scope: STAFF,
        group: Literal["day", "week", "month"] = "day",
    ):
        admin(scope)
        return sales_report(db, scope.canteen_id, start, end, group)

    return router
