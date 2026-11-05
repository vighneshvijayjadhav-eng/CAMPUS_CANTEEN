"""add refund retry schedule

Additive only: a nullable next_attempt_at column and an index for due retries.
"""

import sqlalchemy as sa
from alembic import op

revision = "9014a5236447"
down_revision = "189437663676"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("refunds") as batch_op:
        batch_op.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.create_index("ix_refunds_retry", ["status", "next_attempt_at"], unique=False)


def downgrade():
    raise RuntimeError("Destructive downgrade requires an approved backup/restore plan.")
