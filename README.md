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

## Docker启动（中间件）

后端运行依赖两个中间件：**PostgreSQL**（数据库，5432）和 **Redis**（Dramatiq broker，6379）。
两者已编排在根目录 `docker-compose.yml`，配置默认值与 `.env.example` 对齐，存在 `.env` 时自动覆盖。

```bash
docker compose up -d        # 一键启动（后台）
docker compose ps           # 查看状态 / 健康检查（healthy 即就绪）
docker compose logs -f      # 跟踪日志
docker compose down         # 停止并删除容器（保留数据卷）
docker compose down -v      # 连同数据卷一起删除（清空数据，慎用）
```

> 无 Docker Compose 的环境，可用等价脚本 `bash scripts/start-middleware.sh`（支持 `stop` / `down` 子命令）。

连接地址通过 `DATABASE_URL` / `REDIS_URL` 配置（默认见 `.env.example`），可在 `.env` 覆盖。

## 异步任务 Worker（Dramatiq + Redis）

写作任务创建后，会按 `ai_generate_count` 拆分出多个文章小任务并投递到 Redis；
由 Dramatiq Worker 异步消费、调用 AI（第一版为 Mock）生成标题与正文。

### 1. 启动中间件

见上方「Docker启动（中间件）」，确保 Redis 已就绪（`docker compose ps` 显示 `healthy`）。

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