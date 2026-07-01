# GEO-Platform

GEO-Platform 是一个后端优先的 AI 应用监测平台。系统围绕监测项目、品牌、竞品、Prompt 集和 AI 平台配置工作，按 `Prompt x Platform` 发起采集，沉淀 AI 回答、引用源、品牌识别、指标快照、Agent 洞察，并输出 Markdown / HTML / PDF 诊断报告。

当前仓库后端开发主线包括接口缺口补齐、第三方采集接口替换（Aidso → 模力指数）和生产 readiness 整改。开发重心在 `backend/`；`frontend/` 保留 React + Vite + Ant Design 管理端壳层，除非明确要求，一般不作为当前后端任务的改动范围。

- 当前业务 API 前缀：`/api/geo-monitoring`
- 兼容业务 API 前缀：`/api/v1/geo-monitoring`
- 当前 Alembic head：`geo_monitoring_0014`
- 默认配置文件：仓库根目录 `.env`
- 报告默认目录：本地 `./data/reports`，容器内 `/app/backend/data/reports`

## 当前能力

- 项目管理：项目列表、项目卡片概览、项目切换器、一步创建项目、创建向导草稿、暂停/恢复监测、删除前关联检查。
- 监测配置：目标品牌、竞品、品牌别名、核心词、Prompt 词库、Prompt 集版本、监测设置、平台端元数据与展示字典。
- AI 生成辅助：优先 Agent LLM 结构化生成品牌词、竞品和监测问题候选，失败或未配置时规则兜底；候选结果不自动落库。
- 平台采集：支持豆包、通义千问、腾讯元宝、DeepSeek、Kimi 官方 Adapter，以及 `collection_source=molizhishu` 的模力指数第三方采集（11 个 `molizhishu_*` 平台端、ProviderBatch、回调与轮询兜底）。历史 Aidso 数据只读兼容，新建 Run 不再接受 `collection_source=aidso`。
- 异步运行：创建监测运行后生成 QueryTask，由 Dramatiq worker 消费 `collection`、`analysis`、`report` 队列；手工触发分析会入队并返回 `queued=true`。
- 分析指标：品牌可见度、提及率、首位率、平均排名、平台表现、Prompt 竞争力、引用来源、竞品表现、趋势快照等确定性指标。
- Agent 洞察：采集/分析完成后可通过 LangGraph + OpenAI-compatible LLM 生成诊断和建议，并保留 Agent 执行审计。
- 页面级聚合：数据大盘、AI 对话记录、竞品分析、信源引用分析等原型页面所需聚合接口。
- 导出与报告：AI 对话记录 CSV、信源引用分析 CSV，以及 Markdown / HTML / PDF 监测报告生成、下载和删除。
- 定时任务：APScheduler 独立进程轮询启用的 cron 计划并触发监测运行。

## 技术栈

| 层次 | 当前实现 |
| --- | --- |
| API | FastAPI、Pydantic、统一响应封装、统一异常处理、健康/就绪探针 |
| 数据访问 | SQLAlchemy 2.0、Alembic、PostgreSQL；pytest 默认使用 SQLite |
| 异步任务 | Redis + Dramatiq；测试中使用 stub broker |
| 调度 | APScheduler 独立进程 |
| 采集 | httpx、tenacity、平台 Adapter、API key 池 |
| Agent | LangGraph、OpenAI SDK、DashScope 可选传输 |
| 报告 | Jinja2、Markdown、ReportLab、文件存储 |
| 配置 | pydantic-settings、`.env`、可选 Nacos |
| 前端壳层 | React 18、TypeScript、Vite、Ant Design、React Router、Axios |

## 目录结构

```text
.
├── backend/
│   ├── app/
│   │   ├── main.py                       # FastAPI 应用入口
│   │   ├── api/router.py                 # 全局 API router 与探针
│   │   ├── core/                         # 配置、数据库、响应、异常、日志、ready 检查
│   │   ├── models/                       # ORM 通用基类
│   │   ├── geo_monitoring/               # AI 应用监测业务域
│   │   │   ├── api/                      # 业务接口路由
│   │   │   ├── services/                 # 业务编排与事务边界
│   │   │   ├── repositories/             # 查询与持久化封装
│   │   │   ├── analysis/                 # 指标、品牌、竞品、信源分析
│   │   │   ├── adapters/                 # 官方 / 模力指数 / 历史 Aidso 采集适配器
│   │   │   ├── agents/                   # LangGraph Agent 分析链路
│   │   │   ├── reports/                  # 报告渲染、PDF、文件存储
│   │   │   ├── templates/report/         # md/html 报告模板
│   │   │   ├── models.py                 # 监测域 ORM 模型
│   │   │   └── schemas.py                # Pydantic 入参与出参
│   │   ├── worker/actors/                # Dramatiq collection/analysis/report actor
│   │   └── scheduler/                    # APScheduler 入口与任务同步
│   ├── alembic/                          # 数据库迁移
│   ├── scripts/                          # API 联调、E2E、平台 smoke 脚本
│   └── tests/                            # 后端测试
├── frontend/                             # 管理端壳层
├── docs/                                 # API 文档、测试文档、任务书、原型映射、部署资料
├── scripts/                              # 初始化和迁移辅助脚本
├── Dockerfile                            # 后端运行镜像
├── docker-compose.yml                    # API / worker / scheduler 编排
└── .env.example                          # 本地配置模板
```

## 主要接口模块

所有业务接口都挂在 `/api/geo-monitoring` 下，并同步保留 `/api/v1/geo-monitoring` 兼容前缀。

| 模块 | 代表接口 |
| --- | --- |
| 探针 | `GET /api/health`、`GET /api/ready`、`GET /api/geo-monitoring/health`、`GET /api/geo-monitoring/ready` |
| 项目 | `GET/POST /projects`、`POST /projects:setup`、`GET /projects/overview`、`POST /projects/{id}/pause`、`POST /projects/{id}/resume` |
| 创建向导草稿 | `POST /project-drafts`、`PUT /project-drafts/current`、`GET /project-drafts/current` |
| 品牌与核心词 | `/projects/{project_id}/brands`、`/brands/{brand_id}/aliases`、`/projects/{project_id}/core-keywords` |
| Prompt | `/prompt-library`、`/projects/{project_id}/prompt-sets`、`/prompt-sets/{id}/prompts`、`/prompt-sets/{id}/activate` |
| 平台与字典 | `/platforms`、`/platform-endpoints`、`/prompt-types`、`/source-types`、`/benchmarks` |
| AI 生成 | `/ai/brand-words:generate`、`/ai/competitors:generate`、`/ai/questions:generate`、`/projects/{project_id}/ai/*:generate` |
| 运行与任务 | `/runs`、`/runs/{run_id}`、`/runs/{run_id}/cancel`、`/runs/{run_id}/retry-failed`、`/runs/{run_id}/query-tasks` |
| 分析与看板 | `/runs/{run_id}/analyze`、`/runs/{run_id}/analysis`、`/projects/{project_id}/dashboard`、`/projects/{project_id}/dashboard/overview`、`/projects/{project_id}/trends` |
| 页面级聚合 | `/projects/{project_id}/conversation-questions`、`/competitor-analysis`、`/source-analysis` |
| 导出 | `/conversation-questions/export`、`/source-analysis/export` |
| 调度 | `/projects/{project_id}/schedules`、`/schedules/{id}/enable`、`/disable`、`/trigger` |
| 报告 | `POST /runs/{run_id}/reports`、`GET /reports/{report_id}/download`、`DELETE /reports/{report_id}` |

接口返回统一使用：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页接口的 `data` 包含 `items`、`total`、`page`、`page_size`。比率与平均排名等 decimal 字段按字符串返回；无分母时返回 `null`。

## 本地开发

### 1. 准备环境

后端指定使用 `backend/.venv`。Windows / PowerShell 下建议所有后端命令都显式使用该解释器。

```powershell
# 仓库根目录
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Copy-Item .env.example .env
```

编辑 `.env`，至少确认：

```env
APP_ENV=dev
APP_DEBUG=false
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<server-host>:5432/geo_platform
REDIS_URL=redis://:<password>@<server-host>:6379/0
DRAMATIQ_BROKER=redis
NACOS_ENABLED=false
REPORT_STORAGE_DIR=./data/reports
```

本地开发默认连接外部 PostgreSQL / Redis / Nacos，不要求在 compose 中启动这些中间件。

### 2. 执行迁移

```powershell
cd backend
.\.venv\Scripts\alembic.exe -c alembic.ini heads
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

当前迁移链：

```text
geo_monitoring_0001
  -> geo_monitoring_0002
  -> geo_monitoring_0003
  -> geo_monitoring_0004
  -> geo_monitoring_0005
  -> geo_monitoring_0006
  -> geo_monitoring_0007
  -> geo_monitoring_0008
  -> geo_monitoring_0009
  -> geo_monitoring_0010
  -> geo_monitoring_0011
  -> geo_monitoring_0012
  -> geo_monitoring_0013
  -> geo_monitoring_0014
```

空库可以通过 Alembic 初始化到最新版本。`docs/geo-platform_schema.sql` 已按 `geo_monitoring_0014` 生成，仅用于空库人工建表参考；已有数据的库不要重复执行全量建表 SQL。

### 3. 启动 API

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

访问：

- Swagger UI: `http://127.0.0.1:8000/docs`
- OpenAPI: `http://127.0.0.1:8000/openapi.json`
- 监测健康检查：`http://127.0.0.1:8000/api/geo-monitoring/health`
- 监测就绪检查：`http://127.0.0.1:8000/api/geo-monitoring/ready`

### 4. 启动 worker

```powershell
cd backend
.\.venv\Scripts\dramatiq.exe app.worker.actors.collection app.worker.actors.analysis app.worker.actors.report `
  -Q collection -Q analysis -Q report --processes 2 --threads 1
```

worker 消费三类队列：

- `collection`：执行单条 QueryTask 采集，可按平台失败隔离和重试。
- `analysis`：生成确定性指标快照和 Agent 洞察。
- `report`：生成报告文件。

本地联调可使用上面的 all-in-one worker；生产建议按队列拆分 worker，避免采集队列积压时阻塞分析或报告任务：

```powershell
# 采集 worker：外部平台调用、模力指数 ProviderBatch 提交与轮询
.\.venv\Scripts\dramatiq.exe app.worker.actors.collection `
  -Q collection --processes 4 --threads 2

# 分析 worker：确定性指标与 Agent LLM 洞察
.\.venv\Scripts\dramatiq.exe app.worker.actors.analysis `
  -Q analysis --processes 1 --threads 1

# 报告 worker：异步报告生成/清理任务
.\.venv\Scripts\dramatiq.exe app.worker.actors.report `
  -Q report --processes 1 --threads 1
```

推荐的生产环境变量：

```env
COLLECTION_WORKER_PROCESSES=4
COLLECTION_WORKER_THREADS=2
ANALYSIS_WORKER_PROCESSES=1
ANALYSIS_WORKER_THREADS=1
REPORT_WORKER_PROCESSES=1
REPORT_WORKER_THREADS=1
```

### 5. 启动 scheduler

调度进程要求 `.env` 中 `SCHEDULER_ENABLED=true`。

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.scheduler.main
```

scheduler 会按 `SCHEDULER_POLL_SECONDS` 周期同步数据库中启用的 cron 调度，并触发监测运行。

## 采集运行示例

创建普通运行：

```http
POST /api/geo-monitoring/runs
Content-Type: application/json

{
  "project_id": 1
}
```

指定模力指数第三方采集（需 `.env` 中 `MOLIZHISHU_ENABLED=true` 且配置 `MOLIZHISHU_API_TOKEN`）：

```http
POST /api/geo-monitoring/runs
Content-Type: application/json

{
  "project_id": 1,
  "collection_source": "molizhishu",
  "platform_codes": ["molizhishu_doubao_web", "molizhishu_kimi_web"],
  "provider_mode_by_platform": {
    "molizhishu_doubao_web": "search",
    "molizhishu_kimi_web": "standard"
  },
  "provider_screenshot": 0,
  "region_code": "110000"
}
```

区域编码可选，列表见 `GET /api/geo-monitoring/providers/molizhishu/regions`。`collection_source=aidso` 与 `aidso_thinking_enabled_by_platform` 在新建请求中返回 `422`（历史 Run 详情仍可读取）。

取消运行、重试失败任务：

```http
POST /api/geo-monitoring/runs/{run_id}/cancel
POST /api/geo-monitoring/runs/{run_id}/retry-failed
```

触发 Agent 分析：

```http
POST /api/geo-monitoring/runs/{run_id}/analyze
```

该接口会校验 `AGENT_LLM_*` 后投递到 `analysis` 队列，返回 `queued=true`；调用方应轮询 `GET /api/geo-monitoring/runs/{run_id}` 或 `GET /api/geo-monitoring/runs/{run_id}/analysis`，等待 `analysis_status=completed` 后再展示洞察或生成报告。

## 报告生成与下载

生成单一格式：

```http
POST /api/geo-monitoring/runs/{run_id}/reports
Content-Type: application/json

{
  "formats": ["pdf"]
}
```

一次生成多种格式：

```json
{
  "formats": ["md", "html", "pdf"]
}
```

下载报告：

```http
GET /api/geo-monitoring/reports/{report_id}/download
```

`pdf` 响应类型为 `application/pdf`，`md` 和 `html` 使用 UTF-8 文本响应。报告文件写入 `REPORT_STORAGE_DIR`；容器部署时写入持久卷 `geo_platform_reports_data`。

## 后端部署、发布与回滚

`docker-compose.yml` 只编排后端 API、Dramatiq worker 和 APScheduler scheduler，不启动 PostgreSQL、Redis、Nacos。生产建议将 Dramatiq worker 拆分为 `worker-collection`、`worker-analysis`、`worker-report` 三个服务；如部署文件尚未拆分，可继续使用 all-in-one `worker` 服务临时过渡。三者连接信息从根目录 `.env` 读取。

**发布前：** 备份数据库和报告目录；确认 `.env` 中 `APP_ENV=prod`、`DRAMATIQ_BROKER=redis`、Agent LLM 与需启用的平台开关已显式配置（未启用的官方平台保持 `*_ENABLED=false`；Nacos 不可用时设 `NACOS_ENABLED=false` 使用本地 `.env` 兜底）。

**发布顺序（固定）：** 构建镜像 → 暂停 worker/scheduler → 执行迁移 → 启动拆分 worker/scheduler，最后切换 API。

```bash
cd /opt/geo-platform
git pull origin main

docker compose config --quiet
docker compose build

docker compose stop worker-collection worker-analysis worker-report scheduler
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head

docker compose up -d worker-collection worker-analysis worker-report scheduler
docker compose up -d api
docker compose ps
```

若部署文件仍使用旧的 all-in-one `worker` 服务，发布命令中的 `worker-collection worker-analysis worker-report` 临时替换为 `worker`；生产新部署建议采用拆分服务名。

**发布后 smoke（分层，不再使用 mock run）：**

1. **config preflight（默认，无付费）：** 在仓库根目录执行 `backend/scripts/run_production_smoke_test.py`，仅检查配置与 blocker。
2. **ready 探针：** `GET /api/geo-monitoring/health` 与 `GET /api/geo-monitoring/ready` 均返回成功。
3. **可选真实 smoke：** 加 `--api-preflight` 或 `--business-loop --allow-paid-provider`（见 `docker-compose.yml` 中 `x-release-commands`）。

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py
backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py --api-preflight --base-url http://127.0.0.1:8000
```

**回滚：** 应用回滚优先回滚镜像，不自动 downgrade 数据库；平台异常优先将对应 `*_ENABLED=false` 并重启 worker。

常用运维命令：

```bash
docker compose logs -f --tail=100 api
docker compose logs -f --tail=100 worker-collection
docker compose logs -f --tail=100 worker-analysis
docker compose logs -f --tail=100 worker-report
docker compose logs -f --tail=100 scheduler
docker compose restart worker-collection worker-analysis worker-report
docker compose down
```

不要轻易执行 `docker compose down -v`，它会删除报告持久卷 `geo_platform_reports_data`。容器访问宿主机中间件时，不要把 `DATABASE_URL` 或 `REDIS_URL` 的 host 写成 `localhost`，优先使用服务器内网 IP 或 `host.docker.internal`。

生产镜像通过 `.dockerignore` 排除 `backend/tests`、`backend/scripts`、`backend/app/test` 与本地 `data/`，仅保留 API / worker / scheduler 运行所需代码。正式 Dramatiq 入口为 `app.worker.actors.*`，生产推荐拆分消费 `collection`、`analysis`、`report` 三个队列；历史 `app.workers` 空包已移除。

## Docker Compose 部署

本节与上一节「后端部署、发布与回滚」内容一致，保留命令速查。

## 关键配置

| 配置 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接；pytest 可覆盖为 SQLite |
| `REDIS_URL` | Redis 连接；Dramatiq 与运行时标记共用 |
| `DRAMATIQ_BROKER` | 联调/生产使用 `redis`，测试覆盖为 `stub`；`APP_ENV=prod` 时启动会拒绝 `stub` |
| `APP_ENV` | `dev` 为本地默认；生产部署设为 `prod` 并触发 fail-fast 校验 |
| `API_PREFIX` | 默认 `/api` |
| `CORS_ALLOWED_ORIGINS` | 逗号分隔的允许跨域来源；为空时不开放跨域凭据 |
| `REPORT_STORAGE_DIR` | 报告文件目录 |
| `REPORT_PUBLIC_BASE_URL` | 可选报告公开访问基地址 |
| `SCHEDULER_ENABLED` | scheduler 进程开关 |
| `SCHEDULER_POLL_SECONDS` | 调度计划同步周期 |
| `NACOS_ENABLED` / `NACOS_*` | 可选配置中心连接 |
| `COLLECTION_*` | 采集超时、重试、并发、模力指数/Aidso 轮询上限、原始响应保存开关 |
| `COLLECTION_WORKER_*` / `ANALYSIS_WORKER_*` / `REPORT_WORKER_*` | 生产拆分 worker 的进程数和线程数；本地 all-in-one worker 可继续使用 `WORKER_PROCESSES` / `WORKER_THREADS` |
| `DOUBAO_*` / `QWEN_*` / `YUANBAO_*` / `DEEPSEEK_*` / `KIMI_*` | 官方平台 Adapter 开关、模型、密钥或凭证 |
| `MOLIZHISHU_*` / `COLLECTION_MOLIZHISHU_*` | 模力指数 API 开关、Token、超时、轮询、截图默认、回调与区域列表 |
| `AIDSO_*` / `COLLECTION_AIDSO_MAX_POLLS` | **历史兼容**：仅用于续跑历史 pending Aidso 任务；新建 Run 不使用 |
| `AGENT_LLM_*` | Agent 语义分析使用的 OpenAI-compatible 或 DashScope LLM 配置；`APP_ENV=prod` 时三项必填 |

### 生产环境 fail-fast（`APP_ENV=prod`）

线上进程启动时会拒绝以下配置，避免误用测试默认值或隐式开关：

- `DRAMATIQ_BROKER` 必须为 `redis`，不得为 `stub`。
- `AGENT_LLM_BASE_URL`、`AGENT_LLM_API_KEY`、`AGENT_LLM_MODEL` 不能为空。
- `API_AUTH_ENABLED` 必须为 `true`，且必须显式配置 `API_AUTH_TOKEN_MAP_JSON` 或 `API_AUTH_BEARER_TOKENS`。
- 启用模力指数（`MOLIZHISHU_ENABLED=true`）时，`.env` 必须显式提供 `MOLIZHISHU_ENABLED`、`MOLIZHISHU_API_TOKEN`、`MOLIZHISHU_PROVIDER_BATCH_ENABLED`，不能仅依赖代码默认值。
- `GET /api/geo-monitoring/ready` 会返回数据库、Redis、`platform_runtime` 和可选 Nacos 诊断；`platform_runtime` 用于脱敏展示 DB 启用平台、adapter 注册、凭证数量与 `ready_for_collection` 状态，不输出 token 明文。

真实账号、密码、API Key 只写入 `.env`、Nacos 或服务器密钥管理系统，不写入仓库。

## 测试与验收

后端测试必须使用 `backend/.venv`。

```powershell
# 后端完整测试
backend\.venv\Scripts\python.exe -m pytest -v backend\tests

# 当前监测域常用回归
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring

# 快速静默回归
backend\.venv\Scripts\python.exe -m pytest backend\tests -q

# Alembic 检查
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head --sql
```

报告相关测试在 Windows / Codex 沙箱下可能涉及文件原子替换和删除，建议使用工作区内临时目录：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring --basetemp .pytest-tmp
```

接口联调脚本需要本地 API 已启动：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py --base-url http://127.0.0.1:8000
backend\.venv\Scripts\python.exe backend\scripts\run_api_focused_retest.py --base-url http://127.0.0.1:8000
backend\.venv\Scripts\python.exe backend\scripts\run_e2e_pipeline_test.py --base-url http://127.0.0.1:8000
```

pytest 默认使用 SQLite、Stub broker、mock 平台 HTTP 和 Fake Agent LLM，不连接真实官方 API。真实平台 smoke 需要在 `.env` 中显式启用对应平台并配置密钥，且必须手动执行下列脚本。

### Smoke 分层（Task O4）

| 层级 | 命令 | 说明 |
| --- | --- | --- |
| mock 回归 | `backend\.venv\Scripts\python.exe -m pytest -v backend\tests` | 自动化测试，不访问真实 provider |
| preflight dry-run | `backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py` | 默认仅检查配置与 blocker，不产生费用 |
| adapter-smoke | `backend\.venv\Scripts\python.exe backend\scripts\molizhishu_smoke_test.py --allow-paid-provider` | 单条模力指数 adapter 真实 HTTP，可能付费，不写业务库 |
| business-loop | `backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py --business-loop --allow-paid-provider` | 经 API 创建 `collection_source=molizhishu` Run，等待 worker、分析、PDF 报告 |

模力指数 adapter smoke（默认 dry-run，不加 `--allow-paid-provider` 不会调用真实 API）：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\molizhishu_smoke_test.py
backend\.venv\Scripts\python.exe backend\scripts\molizhishu_smoke_test.py --allow-paid-provider
```

生产 preflight + 可选 API / 业务闭环 smoke：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py
backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py --api-preflight --base-url http://127.0.0.1:8000
backend\.venv\Scripts\python.exe backend\scripts\run_production_smoke_test.py --business-loop --allow-paid-provider --base-url http://127.0.0.1:8000
```

### 上线验收观测（Task O10）

`run_api_full_test.py` 默认在 API 全量联调前输出 release checklist：配置摘要、/ready、Dramatiq 三队列深度、ProviderBatch 与 Agent LLM 聚合指标。

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py --base-url http://127.0.0.1:8000
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py --release-checklist-only --base-url http://127.0.0.1:8000
```

全量联调脚本会在控制台输出 release checklist；如需保存报告，可按脚本参数或重定向另存到本地文件。

需先在 `.env` 配置 `MOLIZHISHU_ENABLED=true`、`MOLIZHISHU_API_TOKEN`；business-loop 另需 API/worker 已启动、Agent LLM 已配置。脚本输出已脱敏，不包含 token 或完整 prompt 回答正文。

上线前最小 smoke test：

1. `GET /api/geo-monitoring/health` 返回成功。
2. `GET /api/geo-monitoring/ready` 确认数据库和 Redis ready。
3. 创建项目、品牌、Prompt 集、平台配置。
4. `POST /api/geo-monitoring/runs` 创建运行。
5. Worker 日志能看到 `collection`、`analysis`、`report` 队列消费。
6. `POST /api/geo-monitoring/runs/{run_id}/reports` 生成 `pdf`。
7. `GET /api/geo-monitoring/reports/{report_id}/download` 能下载 PDF。

前端仅在明确改动 `frontend/` 时验证：

```powershell
cd frontend
npm test
npm run build
```

## 开发依据与文档入口

当前后端开发以接口缺口任务书、模力指数替换任务书和线上整改任务书为准；当前工作区可直接查阅的主要入口如下。若历史任务书文件不在本工作区，以当前代码、API 文档、操作手册和 AGENTS.md 的任务口径为准。

- 模力指数替换 Task 索引：[docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md](./docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md)
- 模力指数替换主任务书：[docs/Cursor模力指数API替换Aidso开发任务书.md](./docs/Cursor模力指数API替换Aidso开发任务书.md)
- 线上整改计划：[docs/superpowers/plans/2026-06-30-production-readiness-remediation.md](./docs/superpowers/plans/2026-06-30-production-readiness-remediation.md)
- 采集生命周期：[docs/采集任务生命周期说明.md](./docs/采集任务生命周期说明.md)
- 原型/API 映射：[docs/原型功能_API映射整合精简版.md](./docs/原型功能_API映射整合精简版.md)
- API 接口文档：[docs/API接口文档.md](./docs/API接口文档.md)
- 操作手册：[docs/AI应用监测平台操作手册.md](./docs/AI应用监测平台操作手册.md)
- 远程空库建表指南：[docs/PostgreSQL远程建表操作文档_无需部署代码.md](./docs/PostgreSQL远程建表操作文档_无需部署代码.md)
- 数据库 SQL 参考：[docs/geo-platform_schema.sql](./docs/geo-platform_schema.sql)
- ER 图：[docs/ER图.md](./docs/ER图.md)
- 代码审核要求：[docs/代码审核要求.md](./docs/代码审核要求.md)

MVP V2 相关任务属于已完成历史归档，不作为当前接口缺口、模力指数替换或生产整改开发依据。

## 开发注意事项

- 外部平台 API 和 LLM 调用不得运行在数据库长事务内。
- 确定性统计指标必须由 SQL/Python 计算，LLM 不得生成或修改统计口径。
- 平台采集失败要相互隔离，运行允许进入 `partial_success`。
- 趋势比较必须限定同一 Prompt 集版本。
- 新增 API 文件必须在 `backend/app/geo_monitoring/api/__init__.py` 注册 router。
- 新增或改造接口需同步更新 API 文档、原型映射文档、操作手册和必要的测试/联调脚本说明。
- 新增表、字段、索引、约束必须补 Alembic migration。
- 中文文档、源码、配置和命令输出统一按 UTF-8 处理，避免在 Windows 下写入乱码。
