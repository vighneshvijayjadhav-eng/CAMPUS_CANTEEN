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
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.menu.models import identifier


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        UniqueConstraint("canteen_id", "id"),
        CheckConstraint("total_paise > 0"),
        CheckConstraint(
            "state IN ('PAYMENT_PENDING','PAID_ACTIVE','PARTIALLY_COLLECTED',"
            "'COLLECTED','CANCELLED')"
        ),
        Index("ix_orders_queue", "canteen_id", "state"),
        Index("ix_orders_student_history", "student_id", "created_at"),
        UniqueConstraint("student_id", "checkout_request_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"))
    student_id: Mapped[str] = mapped_column(String(128), index=True)
    state: Mapped[str] = mapped_column(String(32), default="PAYMENT_PENDING")
    total_paise: Mapped[int]
    payment_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    refund_status: Mapped[str | None] = mapped_column(String(40))
    exception_status: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    checkout_request_id: Mapped[str | None] = mapped_column(String(36))


class OrderLine(Base):
    __tablename__ = "order_lines"
    __table_args__ = (
        ForeignKeyConstraint(["canteen_id", "order_id"], ["orders.canteen_id", "orders.id"]),
        ForeignKeyConstraint(
            ["canteen_id", "station_id"], ["canteen_stations.canteen_id", "canteen_stations.id"]
        ),
        ForeignKeyConstraint(
            ["canteen_id", "variant_id"], ["menu_variants.canteen_id", "menu_variants.id"]
        ),
        CheckConstraint("quantity > 0 AND fulfilled >= 0 AND fulfilled <= quantity"),
        CheckConstraint("unit_price_paise > 0"),
        Index("ix_order_lines_station", "canteen_id", "station_id", "order_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    canteen_id: Mapped[str] = mapped_column(String(36))
    order_id: Mapped[str] = mapped_column(String(36))
    station_id: Mapped[str] = mapped_column(String(36))
    station_name: Mapped[str] = mapped_column(String(80))
    variant_id: Mapped[str | None] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(160))
    variant_label: Mapped[str] = mapped_column(String(80))
    unit_price_paise: Mapped[int]
    quantity: Mapped[int]
    fulfilled: Mapped[int] = mapped_column(default=0)


class PickupCredential(Base):
    __tablename__ = "pickup_credentials"
    __table_args__ = (
        ForeignKeyConstraint(["canteen_id", "order_id"], ["orders.canteen_id", "orders.id"]),
        Index(
            "uq_active_pickup",
            "canteen_id",
            "digest",
            unique=True,
            postgresql_where=text("active"),
            sqlite_where=text("active = 1"),
        ),
    )
    order_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    canteen_id: Mapped[str] = mapped_column(String(36))
    digest: Mapped[str] = mapped_column(String(64))
    encrypted_code: Mapped[str | None] = mapped_column(String(256))
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class FulfillmentEvent(Base):
    __tablename__ = "fulfillment_events"
    __table_args__ = (UniqueConstraint("order_id", "request_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    line_id: Mapped[str] = mapped_column(ForeignKey("order_lines.id"))
    request_id: Mapped[str] = mapped_column(String(36))
    actor_id: Mapped[str] = mapped_column(String(36))
    session_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int]
    expected_fulfilled: Mapped[int]
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OrderException(Base):
    __tablename__ = "order_exceptions"
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), primary_key=True)
    requested_by: Mapped[str] = mapped_column(String(128))
    reason: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    contact_note: Mapped[str | None] = mapped_column(String(2000))
    reviewed_by: Mapped[str | None] = mapped_column(String(36))
    reviewed_session: Mapped[str | None] = mapped_column(String(36))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class QueueEvent(Base):
    __tablename__ = "queue_events"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"), index=True)
    station_id: Mapped[str] = mapped_column(ForeignKey("canteen_stations.id"))
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"))
    kind: Mapped[str] = mapped_column(String(40))
