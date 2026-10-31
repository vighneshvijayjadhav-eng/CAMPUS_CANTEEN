from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, ForeignKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.menu.models import identifier


class StaffAccount(Base):
    __tablename__ = "staff_accounts"
    __table_args__ = (
        ForeignKeyConstraint(
            ["canteen_id", "station_id"], ["canteen_stations.canteen_id", "canteen_stations.id"]
        ),
        CheckConstraint(
            "(role = 'admin' AND station_id IS NULL) OR "
            "(role = 'station' AND station_id IS NOT NULL)"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    username: Mapped[str] = mapped_column(String(160), unique=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"))
    station_id: Mapped[str | None] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Student(Base):
    __tablename__ = "students"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    google_sub: Mapped[str] = mapped_column(String(255), unique=True)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    display_name: Mapped[str] = mapped_column(String(160))
    avatar_url: Mapped[str | None] = mapped_column(String(2000))


class StudentSession(Base):
    __tablename__ = "student_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    device_name: Mapped[str] = mapped_column(String(120))
    access_digest: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_digest: Mapped[str] = mapped_column(String(64), unique=True)
    access_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class StudentPreference(Base):
    __tablename__ = "student_preferences"
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    selected_institute_id: Mapped[str | None] = mapped_column(ForeignKey("institutes.id"))


class DeviceSession(Base):
    __tablename__ = "device_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    staff_id: Mapped[str] = mapped_column(ForeignKey("staff_accounts.id"), index=True)
    device_name: Mapped[str] = mapped_column(String(120))
    access_digest: Mapped[str] = mapped_column(String(64), unique=True)
    refresh_digest: Mapped[str] = mapped_column(String(64), unique=True)
    access_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    refresh_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    absolute_until: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    authenticated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)


class RateBucket(Base):
    __tablename__ = "rate_buckets"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int]


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    actor_id: Mapped[str] = mapped_column(ForeignKey("staff_accounts.id"))
    session_id: Mapped[str] = mapped_column(ForeignKey("device_sessions.id"))
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    action: Mapped[str] = mapped_column(String(256))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
