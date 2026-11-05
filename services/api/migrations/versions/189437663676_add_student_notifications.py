"""add student notifications

Additive only: one new table for the in-app inbox.
"""

import sqlalchemy as sa
from alembic import op

revision = "189437663676"
down_revision = "9e348ecd3027"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "student_notifications",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("student_id", sa.String(length=128), nullable=False),
        sa.Column("order_id", sa.String(length=36), nullable=True),
        sa.Column("kind", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("body", sa.String(length=300), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_student_notifications_inbox",
        "student_notifications",
        ["student_id", "id"],
        unique=False,
    )


def downgrade():
    raise RuntimeError("Destructive downgrade requires an approved backup/restore plan.")
