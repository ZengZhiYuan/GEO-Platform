"""add keyword_library

Revision ID: a1b2c3d4e5f6
Revises: 327ce9fdb8a5
Create Date: 2026-06-03 14:00:00.000000

关键词库首个业务表，挂在 baseline 之后。字段对齐 docs/claude-code-dev.md 8.3
及通用公共字段（BaseModel）。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "327ce9fdb8a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "keyword_library",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("main_word", sa.String(length=255), nullable=False),
        sa.Column(
            "question_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "optimize_status",
            sa.String(length=32),
            server_default="not_optimized",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_keyword_library_main_word", "keyword_library", ["main_word"]
    )


def downgrade() -> None:
    op.drop_index("ix_keyword_library_main_word", table_name="keyword_library")
    op.drop_table("keyword_library")
