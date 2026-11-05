"""add refunds

Additive only: one new table for gateway refunds.
"""

import sqlalchemy as sa
from alembic import op

revision = "f162cf38ee04"
down_revision = "a824997c8e58"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refunds",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canteen_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("payment_attempt_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_account_id", sa.String(length=36), nullable=False),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=24), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("provider_refund_id", sa.String(length=80), nullable=True),
        sa.Column("requested_by_kind", sa.String(length=8), nullable=False),
        sa.Column("requested_by", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("submit_attempts", sa.Integer(), nullable=False),
        sa.Column("last_error", sa.String(length=160), nullable=True),
        sa.CheckConstraint(
            "reason IN ('STUDENT_CANCELLED','STAFF_CANCELLED','DUPLICATE_PAYMENT',"
            "'AMOUNT_MISMATCH')"
        ),
        sa.CheckConstraint("requested_by_kind IN ('student','staff','system')"),
        sa.CheckConstraint("status IN ('REQUESTED','PENDING','PROCESSED','FAILED')"),
        sa.CheckConstraint("amount_paise > 0"),
        sa.ForeignKeyConstraint(
            ["canteen_id", "merchant_account_id"],
            ["merchant_accounts.canteen_id", "merchant_accounts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["canteen_id", "order_id"],
            ["orders.canteen_id", "orders.id"],
        ),
        sa.ForeignKeyConstraint(
            ["payment_attempt_id"],
            ["payment_attempts.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_account_id", "provider_refund_id"),
    )
    op.create_index(
        "ix_refunds_canteen_status", "refunds", ["canteen_id", "status", "created_at"], unique=False
    )
    op.create_index(
        "uq_open_refund_per_attempt",
        "refunds",
        ["payment_attempt_id"],
        unique=True,
        postgresql_where=sa.text("status <> 'FAILED'"),
        sqlite_where=sa.text("status <> 'FAILED'"),
    )


def downgrade():
    raise RuntimeError("Destructive downgrade requires an approved backup/restore plan.")
