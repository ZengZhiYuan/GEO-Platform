#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${REPO_DIR:-$(pwd)}"

cd "$REPO_DIR"

echo "[1/3] 启动 PostgreSQL 与 Redis..."
docker compose up -d postgres redis

echo "[2/3] 等待 PostgreSQL 就绪..."
for _ in $(seq 1 30); do
  if docker compose exec -T postgres pg_isready >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "[3/3] 执行建表脚本..."
python "$ROOT_DIR/init_geo_monitoring.py"

echo "完成。"
