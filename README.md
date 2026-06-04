# 实朴GEO

实朴GEO 是一个面向小红书、知乎、微信公众号等自媒体平台的内容生成 Web 应用。

## 模块

### 素材中心

- 关键词库
- 标题灵感
- 画像图库
- 品牌知识库

### 写作工作台

- 写作规范
- 内容分类
- 写作任务
- 文章清单

## 后端启动

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
````

## 前端启动

```bash
cd frontend
npm install
npm run dev
```

## Docker启动

```bash
docker compose up -d
```

## 异步任务 Worker（Dramatiq + Redis）

写作任务创建后，会按 `ai_generate_count` 拆分出多个文章小任务并投递到 Redis；
由 Dramatiq Worker 异步消费、调用 AI（第一版为 Mock）生成标题与正文。

### 1. 启动 Redis

尚未提供 docker-compose（见 TASK-0102），可先用单容器启动：

```bash
docker run -d --name shipu_geo_redis -p 6379:6379 redis:7
```

或加入 `docker-compose.yml`（TASK-0102 会正式编排）：

```yaml
  redis:
    image: redis:7
    container_name: shipu_geo_redis
    ports:
      - "6379:6379"
```

连接地址通过 `REDIS_URL`（默认 `redis://localhost:6379/0`）配置，可在 `.env` 覆盖。

### 2. 启动 Worker

```bash
cd backend
# 已激活 .venv 且 Redis 已就绪
dramatiq app.workers.worker
# Windows 建议显式指定进程/线程数
dramatiq app.workers.worker --processes 1 --threads 4
```

启动后，调用 `POST /api/writing-tasks` 创建写作任务即可看到 Worker 消费日志，
文章状态由 `generating` 流转为 `pending_review`（成功）或 `failed`（失败）。

> 无 Redis 的本地验证：设置环境变量 `DRAMATIQ_BROKER=stub` 使用内存 broker。

## 数据库迁移

迁移使用 Alembic，连接地址从 `app.core.config.settings.DATABASE_URL` 读取
（默认值与根目录 `.env.example` 一致，可通过 `.env` 覆盖）。
执行 `upgrade` / `--autogenerate` 需要 PostgreSQL 已启动（见 Docker 启动）。

```bash
cd backend
# 生成迁移（需连接数据库以对比表结构）
alembic revision --autogenerate -m "your message"
# 应用迁移
alembic upgrade head
# 仅生成 SQL 而不连接数据库（离线预览）
alembic upgrade head --sql
```