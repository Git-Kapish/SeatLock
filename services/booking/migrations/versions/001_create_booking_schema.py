"""Create booking schema and tables: seats, holds, bookings, payments, idempotency.

Revision ID: 001_booking_init
Revises: None
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_booking_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure booking schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS booking;")

    # 1. Seats table
    op.create_table(
        "seats",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=False),
        sa.Column("row", sa.String(length=10), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="available", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint(
            "event_id", "section", "row", "number", name="uq_seats_event_section_row_number"
        ),
        schema="booking",
    )
    op.create_index("ix_seats_event_id", "seats", ["event_id"], schema="booking")
    op.create_index("ix_seats_event_status", "seats", ["event_id", "status"], schema="booking")

    # 2. Holds table
    op.create_table(
        "holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="booking",
    )
    op.create_index("ix_holds_user_status", "holds", ["user_id", "status"], schema="booking")
    op.create_index("ix_holds_expires_status", "holds", ["expires_at", "status"], schema="booking")

    # 3. Hold seats junction table
    op.create_table(
        "hold_seats",
        sa.Column(
            "hold_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.holds.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "seat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.seats.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        schema="booking",
    )

    # 4. Bookings table
    op.create_table(
        "bookings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "hold_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.holds.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(length=32), server_default="pending_payment", nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="booking",
    )
    op.create_index("ix_bookings_user_id", "bookings", ["user_id"], schema="booking")
    op.create_index("ix_bookings_event_id", "bookings", ["event_id"], schema="booking")

    # 5. Booking seats junction table with partial unique index
    op.create_table(
        "booking_seats",
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.bookings.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "seat_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.seats.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("status", sa.String(length=32), server_default="pending_payment", nullable=False),
        schema="booking",
    )
    op.create_index(
        "ix_booking_seats_active",
        "booking_seats",
        ["seat_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending_payment', 'confirmed')"),
        schema="booking",
    )

    # 6. Payments table
    op.create_table(
        "payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "booking_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("booking.bookings.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("provider_ref", sa.String(length=255), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="initiated", nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="booking",
    )
    op.create_index("ix_payments_booking_id", "payments", ["booking_id"], schema="booking")

    # 7. Idempotency keys table
    op.create_table(
        "idempotency_keys",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_body", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="booking",
    )

    # 8. Processed webhooks table
    op.create_table(
        "processed_webhooks",
        sa.Column("provider_event_id", sa.String(length=255), primary_key=True),
        sa.Column(
            "processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="booking",
    )


def downgrade() -> None:
    op.drop_table("processed_webhooks", schema="booking")
    op.drop_table("idempotency_keys", schema="booking")
    op.drop_index("ix_payments_booking_id", table_name="payments", schema="booking")
    op.drop_table("payments", schema="booking")
    op.drop_index("ix_booking_seats_active", table_name="booking_seats", schema="booking")
    op.drop_table("booking_seats", schema="booking")
    op.drop_index("ix_bookings_event_id", table_name="bookings", schema="booking")
    op.drop_index("ix_bookings_user_id", table_name="bookings", schema="booking")
    op.drop_table("bookings", schema="booking")
    op.drop_table("hold_seats", schema="booking")
    op.drop_index("ix_holds_expires_status", table_name="holds", schema="booking")
    op.drop_index("ix_holds_user_status", table_name="holds", schema="booking")
    op.drop_table("holds", schema="booking")
    op.drop_index("ix_seats_event_status", table_name="seats", schema="booking")
    op.drop_index("ix_seats_event_id", table_name="seats", schema="booking")
    op.drop_table("seats", schema="booking")
    op.execute("DROP SCHEMA IF EXISTS booking CASCADE;")
