"""add article

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04 17:00:00.000000

文章清单业务表，挂在 content_category 之后。字段对齐 docs/api-contract.md：
    article: writing_task_id / article_title / cover_image_url / status /
             content / error_message
及通用公共字段（BaseModel）。沿用代码库无 DB 外键约定，writing_task_id
仅建索引（ix_article_writing_task_id），引用完整性在 service 层校验。
status 默认 generating（文章由写作任务/Worker 生成）。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "article",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("writing_task_id", sa.BigInteger(), nullable=False),
        sa.Column("article_title", sa.String(length=500), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="generating",
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
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
        "ix_article_writing_task_id", "article", ["writing_task_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_article_writing_task_id", table_name="article")
    op.drop_table("article")
