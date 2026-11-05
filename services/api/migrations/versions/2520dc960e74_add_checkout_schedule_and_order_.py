"""add checkout schedule and order snapshots

Additive only: new canteen_hours table, nullable snapshot/idempotency columns and a
created_at column defaulted for existing rows.
"""

import sqlalchemy as sa
from alembic import op

revision = "2520dc960e74"
down_revision = "c4e95a58b9ea"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "canteen_hours",
        sa.Column("canteen_id", sa.String(length=36), nullable=False),
        sa.Column("weekday", sa.Integer(), nullable=False),
        sa.Column("opens_minute", sa.Integer(), nullable=False),
        sa.Column("closes_minute", sa.Integer(), nullable=False),
        sa.CheckConstraint("closes_minute <= 1440"),
        sa.CheckConstraint("opens_minute >= 0 AND opens_minute < closes_minute"),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6"),
        sa.ForeignKeyConstraint(["canteen_id"], ["canteens.id"]),
        sa.PrimaryKeyConstraint("canteen_id", "weekday"),
    )
    with op.batch_alter_table("order_lines") as batch_op:
        batch_op.add_column(sa.Column("variant_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_order_lines_variant",
            "menu_variants",
            ["canteen_id", "variant_id"],
            ["canteen_id", "id"],
        )
    with op.batch_alter_table("orders") as batch_op:
        batch_op.add_column(
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("checkout_request_id", sa.String(length=36), nullable=True))
        batch_op.create_index(
            "ix_orders_student_history", ["student_id", "created_at"], unique=False
        )
        batch_op.create_unique_constraint(
            "uq_orders_student_checkout", ["student_id", "checkout_request_id"]
        )


def downgrade():
    raise RuntimeError("Destructive downgrade requires an approved backup/restore plan.")
