# AI 应用监测完整 MVP Cursor 实施任务

> **For agentic workers:** 按本文自上而下执行。主 Agent 负责数据库迁移、公共契约、集成和最终验收；并行任务使用独立 worktree 和独立 Cursor Agent/Subagent，完成后先审查再合并。

**目标：** 基于当前 GEO-Platform 基础设施，实现从监测配置、官方 API 采集、指标分析、Agent 洞察、趋势看板、定时调度到报告导出的完整 AI 应用监测 MVP。

**架构：** FastAPI + SQLAlchemy + Alembic 提供控制面和数据面 API；Dramatiq/Redis 承担采集、分析和报告异步任务；独立 APScheduler 进程创建定时运行；PostgreSQL 保存业务数据；报告写入本地目录；前端沿用 React/Vite/Ant Design。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy 2、Alembic、PostgreSQL 16、Redis 7、Dramatiq、APScheduler、LangGraph、Pydantic、React 18、TypeScript、Vite、Ant Design、Vitest、Playwright。

---

## 1. 执行规则

### 1.1 标记说明

- `[S]`：串行任务，必须等待前置任务完成并合并。
- `[P]`：可并行任务，可分配给独立 Cursor Agent/Subagent。
- `[B]`：阻塞点，未通过验收不得开始依赖它的任务。
- `[M]`：只能由主 Agent 修改或合并，避免公共文件冲突。

### 1.2 Cursor 工作方式

1. 主 Agent 始终在集成分支工作，负责拆任务、维护契约和执行全量验证。
2. 每个并行任务创建独立 worktree，不让多个 Agent 同时修改同一目录。
3. 给 Subagent 的提示词必须包含：任务编号、允许修改的文件、禁止修改的文件、验收命令、提交信息。
4. Subagent 完成后先运行局部测试并提交；主 Agent使用 `git show --stat` 和 `git diff <base>...<branch>` 审查。
5. 公共文件由主 Agent维护：Alembic 迁移链、`backend/app/core/config.py`、公共 Schema、前端路由、依赖锁文件、Docker Compose。
6. 每次只合并一个公共契约变更；合并后重新基线化后续并行分支。

推荐目录：

```powershell
New-Item -ItemType Directory -Force .worktrees | Out-Null
git worktree add .worktrees/mvp-integration -b feature/ai-monitoring-mvp
```

并行分支示例：

```powershell
git worktree add .worktrees/adapter-doubao -b feature/adapter-doubao feature/ai-monitoring-mvp
git worktree add .worktrees/adapter-qwen -b feature/adapter-qwen feature/ai-monitoring-mvp
git worktree add .worktrees/frontend-runs -b feature/frontend-runs feature/ai-monitoring-mvp
```

### 1.3 Cursor Subagent 提示词模板

```text
执行《docs/AI应用监测_MVP_Cursor实施任务.md》的 Task X。
基线分支：feature/ai-monitoring-mvp。
只允许修改：<文件或目录列表>。
禁止修改：Alembic 迁移链、公共配置、锁文件以及任务范围外文件。
先阅读根目录 AI应用监测_技术开发文档.md 和相关现有代码。
按测试先行方式实现，运行任务列出的验证命令。
完成后提交，提交信息使用：<commit message>。
输出：改动摘要、测试结果、遗留风险、commit hash。
```

### 1.4 总体依赖与并行窗口

```text
Task 0
  -> Task 1 [数据库采集迁移，串行阻塞]
  -> Task 2 [采集模型与公共契约，串行阻塞]
  -> Task 3 [环境变量与依赖，串行阻塞]
      -> Task 4 [适配器基础设施]
          -> Task 5A/5B/5C/5D/5E [五个平台适配器，并行]
          -> Task 6 [采集 Actor]
              -> Task 7 [运行聚合与 API]
  -> Task 8 [分析迁移，串行阻塞]
      -> Task 9 [确定性指标]
      -> Task 10 [LLM 公共能力]
          -> Task 11 [LangGraph Agent]
              -> Task 12 [分析 Actor/API]
  -> Task 13 [调度与报告迁移，串行阻塞]
      -> Task 14 [调度器]
      -> Task 15 [报告]
  -> Task 16 [前端公共基础]
      -> Task 17A/17B/17C/17D [页面域，并行]
  -> Task 18 [端到端、可观测性与安全]
  -> Task 19 [部署、发布与回滚]
```

数据库迁移 Task 1、8、13 必须在同一集成分支按顺序创建。禁止在并行 worktree 中各自生成 Alembic revision。

---

## 2. Task 0：基线确认与本地环境 `[S][B][M]`

**目标：** 固化重构后的当前基线，确认开发工具和基础服务可用。

**修改文件：** 无；只有依赖安装产生的被忽略文件。

### 步骤

- [ ] 确认工作区没有非本任务改动：

```powershell
git status --short
git branch --show-current
git log -5 --oneline
```

- [ ] 创建并进入集成 worktree：

```powershell
git worktree add .worktrees/mvp-integration -b feature/ai-monitoring-mvp
Set-Location .worktrees/mvp-integration
```

- [ ] 创建 Python 虚拟环境并安装依赖：

```powershell
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install --upgrade pip
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

- [ ] 安装前端依赖：

```powershell
npm --prefix frontend install
```

- [ ] 复制本地环境文件，禁止提交 `.env`：

```powershell
Copy-Item .env.example .env
```

- [ ] 启动 PostgreSQL 和 Redis：

```powershell
docker compose up -d postgres redis
docker compose ps
```

- [ ] 执行当前迁移和基线测试：

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m pytest backend/tests -q
npm --prefix frontend run build
```

### 完成标准

- PostgreSQL、Redis 状态为 healthy。
- Alembic head 为 `geo_monitoring_0001`。
- 后端测试和前端构建全部通过。
- `.env`、`.venv`、`node_modules` 未出现在 `git status`。

---

## 3. Task 1：创建采集域库表 `[S][B][M]`

**目标：** 通过增量迁移增加答案、引用、品牌识别结果，并扩展运行状态信息。

**修改文件：**

- `backend/alembic/versions/*_geo_monitoring_0002_collection.py`
- `backend/tests/test_migrations.py`

### 迁移内容

- [ ] `geo_monitor_run` 增加：`trigger_type`、`triggered_by`、`total_tasks`、`succeeded_tasks`、`failed_tasks`、`cancelled_tasks`、`started_at`、`completed_at`、`error_summary`。
- [ ] `geo_query_task` 增加：`attempt_count`、`max_attempts`、`queued_at`、`started_at`、`completed_at`、`last_error_code`、`last_error_message`、`provider_request_id`。
- [ ] 创建 `geo_answer`：任务、平台、Prompt、原始文本、规范化文本、模型名、token 用量、耗时、采集时间和原始响应 JSON。
- [ ] 创建 `geo_answer_citation`：答案、序号、标题、URL、域名、来源类型、引用文本。
- [ ] 创建 `geo_answer_brand_result`：答案、品牌、是否提及、提及次数、首次位置、情感、上下文 JSON。
- [ ] 为任务状态、运行状态、答案平台与时间、引用域名、品牌结果建立索引和唯一约束。
- [ ] `downgrade()` 必须完整逆序删除新增对象。

### 实施步骤

1. 先写迁移测试，验证从 `base -> 0001 -> 0002 -> 0001 -> 0002` 可重复执行。
2. 运行 revision 命令，只生成一个迁移：

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini revision -m "add collection domain"
```

3. 手工审查字段类型、外键删除策略、索引名和 downgrade，不直接接受自动生成结果。
4. 对干净数据库执行升级和回退：

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini downgrade geo_monitoring_0001
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
```

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/test_migrations.py -q
```

**提交信息：** `feat(db): add monitoring collection schema`

---

## 4. Task 2：采集模型、Schema 与仓储契约 `[S][B][M]`

**目标：** 让 ORM、API Schema 和服务层完整覆盖 Task 1 数据结构，并拆分现有过于集中的模块。

**修改文件：**

- `backend/app/geo_monitoring/models.py`
- `backend/app/geo_monitoring/schemas.py`
- `backend/app/geo_monitoring/repositories/`
- `backend/app/geo_monitoring/services/runs.py`
- `backend/app/geo_monitoring/api/`
- `backend/tests/geo_monitoring/`

### 步骤

- [ ] 为新增表和字段添加 SQLAlchemy 模型、关系、枚举和约束镜像。
- [ ] 增加 `AnswerRead`、`CitationRead`、`BrandResultRead`、`RunDetailRead`、分页响应 Schema。
- [ ] 将数据库读写集中到 `repositories/`，service 不直接散落 SQLAlchemy 查询。
- [ ] 将单文件 API 拆为 `projects.py`、`brands.py`、`prompts.py`、`platforms.py`、`runs.py`、`answers.py`，保留 `/api/v1` 路径兼容。
- [ ] 保留当前“创建运行后生成 Prompt × Platform 任务”的语义，并在同一事务写入任务总数。
- [ ] 增加运行详情、任务列表、答案详情分页接口。
- [ ] 使用数据库唯一约束和 service 校验保证幂等，不依赖前端去重。

### 测试先行

- 创建运行时无 Prompt 或无启用平台应返回 409。
- 重复创建同一答案不得产生两条记录。
- 删除被运行引用的配置时返回明确的 409，而非数据库 500。
- 分页参数越界返回 422。
- 现有 17 个 path template 不得丢失。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring -q
backend/.venv/Scripts/python -m pytest backend/tests/test_api_contract.py -q
```

**提交信息：** `refactor(api): introduce monitoring collection contracts`

---

## 5. Task 3：依赖与环境变量契约 `[S][B][M]`

**目标：** 一次性定义后端采集、Agent、调度和报告所需配置，所有密钥只从环境变量读取。

**修改文件：**

- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/app/core/config.py`
- `.env.example`
- `docker-compose.yml`
- `backend/tests/test_config.py`

### 依赖

- [ ] 运行依赖加入 `httpx`、`tenacity`、`apscheduler`、`langgraph`、`openai`、`jinja2`、`markdown`。
- [ ] 开发依赖加入 `respx`、`freezegun`、`pytest-cov`。
- [ ] 固定兼容版本范围，并运行 `pip check`。

### `.env.example` 必须包含

```dotenv
APP_ENV=dev
DEBUG=false
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/geo_platform
REDIS_URL=redis://localhost:6379/0

COLLECTION_REQUEST_TIMEOUT_SECONDS=60
COLLECTION_MAX_ATTEMPTS=3
COLLECTION_RETRY_BASE_SECONDS=2
COLLECTION_MAX_CONCURRENCY=10
COLLECTION_RAW_RESPONSE_ENABLED=true

DOUBAO_ENABLED=false
DOUBAO_BASE_URL=https://ark.cn-beijing.volces.com/api/v3
DOUBAO_MODEL=
DOUBAO_API_KEYS=

QWEN_ENABLED=false
QWEN_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
QWEN_MODEL=
QWEN_API_KEYS=

YUANBAO_ENABLED=false
YUANBAO_BASE_URL=https://api.hunyuan.cloud.tencent.com/v1
YUANBAO_MODEL=
YUANBAO_CREDENTIALS_JSON=[]

DEEPSEEK_ENABLED=false
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=
DEEPSEEK_API_KEYS=

KIMI_ENABLED=false
KIMI_BASE_URL=https://api.moonshot.cn/v1
KIMI_MODEL=
KIMI_API_KEYS=

AGENT_LLM_BASE_URL=
AGENT_LLM_API_KEY=
AGENT_LLM_MODEL=
AGENT_LLM_TIMEOUT_SECONDS=90
AGENT_LLM_MAX_ATTEMPTS=2

SCHEDULER_ENABLED=false
SCHEDULER_TIMEZONE=Asia/Shanghai
SCHEDULER_POLL_SECONDS=30

REPORT_STORAGE_DIR=./data/reports
REPORT_PUBLIC_BASE_URL=
REPORT_RETENTION_DAYS=90
```

`*_API_KEYS` 使用英文逗号分隔；解析时去空格、去空值、去重。`YUANBAO_CREDENTIALS_JSON` 是 JSON 数组，每项包含 `secret_id` 和 `secret_key`。任何密钥都不得出现在日志、异常消息、数据库原始响应或 API 返回值中。

### 配置校验

- [ ] 平台 `ENABLED=true` 时，模型和凭证为空应在进程启动阶段失败。
- [ ] `SCHEDULER_ENABLED=true` 时校验时区合法。
- [ ] `REPORT_STORAGE_DIR` 启动时创建，无法写入则启动失败。
- [ ] 开发、测试、生产可通过同一 Settings 类加载，不在代码中判断机器路径。
- [ ] Docker Compose 增加 `api`、`worker`、`scheduler` 服务模板，三者复用同一镜像和环境文件，仅启动命令不同。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/test_config.py -q
backend/.venv/Scripts/python -m pip check
docker compose config --quiet
```

**提交信息：** `feat(config): define monitoring runtime settings`

---

## 6. Task 4：平台适配器与密钥池基础设施 `[S][B]`

**目标：** 提供统一的官方 API 适配器接口、错误分类、限流和 Redis 密钥池。

**修改文件：**

- `backend/app/geo_monitoring/adapters/base.py`
- `backend/app/geo_monitoring/adapters/registry.py`
- `backend/app/geo_monitoring/adapters/key_pool.py`
- `backend/app/geo_monitoring/adapters/errors.py`
- `backend/tests/geo_monitoring/adapters/`

### 公共契约

```python
class PlatformAdapter(Protocol):
    code: str

    async def query(self, request: PlatformQuery) -> PlatformAnswer:
        ...
```

`PlatformQuery` 至少包含 prompt、system_prompt、model、temperature、request_id；`PlatformAnswer` 至少包含 text、citations、model、usage、latency_ms、provider_request_id、raw_response。

### 密钥池规则

- [ ] Redis 中只保存密钥指纹和状态，不保存可逆明文；实际密钥来自当前进程 Settings。
- [ ] 使用轮询选择健康密钥，Redis 原子自增维护游标。
- [ ] 429/限流：按响应头或指数退避进入冷却。
- [ ] 401/403：标记当前密钥不可用，继续尝试其他密钥。
- [ ] 5xx/网络错误：可重试；参数错误和内容安全拒绝不可重试。
- [ ] 所有密钥不可用时抛出 `NoAvailableCredentialError`，Actor 负责记录失败。
- [ ] 日志只记录平台、密钥指纹、错误分类和 request id。

### 测试

- 密钥轮询顺序稳定。
- 冷却中的密钥不会被选中。
- Redis 临时不可用时使用进程内轮询降级，但打印一次告警。
- 异常字符串和日志中不包含完整密钥。
- adapter registry 对禁用平台返回明确异常。

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/adapters -q
```

**提交信息：** `feat(collection): add adapter and credential pool contracts`

---

## 7. Task 5A-5E：官方平台适配器 `[P]`

五个任务可在 Task 4 合并后同时开始。每个 Subagent 只能修改自己的适配器文件和测试文件。

### 通用验收要求

- 使用平台官方开放 API，不使用网页抓取、浏览器自动化或非公开接口。
- 通过 `respx`/HTTP mock 覆盖成功、超时、429、401、5xx、空答案、引用解析。
- CI 不发起真实付费请求；真实 smoke test 通过显式环境开关手工执行。
- 返回统一 `PlatformAnswer`，原始响应按 `COLLECTION_RAW_RESPONSE_ENABLED` 决定是否保留。
- 平台未配置或未启用时不注册。

### Task 5A：豆包适配器

**文件：** `adapters/doubao.py`、`tests/.../test_doubao.py`

**分支：** `feature/adapter-doubao`

**提交：** `feat(adapter): add doubao official api`

### Task 5B：通义千问适配器

**文件：** `adapters/qwen.py`、`tests/.../test_qwen.py`

**分支：** `feature/adapter-qwen`

**提交：** `feat(adapter): add qwen official api`

### Task 5C：腾讯元宝映射适配器

**文件：** `adapters/yuanbao.py`、`tests/.../test_yuanbao.py`

**实现约束：** 产品平台代码保持 `yuanbao`，底层仅调用腾讯混元官方 API；文档和 UI 明确该映射。

**分支：** `feature/adapter-yuanbao`

**提交：** `feat(adapter): add yuanbao hunyuan mapping`

### Task 5D：DeepSeek 适配器

**文件：** `adapters/deepseek.py`、`tests/.../test_deepseek.py`

**分支：** `feature/adapter-deepseek`

**提交：** `feat(adapter): add deepseek official api`

### Task 5E：Kimi 适配器

**文件：** `adapters/kimi.py`、`tests/.../test_kimi.py`

**分支：** `feature/adapter-kimi`

**提交：** `feat(adapter): add kimi official api`

### 主 Agent 合并顺序

```powershell
git merge --no-ff feature/adapter-doubao
git merge --no-ff feature/adapter-qwen
git merge --no-ff feature/adapter-yuanbao
git merge --no-ff feature/adapter-deepseek
git merge --no-ff feature/adapter-kimi
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/adapters -q
```

合并后由主 Agent 单独更新 `adapters/registry.py`，禁止各适配器分支争抢注册表。

---

## 8. Task 6：采集队列与 Actor `[S][B]`

**目标：** 创建运行后异步采集每个 QueryTask，并原子落库答案、引用和品牌识别结果。

**修改文件：**

- `backend/app/worker/actors/collection.py`
- `backend/app/worker/broker.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/app/geo_monitoring/services/brand_matcher.py`
- `backend/tests/worker/test_collection_actor.py`

### 步骤

- [ ] 创建运行事务提交后，再逐个发送 `collect_query_task(task_id)` 消息。
- [ ] Actor 读取任务并使用行锁将 `pending -> running`；非 pending 任务直接幂等退出。
- [ ] 调用 registry 中的平台适配器，不把 ORM Session 跨 await 或消息边界传递。
- [ ] 规范化答案文本和引用 URL；提取品牌、别名和竞品提及。
- [ ] 在单个数据库事务中写入 answer、citation、brand result 并将任务置为 succeeded。
- [ ] 失败时记录可枚举错误码；达到最大尝试次数后置为 failed。
- [ ] 用户取消的 run/task 不再调用外部 API。
- [ ] Dramatiq 消息只携带 ID，不携带密钥、Prompt 全文或 ORM 对象。

### 测试

- 消息重复投递只生成一个答案。
- worker 在 API 事务提交前不会读取任务。
- 可重试异常按配置重试；不可重试异常一次失败。
- 取消发生在 API 调用前和调用后都保持终态一致。
- worker 崩溃后重新投递可恢复，不留下永久 running 任务。

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/worker/test_collection_actor.py -q
```

**提交信息：** `feat(collection): execute query tasks asynchronously`

---

## 9. Task 7：运行聚合、重试、取消与采集 API `[S][B]`

**目标：** 提供可操作的运行生命周期，并在任务终态后准确聚合运行状态。

**修改文件：**

- `backend/app/geo_monitoring/services/runs.py`
- `backend/app/geo_monitoring/api/runs.py`
- `backend/app/geo_monitoring/api/answers.py`
- `backend/tests/geo_monitoring/test_run_lifecycle.py`

### 状态规则

- Run：`pending -> running -> completed | partial_failed | failed | cancelled`。
- QueryTask：`pending -> running -> succeeded | failed | cancelled`。
- 任何终态不可回退；重试通过创建新的尝试或显式重置失败任务实现，必须记录 attempt_count。

### API

- [ ] `POST /api/v1/runs` 创建运行并入队。
- [ ] `GET /api/v1/runs` 按项目、状态、时间分页筛选。
- [ ] `GET /api/v1/runs/{id}` 返回计数、进度和错误摘要。
- [ ] `POST /api/v1/runs/{id}/cancel` 取消未完成任务。
- [ ] `POST /api/v1/runs/{id}/retry-failed` 只重试失败任务。
- [ ] `GET /api/v1/runs/{id}/tasks` 查询任务。
- [ ] `GET /api/v1/runs/{id}/answers` 查询答案摘要。
- [ ] `GET /api/v1/answers/{id}` 查询答案、引用和品牌结果。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/test_run_lifecycle.py -q
backend/.venv/Scripts/python -m pytest backend/tests/test_api_contract.py -q
```

**提交信息：** `feat(runs): complete collection lifecycle APIs`

---

## 10. Task 8：创建分析域库表 `[S][B][M]`

**目标：** 增加确定性指标、Agent 执行和趋势快照存储。

**修改文件：**

- `backend/alembic/versions/*_geo_monitoring_0003_analysis_metrics.py`
- `backend/tests/test_migrations.py`

### 新表

- [ ] `geo_agent_execution`：运行、Agent 类型、状态、输入/输出 JSON、模型、token、耗时、错误、开始/结束时间。
- [ ] `geo_platform_analysis`：运行、平台、品牌可见度、引用率、情感分、推荐率、答案数和摘要 JSON。
- [ ] `geo_metric_snapshot`：项目、品牌、平台、指标名、指标值、样本数、统计周期、计算时间。
- [ ] `geo_prompt_competitiveness`：运行、Prompt、品牌、竞品、相对排名、差值和证据 JSON。
- [ ] `geo_source_stat`：运行、平台、域名、引用次数、答案覆盖数和来源类型。

### 约束

- 同一 run/platform 的平台分析唯一。
- 同一统计维度和周期的快照唯一。
- JSON 字段使用 PostgreSQL JSONB；SQLite 测试需有兼容类型策略。
- 外键删除策略不得导致删除项目时留下孤儿分析数据。

### 验证

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini downgrade geo_monitoring_0002
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m pytest backend/tests/test_migrations.py -q
```

**提交信息：** `feat(db): add monitoring analysis schema`

---

## 11. Task 9：确定性指标计算 `[P]`

**目标：** 不依赖 LLM，计算可复现、可测试的监测指标。

**修改文件：**

- `backend/app/geo_monitoring/analysis/metrics.py`
- `backend/app/geo_monitoring/analysis/sources.py`
- `backend/app/geo_monitoring/analysis/competitors.py`
- `backend/tests/geo_monitoring/analysis/`

### 指标定义

- 品牌可见度 = 提及目标品牌的有效答案数 / 有效答案总数。
- 引用率 = 含至少一个有效引用的答案数 / 有效答案总数。
- 推荐率 = 明确推荐目标品牌的答案数 / 有效答案总数；第一版使用规则结果和 Agent 结构化标签，分别保存来源。
- 竞品优势差 = 目标品牌可见度 - 指定竞品可见度。
- 来源覆盖 = 引用目标域名的去重答案数。

### 步骤

- [ ] 对分母为 0、重复引用、品牌别名重叠、大小写和全半角进行明确处理。
- [ ] 指标函数保持纯函数，输入 DTO，输出 DTO；数据库读写放 service。
- [ ] 使用参数化测试覆盖中文、英文、别名冲突和空数据。
- [ ] 写入平台分析、Prompt 竞争力和来源统计时使用 upsert，重复执行结果一致。

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/analysis -q
```

**提交信息：** `feat(analysis): calculate deterministic monitoring metrics`

---

## 12. Task 10：统一 Agent LLM 客户端 `[P][B]`

**目标：** 通过 OpenAI-compatible 配置提供结构化输出、重试、审计和脱敏能力。

**修改文件：**

- `backend/app/geo_monitoring/agents/llm.py`
- `backend/app/geo_monitoring/agents/schemas.py`
- `backend/app/geo_monitoring/agents/prompts.py`
- `backend/tests/geo_monitoring/agents/test_llm.py`

### 步骤

- [ ] 封装 async OpenAI-compatible client，不在业务代码直接实例化 SDK。
- [ ] 定义情感、推荐意图、风险、洞察摘要等 Pydantic 输出 Schema。
- [ ] 结构化解析失败时最多修复一次；仍失败则记录 Agent 执行失败，不伪造结果。
- [ ] Prompt 模板版本化，并将模板版本写入 execution input metadata。
- [ ] 输入裁剪到可配置上限；日志不打印完整答案批次和密钥。
- [ ] 用 mock 覆盖超时、限流、非法 JSON、字段缺失和成功响应。

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/agents/test_llm.py -q
```

**提交信息：** `feat(agent): add openai compatible llm client`

---

## 13. Task 11：LangGraph 分析 Agent `[S][B]`

**前置：** Task 9、10 已合并。

**目标：** 以可恢复节点编排完成数据准备、指标汇总、LLM 洞察和结果持久化。

**修改文件：**

- `backend/app/geo_monitoring/agents/graph.py`
- `backend/app/geo_monitoring/agents/nodes.py`
- `backend/app/geo_monitoring/services/analysis.py`
- `backend/tests/geo_monitoring/agents/test_graph.py`

### 图节点

1. `load_run_data`：只加载 succeeded 答案，生成不可变输入 DTO。
2. `calculate_metrics`：调用 Task 9 纯函数。
3. `classify_answers`：批量调用 LLM 获取结构化标签。
4. `generate_insights`：生成平台差异、竞品差距、来源特征和风险摘要。
5. `persist_results`：事务性 upsert 分析结果和 execution 审计。

### 规则

- 无有效答案时不调用 LLM，分析以 skipped 结束并说明原因。
- 单个平台 LLM 失败不阻塞其他平台；最终状态可为 partial_failed。
- 图节点只传递可序列化 state，不传递 Session、HTTP client 或密钥。
- 同一 run 重跑分析必须幂等，保留 execution 历史但覆盖当前聚合结果。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/agents/test_graph.py -q
```

**提交信息：** `feat(agent): orchestrate monitoring analysis graph`

---

## 14. Task 12：分析 Actor 与分析 API `[S][B]`

**目标：** 采集完成后触发分析，并提供看板、趋势和 Agent 执行查询接口。

**修改文件：**

- `backend/app/worker/actors/analysis.py`
- `backend/app/geo_monitoring/api/analysis.py`
- `backend/app/geo_monitoring/api/dashboard.py`
- `backend/tests/worker/test_analysis_actor.py`
- `backend/tests/geo_monitoring/test_dashboard_api.py`

### API

- [ ] `POST /api/v1/runs/{id}/analyze` 手工触发或重跑。
- [ ] `GET /api/v1/runs/{id}/analysis` 获取平台指标和洞察。
- [ ] `GET /api/v1/runs/{id}/agent-executions` 获取执行审计。
- [ ] `GET /api/v1/projects/{id}/dashboard` 获取最新汇总。
- [ ] `GET /api/v1/projects/{id}/trends` 按指标、平台和时间范围查询趋势。
- [ ] 运行所有采集任务进入终态后自动发送一次分析消息。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/worker/test_analysis_actor.py backend/tests/geo_monitoring/test_dashboard_api.py -q
```

**提交信息：** `feat(analysis): expose analysis workflow and dashboard APIs`

---

## 15. Task 13：创建调度与报告库表 `[S][B][M]`

**目标：** 增加持久化调度配置和报告元数据。

**修改文件：**

- `backend/alembic/versions/*_geo_monitoring_0004_schedule_report.py`
- `backend/tests/test_migrations.py`

### 新表

- [ ] `geo_monitor_schedule`：项目、名称、cron、时区、启用状态、下次/上次运行时间、misfire 策略、创建更新时间。
- [ ] `geo_report`：项目、运行、状态、格式、文件名、相对存储路径、大小、checksum、错误、创建完成时间。
- [ ] cron + timezone 在应用层校验；数据库保存规范化表达式。
- [ ] 同一项目下调度名称唯一；报告相对路径唯一。

### 验证

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini downgrade geo_monitoring_0003
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m pytest backend/tests/test_migrations.py -q
```

**提交信息：** `feat(db): add monitoring schedule and report schema`

---

## 16. Task 14：独立 APScheduler 进程 `[P]`

**目标：** 从数据库同步调度配置，到期后幂等创建监测运行。

**修改文件：**

- `backend/app/scheduler/main.py`
- `backend/app/scheduler/jobs.py`
- `backend/app/geo_monitoring/services/schedules.py`
- `backend/app/geo_monitoring/api/schedules.py`
- `backend/tests/scheduler/`

### 步骤

- [ ] 独立命令启动 scheduler，不嵌入 FastAPI 多 worker 进程。
- [ ] 每 `SCHEDULER_POLL_SECONDS` 同步启用的数据库调度。
- [ ] job 使用 `schedule_id + planned_fire_time` 作为幂等键，避免多实例重复创建 run。
- [ ] 明确 misfire 行为：默认只补一次，不补历史全部漏跑。
- [ ] 创建运行时写 `trigger_type=schedule`、`triggered_by=<schedule_id>`。
- [ ] 提供调度 CRUD、启停和手工立即运行 API。
- [ ] 使用冻结时间测试时区、夏令时、misfire、重复触发。

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/scheduler -q
```

**提交信息：** `feat(schedule): run monitoring schedules in dedicated process`

---

## 17. Task 15：报告生成与本地存储 `[P]`

**目标：** 从分析结果生成可下载的 Markdown 和 HTML 报告，并管理本地文件生命周期。

**修改文件：**

- `backend/app/geo_monitoring/reports/renderer.py`
- `backend/app/geo_monitoring/reports/storage.py`
- `backend/app/worker/actors/report.py`
- `backend/app/geo_monitoring/api/reports.py`
- `backend/app/geo_monitoring/templates/report/`
- `backend/tests/geo_monitoring/reports/`

### 步骤

- [ ] 使用 Jinja2 模板渲染项目摘要、平台指标、竞品差距、Prompt 表现、来源统计和 Agent 洞察。
- [ ] 报告路径使用 `project_id/run_id/report_id.ext`，数据库只保存相对路径。
- [ ] 写入临时文件后原子 rename，计算 SHA-256 和文件大小。
- [ ] 只允许通过 report id 下载，不接受用户输入的任意文件路径。
- [ ] 支持创建、列表、状态、下载和删除 API。
- [ ] 每日清理超过 `REPORT_RETENTION_DAYS` 且无保留标记的报告。
- [ ] HTML 转义原始答案内容，防止存储型 XSS。

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/reports -q
```

**提交信息：** `feat(report): generate and store monitoring reports`

---

## 18. Task 16：前端公共基础 `[S][B][M]`

**目标：** 建立监测管理页面所需 API 层、类型、路由、测试框架和统一布局。

**修改文件：**

- `frontend/package.json`
- `frontend/src/api/`
- `frontend/src/types/`
- `frontend/src/router/`
- `frontend/src/layouts/`
- `frontend/src/test/`
- `frontend/vite.config.ts`

### 步骤

- [ ] 增加 React Router、TanStack Query、Vitest、Testing Library、MSW；更新锁文件。
- [ ] 创建统一 `apiClient`，处理 base URL、超时、错误体、分页和取消请求。
- [ ] TypeScript 类型与后端 Schema 对齐，不使用 `any` 逃避契约。
- [ ] 建立路由：项目配置、品牌、Prompt、平台、运行、运行详情、看板、趋势、调度、报告。
- [ ] 布局保留项目切换、导航、加载态、空态和错误边界。
- [ ] API mock 必须使用真实路径和响应结构。

### 验证

```powershell
npm --prefix frontend run lint
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

**提交信息：** `feat(frontend): add monitoring application foundation`

---

## 19. Task 17A-17D：前端页面域 `[P]`

Task 16 合并后可并行。每个分支只修改自己的 `pages/<domain>`、对应 components 和测试；路由注册由主 Agent 最后完成。

### Task 17A：监测配置

**范围：** 项目、品牌与别名、Prompt Set/Prompt、平台启停和模型配置。

**验收：** CRUD、表单校验、删除冲突提示、空态、分页和 loading。

**提交：** `feat(frontend): add monitoring configuration pages`

### Task 17B：运行与答案

**范围：** 创建运行、运行列表、进度、取消、失败重试、任务列表、答案/引用/品牌结果详情。

**验收：** 状态轮询有停止条件；页面卸载取消请求；终态不继续轮询。

**提交：** `feat(frontend): add monitoring run pages`

### Task 17C：看板与趋势

**范围：** 总览卡片、平台对比、竞品差距、Prompt 表现、来源排行、时间趋势。

**验收：** 指标定义有 tooltip；分母为零显示 `--`；筛选条件进入 URL。

**提交：** `feat(frontend): add monitoring dashboard and trends`

### Task 17D：调度与报告

**范围：** cron/时区配置、启停、立即运行、报告生成、状态和下载。

**验收：** cron 错误可读；生成中状态刷新；下载失败有明确提示。

**提交：** `feat(frontend): add schedules and reports pages`

### 每个分支验证

```powershell
npm --prefix frontend run test -- --run
npm --prefix frontend run build
```

### 主 Agent 集成

- [ ] 按 17A、17B、17C、17D 顺序合并。
- [ ] 集中更新路由、导航和共享导出。
- [ ] 解决重复组件时保留更接近 Task 16 公共模式的实现。
- [ ] 合并后执行前端全量 lint、test、build。

---

## 20. Task 18：端到端、可观测性与安全 `[S][B][M]`

**目标：** 验证完整业务链路，并补齐上线前必须具备的运行保障。

**修改文件：**

- `backend/app/core/logging.py`
- `backend/app/main.py`
- `backend/tests/e2e/`
- `frontend/e2e/`
- `docker-compose.yml`
- `README.md`

### 端到端场景

1. 创建项目、目标品牌、竞品、Prompt Set 和 Prompt。
2. 启用一个 mock 官方平台适配器配置。
3. 创建运行，等待 QueryTask 完成并验证答案、引用和品牌结果。
4. 自动触发分析，验证指标、Agent execution 和趋势快照。
5. 创建报告并下载，校验 checksum。
6. 创建调度，冻结时间触发新运行且不重复。
7. 对运行执行取消、失败重试和分析重跑。

### 可观测性

- [ ] API、worker、scheduler 使用统一 JSON 日志字段：`request_id`、`run_id`、`task_id`、`platform_code`、`duration_ms`。
- [ ] `/api/v1/health` 检查进程；`/api/v1/ready` 检查数据库和 Redis。
- [ ] 日志记录状态转换和外部 API 错误分类，不记录密钥与完整 Prompt/答案。
- [ ] worker 启动日志显示 actor 注册列表；scheduler 显示加载的 job 数量。

### 安全检查

- [ ] API 参数、分页上限、报告路径和文件名均校验。
- [ ] HTML 报告转义用户和模型内容。
- [ ] CORS 只允许配置来源。
- [ ] 生产环境 `DEBUG=false`，异常响应不返回堆栈。
- [ ] 用测试扫描响应、日志 fixture 和数据库 raw response，不得出现测试密钥。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q --cov=backend/app --cov-report=term-missing
npm --prefix frontend run lint
npm --prefix frontend run test -- --run
npm --prefix frontend run build
npm --prefix frontend run e2e
docker compose config --quiet
```

**提交信息：** `test: cover monitoring mvp end to end`

---

## 21. Task 19：部署、发布与回滚 `[S][B][M]`

**目标：** 提供可重复部署的 API、worker、scheduler 和前端产物，并验证迁移和文件存储策略。

**修改文件：**

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `README.md`
- `CLAUDE.md`

### 部署步骤

- [ ] 构建同一后端镜像，分别以 API、worker、scheduler 命令启动。
- [ ] 报告目录挂载持久卷；确认容器用户拥有写权限。
- [ ] PostgreSQL 和 Redis 不暴露到公网。
- [ ] 部署前备份数据库和报告目录。
- [ ] 先运行 `alembic upgrade head`，再启动 worker/scheduler，最后切换 API 和前端。
- [ ] 启动后执行 health、ready、创建测试项目、mock 运行和报告下载 smoke test。

### 回滚规则

- 应用回滚优先回滚镜像，不自动 downgrade 数据库。
- 只有确认新表无生产数据且旧应用无法兼容时，才人工执行逐版本 downgrade。
- 报告目录回滚只恢复元数据一致的备份，不覆盖新生成文件。
- 平台 API 异常时先设置对应 `*_ENABLED=false` 并重启 worker，不阻塞其他平台。

### 最终验证

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini current
backend/.venv/Scripts/python -m pytest backend/tests -q
npm --prefix frontend run lint
npm --prefix frontend run test -- --run
npm --prefix frontend run build
docker compose build
docker compose up -d
docker compose ps
```

**提交信息：** `chore: prepare monitoring mvp deployment`

---

## 22. 最终验收清单

### 数据库

- [ ] 新数据库可从空库升级到 `geo_monitoring_0004`。
- [ ] 现有 `geo_monitoring_0001` 数据可无损升级。
- [ ] 三个增量迁移都能单独 downgrade/upgrade。
- [ ] 没有通过 `create_all()` 绕过 Alembic 创建生产表。

### 后端

- [ ] 五个平台只使用官方 API，默认全部禁用。
- [ ] 单个平台或单个密钥失败不会阻塞整个运行。
- [ ] 创建、采集、分析、报告和调度均具备幂等保护。
- [ ] API、worker、scheduler 可独立水平扩展；scheduler 单活或具备幂等锁。
- [ ] 所有密钥和敏感响应经过脱敏。

### 前端

- [ ] 配置、运行、答案、看板、趋势、调度、报告页面可完成闭环操作。
- [ ] loading、empty、error、partial_failed、cancelled 状态均有可读反馈。
- [ ] 前端类型、mock 和后端 OpenAPI 契约一致。

### 工程质量

- [ ] 后端全量测试、前端 lint/test/build、E2E 全部通过。
- [ ] `git diff --check` 无空白错误。
- [ ] `.env`、密钥、数据库数据、报告文件、`.codegraph/` 未提交。
- [ ] README 和 CLAUDE.md 与实际启动方式一致。
- [ ] 主 Agent 对每个并行分支完成代码审查，未直接信任 Subagent 自报结果。

### 交付记录

主 Agent 在最终 PR 描述中列出：

1. 数据库迁移 revision 和回滚方式。
2. 新增环境变量及默认值。
3. 平台适配器启用方式和官方 API 限制。
4. API、worker、scheduler、frontend 的启动命令。
5. 自动化测试结果和未覆盖的真实平台 smoke test。
6. 报告目录的持久化、备份和清理策略。
