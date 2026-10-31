from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session

from app.core.db import Base
from app.core.errors import DomainError
from app.modules.identity.models import Student
from app.modules.identity.service import (
    authenticate_student,
    login_student,
    refresh_student_session,
)


@pytest.fixture
def db(monkeypatch):
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda c, _: c.execute("PRAGMA foreign_keys=ON"))
    Base.metadata.create_all(engine)
    import app.modules.identity.service as service

    now = datetime(2026, 10, 31, 12, tzinfo=UTC)
    monkeypatch.setattr(service, "server_now", lambda _: now)
    with Session(engine, expire_on_commit=False) as db:
        yield db, now


def claims(email="student@example.test"):
    return {"sub": "google-subject", "email": email, "name": "Student", "picture": None}


def test_google_identity_creates_student_and_rotates_student_session(db):
    session, now = db
    student, device, access, refresh = login_student(session, claims(), "Android phone")
    assert authenticate_student(session, access).actor_id == student.id
    old_refresh = refresh
    refreshed, next_access, next_refresh = refresh_student_session(session, refresh)
    assert refreshed.id == device.id
    assert next_refresh != old_refresh
    with pytest.raises(DomainError, match="AUTHENTICATION_REQUIRED"):
        refresh_student_session(session, old_refresh)
    assert authenticate_student(session, next_access).session_id == device.id


def test_same_google_subject_updates_profile_but_email_collision_fails(db):
    session, _ = db
    student, *_ = login_student(session, claims(), "Phone")
    updated = {**claims("updated@example.test"), "name": "Updated"}
    same, *_ = login_student(session, updated, "Tablet")
    assert same.id == student.id and same.display_name == "Updated"
    session.add(
        Student(google_sub="other-subject", email="taken@example.test", display_name="Other")
    )
    session.flush()
    with pytest.raises(DomainError, match="GOOGLE_ACCOUNT_CONFLICT"):
        login_student(
            session, {**claims("taken@example.test"), "sub": "new-subject"}, "Other phone"
        )
    with pytest.raises(DomainError, match="GOOGLE_ACCOUNT_CONFLICT"):
        login_student(
            session,
            {**claims("taken@example.test"), "name": "Changed"},
            "Same phone",
        )


def test_student_session_expiry_and_revocation(db):
    session, now = db
    _, device, access, _ = login_student(session, claims(), "Phone")
    device.access_until = now - timedelta(seconds=1)
    session.flush()
    with pytest.raises(DomainError, match="AUTHENTICATION_REQUIRED"):
        authenticate_student(session, access)
    device.access_until = now + timedelta(minutes=1)
    device.revoked = True
    session.flush()
    with pytest.raises(DomainError, match="AUTHENTICATION_REQUIRED"):
        authenticate_student(session, access)
