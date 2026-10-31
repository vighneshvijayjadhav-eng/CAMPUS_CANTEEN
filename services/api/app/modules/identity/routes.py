from uuid import UUID

from fastapi import APIRouter, Request, Response
from pydantic import Field
from sqlalchemy import select

from app.core.errors import DomainError
from app.core.http import DB, STAFF, Input
from app.modules.identity.models import DeviceSession
from app.modules.identity.service import login, refresh_session, throttle
from app.modules.menu.models import Canteen


class LoginInput(Input):
    username: str = Field(min_length=1, max_length=160)
    password: str = Field(min_length=1, max_length=1024)
    device_name: str = Field(min_length=1, max_length=120)


def create_router(settings, engine):
    router = APIRouter()

    def cookies(response, access, refresh):
        options = dict(httponly=True, secure=settings.environment != "local", samesite="strict")
        response.set_cookie("canteen_access", access, max_age=900, path="/api/v1", **options)
        response.set_cookie(
            "canteen_refresh", refresh, max_age=30 * 86400, path="/api/v1/auth", **options
        )

    @router.post("/api/v1/auth/staff/login")
    def sign_in(body: LoginInput, request: Request, response: Response, db: DB):
        throttle(engine, f"login-ip:{request.client.host}", 30)
        throttle(engine, f"login-user:{body.username.strip().lower()}", 10, 300)
        session, access, refresh = login(db, body.username, body.password, body.device_name)
        cookies(response, access, refresh)
        return {"session_id": session.id}

    @router.post("/api/v1/auth/refresh")
    def refresh(request: Request, response: Response, db: DB):
        throttle(engine, f"refresh:{request.client.host}", 60)
        session, access, token = refresh_session(db, request.cookies.get("canteen_refresh", ""))
        cookies(response, access, token)
        return {"session_id": session.id}

    @router.post("/api/v1/auth/logout")
    def logout(response: Response, db: DB, scope: STAFF):
        db.get(DeviceSession, scope.session_id).revoked = True
        response.delete_cookie("canteen_access", path="/api/v1")
        response.delete_cookie("canteen_refresh", path="/api/v1/auth")
        return {"signed_out": True}

    @router.get("/api/v1/staff/me")
    def me(db: DB, scope: STAFF):
        return {
            "role": scope.role,
            "station_id": scope.station_id,
            "canteen_id": scope.canteen_id,
            "session_id": scope.session_id,
            "canteen": db.get(Canteen, scope.canteen_id).name,
        }

    @router.get("/api/v1/staff/sessions")
    def sessions(db: DB, scope: STAFF):
        rows = db.scalars(select(DeviceSession).where(DeviceSession.staff_id == scope.actor_id))
        return [
            {
                "id": row.id,
                "device": row.device_name,
                "revoked": row.revoked,
                "expires_at": row.absolute_until,
            }
            for row in rows
        ]

    @router.post("/api/v1/staff/sessions/{session_id}/revoke")
    def revoke(session_id: UUID, db: DB, scope: STAFF):
        session = db.get(DeviceSession, str(session_id))
        if not session or session.staff_id != scope.actor_id:
            raise DomainError("SESSION_NOT_FOUND", 404)
        session.revoked = True
        return {"revoked": True}

    return router
