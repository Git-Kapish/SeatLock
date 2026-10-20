"""Create events schema and events table.

Revision ID: 001_events_init
Revises: None
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_events_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS events;")

    # Create events table
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("venue", sa.String(length=255), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="events",
    )
    op.create_index("ix_events_events_city", "events", ["city"], schema="events")
    op.create_index("ix_events_events_category", "events", ["category"], schema="events")
    op.create_index("ix_events_events_starts_at", "events", ["starts_at"], schema="events")
    op.create_index("ix_events_events_status", "events", ["status"], schema="events")
    op.create_index("ix_events_events_deleted_at", "events", ["deleted_at"], schema="events")
    op.create_index(
        "ix_events_city_category_starts_at",
        "events",
        ["city", "category", "starts_at"],
        schema="events",
    )


def downgrade() -> None:
    op.drop_index("ix_events_city_category_starts_at", table_name="events", schema="events")
    op.drop_index("ix_events_events_deleted_at", table_name="events", schema="events")
    op.drop_index("ix_events_events_status", table_name="events", schema="events")
    op.drop_index("ix_events_events_starts_at", table_name="events", schema="events")
    op.drop_index("ix_events_events_category", table_name="events", schema="events")
    op.drop_index("ix_events_events_city", table_name="events", schema="events")
    op.drop_table("events", schema="events")
    op.execute("DROP SCHEMA IF EXISTS events CASCADE;")
