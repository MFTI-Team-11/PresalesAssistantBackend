"""add presale description and chat messages

Revision ID: 0002_presale_chat
Revises: 0001_file_storage
Create Date: 2026-05-22 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.dialects import postgresql

revision: str = "0002_presale_chat"
down_revision: str | None = "0001_file_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    inspector = inspect(op.get_bind())
    presale_columns = {column["name"] for column in inspector.get_columns("presale_requests")}
    if "description" not in presale_columns:
        op.add_column("presale_requests", sa.Column("description", sa.Text(), nullable=True))

    if "presale_chat_messages" not in inspector.get_table_names():
        op.create_table(
            "presale_chat_messages",
            sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("presale_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["presale_id"], ["presale_requests.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_presale_chat_messages_presale_id",
            "presale_chat_messages",
            ["presale_id"],
        )


def downgrade() -> None:
    inspector = inspect(op.get_bind())
    if "presale_chat_messages" in inspector.get_table_names():
        indexes = {index["name"] for index in inspector.get_indexes("presale_chat_messages")}
        if "ix_presale_chat_messages_presale_id" in indexes:
            op.drop_index("ix_presale_chat_messages_presale_id", table_name="presale_chat_messages")
        op.drop_table("presale_chat_messages")
    presale_columns = {column["name"] for column in inspector.get_columns("presale_requests")}
    if "description" in presale_columns:
        op.drop_column("presale_requests", "description")
