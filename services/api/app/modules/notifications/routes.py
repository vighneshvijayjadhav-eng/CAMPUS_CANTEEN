from fastapi import APIRouter

from app.core.http import DB, STUDENT
from app.modules.notifications.service import inbox, mark_all_read
from app.modules.orders.service import server_now


def create_router(settings, engine):
    router = APIRouter()

    @router.get("/api/v1/student/notifications")
    def notifications(db: DB, scope: STUDENT):
        return inbox(db, scope.actor_id)

    @router.post("/api/v1/student/notifications/read")
    def read_all(db: DB, scope: STUDENT):
        mark_all_read(db, scope.actor_id, server_now(db))
        return inbox(db, scope.actor_id)

    return router
