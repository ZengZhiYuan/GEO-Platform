"""add writing_rule

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-04 15:00:00.000000

写作规范业务表，挂在 image_library 之后。字段对齐 docs/api-contract.md：
    writing_rule: rule_name / creation_type / instruction_content
及通用公共字段（BaseModel）。creation_type 取值 article_creation /
title_creation / traffic_replication，约束在应用层（Schema 枚举）保证。
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "writing_rule",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rule_name", sa.String(length=255), nullable=False),
        sa.Column("creation_type", sa.String(length=32), nullable=False),
        sa.Column("instruction_content", sa.Text(), nullable=False),
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
        "ix_writing_rule_creation_type", "writing_rule", ["creation_type"]
    )


def downgrade() -> None:
    op.drop_index("ix_writing_rule_creation_type", table_name="writing_rule")
    op.drop_table("writing_rule")
