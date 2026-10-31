import hashlib
import secrets
from dataclasses import dataclass
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from sqlalchemy import select

from app.core.errors import DomainError
from app.modules.identity.models import (
    DeviceSession,
    RateBucket,
    StaffAccount,
    Student,
    StudentSession,
)
from app.modules.menu.models import Station
from app.modules.orders.service import StaffScope, instant, server_now

hasher = PasswordHasher()
DUMMY_HASH = hasher.hash(secrets.token_urlsafe(32))


@dataclass(frozen=True)
class StudentScope:
    actor_id: str
    session_id: str


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def throttle(engine, key, limit, seconds=60):
    """Own transaction so failed requests still count across workers and restarts."""
    from sqlalchemy.orm import Session

    key = digest(key)
    with Session(engine) as db, db.begin():
        if engine.dialect.name == "postgresql":
            from sqlalchemy import text

            db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": int(key[:15], 16)})
        bucket = db.get(RateBucket, key)
        now = server_now(db)
        if bucket is None:
            db.add(RateBucket(key=key, starts_at=now, attempts=1))
            blocked = False
        else:
            if instant(bucket.starts_at) + timedelta(seconds=seconds) <= now:
                bucket.starts_at, bucket.attempts = now, 0
            bucket.attempts += 1
            blocked = bucket.attempts > limit
    if blocked:
        raise DomainError("RATE_LIMITED", 429)


def password_matches(account, password):
    try:
        return hasher.verify(account.password_hash if account else DUMMY_HASH, password)
    except VerificationError:
        return False


def ensure_account(db, account):
    if not account or not account.active:
        raise DomainError("AUTHENTICATION_REQUIRED", 401)
    if account.role == "station":
        station = db.get(Station, account.station_id)
        if not station or not station.active or station.canteen_id != account.canteen_id:
            raise DomainError("AUTHENTICATION_REQUIRED", 401)


def rotate(db, session):
    now = server_now(db)
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    session.access_digest, session.refresh_digest = digest(access), digest(refresh)
    session.access_until = now + timedelta(minutes=15)
    session.refresh_until = min(now + timedelta(days=30), instant(session.absolute_until))
    db.flush()
    return access, refresh


def login(db, username, password, device_name):
    account = db.scalar(
        select(StaffAccount).where(StaffAccount.username == username.strip().lower())
    )
    if not password_matches(account, password):
        raise DomainError("INVALID_CREDENTIALS", 401)
    ensure_account(db, account)
    now = server_now(db)
    session = DeviceSession(
        staff_id=account.id,
        device_name=device_name,
        authenticated_at=now,
        absolute_until=now + timedelta(days=90),
    )
    # Set required token fields before the first flush.
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    session.access_digest, session.refresh_digest = digest(access), digest(refresh)
    session.access_until = now + timedelta(minutes=15)
    session.refresh_until = now + timedelta(days=30)
    db.add(session)
    db.flush()
    return session, access, refresh


def refresh_session(db, token):
    session = db.scalar(
        select(DeviceSession).where(DeviceSession.refresh_digest == digest(token)).with_for_update()
    )
    now = server_now(db)
    if (
        not session
        or session.revoked
        or instant(session.refresh_until) <= now
        or instant(session.absolute_until) <= now
    ):
        raise DomainError("AUTHENTICATION_REQUIRED", 401)
    ensure_account(db, db.get(StaffAccount, session.staff_id))
    return session, *rotate(db, session)


def authenticate(db, token):
    session = db.scalar(select(DeviceSession).where(DeviceSession.access_digest == digest(token)))
    now = server_now(db)
    if (
        not session
        or session.revoked
        or instant(session.access_until) <= now
        or instant(session.absolute_until) <= now
    ):
        raise DomainError("AUTHENTICATION_REQUIRED", 401)
    account = db.get(StaffAccount, session.staff_id)
    ensure_account(db, account)
    return StaffScope(account.id, session.id, account.canteen_id, account.station_id, account.role)


def verify_google_id_token(token, client_id):
    if not client_id:
        raise DomainError("GOOGLE_AUTH_NOT_CONFIGURED", 503)
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.id_token import verify_oauth2_token

        claims = verify_oauth2_token(token, Request(), client_id)
    except Exception as error:
        raise DomainError("INVALID_GOOGLE_TOKEN", 401) from error
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise DomainError("INVALID_GOOGLE_TOKEN", 401)
    if claims.get("email_verified") is not True:
        raise DomainError("GOOGLE_EMAIL_NOT_VERIFIED", 401)
    sub, email = claims.get("sub"), claims.get("email")
    if not isinstance(sub, str) or not sub or not isinstance(email, str) or "@" not in email:
        raise DomainError("INVALID_GOOGLE_TOKEN", 401)
    return {
        "sub": sub,
        "email": email.casefold(),
        "name": str(claims.get("name") or email),
        "picture": claims.get("picture") if isinstance(claims.get("picture"), str) else None,
    }


def issue_student_tokens(db, session):
    now = server_now(db)
    access, refresh = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    session.access_digest, session.refresh_digest = digest(access), digest(refresh)
    session.access_until = now + timedelta(minutes=15)
    session.refresh_until = min(now + timedelta(days=30), instant(session.absolute_until))
    db.flush()
    return access, refresh


def login_student(db, claims, device_name):
    student = db.scalar(select(Student).where(Student.google_sub == claims["sub"]))
    if student is None:
        email_owner = db.scalar(select(Student).where(Student.email == claims["email"]))
        if email_owner:
            raise DomainError("GOOGLE_ACCOUNT_CONFLICT")
        student = Student(
            google_sub=claims["sub"],
            email=claims["email"],
            display_name=claims["name"],
            avatar_url=claims["picture"],
        )
        db.add(student)
        db.flush()
    else:
        email_owner = db.scalar(select(Student).where(Student.email == claims["email"]))
        if email_owner and email_owner.id != student.id:
            raise DomainError("GOOGLE_ACCOUNT_CONFLICT")
        student.email, student.display_name, student.avatar_url = (
            claims["email"],
            claims["name"],
            claims["picture"],
        )
    now = server_now(db)
    session = StudentSession(
        student_id=student.id,
        device_name=device_name,
        authenticated_at=now,
        absolute_until=now + timedelta(days=90),
        access_digest=digest(secrets.token_urlsafe(32)),
        refresh_digest=digest(secrets.token_urlsafe(48)),
        access_until=now,
        refresh_until=now,
    )
    db.add(session)
    db.flush()
    access, refresh = issue_student_tokens(db, session)
    return student, session, access, refresh


def refresh_student_session(db, token):
    session = db.scalar(
        select(StudentSession)
        .where(StudentSession.refresh_digest == digest(token))
        .with_for_update()
    )
    now = server_now(db)
    if (
        not session
        or session.revoked
        or instant(session.refresh_until) <= now
        or instant(session.absolute_until) <= now
    ):
        raise DomainError("AUTHENTICATION_REQUIRED", 401)
    return session, *issue_student_tokens(db, session)


def authenticate_student(db, token):
    session = db.scalar(select(StudentSession).where(StudentSession.access_digest == digest(token)))
    now = server_now(db)
    if (
        not session
        or session.revoked
        or instant(session.access_until) <= now
        or instant(session.absolute_until) <= now
    ):
        raise DomainError("AUTHENTICATION_REQUIRED", 401)
    return StudentScope(session.student_id, session.id)
