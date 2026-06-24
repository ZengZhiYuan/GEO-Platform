"""Add Aidso collection source to monitoring runs."""

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision = "geo_monitoring_0007"
down_revision = "geo_monitoring_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

AIDSO_PLATFORM_ROWS = [
    ("aidso_doubao_web", "豆包 Web 端", "DB"),
    ("aidso_doubao_app", "豆包 App 端", "DOUBA"),
    ("aidso_deepseek_web", "DeepSeek Web 端", "DP"),
    ("aidso_deepseek_app", "DeepSeek App 端", "DPA"),
    ("aidso_kimi_web", "Kimi Web 端", "KIMI"),
    ("aidso_yuanbao_web", "元宝 Web 端", "TXYB"),
    ("aidso_yuanbao_app", "元宝 App 端", "TXYBA"),
    ("aidso_qwen_web", "千问 Web 端", "TYQW"),
    ("aidso_qwen_app", "千问 App 端", "TYQWA"),
    ("aidso_baidu_web", "百度 AI", "BDAI"),
    ("aidso_douyin_web", "抖音 AI", "DYAI"),
    ("aidso_wenxin_web", "文心一言", "WXYY"),
]


def _sql_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


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
            "aidso_thinking_enabled_by_platform",
            sa.JSON(),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_check_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        "collection_source IN ('official', 'aidso')",
    )
    for code, name, aidso_name in AIDSO_PLATFORM_ROWS:
        extra_config = json.dumps({"aidso_name": aidso_name}, ensure_ascii=False)
        op.execute(
            "INSERT INTO geo_ai_platform ("
            "platform_code, platform_name, adapter_type, base_url, model_name, "
            "search_enabled, citation_supported, max_concurrency, timeout_seconds, "
            "enabled, extra_config"
            ") VALUES ("
            f"{_sql_literal(code)}, {_sql_literal(name)}, 'aidso', NULL, "
            f"{_sql_literal(f'aidso:{aidso_name}')}, true, true, 2, 120, true, "
            f"{_sql_literal(extra_config)}::jsonb"
            ")"
        )


def downgrade() -> None:
    op.execute("DELETE FROM geo_ai_platform WHERE platform_code LIKE 'aidso_%'")
    op.drop_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        type_="check",
    )
    op.drop_column("geo_monitor_run", "aidso_thinking_enabled_by_platform")
    op.drop_column("geo_monitor_run", "collection_source")
