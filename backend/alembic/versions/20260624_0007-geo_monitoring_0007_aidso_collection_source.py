"""Add Aidso collection source to monitoring runs."""

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
    platform_table = sa.table(
        "geo_ai_platform",
        sa.column("platform_code", sa.String),
        sa.column("platform_name", sa.String),
        sa.column("adapter_type", sa.String),
        sa.column("base_url", sa.String),
        sa.column("model_name", sa.String),
        sa.column("search_enabled", sa.Boolean),
        sa.column("citation_supported", sa.Boolean),
        sa.column("max_concurrency", sa.Integer),
        sa.column("timeout_seconds", sa.Integer),
        sa.column("enabled", sa.Boolean),
        sa.column("extra_config", sa.JSON),
    )
    op.bulk_insert(
        platform_table,
        [
            {
                "platform_code": code,
                "platform_name": name,
                "adapter_type": "aidso",
                "base_url": None,
                "model_name": f"aidso:{aidso_name}",
                "search_enabled": True,
                "citation_supported": True,
                "max_concurrency": 2,
                "timeout_seconds": 120,
                "enabled": True,
                "extra_config": {"aidso_name": aidso_name},
            }
            for code, name, aidso_name in AIDSO_PLATFORM_ROWS
        ],
    )


def downgrade() -> None:
    op.execute("DELETE FROM geo_ai_platform WHERE platform_code LIKE 'aidso_%'")
    op.drop_constraint(
        "ck_geo_monitor_run_collection_source",
        "geo_monitor_run",
        type_="check",
    )
    op.drop_column("geo_monitor_run", "aidso_thinking_enabled")
    op.drop_column("geo_monitor_run", "collection_source")
