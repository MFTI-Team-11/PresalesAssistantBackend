"""add presale file storage metadata

Revision ID: 0001_file_storage
Revises:
Create Date: 2026-05-18 00:00:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0001_file_storage"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "presale_documents",
        sa.Column("storage_bucket", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "presale_documents",
        sa.Column("storage_object_key", sa.String(length=512), nullable=True),
    )
    op.add_column("presale_documents", sa.Column("size_bytes", sa.Integer(), nullable=True))
    op.alter_column("presale_documents", "text_content", server_default="")


def downgrade() -> None:
    op.alter_column("presale_documents", "text_content", server_default=None)
    op.drop_column("presale_documents", "size_bytes")
    op.drop_column("presale_documents", "storage_object_key")
    op.drop_column("presale_documents", "storage_bucket")
