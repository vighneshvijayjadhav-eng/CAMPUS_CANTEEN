"""add reviews, photos, reports and moderation events

Additive only: four new tables. Photo files live in MEDIA_DIR, not the database.
"""

import sqlalchemy as sa
from alembic import op

revision = "9e348ecd3027"
down_revision = "f162cf38ee04"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reviews",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("canteen_id", sa.String(length=36), nullable=False),
        sa.Column("menu_item_id", sa.String(length=36), nullable=False),
        sa.Column("order_line_id", sa.String(length=36), nullable=False),
        sa.Column("student_id", sa.String(length=36), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("body", sa.String(length=1000), nullable=True),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("reports_cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('VISIBLE','HIDDEN','REMOVED')"),
        sa.CheckConstraint("rating >= 1 AND rating <= 5"),
        sa.ForeignKeyConstraint(
            ["canteen_id", "menu_item_id"],
            ["menu_items.canteen_id", "menu_items.id"],
        ),
        sa.ForeignKeyConstraint(
            ["order_line_id"],
            ["order_lines.id"],
        ),
        sa.ForeignKeyConstraint(
            ["student_id"],
            ["students.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_line_id"),
    )
    op.create_index(
        "ix_reviews_item", "reviews", ["menu_item_id", "status", "created_at"], unique=False
    )
    op.create_index("ix_reviews_moderation", "reviews", ["canteen_id", "status"], unique=False)
    op.create_index(op.f("ix_reviews_student_id"), "reviews", ["student_id"], unique=False)
    op.create_table(
        "review_moderation_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("action", sa.String(length=12), nullable=False),
        sa.Column("actor_kind", sa.String(length=8), nullable=False),
        sa.Column("actor_id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("action IN ('AUTO_HIDDEN','RESTORED','REMOVED')"),
        sa.CheckConstraint("actor_kind IN ('system','staff')"),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_review_moderation_events_review_id"),
        "review_moderation_events",
        ["review_id"],
        unique=False,
    )
    op.create_table(
        "review_photos",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("storage_key", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(
        op.f("ix_review_photos_review_id"), "review_photos", ["review_id"], unique=False
    )
    op.create_table(
        "review_reports",
        sa.Column("review_id", sa.String(length=36), nullable=False),
        sa.Column("reporter_id", sa.String(length=36), nullable=False),
        sa.Column("reason", sa.String(length=12), nullable=False),
        sa.Column("note", sa.String(length=300), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("reason IN ('SPAM','OFFENSIVE','IRRELEVANT','PRIVACY','OTHER')"),
        sa.ForeignKeyConstraint(
            ["reporter_id"],
            ["students.id"],
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
        ),
        sa.PrimaryKeyConstraint("review_id", "reporter_id"),
    )


def downgrade():
    raise RuntimeError("Destructive downgrade requires an approved backup/restore plan.")
