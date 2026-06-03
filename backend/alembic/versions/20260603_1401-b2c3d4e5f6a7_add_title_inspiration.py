"""add title_inspiration

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-03 14:01:00.000000

标题灵感业务表，挂在 keyword_library 之后。字段对齐 docs/api-contract.md
（main_word / question / collect_status）及通用公共字段（BaseModel）。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "title_inspiration",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("main_word", sa.String(length=255), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column(
            "collect_status",
            sa.String(length=32),
            server_default="not_included",
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
        "ix_title_inspiration_main_word", "title_inspiration", ["main_word"]
    )


def downgrade() -> None:
    op.drop_index(
        "ix_title_inspiration_main_word", table_name="title_inspiration"
    )
    op.drop_table("title_inspiration")
