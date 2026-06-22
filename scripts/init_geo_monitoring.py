#!/usr/bin/env python3
"""一键执行 AI 应用监测模块 PostgreSQL 建表脚本。"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv
import psycopg2


def normalize_database_url(url: str) -> str:
    """将 SQLAlchemy URL 转换为 psycopg2 可识别的 PostgreSQL URL。"""
    return (
        url.replace("postgresql+psycopg2://", "postgresql://", 1)
        .replace("postgresql+psycopg://", "postgresql://", 1)
    )


def mask_url(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.hostname or "unknown"
    port = f":{parsed.port}" if parsed.port else ""
    database = parsed.path.lstrip("/") or "unknown"
    return f"postgresql://***:***@{host}{port}/{database}"


def main() -> int:
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent if script_dir.name == "scripts" else script_dir

    for candidate in (
        Path.cwd() / ".env",
        Path.cwd() / "backend" / ".env",
        project_root / ".env",
        project_root / "backend" / ".env",
    ):
        if candidate.exists():
            load_dotenv(candidate, override=False)

    database_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI")
    if not database_url:
        print("ERROR: 未找到 DATABASE_URL 或 SQLALCHEMY_DATABASE_URI。", file=sys.stderr)
        return 2

    sql_path = script_dir / "init_geo_monitoring.sql"
    if not sql_path.exists():
        print(f"ERROR: 建表脚本不存在：{sql_path}", file=sys.stderr)
        return 3

    normalized_url = normalize_database_url(database_url)
    sql = sql_path.read_text(encoding="utf-8")

    print(f"连接数据库：{mask_url(normalized_url)}")
    try:
        with psycopg2.connect(normalized_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql)
        print("AI 应用监测模块数据库初始化完成。")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: 数据库初始化失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
