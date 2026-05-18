"""add auth session device metadata

Revision ID: 0002_session_device_meta
Revises: 0001_initial_auth
Create Date: 2026-05-17 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002_session_device_meta"
down_revision: str | None = "0001_initial_auth"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("auth_sessions", sa.Column("fingerprint", sa.String(length=255), nullable=True))
    op.add_column("auth_sessions", sa.Column("session_source", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("device_type", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("os_name", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("os_version", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("browser_name", sa.String(length=64), nullable=True))
    op.add_column("auth_sessions", sa.Column("browser_version", sa.String(length=64), nullable=True))
    op.add_column(
        "auth_sessions",
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("auth_sessions", "metadata")
    op.drop_column("auth_sessions", "browser_version")
    op.drop_column("auth_sessions", "browser_name")
    op.drop_column("auth_sessions", "os_version")
    op.drop_column("auth_sessions", "os_name")
    op.drop_column("auth_sessions", "device_type")
    op.drop_column("auth_sessions", "session_source")
    op.drop_column("auth_sessions", "fingerprint")
