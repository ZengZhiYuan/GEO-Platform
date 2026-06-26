"""Add monitoring_paused flag to monitor projects."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "geo_monitoring_0009"
down_revision = "geo_monitoring_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "geo_monitor_project",
        sa.Column(
            "monitoring_paused",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_column("geo_monitor_project", "monitoring_paused")
