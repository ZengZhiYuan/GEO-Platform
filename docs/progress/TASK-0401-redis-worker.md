# TASK-0401 接入 Redis + Worker

- 分支：feat/worker-generation
- 范围：仅改动 backend/（新增 app/workers、app/tasks、app/services/ai_generation；改 config.py、requirements.txt）+ README.md；未触碰 frontend/；未改既有接口字段名
- 状态：已完成

## 技术选型

- **Broker：Redis**（对齐 docs/decisions.md 003，不引入 RabbitMQ）。
- **MQ 框架：Dramatiq**（而非 Celery）。理由：Redis 原生、无需独立 result backend、
  API 简洁；且开发机为 Windows——Celery prefork 进程池在 Windows 不可用，Dramatiq
  多线程 Worker 在 Windows 原生可用，是「当前依赖更简单且可跑」的一种。

## 变更要点

- 新增 `app/workers/broker.py`：按 `settings.DRAMATIQ_BROKER` 构建 RedisBroker（默认）
  或 StubBroker（测试/无 Redis）；启用 `Retries` + `CurrentMessage` 中间件；
  `dramatiq.set_broker(broker)`。RedisBroker 惰性连接——「导入」不要求 Redis 在线。
- 新增 `app/workers/worker.py`：Dramatiq CLI 入口（`dramatiq app.workers.worker`），
  导入 broker 后导入 `app.tasks.article_tasks` 注册 actor。
- 修改 `app/core/config.py`：新增 `REDIS_URL` / `DRAMATIQ_BROKER` / `ARTICLE_MAX_RETRIES`
  / `AI_PROVIDER` / `AI_MOCK_DELAY_SECONDS`。
- 修改 `backend/requirements.txt`：新增 `dramatiq[redis]>=1.16`。
- 更新 `README.md`：新增「异步任务 Worker（Dramatiq + Redis）」章节（Redis 单容器
  启动命令、Worker 启动命令、Windows 进程/线程参数、`DRAMATIQ_BROKER=stub` 本地验证）。

## 契约一致性

- 不涉及对外接口字段；沿用同步 SQLAlchemy（decisions 002）、Redis broker（decisions 003）。

## 实测

- `python -m venv .venv` + `pip install -r requirements.txt`（dramatiq 2.1.0 安装成功）。
- 无 Redis 在线时 `import app.main` / `import app.workers.worker` 成功；
  `dramatiq.get_broker()` 为 RedisBroker，actor `generate_article` 已注册，max_retries=3。
- StubBroker 端到端：`generate_article.send(id)` 经 `dramatiq.Worker` 消费后，文章
  状态 generating -> pending_review（证明「Worker 可正常消费任务」）。

## 备注 / 遗留

- 未创建 `docker-compose.yml`（其归属 TASK-0102）；README 给出 redis 单容器命令与
  可粘贴的 compose 片段，避免与 TASK-0102 冲突。
- 详见 [[TASK-0402-article-generation]]、[[TASK-0403-task-aggregation]]。
