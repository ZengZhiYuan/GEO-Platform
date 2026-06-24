"""Add Aidso collection source to monitoring runs."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "geo_monitoring_0007"
down_revision = "geo_monitoring_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "geo_monitor_run",
        sa.Column(
            "collection_source",
            sa.String(length=20),
            server_default="official",
            nullable=False,
        ),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column(
            "aidso_thinking_enabled",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        "collection_source IN ('official', 'aidso')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        type_="check",
    )
    op.drop_column("geo_monitor_run", "aidso_thinking_enabled")
    op.drop_column("geo_monitor_run", "collection_source")
