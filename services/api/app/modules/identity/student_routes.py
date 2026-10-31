from uuid import UUID

from fastapi import APIRouter, Request
from pydantic import Field
from sqlalchemy import select

from app.core.errors import DomainError
from app.core.http import DB, STUDENT, Input
from app.modules.identity.models import Student, StudentPreference, StudentSession
from app.modules.identity.service import login_student, refresh_student_session, throttle
from app.modules.menu.models import Institute


class GoogleLoginInput(Input):
    id_token: str = Field(min_length=20, max_length=12000)
    device_name: str = Field(min_length=1, max_length=120)


class StudentRefreshInput(Input):
    refresh_token: str = Field(min_length=20, max_length=1024)


class InstitutePreferenceInput(Input):
    institute_id: UUID


class SessionRevokeInput(Input):
    session_id: UUID


def tokens(session, access, refresh):
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "Bearer",
        "access_expires_in": 900,
        "session_id": session.id,
    }


def create_router(settings, engine):
    router = APIRouter()

    @router.post("/api/v1/auth/google")
    def google_login(body: GoogleLoginInput, request: Request, db: DB):
        throttle(engine, f"google-login-ip:{request.client.host}", 20)
        claims = request.app.state.google_verifier(body.id_token)
        student, session, access, refresh = login_student(db, claims, body.device_name)
        return {"student": student.id, **tokens(session, access, refresh)}

    @router.post("/api/v1/auth/student/refresh")
    def refresh_student(body: StudentRefreshInput, request: Request, db: DB):
        throttle(engine, f"student-refresh-ip:{request.client.host}", 60)
        session, access, refresh = refresh_student_session(db, body.refresh_token)
        return tokens(session, access, refresh)

    @router.get("/api/v1/student/me")
    def me(db: DB, scope: STUDENT):
        student = db.get(Student, scope.actor_id)
        preference = db.get(StudentPreference, student.id)
        return {
            "id": student.id,
            "email": student.email,
            "display_name": student.display_name,
            "avatar_url": student.avatar_url,
            "selected_institute_id": preference.selected_institute_id if preference else None,
        }

    @router.patch("/api/v1/student/preferences/institute")
    def select_institute(body: InstitutePreferenceInput, db: DB, scope: STUDENT):
        institute = db.get(Institute, str(body.institute_id))
        if not institute or not institute.approved:
            raise DomainError("INSTITUTE_NOT_FOUND", 404)
        preference = db.get(StudentPreference, scope.actor_id)
        if preference is None:
            preference = StudentPreference(student_id=scope.actor_id)
            db.add(preference)
        preference.selected_institute_id = institute.id
        return {"selected_institute_id": institute.id}

    @router.get("/api/v1/student/sessions")
    def sessions(db: DB, scope: STUDENT):
        rows = db.scalars(select(StudentSession).where(StudentSession.student_id == scope.actor_id))
        return [
            {
                "id": row.id,
                "device": row.device_name,
                "revoked": row.revoked,
                "expires_at": row.absolute_until,
            }
            for row in rows
        ]

    @router.post("/api/v1/student/sessions/revoke")
    def revoke_session(body: SessionRevokeInput, db: DB, scope: STUDENT):
        session = db.get(StudentSession, str(body.session_id))
        if not session or session.student_id != scope.actor_id:
            raise DomainError("SESSION_NOT_FOUND", 404)
        session.revoked = True
        return {"revoked": True}

    return router
