"""Add molizhishu collection source and provider tracking fields."""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "geo_monitoring_0011"
down_revision = "geo_monitoring_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

JSON_VALUE = sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql")

MOLIZHISHU_PLATFORM_ROWS = [
    (
        "molizhishu_deepseek_web",
        "DeepSeek 网页端",
        "deepseek",
        {
            "molizhishu_platform": "deepseek",
            "base_platform": "deepseek",
            "endpoint_type": "web",
            "default_mode": "reasoning_search",
            "supported_modes": ["standard", "reasoning", "search", "reasoning_search"],
        },
    ),
    (
        "molizhishu_deepseek_mobile",
        "DeepSeek 手机端",
        "deepseek_mobile",
        {
            "molizhishu_platform": "deepseek_mobile",
            "base_platform": "deepseek",
            "endpoint_type": "app",
            "default_mode": "reasoning_search",
            "supported_modes": ["standard", "reasoning", "search", "reasoning_search"],
        },
    ),
    (
        "molizhishu_doubao_web",
        "豆包网页端",
        "doubao",
        {
            "molizhishu_platform": "doubao",
            "base_platform": "doubao",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_doubao_mobile",
        "豆包手机端",
        "doubao_mobile",
        {
            "molizhishu_platform": "doubao_mobile",
            "base_platform": "doubao",
            "endpoint_type": "app",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_yuanbao_web",
        "腾讯元宝",
        "yuanbao",
        {
            "molizhishu_platform": "yuanbao",
            "base_platform": "yuanbao",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_kimi_web",
        "Kimi",
        "kimi",
        {
            "molizhishu_platform": "kimi",
            "base_platform": "kimi",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_qianwen_web",
        "通义千问",
        "qianwen",
        {
            "molizhishu_platform": "qianwen",
            "base_platform": "qianwen",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_quark_web",
        "夸克 AI",
        "quark",
        {
            "molizhishu_platform": "quark",
            "base_platform": "quark",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_baiduai_web",
        "百度 AI+",
        "baiduai",
        {
            "molizhishu_platform": "baiduai",
            "base_platform": "baiduai",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_weibo_zhisou_web",
        "微博智搜",
        "weibo_zhisou",
        {
            "molizhishu_platform": "weibo_zhisou",
            "base_platform": "weibo_zhisou",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
    (
        "molizhishu_wenxinyiyan_web",
        "文心一言",
        "wenxinyiyan",
        {
            "molizhishu_platform": "wenxinyiyan",
            "base_platform": "wenxinyiyan",
            "endpoint_type": "web",
            "default_mode": "search",
            "supported_modes": ["standard", "search"],
        },
    ),
]


def _molizhishu_platform_codes_sql_list() -> str:
    return ", ".join(_sql_literal(row[0]) for row in MOLIZHISHU_PLATFORM_ROWS)


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    op.drop_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        type_="check",
    )
    op.create_check_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        "collection_source IN ('official', 'aidso', 'molizhishu')",
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column(
            "provider_mode_by_platform",
            JSON_VALUE,
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column(
            "provider_screenshot",
            sa.Integer(),
            server_default="0",
            nullable=False,
        ),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("provider_callback_url", sa.String(length=500), nullable=True),
    )
    op.add_column(
        "geo_monitor_run",
        sa.Column("region_code", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_name", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_task_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_subtask_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_platform_code", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_mode", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_status", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_result_json", JSON_VALUE, nullable=True),
    )
    op.add_column(
        "geo_query_task",
        sa.Column("provider_error_message", sa.Text(), nullable=True),
    )
    for code, name, molizhishu_platform, extra_config in MOLIZHISHU_PLATFORM_ROWS:
        extra_config_json = json.dumps(extra_config, ensure_ascii=False)
        op.execute(
            "INSERT INTO geo_ai_platform ("
            "platform_code, platform_name, adapter_type, base_url, model_name, "
            "search_enabled, citation_supported, max_concurrency, timeout_seconds, "
            "enabled, extra_config"
            ") VALUES ("
            f"{_sql_literal(code)}, {_sql_literal(name)}, 'molizhishu', NULL, "
            f"{_sql_literal(f'molizhishu:{molizhishu_platform}')}, true, true, 2, 120, true, "
            f"{_sql_literal(extra_config_json)}::jsonb"
            ")"
        )


def downgrade() -> None:
    op.execute(
        "DELETE FROM geo_ai_platform "
        f"WHERE platform_code IN ({_molizhishu_platform_codes_sql_list()})"
    )
    op.drop_column("geo_query_task", "provider_error_message")
    op.drop_column("geo_query_task", "provider_result_json")
    op.drop_column("geo_query_task", "provider_status")
    op.drop_column("geo_query_task", "provider_mode")
    op.drop_column("geo_query_task", "provider_platform_code")
    op.drop_column("geo_query_task", "provider_subtask_id")
    op.drop_column("geo_query_task", "provider_task_id")
    op.drop_column("geo_query_task", "provider_name")
    op.drop_column("geo_monitor_run", "region_code")
    op.drop_column("geo_monitor_run", "provider_callback_url")
    op.drop_column("geo_monitor_run", "provider_screenshot")
    op.drop_column("geo_monitor_run", "provider_mode_by_platform")
    op.drop_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        type_="check",
    )
    op.create_check_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        "collection_source IN ('official', 'aidso')",
    )
