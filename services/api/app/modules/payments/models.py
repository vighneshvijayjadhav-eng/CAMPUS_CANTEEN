from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.menu.models import identifier


class MerchantAccount(Base):
    """Non-secret gateway metadata. Secrets live only in server configuration.

    Rows are never repointed: a new account is a new row, so earlier payments and refunds keep
    the account they were made with.
    """

    __tablename__ = "merchant_accounts"
    __table_args__ = (
        UniqueConstraint("canteen_id", "id"),
        UniqueConstraint("provider", "key_id"),
        CheckConstraint("provider IN ('razorpay')"),
        CheckConstraint("mode IN ('test','live')"),
        Index(
            "uq_active_merchant",
            "canteen_id",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active = 1"),
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    provider: Mapped[str] = mapped_column(String(20))
    key_id: Mapped[str] = mapped_column(String(80))
    mode: Mapped[str] = mapped_column(String(8))
    display_name: Mapped[str] = mapped_column(String(160))
    active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


PAYMENT_STATES = ("CREATED", "CAPTURED", "FAILED", "AMOUNT_MISMATCH", "CAPTURED_UNAPPLIED")


class PaymentAttempt(Base):
    """One gateway order per attempt. CAPTURED_UNAPPLIED marks money received for an order that
    could not be activated (already paid by another attempt); it must be refunded."""

    __tablename__ = "payment_attempts"
    __table_args__ = (
        ForeignKeyConstraint(["canteen_id", "order_id"], ["orders.canteen_id", "orders.id"]),
        ForeignKeyConstraint(
            ["canteen_id", "merchant_account_id"],
            ["merchant_accounts.canteen_id", "merchant_accounts.id"],
        ),
        UniqueConstraint("merchant_account_id", "provider_order_id"),
        UniqueConstraint("merchant_account_id", "provider_payment_id"),
        CheckConstraint("amount_paise > 0"),
        CheckConstraint(
            "status IN ('CREATED','CAPTURED','FAILED','AMOUNT_MISMATCH','CAPTURED_UNAPPLIED')"
        ),
        Index("ix_payment_attempts_order", "order_id", "status"),
        Index("ix_payment_attempts_status", "status", "created_at"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(String(36))
    order_id: Mapped[str] = mapped_column(String(36))
    merchant_account_id: Mapped[str] = mapped_column(String(36))
    provider_order_id: Mapped[str] = mapped_column(String(80))
    provider_payment_id: Mapped[str | None] = mapped_column(String(80))
    amount_paise: Mapped[int]
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(24), default="CREATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    captured_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(String(160))


class PaymentWebhookEvent(Base):
    """Replay guard: each verified provider event is processed at most once."""

    __tablename__ = "payment_webhook_events"
    merchant_account_id: Mapped[str] = mapped_column(
        ForeignKey("merchant_accounts.id"), primary_key=True
    )
    provider_event_id: Mapped[str] = mapped_column(String(120), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(80))
    body_sha256: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
