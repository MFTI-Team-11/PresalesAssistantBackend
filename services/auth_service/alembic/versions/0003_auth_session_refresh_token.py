"""add auth session refresh token

Revision ID: 0003_auth_session_refresh_token
Revises: 0002_auth_session_device_metadata
Create Date: 2026-05-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0003_auth_session_refresh_token"
down_revision: str | None = "0002_auth_session_device_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("refresh_token_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "auth_sessions",
        sa.Column("refresh_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute("UPDATE auth_sessions SET refresh_token_hash = token_hash")
    op.execute("UPDATE auth_sessions SET refresh_expires_at = expires_at")
    op.alter_column("auth_sessions", "refresh_token_hash", nullable=False)
    op.alter_column("auth_sessions", "refresh_expires_at", nullable=False)
    op.create_index(
        op.f("ix_auth_sessions_refresh_token_hash"),
        "auth_sessions",
        ["refresh_token_hash"],
        unique=True,
    )
    op.create_index(
        op.f("ix_auth_sessions_refresh_expires_at"),
        "auth_sessions",
        ["refresh_expires_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_auth_sessions_refresh_expires_at"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_refresh_token_hash"), table_name="auth_sessions")
    op.drop_column("auth_sessions", "refresh_expires_at")
    op.drop_column("auth_sessions", "refresh_token_hash")
