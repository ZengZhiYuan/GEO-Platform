"""Add GEO monitoring schedule and report tables."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "geo_monitoring_0004"
down_revision = "geo_monitoring_0003"
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
    op.create_table(
        "geo_monitor_schedule",
        *_common_columns(),
        sa.Column(
            "project_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_monitor_project.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("cron_expr", sa.String(length=100), nullable=False),
        sa.Column(
            "timezone",
            sa.String(length=64),
            server_default="Asia/Shanghai",
            nullable=False,
        ),
        sa.Column(
            "enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("next_run_at", sa.DateTime(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(), nullable=True),
        sa.Column(
            "misfire_policy",
            sa.String(length=20),
            server_default="fire_once",
            nullable=False,
        ),
        sa.CheckConstraint(
            "misfire_policy IN ('fire_once', 'ignore')",
            name="ck_geo_monitor_schedule_misfire_policy",
        ),
    )
    op.create_index(
        "uq_geo_monitor_schedule_project_name",
        "geo_monitor_schedule",
        ["project_id", "name"],
        unique=True,
    )
    op.create_index(
        "ix_geo_monitor_schedule_project_enabled",
        "geo_monitor_schedule",
        ["project_id", "enabled"],
    )

    op.create_table(
        "geo_report",
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
        sa.Column(
            "status",
            sa.String(length=20),
            server_default="pending",
            nullable=False,
        ),
        sa.Column("format", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("relative_storage_path", sa.String(length=500), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=True),
        sa.Column("checksum", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'generating', 'completed', 'failed')",
            name="ck_geo_report_status",
        ),
        sa.CheckConstraint(
            "format IN ('md', 'html')",
            name="ck_geo_report_format",
        ),
        sa.CheckConstraint(
            "relative_storage_path NOT LIKE '/%' "
            "AND relative_storage_path !~ '^[A-Za-z]:' "
            "AND relative_storage_path NOT LIKE '\\\\%'",
            name="ck_geo_report_relative_storage_path",
        ),
    )
    op.create_index(
        "uq_geo_report_relative_storage_path",
        "geo_report",
        ["relative_storage_path"],
        unique=True,
    )
    op.create_index(
        "ix_geo_report_project_run",
        "geo_report",
        ["project_id", "run_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_geo_report_project_run",
        table_name="geo_report",
    )
    op.drop_index(
        "uq_geo_report_relative_storage_path",
        table_name="geo_report",
    )
    op.drop_table("geo_report")

    op.drop_index(
        "ix_geo_monitor_schedule_project_enabled",
        table_name="geo_monitor_schedule",
    )
    op.drop_index(
        "uq_geo_monitor_schedule_project_name",
        table_name="geo_monitor_schedule",
    )
    op.drop_table("geo_monitor_schedule")
