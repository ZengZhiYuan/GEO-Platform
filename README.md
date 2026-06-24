# AI 应用监测平台

GEO-Platform 是一个后端优先的 AI 应用监测系统：配置项目、品牌、Prompt 和 AI 平台后，系统按 `Prompt × Platform` 发起采集，沉淀回答、引用源、品牌识别、指标快照和 Agent 洞察，最后导出 Markdown / HTML / PDF 诊断报告。

当前后端 Alembic head：`geo_monitoring_0007`。

## 现在能做什么

- 管理监测项目、目标品牌、竞品、品牌别名、核心词和 Prompt 集版本。
- 配置并调用豆包、通义千问、腾讯元宝、DeepSeek、Kimi 等官方平台 Adapter。
- 可在创建运行时选择 `collection_source=aidso`，通过 Aidso 采集 AI Web/App 端真实回答结果。
- 创建监测运行，自动扇出查询任务，由 Dramatiq Worker 异步采集。
- 汇总品牌提及率、首位率、Prompt 竞争力、引用来源、平台表现等指标。
- 采集完成后触发 LangGraph Agent 生成语义诊断和优化建议。
- 支持 APScheduler 定时运行。
- 支持通过接口生成并下载 `md`、`html`、`pdf` 三种报告。

接口统一前缀：`/api/geo-monitoring`。兼容保留：`/api/v1/geo-monitoring`。

## 架构要点

| 模块 | 技术/作用 |
| --- | --- |
| API | FastAPI + SQLAlchemy，提供监测配置、运行、指标、报告接口 |
| 数据库 | PostgreSQL，保存业务数据、运行结果和 Alembic 版本 |
| 队列 | Redis + Dramatiq，消费 `collection`、`analysis`、`report` 队列 |
| 调度 | APScheduler 独立进程，扫描 cron 计划并创建运行 |
| Agent | LangGraph + OpenAI-compatible LLM，生成诊断和建议 |
| 报告 | Jinja2 / Markdown / ReportLab，输出 Markdown、HTML、PDF |
| 配置 | 根目录 `.env` 为本地默认配置；可选接入 Nacos |

`frontend` 目录目前只保留已有管理端壳层，MVP V2 的开发、测试和验收重点在 `backend`。

## 本地开发启动

前提：PostgreSQL、Redis、Nacos 已在服务器或可访问环境中部署。本项目默认不要求本地 Docker 启动这些中间件。

```powershell
# 仓库根目录
python -m venv backend\.venv
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
backend\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
Copy-Item .env.example .env
```

编辑 `.env`，至少确认：

```env
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<pgsql-host>:5432/<database>
REDIS_URL=redis://:<password>@<redis-host>:6379/0
DRAMATIQ_BROKER=redis
NACOS_ENABLED=false
REPORT_STORAGE_DIR=./data/reports
```

执行数据库迁移：

```powershell
cd backend
.\.venv\Scripts\alembic.exe -c alembic.ini heads
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head
```

启动 API：

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

另开终端启动 Worker：

```powershell
cd backend
.\.venv\Scripts\dramatiq.exe app.worker.actors.collection app.worker.actors.analysis app.worker.actors.report `
  -Q collection -Q analysis -Q report --processes 2 --threads 1
```

需要定时任务时再启动 Scheduler：

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.scheduler.main
```

快速检查：

```powershell
curl http://127.0.0.1:8000/api/geo-monitoring/health
curl http://127.0.0.1:8000/api/geo-monitoring/ready
```

创建 Aidso 数据源运行示例：

```http
POST /api/geo-monitoring/runs
Content-Type: application/json

{
  "project_id": 1,
  "collection_source": "aidso",
  "aidso_thinking_enabled": false,
  "platform_codes": ["aidso_doubao_web", "aidso_doubao_app"]
}
```

## PDF 报告导出

生成报告：

```http
POST /api/geo-monitoring/runs/{run_id}/reports
Content-Type: application/json

{
  "formats": ["pdf"]
}
```

也可以一次生成多种格式：

```json
{
  "formats": ["md", "html", "pdf"]
}
```

下载报告：

```http
GET /api/geo-monitoring/reports/{report_id}/download
```

PDF 下载响应的 `Content-Type` 为 `application/pdf`。报告文件写入 `REPORT_STORAGE_DIR`，Docker 部署时写入持久卷 `geo_platform_reports_data`。


## Docker Compose 部署

`docker-compose.yml` 只编排 API、Worker、Scheduler，不启动 PostgreSQL、Redis、Nacos。三者连接信息从根目录 `.env` 读取。

### 后端部署、发布与回滚

发布前先备份数据库和报告目录，确认 `.env` 中 PostgreSQL、Redis、Nacos、平台 Key 和 Agent LLM Key 都指向目标环境。

先判断本次 `git pull` 拉到了什么：

| 变更类型 | 需要做什么 |
| --- | --- |
| 只改 README / docs / 注释 | 不需要重启服务；`git pull` 后即可 |
| 改了后端 Python 代码、模板、依赖或 Dockerfile | 需要 `docker compose build`，并重新创建 API、Worker、Scheduler |
| 新增/修改 Alembic migration | 需要执行 `alembic upgrade head` |
| 只改 `.env` 平台 Key 或开关 | 通常重启受影响服务；平台采集配置优先重启 `worker`，API 配置变更重启 `api` |

无需 `docker compose down`，不要删除 volume，也不要重启 PostgreSQL / Redis / Nacos。

```bash
# 1. 进入服务器项目目录，拉取最新代码
cd /opt/geo-platform
git pull origin main

# 2. 校验 compose 与 .env
docker compose config --quiet

# 3. 构建新镜像。后端代码、requirements.txt、Dockerfile 任一变化都要执行
docker compose build

# 4. 暂停后台任务，避免迁移期间旧 worker 继续消费任务
docker compose stop worker scheduler

# 5. 执行数据库迁移。若没有新 migration，此命令会显示 already up to date
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head

# 6. 先启动后台，再启动/切换 API
docker compose up -d worker scheduler
docker compose up -d api

# 7. 查看状态
docker compose ps
```

发布顺序固定为：先构建镜像，暂停后台任务，执行迁移，再启动 worker/scheduler，最后切换 API。上线 smoke test 至少覆盖 health、ready、创建测试项目、mock 运行和报告下载。

回滚时应用回滚优先回滚镜像，不自动 downgrade 数据库；只有确认迁移可逆且不会影响数据时才考虑数据库回退。某个平台异常时，把对应 `*_ENABLED=false` 后重启 worker；Nacos 不可用且允许本地配置兜底时，设置 `NACOS_ENABLED=false` 后重启服务。

容器访问宿主机中间件时，不要把 `DATABASE_URL` 或 `REDIS_URL` 的 host 写成 `localhost`。优先使用服务器内网 IP，或使用 compose 中已配置的 `host.docker.internal`。

常用命令：

```bash
docker compose logs -f --tail=100 api
docker compose logs -f --tail=100 worker
docker compose restart worker
docker compose down
```

不要轻易执行 `docker compose down -v`，它会删除报告持久卷。

## 关键配置

| 配置 | 说明 |
| --- | --- |
| `DATABASE_URL` | PostgreSQL 连接，生产/联调必须指向真实库 |
| `REDIS_URL` | Redis 连接，Dramatiq 和冷却标记共用 |
| `DRAMATIQ_BROKER` | 联调/生产用 `redis`，pytest 固定覆盖为 `stub` |
| `REPORT_STORAGE_DIR` | 报告文件目录；容器内为 `/app/backend/data/reports` |
| `SCHEDULER_ENABLED` | 本地 scheduler 进程需显式设为 `true` 才运行 |
| `NACOS_ENABLED` | 为 `true` 时必须配置 Nacos 连接信息 |
| `DOUBAO_*` / `QWEN_*` / `YUANBAO_*` / `DEEPSEEK_*` / `KIMI_*` | 各平台采集开关、模型和密钥 |
| `AIDSO_ENABLED` / `AIDSO_BASE_URL` / `AIDSO_API_TOKEN` | Aidso 第三方数据源开关、地址和 token；深度思考由创建运行入参控制 |
| `AGENT_LLM_*` | Agent 语义分析使用的 OpenAI-compatible LLM |

真实账号、密码、API Key 只写入 `.env`、Nacos 或服务器密钥管理系统，不写入仓库。

## 测试与验收

后端测试必须使用 `backend/.venv`：

```powershell
backend\.venv\Scripts\python.exe -m pytest backend\tests -q
```

接口联调脚本：

```powershell
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py --base-url http://127.0.0.1:8000
```

测试默认使用 SQLite、Stub broker、mock 平台 HTTP 和 Fake Agent LLM，不连接真实官方 API。真实平台 smoke test 需要你在 `.env` 中显式启用对应平台和密钥。

上线前最小验收：

1. `GET /api/geo-monitoring/health` 返回成功。
2. `GET /api/geo-monitoring/ready` 确认数据库和 Redis ready。
3. 创建项目、品牌、Prompt 集、平台配置。
4. `POST /api/geo-monitoring/runs` 创建运行。
5. Worker 日志能看到 `collection`、`analysis`、`report` 队列消费。
6. `POST /api/geo-monitoring/runs/{run_id}/reports` 生成 `pdf`。
7. `GET /api/geo-monitoring/reports/{report_id}/download` 能下载 PDF。

## 数据库版本

当前迁移链：

```text
geo_monitoring_0001
  -> geo_monitoring_0002
  -> geo_monitoring_0003
  -> geo_monitoring_0004
  -> geo_monitoring_0005
  -> geo_monitoring_0006
  -> geo_monitoring_0007
```

查看版本：

```sql
SELECT version_num FROM public.alembic_version;
```

空库初始化请使用 [docs/geo-platform_schema.sql](./docs/geo-platform_schema.sql)。已有数据的库不要重复执行全量建表 SQL。
生产库升级前先备份。应用回滚优先回滚镜像/代码，不要自动 downgrade 数据库，除非已经确认迁移可逆且不会影响现有业务数据。

## 文档入口

- API 接口说明：[docs/API接口文档.md](./docs/API接口文档.md)
- API 测试说明：[docs/API测试文档.md](./docs/API测试文档.md)
- 操作手册：[docs/AI应用监测平台操作手册.md](./docs/AI应用监测平台操作手册.md)
- PostgreSQL Navicat 建表：[docs/PostgreSQL远程建表操作文档_无需部署代码.md](./docs/PostgreSQL远程建表操作文档_无需部署代码.md)
- 当前 schema SQL：[docs/geo-platform_schema.sql](./docs/geo-platform_schema.sql)
