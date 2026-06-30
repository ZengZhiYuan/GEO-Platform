"""Add tenant_id indexes for geo monitoring ownership queries."""

from collections.abc import Sequence

from alembic import op

revision = "geo_monitoring_0013"
down_revision = "geo_monitoring_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index(
        "ix_geo_monitor_project_tenant",
        "geo_monitor_project",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_geo_monitor_run_tenant",
        "geo_monitor_run",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_geo_report_tenant",
        "geo_report",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_geo_report_tenant", table_name="geo_report")
    op.drop_index("ix_geo_monitor_run_tenant", table_name="geo_monitor_run")
    op.drop_index("ix_geo_monitor_project_tenant", table_name="geo_monitor_project")
