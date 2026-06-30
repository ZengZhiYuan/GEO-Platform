"""Add geo_provider_batch and query task batch linkage."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0012"
down_revision = "geo_monitoring_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")


def upgrade() -> None:
    op.create_table(
        "geo_provider_batch",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
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
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("provider_name", sa.String(length=64), nullable=False),
        sa.Column("provider_task_id", sa.String(length=128), nullable=True),
        sa.Column("batch_no", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(length=32),
            server_default="pending",
            nullable=False,
        ),
        sa.Column(
            "total_items",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "completed_items",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column(
            "failed_items",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_submit_json", JSON_VALUE, nullable=True),
        sa.Column("raw_status_json", JSON_VALUE, nullable=True),
        sa.Column("raw_result_json", JSON_VALUE, nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'submitted', 'processing', 'completed', "
            "'partial_completed', 'failed', 'cancelled')",
            name="ck_geo_provider_batch_status",
        ),
        sa.CheckConstraint("total_items >= 0", name="ck_geo_provider_batch_total_items"),
        sa.CheckConstraint(
            "completed_items >= 0", name="ck_geo_provider_batch_completed_items"
        ),
        sa.CheckConstraint(
            "failed_items >= 0", name="ck_geo_provider_batch_failed_items"
        ),
        sa.ForeignKeyConstraint(["run_id"], ["geo_monitor_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "batch_no", name="uq_geo_provider_batch_run_no"),
    )
    op.create_index(
        "ix_geo_provider_batch_run_status",
        "geo_provider_batch",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_geo_provider_batch_provider_task",
        "geo_provider_batch",
        ["provider_name", "provider_task_id"],
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_batch_id", sa.BigInteger(), nullable=True),
    )
    op.create_foreign_key(
        "fk_geo_query_task_provider_batch_id",
        "geo_query_task",
        "geo_provider_batch",
        ["provider_batch_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_geo_query_task_provider_batch_id",
        "geo_query_task",
        type_="foreignkey",
    )
    op.drop_column("geo_query_task", "provider_batch_id")
    op.drop_index(
        "ix_geo_provider_batch_provider_task",
        table_name="geo_provider_batch",
    )
    op.drop_index(
        "ix_geo_provider_batch_run_status",
        table_name="geo_provider_batch",
    )
    op.drop_table("geo_provider_batch")
