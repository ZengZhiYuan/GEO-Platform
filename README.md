# AI 应用监测平台

本项目用于配置监测项目、品牌、版本化 Prompt 和 AI 平台，创建监测运行，通过 Dramatiq Worker 并发调用各 AI 平台官方 API 采集回答，计算确定性指标，经 LangGraph Agent 生成语义分析与改进建议，并支持定时调度与 Markdown/HTML 报告生成。

## AI 应用监测 MVP V2 开发约束

> **适用范围：** 本版本只规划 `backend` 目录下的 MVP 功能实现。`frontend` 目录暂不纳入开发、测试和验收；后续需要前端时再单独拆分任务。

**目标：** 基于当前 GEO-Platform 后端基础设施，实现 AI 应用监测 MVP 的后端闭环：监测配置、官方 API 采集、确定性指标、Agent 洞察、调度、报告和后端部署验证。

**统一本地运行环境：** PostgreSQL、Redis、Nacos 已在服务器中安装部署，连接信息已写入本地 `.env`。后续本地运行、调试和联调统一使用 `.env` 中配置的这三项服务，不再要求本地 Docker 启动 PostgreSQL/Redis/Nacos。

**后端架构：** FastAPI + SQLAlchemy + Alembic 提供控制面和数据面 API；Dramatiq/Redis 承担采集（`collection`）、分析（`analysis`）、报告（`report`）三类异步任务；独立 APScheduler 进程扫描到期计划并创建运行；PostgreSQL 保存业务数据；Nacos 提供后端运行所需的外部配置/服务发现基础；报告写入本地目录或 Docker 持久卷。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy 2、Alembic、PostgreSQL 16、Redis 7、Dramatiq、APScheduler、LangGraph、Pydantic、Nacos、OpenAI-compatible LLM SDK、Jinja2、pytest、respx、freezegun。

## 当前能力

- 监测项目、品牌与品牌别名管理
- 核心词、Prompt 词库与监测设置（品牌/竞品/问题/平台一站式配置）
- Prompt 集版本管理、激活与内容摘要
- AI 平台参数管理与五个平台官方 API Adapter（豆包、千问、混元、DeepSeek、Kimi）
- 监测运行创建、Prompt×Platform 查询任务扇出、Dramatiq 异步入队采集
- 采集结果入库（回答、引用、规则优先品牌匹配）、运行聚合与失败重试/取消
- 采集完成后自动触发 LangGraph 分析（可手工重跑）；确定性指标快照与看板/趋势查询
- 监测调度 CRUD、启用/停用、立即触发；APScheduler 独立进程同步 cron 计划
- Markdown/HTML 报告生成与按 ID 下载
- PostgreSQL、Redis、Dramatiq、Docker Compose 三类进程部署
- React + Ant Design 监测管理端壳层（本阶段不扩展、不验收）

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

### 本地进程（联调）

除 API 外，完整闭环须另启 Worker 与（可选）Scheduler：

```powershell
# 采集 + 分析 + 报告 Worker（须与 API 共用同一份 .env，DRAMATIQ_BROKER=redis）
cd backend
.venv\Scripts\dramatiq.exe app.worker.actors.collection app.worker.actors.analysis app.worker.actors.report `
  -Q collection -Q analysis -Q report --processes 2 --threads 1

# 调度进程（.env 中 SCHEDULER_ENABLED=true 时）
.venv\Scripts\python.exe -m app.scheduler.main
```

`POST /api/geo-monitoring/runs` 创建运行后会自动将 QueryTask 入队到 `collection` 队列；全部采集任务进入终态后，若 `analysis_status=skipped`，会自动入队 `analysis` 队列。报告需通过 `POST /api/geo-monitoring/runs/{run_id}/reports` 触发。

### 测试环境与生产环境区分

pytest 在 `backend/tests/conftest.py` 中固定 `DRAMATIQ_BROKER=stub`，仅用于单元测试；本地联调与生产部署必须设为 `redis` 并确保 Redis 可达。

主要连接项：

- `DATABASE_URL`：服务器 PostgreSQL
- `REDIS_URL`：服务器 Redis（Dramatiq 与 Key 池冷却标记共用）
- `DRAMATIQ_BROKER`：异步任务 broker 类型；生产/联调为 `redis`，pytest 为 `stub`
- `NACOS_SERVER_ADDRESSES`、`NACOS_NAMESPACE`、`NACOS_GROUP`、`NACOS_CONFIG_DATA_ID`：Nacos 配置中心；需要时在 `.env` 中设置 `NACOS_ENABLED=true`
- `DOUBAO_*`、`QWEN_*`、`YUANBAO_*`、`DEEPSEEK_*`、`KIMI_*`：各平台官方 API 采集配置（默认关闭）
- `AGENT_LLM_*`：Agent 语义分析 LLM
- `SCHEDULER_*`：独立调度进程开关与时区
- `REPORT_STORAGE_DIR`：报告本地存储目录

接口前缀为 `/api/geo-monitoring`（兼容保留 `/api/v1/geo-monitoring`）。健康与就绪探针：

- `/api/geo-monitoring/health`：进程存活检查
- `/api/geo-monitoring/ready`：数据库与 Redis 连通性（启用 Nacos 时附带 Nacos 检查）
- 兼容保留 `/api/health` 与 `/api/ready`

跨域默认关闭；本地前后端联调时在 `.env` 设置 `CORS_ALLOWED_ORIGINS`（逗号分隔，例如 `http://localhost:5173`）。生产环境保持 `APP_DEBUG=false`，异常响应不返回堆栈。

结构化日志（JSON）统一包含 `request_id`、`run_id`、`task_id`、`platform_code`、`duration_ms` 等字段；API 响应头返回 `X-Request-ID` 与 `X-Response-Time-Ms`。

## Ubuntu 服务器部署（Docker Compose）

以下步骤适用于在 **Ubuntu 22.04 / 24.04** 上，使用 Docker Compose 部署 API、Worker、Scheduler 三类进程。PostgreSQL、Redis、Nacos 已在同一台或可达的服务器上安装时，只需在 `.env` 中填写连接信息；`docker-compose.yml` **不会**启动这些中间件。

### 1. 前置条件

在部署机上安装：

```bash
# 更新系统并安装基础工具
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl ca-certificates

# 安装 Docker Engine 与 Compose 插件（官方推荐方式）
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
# 重新登录 SSH 会话后，docker 命令才无需 sudo

docker --version
docker compose version
```

服务器侧请提前确认：

| 检查项 | 说明 |
| --- | --- |
| PostgreSQL | 已创建数据库（如 `geo_platform`），账号具备 DDL/DML 权限 |
| Redis | 已启动，Dramatiq 使用 `REDIS_URL` 可达 |
| Nacos | 若使用，端口与账号可用；否则 `.env` 设 `NACOS_ENABLED=false` |
| 防火墙 | 放行 API 端口（默认 `8000`）；PostgreSQL/Redis 仅内网访问 |
| 磁盘 | 报告卷 `geo_platform_reports_data` 有足够空间 |

### 2. 获取代码

```bash
# 示例：部署到 /opt/geo-platform（按实际路径调整）
sudo mkdir -p /opt/geo-platform
sudo chown "$USER:$USER" /opt/geo-platform
cd /opt/geo-platform

# 首次克隆（替换为实际仓库地址与分支）
git clone <your-repo-url> .
git checkout mvp-integration   # 或你的发布分支

# 后续更新
# git pull origin mvp-integration
```

### 3. 配置环境变量

```bash
cd /opt/geo-platform
cp .env.example .env
chmod 600 .env
nano .env   # 或 vim .env
```

生产环境至少修改以下项（**勿将真实密钥提交到 Git**）：

```env
APP_ENV=prod
APP_DEBUG=false
APP_TIMEZONE=Asia/Shanghai
BACKEND_PORT=8000

# 数据库与 Redis（见下方「容器访问宿主机中间件」说明）
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<db-host>:5432/geo_platform
REDIS_URL=redis://:<password>@<redis-host>:6379/0
DRAMATIQ_BROKER=redis

NACOS_ENABLED=false
# NACOS_ENABLED=true 时填写 NACOS_SERVER_ADDRESSES 等

# 按需启用平台与 Agent LLM
QWEN_ENABLED=true
QWEN_MODEL=<model-id>
QWEN_API_KEYS=<key1>,<key2>

AGENT_LLM_BASE_URL=<openai-compatible-url>
AGENT_LLM_API_KEY=<key>
AGENT_LLM_MODEL=<model>

# Worker 规模（可选，compose 会读取）
WORKER_PROCESSES=2
WORKER_THREADS=1
```

**容器访问宿主机中间件：** API/Worker 运行在 Docker 容器内，容器里的 `localhost` 指向容器自身，**不能**用来访问宿主机上的 PostgreSQL/Redis。若中间件与 Docker 在同一台 Ubuntu 上，请将 `<db-host>` / `<redis-host>` 设为：

- 服务器内网 IP（推荐，如 `10.x.x.x`），或
- Docker 网桥网关（常见为 `172.17.0.1`），或
- 在 `docker-compose.yml` 为各 service 增加 `extra_hosts: ["host.docker.internal:host-gateway"]` 后使用 `host.docker.internal`

修改 `.env` 后可用以下命令从**宿主机**验证连通性（需已安装 `psql` / `redis-cli`，或临时起一个容器测试）：

```bash
# 示例：用 curl 测 Redis（替换为 REDIS_URL 中的 host:port）
redis-cli -h <redis-host> -p 6379 -a '<password>' ping

# 示例：测 PostgreSQL
psql "postgresql://<user>:<password>@<db-host>:5432/geo_platform" -c "SELECT 1"
```

### 4. 构建镜像

在仓库根目录执行：

```bash
cd /opt/geo-platform
docker compose config --quiet    # 校验 compose 与 .env 语法
docker compose build             # 构建 geo-platform-backend:local
```

指定镜像标签（可选）：

```bash
export APP_IMAGE_TAG=20260622
docker compose build
```

### 5. 数据库迁移

**发布前请自行备份 PostgreSQL。** 在应用容器内执行 Alembic：

```bash
cd /opt/geo-platform

# 查看当前 revision
docker compose run --rm api python -m alembic -c backend/alembic.ini current

# 升级到最新（geo_monitoring_0001 → 0005）
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head

# 可选：仅预览 SQL，不执行
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head --sql
```

### 6. 启动服务

推荐顺序：**先 Worker 与 Scheduler，再 API**（与本地发布一致）。

```bash
cd /opt/geo-platform

docker compose up -d worker scheduler
docker compose up -d api

# 查看状态
docker compose ps
docker compose logs -f --tail=100 api
docker compose logs -f --tail=100 worker
docker compose logs -f --tail=100 scheduler
```

三个服务说明：

| 服务 | 作用 |
| --- | --- |
| `api` | FastAPI，对外暴露 `${BACKEND_PORT:-8000}` |
| `worker` | Dramatiq，消费 `collection` / `analysis` / `report` 队列 |
| `scheduler` | APScheduler，容器内 `SCHEDULER_ENABLED=true` |

报告文件写入命名卷 `geo_platform_reports_data`，挂载到容器内 `/app/backend/data/reports`。

### 7. 部署后验证

在服务器或能访问 API 的机器上：

```bash
# 健康检查（进程存活）
curl -s http://127.0.0.1:8000/api/geo-monitoring/health | jq .

# 就绪检查（数据库 + Redis；启用 Nacos 时一并检查）
curl -s http://127.0.0.1:8000/api/geo-monitoring/ready | jq .
# 若 status 为 not_ready，HTTP 状态码为 503，请检查 .env 中的连接地址与防火墙

# 查看容器健康状态
docker compose ps
```

建议 smoke test 流程：

1. `GET /api/geo-monitoring/ready` 返回 `ready`；
2. 通过 API 创建测试项目（见 `docs/API接口文档.md`）；
3. `POST /api/geo-monitoring/runs` 创建运行；
4. 确认 `worker` 日志中有采集任务消费记录；
5. 配置平台密钥后等待采集/分析完成；
6. `POST /api/geo-monitoring/runs/{run_id}/reports` 生成报告并 `GET .../download` 下载。

### 8. 日常运维命令

```bash
cd /opt/geo-platform

# 重启全部
docker compose restart

# 仅重启 Worker（例如修改平台 *_ENABLED 后）
docker compose restart worker

# 停止
docker compose down

# 停止并删除报告卷（危险：会删除已生成报告文件）
# docker compose down -v

# 拉代码、重建、滚动更新示例
git pull
docker compose build
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head
docker compose up -d worker scheduler
docker compose up -d api
```

### 9. 回滚与故障处理

- **应用回滚：** 切回上一版本代码/镜像标签后 `docker compose up -d`，**不要**自动 `alembic downgrade`，除非确认新 migration 无生产数据且旧版本不兼容。
- **平台 API 异常：** 在 `.env` 将对应 `*_ENABLED=false`，执行 `docker compose restart worker`。
- **任务长期 queued：** 检查 `DRAMATIQ_BROKER=redis`、`REDIS_URL` 可达，且 `worker` 容器在运行并监听三队列。
- **Nacos 不可用：** 若可接受本地配置，设 `NACOS_ENABLED=false` 后重启三个服务；若必须依赖 Nacos，保持 `NACOS_ENABLED=true`，ready 会 fail fast，应先恢复 Nacos。
- **报告丢失：** 勿随意 `docker volume rm geo_platform_reports_data`；升级前备份该卷或导出报告目录。

### 10.（可选）不用 Docker、直接在 Ubuntu 跑进程

若希望在宿主机用 Python 虚拟环境运行（调试或不用容器时）：

```bash
cd /opt/geo-platform/backend
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 仓库根目录 .env 会被自动加载（需在 backend 目录启动，或 export 环境变量）
export PYTHONPATH=/opt/geo-platform/backend

# 终端 1：API
uvicorn app.main:app --host 0.0.0.0 --port 8000

# 终端 2：Worker
dramatiq app.worker.actors.collection app.worker.actors.analysis app.worker.actors.report \
  -Q collection -Q analysis -Q report --processes 2 --threads 1

# 终端 3：Scheduler（.env 中 SCHEDULER_ENABLED=true）
python -m app.scheduler.main
```

生产环境仍推荐使用 Docker Compose，便于统一镜像、卷挂载与进程守护。

### 后端部署、发布与回滚（摘要）

后端部署使用同一个 `Dockerfile` 镜像分别启动 API、worker、scheduler 三类进程。PostgreSQL、Redis、Nacos 由根目录 `.env` 指向服务器服务，`docker-compose.yml` 不默认启动本地中间件。报告目录通过 `reports_data` 持久卷挂载到容器内 `/app/backend/data/reports`，容器镜像已创建非 root 用户并授予该目录写权限。

发布前由用户确认服务器 PostgreSQL、Redis、Nacos 的备份、账号、网络和权限，并备份数据库和报告目录。真实 API key、LLM key、报告存储目录和进程管理方式只写入 `.env`、Nacos 或服务器密钥管理系统，不写入仓库。

Windows 本地快速发布命令（与 Ubuntu 上 `docker compose` 等价）：

```powershell
docker compose config --quiet
docker compose build
docker compose run --rm api python -m alembic -c backend/alembic.ini upgrade head
docker compose up -d worker scheduler
docker compose up -d api
```

`docker-compose.yml` 中 Worker 默认监听 `collection`、`analysis`、`report` 三个队列；Scheduler 容器内设置 `SCHEDULER_ENABLED=true`。全量接口回归可使用 `backend/scripts/run_api_full_test.py`（需 API 与 Worker 已启动）。

回滚规则：应用回滚优先回滚镜像，不自动 downgrade 数据库；报告目录回滚只恢复元数据一致的备份；平台异常时设置 `*_ENABLED=false` 并重启 worker。

## 前端

`frontend` 目录当前仅保留已有管理端壳层。V2 后端 MVP 不开发、测试或验收前端；后续需要前端时再单独拆分任务。

## 中间件

PostgreSQL 用于业务数据，Redis 与 Dramatiq 用于采集、分析和报告异步任务，Nacos 用于后端运行所需的外部配置和服务发现基础。不要在文档、日志或提交中输出 `.env` 内的真实连接信息和密钥。

`/api/geo-monitoring/ready` 会检查数据库和 Redis 连通性，并且只返回脱敏后的连接目标摘要。启用 Nacos 时追加 Nacos 连通性检查。

## 数据库迁移

当前迁移链为 Alembic 增量 revision，基线为 `geo_monitoring_0001`，后续依次为 `0002_collection`、`0003_analysis_metrics`、`0004_schedule_report`、`0005_monitor_setup`。不要直接应用到包含旧迁移历史的数据库；应使用空数据库或明确清理后的开发环境。

```powershell
cd backend
.venv\Scripts\alembic.exe heads
.venv\Scripts\alembic.exe upgrade head --sql
.venv\Scripts\alembic.exe upgrade head
```

## 验证

```powershell
cd backend
.venv\Scripts\python.exe -m pytest -v
.venv\Scripts\python.exe -m pytest -q --cov=app --cov-report=term-missing
```

默认测试使用 **mock 平台 HTTP（respx）与 Fake Agent LLM**，不连接真实官方 API 或 Agent LLM。可选 smoke test（需用户确认 `.env` 中 PostgreSQL/Redis/Nacos 可达，并显式启用真实平台/LLM 配置）不在 CI 默认 pytest 范围内。

测试环境通过 `backend/tests/conftest.py` 注入独立配置并使用 SQLite/Stub broker 覆盖运行依赖，不直接连接共享服务器 PostgreSQL、Redis 或 Nacos。

平台密钥、Agent LLM 密钥与 Nacos 账号只通过 `.env` 或 Nacos 配置中心注入；Settings 对外只暴露脱敏摘要，不要在仓库、日志或普通数据库字段中保存明文密钥。

## 文档

- 技术权威文档：[`AI应用监测_技术开发文档.md`](./AI应用监测_技术开发文档.md)
- API 接口说明：[`docs/API接口文档.md`](./docs/API接口文档.md)
- MVP 开发任务书：[`docs/AI应用监测_MVP_Cursor实施任务V2.md`](./docs/AI应用监测_MVP_Cursor实施任务V2.md)
