# AI 应用监测 MVP Cursor 实施任务 V2

> **适用范围：** 本版本只规划 `backend` 目录下的 MVP 功能实现。`frontend` 目录暂不纳入开发、测试和验收；后续需要前端时再单独拆分任务。

**目标：** 基于当前 GEO-Platform 后端基础设施，实现 AI 应用监测 MVP 的后端闭环：监测配置、官方 API 采集、确定性指标、Agent 洞察、调度、报告和后端部署验证。

**统一本地运行环境：** PostgreSQL、Redis、Nacos 已在服务器中安装部署，连接信息已写入本地 `.env`。后续本地运行、调试和联调统一使用 `.env` 中配置的这三项服务，不再要求本地 Docker 启动 PostgreSQL/Redis/Nacos。

**后端架构：** FastAPI + SQLAlchemy + Alembic 提供控制面和数据面 API；Dramatiq/Redis 承担采集、分析和报告异步任务；独立 APScheduler 进程创建定时运行；PostgreSQL 保存业务数据；Nacos 提供后端运行所需的外部配置/服务发现基础；报告写入本地目录或后续配置的持久化目录。

**技术栈：** Python 3.11、FastAPI、SQLAlchemy 2、Alembic、PostgreSQL 16、Redis 7、Dramatiq、APScheduler、LangGraph、Pydantic、Nacos、OpenAI-compatible LLM SDK、Jinja2、pytest、respx、freezegun。

---

## 1. 执行规则

### 1.1 标记说明

- `[S]`：串行任务，必须等待前置任务完成并合并。
- `[P]`：可并行任务，可分配给独立 Cursor Agent/Subagent。
- `[B]`：阻塞点，未通过验收不得开始依赖它的任务。
- `[M]`：只能由主 Agent 修改或合并，避免公共文件冲突。
- `[H]`：包含必须由用户人工完成或确认的操作。

### 1.2 人机边界规则

每个任务都必须显式声明：

- **需要你操作：** 涉及真实服务器、真实密钥、真实外部平台、生产/共享环境变更、业务口径确认和最终人工 smoke test 的事项。
- **由我操作：** 仓库内代码、测试、迁移、文档、Mock、局部验证和主 Agent 审查合并。

我不会读取、打印或提交 `.env` 中的真实密钥；如需确认配置，只验证变量名、格式和连接结果，不输出敏感值。

### 1.3 Cursor 工作方式

1. 主 Agent 在集成分支工作，负责拆任务、维护公共契约、数据库迁移链和最终验收。
2. 每个并行任务创建独立 worktree，避免多个 Agent 同时修改同一目录。
3. 不使用统一 Subagent 提示词模板；每个任务都在任务正文内提供独立提示词，提示词必须按任务目标、允许文件、禁止文件和验收命令定制。
4. Subagent 完成后先运行局部测试并提交；主 Agent 使用 `git show --stat` 和 `git diff <base>...<branch>` 审查。
5. 公共文件由主 Agent 维护：Alembic 迁移链、`backend/app/core/config.py`、公共 Schema、worker broker、依赖文件、`.env.example`、部署文档。
6. 每次只合并一个公共契约变更；合并后重新基线化后续并行分支。

推荐目录：

```powershell
New-Item -ItemType Directory -Force .worktrees | Out-Null
git worktree add .worktrees/mvp-backend-integration -b feature/ai-monitoring-backend-mvp
```

### 1.4 总体依赖与并行窗口

```text
Task 0
  -> Task 1 [服务器环境与基线确认，串行阻塞]
  -> Task 2 [数据库采集迁移，串行阻塞]
  -> Task 3 [采集模型与公共契约，串行阻塞]
  -> Task 4 [后端依赖、环境变量与 Nacos 契约，串行阻塞]
      -> Task 5 [适配器基础设施]
          -> Task 6A/6B/6C/6D/6E [五个平台适配器，并行]
          -> Task 7 [采集 Actor]
              -> Task 8 [运行聚合与 API]
  -> Task 9 [分析迁移，串行阻塞]
      -> Task 10 [确定性指标]
      -> Task 11 [LLM 公共能力]
          -> Task 12 [LangGraph Agent]
              -> Task 13 [分析 Actor/API]
  -> Task 14 [调度与报告迁移，串行阻塞]
      -> Task 15 [调度器]
      -> Task 16 [报告]
  -> Task 17 [后端端到端、可观测性与安全]
  -> Task 18 [后端部署、发布与回滚]
```

数据库迁移 Task 2、9、14 必须在同一集成分支按顺序创建。禁止在并行 worktree 中各自生成 Alembic revision。

### 1.5 统一验证边界

后端任务默认使用：

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini heads
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head --sql
```

如任务涉及 Redis/Nacos 连接，只允许通过 `.env` 中配置的服务器地址验证；不新增本地 Docker 服务作为默认路径。CI 和单元测试仍以 mock/fake 为主，避免依赖共享服务器状态。

---

## 2. Task 0：确认 V2 范围与执行基线 `[S][B][M]`

**目标：** 固化 V2 后端优先范围，确认当前仓库和任务书使用方式。

**修改文件：** 无。

### 需要你操作

- 确认本阶段暂不开发 `frontend`。
- 确认 `.env` 已包含可用的 PostgreSQL、Redis、Nacos 连接信息。
- 如服务器服务需要白名单、防火墙或账号权限调整，由你在服务器侧完成。

### 由我操作

- 检查工作区状态、当前分支和最近提交。
- 只在 `backend`、`docs`、根部后端相关配置文件范围内推进后续任务。
- 不读取或提交 `.env` 中的真实密钥。

### 步骤

```powershell
git status --short
git branch --show-current
git log -5 --oneline
```

创建并进入集成 worktree：

```powershell
git worktree add .worktrees/mvp-backend-integration -b feature/ai-monitoring-backend-mvp
Set-Location .worktrees/mvp-backend-integration
```

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 0：确认 AI 应用监测后端 MVP 的执行基线。
本阶段只处理 backend 和后端相关配置，不开发 frontend。
请检查 git 状态、当前分支、最近提交、Python 测试基线，并确认 .env 文件存在但不要打印其中内容。
禁止修改业务代码、迁移文件和 frontend 目录。
输出基线结论、发现的阻塞项、已运行命令和后续建议。
```

**提交信息：** 无提交。

---

## 3. Task 1：服务器 PostgreSQL/Redis/Nacos 本地运行契约 `[S][B][M][H]`

**目标：** 将本地运行方式固定为使用 `.env` 中的服务器 PostgreSQL、Redis、Nacos，不再把本地 Docker 服务作为默认开发路径。

**修改文件：**

- `.env.example`
- `backend/app/core/config.py`
- `backend/tests/test_config.py`
- `README.md` 或后端启动文档

### 需要你操作

- 提供或确认 `.env` 中已配置：`DATABASE_URL`、`REDIS_URL`、`NACOS_SERVER_ADDRESSES`、`NACOS_NAMESPACE`、`NACOS_GROUP`、`NACOS_USERNAME`、`NACOS_PASSWORD` 等实际值。
- 在服务器侧保证 PostgreSQL、Redis、Nacos 可从本机访问。
- 如果需要创建数据库、账号或 Nacos namespace/group，由你执行服务器侧操作。

### 由我操作

- 在 `.env.example` 中增加不含真实密钥的占位配置。
- 在 Settings 中增加 Nacos 配置和格式校验。
- 增加配置测试，覆盖缺失值、非法 URL、禁用/启用场景。
- 更新启动文档，明确本地不再默认 `docker compose up postgres redis nacos`。

### 契约要求

- `.env` 是本地真实连接的唯一来源，禁止在代码中硬编码服务器地址。
- 测试环境可通过独立测试配置覆盖，不直接依赖共享服务器。
- readiness 检查需要覆盖数据库和 Redis；Nacos readiness 可先提供独立检查函数或管理命令，避免阻塞普通单元测试。
- 日志只能显示连接目标的脱敏摘要，不输出用户名、密码、token。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/test_config.py -q
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini current
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 1：把后端本地运行契约调整为统一使用 .env 中的服务器 PostgreSQL、Redis、Nacos。
允许修改 .env.example、backend/app/core/config.py、backend/tests/test_config.py 和后端启动文档。
不要读取、打印、提交 .env 的真实值；只校验变量存在性、类型和脱敏显示。
删除或改写文档中要求本地启动 postgres/redis/nacos 容器作为默认路径的描述，但不要删除 docker compose 中未来部署可能仍需的服务模板，除非测试证明必须调整。
请先写配置失败测试，再实现 Settings 与文档修改，最后运行 test_config 和 alembic current。
输出配置项清单、测试结果和仍需用户在服务器侧确认的事项。
```

**提交信息：** `chore(config): use shared server services for local backend`

---

## 4. Task 2：创建采集域库表 `[S][B][M]`

**目标：** 通过增量迁移增加答案、引用、品牌识别结果，并扩展运行状态信息。

**修改文件：**

- `backend/alembic/versions/*_geo_monitoring_0002_collection.py`
- `backend/tests/test_migrations.py`

### 需要你操作

- 不需要直接操作代码。
- 如迁移需要连接真实服务器数据库执行验证，由你确认是否允许对当前 `.env` 指向的数据库执行迁移；未确认前只生成 SQL 或使用测试数据库。

### 由我操作

- 编写迁移测试。
- 创建并手工审查 Alembic revision。
- 验证 upgrade/downgrade 顺序。
- 确保迁移不依赖前端或用户手工 SQL。

### 迁移内容

- [ ] `geo_monitor_run` 增加：`trigger_type`、`triggered_by`、`total_tasks`、`succeeded_tasks`、`failed_tasks`、`cancelled_tasks`、`started_at`、`completed_at`、`error_summary`。
- [ ] `geo_query_task` 增加：`attempt_count`、`max_attempts`、`queued_at`、`started_at`、`completed_at`、`last_error_code`、`last_error_message`、`provider_request_id`。
- [ ] 创建 `geo_answer`：任务、平台、Prompt、原始文本、规范化文本、模型名、token 用量、耗时、采集时间和原始响应 JSON。
- [ ] 创建 `geo_answer_citation`：答案、序号、标题、URL、域名、来源类型、引用文本。
- [ ] 创建 `geo_answer_brand_result`：答案、品牌、是否提及、提及次数、首次位置、情感、上下文 JSON。
- [ ] 为任务状态、运行状态、答案平台与时间、引用域名、品牌结果建立索引和唯一约束。
- [ ] `downgrade()` 必须完整逆序删除新增对象。

### 验证

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini downgrade geo_monitoring_0001
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head
backend/.venv/Scripts/python -m pytest backend/tests/test_migrations.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 2：创建 AI 应用监测采集域数据库迁移。
只允许修改 backend/alembic/versions 下新建的 0002 collection revision 和 backend/tests/test_migrations.py。
禁止修改模型、API、Settings、frontend 或已有迁移 revision。
请先补充迁移测试，覆盖 base -> 0001 -> 0002 -> 0001 -> 0002 的升级回退，再创建一个 Alembic revision。
迁移必须包含 run/task 扩展字段、answer、citation、brand result 表、索引、唯一约束和完整 downgrade。
不要对真实共享数据库执行破坏性 downgrade，除非用户明确确认。
输出 revision id、升级回退结果、测试结果和迁移风险。
```

**提交信息：** `feat(db): add monitoring collection schema`

---

## 5. Task 3：采集模型、Schema 与仓储契约 `[S][B][M]`

**目标：** 让 ORM、API Schema 和服务层完整覆盖 Task 2 数据结构，并拆分现有过于集中的模块。

**修改文件：**

- `backend/app/geo_monitoring/models.py`
- `backend/app/geo_monitoring/schemas.py`
- `backend/app/geo_monitoring/repositories/`
- `backend/app/geo_monitoring/services/runs.py`
- `backend/app/geo_monitoring/api/`
- `backend/tests/geo_monitoring/`

### 需要你操作

- 确认 API 路径兼容策略：继续保留现有 `/api/v1` 兼容路径，还是统一迁移到 `/api/geo-monitoring`。
- 如有业务口径变化，例如删除被运行引用的配置是否允许软删除，由你确认。

### 由我操作

- 编写失败测试。
- 添加 ORM、Pydantic Schema、repository 和 service。
- 拆分 API 文件并保持路由注册完整。
- 保证统一响应结构和分页结构不变。

### 步骤

- [ ] 为新增表和字段添加 SQLAlchemy 模型、关系、枚举和约束镜像。
- [ ] 增加 `AnswerRead`、`CitationRead`、`BrandResultRead`、`RunDetailRead`、分页响应 Schema。
- [ ] 将数据库读写集中到 `repositories/`，service 不直接散落 SQLAlchemy 查询。
- [ ] 将单文件 API 拆为 `projects.py`、`brands.py`、`prompts.py`、`platforms.py`、`runs.py`、`answers.py`。
- [ ] 保留当前“创建运行后生成 Prompt × Platform 任务”的语义，并在同一事务写入任务总数。
- [ ] 增加运行详情、任务列表、答案详情分页接口。
- [ ] 使用数据库唯一约束和 service 校验保证幂等，不依赖调用端去重。

### 测试先行

- 创建运行时无 Prompt 或无启用平台应返回 409。
- 重复创建同一答案不得产生两条记录。
- 删除被运行引用的配置时返回明确的 409，而非数据库 500。
- 分页参数越界返回 422。
- 现有 path template 不得丢失。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring -q
backend/.venv/Scripts/python -m pytest backend/tests/test_api_contract.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 3：补齐采集域 ORM、Schema、repository、service 和后端 API 契约。
允许修改 backend/app/geo_monitoring/models.py、schemas.py、repositories、services/runs.py、api 目录和 backend/tests/geo_monitoring。
禁止修改 Alembic 迁移链、Settings、worker、adapter、frontend。
请先写失败测试覆盖创建运行前置条件、答案幂等、删除冲突、分页 422 和 API path template 保持。
实现时将数据库访问收敛到 repositories，service 负责业务语义，API 只做请求响应编排。
输出接口变化、测试结果、兼容路径处理方式和剩余风险。
```

**提交信息：** `refactor(api): introduce monitoring collection contracts`

---

## 6. Task 4：后端依赖、环境变量与 Nacos 契约 `[S][B][M][H]`

**目标：** 一次性定义后端采集、Agent、调度、报告、Nacos 所需配置，所有密钥只从环境变量或受控配置源读取。

**修改文件：**

- `backend/requirements.txt`
- `backend/requirements-dev.txt`
- `backend/app/core/config.py`
- `.env.example`
- `backend/tests/test_config.py`
- 后端启动文档

### 需要你操作

- 确认真实平台 API key、Agent LLM key、Nacos 账号是否已经写入 `.env`。
- 若 Nacos 需要创建 namespace、group 或配置项，由你在 Nacos 控制台完成，或明确授权我只修改仓库内示例文档。

### 由我操作

- 增加后端依赖和配置项。
- 更新 `.env.example`，只写占位值和说明，不写真实地址和密钥。
- 增加 Settings 校验和脱敏测试。
- 更新启动文档，说明本地统一从 `.env` 连接服务器 PostgreSQL/Redis/Nacos。

### 依赖

- [ ] 运行依赖加入 `httpx`、`tenacity`、`apscheduler`、`langgraph`、`openai`、`jinja2`、`markdown`、Nacos Python 客户端。
- [ ] 开发依赖加入 `respx`、`freezegun`、`pytest-cov`。
- [ ] 固定兼容版本范围，并运行 `pip check`。

### `.env.example` 必须包含

```dotenv
APP_ENV=dev
DEBUG=false
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<server-host>:5432/geo_platform
REDIS_URL=redis://:<password>@<server-host>:6379/0

NACOS_SERVER_ADDRESSES=<server-host>:8848
NACOS_NAMESPACE=
NACOS_GROUP=DEFAULT_GROUP
NACOS_USERNAME=
NACOS_PASSWORD=
NACOS_CONFIG_DATA_ID=geo-platform-backend

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

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/test_config.py -q
backend/.venv/Scripts/python -m pip check
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 4：定义后端依赖、环境变量和 Nacos 配置契约。
允许修改 backend/requirements.txt、backend/requirements-dev.txt、backend/app/core/config.py、.env.example、backend/tests/test_config.py 和后端启动文档。
禁止修改业务模型、迁移、worker actor、adapter 实现和 frontend。
请先写 Settings 校验测试，覆盖平台启用但缺少密钥、Nacos 配置格式、报告目录创建失败、密钥脱敏。
实现后更新 .env.example，使用占位符表示服务器地址，不写任何真实 .env 值。
运行 test_config 和 pip check，输出新增配置项、默认值、测试结果和需要用户在 .env/Nacos 控制台完成的事项。
```

**提交信息：** `feat(config): define backend runtime settings`

---

## 7. Task 5：平台适配器与密钥池基础设施 `[S][B]`

**目标：** 提供统一的官方 API 适配器接口、错误分类、限流和 Redis 密钥池。

**修改文件：**

- `backend/app/geo_monitoring/adapters/base.py`
- `backend/app/geo_monitoring/adapters/registry.py`
- `backend/app/geo_monitoring/adapters/key_pool.py`
- `backend/app/geo_monitoring/adapters/errors.py`
- `backend/tests/geo_monitoring/adapters/`

### 需要你操作

- 不需要直接写代码。
- 如需要对真实 Redis 服务器做联调，由你确认可用的测试库编号和是否允许写入短生命周期 key。

### 由我操作

- 实现统一 adapter 协议、错误类型、密钥池和 registry。
- 使用 fake Redis 或 mock 覆盖绝大多数测试。
- 真实 Redis 只作为可选 smoke test，不作为单元测试前提。

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

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/adapters -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 5：实现官方平台适配器基础设施和 Redis 密钥池。
允许修改 backend/app/geo_monitoring/adapters/base.py、registry.py、key_pool.py、errors.py 以及 backend/tests/geo_monitoring/adapters。
禁止修改具体平台适配器、迁移、Settings、worker actor、frontend。
请先写测试覆盖密钥轮询、冷却、禁用平台、Redis 临时不可用降级、错误脱敏。
实现 PlatformQuery、PlatformAnswer、PlatformAdapter 协议和错误分类，Redis 只保存密钥指纹和状态。
运行 adapters 测试，输出公共接口说明、错误分类和测试结果。
```

**提交信息：** `feat(collection): add adapter and credential pool contracts`

---

## 8. Task 6A-6E：官方平台适配器 `[P][H]`

五个任务可在 Task 5 合并后同时开始。每个 Subagent 只能修改自己的适配器文件和测试文件，registry 注册由主 Agent 合并后统一处理。

### 通用验收要求

- 使用平台官方开放 API，不使用网页抓取、浏览器自动化或非公开接口。
- 通过 `respx`/HTTP mock 覆盖成功、超时、429、401、5xx、空答案、引用解析。
- CI 不发起真实付费请求；真实 smoke test 通过显式环境开关手工执行。
- 返回统一 `PlatformAnswer`，原始响应按 `COLLECTION_RAW_RESPONSE_ENABLED` 决定是否保留。
- 平台未配置或未启用时不注册。

### 需要你操作

- 在 `.env` 中配置你准备启用的平台 key 和模型名。
- 确认是否执行真实付费 smoke test；默认不执行。
- 如某个平台账号未开通或额度不足，由你在平台控制台处理。

### 由我操作

- 为每个平台实现官方 API adapter 和 mock 测试。
- 不接触真实平台控制台，不把真实 key 写入仓库。
- 合并后由主 Agent 统一更新 registry。

### Task 6A：豆包适配器

**文件：** `backend/app/geo_monitoring/adapters/doubao.py`、`backend/tests/geo_monitoring/adapters/test_doubao.py`

**分支：** `feature/adapter-doubao`

**专用 Cursor 提示词：**

```text
请执行 V2 Task 6A：实现豆包官方 API 适配器。
只允许修改 backend/app/geo_monitoring/adapters/doubao.py 和 backend/tests/geo_monitoring/adapters/test_doubao.py。
禁止修改 adapter registry、Settings、迁移、worker、其他平台适配器和 frontend。
请基于 Task 5 的 PlatformAdapter 契约实现 DoubaoAdapter，使用 respx mock 覆盖成功、超时、429、401、5xx、空答案和引用解析。
不得发起真实豆包请求，不得记录 API key。
运行 test_doubao.py，输出请求/响应映射、错误映射和测试结果。
```

**提交：** `feat(adapter): add doubao official api`

### Task 6B：通义千问适配器

**文件：** `backend/app/geo_monitoring/adapters/qwen.py`、`backend/tests/geo_monitoring/adapters/test_qwen.py`

**分支：** `feature/adapter-qwen`

**专用 Cursor 提示词：**

```text
请执行 V2 Task 6B：实现通义千问 OpenAI-compatible 官方 API 适配器。
只允许修改 backend/app/geo_monitoring/adapters/qwen.py 和 backend/tests/geo_monitoring/adapters/test_qwen.py。
禁止修改 registry、Settings、迁移、worker、其他平台适配器和 frontend。
请将千问响应规范化为 PlatformAnswer，覆盖 usage、model、provider_request_id、raw_response 和引用信息可为空的情况。
使用 respx mock 覆盖成功、超时、429、401、5xx、空答案。
不得发起真实请求，不得输出密钥。
运行 test_qwen.py，输出映射说明和测试结果。
```

**提交：** `feat(adapter): add qwen official api`

### Task 6C：腾讯元宝映射适配器

**文件：** `backend/app/geo_monitoring/adapters/yuanbao.py`、`backend/tests/geo_monitoring/adapters/test_yuanbao.py`

**实现约束：** 产品平台代码保持 `yuanbao`，底层仅调用腾讯混元官方 API；文档和 API 描述明确该映射。

**分支：** `feature/adapter-yuanbao`

**专用 Cursor 提示词：**

```text
请执行 V2 Task 6C：实现腾讯元宝到腾讯混元官方 API 的映射适配器。
只允许修改 backend/app/geo_monitoring/adapters/yuanbao.py 和 backend/tests/geo_monitoring/adapters/test_yuanbao.py。
禁止修改 registry、Settings、迁移、worker、其他平台适配器和 frontend。
平台 code 必须保持 yuanbao，但请求实现只能调用腾讯混元官方 API。
请覆盖 JSON credentials 解析后的调用、成功、鉴权失败、限流、服务端错误、空答案和引用为空。
不得发起真实请求，不得输出 secret_id 或 secret_key。
运行 test_yuanbao.py，输出映射说明、风险和测试结果。
```

**提交：** `feat(adapter): add yuanbao hunyuan mapping`

### Task 6D：DeepSeek 适配器

**文件：** `backend/app/geo_monitoring/adapters/deepseek.py`、`backend/tests/geo_monitoring/adapters/test_deepseek.py`

**分支：** `feature/adapter-deepseek`

**专用 Cursor 提示词：**

```text
请执行 V2 Task 6D：实现 DeepSeek 官方 API 适配器。
只允许修改 backend/app/geo_monitoring/adapters/deepseek.py 和 backend/tests/geo_monitoring/adapters/test_deepseek.py。
禁止修改 registry、Settings、迁移、worker、其他平台适配器和 frontend。
请按 OpenAI-compatible chat completions 形态实现请求和响应解析，规范化为 PlatformAnswer。
使用 respx mock 覆盖成功、超时、429、401、5xx、空 choices、空 content。
不得发起真实请求，不得输出 API key。
运行 test_deepseek.py，输出错误映射和测试结果。
```

**提交：** `feat(adapter): add deepseek official api`

### Task 6E：Kimi 适配器

**文件：** `backend/app/geo_monitoring/adapters/kimi.py`、`backend/tests/geo_monitoring/adapters/test_kimi.py`

**分支：** `feature/adapter-kimi`

**专用 Cursor 提示词：**

```text
请执行 V2 Task 6E：实现 Kimi/Moonshot 官方 API 适配器。
只允许修改 backend/app/geo_monitoring/adapters/kimi.py 和 backend/tests/geo_monitoring/adapters/test_kimi.py。
禁止修改 registry、Settings、迁移、worker、其他平台适配器和 frontend。
请按 Moonshot OpenAI-compatible 接口实现请求和响应解析，覆盖 usage、model、request id 和空答案。
使用 respx mock 覆盖成功、超时、429、401、5xx、内容安全拒绝。
不得发起真实请求，不得输出 API key。
运行 test_kimi.py，输出映射说明和测试结果。
```

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

合并后由主 Agent 单独更新 `backend/app/geo_monitoring/adapters/registry.py`，禁止各适配器分支争抢注册表。

---

## 9. Task 7：采集队列与 Actor `[S][B]`

**目标：** 创建运行后异步采集每个 QueryTask，并原子落库答案、引用和品牌识别结果。

**修改文件：**

- `backend/app/worker/actors/collection.py`
- `backend/app/worker/broker.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/app/geo_monitoring/services/brand_matcher.py`
- `backend/tests/worker/test_collection_actor.py`

### 需要你操作

- 确认本地 `.env` 中 Redis 连接可供 worker 开发联调使用。
- 如果要执行真实平台采集 smoke test，由你确认启用的平台和费用风险。

### 由我操作

- 实现 Dramatiq actor、采集 service 和品牌匹配。
- 使用 mock adapter 测试任务状态流转和幂等。
- 确保外部 API 调用不发生在数据库长事务内。

### 步骤

- [ ] 创建运行事务提交后，再逐个发送 `collect_query_task(task_id)` 消息。
- [ ] Actor 读取任务并使用行锁将 `pending -> running`；非 pending 任务直接幂等退出。
- [ ] 调用 registry 中的平台适配器，不把 ORM Session 跨 await 或消息边界传递。
- [ ] 规范化答案文本和引用 URL；提取品牌、别名和竞品提及。
- [ ] 在单个数据库事务中写入 answer、citation、brand result 并将任务置为 succeeded。
- [ ] 失败时记录可枚举错误码；达到最大尝试次数后置为 failed。
- [ ] 用户取消的 run/task 不再调用外部 API。
- [ ] Dramatiq 消息只携带 ID，不携带密钥、Prompt 全文或 ORM 对象。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/worker/test_collection_actor.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 7：实现采集队列和 collect_query_task Actor。
允许修改 backend/app/worker/actors/collection.py、backend/app/worker/broker.py、backend/app/geo_monitoring/services/collection.py、brand_matcher.py 和 backend/tests/worker/test_collection_actor.py。
禁止修改迁移、平台适配器实现、Settings、分析模块、报告模块和 frontend。
请先写测试覆盖重复消息幂等、事务提交后入队、可重试/不可重试异常、取消前后状态一致、worker 崩溃后恢复。
实现中不得在数据库事务内调用外部 API，不得在 Dramatiq 消息中携带密钥、Prompt 全文或 ORM 对象。
运行 collection actor 测试，输出状态机说明和测试结果。
```

**提交信息：** `feat(collection): execute query tasks asynchronously`

---

## 10. Task 8：运行聚合、重试、取消与采集 API `[S][B]`

**目标：** 提供可操作的运行生命周期，并在任务终态后准确聚合运行状态。

**修改文件：**

- `backend/app/geo_monitoring/services/runs.py`
- `backend/app/geo_monitoring/api/runs.py`
- `backend/app/geo_monitoring/api/answers.py`
- `backend/tests/geo_monitoring/test_run_lifecycle.py`

### 需要你操作

- 确认运行失败聚合状态命名使用 `partial_success` 还是 `partial_failed`；项目规则预留为 `partial_success`。

### 由我操作

- 实现运行聚合、取消、失败重试和答案查询 API。
- 增加后端测试覆盖状态不可逆和幂等。

### 状态规则

- Run：`pending -> collecting -> completed | partial_success | failed | cancelled`。
- QueryTask：`pending -> queued -> running -> success | failed | cancelled`。
- 任何终态不可回退；重试通过创建新的尝试或显式重置失败任务实现，必须记录 `attempt_count`。

### API

- [ ] `POST /api/geo-monitoring/runs` 创建运行并入队。
- [ ] `GET /api/geo-monitoring/runs` 按项目、状态、时间分页筛选。
- [ ] `GET /api/geo-monitoring/runs/{id}` 返回计数、进度和错误摘要。
- [ ] `POST /api/geo-monitoring/runs/{id}/cancel` 取消未完成任务。
- [ ] `POST /api/geo-monitoring/runs/{id}/retry-failed` 只重试失败任务。
- [ ] `GET /api/geo-monitoring/runs/{id}/tasks` 查询任务。
- [ ] `GET /api/geo-monitoring/runs/{id}/answers` 查询答案摘要。
- [ ] `GET /api/geo-monitoring/answers/{id}` 查询答案、引用和品牌结果。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/test_run_lifecycle.py -q
backend/.venv/Scripts/python -m pytest backend/tests/test_api_contract.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 8：实现运行聚合、重试、取消和采集查询 API。
允许修改 backend/app/geo_monitoring/services/runs.py、api/runs.py、api/answers.py 和 backend/tests/geo_monitoring/test_run_lifecycle.py。
禁止修改迁移、adapter、worker actor、分析模块、报告模块和 frontend。
请先写测试覆盖 run/task 状态聚合、终态不可回退、取消、失败重试、分页和答案详情。
状态命名遵循项目规则：运行部分成功使用 partial_success，任务成功使用 success。
运行 run lifecycle 和 API contract 测试，输出接口清单、状态机和测试结果。
```

**提交信息：** `feat(runs): complete collection lifecycle APIs`

---

## 11. Task 9：创建分析域库表 `[S][B][M]`

**目标：** 增加确定性指标、Agent 执行和趋势快照存储。

**修改文件：**

- `backend/alembic/versions/*_geo_monitoring_0003_analysis_metrics.py`
- `backend/tests/test_migrations.py`

### 需要你操作

- 如需在真实服务器数据库验证迁移，由你确认执行窗口和备份策略。

### 由我操作

- 编写迁移测试。
- 创建并审查分析域迁移。
- 确保 JSONB、唯一约束和 downgrade 正确。

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

### 专用 Cursor 提示词

```text
请执行 V2 Task 9：创建分析域数据库迁移。
只允许修改 backend/alembic/versions 下新建的 0003 analysis metrics revision 和 backend/tests/test_migrations.py。
禁止修改模型、API、Agent、指标实现、报告、frontend 或已有迁移。
请先写迁移测试，再创建一个 Alembic revision，包含 agent execution、platform analysis、metric snapshot、prompt competitiveness、source stat。
迁移必须使用稳定命名的索引/唯一约束，downgrade 完整逆序。
不要对真实共享数据库执行破坏性 downgrade，除非用户明确确认。
输出 revision id、SQL 审查重点、测试结果和风险。
```

**提交信息：** `feat(db): add monitoring analysis schema`

---

## 12. Task 10：确定性指标计算 `[P]`

**目标：** 不依赖 LLM，计算可复现、可测试的监测指标。

**修改文件：**

- `backend/app/geo_monitoring/analysis/metrics.py`
- `backend/app/geo_monitoring/analysis/sources.py`
- `backend/app/geo_monitoring/analysis/competitors.py`
- `backend/tests/geo_monitoring/analysis/`

### 需要你操作

- 确认第一版指标口径是否采用本文定义。
- 对推荐率等语义标签口径，如果需要业务调整，由你给出规则优先级。

### 由我操作

- 编写纯函数和参数化测试。
- 不让 LLM 修改确定性数值结果。
- 将数据库读写留给后续 service，不混入纯计算函数。

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

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/analysis -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 10：实现确定性监测指标计算。
允许修改 backend/app/geo_monitoring/analysis/metrics.py、sources.py、competitors.py 和 backend/tests/geo_monitoring/analysis。
禁止修改 Agent/LLM、迁移、API、worker、Settings 和 frontend。
请先写参数化测试覆盖分母为 0、重复引用、品牌别名重叠、中文英文、大小写、全半角和空数据。
指标函数必须是纯函数，LLM 不得参与或修改数值计算。
运行 analysis 测试，输出指标口径、边界处理和测试结果。
```

**提交信息：** `feat(analysis): calculate deterministic monitoring metrics`

---

## 13. Task 11：统一 Agent LLM 客户端 `[P][B][H]`

**目标：** 通过 OpenAI-compatible 配置提供结构化输出、重试、审计和脱敏能力。

**修改文件：**

- `backend/app/geo_monitoring/agents/llm.py`
- `backend/app/geo_monitoring/agents/schemas.py`
- `backend/app/geo_monitoring/agents/prompts.py`
- `backend/tests/geo_monitoring/agents/test_llm.py`

### 需要你操作

- 在 `.env` 中配置 `AGENT_LLM_BASE_URL`、`AGENT_LLM_API_KEY`、`AGENT_LLM_MODEL`。
- 确认是否允许执行真实 LLM smoke test；默认只跑 mock 测试。

### 由我操作

- 封装 LLM 客户端。
- 增加结构化输出 Schema、Prompt 版本和解析修复逻辑。
- 用 mock 覆盖异常和成功路径。

### 步骤

- [ ] 封装 async OpenAI-compatible client，不在业务代码直接实例化 SDK。
- [ ] 定义情感、推荐意图、风险、洞察摘要等 Pydantic 输出 Schema。
- [ ] 结构化解析失败时最多修复一次；仍失败则记录 Agent 执行失败，不伪造结果。
- [ ] Prompt 模板版本化，并将模板版本写入 execution input metadata。
- [ ] 输入裁剪到可配置上限；日志不打印完整答案批次和密钥。
- [ ] 用 mock 覆盖超时、限流、非法 JSON、字段缺失和成功响应。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/agents/test_llm.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 11：实现统一 Agent LLM 客户端和结构化输出能力。
允许修改 backend/app/geo_monitoring/agents/llm.py、schemas.py、prompts.py 和 backend/tests/geo_monitoring/agents/test_llm.py。
禁止修改指标计算、迁移、worker、API、Settings 和 frontend。
请先写 mock 测试覆盖成功结构化输出、超时、限流、非法 JSON、字段缺失、修复一次仍失败和日志脱敏。
实现 OpenAI-compatible async client 封装，业务代码不得直接实例化 SDK。
不得发起真实 LLM 请求，不得输出 AGENT_LLM_API_KEY。
运行 test_llm.py，输出 Prompt 版本、错误处理策略和测试结果。
```

**提交信息：** `feat(agent): add openai compatible llm client`

---

## 14. Task 12：LangGraph 分析 Agent `[S][B]`

**前置：** Task 10、11 已合并。

**目标：** 以可恢复节点编排完成数据准备、指标汇总、LLM 洞察和结果持久化。

**修改文件：**

- `backend/app/geo_monitoring/agents/graph.py`
- `backend/app/geo_monitoring/agents/nodes.py`
- `backend/app/geo_monitoring/services/analysis.py`
- `backend/tests/geo_monitoring/agents/test_graph.py`

### 需要你操作

- 确认无有效答案时是否只记录 skipped execution，还是仍生成空分析结果；建议记录 skipped 且不调用 LLM。

### 由我操作

- 实现 LangGraph 节点和分析 service。
- 确保确定性指标由 Task 10 函数产生，LLM 只生成语义标签和洞察。
- 增加图编排测试和幂等测试。

### 图节点

1. `load_run_data`：只加载 success 答案，生成不可变输入 DTO。
2. `calculate_metrics`：调用 Task 10 纯函数。
3. `classify_answers`：批量调用 LLM 获取结构化标签。
4. `generate_insights`：生成平台差异、竞品差距、来源特征和风险摘要。
5. `persist_results`：事务性 upsert 分析结果和 execution 审计。

### 规则

- 无有效答案时不调用 LLM，分析以 skipped 结束并说明原因。
- 单个平台 LLM 失败不阻塞其他平台；最终状态可为 `partial_success`。
- 图节点只传递可序列化 state，不传递 Session、HTTP client 或密钥。
- 同一 run 重跑分析必须幂等，保留 execution 历史但覆盖当前聚合结果。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/agents/test_graph.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 12：实现 LangGraph 分析 Agent。
允许修改 backend/app/geo_monitoring/agents/graph.py、nodes.py、backend/app/geo_monitoring/services/analysis.py 和 backend/tests/geo_monitoring/agents/test_graph.py。
禁止修改确定性指标口径、LLM client 底层封装、迁移、采集 worker、报告、frontend。
请先写测试覆盖无有效答案跳过 LLM、单平台 LLM 失败部分成功、重跑幂等、execution 历史保留和 state 可序列化。
实现 load_run_data、calculate_metrics、classify_answers、generate_insights、persist_results 节点。
运行 test_graph.py，输出图节点职责、幂等策略和测试结果。
```

**提交信息：** `feat(agent): orchestrate monitoring analysis graph`

---

## 15. Task 13：分析 Actor 与分析 API `[S][B]`

**目标：** 采集完成后触发分析，并提供看板、趋势和 Agent 执行查询接口。

**修改文件：**

- `backend/app/worker/actors/analysis.py`
- `backend/app/geo_monitoring/api/analysis.py`
- `backend/app/geo_monitoring/api/dashboard.py`
- `backend/tests/worker/test_analysis_actor.py`
- `backend/tests/geo_monitoring/test_dashboard_api.py`

### 需要你操作

- 确认看板和趋势 API 第一版只服务后端验收，不开发前端页面。

### 由我操作

- 实现分析 actor、手工触发 API、查询 API。
- 增加 worker 和 API 测试。

### API

- [ ] `POST /api/geo-monitoring/runs/{id}/analyze` 手工触发或重跑。
- [ ] `GET /api/geo-monitoring/runs/{id}/analysis` 获取平台指标和洞察。
- [ ] `GET /api/geo-monitoring/runs/{id}/agent-executions` 获取执行审计。
- [ ] `GET /api/geo-monitoring/projects/{id}/dashboard` 获取最新汇总。
- [ ] `GET /api/geo-monitoring/projects/{id}/trends` 按指标、平台和时间范围查询趋势。
- [ ] 运行所有采集任务进入终态后自动发送一次分析消息。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/worker/test_analysis_actor.py backend/tests/geo_monitoring/test_dashboard_api.py -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 13：实现分析 Actor 和分析查询 API。
允许修改 backend/app/worker/actors/analysis.py、backend/app/geo_monitoring/api/analysis.py、api/dashboard.py、backend/tests/worker/test_analysis_actor.py 和 backend/tests/geo_monitoring/test_dashboard_api.py。
禁止修改 LangGraph 节点内部实现、指标口径、迁移、采集 adapter、报告和 frontend。
请先写测试覆盖采集终态后自动触发一次分析、手工重跑、运行分析查询、agent executions 查询、dashboard 最新汇总和 trends 筛选。
API 路径使用 /api/geo-monitoring，响应保持统一 code/message/data 结构。
运行 analysis actor 和 dashboard API 测试，输出接口清单和测试结果。
```

**提交信息：** `feat(analysis): expose analysis workflow and dashboard APIs`

---

## 16. Task 14：创建调度与报告库表 `[S][B][M]`

**目标：** 增加持久化调度配置和报告元数据。

**修改文件：**

- `backend/alembic/versions/*_geo_monitoring_0004_schedule_report.py`
- `backend/tests/test_migrations.py`

### 需要你操作

- 如需在真实服务器数据库验证迁移，由你确认执行窗口和备份策略。

### 由我操作

- 编写迁移测试。
- 创建并审查调度和报告迁移。
- 确保 cron、报告路径和唯一约束满足后续 service 使用。

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

### 专用 Cursor 提示词

```text
请执行 V2 Task 14：创建调度与报告数据库迁移。
只允许修改 backend/alembic/versions 下新建的 0004 schedule report revision 和 backend/tests/test_migrations.py。
禁止修改 scheduler service、report service、API、Settings、frontend 或已有迁移。
请先写迁移测试，再创建一个 Alembic revision，包含 geo_monitor_schedule 和 geo_report。
迁移必须有稳定命名约束、完整 downgrade，并避免报告路径接受绝对路径。
不要对真实共享数据库执行破坏性 downgrade，除非用户明确确认。
输出 revision id、测试结果和迁移风险。
```

**提交信息：** `feat(db): add monitoring schedule and report schema`

---

## 17. Task 15：独立 APScheduler 进程 `[P]`

**目标：** 从数据库同步调度配置，到期后幂等创建监测运行。

**修改文件：**

- `backend/app/scheduler/main.py`
- `backend/app/scheduler/jobs.py`
- `backend/app/geo_monitoring/services/schedules.py`
- `backend/app/geo_monitoring/api/schedules.py`
- `backend/tests/scheduler/`

### 需要你操作

- 确认本地或服务器运行 scheduler 的方式：独立进程、Windows 任务、systemd 或容器。
- 如需要真实时间触发 smoke test，由你确认测试项目和触发时间。

### 由我操作

- 实现 scheduler 入口、job 同步、调度 service 和 API。
- 用冻结时间测试 cron、时区、misfire 和幂等。

### 步骤

- [ ] 独立命令启动 scheduler，不嵌入 FastAPI 多 worker 进程。
- [ ] 每 `SCHEDULER_POLL_SECONDS` 同步启用的数据库调度。
- [ ] job 使用 `schedule_id + planned_fire_time` 作为幂等键，避免多实例重复创建 run。
- [ ] 明确 misfire 行为：默认只补一次，不补历史全部漏跑。
- [ ] 创建运行时写 `trigger_type=schedule`、`triggered_by=<schedule_id>`。
- [ ] 提供调度 CRUD、启停和手工立即运行 API。
- [ ] 使用冻结时间测试时区、夏令时、misfire、重复触发。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/scheduler -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 15：实现独立 APScheduler 调度进程和调度 API。
允许修改 backend/app/scheduler/main.py、jobs.py、backend/app/geo_monitoring/services/schedules.py、api/schedules.py 和 backend/tests/scheduler。
禁止修改迁移、采集 Actor、分析 Agent、报告模块、frontend。
请先写冻结时间测试覆盖 cron、时区、misfire、重复触发、启停和手工立即运行。
scheduler 必须作为独立命令运行，不嵌入 FastAPI 多 worker 进程。
运行 scheduler 测试，输出启动命令、幂等键策略和测试结果。
```

**提交信息：** `feat(schedule): run monitoring schedules in dedicated process`

---

## 18. Task 16：报告生成与本地存储 `[P]`

**目标：** 从分析结果生成可下载的 Markdown 和 HTML 报告，并管理本地文件生命周期。

**修改文件：**

- `backend/app/geo_monitoring/reports/renderer.py`
- `backend/app/geo_monitoring/reports/storage.py`
- `backend/app/worker/actors/report.py`
- `backend/app/geo_monitoring/api/reports.py`
- `backend/app/geo_monitoring/templates/report/`
- `backend/tests/geo_monitoring/reports/`

### 需要你操作

- 确认 `REPORT_STORAGE_DIR` 指向的本地或服务器目录可写。
- 如报告目录需要持久化、备份或权限调整，由你在服务器侧处理。

### 由我操作

- 实现报告渲染、存储、actor 和 API。
- 确保路径安全、HTML 转义和文件生命周期测试。

### 步骤

- [ ] 使用 Jinja2 模板渲染项目摘要、平台指标、竞品差距、Prompt 表现、来源统计和 Agent 洞察。
- [ ] 报告路径使用 `project_id/run_id/report_id.ext`，数据库只保存相对路径。
- [ ] 写入临时文件后原子 rename，计算 SHA-256 和文件大小。
- [ ] 只允许通过 report id 下载，不接受用户输入的任意文件路径。
- [ ] 支持创建、列表、状态、下载和删除 API。
- [ ] 每日清理超过 `REPORT_RETENTION_DAYS` 且无保留标记的报告。
- [ ] HTML 转义原始答案内容，防止存储型 XSS。

### 验证

```powershell
backend/.venv/Scripts/python -m pytest backend/tests/geo_monitoring/reports -q
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 16：实现报告生成、存储、Actor 和报告 API。
允许修改 backend/app/geo_monitoring/reports/renderer.py、storage.py、backend/app/worker/actors/report.py、backend/app/geo_monitoring/api/reports.py、backend/app/geo_monitoring/templates/report 和 backend/tests/geo_monitoring/reports。
禁止修改迁移、调度器、分析指标口径、采集 adapter、frontend。
请先写测试覆盖 Markdown/HTML 渲染、HTML 转义、路径穿越防护、原子写入、checksum、下载、删除和过期清理。
报告数据库只保存相对路径，API 只通过 report id 下载。
运行 reports 测试，输出报告格式、存储策略和测试结果。
```

**提交信息：** `feat(report): generate and store monitoring reports`

---

## 19. Task 17：后端端到端、可观测性与安全 `[S][B][M]`

**目标：** 验证完整后端业务链路，并补齐上线前必须具备的运行保障。

**修改文件：**

- `backend/app/core/logging.py`
- `backend/app/main.py`
- `backend/tests/e2e/`
- `backend/tests/`
- `README.md`

### 需要你操作

- 确认是否允许使用 `.env` 连接服务器 PostgreSQL/Redis/Nacos 做后端 smoke test。
- 确认真实平台和真实 LLM smoke test 是否启用；默认只使用 mock。
- 如发现服务器服务不可达，由你处理网络、账号或服务状态。

### 由我操作

- 编写后端 e2e/mock 测试。
- 增加 health/ready、结构化日志和安全测试。
- 不开发或验证 frontend。

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
- [ ] `/api/geo-monitoring/health` 检查进程；`/api/geo-monitoring/ready` 检查数据库、Redis，必要时提供 Nacos 检查结果。
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
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini heads
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head --sql
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 17：补齐后端端到端测试、可观测性和安全检查。
允许修改 backend/app/core/logging.py、backend/app/main.py、backend/tests/e2e、backend/tests 和 README.md 中的后端运行说明。
禁止修改 frontend，不运行 npm 命令，不新增前端页面。
请先写后端 e2e/mock 测试，覆盖项目配置、mock 采集、分析、报告、调度、取消、失败重试和分析重跑。
增加 health/ready、结构化日志和敏感信息泄漏测试。
运行后端全量 pytest、alembic heads 和 upgrade head --sql，输出覆盖范围、测试结果和未执行的真实服务 smoke test。
```

**提交信息：** `test: cover monitoring backend mvp end to end`

---

## 20. Task 18：后端部署、发布与回滚 `[S][B][M][H]`

**目标：** 提供可重复部署的 API、worker、scheduler 后端进程，并验证迁移和文件存储策略。

**修改文件：**

- `Dockerfile`
- `docker-compose.yml`
- `.env.example`
- `README.md`
- `CLAUDE.md`

### 需要你操作

- 确认服务器 PostgreSQL、Redis、Nacos 的备份、账号、网络和权限。
- 执行或批准真实环境数据库迁移。
- 配置真实 API key、LLM key、报告存储目录和进程管理方式。
- 在发布窗口内执行最终 smoke test 或授权我按文档命令协助。

### 由我操作

- 更新后端部署文档和后端服务模板。
- 明确 API、worker、scheduler 的启动命令。
- 给出迁移、回滚和平台禁用策略。
- 不处理前端构建、前端发布和页面回归。

### 部署步骤

- [ ] 构建同一后端镜像，分别以 API、worker、scheduler 命令启动。
- [ ] 报告目录挂载持久卷；确认容器用户拥有写权限。
- [ ] PostgreSQL、Redis、Nacos 使用 `.env` 指向的服务器服务，不在本地 compose 中默认启动。
- [ ] 部署前备份数据库和报告目录。
- [ ] 先运行 `alembic upgrade head`，再启动 worker/scheduler，最后切换 API。
- [ ] 启动后执行 health、ready、创建测试项目、mock 运行和报告下载 smoke test。

### 回滚规则

- 应用回滚优先回滚镜像，不自动 downgrade 数据库。
- 只有确认新表无生产数据且旧应用无法兼容时，才人工执行逐版本 downgrade。
- 报告目录回滚只恢复元数据一致的备份，不覆盖新生成文件。
- 平台 API 异常时先设置对应 `*_ENABLED=false` 并重启 worker，不阻塞其他平台。
- Nacos 不可用时按启动配置决定 fail fast 或使用 `.env` 本地配置兜底；该策略必须在 Settings 中有测试覆盖。

### 最终验证

```powershell
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini current
backend/.venv/Scripts/python -m pytest backend/tests -q
docker compose config --quiet
```

### 专用 Cursor 提示词

```text
请执行 V2 Task 18：完善后端部署、发布和回滚说明。
允许修改 Dockerfile、docker-compose.yml、.env.example、README.md、CLAUDE.md 中与后端 API/worker/scheduler 相关的内容。
禁止修改 frontend，不添加前端构建、前端路由或前端发布步骤。
请将本地和部署默认服务改为使用 .env 指向的服务器 PostgreSQL、Redis、Nacos，并保留必要的后端进程启动模板。
补充迁移前备份、报告目录持久化、平台禁用、Nacos 不可用策略和回滚规则。
运行后端测试、alembic current 和 docker compose config --quiet，输出部署命令、回滚策略和需要用户人工执行的服务器操作。
```

**提交信息：** `chore: prepare monitoring backend mvp deployment`

---

## 21. 后端最终验收清单

### 数据库

- [ ] 新数据库可从空库升级到 `geo_monitoring_0004`。
- [ ] 现有 `geo_monitoring_0001` 数据可无损升级。
- [ ] 三个增量迁移都能单独 downgrade/upgrade。
- [ ] 没有通过 `create_all()` 绕过 Alembic 创建生产表。
- [ ] 真实服务器数据库执行迁移前已由你确认备份和窗口。

### 后端服务

- [ ] 本地运行统一使用 `.env` 中配置的服务器 PostgreSQL、Redis、Nacos。
- [ ] API、worker、scheduler 可独立启动。
- [ ] 五个平台只使用官方 API，默认全部禁用。
- [ ] 单个平台或单个密钥失败不会阻塞整个运行。
- [ ] 创建、采集、分析、报告和调度均具备幂等保护。
- [ ] 所有密钥和敏感响应经过脱敏。

### 后端 API

- [ ] 普通接口返回 `{ "code": 0, "message": "success", "data": {} }`。
- [ ] 分页接口 `data` 包含 `items`、`total`、`page`、`page_size`。
- [ ] 对外路径统一使用 `/api/geo-monitoring`；如保留旧路径，必须有测试证明兼容。
- [ ] health/ready 可区分进程存活、数据库、Redis、Nacos 状态。

### 工程质量

- [ ] 后端全量测试通过。
- [ ] `alembic heads` 只有一个 head。
- [ ] `alembic upgrade head --sql` 可生成完整 SQL。
- [ ] `git diff --check` 无空白错误。
- [ ] `.env`、密钥、数据库数据、报告文件、`.codegraph/` 未提交。
- [ ] 主 Agent 对每个并行分支完成代码审查，未直接信任 Subagent 自报结果。

### 暂不验收

- [ ] `frontend` 目录下的页面、路由、类型、mock、构建和端到端测试。
- [ ] 前端部署、前端 Nginx 配置、前端用户交互体验。
- [ ] 真实平台付费采集 smoke test，除非你明确开启并确认费用风险。

### 交付记录

主 Agent 在最终 PR 描述中列出：

1. 数据库迁移 revision 和回滚方式。
2. 新增环境变量及默认值，特别是 PostgreSQL、Redis、Nacos 的配置项。
3. 平台适配器启用方式和官方 API 限制。
4. API、worker、scheduler 的启动命令。
5. 自动化测试结果和未执行的真实平台 smoke test。
6. 报告目录的持久化、备份和清理策略。
7. 明确说明本阶段未包含 `frontend` 实现。
