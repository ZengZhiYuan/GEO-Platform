# AGENTS.md

## 项目背景

GEO-Platform 是后端优先的 AI 应用监测平台：配置监测项目、品牌、Prompt 和 AI 平台后，系统按 `Prompt × Platform` 发起采集，沉淀回答、引用源、品牌识别、指标快照和 Agent 洞察，并导出 Markdown / HTML / PDF 诊断报告。

当前阶段后端开发以接口缺口任务书为准，补齐原型六页所需的页面级聚合、字典、AI 生成、导出和指标口径等接口。

- **主任务书：** `docs/Cursor接口缺口开发任务书.md`
- **事实来源：** `docs/原型功能_API映射整合精简版.md`
- **默认入口：** 凡涉及当前后端开发、原型页面对接、接口缺口、页面级聚合、字典、AI 生成、导出、指标口径等需求，默认以 `docs/Cursor接口缺口开发任务书.md` 为准；不要切回 MVP V2 任务书作为开发依据。
- **默认授权：** 用户下达 Task 开发指令时，默认授权按任务书执行，无需每次重复「先读任务文档」。
- **冲突处理：** 用户当次指令 > 本文件 / `.cursor/rules/*` / `CLAUDE.md` > `docs/Cursor接口缺口开发任务书.md` > `docs/原型功能_API映射整合精简版.md` > Superpowers skills。
- **历史归档：** `docs/AI应用监测_MVP_Cursor实施任务V2.md` 中的任务已完成。当前开发任务中忽略该任务书，不再按 `V2 Task N` 开展新开发；仅当用户明确要求追溯历史实现、核对旧任务背景或审计已完成工作时，才局部查阅历史资料。

## 技术栈

- **后端：** Python、FastAPI、Pydantic / Pydantic Settings、SQLAlchemy 2.0、Alembic、PostgreSQL、Redis、Dramatiq、APScheduler、LangGraph、OpenAI-compatible LLM、httpx、tenacity、Jinja2、Markdown、ReportLab、可选 Nacos。
- **前端：** React 18、TypeScript、Vite、Ant Design、React Router、Axios。当前接口缺口阶段默认只做 `backend`，除非用户明确要求前端改动。
- **部署：** 同一个 `Dockerfile` 镜像启动 API、worker、scheduler；`docker-compose.yml` 只编排后端进程，PostgreSQL、Redis、Nacos 默认由 `.env` 指向外部服务。
- **报告与数据目录：** 报告默认写入 `REPORT_STORAGE_DIR`，本地通常为 `data/reports`，容器内为 `/app/backend/data/reports`。

## 目录结构

- `backend/app/main.py`：FastAPI 应用入口。
- `backend/app/core/`：配置、数据库、统一响应、健康检查、可观测性等基础设施。
- `backend/app/models/`：通用 ORM 基类与模型导出。
- `backend/app/geo_monitoring/`：AI 应用监测业务主域。
- `backend/app/geo_monitoring/api/`：后端接口路由；新增 API 文件必须在 `backend/app/geo_monitoring/api/__init__.py` 注册 router。
- `backend/app/geo_monitoring/services/`：业务编排与事务边界。
- `backend/app/geo_monitoring/repositories/`：数据库查询与持久化封装。
- `backend/app/geo_monitoring/schemas.py`：Pydantic 入参与出参模型。
- `backend/app/geo_monitoring/models.py`：监测业务 ORM 模型。
- `backend/app/geo_monitoring/agents/`：LangGraph Agent 分析链路。
- `backend/app/geo_monitoring/reports/`：报告生成、存储与下载。
- `backend/app/worker/`、`backend/app/workers/`：Dramatiq worker 入口与平台适配。
- `backend/app/scheduler/`：APScheduler 调度进程。
- `backend/alembic/`：数据库迁移脚本；当前后端 Alembic head 以 README 和迁移目录为准。
- `backend/tests/`：后端测试；接口缺口任务默认优先补 `backend/tests/geo_monitoring/`。
- `backend/scripts/`：API 全量/专项联调脚本。
- `frontend/`：管理端壳层与前端页面。
- `docs/`：任务书、API 文档、测试文档、原型映射、数据库说明、审核要求。
- `.cursor/rules/`：Cursor / Codex 执行规则；本文件与其中规则共同约束开发。
- `.codegraph/`：CodeGraph 本地索引；不要手工编辑索引数据库。

## 开发规范

### 任务读取

1. 先读 `docs/Cursor接口缺口开发任务书_Task索引.md`（执行规则摘要 + Task 行号目录 + 原型文档章节映射）。
2. 再按索引行号局部读取任务书对应 Task 章节；禁止通读全文。
3. 按 Task 局部读取 `docs/原型功能_API映射整合精简版.md` 对应章节。
4. 新增/改造接口前读 `docs/API接口文档.md`；写测试前读 `docs/API测试文档.md`。
5. 细则见 `.cursor/rules/cursor-api-gap-tasks.mdc`。

用户推荐指令格式：`执行 Task P0-1：<简述>`（或 `执行 Task P1-2：…` 等）。

### Superpowers 开发技能

凡涉及**代码开发**（新功能、行为变更、重构、修 bug、补测试、迁移），Agent 必须启用 Superpowers 插件 skills，细则见 `.cursor/rules/superpowers-dev-workflow.mdc`。

最低要求：

1. `using-superpowers`：会话开始或接到开发任务后，先 Read 该 skill，再决定后续 skills。
2. `test-driven-development`：写/改实现前，先写失败测试（与任务书「测试先行」一致）。
3. `verification-before-completion`：声称完成前，必须运行验收命令并用输出证明通过。

常见扩展：

| 场景 | Skill |
|------|-------|
| 新功能 / 行为变更 | `brainstorming` |
| 多步骤实施 | `writing-plans` → `executing-plans` |
| bug / 测试失败 | `systematic-debugging` |
| 并行独立子任务 | `dispatching-parallel-agents` |
| 大步骤完成 / 合并前 | `requesting-code-review` |
| 分支收尾 | `finishing-a-development-branch` |

### 后端工程规则

- 采集、分析、报告分阶段解耦。
- 外部 API 和 LLM 调用不得运行在数据库长事务内。
- 数值指标必须由 SQL/Python 确定性计算；LLM 不得生成或修改确定性统计指标。
- 平台失败相互隔离，运行可进入 `partial_success`。
- 趋势比较必须限定同一 Prompt 集版本。
- 聚合接口避免 N+1；优先复用现有表与分析 JSON，不优先新增大表。
- 真实账号、密码、API Key 只写入 `.env`、Nacos 或服务器密钥管理系统，不写入仓库。

### UTF-8 编码

本仓库文档、源码、配置与命令输出一律以 UTF-8 为默认编码。读取文档或查看运行日志时，必须显式按 UTF-8 处理，避免在中文 Windows 下出现乱码。

- Shell 中读取文本：`Get-Content -Encoding UTF8 <path>`，或 `[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)`。
- Python 读写文件必须 `encoding="utf-8"`；写入 Markdown、配置、日志文件时同样使用 UTF-8。
- 执行可能输出中文的命令前设置：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

- Git 日志/差异含中文时，在同一 UTF-8 终端会话中执行，或配合 `git -c core.quotepath=false` 查看路径。
- 发现乱码时，先检查读取/输出编码，不要将乱码文本写回仓库。

### 后端虚拟环境

- 本项目后端唯一指定虚拟环境为 `backend/.venv`。
- Codex 执行任何后端 Python、pytest、alembic、uvicorn、dramatiq、pip 相关命令前，必须使用该虚拟环境。
- Windows / PowerShell 中优先使用显式解释器路径，例如 `backend\.venv\Scripts\python.exe -m pytest -v backend/tests`。
- 如果命令需要在 `backend/` 目录下执行，则先切换工作目录到 `backend`，再使用 `.venv\Scripts\python.exe` 或 `.venv\Scripts\alembic.exe`。
- 不要写成裸 `python`、`pip`、`pytest`、`alembic`，除非已经明确激活了 `backend/.venv` 且当前 shell 可验证 `python` 来自该目录。

### 代码审核

当用户要求对 Cursor 完成的代码、本轮开发改动、当前分支差异或未提交改动进行代码审核时，默认按 `docs/代码审核要求.md` 执行，细则见 `.cursor/rules/code-review-workflow.mdc`。

- 默认先读 `docs/代码审核要求.md`，再用 `git status`、`git diff`、按需 `git diff main...HEAD` 确认变更范围。
- 审核重点覆盖规范性、准确性、功能完成度、需求符合度、可维护性、安全性、稳定性、性能与测试完整性；无法确认的结论标注“需要人工确认”。
- 审核任务默认只出审查报告，不自动修改代码、不自动提交、不自动合并，除非用户明确要求进入修复阶段。

### CodeGraph

本项目已配置 CodeGraph MCP（`codegraph_*` 工具），适合结构查询。

- 架构或「X 如何工作」：先 `codegraph_context`，至多一次 `codegraph_explore`。
- 特定调用链：用 `codegraph_trace`，不要用 grep 拼路径。
- 按符号名查找：用 `codegraph_search`，不要先 grep。
- 不要对多个符号循环 `codegraph_node`；用 `codegraph_explore`。
- 查询前若刚改过代码，应先 `codegraph sync`，再调用 MCP 工具（或 CLI：`codegraph query`、`codegraph explore`）。

## 接口规范

- 统一接口前缀：`/api/geo-monitoring`；兼容保留：`/api/v1/geo-monitoring`。
- 普通接口返回 `{ "code": 0, "message": "success", "data": {} }`。
- 分页接口的 `data` 包含 `items`、`total`、`page`、`page_size`。
- 列表接口支持 `page` / `page_size`；多页面复用 `run_id`、`platform_codes`、`start_at` / `end_at`、`keyword`。
- 比率与平均排名用 decimal 字符串；无分母返回 `null`。
- 新增 API 文件须在 `backend/app/geo_monitoring/api/__init__.py` 注册 router。
- 接口入参/出参以 Pydantic schema 表达，错误响应和错误码同步写入 API 文档。
- 新增或改造接口前局部读取 `docs/API接口文档.md` 相关章节；写测试前读取 `docs/API测试文档.md` 约定。
- 每个接口缺口 Task 完成后，必须更新 `docs/API接口文档.md`、`docs/API测试文档.md`，并在 `docs/原型功能_API映射整合精简版.md` 标注已覆盖缺口。

## 数据库规范

- 主数据库为 PostgreSQL；pytest 默认使用 SQLite、Stub broker、mock 平台 HTTP 和 Fake Agent LLM，不连接真实官方 API。
- 数据库连接来自 `DATABASE_URL`；Alembic 从 `app.core.config.settings.DATABASE_URL` 读取连接，不在 `backend/alembic.ini` 硬编码数据库地址。
- ORM 统一使用 SQLAlchemy 2.0 风格；业务模型继承 `app.models.base.BaseModel`，公共字段由基类提供。
- 所有新增表、字段、索引、约束和数据结构变化都必须有 Alembic migration。
- 已有数据的库不要重复执行全量建表 SQL；空库初始化才可使用 `docs/geo-platform_schema.sql`。
- 生产库升级前必须备份数据库和报告目录。
- 发布顺序固定为：先构建镜像，暂停后台任务，执行 `alembic upgrade head`，再启动 worker / scheduler，最后切换 API。
- 应用回滚优先回滚镜像/代码，不自动 downgrade 数据库；只有确认迁移可逆且不会影响数据时才考虑数据库回退。
- 容器访问宿主机中间件时，不要把 `DATABASE_URL` 或 `REDIS_URL` 的 host 写成 `localhost`，优先使用服务器内网 IP 或 `host.docker.internal`。

## 测试命令

后端命令必须使用 `backend/.venv`。Windows / PowerShell 下如命令可能输出中文，先设置 UTF-8 终端变量。

```powershell
# 后端完整测试
backend\.venv\Scripts\python.exe -m pytest -v backend/tests

# 当前接口缺口任务常用范围
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring

# 静默快速回归
backend\.venv\Scripts\python.exe -m pytest backend\tests -q

# Alembic 检查
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head --sql

# API 全量联调脚本（需本地 API 已启动）
backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py --base-url http://127.0.0.1:8000
```

如已切换到 `backend/` 目录：

```powershell
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\alembic.exe -c alembic.ini heads
.\.venv\Scripts\alembic.exe -c alembic.ini upgrade head --sql
```

前端仅在用户明确要求或改动了 `frontend/` 时验证：

```powershell
cd frontend
npm test
npm run build
```

### Windows 报告存储测试权限说明

在 Windows / Codex 沙箱下，报告相关测试会执行 `os.replace()`、`unlink()` 等文件原子替换和删除操作，普通沙箱可能报 `PermissionError`。

当运行以下范围时：

- `backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring`
- `backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\reports`
- 任何包含报告生成、报告下载、报告存储的测试

Codex 应优先使用工作区内临时目录，并申请提权执行：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring --basetemp .pytest-tmp
```

执行时使用 `sandbox_permissions=require_escalated`，理由为：“报告存储测试需要在工作区临时目录内执行文件原子替换和删除，普通沙箱在 Windows 下可能拒绝访问。”

测试结束后清理 `.pytest-tmp`；如普通权限清理失败，可在确认路径位于当前 workspace 后提权清理。

## 分支规范

- 当前工作区可能存在用户或其他 Agent 的未提交改动；不要还原、覆盖、格式化或清理与本任务无关的改动。
- 不主动创建、切换、合并、推送分支，除非用户明确要求。
- 用户要求创建 Codex 工作分支时，默认使用 `codex/<short-topic>` 前缀；若用户指定分支名或项目已有明确分支策略，则按用户指令执行。
- 常规开发基线默认以 `main` 为主干；审查分支差异时按需使用 `git diff main...HEAD`。
- 不自动提交、不自动合并、不自动推送、不自动创建 PR，除非用户明确要求。
- 禁止使用 `git reset --hard`、`git checkout --`、`git restore` 等会丢弃改动的命令，除非用户明确指定目标且已确认不会影响他人改动。

## 禁止事项

- 禁止把 MVP V2 任务书作为当前接口缺口开发依据；旧版原型映射文档与 MVP V2 任务书仅作历史参考。
- 禁止一次性通读大型任务书；必须按索引和行号局部读取。
- 禁止使用未指定编码的 `type`、`cat`、`Get-Content` 读取中文文档或日志。
- 禁止将乱码文本写回仓库。
- 禁止使用系统 Python、其他项目虚拟环境或 Conda 环境执行后端命令。
- 禁止在仓库、日志、普通数据库配置字段中保存明文平台密钥、数据库密码、API token。
- 禁止恢复已移除的内容生产业务域。
- 禁止在数据库事务中调用外部 AI 平台或 LLM。
- 禁止让 LLM 生成或修改确定性统计指标。
- 禁止无测试、无迁移或无法验证的业务变更。
- 禁止在未确认影响前执行 `docker compose down -v`，它会删除报告持久卷。
- 禁止手工编辑 `.codegraph/` 索引数据库。

## 验收标准

每个开发 Task 完成前必须满足：

1. 已按任务索引局部读取当前 Task、对应原型章节、API 文档和测试文档。
2. 代码任务已按 Superpowers 工作流执行：`using-superpowers`、`test-driven-development`、`verification-before-completion`。
3. 已先写失败测试，并确认失败原因对应本次需求；纯文档任务可跳过。
4. 实现范围与任务书一致，不引入无关重构或额外行为。
5. 已运行任务书指定验收命令和必要的回归测试，并在汇报中说明命令与结果。
6. 新增/改造接口已同步 `docs/API接口文档.md`、`docs/API测试文档.md`，并在 `docs/原型功能_API映射整合精简版.md` 标注已覆盖缺口。
7. 数据库结构变化已补 Alembic migration，并通过 `alembic heads`、`alembic upgrade head --sql` 等验证。
8. 改动了 `backend/` 等源码且验收通过后，在仓库根目录执行：

```powershell
codegraph status
codegraph sync
codegraph status
```

如无 `.codegraph/` 或 `status` 提示未初始化，先 `codegraph init`，再 `codegraph sync`。索引失败不推翻已通过测试，但须在 Task 汇报中说明。文档-only 或无代码改动可跳过。

上线前最小验收还应覆盖：

1. `GET /api/geo-monitoring/health` 返回成功。
2. `GET /api/geo-monitoring/ready` 确认数据库和 Redis ready。
3. 创建项目、品牌、Prompt 集、平台配置。
4. `POST /api/geo-monitoring/runs` 创建运行。
5. Worker 日志能看到 `collection`、`analysis`、`report` 队列消费。
6. `POST /api/geo-monitoring/runs/{run_id}/reports` 生成 `pdf`。
7. `GET /api/geo-monitoring/reports/{report_id}/download` 能下载 PDF。

