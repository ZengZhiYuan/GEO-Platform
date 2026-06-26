"""Add project creation wizard draft table."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0010"
down_revision = "geo_monitoring_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "geo_project_draft",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("tenant_id", sa.BigInteger(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        sa.Column("draft_key", sa.String(length=128), nullable=True),
        sa.Column("current_step", sa.Integer(), server_default="1", nullable=False),
        sa.Column("project_data", JSON_VALUE, server_default=sa.text("'{}'"), nullable=False),
        sa.Column(
            "monitor_setup_data",
            JSON_VALUE,
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "current_step >= 1 AND current_step <= 3",
            name="ck_geo_project_draft_current_step",
        ),
    )
    op.create_index(
        "ix_geo_project_draft_key_updated",
        "geo_project_draft",
        ["draft_key", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_geo_project_draft_key_updated", table_name="geo_project_draft")
    op.drop_table("geo_project_draft")
