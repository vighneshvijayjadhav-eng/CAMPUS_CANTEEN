"""add razorpay merchants and payment attempts

Additive only: three new tables. Gateway secrets are not stored in the database.
"""

import sqlalchemy as sa
from alembic import op

revision = "a824997c8e58"
down_revision = "2520dc960e74"
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "merchant_accounts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canteen_id", sa.String(length=36), nullable=False),
        sa.Column("provider", sa.String(length=20), nullable=False),
        sa.Column("key_id", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("mode IN ('test','live')"),
        sa.CheckConstraint("provider IN ('razorpay')"),
        sa.ForeignKeyConstraint(
            ["canteen_id"],
            ["canteens.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canteen_id", "id"),
        sa.UniqueConstraint("provider", "key_id"),
    )
    op.create_index(
        op.f("ix_merchant_accounts_canteen_id"), "merchant_accounts", ["canteen_id"], unique=False
    )
    op.create_index(
        "uq_active_merchant",
        "merchant_accounts",
        ["canteen_id"],
        unique=True,
        postgresql_where=sa.text("active"),
        sqlite_where=sa.text("active = 1"),
    )
    op.create_table(
        "payment_attempts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canteen_id", sa.String(length=36), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=False),
        sa.Column("merchant_account_id", sa.String(length=36), nullable=False),
        sa.Column("provider_order_id", sa.String(length=80), nullable=False),
        sa.Column("provider_payment_id", sa.String(length=80), nullable=True),
        sa.Column("amount_paise", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_reason", sa.String(length=160), nullable=True),
        sa.CheckConstraint(
            "status IN ('CREATED','CAPTURED','FAILED','AMOUNT_MISMATCH','CAPTURED_UNAPPLIED')"
        ),
        sa.CheckConstraint("amount_paise > 0"),
        sa.ForeignKeyConstraint(
            ["canteen_id", "merchant_account_id"],
            ["merchant_accounts.canteen_id", "merchant_accounts.id"],
        ),
        sa.ForeignKeyConstraint(
            ["canteen_id", "order_id"],
            ["orders.canteen_id", "orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("merchant_account_id", "provider_order_id"),
        sa.UniqueConstraint("merchant_account_id", "provider_payment_id"),
    )
    op.create_index(
        "ix_payment_attempts_order", "payment_attempts", ["order_id", "status"], unique=False
    )
    op.create_index(
        "ix_payment_attempts_status", "payment_attempts", ["status", "created_at"], unique=False
    )
    op.create_table(
        "payment_webhook_events",
        sa.Column("merchant_account_id", sa.String(length=36), nullable=False),
        sa.Column("provider_event_id", sa.String(length=120), nullable=False),
        sa.Column("event_type", sa.String(length=80), nullable=False),
        sa.Column("body_sha256", sa.String(length=64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["merchant_account_id"],
            ["merchant_accounts.id"],
        ),
        sa.PrimaryKeyConstraint("merchant_account_id", "provider_event_id"),
    )


def downgrade():
    raise RuntimeError("Destructive downgrade requires an approved backup/restore plan.")
