"""PostgreSQL timestamptz 与 timestamp 互转 SQL 生成。"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Connection

DEFAULT_STORE_TIMEZONE = "Asia/Shanghai"


def _quote_identifier(value: str) -> str:
    return f'"{value.replace(chr(34), chr(34) * 2)}"'


def _quote_literal(value: str) -> str:
    return f"'{value.replace(chr(39), chr(39) * 2)}'"


def alter_timestamptz_to_timestamp_sql(
    table_name: str,
    column_name: str,
    *,
    table_schema: str = "public",
    store_timezone: str = DEFAULT_STORE_TIMEZONE,
) -> str:
    """将 timestamptz 列改为 timestamp without time zone。"""
    qualified_table = ".".join(
        [_quote_identifier(table_schema), _quote_identifier(table_name)]
    )
    quoted_column = _quote_identifier(column_name)
    return (
        f"ALTER TABLE {qualified_table} ALTER COLUMN {quoted_column} "
        f"TYPE TIMESTAMP WITHOUT TIME ZONE "
        f"USING {quoted_column} AT TIME ZONE {_quote_literal(store_timezone)}"
    )


def alter_timestamp_to_timestamptz_sql(
    table_name: str,
    column_name: str,
    *,
    table_schema: str = "public",
    store_timezone: str = DEFAULT_STORE_TIMEZONE,
) -> str:
    """将 timestamp without time zone 列改回 timestamptz（回滚用）。"""
    qualified_table = ".".join(
        [_quote_identifier(table_schema), _quote_identifier(table_name)]
    )
    quoted_column = _quote_identifier(column_name)
    return (
        f"ALTER TABLE {qualified_table} ALTER COLUMN {quoted_column} "
        f"TYPE TIMESTAMP WITH TIME ZONE "
        f"USING {quoted_column} AT TIME ZONE {_quote_literal(store_timezone)}"
    )


def list_timestamptz_columns(
    connection: Connection,
    *,
    table_schema: str = "public",
    table_prefix: str = "geo_",
) -> list[tuple[str, str]]:
    """查询仍为 timestamptz 的业务表时间列。"""
    rows = connection.execute(
        text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = :table_schema
              AND udt_name = 'timestamptz'
              AND table_name LIKE :prefix
            ORDER BY table_name, ordinal_position
            """
        ),
        {"table_schema": table_schema, "prefix": f"{table_prefix}%"},
    ).fetchall()
    return [(str(table_name), str(column_name)) for table_name, column_name in rows]


def list_timestamp_without_tz_columns(
    connection: Connection,
    *,
    table_schema: str = "public",
    table_prefix: str = "geo_",
) -> list[tuple[str, str]]:
    """查询 timestamp without time zone 的业务表时间列。"""
    rows = connection.execute(
        text(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = :table_schema
              AND udt_name = 'timestamp'
              AND table_name LIKE :prefix
            ORDER BY table_name, ordinal_position
            """
        ),
        {"table_schema": table_schema, "prefix": f"{table_prefix}%"},
    ).fetchall()
    return [(str(table_name), str(column_name)) for table_name, column_name in rows]


def convert_timestamptz_columns(
    connection: Connection,
    *,
    table_schema: str = "public",
    table_prefix: str = "geo_",
    store_timezone: str = DEFAULT_STORE_TIMEZONE,
) -> list[tuple[str, str]]:
    """转换所有匹配的 timestamptz 列，返回已转换的 (table, column) 列表。"""
    converted: list[tuple[str, str]] = []
    for table_name, column_name in list_timestamptz_columns(
        connection, table_schema=table_schema, table_prefix=table_prefix
    ):
        connection.execute(
            text(
                alter_timestamptz_to_timestamp_sql(
                    table_name,
                    column_name,
                    table_schema=table_schema,
                    store_timezone=store_timezone,
                )
            )
        )
        converted.append((table_name, column_name))
    return converted
