"""add writing_task and article

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-04 17:00:00.000000

写作任务（大任务）与文章（小任务）两张业务表，挂在 content_category 之后。
字段对齐 docs/api-contract.md：
    writing_task: task_name / content_category_id / distill_keywords /
        image_category_id / article_image_count / brand_knowledge_id /
        content_rule_id / title_rule_id / article_result_status /
        ai_generate_count / task_status
    article: writing_task_id / article_title / cover_image_url / status /
        content / error_message
及通用公共字段（BaseModel）。沿用「无 DB 外键」约定，仅为引用列建索引。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: str | None = "e5f6a7b8c9d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_columns() -> list[sa.Column]:
    """BaseModel 公共字段。"""
    return [
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
    ]


def upgrade() -> None:
    op.create_table(
        "writing_task",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("task_name", sa.String(length=255), nullable=False),
        sa.Column("content_category_id", sa.BigInteger(), nullable=False),
        sa.Column("distill_keywords", sa.String(length=255), nullable=False),
        sa.Column("image_category_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "article_image_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("brand_knowledge_id", sa.BigInteger(), nullable=True),
        sa.Column("content_rule_id", sa.BigInteger(), nullable=False),
        sa.Column("title_rule_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "article_result_status",
            sa.String(length=64),
            server_default="generating",
            nullable=False,
        ),
        sa.Column(
            "ai_generate_count",
            sa.Integer(),
            server_default="1",
            nullable=False,
        ),
        sa.Column(
            "task_status",
            sa.String(length=64),
            server_default="pending",
            nullable=False,
        ),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_writing_task_content_category_id",
        "writing_task",
        ["content_category_id"],
    )

    op.create_table(
        "article",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("writing_task_id", sa.BigInteger(), nullable=False),
        sa.Column("article_title", sa.String(length=500), nullable=True),
        sa.Column("cover_image_url", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=64),
            server_default="generating",
            nullable=False,
        ),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        *_common_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_article_writing_task_id",
        "article",
        ["writing_task_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_article_writing_task_id", table_name="article")
    op.drop_table("article")
    op.drop_index(
        "ix_writing_task_content_category_id", table_name="writing_task"
    )
    op.drop_table("writing_task")
