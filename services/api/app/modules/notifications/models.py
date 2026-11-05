from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class StudentNotification(Base):
    """In-app inbox entry (no OS push by decision). Written in the same transaction as the
    order/payment/refund change it describes, so it can never announce something that rolled
    back."""

    __tablename__ = "student_notifications"
    __table_args__ = (Index("ix_student_notifications_inbox", "student_id", "id"),)
    # Increasing id = true insertion order, even for events written in one transaction.
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(String(128))
    order_id: Mapped[str | None] = mapped_column(ForeignKey("orders.id"))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
