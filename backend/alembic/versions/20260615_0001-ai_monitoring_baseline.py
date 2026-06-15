"""AI 应用监测数据库基线。"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0001"
down_revision = None
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
    op.create_table(
        "geo_monitor_project",
        *_common_columns(),
        sa.Column("project_name", sa.String(length=100), nullable=False),
        sa.Column(
            "industry",
            sa.String(length=100),
            server_default="文旅演艺",
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="Asia/Shanghai",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=20), server_default="active", nullable=False
        ),
        sa.Column("official_domain", sa.String(length=255), nullable=True),
        sa.Column("report_title", sa.String(length=255), nullable=True),
        sa.Column("report_subtitle", sa.String(length=500), nullable=True),
        sa.CheckConstraint(
            "status IN ('active', 'disabled', 'archived')",
            name="ck_geo_monitor_project_status",
        ),
    )
    op.create_index(
        "ix_geo_monitor_project_status", "geo_monitor_project", ["status"]
    )

    op.create_table(
        "geo_brand",
        *_common_columns(),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("brand_name", sa.String(length=255), nullable=False),
        sa.Column(
            "brand_type",
            sa.String(length=20),
            server_default="competitor",
            nullable=False,
        ),
        sa.Column("official_domain", sa.String(length=255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(length=20), server_default="active", nullable=False
        ),
        sa.CheckConstraint(
            "brand_type IN ('target', 'competitor', 'candidate')",
            name="ck_geo_brand_type",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'disabled')", name="ck_geo_brand_status"
        ),
        sa.UniqueConstraint(
            "project_id", "brand_name", name="uq_geo_brand_project_name"
        ),
    )
    op.create_index(
        "ix_geo_brand_project_type", "geo_brand", ["project_id", "brand_type"]
    )
    op.create_index(
        "uq_geo_brand_one_target_per_project",
        "geo_brand",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("brand_type = 'target' AND is_deleted = false"),
    )

    op.create_table(
        "geo_brand_alias",
        *_common_columns(),
        sa.Column(
            "brand_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_brand.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_name", sa.String(length=255), nullable=False),
        sa.Column(
            "match_mode",
            sa.String(length=20),
            server_default="contains",
            nullable=False,
        ),
        sa.Column(
            "is_ambiguous",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "context_keywords",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "match_mode IN ('exact', 'contains', 'context')",
            name="ck_geo_brand_alias_match_mode",
        ),
        sa.UniqueConstraint("brand_id", "alias_name", name="uq_geo_brand_alias"),
    )
    op.create_index("ix_geo_brand_alias_brand_id", "geo_brand_alias", ["brand_id"])
    op.create_index("ix_geo_brand_alias_name", "geo_brand_alias", ["alias_name"])

    op.create_table(
        "geo_prompt_set",
        *_common_columns(),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("set_name", sa.String(length=100), nullable=False),
        sa.Column("version_no", sa.String(length=50), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="draft", nullable=False
        ),
        sa.Column(
            "prompt_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('draft', 'active', 'archived')",
            name="ck_geo_prompt_set_status",
        ),
        sa.UniqueConstraint(
            "project_id", "version_no", name="uq_geo_prompt_set_version"
        ),
    )
    op.create_index(
        "ix_geo_prompt_set_project_status",
        "geo_prompt_set",
        ["project_id", "status"],
    )
    op.create_index(
        "uq_geo_prompt_set_one_active_per_project",
        "geo_prompt_set",
        ["project_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND is_deleted = false"),
    )

    op.create_table(
        "geo_prompt",
        *_common_columns(),
        sa.Column(
            "prompt_set_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_prompt_set.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_code", sa.String(length=64), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "prompt_type",
            sa.String(length=50),
            server_default="generic",
            nullable=False,
        ),
        sa.Column("scene_tag", sa.String(length=100), nullable=True),
        sa.Column(
            "contains_brand",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.UniqueConstraint(
            "prompt_set_id", "prompt_code", name="uq_geo_prompt_code"
        ),
    )
    op.create_index(
        "ix_geo_prompt_prompt_set_enabled",
        "geo_prompt",
        ["prompt_set_id", "enabled", "sort_order"],
    )

    op.create_table(
        "geo_ai_platform",
        *_common_columns(),
        sa.Column("platform_code", sa.String(length=32), nullable=False),
        sa.Column("platform_name", sa.String(length=100), nullable=False),
        sa.Column(
            "adapter_type",
            sa.String(length=50),
            server_default="openai_compatible",
            nullable=False,
        ),
        sa.Column("base_url", sa.String(length=500), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column(
            "search_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "citation_supported",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "max_concurrency", sa.Integer(), server_default="2", nullable=False
        ),
        sa.Column(
            "timeout_seconds", sa.Integer(), server_default="120", nullable=False
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "extra_config",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "max_concurrency > 0", name="ck_geo_ai_platform_max_concurrency"
        ),
        sa.CheckConstraint(
            "timeout_seconds > 0", name="ck_geo_ai_platform_timeout"
        ),
        sa.UniqueConstraint("platform_code", name="uq_geo_ai_platform_code"),
    )
    op.create_index(
        "ix_geo_ai_platform_platform_code",
        "geo_ai_platform",
        ["platform_code"],
        unique=True,
    )

    op.create_table(
        "geo_monitor_run",
        *_common_columns(),
        sa.Column("run_no", sa.String(length=64), nullable=False),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_project.id"),
            nullable=False,
        ),
        sa.Column(
            "prompt_set_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_prompt_set.id"),
            nullable=False,
        ),
        sa.Column("prompt_set_version", sa.String(length=50), nullable=False),
        sa.Column(
            "trigger_type",
            sa.String(length=20),
            server_default="manual",
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(length=30), server_default="pending", nullable=False
        ),
        sa.Column(
            "collection_status",
            sa.String(length=30),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "analysis_status",
            sa.String(length=30),
            server_default="skipped",
            nullable=False,
        ),
        sa.Column(
            "report_status",
            sa.String(length=30),
            server_default="skipped",
            nullable=False,
        ),
        sa.Column(
            "platform_codes",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "expected_query_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "success_query_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "failed_query_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "valid_answer_count", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "data_completeness_rate",
            sa.Numeric(precision=8, scale=4),
            server_default="0",
            nullable=False,
        ),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "trigger_type IN ('manual', 'schedule', 'retry')",
            name="ck_geo_monitor_run_trigger_type",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'collecting', 'analyzing', 'reporting', "
            "'completed', 'partial_success', 'failed', 'cancelled')",
            name="ck_geo_monitor_run_status",
        ),
        sa.CheckConstraint(
            "collection_status IN ('pending', 'running', 'completed', "
            "'partial_success', 'failed', 'cancelled')",
            name="ck_geo_monitor_run_collection_status",
        ),
        sa.CheckConstraint(
            "analysis_status IN ('pending', 'running', 'completed', "
            "'partial_success', 'failed', 'skipped')",
            name="ck_geo_monitor_run_analysis_status",
        ),
        sa.CheckConstraint(
            "report_status IN ('pending', 'running', 'completed', 'failed', 'skipped')",
            name="ck_geo_monitor_run_report_status",
        ),
        sa.UniqueConstraint("run_no", name="uq_geo_monitor_run_no"),
    )
    op.create_index(
        "ix_geo_monitor_run_project_created",
        "geo_monitor_run",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_geo_monitor_run_status", "geo_monitor_run", ["status", "created_at"]
    )

    op.create_table(
        "geo_query_task",
        *_common_columns(),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prompt_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_prompt.id"),
            nullable=False,
        ),
        sa.Column(
            "platform_code",
            sa.String(length=32),
            sa.ForeignKey("geo_ai_platform.platform_code"),
            nullable=False,
        ),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default="pending", nullable=False
        ),
        sa.Column("key_slot", sa.Integer(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("request_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("response_http_status", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=100), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'queued', 'running', 'success', 'failed', 'cancelled')",
            name="ck_geo_query_task_status",
        ),
        sa.CheckConstraint(
            "retry_count >= 0", name="ck_geo_query_task_retry_count"
        ),
        sa.UniqueConstraint(
            "run_id", "prompt_id", "platform_code", name="uq_geo_query_task"
        ),
        sa.UniqueConstraint(
            "idempotency_key", name="uq_geo_query_task_idempotency_key"
        ),
    )
    op.create_index(
        "ix_geo_query_task_run_status", "geo_query_task", ["run_id", "status"]
    )
    op.create_index(
        "ix_geo_query_task_platform_status",
        "geo_query_task",
        ["platform_code", "status"],
    )

    platform_table = sa.table(
        "geo_ai_platform",
        sa.column("platform_code", sa.String()),
        sa.column("platform_name", sa.String()),
        sa.column("adapter_type", sa.String()),
    )
    op.bulk_insert(
        platform_table,
        [
            {
                "platform_code": "doubao",
                "platform_name": "豆包",
                "adapter_type": "openai_compatible",
            },
            {
                "platform_code": "qwen",
                "platform_name": "通义千问",
                "adapter_type": "openai_compatible",
            },
            {
                "platform_code": "yuanbao",
                "platform_name": "腾讯元宝",
                "adapter_type": "tencent",
            },
            {
                "platform_code": "deepseek",
                "platform_name": "DeepSeek",
                "adapter_type": "openai_compatible",
            },
            {
                "platform_code": "kimi",
                "platform_name": "Kimi",
                "adapter_type": "openai_compatible",
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("geo_query_task")
    op.drop_table("geo_monitor_run")
    op.drop_table("geo_ai_platform")
    op.drop_table("geo_prompt")
    op.drop_table("geo_prompt_set")
    op.drop_table("geo_brand_alias")
    op.drop_table("geo_brand")
    op.drop_table("geo_monitor_project")
