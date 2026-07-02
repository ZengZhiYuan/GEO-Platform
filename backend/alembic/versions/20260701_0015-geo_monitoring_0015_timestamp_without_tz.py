"""Convert timestamptz columns to timestamp without time zone."""

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

from app.core.timestamp_migration import (
    DEFAULT_STORE_TIMEZONE,
    alter_timestamp_to_timestamptz_sql,
    alter_timestamptz_to_timestamp_sql,
    list_timestamp_without_tz_columns,
    list_timestamptz_columns,
)

revision = "geo_monitoring_0015"
down_revision = "geo_monitoring_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LOCK_TIMEOUT = "5s"
STATEMENT_TIMEOUT = "30min"


def _convert_columns(
    connection,
    *,
    direction: str,
    store_timezone: str = DEFAULT_STORE_TIMEZONE,
) -> None:
    context = op.get_context()
    if context.as_sql:
        context.impl.static_output(
            "-- geo_monitoring_0015 skipped in offline SQL mode; "
            "run this migration online or execute "
            "backend/scripts/migrate_timestamptz_to_timestamp.sql "
            "against existing databases."
        )
        return

    columns = (
        list_timestamptz_columns(connection)
        if direction == "upgrade"
        else list_timestamp_without_tz_columns(connection)
    )
    sql_builder = (
        alter_timestamptz_to_timestamp_sql
        if direction == "upgrade"
        else alter_timestamp_to_timestamptz_sql
    )

    for table_name, column_name in columns:
        with context.autocommit_block():
            bind = op.get_bind()
            bind.execute(text(f"SET lock_timeout = '{LOCK_TIMEOUT}'"))
            bind.execute(text(f"SET statement_timeout = '{STATEMENT_TIMEOUT}'"))
            bind.execute(
                text(
                    sql_builder(
                        table_name,
                        column_name,
                        store_timezone=store_timezone,
                    )
                )
            )


def upgrade() -> None:
    connection = op.get_bind()
    _convert_columns(connection, direction="upgrade")


def downgrade() -> None:
    connection = op.get_bind()
    _convert_columns(connection, direction="downgrade")
