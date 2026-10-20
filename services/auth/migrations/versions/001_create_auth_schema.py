"""Create auth schema, users, and refresh_tokens tables.

Revision ID: 001_auth_init
Revises: None
Create Date: 2026-10-20
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "001_auth_init"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Ensure schema exists
    op.execute("CREATE SCHEMA IF NOT EXISTS auth;")

    # Create users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), server_default="user", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        schema="auth",
    )
    op.create_index("ix_auth_users_email", "users", ["email"], unique=True, schema="auth")

    # Create refresh_tokens table
    op.create_table(
        "refresh_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        schema="auth",
    )
    op.create_index(
        "ix_auth_refresh_tokens_token_hash",
        "refresh_tokens",
        ["token_hash"],
        unique=True,
        schema="auth",
    )
    op.create_index("ix_auth_refresh_tokens_user_id", "refresh_tokens", ["user_id"], schema="auth")


def downgrade() -> None:
    op.drop_index("ix_auth_refresh_tokens_user_id", table_name="refresh_tokens", schema="auth")
    op.drop_index("ix_auth_refresh_tokens_token_hash", table_name="refresh_tokens", schema="auth")
    op.drop_table("refresh_tokens", schema="auth")
    op.drop_index("ix_auth_users_email", table_name="users", schema="auth")
    op.drop_table("users", schema="auth")
    op.execute("DROP SCHEMA IF EXISTS auth CASCADE;")
