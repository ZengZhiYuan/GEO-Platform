"""Add GEO analysis metrics and agent execution tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0003"
down_revision = "geo_monitoring_0002"
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
        "geo_agent_execution",
        *_common_columns(),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform_code", sa.String(length=32), nullable=True),
        sa.Column("agent_code", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.String(length=20),
            server_default="1.0",
            nullable=False,
        ),
        sa.Column(
            "input_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "output_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("model_provider", sa.String(length=100), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'success', 'failed', 'skipped')",
            name="ck_geo_agent_execution_status",
        ),
    )
    op.create_index(
        "uq_geo_agent_execution_run_agent",
        "geo_agent_execution",
        [
            "run_id",
            "agent_code",
            "schema_version",
            sa.text("coalesce(platform_code, '')"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_geo_agent_execution_run_platform_agent",
        "geo_agent_execution",
        ["run_id", "platform_code", "agent_code"],
    )

    op.create_table(
        "geo_platform_analysis",
        *_common_columns(),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "platform_code",
            sa.String(length=32),
            sa.ForeignKey("geo_ai_platform.platform_code"),
            nullable=False,
        ),
        sa.Column(
            "valid_answer_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "data_completeness_rate",
            sa.Numeric(8, 4),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "brand_mention_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "brand_mention_rate",
            sa.Numeric(8, 4),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "brand_first_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "brand_first_rate",
            sa.Numeric(8, 4),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "brand_first_among_mentions_rate",
            sa.Numeric(8, 4),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "top_competitors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "top_sources",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "prompt_competitiveness_summary",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "improvement_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'partial_success', 'failed')",
            name="ck_geo_platform_analysis_status",
        ),
        sa.UniqueConstraint(
            "run_id",
            "platform_code",
            name="uq_geo_platform_analysis",
        ),
    )

    op.create_table(
        "geo_metric_snapshot",
        *_common_columns(),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform_code", sa.String(length=32), nullable=True),
        sa.Column(
            "prompt_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_prompt.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metric_code", sa.String(length=100), nullable=False),
        sa.Column("numerator", sa.Numeric(18, 4), nullable=True),
        sa.Column("denominator", sa.Numeric(18, 4), nullable=True),
        sa.Column("metric_value", sa.Numeric(18, 6), nullable=True),
        sa.Column(
            "metric_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "snapshot_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("prompt_set_version", sa.String(length=50), nullable=False),
        sa.Column(
            "is_comparable",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column(
            "completeness_rate",
            sa.Numeric(8, 4),
            server_default="0",
            nullable=False,
        ),
    )
    op.create_index(
        "uq_geo_metric_snapshot_dimension",
        "geo_metric_snapshot",
        [
            "project_id",
            "run_id",
            "metric_code",
            sa.text("coalesce(platform_code, '')"),
            sa.text("coalesce(prompt_id, -1)"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_geo_metric_snapshot_trend",
        "geo_metric_snapshot",
        ["project_id", "metric_code", "platform_code", "snapshot_at"],
    )

    op.create_table(
        "geo_prompt_competitiveness",
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
        sa.Column(
            "target_mentioned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("target_rank", sa.Integer(), nullable=True),
        sa.Column("target_first", sa.Boolean(), nullable=True),
        sa.Column(
            "competitors_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("position_label", sa.String(length=30), nullable=True),
        sa.Column("competitiveness_score", sa.Numeric(8, 4), nullable=True),
        sa.Column(
            "evidence_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.UniqueConstraint(
            "run_id",
            "prompt_id",
            "platform_code",
            name="uq_geo_prompt_competitiveness",
        ),
    )
    op.create_index(
        "ix_geo_prompt_competitiveness_run_prompt",
        "geo_prompt_competitiveness",
        ["run_id", "prompt_id"],
    )

    op.create_table(
        "geo_source_stat",
        *_common_columns(),
        sa.Column(
            "run_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_run.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("platform_code", sa.String(length=32), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=False),
        sa.Column("source_name", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column(
            "citation_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "brand_related_count",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "share_rate",
            sa.Numeric(8, 4),
            server_default="0",
            nullable=False,
        ),
        sa.Column("rank_no", sa.Integer(), nullable=True),
    )
    op.create_index(
        "uq_geo_source_stat_run_platform_domain",
        "geo_source_stat",
        [
            "run_id",
            "domain",
            sa.text("coalesce(platform_code, '')"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_geo_source_stat_run_platform_rank",
        "geo_source_stat",
        ["run_id", "platform_code", "rank_no"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_geo_source_stat_run_platform_rank",
        table_name="geo_source_stat",
    )
    op.drop_table("geo_source_stat")

    op.drop_index(
        "ix_geo_prompt_competitiveness_run_prompt",
        table_name="geo_prompt_competitiveness",
    )
    op.drop_table("geo_prompt_competitiveness")

    op.drop_index(
        "ix_geo_metric_snapshot_trend",
        table_name="geo_metric_snapshot",
    )
    op.drop_table("geo_metric_snapshot")

    op.drop_table("geo_platform_analysis")

    op.drop_index(
        "ix_geo_agent_execution_run_platform_agent",
        table_name="geo_agent_execution",
    )
    op.drop_index(
        "uq_geo_agent_execution_run_agent",
        table_name="geo_agent_execution",
    )
    op.drop_table("geo_agent_execution")
