# AI 应用监测平台

本项目用于配置监测项目、品牌、版本化 Prompt 和 AI 平台，并创建监测运行及其查询任务。当前版本完成配置域、运行落库骨架和管理端壳层；真实平台采集、指标分析、Agent 分析、调度与报告尚未实现。

## AI 应用监测 MVP V2 开发约束

> **适用范围：** 本版本只规划 `backend` 目录下的 MVP 功能实现。`frontend` 目录暂不纳入开发、测试和验收；后续需要前端时再单独拆分任务。

**目标：** 基于当前 GEO-Platform 后端基础设施，实现 AI 应用监测 MVP 的后端闭环：监测配置、官方 API 采集、确定性指标、Agent 洞察、调度、报告和后端部署验证。

**统一本地运行环境：** PostgreSQL、Redis、Nacos 已在服务器中安装部署，连接信息已写入本地 `.env`。后续本地运行、调试和联调统一使用 `.env` 中配置的这三项服务，不再要求本地 Docker 启动 PostgreSQL/Redis/Nacos。

**后端架构：** FastAPI + SQLAlchemy + Alembic 提供控制面和数据面 API；Dramatiq/Redis 承担采集、分析和报告异步任务；独立 APScheduler 进程创建定时运行；PostgreSQL 保存业务数据；Nacos 提供后端运行所需的外部配置/服务发现基础；报告写入本地目录或后续配置的持久化目录。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy 2、Alembic、PostgreSQL 16、Redis 7、Dramatiq、APScheduler、LangGraph、Pydantic、Nacos、OpenAI-compatible LLM SDK、Jinja2、pytest、respx、freezegun。

## 当前能力

- 监测项目、品牌与品牌别名管理
- Prompt 集版本管理、激活与内容摘要
- AI 平台参数管理
- 监测运行创建及 Prompt×Platform 查询任务扇出
- PostgreSQL、Redis、Dramatiq 基础设施
- React + Ant Design 监测管理端壳层

## 后端

```powershell
cd backend
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-dev.txt
Copy-Item ..\.env.example ..\.env
# 编辑 ..\.env，填入服务器 PostgreSQL、Redis、Nacos 的真实连接信息。
backend\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

本地运行统一从仓库根目录 `.env` 读取 PostgreSQL、Redis、Nacos 以及采集平台、Agent LLM、调度与报告相关配置；代码和文档示例不得硬编码服务器地址、用户名、密码或 token。`.env.example` 仅提供占位符，真实密钥只写入本地 `.env` 或 Nacos 配置中心。

### 采集 Worker 生产部署

创建监测运行（`POST /api/geo-monitoring/runs`）后，任务经 Dramatiq 异步入队，须由独立 Worker 进程消费。生产联调请注意：

1. **API 与 Worker 共用同一份 `.env`**：两者必须使用相同的 `REDIS_URL`，且 `DRAMATIQ_BROKER=redis`（勿在生产环境使用 `stub`）。
2. **独立启动 Worker 进程**：除 FastAPI 外，须另启 Worker 并监听 `collection` 队列，否则任务会长期停留在 `queued`：

   ```powershell
   cd backend
   .venv\Scripts\dramatiq.exe app.worker.actors.collection -Q collection --processes 2 --threads 1
   ```

3. **测试环境与生产环境区分**：pytest 在 `backend/tests/conftest.py` 中固定 `DRAMATIQ_BROKER=stub`，仅用于单元测试；本地联调与生产部署必须设为 `redis` 并确保 Redis 可达。

主要连接项：

- `DATABASE_URL`：服务器 PostgreSQL
- `REDIS_URL`：服务器 Redis（Dramatiq 与后续采集/分析任务共用）
- `DRAMATIQ_BROKER`：异步任务 broker 类型；生产/联调为 `redis`，pytest 为 `stub`
- `NACOS_SERVER_ADDRESSES`、`NACOS_NAMESPACE`、`NACOS_GROUP`、`NACOS_CONFIG_DATA_ID`：Nacos 配置中心；需要时在 `.env` 中设置 `NACOS_ENABLED=true`
- `DOUBAO_*`、`QWEN_*`、`YUANBAO_*`、`DEEPSEEK_*`、`KIMI_*`：各平台官方 API 采集配置（默认关闭）
- `AGENT_LLM_*`：Agent 语义分析 LLM
- `SCHEDULER_*`：独立调度进程开关与时区
- `REPORT_STORAGE_DIR`：报告本地存储目录

接口前缀为 `/api/geo-monitoring`。健康与就绪探针：

- `/api/geo-monitoring/health`：进程存活检查
- `/api/geo-monitoring/ready`：数据库与 Redis 连通性（启用 Nacos 时附带 Nacos 检查）
- 兼容保留 `/api/health` 与 `/api/ready`

跨域默认关闭；本地前后端联调时在 `.env` 设置 `CORS_ALLOWED_ORIGINS`（逗号分隔，例如 `http://localhost:5173`）。生产环境保持 `DEBUG=false`，异常响应不返回堆栈。

结构化日志（JSON）统一包含 `request_id`、`run_id`、`task_id`、`platform_code`、`duration_ms` 等字段；API 响应头返回 `X-Request-ID` 与 `X-Response-Time-Ms`。Worker 启动时可调用 `app.core.logging.log_worker_startup`，调度进程可调用 `log_scheduler_startup`。

## 前端

`frontend` 目录当前仅保留已有管理端壳层。V2 后端 MVP 不开发、测试或验收前端；后续需要前端时再单独拆分任务。

## 中间件

```powershell
# PostgreSQL、Redis、Nacos 使用本地 .env 中配置的服务器服务。
# 本地默认不再通过 Docker 启动这些中间件。
```

PostgreSQL 用于业务数据，Redis 与 Dramatiq 用于后续采集、分析和报告异步任务，Nacos 用于后端运行所需的外部配置和服务发现基础。不要在文档、日志或提交中输出 `.env` 内的真实连接信息和密钥。

`/api/ready` 会检查数据库和 Redis 连通性，并且只返回脱敏后的连接目标摘要。Nacos 就绪检查保留为独立函数，后续接入管理命令或运维探针时显式调用，避免普通单元测试和本地 API 启动被 Nacos 网络状态阻塞。

## 数据库迁移

当前迁移是新的监测业务基线 `geo_monitoring_0001`。不要直接应用到包含旧迁移历史的数据库；应使用空数据库或明确清理后的开发环境。

```powershell
cd backend
python -m alembic heads
python -m alembic upgrade head --sql
python -m alembic upgrade head
```

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -v
.venv\Scripts\python.exe -m pytest -v tests/e2e
.venv\Scripts\python.exe -m pytest -q --cov=app --cov-report=term-missing
```

默认 e2e 测试使用 **mock 平台 HTTP（respx）与 Fake Agent LLM**，不连接真实官方 API 或 Agent LLM。可选 smoke test（需用户确认 `.env` 中 PostgreSQL/Redis/Nacos 可达，并显式启用真实平台/LLM 配置）不在 CI 默认 pytest 范围内。

测试环境通过 `backend/tests/conftest.py` 注入独立配置并使用 SQLite/Stub broker 覆盖运行依赖，不直接连接共享服务器 PostgreSQL、Redis 或 Nacos。

平台密钥、Agent LLM 密钥与 Nacos 账号只通过 `.env` 或 Nacos 配置中心注入；Settings 对外只暴露脱敏摘要，不要在仓库、日志或普通数据库字段中保存明文密钥。
