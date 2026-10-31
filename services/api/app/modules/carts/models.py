from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.modules.menu.models import identifier


class Cart(Base):
    __tablename__ = "carts"
    __table_args__ = (UniqueConstraint("canteen_id", "id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.id"), unique=True)
    canteen_id: Mapped[str] = mapped_column(ForeignKey("canteens.id"))


class CartLine(Base):
    __tablename__ = "cart_lines"
    __table_args__ = (
        ForeignKeyConstraint(["canteen_id", "cart_id"], ["carts.canteen_id", "carts.id"]),
        ForeignKeyConstraint(
            ["canteen_id", "variant_id"],
            ["menu_variants.canteen_id", "menu_variants.id"],
        ),
        UniqueConstraint("cart_id", "variant_id"),
        CheckConstraint("quantity > 0 AND quantity <= 99"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=identifier)
    cart_id: Mapped[str] = mapped_column(String(36))
    canteen_id: Mapped[str] = mapped_column(String(36))
    variant_id: Mapped[str] = mapped_column(String(36))
    quantity: Mapped[int]
