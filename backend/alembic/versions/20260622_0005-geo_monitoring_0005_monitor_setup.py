"""Add core keywords, prompt library, and monitor setup fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "geo_monitoring_0005"
down_revision = "geo_monitoring_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "geo_monitor_project",
        sa.Column(
            "default_platform_codes",
            sa.JSON(),
            server_default=sa.text("'[]'"),
            nullable=False,
        ),
    )

    op.create_table(
        "geo_core_keyword",
        *_common_columns(),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("keyword", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "project_id", "keyword", name="uq_geo_core_keyword_project_keyword"
        ),
    )
    op.create_index(
        "ix_geo_core_keyword_project_sort",
        "geo_core_keyword",
        ["project_id", "sort_order"],
    )

    op.create_table(
        "geo_prompt_library",
        *_common_columns(),
        sa.Column("prompt_code", sa.String(length=64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "prompt_type",
            sa.String(length=50),
            server_default="generic",
            nullable=False,
        ),
        sa.Column("industry", sa.String(length=100), nullable=True),
        sa.Column("scene_tag", sa.String(length=100), nullable=True),
        sa.Column("default_core_keyword", sa.String(length=100), nullable=True),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.UniqueConstraint("prompt_code", name="uq_geo_prompt_library_code"),
    )
    op.create_index(
        "ix_geo_prompt_library_industry_enabled",
        "geo_prompt_library",
        ["industry", "enabled"],
    )

    op.add_column(
        "geo_prompt",
        sa.Column("core_keyword_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_geo_prompt_core_keyword_id",
        "geo_prompt",
        "geo_core_keyword",
        ["core_keyword_id"],
        ["id"],
        ondelete="SET NULL",
    )

    prompt_library = sa.table(
        "geo_prompt_library",
        sa.column("prompt_code", sa.String),
        sa.column("prompt_text", sa.Text),
        sa.column("prompt_type", sa.String),
        sa.column("industry", sa.String),
        sa.column("scene_tag", sa.String),
        sa.column("default_core_keyword", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("is_deleted", sa.Boolean),
    )
    op.bulk_insert(
        prompt_library,
        [
            {
                "prompt_code": "LIB_RECOMMEND_001",
                "prompt_text": "推荐国内有哪些值得看的文旅演艺项目？",
                "prompt_type": "recommendation",
                "industry": "文旅演艺",
                "scene_tag": "推荐",
                "default_core_keyword": "文旅演艺",
                "enabled": True,
                "is_deleted": False,
            },
            {
                "prompt_code": "LIB_COMPARE_001",
                "prompt_text": "宋城演艺和只有河南·戏剧幻城哪个更值得看？",
                "prompt_type": "comparison",
                "industry": "文旅演艺",
                "scene_tag": "对比",
                "default_core_keyword": "文旅演艺",
                "enabled": True,
                "is_deleted": False,
            },
            {
                "prompt_code": "LIB_VISIBILITY_001",
                "prompt_text": "介绍一下只有河南·戏剧幻城这个品牌。",
                "prompt_type": "brand_visibility",
                "industry": "文旅演艺",
                "scene_tag": "品牌认知",
                "default_core_keyword": "只有河南",
                "enabled": True,
                "is_deleted": False,
            },
        ],
    )


def downgrade() -> None:
    op.drop_constraint("fk_geo_prompt_core_keyword_id", "geo_prompt", type_="foreignkey")
    op.drop_column("geo_prompt", "core_keyword_id")
    op.drop_index("ix_geo_prompt_library_industry_enabled", table_name="geo_prompt_library")
    op.drop_table("geo_prompt_library")
    op.drop_index("ix_geo_core_keyword_project_sort", table_name="geo_core_keyword")
    op.drop_table("geo_core_keyword")
    op.drop_column("geo_monitor_project", "default_platform_codes")
