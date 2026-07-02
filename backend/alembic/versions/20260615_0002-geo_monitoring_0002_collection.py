"""Add GEO collection answer result tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0002"
down_revision = "geo_monitoring_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _common_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
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
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
    ]


def upgrade() -> None:
    op.add_column(
        "geo_monitor_run",
        sa.Column("triggered_by", sa.BigInteger(), nullable=True),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("total_tasks", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("succeeded_tasks", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("failed_tasks", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("cancelled_tasks", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("error_summary", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_geo_monitor_run_status_completed",
        "geo_monitor_run",
        ["status", "completed_at"],
    )

    op.add_column(
        "geo_query_task",
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("queued_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("last_error_code", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("last_error_message", sa.Text(), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_request_id", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ix_geo_query_task_status_queued",
        "geo_query_task",
        ["status", "queued_at"],
    )

    op.create_table(
        "geo_answer",
        *_common_columns(),
        sa.Column(
            "task_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_query_task.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "platform_code",
            sa.String(length=32),
            sa.ForeignKey("geo_ai_platform.platform_code"),
            nullable=False,
        ),
        sa.Column(
            "prompt_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_prompt.id"),
            nullable=False,
        ),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("normalized_text", sa.Text(), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=True),
        sa.Column(
            "prompt_tokens", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column(
            "completion_tokens", sa.Integer(), server_default="0", nullable=False
        ),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column(
            "collected_at",
            sa.DateTime(),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "raw_response_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.UniqueConstraint("task_id", name="uq_geo_answer_task"),
    )
    op.create_index(
        "ix_geo_answer_platform_collected",
        "geo_answer",
        ["platform_code", "collected_at"],
    )

    op.create_table(
        "geo_answer_citation",
        *_common_columns(),
        sa.Column(
            "answer_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_answer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("citation_no", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("domain", sa.String(length=255), nullable=True),
        sa.Column("source_type", sa.String(length=50), nullable=True),
        sa.Column("quoted_text", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "answer_id", "citation_no", name="uq_geo_answer_citation_answer_no"
        ),
    )
    op.create_index(
        "ix_geo_answer_citation_domain",
        "geo_answer_citation",
        ["domain"],
    )

    op.create_table(
        "geo_answer_brand_result",
        *_common_columns(),
        sa.Column(
            "answer_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_answer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "brand_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_brand.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "is_mentioned",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("mention_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("first_position", sa.Integer(), nullable=True),
        sa.Column("sentiment", sa.String(length=30), nullable=True),
        sa.Column(
            "context_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "answer_id", "brand_id", name="uq_geo_answer_brand_result_answer_brand"
        ),
    )
    op.create_index(
        "ix_geo_answer_brand_result_brand_mentioned",
        "geo_answer_brand_result",
        ["brand_id", "is_mentioned"],
    )


def downgrade() -> None:
    op.drop_table("geo_answer_brand_result")
    op.drop_table("geo_answer_citation")
    op.drop_index("ix_geo_answer_platform_collected", table_name="geo_answer")
    op.drop_table("geo_answer")

    op.drop_index("ix_geo_query_task_status_queued", table_name="geo_query_task")
    op.drop_column("geo_query_task", "provider_request_id")
    op.drop_column("geo_query_task", "last_error_message")
    op.drop_column("geo_query_task", "last_error_code")
    op.drop_column("geo_query_task", "completed_at")
    op.drop_column("geo_query_task", "queued_at")
    op.drop_column("geo_query_task", "max_attempts")
    op.drop_column("geo_query_task", "attempt_count")

    op.drop_index("ix_geo_monitor_run_status_completed", table_name="geo_monitor_run")
    op.drop_column("geo_monitor_run", "error_summary")
    op.drop_column("geo_monitor_run", "completed_at")
    op.drop_column("geo_monitor_run", "cancelled_tasks")
    op.drop_column("geo_monitor_run", "failed_tasks")
    op.drop_column("geo_monitor_run", "succeeded_tasks")
    op.drop_column("geo_monitor_run", "total_tasks")
    op.drop_column("geo_monitor_run", "triggered_by")
