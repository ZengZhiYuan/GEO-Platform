# AI 应用监测系统技术开发文档

> 文档版本：V2.0
> 更新时间：2026-06-16
> 产品阶段：后端 MVP 实施架构
> 适用范围：本版本只规划 `backend` 目录下的 MVP 功能实现，`frontend` 目录暂不纳入开发、测试和验收
> 当前代码基线：`main` 分支，已完成配置域和运行落库骨架
> 数据库策略：保留 `geo_monitoring_0001`，后续只使用 Alembic 增量迁移
> 平台策略：仅接入厂商官方 API；没有合规官方 API 或未配置凭据的平台默认禁用
> 本地运行环境：统一使用 `.env` 中配置的服务器 PostgreSQL、Redis、Nacos，不再要求本地 Docker 启动这些中间件

---

## 1. 文档目的

本文档是 AI 应用监测平台的技术权威文档，用于统一以下内容：

1. 当前仓库已经实现的能力；
2. 后端 MVP 尚需建设的能力；
3. 目标架构、数据模型、状态机和接口契约；
4. 平台采集、确定性指标、LangGraph Agent、调度和报告的工程边界；
5. 环境变量、测试、部署、安全和验收要求。

具体开发顺序、Cursor 操作方式、串并行关系和逐步验收命令见：

```text
docs/AI应用监测_MVP_Cursor实施任务V2.md
```

本文档不再提供独立“一键建表 SQL”。数据库结构以 SQLAlchemy Model 和 Alembic 增量迁移为唯一事实来源，避免 SQL、ORM 与迁移历史三套定义漂移。

本版本不定义前端页面、前端路由、前端测试、前端构建和前端部署要求。后续需要前端时，应另行拆分任务并独立更新本文档。

---

## 2. 产品目标与范围

### 2.1 后端 MVP 闭环

```text
监测项目与品牌配置
  → Prompt 集版本化与激活
  → 选择可用官方 API 平台
  → 创建 MonitorRun 和 Prompt×Platform 查询任务
  → Dramatiq 并发采集回答与引用
  → 原始响应、标准回答和引用入库
  → 规则优先的品牌/竞品识别
  → SQL/Python 计算确定性指标
  → LangGraph 多 Agent 生成语义分析与建议
  → 保存平台分析、指标快照和趋势数据
  → APScheduler 定时创建运行
  → 生成 Markdown/HTML 报告并保存到本地或后续配置的持久化目录
  → 后端 API 提供配置、运行、答案、分析、趋势、调度和报告查询能力
```

### 2.2 单次运行参考规模

- 默认 Prompt 数：50；
- 平台上限：5；
- 默认期望查询任务：`50 × 5 = 250`；
- 实际任务数按启用 Prompt 与启用平台动态计算；
- 任一平台失败不得阻塞其他平台；
- 单个平台和整体均需计算数据完整度。

### 2.3 MVP 不包含

- 用户、角色、租户权限体系；
- 复杂审批流和人工标注平台；
- 平台 Web/App 浏览器模拟采集；
- 非官方平台代理或逆向接口；
- 分布式多实例 Scheduler；
- 对象存储和 CDN；
- 可视化拖拽式 Agent 编排；
- 计费和额度结算系统。
- `frontend` 目录下的页面、路由、类型、mock、构建和端到端测试；
- 前端部署、前端 Nginx 配置和前端用户交互体验验收。

---

## 3. 当前代码基线

### 3.1 当前目录

```text
backend/
├─ alembic/
│  └─ versions/20260615_0001-ai_monitoring_baseline.py
├─ app/
│  ├─ api/router.py
│  ├─ core/
│  │  ├─ config.py
│  │  ├─ database.py
│  │  ├─ exceptions.py
│  │  └─ response.py
│  ├─ geo_monitoring/
│  │  ├─ api.py
│  │  ├─ models.py
│  │  ├─ schemas.py
│  │  └─ services/
│  │     ├─ projects.py
│  │     ├─ brands.py
│  │     ├─ prompts.py
│  │     ├─ platforms.py
│  │     └─ runs.py
│  ├─ models/base.py
│  └─ workers/
│     ├─ broker.py
│     └─ worker.py
└─ tests/

frontend/                         # 已存在管理端壳层，本版本不纳入开发、测试和验收
```

### 3.2 已实现能力

| 领域 | 已实现内容 |
| --- | --- |
| 基础设施 | FastAPI、统一响应、SQLAlchemy、Alembic、PostgreSQL 配置、Redis/Dramatiq Broker |
| 项目 | 创建、查询、更新、软删除、状态筛选 |
| 品牌 | 目标品牌、竞品、候选品牌和品牌别名 CRUD |
| Prompt | PromptSet 版本、草稿编辑、激活、归档、checksum、Prompt CRUD |
| 平台 | 五个平台种子配置、查询和更新 |
| 运行 | 创建 MonitorRun、选择激活 PromptSet、选择启用平台 |
| 任务 | 在同一数据库事务内生成 Prompt×Platform QueryTask 笛卡尔积 |
| 测试 | 后端模型、服务、API 边界、迁移和文档边界测试 |

说明：前端壳层属于当前仓库已有内容，但 V2 后端 MVP 不继续扩展、测试或验收 `frontend` 目录。

### 3.3 当前 8 张业务表

1. `geo_monitor_project`
2. `geo_brand`
3. `geo_brand_alias`
4. `geo_prompt_set`
5. `geo_prompt`
6. `geo_ai_platform`
7. `geo_monitor_run`
8. `geo_query_task`

公共字段由 `BaseModel` 提供：

```text
id, created_at, updated_at, deleted_at, is_deleted,
tenant_id, created_by, updated_by
```

### 3.4 当前 API 边界

当前 OpenAPI 包含 17 个路径模板，其中业务前缀统一为 `/api/geo-monitoring`：

```text
GET    /api/health

GET    /api/geo-monitoring/platforms
GET    /api/geo-monitoring/platforms/{platform_code}
PUT    /api/geo-monitoring/platforms/{platform_code}

GET    /api/geo-monitoring/projects
POST   /api/geo-monitoring/projects
GET    /api/geo-monitoring/projects/{project_id}
PUT    /api/geo-monitoring/projects/{project_id}
DELETE /api/geo-monitoring/projects/{project_id}

GET    /api/geo-monitoring/projects/{project_id}/brands
POST   /api/geo-monitoring/projects/{project_id}/brands
GET    /api/geo-monitoring/brands/{brand_id}
PUT    /api/geo-monitoring/brands/{brand_id}
DELETE /api/geo-monitoring/brands/{brand_id}
GET    /api/geo-monitoring/brands/{brand_id}/aliases
POST   /api/geo-monitoring/brands/{brand_id}/aliases
PUT    /api/geo-monitoring/brand-aliases/{alias_id}
DELETE /api/geo-monitoring/brand-aliases/{alias_id}

GET    /api/geo-monitoring/projects/{project_id}/prompt-sets
POST   /api/geo-monitoring/projects/{project_id}/prompt-sets
GET    /api/geo-monitoring/prompt-sets/{prompt_set_id}
PUT    /api/geo-monitoring/prompt-sets/{prompt_set_id}
DELETE /api/geo-monitoring/prompt-sets/{prompt_set_id}
POST   /api/geo-monitoring/prompt-sets/{prompt_set_id}/activate
GET    /api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts
POST   /api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts
PUT    /api/geo-monitoring/prompts/{prompt_id}
DELETE /api/geo-monitoring/prompts/{prompt_id}

GET    /api/geo-monitoring/runs
POST   /api/geo-monitoring/runs
GET    /api/geo-monitoring/runs/{run_id}
GET    /api/geo-monitoring/runs/{run_id}/query-tasks
```

同一路径模板可承载多个 HTTP 方法，因此方法数量大于路径模板数量。

### 3.5 当前运行创建语义

`POST /runs` 当前只执行以下数据库行为：

1. 校验项目为 `active`；
2. 获取指定或当前激活 PromptSet；
3. 获取启用 Prompt；
4. 获取指定或全部启用平台；
5. 创建 `geo_monitor_run`；
6. 创建 Prompt×Platform 的 `geo_query_task`；
7. 提交事务。

当前不会：

- 向 Redis/Dramatiq 投递消息；
- 调用任何平台 API；
- 保存回答或引用；
- 执行指标或 Agent 分析；
- 生成报告。

因此当前 `analysis_status` 和 `report_status` 固定为 `skipped`。

---

## 4. 后端 MVP 目标架构

```mermaid
flowchart TB
    API --> PG[(PostgreSQL)]
    API --> REDIS[(Redis)]
    API --> NACOS[Nacos 配置/服务发现]

    API -->|提交采集 Actor| CQ[Dramatiq Collection Queue]
    CQ --> CW[Collection Worker]
    CW --> ADAPTER[Official Platform Adapters]
    ADAPTER --> DOU[火山方舟/豆包]
    ADAPTER --> QWEN[阿里云百炼/千问]
    ADAPTER --> HY[腾讯混元 API]
    ADAPTER --> DS[DeepSeek API]
    ADAPTER --> KIMI[Kimi API]
    CW --> PG

    CW -->|采集聚合完成| AQ[Dramatiq Analysis Queue]
    AQ --> AW[Analysis Worker]
    AW --> METRIC[Deterministic Metrics]
    AW --> GRAPH[LangGraph]
    METRIC --> PG
    GRAPH --> PG

    AW -->|分析完成| RQ[Dramatiq Report Queue]
    RQ --> RW[Report Worker]
    RW --> MD[Jinja2 Markdown]
    RW --> HTML[Jinja2 HTML]
    MD --> FILES[REPORT_STORAGE_DIR]
    HTML --> FILES
    RW --> PG

    SCHED[APScheduler 单实例进程] --> PG
    SCHED -->|创建并投递运行| REDIS
```

### 4.1 进程职责

| 进程 | 职责 | 横向扩展 |
| --- | --- | --- |
| FastAPI | 配置 CRUD、运行触发、结果查询、报告下载 | 可多实例 |
| Collection Worker | 调用官方 API、保存回答和引用 | 可多实例 |
| Analysis Worker | 指标计算、LangGraph、结果聚合 | 可多实例 |
| Report Worker | Markdown/HTML 生成 | 可多实例，建议独立队列 |
| Scheduler | 扫描到期计划并创建运行 | MVP 只允许单实例 |
| PostgreSQL | 业务数据、快照、调度规则 | 单主库 |
| Redis | Broker、Key 轮询、冷却标记、短期锁 | 单实例或托管服务 |
| Nacos | 后端运行所需的外部配置和服务发现基础 | 使用 `.env` 配置连接 |

### 4.2 工程原则

1. 数据库事务内禁止调用外部 API 或 LLM；
2. 采集、分析、报告必须是独立阶段；
3. 确定性指标只由 SQL/Python 计算；
4. LLM 输出必须通过 Pydantic Schema 校验；
5. 总控 Agent 不得修改程序计算的指标值；
6. 平台失败相互隔离；
7. 每个 Actor 必须幂等；
8. API Key 不入库、不写日志、不通过 API 返回；
9. 趋势只比较相同 PromptSet 版本；
10. 所有表变更通过 Alembic 增量迁移完成。
11. 本地运行、调试和联调统一使用 `.env` 中配置的服务器 PostgreSQL、Redis、Nacos。

---

## 5. 数据库增量设计

### 5.1 迁移策略

保留：

```text
geo_monitoring_0001
```

后续建议拆为：

```text
geo_monitoring_0002_collection
geo_monitoring_0003_analysis_metrics
geo_monitoring_0004_schedule_report
```

禁止修改已经存在的 `0001` 来追加后端 MVP 表。原因：

- `0001` 已成为当前仓库和环境的共同基线；
- 重写会破坏已应用数据库的迁移历史；
- 增量迁移更容易测试、回滚和代码审查。

### 5.2 `0002_collection` 表与字段

#### 修改 `geo_monitor_run`

新增：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `trigger_type` | VARCHAR | `manual`、`schedule`、`api` 等触发来源 |
| `triggered_by` | VARCHAR NULL | 用户、调度 ID 或系统来源摘要 |
| `total_tasks` | INTEGER | 本次运行期望任务数 |
| `succeeded_tasks` | INTEGER | 成功任务数 |
| `failed_tasks` | INTEGER | 失败任务数 |
| `cancelled_tasks` | INTEGER | 取消任务数 |
| `started_at` | TIMESTAMPTZ NULL | 开始采集时间 |
| `completed_at` | TIMESTAMPTZ NULL | 运行终态时间 |
| `error_summary` | TEXT NULL | 聚合错误摘要，必须脱敏 |

当采集链路上线后：

- 新建运行的 `analysis_status` 改为 `pending`；
- 新建运行的 `report_status` 默认 `pending` 或按请求设置为 `skipped`；
- `collection_status` 从 `pending` 进入 `running`。

#### 修改 `geo_query_task`

新增：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `attempt_count` | INTEGER | 已尝试次数 |
| `max_attempts` | INTEGER | 最大尝试次数 |
| `queued_at` | TIMESTAMPTZ NULL | 入队时间 |
| `started_at` | TIMESTAMPTZ NULL | 开始调用平台时间 |
| `completed_at` | TIMESTAMPTZ NULL | 任务终态时间 |
| `last_error_code` | VARCHAR NULL | 稳定错误码 |
| `last_error_message` | TEXT NULL | 脱敏错误消息 |
| `provider_request_id` | VARCHAR NULL | 平台侧请求 ID |

#### 新建 `geo_answer`

| 字段 | 约束 |
| --- | --- |
| `query_task_id` | 唯一，关联 `geo_query_task.id`，级联删除 |
| `run_id` | 关联运行，建立 `(run_id, platform_code)` 索引 |
| `prompt_id` | 关联 Prompt |
| `platform_code` | 关联平台编码 |
| `model_name` | 实际模型名称 |
| `raw_text` | 平台返回的脱敏原始文本 |
| `normalized_text` | 标准化后用于指标计算的文本，非空 |
| `raw_response` | JSONB，保存脱敏原始响应 |
| `prompt_tokens` / `completion_tokens` / `total_tokens` | Token 统计 |
| `latency_ms` | 平台调用耗时 |
| `collected_at` | 实际采集时间 |

#### 新建 `geo_answer_citation`

| 字段 | 约束 |
| --- | --- |
| `answer_id` | 关联回答，级联删除 |
| `citation_rank` | 回答内引用顺序，与 answer 组成唯一键 |
| `title` / `url` | 引用标题和 URL |
| `domain` | 标准化域名 |
| `source_type` | 来源类型 |
| `citation_text` | 引用片段或证据文本 |
| `raw_json` | 单条引用脱敏原始数据 |

#### 新建 `geo_answer_brand_result`

| 字段 | 约束 |
| --- | --- |
| `answer_id` / `brand_id` | 组成唯一键 |
| `mentioned` | 是否提及 |
| `mention_count` | 提及次数 |
| `first_position` | 首次字符位置 |
| `sentiment` | 情感或倾向标签 |
| `context_json` | 命中上下文、证据句和算法补充信息 |

### 5.3 `0003_analysis_metrics` 表

#### `geo_agent_execution`

记录每个 Agent 节点的输入快照、结构化输出、模型、Prompt 版本、Token、状态和错误。唯一执行键建议为：

```text
run_id + platform_code + agent_code + schema_version
```

#### `geo_platform_analysis`

每个运行、每个平台一行，保存：

- 有效回答数和完整度；
- 品牌提及与首推指标；
- TOP 竞品；
- TOP 来源；
- Prompt 竞争力摘要；
- 平台改进建议；
- 状态和限制说明。

#### `geo_metric_snapshot`

用于整体、平台和 Prompt 级趋势：

```text
project_id, run_id, platform_code, prompt_id,
metric_code, numerator, denominator, metric_value,
metric_json, snapshot_at, prompt_set_version,
is_comparable, completeness_rate
```

#### `geo_prompt_competitiveness`

保存每个 `run × prompt × platform` 的目标品牌排名、竞品、位置标签、竞争力得分和证据。

#### `geo_source_stat`

保存运行级和平台级 Domain 聚合结果、引用次数、品牌相关次数、占比与排名。

### 5.4 `0004_schedule_report` 表

#### `geo_monitor_schedule`

```text
project_id, name, cron_expr, timezone, enabled,
next_run_at, last_run_at, misfire_policy,
created_at, updated_at
```

要求：

- 只允许引用同项目的 active PromptSet；
- `cron_expr` 创建和更新时必须校验；
- 计划触发必须使用唯一执行键防重复；
- 禁用计划后不得继续创建运行。

#### `geo_report`

```text
project_id, run_id, status, format, file_name,
relative_storage_path, file_size, checksum,
error_message, created_at, completed_at
```

状态：

```text
pending | generating | completed | failed
```

文件路径必须保存相对 `REPORT_STORAGE_DIR` 的相对路径，禁止把绝对服务器路径通过 API 返回。

---

## 6. 环境变量契约

### 6.1 基础运行变量

```env
APP_ENV=dev
APP_DEBUG=false
DATABASE_URL=postgresql+psycopg2://<user>:<password>@<server-host>:5432/geo_platform
REDIS_URL=redis://:<password>@<server-host>:6379/0

NACOS_SERVER_ADDRESSES=<server-host>:8848
NACOS_NAMESPACE=
NACOS_GROUP=DEFAULT_GROUP
NACOS_USERNAME=
NACOS_PASSWORD=
NACOS_CONFIG_DATA_ID=geo-platform-backend
```

规则：

- `.env` 是本地真实连接的唯一来源，代码和文档示例不得写入真实服务器地址、账号或密钥；
- 本地运行、调试和联调统一使用 `.env` 中配置的服务器 PostgreSQL、Redis、Nacos；
- 不再要求本地 Docker 启动 PostgreSQL、Redis、Nacos；
- 日志和异常只能显示脱敏后的连接目标摘要，不输出用户名、密码、token 或 API Key。

### 6.2 采集通用变量

```env
COLLECTION_REQUEST_TIMEOUT_SECONDS=60
COLLECTION_MAX_ATTEMPTS=3
COLLECTION_RETRY_BASE_SECONDS=2
COLLECTION_MAX_CONCURRENCY=10
COLLECTION_RAW_RESPONSE_ENABLED=true
```

### 6.3 官方平台变量

```env
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
```

规则：

- `*_ENABLED=true` 前必须通过凭据格式检查，真实探活只作为显式 smoke test；
- `*_API_KEYS` 使用英文逗号分隔，解析时去空格、去空值、去重；
- `YUANBAO_CREDENTIALS_JSON` 是 JSON 数组，每项包含 `secret_id` 和 `secret_key`；
- 日志只记录 `key_slot`，不得记录 Key、SecretId 或 SecretKey；
- 任何密钥都不得出现在日志、异常消息、数据库原始响应或 API 返回值中；
- 数据库只保存平台能力、非敏感模型参数和脱敏后的原始响应。

### 6.4 Agent 变量

```env
AGENT_LLM_BASE_URL=
AGENT_LLM_API_KEY=
AGENT_LLM_MODEL=
AGENT_LLM_TIMEOUT_SECONDS=90
AGENT_LLM_MAX_ATTEMPTS=2
```

Agent 统一走 OpenAI-compatible LLM SDK。LLM 只生成语义标签、解释和建议，不得覆盖确定性指标。

### 6.5 Scheduler 与报告变量

```env
SCHEDULER_ENABLED=false
SCHEDULER_TIMEZONE=Asia/Shanghai
SCHEDULER_POLL_SECONDS=30

REPORT_STORAGE_DIR=./data/reports
REPORT_PUBLIC_BASE_URL=
REPORT_RETENTION_DAYS=90
```

报告写入本地目录或后续配置的持久化目录。数据库只保存相对路径、checksum、大小和状态，不保存任意用户输入文件路径。

---

## 7. 官方平台 Adapter

### 7.1 统一输出

```python
@dataclass
class NormalizedCitation:
    rank: int
    title: str | None
    url: str | None
    source_name: str | None
    snippet: str | None
    raw: dict[str, Any]


@dataclass
class PlatformResponse:
    platform_code: str
    model_name: str
    answer_text: str
    answer_markdown: str | None
    citations: list[NormalizedCitation]
    raw_response: dict[str, Any]
    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None
    finish_reason: str | None
    latency_ms: int
```

### 7.2 目标目录

```text
backend/app/geo_monitoring/adapters/
├─ base.py
├─ factory.py
├─ key_pool.py
├─ openai_compatible.py
├─ citation_normalizer.py
├─ doubao.py
├─ qwen.py
├─ yuanbao.py
├─ deepseek.py
└─ kimi.py
```

### 7.3 平台可用性规则

- Adapter 文件和契约测试可以存在；
- 没有官方凭据或官方能力不满足要求时，数据库中的平台必须保持 `enabled=false`；
- 运行创建时只能选择数据库启用且环境配置可用的平台；
- 启动时不得因为某个平台未配置而阻止整个 API 服务启动；
- 平台能力检查结果应出现在健康检查或平台详情中，但不得暴露秘密。

### 7.4 Key 池

Redis Key：

```text
geo:key-index:{platform_code}
geo:key-cooldown:{platform_code}:{slot}
```

选择算法：

1. 过滤处于冷却期的槽位；
2. Redis `INCR` 获取轮询序号；
3. 对可用槽位数量取模；
4. 401/403 将槽位冷却；
5. 429 退避并切换槽位；
6. 所有槽位不可用时任务失败并记录稳定错误码。

---

## 8. 采集任务与状态机

### 8.1 Actor

```text
collect_query_task(query_task_id)
aggregate_collection(run_id)
analyze_run(run_id)
generate_report(report_id)
```

### 8.2 QueryTask 状态

```text
pending → queued → running → success
                           ↘ failed
pending/queued/running → cancelled
```

Actor 开始前必须使用条件更新抢占任务：

```sql
UPDATE geo_query_task
SET status = 'running', started_at = NOW()
WHERE id = :id AND status IN ('pending', 'queued')
```

受影响行数为 0 时直接退出，保证重复消息不重复调用平台。

### 8.3 MonitorRun 状态

```text
pending
  → collecting
  → analyzing
  → reporting
  → completed
```

异常分支：

```text
collecting/analyzing/reporting → partial_success | failed | cancelled
```

当至少一个平台有有效回答且部分平台失败时，运行可进入 `partial_success`；全部查询失败时进入 `failed`。

### 8.4 事务边界

正确：

```text
短事务抢占任务
→ 关闭事务
→ 调用外部 API
→ 短事务保存 Answer/Citation 并更新 QueryTask
→ 关闭事务
→ 聚合 Run
```

禁止：

```text
打开事务 → 调用平台 API/LLM → 长时间等待 → 提交
```

---

## 9. 回答、引用与标准化

### 9.1 保存规则

- `normalized_text` 必须是可用于规则分析的纯文本；
- `raw_response` 写入前必须移除请求头、鉴权字段和潜在密钥；
- 超过 `PLATFORM_RAW_RESPONSE_MAX_BYTES` 时保存截断标记；
- 同一 QueryTask 只允许一条 Answer；
- Citation 按回答内顺序保存；
- URL 标准化移除 fragment、统一 host 大小写、移除默认端口；
- 引用能力不存在时保存空列表和 `citation_supported=false`，不得推测来源。

### 9.2 有效回答

```text
QueryTask.status = success
AND Answer.normalized_text 去空白后非空
AND QueryTask 未取消
```

---

## 10. 确定性指标

### 10.1 品牌提及

```text
品牌提及回答数 = 提及目标品牌或有效别名的有效回答去重数
品牌提及率 = 品牌提及回答数 / 有效回答数
```

先执行 exact/contains/context 规则。只有歧义别名或无法确定的上下文进入 LLM 消解。

### 10.2 品牌首推

```text
品牌首推回答数 = 目标品牌推荐排名为 1 的有效回答数
品牌首推率 = 品牌首推回答数 / 有效回答数
提及后首推率 = 品牌首推回答数 / 品牌提及回答数
```

优先解析编号列表、Markdown 列表和明确顺序词；规则无法判断时才调用 LLM。

### 10.3 竞品与竞争力

竞品提及次数默认按“提及该竞品的回答数”统计，另存字符串原始出现次数。

透明评分：

| 排名 | 得分 |
| --- | ---: |
| 1 | 100 |
| 2 | 70 |
| 3 | 50 |
| 4 及以后 | 30 |
| 未提及 | 0 |

Prompt 总体竞争力为可用平台得分算术平均值，同时必须保留各平台原始排名。

### 10.4 引用来源

```text
来源占比 = Domain 引用次数 / 实际引用总数
品牌相关来源占比 = Domain 品牌相关引用次数 / 品牌相关引用总数
```

分母为 0 时返回 `null`，API 调用方应展示“未返回引用信息”，不得显示 0%。

### 10.5 数据完整度

```text
整体完整度 = 有效回答数 / expected_query_count
平台完整度 = 平台有效回答数 / 该平台期望任务数
```

### 10.6 趋势

必须保存：

```text
brand_mention_count
brand_mention_rate
brand_first_count
brand_first_rate
brand_first_among_mentions_rate
valid_answer_count
data_completeness_rate
citation_count
brand_related_citation_count
competitor_top1_count
prompt_competitiveness_avg
```

只有 `prompt_set_version` 相同的运行才设置 `is_comparable=true`。

---

## 11. LangGraph Agent

### 11.1 分层执行

```mermaid
flowchart TB
    START --> LOAD[加载 Run、品牌、回答、确定性指标]
    LOAD --> MAP{平台并行}
    MAP --> M[品牌提及语义消解]
    MAP --> F[首推语义兜底]
    MAP --> C[新竞品识别]
    MAP --> S[引用相关性分析]
    M --> I[平台改进建议]
    F --> I
    C --> I
    S --> I
    I --> P[保存平台分析]
    P --> G[总控汇总]
    G --> SNAP[保存快照与 result_json]
    SNAP --> END
```

### 11.2 Agent 输入约束

- 输入包含程序指标和必要证据，不传入全部无关原始响应；
- Prompt 必须版本化；
- 每个节点使用 Pydantic Structured Output；
- 温度默认 0；
- Schema 校验失败可重试一次；
- 第二次失败保存原始文本和错误，不覆盖确定性指标。

### 11.3 Agent 输出边界

Agent 可以输出：

- 歧义消解；
- 语义排名兜底；
- 新竞品候选；
- 引用相关性；
- 平台总结；
- P0/P1/P2 改进建议；
- 总体摘要。

Agent 不得输出或修改：

- 已计算的计数、比率、排名和完整度；
- 数据库主键；
- 平台任务状态；
- 未出现的引用 URL 或文章标题。

---

## 12. APScheduler 调度

### 12.1 运行方式

独立进程入口：

```powershell
python -m app.scheduler.main
```

MVP 使用 APScheduler 3.x，Scheduler 单实例运行。FastAPI 和 Worker 不内嵌调度器，避免多实例重复触发。

### 12.2 防重复

每次计划触发使用 PostgreSQL advisory lock，并生成：

```text
schedule:{schedule_id}:{planned_fire_time_iso}
```

该值写入运行创建幂等逻辑。重复扫描同一时间点时返回已有运行。

### 12.3 时间处理

- 数据库统一保存 UTC；
- Schedule 保存 IANA timezone；
- Cron 计算使用规则 timezone；
- API 返回 UTC 时间和项目 timezone，调用方按项目 timezone 展示；
- 夏令时重复或缺失时间必须有测试。

---

## 13. Markdown/HTML 报告

### 13.1 存储

MVP 使用本地目录：

```text
REPORT_STORAGE_DIR/
└─ {project_id}/
   └─ {run_id}/
      └─ {report_id}.{md|html}
```

写入流程：

1. 生成临时文件；
2. 校验文件非空；
3. 原子重命名到目标路径；
4. 更新 `geo_report`；
5. API 根据 report_id 下载，不接受任意文件路径。

### 13.2 报告内容

- 项目、PromptSet 版本、运行时间和数据完整度；
- 总体品牌提及和首推；
- 五平台对比；
- 竞品排行和 Prompt 竞争力；
- 引用来源 TOP10；
- 平台建议和总体建议；
- 趋势对比；
- 失败平台、缺失数据和 API 口径说明。

---

## 14. 目标 API

在保留现有 API 的基础上增加：

### 14.1 运行与采集

```text
POST /api/geo-monitoring/runs/{run_id}/enqueue
POST /api/geo-monitoring/runs/{run_id}/retry-failed
POST /api/geo-monitoring/runs/{run_id}/cancel
GET  /api/geo-monitoring/runs/{run_id}/answers
GET  /api/geo-monitoring/answers/{answer_id}
```

后端 MVP 可将 `POST /runs` 默认行为升级为“创建后提交采集任务”，但必须保留 Service 层 `create_run()` 与 `enqueue_run()` 的事务边界。

### 14.2 分析与指标

```text
POST /api/geo-monitoring/runs/{run_id}/analyze
GET  /api/geo-monitoring/runs/{run_id}/analysis
GET  /api/geo-monitoring/runs/{run_id}/metrics
GET  /api/geo-monitoring/projects/{project_id}/dashboard
GET  /api/geo-monitoring/projects/{project_id}/trends
```

### 14.3 调度

```text
GET    /api/geo-monitoring/projects/{project_id}/schedules
POST   /api/geo-monitoring/projects/{project_id}/schedules
GET    /api/geo-monitoring/schedules/{schedule_id}
PUT    /api/geo-monitoring/schedules/{schedule_id}
DELETE /api/geo-monitoring/schedules/{schedule_id}
POST   /api/geo-monitoring/schedules/{schedule_id}/trigger
```

### 14.4 报告

```text
POST /api/geo-monitoring/runs/{run_id}/reports
GET  /api/geo-monitoring/runs/{run_id}/reports
GET  /api/geo-monitoring/reports/{report_id}
GET  /api/geo-monitoring/reports/{report_id}/download
POST /api/geo-monitoring/reports/{report_id}/retry
```

---

## 15. 后端目标模块

```text
backend/app/geo_monitoring/
├─ api/                           # projects/brands/prompts/platforms/runs/answers/analysis/dashboard/schedules/reports
├─ models.py                      # 基础模型及后续增量模型镜像
├─ schemas.py                     # Pydantic 请求/响应契约
├─ repositories/                  # 数据库访问收敛层
├─ services/
│  ├─ projects.py
│  ├─ brands.py
│  ├─ prompts.py
│  ├─ platforms.py
│  ├─ runs.py
│  ├─ collection.py
│  ├─ metrics.py
│  ├─ analysis.py
│  ├─ schedules.py
│  └─ reports.py
├─ adapters/
├─ agents/
│  ├─ schemas.py
│  ├─ prompts.py
│  ├─ nodes.py
│  └─ graph.py
├─ reports/
│  ├─ renderer.py
│  └─ storage.py
└─ templates/report/

backend/app/worker/
└─ actors/
   ├─ collection.py
   ├─ analysis.py
   └─ report.py

backend/app/scheduler/
├─ main.py
└─ jobs.py
```

Worker 入口只负责导入并注册 Actor，不包含业务逻辑。若当前仓库仍使用 `backend/app/workers/worker.py` 作为入口，应在实现阶段保持兼容或在任务中显式迁移。

---

## 16. 前端范围

V2 后端 MVP 不开发、测试或验收 `frontend` 目录。当前仓库中已有的管理端壳层可以保留，但本阶段不得把前端页面、路由、类型、mock、构建、端到端测试或部署作为交付条件。

后续需要前端时，应单独拆分任务，并基于后端已稳定的 `/api/geo-monitoring` 契约补充页面设计、状态管理、Mock、测试和部署说明。

---

## 17. 测试策略

### 17.1 后端

- SQLite 单元测试：纯 Service、Schema、规则和状态机；
- PostgreSQL 集成测试：JSONB、部分唯一索引、迁移、advisory lock；
- Adapter 契约测试：使用 MockTransport/录制的脱敏 fixture，不访问真实付费 API；
- Worker 测试：StubBroker、重复消息、失败重试、聚合状态；
- Agent 测试：固定输入、Structured Output、数值不可篡改；
- 报告测试：Markdown/HTML 结构、路径安全、文件非空；
- Scheduler 测试：Cron、时区、防重复和禁用规则。

### 17.2 必跑命令

```powershell
backend/.venv/Scripts/python -m pytest backend/tests -q
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini heads
backend/.venv/Scripts/python -m alembic -c backend/alembic.ini upgrade head --sql
```

涉及 Redis/Nacos 连接的 smoke test 只能使用 `.env` 中配置的服务器地址。CI 和单元测试仍以 mock/fake 为主，不依赖共享服务器状态。

---

## 18. 部署与运行

### 18.1 本地进程

```powershell
# PostgreSQL、Redis、Nacos
# 已在服务器安装部署，连接信息来自本地 .env。
# 本地默认不启动 PostgreSQL/Redis/Nacos Docker 容器。

# API
backend/.venv/Scripts/python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000 --app-dir backend

# Worker
backend/.venv/Scripts/python -m dramatiq app.workers.worker --processes 1 --threads 8

# Scheduler，仅一个实例
backend/.venv/Scripts/python -m app.scheduler.main
```

### 18.2 发布顺序

1. 备份数据库；
2. 发布代码但保持新平台和 Scheduler 禁用；
3. 执行 Alembic 迁移；
4. 启动 API；
5. 启动 Worker；
6. 验证 PostgreSQL、Redis、Nacos ready；
7. 逐个平台启用；
8. 执行小规模 smoke run；
9. 启动 Scheduler；
10. 启用报告生成；
11. 执行 50×5 验收运行。

---

## 19. 安全与可观测性

### 19.1 安全

- `.env` 永不提交；
- API Key 和 LLM Key 只从环境或 Secret Manager 读取；
- 原始响应入库前递归脱敏；
- 报告下载按 report_id 映射，防止路径穿越；
- 日志不得包含完整 Prompt 以外的凭据、请求头或用户隐私；
- 平台管理 API 不返回密钥字段。

### 19.2 日志字段

```text
run_id, query_task_id, platform_code, prompt_id,
actor_name, retry_count, key_slot, latency_ms,
status, error_code
```

### 19.3 关键指标

- 运行成功率和部分成功率；
- 各平台查询成功率、P50/P95 延迟；
- 429、401/403、超时次数；
- Worker 队列积压；
- Agent Schema 失败次数；
- 报告生成时长；
- Scheduler 延迟和重复拦截次数。

---

## 20. 后端 MVP 验收标准

1. 保留现有 8 张表并通过增量迁移新增后端 MVP 表；
2. 至少一个具备官方凭据的平台完成真实采集闭环；
3. 其余未配置平台默认禁用，不影响系统启动；
4. 50×启用平台任务能够稳定投递、重试、聚合和查询；
5. 回答、引用和脱敏原始响应可追溯；
6. 品牌提及、首推、竞品、来源和完整度由程序计算；
7. LangGraph 输出通过 Schema 校验，且不能修改确定性指标；
8. 平台失败时运行可进入 `partial_success`；
9. 趋势只比较相同 PromptSet 版本；
10. APScheduler 不重复创建同一计划时间的运行；
11. Markdown/HTML 报告可生成、查询和下载；
12. API、worker、scheduler 可独立启动并完成后端闭环；
13. 后端测试、迁移验证和部署配置验证通过；
14. 日志、数据库和 API 响应中不存在明文密钥。

---

## 21. 官方 API 参考入口

平台 API 会变化，实施时必须以厂商最新官方文档为准，并在 Adapter 提交中记录验证日期：

- 火山方舟/豆包：`https://www.volcengine.com/docs/82379`
- 阿里云百炼/千问：`https://help.aliyun.com/zh/model-studio/`
- 腾讯混元：`https://cloud.tencent.com/document/product/1729`
- DeepSeek：`https://api-docs.deepseek.com/`
- Kimi：`https://platform.kimi.ai/docs/overview`

平台产品端与 API 模型端的结果可能不同。报告和页面必须明确标注“数据来自官方 API，不等同于 Web/App 产品端结果”。
