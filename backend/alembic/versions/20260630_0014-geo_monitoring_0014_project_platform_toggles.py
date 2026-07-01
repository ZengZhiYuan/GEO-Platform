"""Add per-platform deep thinking and search toggles to monitor projects."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0014"
down_revision = "geo_monitoring_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VALUE = postgresql.JSONB().with_variant(sa.JSON(), "sqlite")


def upgrade() -> None:
    op.add_column(
        "geo_monitor_project",
        sa.Column(
            "deep_thinking_enabled_by_platform",
            JSON_VALUE,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "geo_monitor_project",
        sa.Column(
            "search_enabled_by_platform",
            JSON_VALUE,
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("geo_monitor_project", "search_enabled_by_platform")
    op.drop_column("geo_monitor_project", "deep_thinking_enabled_by_platform")
