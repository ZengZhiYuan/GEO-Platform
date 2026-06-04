#!/usr/bin/env bash
#
# 实朴GEO 中间件一键启动脚本
#
# 启动后端运行所需的两个中间件容器：
#   - PostgreSQL 16  (端口 5432)  应用数据库，连接见 DATABASE_URL
#   - Redis 7        (端口 6379)  Dramatiq broker，连接见 REDIS_URL
#
# 参数与根目录 .env.example 对齐。数据写入命名卷持久化，容器随 Docker 自启。
# 脚本可重复执行：已存在的容器会跳过创建，已停止的会被重新拉起。
#
# 用法：
#   bash scripts/start-middleware.sh          # 启动
#   bash scripts/start-middleware.sh stop     # 停止（保留数据卷）
#   bash scripts/start-middleware.sh down     # 删除容器（保留数据卷）
#
set -euo pipefail

PG_NAME="shipu_geo_postgres"
REDIS_NAME="shipu_geo_redis"

POSTGRES_DB="${POSTGRES_DB:-shipu_geo}"
POSTGRES_USER="${POSTGRES_USER:-shipu_geo}"
POSTGRES_PASSWORD="${POSTGRES_PASSWORD:-shipu_geo_password}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"
REDIS_PORT="${REDIS_PORT:-6379}"

# 确保容器存在且处于运行状态；已存在则按需 start，不存在则 run。
ensure_running() {
  local name="$1"; shift
  if docker ps --format '{{.Names}}' | grep -qx "$name"; then
    echo "✔ $name 已在运行"
  elif docker ps -a --format '{{.Names}}' | grep -qx "$name"; then
    echo "↻ 启动已存在的容器 $name"
    docker start "$name" >/dev/null
  else
    echo "＋ 创建并启动 $name"
    "$@"
  fi
}

start() {
  ensure_running "$PG_NAME" \
    docker run -d --name "$PG_NAME" \
      -e POSTGRES_DB="$POSTGRES_DB" \
      -e POSTGRES_USER="$POSTGRES_USER" \
      -e POSTGRES_PASSWORD="$POSTGRES_PASSWORD" \
      -p "${POSTGRES_PORT}:5432" \
      -v shipu_geo_pgdata:/var/lib/postgresql/data \
      --restart unless-stopped \
      postgres:16

  ensure_running "$REDIS_NAME" \
    docker run -d --name "$REDIS_NAME" \
      -p "${REDIS_PORT}:6379" \
      -v shipu_geo_redisdata:/data \
      --restart unless-stopped \
      redis:7 redis-server --appendonly yes

  echo
  echo "中间件就绪："
  echo "  PostgreSQL  -> postgresql+psycopg2://${POSTGRES_USER}:***@localhost:${POSTGRES_PORT}/${POSTGRES_DB}"
  echo "  Redis       -> redis://localhost:${REDIS_PORT}/0"
}

case "${1:-up}" in
  up|start) start ;;
  stop)     docker stop "$PG_NAME" "$REDIS_NAME" ;;
  down)     docker rm -f "$PG_NAME" "$REDIS_NAME" ;;
  *) echo "用法: $0 [up|stop|down]" >&2; exit 1 ;;
esac
