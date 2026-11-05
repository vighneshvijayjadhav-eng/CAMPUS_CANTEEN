from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.menu.models import identifier

REVIEW_STATES = ("VISIBLE", "HIDDEN", "REMOVED")
REPORT_REASONS = ("SPAM", "OFFENSIVE", "IRRELEVANT", "PRIVACY", "OTHER")


class Review(Base):
    """One review per collected order line, by the student who bought it. Published
    immediately; HIDDEN after enough validated reports until an admin restores or removes it."""

    __tablename__ = "reviews"
    __table_args__ = (
        ForeignKeyConstraint(
            ["canteen_id", "menu_item_id"], ["menu_items.canteen_id", "menu_items.id"]
        ),
        UniqueConstraint("order_line_id"),
        CheckConstraint("rating >= 1 AND rating <= 5"),
        CheckConstraint("status IN ('VISIBLE','HIDDEN','REMOVED')"),
        Index("ix_reviews_item", "menu_item_id", "status", "created_at"),
        Index("ix_reviews_moderation", "canteen_id", "status"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(String(36))
    menu_item_id: Mapped[str] = mapped_column(String(36))
    order_line_id: Mapped[str] = mapped_column(ForeignKey("order_lines.id"))
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), index=True)
    rating: Mapped[int]
    body: Mapped[str | None] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(10), default="VISIBLE")
    # Reports filed before this instant were resolved by a moderator and no longer count.
    reports_cleared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewPhoto(Base):
    __tablename__ = "review_photos"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), index=True)
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    width: Mapped[int]
    height: Mapped[int]
    size_bytes: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewReport(Base):
    """One report per student per review; only students who collected food at the same
    canteen may report (brigade protection)."""

    __tablename__ = "review_reports"
    __table_args__ = (
        CheckConstraint("reason IN ('SPAM','OFFENSIVE','IRRELEVANT','PRIVACY','OTHER')"),
    )
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), primary_key=True)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("students.id"), primary_key=True)
    reason: Mapped[str] = mapped_column(String(12))
    note: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ReviewModerationEvent(Base):
    __tablename__ = "review_moderation_events"
    __table_args__ = (
        CheckConstraint("action IN ('AUTO_HIDDEN','RESTORED','REMOVED')"),
        CheckConstraint("actor_kind IN ('system','staff')"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    review_id: Mapped[str] = mapped_column(ForeignKey("reviews.id"), index=True)
    action: Mapped[str] = mapped_column(String(12))
    actor_kind: Mapped[str] = mapped_column(String(8))
    actor_id: Mapped[str] = mapped_column(String(36))
    session_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
