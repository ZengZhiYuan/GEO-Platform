"""Allow PDF monitoring reports."""

from collections.abc import Sequence

from alembic import op

revision = "geo_monitoring_0006"
down_revision = "geo_monitoring_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_geo_report_format", "geo_report", type_="check")
    op.create_check_constraint(
        "ck_geo_report_format",
        "geo_report",
        "format IN ('md', 'html', 'pdf')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_geo_report_format", "geo_report", type_="check")
    op.create_check_constraint(
        "ck_geo_report_format",
        "geo_report",
        "format IN ('md', 'html')",
    )
