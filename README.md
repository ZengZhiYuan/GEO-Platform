# GEO-Platform

GEO-Platform 是一个后端优先的 AI 应用监测平台。系统围绕监测项目、品牌、竞品、Prompt 集和 AI 平台配置工作，按 `Prompt x Platform` 发起采集，沉淀 AI 回答、引用源、品牌识别、指标快照、Agent 洞察，并输出 Markdown / HTML / PDF 诊断报告。

当前仓库处于“接口缺口补齐”阶段，开发重心在 `backend/`。`frontend/` 保留 React + Vite + Ant Design 管理端壳层，除非明确要求，一般不作为当前后端接口任务的改动范围。

- 当前业务 API 前缀：`/api/geo-monitoring`
- 兼容业务 API 前缀：`/api/v1/geo-monitoring`
- 当前 Alembic head：`geo_monitoring_0010`
- 默认配置文件：仓库根目录 `.env`
- 报告默认目录：本地 `./data/reports`，容器内 `/app/backend/data/reports`

## 当前能力

- 项目管理：项目列表、项目卡片概览、项目切换器、一步创建项目、创建向导草稿、暂停/恢复监测、删除前关联检查。
- 监测配置：目标品牌、竞品、品牌别名、核心词、Prompt 词库、Prompt 集版本、监测设置、平台端元数据与展示字典。
- AI 生成辅助：按项目生成品牌词候选、竞品候选、监测问题候选；候选结果不自动落库。
- 平台采集：支持豆包、通义千问、腾讯元宝、DeepSeek、Kimi 官方 Adapter，以及 `collection_source=molizhishu` 的模力指数第三方采集（11 个 `molizhishu_*` 平台端）。历史 Aidso 数据只读兼容，新建 Run 不再接受 `collection_source=aidso`。
- 异步运行：创建监测运行后生成 QueryTask，由 Dramatiq worker 消费 `collection`、`analysis`、`report` 队列。
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
| AI 生成 | `/projects/{project_id}/ai/brand-words:generate`、`/competitors:generate`、`/questions:generate` |
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
```

空库可以通过 Alembic 初始化到最新版本。`docs/geo-platform_schema.sql` 仅用于空库人工建表参考，已有数据的库不要重复执行全量建表 SQL。

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

## Docker Compose 部署

`docker-compose.yml` 只编排后端 API、Dramatiq worker 和 APScheduler scheduler，不启动 PostgreSQL、Redis、Nacos。三者连接信息从根目录 `.env` 读取。

发布顺序建议固定为：构建镜像，暂停后台任务，执行迁移，启动 worker / scheduler，最后启动或切换 API。

```bash
cd /opt/geo-platform
git pull origin main

docker compose config --quiet
docker compose build

docker compose stop worker scheduler
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head

docker compose up -d worker scheduler
docker compose up -d api
docker compose ps
```

常用运维命令：

```bash
docker compose logs -f --tail=100 api
docker compose logs -f --tail=100 worker
docker compose logs -f --tail=100 scheduler
docker compose restart worker
docker compose down
```

不要轻易执行 `docker compose down -v`，它会删除报告持久卷。容器访问宿主机中间件时，不要把 `DATABASE_URL` 或 `REDIS_URL` 的 host 写成 `localhost`，优先使用服务器内网 IP 或 `host.docker.internal`。

## 关键配置

| 配置 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接；pytest 可覆盖为 SQLite |
| `REDIS_URL` | Redis 连接；Dramatiq 与运行时标记共用 |
| `DRAMATIQ_BROKER` | 联调/生产使用 `redis`，测试覆盖为 `stub` |
| `API_PREFIX` | 默认 `/api` |
| `CORS_ALLOWED_ORIGINS` | 逗号分隔的允许跨域来源；为空时不开放跨域凭据 |
| `REPORT_STORAGE_DIR` | 报告文件目录 |
| `REPORT_PUBLIC_BASE_URL` | 可选报告公开访问基地址 |
| `SCHEDULER_ENABLED` | scheduler 进程开关 |
| `SCHEDULER_POLL_SECONDS` | 调度计划同步周期 |
| `NACOS_ENABLED` / `NACOS_*` | 可选配置中心连接 |
| `COLLECTION_*` | 采集超时、重试、并发、模力指数/Aidso 轮询上限、原始响应保存开关 |
| `DOUBAO_*` / `QWEN_*` / `YUANBAO_*` / `DEEPSEEK_*` / `KIMI_*` | 官方平台 Adapter 开关、模型、密钥或凭证 |
| `MOLIZHISHU_*` / `COLLECTION_MOLIZHISHU_*` | 模力指数 API 开关、Token、超时、轮询、截图默认、回调与区域列表 |
| `AIDSO_*` / `COLLECTION_AIDSO_MAX_POLLS` | **历史兼容**：仅用于续跑历史 pending Aidso 任务；新建 Run 不使用 |
| `AGENT_LLM_*` | Agent 语义分析使用的 OpenAI-compatible 或 DashScope LLM 配置 |

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

pytest 默认使用 SQLite、Stub broker、mock 平台 HTTP 和 Fake Agent LLM，不连接真实官方 API。真实平台 smoke test 需要在 `.env` 中显式启用对应平台并配置密钥。

模力指数真实接口 smoke（手动执行，可能产生费用，不写业务库）：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\molizhishu_smoke_test.py
```

需先在 `.env` 配置 `MOLIZHISHU_API_TOKEN`；无 token 时脚本会直接退出。

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

当前后端开发以接口缺口任务书与模力指数替换任务书为准：

- 模力指数替换 Task 索引：[docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md](./docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md)
- 模力指数设计决策：[docs/molizhishu-collection-source-design.md](./docs/molizhishu-collection-source-design.md)
- 采集生命周期：[docs/采集任务生命周期说明.md](./docs/采集任务生命周期说明.md)
- 接口缺口 Task 索引：[docs/Cursor接口缺口开发任务书_Task索引.md](./docs/Cursor接口缺口开发任务书_Task索引.md)
- 主任务书：[docs/Cursor接口缺口开发任务书.md](./docs/Cursor接口缺口开发任务书.md)
- 原型/API 映射：[docs/原型功能_API映射整合精简版.md](./docs/原型功能_API映射整合精简版.md)
- API 接口文档：[docs/API接口文档.md](./docs/API接口文档.md)
- API 测试文档：[docs/API测试文档.md](./docs/API测试文档.md)
- 操作手册：[docs/AI应用监测平台操作手册.md](./docs/AI应用监测平台操作手册.md)
- 数据库 SQL 参考：[docs/geo-platform_schema.sql](./docs/geo-platform_schema.sql)
- 代码审核要求：[docs/代码审核要求.md](./docs/代码审核要求.md)

`docs/AI应用监测_MVP_Cursor实施任务V2.md` 属于已完成历史归档，不作为当前接口缺口开发依据。

## 开发注意事项

- 外部平台 API 和 LLM 调用不得运行在数据库长事务内。
- 确定性统计指标必须由 SQL/Python 计算，LLM 不得生成或修改统计口径。
- 平台采集失败要相互隔离，运行允许进入 `partial_success`。
- 趋势比较必须限定同一 Prompt 集版本。
- 新增 API 文件必须在 `backend/app/geo_monitoring/api/__init__.py` 注册 router。
- 新增或改造接口需同步更新 API 文档、API 测试文档和原型映射文档。
- 新增表、字段、索引、约束必须补 Alembic migration。
- 中文文档、源码、配置和命令输出统一按 UTF-8 处理，避免在 Windows 下写入乱码。
