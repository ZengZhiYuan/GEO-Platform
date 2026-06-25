"""Add brand dimension to metric snapshots."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "geo_monitoring_0008"
down_revision = "geo_monitoring_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "geo_metric_snapshot",
        sa.Column(
            "brand_id",
            sa.BigInteger(),
            sa.ForeignKey("geo_brand.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.drop_index("uq_geo_metric_snapshot_dimension", table_name="geo_metric_snapshot")
    op.create_index(
        "uq_geo_metric_snapshot_dimension",
        "geo_metric_snapshot",
        [
            "project_id",
            "run_id",
            "metric_code",
            sa.text("coalesce(platform_code, '')"),
            sa.text("coalesce(prompt_id, -1)"),
            sa.text("coalesce(brand_id, -1)"),
        ],
        unique=True,
    )
    op.create_index(
        "ix_geo_metric_snapshot_brand_trend",
        "geo_metric_snapshot",
        ["project_id", "brand_id", "metric_code", "platform_code", "snapshot_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_geo_metric_snapshot_brand_trend", table_name="geo_metric_snapshot")
    op.drop_index("uq_geo_metric_snapshot_dimension", table_name="geo_metric_snapshot")
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
    op.drop_column("geo_metric_snapshot", "brand_id")
