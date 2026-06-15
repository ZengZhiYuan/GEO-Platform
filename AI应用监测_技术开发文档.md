# AI 应用监测系统技术开发文档

> 文档版本：V1.0  
> 开发阶段：MVP  
> 基础仓库：`https://github.com/ZengZhiYuan/GEO-Platform`  
> 核心框架：FastAPI、React、PostgreSQL、Redis、Dramatiq、LangChain、LangGraph  
> 监测平台：豆包、通义千问、腾讯元宝、DeepSeek、Kimi  
> 单次规模：50 个 Prompt × 5 个平台 = 250 条查询任务

---

## 1. 文档目标

本文档用于指导研发团队在现有 GEO-Platform 开源仓库中新增“AI 应用监测”模块，完成以下工程闭环：

```text
项目与 Prompt 配置
  → 250 条 API 查询任务并发采集
  → 回答正文、原始响应、引用来源入库
  → LangGraph 多 Agent 并行分析
  → 确定性指标计算
  → 平台改进建议生成
  → 总控 Agent 汇总 JSON
  → 最新指标与趋势查询
  → HTML/PDF 报告生成
```

本文档重点覆盖：

1. 总体技术方案；
2. 与现有仓库的集成方式；
3. 多 Agent 工作流设计；
4. 数据库表设计；
5. 一键建表脚本；
6. API 开发规范；
7. 异步任务与定时任务；
8. PDF 报告生成；
9. 前端页面与趋势图；
10. 本地和生产部署流程；
11. 测试、验收和开发顺序。

本期暂不建设：用户权限、租户权限、日志审计、复杂审批和真实 Web/App 浏览器采集。

---

## 2. 现有仓库基线与复用策略

### 2.1 现有技术栈

GEO-Platform 当前主要技术结构：

```text
backend/
  FastAPI
  SQLAlchemy
  Alembic
  PostgreSQL
  Redis
  Dramatiq

frontend/
  React
  TypeScript
  Vite
  Ant Design
  Axios
  React Router
  Zustand
```

现有项目已经具备：

- FastAPI 路由和统一响应封装；
- SQLAlchemy Model、Schema、Service 分层；
- Alembic 数据库迁移；
- PostgreSQL 和 Redis Docker Compose；
- Dramatiq 后台 Worker；
- “大任务拆小任务、外部调用、短事务回写、聚合状态”的异步任务范式；
- React + Ant Design 管理端页面框架。

### 2.2 复用原则

| 现有能力                 | 新模块复用方式                              |
| -------------------- | ------------------------------------ |
| FastAPI              | 新增 `/api/geo-monitoring` 路由组         |
| SQLAlchemy BaseModel | 新表沿用统一主键、创建时间、软删除等字段                 |
| Alembic              | 正式环境优先使用迁移脚本建表                       |
| PostgreSQL           | 保存项目、Prompt、任务、回答、引用、指标和报告           |
| Redis + Dramatiq     | 采集任务、分析任务、报告任务异步执行                   |
| Worker 注册机制          | 在现有 `app.workers.worker` 中导入新增 Actor |
| 统一响应结构               | 继续使用 `code/message/data`             |
| React + Ant Design   | 新增“AI 应用监测”一级菜单                      |

### 2.3 不建议的改造方式

不建议直接将监测功能写入现有“写作任务”模块。原因：

- 内容生成和监测分析生命周期不同；
- 监测任务需要 50 × 5 的二维任务拆分；
- 分析结果需要跨平台聚合和历史趋势；
- 后续会扩展定时监测、异常告警和平台诊断。

应新增独立领域目录 `geo_monitoring`，仅复用基础设施。

---

## 3. 核心技术原则

### 3.1 先采集、后分析

采集任务只负责：

- 调用平台 API；
- 保存正文；
- 保存原始响应；
- 标准化并保存引用来源；
- 记录成功、失败、耗时和 Token。

采集任务不得直接生成最终分析结论。分析应在原始数据完整入库后独立执行，便于：

- 重复分析而不重复消耗平台查询额度；
- 调整分析 Prompt 后重新计算；
- 单独查看任一 Prompt 在任一平台的历史回答；
- 对失败 Agent 单独重试。

### 3.2 数值指标由程序计算

以下指标必须由 SQL/Python 确定性计算：

- 品牌提及回答数；
- 品牌提及率；
- 品牌首推回答数；
- 品牌首推率；
- 竞品提及次数；
- TOP10 引用源；
- 引用来源占比；
- 数据完整度；
- 趋势值。

LLM/Agent 主要负责：

- 歧义品牌消解；
- 推荐顺序语义判断的兜底；
- 列表外竞品识别；
- 引用内容与品牌相关性判断；
- 平台表现总结；
- 改进建议；
- 最终自然语言汇总。

总控 Agent 不得修改由程序计算的数值。

### 3.3 平台隔离

每个平台独立执行采集和分析。某个平台失败时：

- 其他平台继续运行；
- 运行状态可为 `partial_success`；
- 报告必须显示缺失数据和完整度；
- 用户可只重试失败平台或失败 Prompt。

### 3.4 Prompt 集版本化

趋势只比较同一 Prompt 集版本。修改 Prompt 正文、增删问题后必须创建新版本，并在趋势中标记不可直接比较。

### 3.5 API 数据口径提示

本系统通过平台 API 获取结果。API 结果可能与平台 Web/App 产品端不一致。引用来源能力也取决于具体 API、模型和联网搜索配置。

---

## 4. 总体系统架构

```mermaid
flowchart TB
    FE[React 管理端] --> API[FastAPI API]
    API --> PG[(PostgreSQL)]
    API --> REDIS[(Redis Broker)]

    API -->|创建监测运行| COLLECTQ[采集任务队列]
    COLLECTQ --> WORKER[Dramatiq Worker]
    WORKER --> ADAPTER[AI Platform Adapter]

    ADAPTER --> DOU[豆包 API]
    ADAPTER --> QWEN[千问 API]
    ADAPTER --> YB[元宝 API]
    ADAPTER --> DS[DeepSeek API]
    ADAPTER --> KIMI[Kimi API]

    WORKER -->|回答/引用入库| PG
    WORKER -->|采集完成| ANALYSISQ[分析任务队列]
    ANALYSISQ --> GRAPH[LangGraph 分析图]
    GRAPH --> PG

    GRAPH --> REPORTQ[报告任务队列]
    REPORTQ --> PDF[HTML + Playwright PDF]
    PDF --> FILES[报告文件目录/对象存储]
    PDF --> PG

    SCHEDULER[独立 Scheduler] -->|按计划创建运行| API
```

### 4.1 服务组成

| 服务                  | 职责                  | 是否独立进程         |
| ------------------- | ------------------- | --------------:|
| Frontend            | 配置、查看、趋势、报告         | 是              |
| FastAPI             | CRUD、运行触发、结果查询      | 是              |
| Dramatiq Worker     | 采集、分析、报告生成          | 是              |
| Scheduler           | 定时创建运行              | 是，且只允许 1 个实例   |
| PostgreSQL          | 业务数据和指标快照           | 是              |
| Redis               | Dramatiq Broker、短期锁 | 是              |
| Playwright Chromium | PDF 渲染              | 可内置于 Worker 镜像 |

---

## 5. 完整数据流

### 5.1 手动分析

```mermaid
sequenceDiagram
    participant U as 用户
    participant F as Frontend
    participant A as FastAPI
    participant P as PostgreSQL
    participant R as Redis/Dramatiq
    participant W as Worker
    participant L as LangGraph

    U->>F: 点击立即分析
    F->>A: POST /runs
    A->>P: 创建 run + 250 query_task
    A->>R: 投递 250 个采集任务
    A-->>F: 返回 run_id

    par 250 个任务受平台并发限制执行
        R->>W: collect_query_task
        W->>W: 调用对应平台 Adapter
        W->>P: 保存 answer + citations
        W->>P: 更新 query_task
    end

    W->>P: 聚合采集状态
    W->>R: 投递 analyze_run
    R->>W: 执行分析 Actor
    W->>L: invoke(run_id)
    L->>P: 保存 Agent 输出、平台分析、指标快照
    L->>P: 保存总控 JSON
    W-->>P: run = completed/partial_success
    F->>A: 轮询运行状态
    A-->>F: 返回最新结果
```

### 5.2 定时分析

定时任务不得复制业务逻辑。Scheduler 到点后调用与手动触发相同的 `RunService.create_and_enqueue()`：

```text
Scheduler
  → 查询到期规则
  → 获取 PostgreSQL 分布式锁/唯一执行键
  → 创建 trigger_type=schedule 的运行
  → 生成查询任务
  → 投递 Dramatiq
```

建议唯一键：

```text
schedule:{schedule_id}:{planned_fire_time_iso}
```

同一计划时间重复触发时返回已有运行，不重复创建。

---

## 6. LangChain 与 LangGraph 多 Agent 设计

## 6.1 为什么采用 LangGraph

本需求不是简单串行 Chain，而是包含：

- 5 个平台动态并行；
- 每个平台内部 4 个指标 Agent 并行；
- 平台改进建议必须等待本平台 4 个指标完成；
- 总控汇总必须等待 5 个平台完成；
- 需要状态持久化、失败恢复和结构化输出。

因此采用 LangGraph 的 `StateGraph + Send + fan-out/fan-in`，LangChain 用于：

- 模型适配；
- PromptTemplate；
- Structured Output；
- Tool 封装；
- 重试与模型调用参数统一。

## 6.2 两级并行图

```mermaid
flowchart TB
    START([START]) --> LOAD[加载 run 与平台列表]
    LOAD --> MAP{Send: 5 个平台并行}

    MAP --> P1[豆包平台子图]
    MAP --> P2[千问平台子图]
    MAP --> P3[元宝平台子图]
    MAP --> P4[DeepSeek 平台子图]
    MAP --> P5[Kimi 平台子图]

    P1 --> AGG[总控汇总 Agent]
    P2 --> AGG
    P3 --> AGG
    P4 --> AGG
    P5 --> AGG

    AGG --> SNAP[保存指标快照与最终 JSON]
    SNAP --> END([END])
```

单个平台子图：

```mermaid
flowchart TB
    S([START]) --> LOAD[加载该平台 50 条回答]
    LOAD --> BM[品牌提及 Agent]
    LOAD --> BF[品牌首推 Agent]
    LOAD --> CP[竞品提及 Agent]
    LOAD --> CS[引用源分析 Agent]

    BM --> IMP[平台改进建议 Agent]
    BF --> IMP
    CP --> IMP
    CS --> IMP

    IMP --> SAVE[保存平台分析]
    SAVE --> E([END])
```

### 6.2.1 严格依赖关系

| 节点           | 前置条件                 | 执行方式    |
| ------------ | -------------------- | ------- |
| 品牌提及 Agent   | 平台回答加载完成             | 与其他指标并行 |
| 品牌首推 Agent   | 平台回答加载完成             | 与其他指标并行 |
| 竞品提及 Agent   | 平台回答加载完成             | 与其他指标并行 |
| 引用源 Agent    | 平台回答加载完成             | 与其他指标并行 |
| 平台改进建议 Agent | 本平台 4 个指标 Agent 全部结束 | 串行      |
| 总控 Agent     | 5 个平台子图全部结束或明确失败     | 串行      |
| 报告生成         | 总控结果和指标快照保存成功        | 串行/独立异步 |

## 6.3 Agent 职责

### 6.3.1 品牌提及 Agent

输入：

- 目标品牌；
- 品牌别名；
- 50 条回答；
- Prompt 元数据。

处理：

1. 规则匹配目标品牌和非歧义别名；
2. 对“宋城”等歧义词调用 LLM 结合上下文判断；
3. 保存每条回答的证据句、位置和置信度；
4. 由指标服务计算计数和比率。

输出：

```json
{
  "platform_code": "qwen",
  "valid_answer_count": 50,
  "brand_mention_count": 31,
  "brand_mention_rate": 0.62,
  "mentioned_prompt_ids": [1, 2],
  "evidence": []
}
```

### 6.3.2 品牌首推 Agent

处理优先级：

1. Markdown/编号列表解析；
2. 推荐实体第一次出现顺序；
3. 明确语义词：“首选、优先、最推荐、第一选择”；
4. 无法确定时调用 LLM Structured Output；
5. 保存推荐顺序与证据。

必须同时提供两个口径：

```text
品牌首推率 = 首推目标品牌的有效回答数 / 有效回答总数
提及后首推率 = 首推目标品牌的回答数 / 提及目标品牌的回答数
```

### 6.3.3 竞品提及 Agent

输入：已配置竞品、候选竞品词典、回答文本。

输出：

- TOP 竞品及提及次数；
- 每个 Prompt × 平台的目标品牌排名；
- 同场竞品；
- 竞争位置标签；
- 证据片段；
- 新发现待确认竞品。

MVP 竞争力得分建议采用透明规则：

| 目标品牌表现   | 单回答得分 |
| -------- | -----:|
| 首推/排名 1  | 100   |
| 排名 2     | 70    |
| 排名 3     | 50    |
| 排名 4 及以后 | 30    |
| 未提及      | 0     |

单个 Prompt 总体竞争力：

```text
该 Prompt 在 5 个平台得分的算术平均值
```

必须同时展示原始排名，不能只展示分数。

### 6.3.4 引用源分析 Agent

处理：

- 标准化 URL；
- 提取 Domain；
- 合并同域名；
- 统计 TOP10；
- 根据标题、摘要、引用片段判断是否与目标品牌相关；
- 区分官方站、OTA、媒体、UGC、百科、其他。

口径：

```text
来源占比 = 某来源引用次数 / 实际返回的全部引用条数
品牌相关来源占比 = 某来源品牌相关引用次数 / 全部品牌相关引用条数
```

若某平台不返回引用信息，输出 `citation_available=false`，不得推测。

### 6.3.5 平台改进建议 Agent

每个平台独立执行，且必须等待本平台四类指标结果。

输入：

- 品牌提及与首推结果；
- 竞品结果；
- 引用来源结果；
- 该平台未命中 Prompt；
- 数据完整度。

输出必须为结构化 JSON：

```json
{
  "platform_code": "kimi",
  "summary": "...",
  "strengths": [],
  "problems": [],
  "priority_actions": [
    {
      "priority": "P0",
      "title": "补齐杭州夜游场景内容",
      "reason": "...",
      "target_prompts": ["P032"],
      "recommended_sources": ["官网", "携程"],
      "expected_metric": "brand_first_rate",
      "evidence": []
    }
  ],
  "data_limitations": []
}
```

约束：

- 每条建议必须关联指标或证据；
- 不得编造不存在的引用文章；
- 数据不完整时必须降低结论强度；
- 建议按 P0、P1、P2 排序。

### 6.3.6 总控 Agent

总控 Agent 输入 5 个平台结果和程序计算的总体指标，负责：

- 汇总平台差异；
- 识别共同问题；
- 汇总总体优先级建议；
- 生成最终 JSON；
- 生成报告摘要文本。

总控 Agent 禁止重新计算或修改指标值。最终 Schema 中确定性字段由程序注入。

## 6.4 LangGraph State 设计

```python
from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict


class GlobalAnalysisState(TypedDict, total=False):
    run_id: int
    project_id: int
    platform_codes: list[str]
    prompt_set_version: str
    target_brand: dict[str, Any]
    platform_results: Annotated[list[dict[str, Any]], operator.add]
    deterministic_metrics: dict[str, Any]
    final_result: dict[str, Any]
    errors: Annotated[list[dict[str, Any]], operator.add]


class PlatformAnalysisState(TypedDict, total=False):
    run_id: int
    project_id: int
    platform_code: str
    target_brand: dict[str, Any]
    answers: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    mention_result: dict[str, Any]
    first_result: dict[str, Any]
    competitor_result: dict[str, Any]
    citation_result: dict[str, Any]
    improvement_result: dict[str, Any]
    platform_result: dict[str, Any]
    errors: Annotated[list[dict[str, Any]], operator.add]
```

## 6.5 Graph 代码骨架

```python
from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph


def route_platforms(state: GlobalAnalysisState):
    return [
        Send(
            "platform_analysis",
            {
                "run_id": state["run_id"],
                "project_id": state["project_id"],
                "platform_code": platform_code,
                "target_brand": state["target_brand"],
            },
        )
        for platform_code in state["platform_codes"]
    ]


def build_platform_subgraph():
    graph = StateGraph(PlatformAnalysisState)
    graph.add_node("load_platform_data", load_platform_data)
    graph.add_node("brand_mention", brand_mention_node)
    graph.add_node("brand_first", brand_first_node)
    graph.add_node("competitor", competitor_node)
    graph.add_node("citation", citation_node)
    graph.add_node("improvement", improvement_node)
    graph.add_node("save_platform_result", save_platform_result_node)

    graph.add_edge(START, "load_platform_data")
    graph.add_edge("load_platform_data", "brand_mention")
    graph.add_edge("load_platform_data", "brand_first")
    graph.add_edge("load_platform_data", "competitor")
    graph.add_edge("load_platform_data", "citation")

    graph.add_edge(
        ["brand_mention", "brand_first", "competitor", "citation"],
        "improvement",
    )
    graph.add_edge("improvement", "save_platform_result")
    graph.add_edge("save_platform_result", END)
    return graph.compile()


def build_global_graph(checkpointer=None):
    graph = StateGraph(GlobalAnalysisState)
    graph.add_node("load_run", load_run_node)
    graph.add_node("platform_analysis", build_platform_subgraph())
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("save_snapshots", save_snapshots_node)

    graph.add_edge(START, "load_run")
    graph.add_conditional_edges("load_run", route_platforms, ["platform_analysis"])
    graph.add_edge("platform_analysis", "aggregate")
    graph.add_edge("aggregate", "save_snapshots")
    graph.add_edge("save_snapshots", END)
    return graph.compile(checkpointer=checkpointer)
```

说明：

- `platform_results` 使用 reducer 进行并行结果合并；
- 各节点只返回自己负责的 State 字段，避免并行写同一字段；
- 实际实现应在图编译测试中验证 LangGraph 当前版本的 fan-in 行为；
- 任何 Agent 异常需转换为结构化 `errors`，由平台结果标记 `partial_success`。

## 6.6 Checkpoint

建议接入 PostgreSQL Checkpointer：

```python
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = settings.LANGGRAPH_DATABASE_URL

with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()  # 首次部署执行一次
    graph = build_global_graph(checkpointer=checkpointer)
    graph.invoke(
        initial_state,
        config={"configurable": {"thread_id": f"geo-run-{run_id}"}},
    )
```

MVP 也可先不启用 Checkpointer，但建议保留接口。启用后可支持分析恢复和节点级追踪。

---

## 7. 结构化输出 Schema

建议所有 Agent 使用 Pydantic Schema 和模型 Structured Output。

```python
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    answer_id: int
    prompt_id: int
    quote: str


class BrandMentionAgentOutput(BaseModel):
    platform_code: str
    valid_answer_count: int
    brand_mention_count: int
    brand_mention_rate: float = Field(ge=0, le=1)
    evidence: list[Evidence]
    ambiguous_answer_ids: list[int] = []


class PlatformImprovementAction(BaseModel):
    priority: str
    title: str
    reason: str
    target_prompt_ids: list[int]
    recommended_sources: list[str]
    expected_metric: str
    evidence: list[Evidence]


class PlatformAnalysisOutput(BaseModel):
    platform_code: str
    data_completeness_rate: float
    metrics: dict
    top_competitors: list[dict]
    top_sources: list[dict]
    prompt_competitiveness: list[dict]
    improvement_actions: list[PlatformImprovementAction]
    limitations: list[str]
```

模型输出校验失败时：

1. 自动重试一次并追加“严格按照 Schema 输出”；
2. 仍失败则保存原始模型文本；
3. 节点标记失败；
4. 不影响确定性指标保存；
5. 平台分析可进入 `partial_success`。

---

## 8. 指标计算规范

## 8.1 有效回答

```text
API 调用成功
AND answer_text 非空
AND 未被取消
```

## 8.2 品牌提及

```text
品牌提及回答数 = 提及目标品牌或有效别名的有效回答去重数
品牌提及率 = 品牌提及回答数 / 有效回答数
```

整体指标使用 5 个平台全部有效回答作为分母；平台指标使用该平台有效回答作为分母。

## 8.3 品牌首推

```text
品牌首推回答数 = 目标品牌推荐排名为 1 的有效回答数
品牌首推率 = 品牌首推回答数 / 有效回答数
提及后首推率 = 品牌首推回答数 / 品牌提及回答数
```

## 8.4 竞品提及

```text
竞品提及次数 = 某竞品在回答中被识别为推荐/比较实体的回答数
```

默认按“回答数”而非字符串出现总次数排序，避免一条回答重复出现同一品牌造成放大。可额外保存 `raw_mention_count`。

## 8.5 引用来源

```text
TOP10 引用源 = 按 Domain 聚合 citation_count 后降序取前 10
来源占比 = citation_count / 本次实际返回的引用总数
品牌相关来源分布 = brand_related_count / 本次品牌相关引用总数
```

引用总数为 0 时：

- rate 返回 `null`；
- 页面显示“未返回引用信息”；
- 不返回 0%。

## 8.6 数据完整度

```text
数据完整度 = 有效回答数 / 期望查询任务数
```

平台完整度：有效回答数 / 50。  
整体完整度：有效回答数 / 250。

## 8.7 趋势指标

MVP 至少保存：

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

每个指标同时保存：

- run_id；
- project_id；
- platform_code，可为空代表整体；
- numerator；
- denominator；
- metric_value；
- Prompt 集版本；
- 数据完整度；
- 是否可比较。

---

## 9. 平台 API Adapter 设计

## 9.1 统一接口

```python
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class NormalizedCitation:
    rank: int
    title: str | None = None
    url: str | None = None
    source_name: str | None = None
    snippet: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


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


class PlatformAdapter(Protocol):
    def ask(self, *, prompt: str, key_slot: int | None = None) -> PlatformResponse:
        ...
```

## 9.2 目录结构

```text
backend/app/services/geo_monitoring/adapters/
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

## 9.3 Key 池

每个平台 10 个 Key 从环境变量读取，不存数据库明文：

```env
GEO_DOUBAO_API_KEYS=key1,key2,...,key10
GEO_QWEN_API_KEYS=key1,key2,...,key10
GEO_YUANBAO_API_KEYS=key1,key2,...,key10
GEO_DEEPSEEK_API_KEYS=key1,key2,...,key10
GEO_KIMI_API_KEYS=key1,key2,...,key10
```

MVP 轮询规则：

1. Redis `INCR geo:key-index:{platform}`；
2. 对 Key 数量取模；
3. 记录 `key_slot`，不记录 Key 明文；
4. 401/403：将该槽位临时标记不可用；
5. 429：指数退避后切换 Key；
6. 网络超时：Actor 自动重试；
7. 日志和异常不得输出 Key。

注意：多 Key 不代表可以绕过平台账户级配额或并发限制。并发仍以平台官方限制和实际压测为准。

## 9.4 联网搜索与引用来源

每个 Adapter 需要实现能力声明：

```python
class AdapterCapabilities(BaseModel):
    search_supported: bool
    citation_supported: bool
    streaming_supported: bool
```

平台接入测试必须记录：

- 是否成功开启搜索；
- 引用字段路径；
- 引用是否包含 URL；
- 是否只返回搜索摘要；
- 引用字段是否仅在流式模式返回。

不能假定所有 OpenAI 兼容接口都返回相同引用结构。每个平台需要独立 `extract_citations()`。

## 9.5 元宝接入说明

“元宝”需要根据实际购买的 API 产品确定 Adapter：

- 腾讯元器智能体 API；
- 腾讯云混元 API；
- 其他官方提供的元宝搜索接口。

统一对外仍使用 `platform_code=yuanbao`。实际端点、认证头、App/Assistant ID 和响应解析放在 `yuanbao.py` 及环境变量中，不在业务服务中写死。

---

## 10. 异步任务设计

## 10.1 任务拆分

一次运行创建：

```text
50 prompts × 5 platforms = 250 geo_query_task
```

每条任务独立保存状态，因此可以：

- 单条失败重试；
- 按平台限流；
- 单独查询答案；
- 断点续跑；
- 避免整批事务过长。

## 10.2 Dramatiq Actor

```text
create_run_and_tasks            同步 Service，不作为 Actor
collect_query_task              每个 Prompt × 平台一个 Actor
aggregate_collection_status     聚合采集状态
analyze_monitor_run             一个运行一个 Actor，内部执行 LangGraph
build_pdf_report                一个报告一个 Actor
```

示例：

```python
import dramatiq


@dramatiq.actor(
    max_retries=3,
    min_backoff=5_000,
    max_backoff=120_000,
    time_limit=180_000,
)
def collect_query_task(task_id: int) -> None:
    task = query_task_service.mark_running(task_id)
    try:
        adapter = adapter_factory.get(task.platform_code)
        result = adapter.ask(prompt=task.prompt_text_snapshot, key_slot=task.key_slot)
        answer_service.save_normalized_result(task, result)
        query_task_service.mark_success(task_id, result.latency_ms)
    except NonRetryablePlatformError as exc:
        query_task_service.mark_failed(task_id, exc.code, str(exc))
    except Exception:
        query_task_service.mark_retrying(task_id)
        raise
    finally:
        aggregate_collection_status.send(task.run_id)
```

### 10.2.1 数据库事务要求

沿用现有项目的短事务模式：

```text
短事务 1：读取任务、标记 running
外部阶段：调用平台 API，不持有数据库事务
短事务 2：保存回答、引用、任务状态
短事务 3：聚合运行状态
```

## 10.3 幂等

`geo_query_task.idempotency_key`：

```text
sha256(run_id + prompt_id + platform_code)
```

同时通过数据库唯一约束保证：

```text
UNIQUE(run_id, prompt_id, platform_code)
UNIQUE(query_task_id) on geo_answer
```

重复 Actor 消息不得创建重复答案。保存时使用查询 + 更新或 PostgreSQL Upsert。

## 10.4 采集完成触发分析

聚合服务规则：

```text
存在 pending/queued/running → collection_status=running
全部 success → collection_status=completed
部分 success + 无运行中 → collection_status=partial_success
全部 failed → collection_status=failed
```

当满足以下条件之一时自动投递分析：

- 所有查询任务已终态；
- 用户手动要求基于当前成功结果提前分析；
- 平台达到配置的最低有效回答阈值。

默认阈值建议：

```text
每个平台有效回答数 >= 40/50
整体有效回答数 >= 200/250
```

即使未达到阈值，也允许用户强制分析，但结果标记低完整度。

---

## 11. 定时任务设计

建议使用独立 APScheduler 进程，并使用 PostgreSQL JobStore。原因：

- 现有 Dramatiq 主要负责异步消费，不负责 Cron 管理；
- Scheduler 与 API/Worker 分离，避免多 Web 实例重复触发；
- 定时和手动统一调用同一个 Service。

目录：

```text
backend/app/scheduler/
├─ __init__.py
├─ main.py
└─ jobs.py
```

启动：

```bash
python -m app.scheduler.main
```

生产要求：

- Scheduler 只部署 1 个副本；
- 时区显式设置 `Asia/Shanghai`；
- 使用唯一执行键防止重复；
- 计划禁用后移除 Job；
- 项目 Prompt 集切换时更新计划绑定版本；
- Scheduler 仅负责创建运行，不直接调用平台 API。

---

## 12. 数据库总体设计

## 12.1 ER 关系

```mermaid
erDiagram
    GEO_MONITOR_PROJECT ||--o{ GEO_BRAND : contains
    GEO_BRAND ||--o{ GEO_BRAND_ALIAS : has
    GEO_MONITOR_PROJECT ||--o{ GEO_PROMPT_SET : owns
    GEO_PROMPT_SET ||--o{ GEO_PROMPT : contains
    GEO_MONITOR_PROJECT ||--o{ GEO_MONITOR_SCHEDULE : schedules
    GEO_PROMPT_SET ||--o{ GEO_MONITOR_RUN : used_by
    GEO_MONITOR_RUN ||--o{ GEO_QUERY_TASK : creates
    GEO_PROMPT ||--o{ GEO_QUERY_TASK : queried_by
    GEO_QUERY_TASK ||--|| GEO_ANSWER : produces
    GEO_ANSWER ||--o{ GEO_ANSWER_CITATION : contains
    GEO_ANSWER ||--o{ GEO_ANSWER_BRAND_RESULT : analyzed_as
    GEO_BRAND ||--o{ GEO_ANSWER_BRAND_RESULT : matched_to
    GEO_MONITOR_RUN ||--o{ GEO_AGENT_EXECUTION : executes
    GEO_MONITOR_RUN ||--o{ GEO_PLATFORM_ANALYSIS : aggregates
    GEO_MONITOR_RUN ||--o{ GEO_METRIC_SNAPSHOT : snapshots
    GEO_MONITOR_RUN ||--o{ GEO_PROMPT_COMPETITIVENESS : evaluates
    GEO_MONITOR_RUN ||--o{ GEO_SOURCE_STAT : aggregates
    GEO_MONITOR_RUN ||--o{ GEO_REPORT : generates
```

## 12.2 表清单

| 表                            | 核心用途                |
| ---------------------------- | ------------------- |
| `geo_monitor_project`        | 项目基本信息              |
| `geo_brand`                  | 目标品牌、竞品、候选品牌        |
| `geo_brand_alias`            | 品牌别名与歧义规则           |
| `geo_prompt_set`             | Prompt 集版本          |
| `geo_prompt`                 | 50 个问题              |
| `geo_ai_platform`            | 平台能力和模型配置，不存 Key 明文 |
| `geo_monitor_schedule`       | 定时规则                |
| `geo_monitor_run`            | 一次完整采集分析运行          |
| `geo_query_task`             | Prompt × 平台查询任务     |
| `geo_answer`                 | 回答正文与原始响应           |
| `geo_answer_citation`        | 引用来源                |
| `geo_answer_brand_result`    | 每条回答的品牌识别与排名        |
| `geo_agent_execution`        | Agent 节点输入输出和状态     |
| `geo_platform_analysis`      | 每个平台最终分析和建议         |
| `geo_metric_snapshot`        | 趋势指标快照              |
| `geo_prompt_competitiveness` | 每个 Prompt × 平台竞争力   |
| `geo_source_stat`            | 来源聚合统计              |
| `geo_report`                 | HTML/PDF 报告记录       |

## 12.3 核心设计说明

### 12.3.1 原始回答不可覆盖

不同运行的答案必须分别保存。不得以 `prompt_id + platform_code` 为唯一键覆盖历史；唯一关系是：

```text
run_id + prompt_id + platform_code
```

### 12.3.2 原始响应使用 JSONB

`raw_response` 用于保留平台特有字段，业务查询使用标准化列。不能只保存标准化文本，否则后续无法补解析引用字段。

### 12.3.3 引用来源独立表

一个回答可能有多个引用，必须使用一对多表，不能只用 JSON 塞进答案表。原始引用结构仍可保存在 `raw_json`。

### 12.3.4 指标快照不可只从最新结果动态计算

趋势查询应直接读取 `geo_metric_snapshot`，避免历史算法变化导致旧趋势随代码版本变化。需要重算时创建新的指标版本或重新生成快照。

---

## 13. 一键建表方案

随本文档提供：

```text
init_geo_monitoring.sql
init_geo_monitoring.py
init-geo-monitoring.sh
init-geo-monitoring.ps1
```

建议复制到仓库：

```text
GEO-Platform/
└─ scripts/
   ├─ init_geo_monitoring.sql
   ├─ init_geo_monitoring.py
   ├─ init-geo-monitoring.sh
   └─ init-geo-monitoring.ps1
```

### 13.1 Python 依赖

```bash
pip install psycopg2-binary python-dotenv
```

### 13.2 Linux/macOS 一键执行

```bash
cd GEO-Platform
bash scripts/init-geo-monitoring.sh
```

### 13.3 Windows PowerShell 一键执行

```powershell
cd GEO-Platform
powershell -ExecutionPolicy Bypass -File .\scripts\init-geo-monitoring.ps1
```

### 13.4 仅执行 SQL

```bash
psql "$DATABASE_URL" -f scripts/init_geo_monitoring.sql
```

### 13.5 与 Alembic 的关系

- 本脚本用于 MVP 初始化、快速联调和测试环境；
- 正式代码仍需创建对应 SQLAlchemy Models；
- 生产环境上线时优先生成 Alembic Migration；
- 不要在同一环境重复以“手工 SQL + Alembic 自动建表”两种方式管理同一版本；
- 若已用 SQL 初始化，需在 Alembic 中正确标记版本或使用幂等迁移。

完整 SQL 见本文档附录 A。

---

## 14. 后端目录设计

```text
backend/app/
├─ api/
│  └─ endpoints/
│     └─ geo_monitoring/
│        ├─ __init__.py
│        ├─ project.py
│        ├─ brand.py
│        ├─ prompt.py
│        ├─ platform.py
│        ├─ schedule.py
│        ├─ run.py
│        ├─ answer.py
│        ├─ analysis.py
│        ├─ trend.py
│        └─ report.py
├─ models/
│  ├─ geo_monitor_project.py
│  ├─ geo_brand.py
│  ├─ geo_prompt.py
│  ├─ geo_platform.py
│  ├─ geo_run.py
│  ├─ geo_answer.py
│  ├─ geo_analysis.py
│  └─ geo_report.py
├─ schemas/
│  └─ geo_monitoring/
│     ├─ project.py
│     ├─ brand.py
│     ├─ prompt.py
│     ├─ platform.py
│     ├─ schedule.py
│     ├─ run.py
│     ├─ answer.py
│     ├─ analysis.py
│     ├─ trend.py
│     └─ report.py
├─ services/
│  └─ geo_monitoring/
│     ├─ project_service.py
│     ├─ prompt_service.py
│     ├─ run_service.py
│     ├─ collection_service.py
│     ├─ answer_service.py
│     ├─ metric_service.py
│     ├─ trend_service.py
│     ├─ report_service.py
│     ├─ adapters/
│     └─ analysis/
│        ├─ state.py
│        ├─ schemas.py
│        ├─ graph.py
│        ├─ platform_subgraph.py
│        ├─ deterministic/
│        │  ├─ brand_matcher.py
│        │  ├─ recommendation_parser.py
│        │  ├─ competitor_counter.py
│        │  └─ citation_aggregator.py
│        ├─ agents/
│        │  ├─ brand_mention_agent.py
│        │  ├─ brand_first_agent.py
│        │  ├─ competitor_agent.py
│        │  ├─ citation_agent.py
│        │  ├─ improvement_agent.py
│        │  └─ supervisor_agent.py
│        └─ prompts/
├─ tasks/
│  ├─ geo_collection_tasks.py
│  ├─ geo_analysis_tasks.py
│  └─ geo_report_tasks.py
└─ scheduler/
   ├─ main.py
   └─ jobs.py
```

---

## 15. API 开发规范

## 15.1 路由前缀

```text
/api/geo-monitoring
```

## 15.2 统一响应

沿用现有项目：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

## 15.3 错误码建议

| code  | 含义                 |
| -----:| ------------------ |
| 40001 | 请求参数不合法            |
| 40002 | Prompt 集无有效 Prompt |
| 40003 | 平台列表为空或平台未启用       |
| 40401 | 项目不存在              |
| 40402 | 运行不存在              |
| 40403 | 回答不存在              |
| 40901 | 相同幂等键运行已存在         |
| 40902 | 项目已有运行中的任务         |
| 50001 | 平台 API 调用失败        |
| 50002 | 分析图执行失败            |
| 50003 | 报告生成失败             |
| 50004 | 引用结构解析失败           |

HTTP 状态码仍需正确使用 400、404、409、422、500、503。

## 15.4 项目与品牌接口

```text
POST   /projects
GET    /projects
GET    /projects/{project_id}
PUT    /projects/{project_id}

POST   /projects/{project_id}/brands
GET    /projects/{project_id}/brands
PUT    /brands/{brand_id}
DELETE /brands/{brand_id}

POST   /brands/{brand_id}/aliases
PUT    /brand-aliases/{alias_id}
DELETE /brand-aliases/{alias_id}
```

## 15.5 Prompt 接口

```text
POST   /projects/{project_id}/prompt-sets
GET    /projects/{project_id}/prompt-sets
POST   /prompt-sets/{prompt_set_id}/activate
POST   /prompt-sets/{prompt_set_id}/import
GET    /prompt-sets/{prompt_set_id}/prompts
POST   /prompt-sets/{prompt_set_id}/prompts
PUT    /prompts/{prompt_id}
DELETE /prompts/{prompt_id}
```

导入支持 `multipart/form-data`，返回：

```json
{
  "success_count": 48,
  "duplicate_count": 1,
  "error_count": 1,
  "errors": [
    {"row": 12, "message": "prompt_text 为空"}
  ]
}
```

## 15.6 平台接口

```text
GET  /platforms
PUT  /platforms/{platform_code}
POST /platforms/{platform_code}/test
GET  /platforms/{platform_code}/health
```

测试接口响应不得回传 API Key。

## 15.7 定时规则接口

```text
POST   /schedules
GET    /schedules
GET    /schedules/{schedule_id}
PUT    /schedules/{schedule_id}
POST   /schedules/{schedule_id}/enable
POST   /schedules/{schedule_id}/disable
DELETE /schedules/{schedule_id}
```

## 15.8 运行接口

```text
POST /runs
GET  /runs
GET  /runs/{run_id}
GET  /runs/{run_id}/progress
POST /runs/{run_id}/cancel
POST /runs/{run_id}/retry-failed
POST /runs/{run_id}/analyze
```

创建运行请求：

```json
{
  "project_id": 1,
  "prompt_set_id": 3,
  "platform_codes": ["doubao", "qwen", "yuanbao", "deepseek", "kimi"],
  "auto_analyze": true,
  "auto_generate_report": false,
  "force": false
}
```

返回：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "run_id": 1001,
    "run_no": "GEO-20260615-0001",
    "expected_query_count": 250,
    "status": "collecting"
  }
}
```

进度响应：

```json
{
  "run_id": 1001,
  "status": "collecting",
  "collection": {
    "total": 250,
    "pending": 20,
    "running": 10,
    "success": 215,
    "failed": 5,
    "progress": 0.88
  },
  "analysis": {
    "status": "pending",
    "agents": []
  },
  "report": {
    "status": "pending"
  }
}
```

## 15.9 查询任务与回答接口

```text
GET /runs/{run_id}/query-tasks
GET /runs/{run_id}/answers
GET /answers/{answer_id}
GET /prompts/{prompt_id}/answers
```

`GET /prompts/{prompt_id}/answers` 支持筛选：

```text
platform_code
start_time
end_time
run_id
page
page_size
```

回答详情必须返回：

- Prompt；
- 平台；
- 模型；
- 回答正文；
- 引用列表；
- 品牌识别结果；
- 竞品及排名；
- 运行时间；
- 原始响应仅在详情中按需返回。

## 15.10 分析接口

```text
GET /runs/{run_id}/analysis/overall
GET /runs/{run_id}/analysis/platforms
GET /runs/{run_id}/analysis/platforms/{platform_code}
GET /runs/{run_id}/analysis/prompts
GET /analysis/latest?project_id=1
```

## 15.11 趋势接口

```text
GET /metrics/trends
```

请求：

```text
project_id=1
metric_code=brand_mention_rate
platform_code=qwen       # 可不传，代表整体
start_date=2026-01-01
end_date=2026-12-31
prompt_set_version=V1
```

响应：

```json
{
  "metric_code": "brand_mention_rate",
  "platform_code": "qwen",
  "points": [
    {
      "run_id": 1001,
      "snapshot_at": "2026-06-01T09:00:00+08:00",
      "value": 0.56,
      "numerator": 28,
      "denominator": 50,
      "completeness_rate": 1.0,
      "prompt_set_version": "V1",
      "is_comparable": true
    }
  ]
}
```

## 15.12 报告接口

```text
POST /runs/{run_id}/reports
GET  /reports
GET  /reports/{report_id}
GET  /reports/{report_id}/html
GET  /reports/{report_id}/download
POST /reports/{report_id}/regenerate
```

报告生成必须异步，接口立即返回 `report_id`。

---

## 16. 最终分析 JSON 规范

总控结果保存到 `geo_monitor_run.result_json`，Schema 示例：

```json
{
  "schema_version": "1.0",
  "run": {
    "run_id": 1001,
    "run_no": "GEO-20260615-0001",
    "project_id": 1,
    "prompt_set_version": "V1",
    "started_at": "2026-06-15T09:00:00+08:00",
    "finished_at": "2026-06-15T09:12:00+08:00",
    "status": "completed",
    "expected_query_count": 250,
    "valid_answer_count": 247,
    "data_completeness_rate": 0.988
  },
  "target_brand": {
    "name": "杭州宋城千古情",
    "aliases": ["宋城千古情", "杭州宋城", "宋城景区"]
  },
  "overall_metrics": {
    "brand_mention_count": 135,
    "brand_mention_rate": 0.5466,
    "brand_first_count": 67,
    "brand_first_rate": 0.2713,
    "brand_first_among_mentions_rate": 0.4963
  },
  "top_competitors": [],
  "top_sources": [],
  "platforms": [
    {
      "platform_code": "doubao",
      "valid_answer_count": 50,
      "data_completeness_rate": 1.0,
      "metrics": {},
      "top_competitors": [],
      "top_sources": [],
      "prompt_competitiveness": [],
      "improvement": {}
    }
  ],
  "cross_platform_findings": [],
  "overall_actions": [],
  "limitations": [
    "本结果基于平台 API，不等同于 Web/App 页面结果"
  ],
  "agent_meta": {
    "analysis_model": "...",
    "prompt_version": "1.0"
  }
}
```

---

## 17. PDF 报告技术方案

## 17.1 生成方式

建议：

```text
React 打印专用报告页
  → 页面加载分析 JSON 和图表
  → 图表渲染完成设置 window.__REPORT_READY__ = true
  → Playwright 打开内部 URL
  → 等待 __REPORT_READY__
  → page.pdf(format='A4', print_background=True)
```

优点：

- 前端和 PDF 共用图表组件；
- ECharts 图表效果稳定；
- 可在线预览；
- 后续调整版式方便。

## 17.2 报告路由

```text
/frontend/report-print/{report_id}
```

该路由应：

- 使用固定 A4 样式；
- 不展示主站导航；
- 使用服务端签名或内部 Token，MVP 可仅内部网络访问；
- 数据加载和图表完成后设置 ready 标识；
- 对长表格分页；
- 对回答正文仅展示证据摘要。

## 17.3 报告章节

MVP 报告建议：

1. 封面；
2. 数据概览；
3. 品牌提及与首推核心指标；
4. 五平台对比；
5. TOP 竞品；
6. 每个 Prompt 的品牌竞争力摘要；
7. TOP10 引用来源；
8. 品牌相关来源分布；
9. 五个平台改进建议；
10. 总体改进建议；
11. 数据完整度与口径说明。

## 17.4 文件存储

MVP：

```text
backend/storage/reports/{project_id}/{run_id}/{report_no}.pdf
```

生产建议切换到对象存储，并在 `geo_report` 中保存对象 Key，不直接保存二进制到 PostgreSQL。

## 17.5 Playwright 代码骨架

```python
from pathlib import Path
from playwright.async_api import async_playwright


async def render_pdf(report_id: int, output_path: Path) -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        await page.goto(
            f"{settings.REPORT_RENDER_BASE_URL}/report-print/{report_id}",
            wait_until="networkidle",
        )
        await page.wait_for_function("window.__REPORT_READY__ === true")
        await page.pdf(
            path=str(output_path),
            format="A4",
            print_background=True,
            margin={"top": "12mm", "bottom": "12mm", "left": "10mm", "right": "10mm"},
        )
        await browser.close()
```

---

## 18. 前端技术设计

## 18.1 菜单

```text
AI 应用监测
├─ 监测总览
├─ 监测项目
├─ Prompt 管理
├─ 运行记录
├─ 平台分析
├─ 指标趋势
├─ 报告中心
└─ 定时设置
```

## 18.2 目录

```text
frontend/src/
├─ api/geoMonitoring.ts
├─ types/geoMonitoring.ts
├─ pages/geoMonitoring/
│  ├─ OverviewPage.tsx
│  ├─ ProjectPage.tsx
│  ├─ PromptSetPage.tsx
│  ├─ RunListPage.tsx
│  ├─ RunDetailPage.tsx
│  ├─ PlatformAnalysisPage.tsx
│  ├─ TrendPage.tsx
│  ├─ ReportPage.tsx
│  ├─ ReportPrintPage.tsx
│  └─ SchedulePage.tsx
└─ components/geoMonitoring/
   ├─ MetricCard.tsx
   ├─ MetricTrendChart.tsx
   ├─ PlatformComparisonChart.tsx
   ├─ CompetitorRankingChart.tsx
   ├─ SourceRankingChart.tsx
   ├─ PromptCompetitivenessTable.tsx
   └─ RunProgress.tsx
```

## 18.3 图表库

建议新增 ECharts：

```bash
npm install echarts echarts-for-react
```

趋势图要求：

- 横轴为运行时间；
- 支持总体和单平台切换；
- Tooltip 显示分子/分母；
- 低完整度点显示警告标识；
- Prompt 版本变化显示分割线；
- 不同版本默认不连线；
- 点击数据点进入运行详情。

## 18.4 运行状态刷新

MVP 使用轮询：

```text
运行中每 3 秒 GET /runs/{id}/progress
终态后停止
```

后续可升级 SSE/WebSocket，但本期不必要。

---

## 19. 依赖与版本建议

在 `backend/requirements.txt` 增加：

```text
langchain>=1.1,<2.0
langgraph>=1.0,<2.0
langgraph-checkpoint-postgres>=2.0
langchain-openai>=0.3
openai>=1.0
httpx>=0.27
psycopg[binary,pool]>=3.2
apscheduler>=3.10,<4.0
jinja2>=3.1
playwright>=1.50
orjson>=3.10
tldextract>=5.1
tenacity>=9.0
openpyxl>=3.1
```

注意：

- 实际提交前锁定可验证版本；
- 不要同时在多个模块直接依赖各厂商 SDK，尽量统一通过 Adapter；
- 若平台特有搜索能力必须使用官方 SDK，仅在对应 Adapter 内引入；
- LangGraph 和 LangChain 的版本需在测试环境固定后再进入生产。

---

## 20. 环境变量

示例 `backend/.env.geo.example`：

```env
# Database / Redis
DATABASE_URL=postgresql+psycopg2://postgres:postgres@localhost:5432/geo_platform
REDIS_URL=redis://localhost:6379/0
LANGGRAPH_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/geo_platform

# Analysis model：用于指标歧义判断、总结和建议
GEO_ANALYSIS_PROVIDER=qwen
GEO_ANALYSIS_MODEL=qwen-plus
GEO_ANALYSIS_API_KEY=replace_me
GEO_ANALYSIS_BASE_URL=https://replace-with-official-endpoint/v1
GEO_ANALYSIS_TEMPERATURE=0.1

# Doubao
GEO_DOUBAO_BASE_URL=https://replace-with-official-endpoint/v1
GEO_DOUBAO_MODEL=replace_me
GEO_DOUBAO_API_KEYS=key1,key2,key3,key4,key5,key6,key7,key8,key9,key10
GEO_DOUBAO_SEARCH_ENABLED=true

# Qwen
GEO_QWEN_BASE_URL=https://replace-with-official-endpoint/v1
GEO_QWEN_MODEL=replace_me
GEO_QWEN_API_KEYS=key1,key2,key3,key4,key5,key6,key7,key8,key9,key10
GEO_QWEN_SEARCH_ENABLED=true

# Yuanbao：按实际购买的腾讯 API 产品配置
GEO_YUANBAO_BASE_URL=https://replace-with-official-endpoint/v1
GEO_YUANBAO_MODEL=replace_me
GEO_YUANBAO_API_KEYS=key1,key2,key3,key4,key5,key6,key7,key8,key9,key10
GEO_YUANBAO_ASSISTANT_ID=
GEO_YUANBAO_SEARCH_ENABLED=true

# DeepSeek
GEO_DEEPSEEK_BASE_URL=https://replace-with-official-endpoint/v1
GEO_DEEPSEEK_MODEL=replace_me
GEO_DEEPSEEK_API_KEYS=key1,key2,key3,key4,key5,key6,key7,key8,key9,key10
GEO_DEEPSEEK_SEARCH_ENABLED=false

# Kimi
GEO_KIMI_BASE_URL=https://replace-with-official-endpoint/v1
GEO_KIMI_MODEL=replace_me
GEO_KIMI_API_KEYS=key1,key2,key3,key4,key5,key6,key7,key8,key9,key10
GEO_KIMI_SEARCH_ENABLED=true

# Limits
GEO_DEFAULT_PLATFORM_CONCURRENCY=2
GEO_QUERY_TIMEOUT_SECONDS=120
GEO_QUERY_MAX_RETRIES=3
GEO_MIN_PLATFORM_VALID_ANSWERS=40
GEO_MIN_OVERALL_VALID_ANSWERS=200

# Report
REPORT_RENDER_BASE_URL=http://frontend:3000
REPORT_STORAGE_PATH=/app/storage/reports
```

正式环境不要提交 `.env`，并确保日志过滤 `API_KEY`、`Authorization` 和原始认证头。

---

## 21. 接入现有路由与 Worker

## 21.1 路由

在现有 API Router 中注册：

```python
from app.api.endpoints.geo_monitoring.router import router as geo_monitoring_router

api_router.include_router(
    geo_monitoring_router,
    prefix="/geo-monitoring",
    tags=["AI应用监测"],
)
```

## 21.2 Worker

确保 Worker 入口导入 Actor：

```python
from app.tasks import geo_analysis_tasks  # noqa: F401
from app.tasks import geo_collection_tasks  # noqa: F401
from app.tasks import geo_report_tasks  # noqa: F401
```

否则 Dramatiq 无法发现 Actor。

---

## 22. 本地开发部署

## 22.1 获取代码

```bash
git clone https://github.com/ZengZhiYuan/GEO-Platform.git
cd GEO-Platform
```

## 22.2 启动 PostgreSQL 和 Redis

```bash
docker compose up -d postgres redis
docker compose ps
```

若现有 Compose 服务名不同，以仓库实际名称为准。

## 22.3 后端环境

```bash
cd backend
python -m venv .venv
```

Windows：

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

Linux/macOS：

```bash
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

## 22.4 初始化数据库

将附带脚本复制到 `scripts/` 后：

Windows：

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\init-geo-monitoring.ps1
```

Linux：

```bash
bash scripts/init-geo-monitoring.sh
```

## 22.5 启动 API

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 22.6 启动 Worker

```bash
cd backend
dramatiq app.workers.worker --processes 1 --threads 8
```

开发机初期建议线程数 4～8，平台级并发由应用层 Semaphore 再限制。

## 22.7 启动 Scheduler

```bash
cd backend
python -m app.scheduler.main
```

## 22.8 启动前端

```bash
cd frontend
npm install
npm run dev
```

---

## 23. 生产部署

## 23.1 推荐容器

```text
postgres
redis
backend-api
backend-worker
backend-scheduler
frontend
```

Worker 镜像中安装 Chromium 依赖，或单独创建 `report-worker`。

## 23.2 Docker Compose 建议

```yaml
services:
  backend-api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2
    env_file: ./backend/.env
    depends_on:
      - postgres
      - redis

  backend-worker:
    build: ./backend
    command: dramatiq app.workers.worker --processes 2 --threads 8
    env_file: ./backend/.env
    depends_on:
      - postgres
      - redis

  backend-scheduler:
    build: ./backend
    command: python -m app.scheduler.main
    env_file: ./backend/.env
    deploy:
      replicas: 1
    depends_on:
      - postgres
      - redis
```

生产注意：

- Scheduler 只能一个副本；
- 报告目录挂载持久卷；
- API 和 Worker 使用同一代码版本；
- 先执行 Alembic Upgrade，再滚动更新服务；
- 平台 Key 通过 Secret/环境变量注入；
- 设置容器时区或全部使用 UTC 存储、Asia/Shanghai 展示；
- 每个平台先从并发 1～2 开始压测；
- PostgreSQL 连接池需考虑 Worker 进程 × 线程总量。

## 23.3 上线顺序

```text
1. 备份数据库
2. 部署新镜像但不启动 Scheduler
3. 执行 Alembic Migration
4. 启动 API
5. 启动 Worker
6. 执行五个平台连通性测试
7. 使用 2 Prompt × 2 平台验证
8. 使用 5 Prompt × 5 平台验证
9. 启动 Scheduler
10. 使用完整 50 × 5 验证
```

---

## 24. 测试方案

## 24.1 单元测试

必须覆盖：

- 品牌别名匹配；
- “宋城”上下文消歧；
- 推荐列表排名解析；
- 竞品去重；
- URL 和 Domain 标准化；
- 比率分母为 0；
- 趋势版本可比性；
- 幂等键；
- Agent Structured Output 校验。

## 24.2 Adapter Contract Test

所有平台 Adapter 使用同一组测试：

```text
返回 platform_code
返回非空 answer_text
raw_response 可 JSON 序列化
latency_ms >= 0
citations 始终为 list
异常转换为统一错误类型
日志不包含完整 API Key
```

## 24.3 LangGraph 测试

- 四个指标节点是否并行；
- Improvement 是否等待四节点；
- 五个平台是否并行；
- 某平台失败是否仍进入总体汇总；
- Checkpoint 恢复；
- 重复执行是否覆盖同一 Agent Execution，而非产生错误快照；
- 总控是否保留程序注入指标。

## 24.4 集成测试分级

### 第一级

```text
2 Prompt × 2 平台 = 4 条任务
```

验证建表、Adapter、入库、分析、JSON。

### 第二级

```text
5 Prompt × 5 平台 = 25 条任务
```

验证跨平台、引用、平台建议和 PDF。

### 第三级

```text
50 Prompt × 5 平台 = 250 条任务
```

验证完整运行、失败重试、趋势快照和性能。

## 24.5 指标校验

抽样至少 20 条回答人工校验：

- 品牌提及准确率；
- 首推判断准确率；
- 竞品识别准确率；
- 引用来源归一准确率；
- 指标与 SQL 手工计算一致。

MVP 建议验收目标：

```text
明确品牌提及识别准确率 >= 95%
明确列表型首推判断准确率 >= 95%
总体品牌识别准确率 >= 90%
指标数值与数据库手工统计 100% 一致
```

---

## 25. 开发顺序与并行安排

## 25.1 必须串行的基础任务

```text
数据模型/字段口径
  → SQLAlchemy Model + Alembic
  → 基础 CRUD 和运行任务创建
  → 采集任务入库
  → 分析图接入真实数据
  → 报告生成
```

## 25.2 可并行开发

在数据库和 API Contract 确定后可开 4 个 Worktree：

| Worktree                      | 任务                               |
| ----------------------------- | -------------------------------- |
| `feature/geo-core`            | Model、Migration、项目/Prompt/运行 API |
| `feature/geo-adapters`        | 5 个平台 Adapter、Key 池、引用标准化        |
| `feature/geo-analysis`        | LangGraph、指标 Agent、总控 JSON       |
| `feature/geo-frontend-report` | 前端页面、趋势、打印报告                     |

可以先用 Mock Repository/JSON Fixture 并行开发；最终按顺序合并：

```text
geo-core
  → geo-adapters
  → 采集 Worker 联调
  → geo-analysis
  → geo-frontend-report
  → 全链路联调
```

## 25.3 建议里程碑

### M1：数据采集闭环

- 建表；
- 项目和 Prompt；
- 5 平台 Adapter；
- 250 条异步任务；
- 回答与引用入库；
- 原始回答查询。

### M2：多 Agent 分析闭环

- 品牌提及；
- 品牌首推；
- 竞品；
- 引用源；
- 平台建议；
- 总控 JSON；
- 手动与定时触发。

### M3：展示与报告

- 最新看板；
- 平台详情；
- 趋势图；
- PDF 报告；
- 完整验收。

---

## 26. 验收标准

### 26.1 数据采集

- [ ] 一次运行自动创建 250 条任务；
- [ ] 成功回答正文入库；
- [ ] 原始响应入库；
- [ ] API 返回引用时可正确入库；
- [ ] 任一 Prompt × 平台 × 运行可独立查询；
- [ ] 重复消息不产生重复答案；
- [ ] 失败任务可单独重试。

### 26.2 多 Agent

- [ ] 每个平台四个指标 Agent 并行；
- [ ] 平台建议 Agent 在四个指标完成后执行；
- [ ] 五个平台子图并行；
- [ ] 总控在平台结果汇合后执行；
- [ ] 输出符合 Schema 的 JSON；
- [ ] 确定性指标不被 LLM 修改；
- [ ] Agent 结果保存并可追溯证据。

### 26.3 前端与趋势

- [ ] 首页展示最新总体指标；
- [ ] 展示五平台指标对比；
- [ ] 可查看单个平台建议；
- [ ] 可查看 Prompt 竞争力；
- [ ] 每个核心指标有趋势图；
- [ ] 趋势显示数据完整度和 Prompt 版本；
- [ ] 点击趋势点进入对应运行。

### 26.4 报告

- [ ] 可异步生成 PDF；
- [ ] 包含核心指标和五平台对比；
- [ ] 包含竞品、引用和建议；
- [ ] 标明 API 口径与数据完整度；
- [ ] 可下载和重新生成。

---

## 27. 风险与处理

| 风险                 | 处理方案                                         |
| ------------------ | -------------------------------------------- |
| API 与 Web/App 结果不同 | 页面和报告明确标注数据口径                                |
| 平台 API 不返回引用       | 引用指标显示不可用，不推测                                |
| 同一平台响应结构变化         | Adapter 隔离 + 保存 raw_response + Contract Test |
| 10 个 Key 仍受账户级限流   | 平台级 Semaphore、指数退避、限并发                       |
| LLM 修改数值           | 指标由程序计算，总控只做解释                               |
| “宋城”误判             | 上下文匹配 + LLM 兜底 + 证据保存                        |
| Prompt 变更破坏趋势      | Prompt 集版本化、跨版本默认不连线                         |
| Scheduler 重复触发     | 单实例 + 唯一执行键 + DB/Redis 锁                     |
| PDF 图表未渲染完成        | `window.__REPORT_READY__` 后再打印               |
| 250 条任务并发过高        | 每个平台独立并发限制，Worker 总并发与平台并发分离                 |
| 分析模型故障             | 确定性指标仍保存；建议模块标记失败，可重跑分析                      |

---

## 28. 最终实施建议

第一阶段优先保证以下链路稳定：

```text
50 Prompt 配置
  → 5 平台 API 采集
  → 正文和引用入库
  → 原始回答可检索
```

第二阶段接入 LangGraph：

```text
平台并行
  → 四指标并行
  → 平台建议
  → 总控 JSON
```

第三阶段完成：

```text
最新看板
  → 平台详情
  → 趋势快照
  → PDF 报告
```

不要在第一期把主要时间投入权限、复杂审计、网页采集或报告视觉精修。MVP 成功的关键标准是：**同一批 50 个 Prompt 能稳定获取五个平台 API 回答、完整入库、重复分析，并输出可追溯的指标与平台建议。**

---

# 附录 A：PostgreSQL 一键建表 SQL

以下 SQL 与附件 `init_geo_monitoring.sql` 内容一致。

```sql
-- AI 应用监测模块 PostgreSQL 一键建表脚本
-- 适用：PostgreSQL 14+
-- 执行方式：psql "$DATABASE_URL" -f init_geo_monitoring.sql
-- 说明：MVP 暂不建设权限、日志审计和 API Key 明文存储。

BEGIN;

CREATE TABLE IF NOT EXISTS geo_monitor_project (
    id BIGSERIAL PRIMARY KEY,
    project_name VARCHAR(100) NOT NULL,
    industry VARCHAR(100) NOT NULL DEFAULT '文旅演艺',
    description TEXT,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    official_domain VARCHAR(255),
    report_title VARCHAR(255),
    report_subtitle VARCHAR(500),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_monitor_project_status CHECK (status IN ('active', 'disabled', 'archived'))
);

CREATE TABLE IF NOT EXISTS geo_brand (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    brand_name VARCHAR(255) NOT NULL,
    brand_type VARCHAR(20) NOT NULL DEFAULT 'competitor',
    official_domain VARCHAR(255),
    description TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_brand_project_name UNIQUE (project_id, brand_name),
    CONSTRAINT ck_geo_brand_type CHECK (brand_type IN ('target', 'competitor', 'candidate')),
    CONSTRAINT ck_geo_brand_status CHECK (status IN ('active', 'disabled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_geo_brand_one_target_per_project
    ON geo_brand(project_id)
    WHERE brand_type = 'target' AND is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS geo_brand_alias (
    id BIGSERIAL PRIMARY KEY,
    brand_id BIGINT NOT NULL REFERENCES geo_brand(id) ON DELETE CASCADE,
    alias_name VARCHAR(255) NOT NULL,
    match_mode VARCHAR(20) NOT NULL DEFAULT 'contains',
    is_ambiguous BOOLEAN NOT NULL DEFAULT FALSE,
    context_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_brand_alias UNIQUE (brand_id, alias_name),
    CONSTRAINT ck_geo_brand_alias_match_mode CHECK (match_mode IN ('exact', 'contains', 'context'))
);

CREATE TABLE IF NOT EXISTS geo_prompt_set (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    set_name VARCHAR(100) NOT NULL,
    version_no VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    prompt_count INTEGER NOT NULL DEFAULT 0,
    checksum VARCHAR(64),
    activated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_prompt_set_version UNIQUE (project_id, version_no),
    CONSTRAINT ck_geo_prompt_set_status CHECK (status IN ('draft', 'active', 'archived'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_geo_prompt_set_one_active_per_project
    ON geo_prompt_set(project_id)
    WHERE status = 'active' AND is_deleted = FALSE;

CREATE TABLE IF NOT EXISTS geo_prompt (
    id BIGSERIAL PRIMARY KEY,
    prompt_set_id BIGINT NOT NULL REFERENCES geo_prompt_set(id) ON DELETE CASCADE,
    prompt_code VARCHAR(64) NOT NULL,
    prompt_text TEXT NOT NULL,
    prompt_type VARCHAR(50) NOT NULL DEFAULT 'generic',
    scene_tag VARCHAR(100),
    contains_brand BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    sort_order INTEGER NOT NULL DEFAULT 0,
    content_hash VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_prompt_code UNIQUE (prompt_set_id, prompt_code)
);

CREATE TABLE IF NOT EXISTS geo_ai_platform (
    id BIGSERIAL PRIMARY KEY,
    platform_code VARCHAR(32) NOT NULL UNIQUE,
    platform_name VARCHAR(100) NOT NULL,
    adapter_type VARCHAR(50) NOT NULL DEFAULT 'openai_compatible',
    base_url VARCHAR(500),
    model_name VARCHAR(255),
    search_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    citation_supported BOOLEAN NOT NULL DEFAULT FALSE,
    max_concurrency INTEGER NOT NULL DEFAULT 2,
    timeout_seconds INTEGER NOT NULL DEFAULT 120,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    extra_config JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_ai_platform_max_concurrency CHECK (max_concurrency > 0),
    CONSTRAINT ck_geo_ai_platform_timeout CHECK (timeout_seconds > 0)
);

CREATE TABLE IF NOT EXISTS geo_monitor_schedule (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    prompt_set_id BIGINT NOT NULL REFERENCES geo_prompt_set(id),
    schedule_name VARCHAR(100) NOT NULL,
    cron_expr VARCHAR(100) NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'Asia/Shanghai',
    platform_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    auto_generate_report BOOLEAN NOT NULL DEFAULT FALSE,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    next_run_at TIMESTAMPTZ,
    last_run_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_monitor_run (
    id BIGSERIAL PRIMARY KEY,
    run_no VARCHAR(64) NOT NULL UNIQUE,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id),
    prompt_set_id BIGINT NOT NULL REFERENCES geo_prompt_set(id),
    trigger_type VARCHAR(20) NOT NULL DEFAULT 'manual',
    schedule_id BIGINT REFERENCES geo_monitor_schedule(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'pending',
    collection_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    analysis_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    report_status VARCHAR(30) NOT NULL DEFAULT 'pending',
    platform_codes JSONB NOT NULL DEFAULT '[]'::jsonb,
    expected_query_count INTEGER NOT NULL DEFAULT 0,
    success_query_count INTEGER NOT NULL DEFAULT 0,
    failed_query_count INTEGER NOT NULL DEFAULT 0,
    valid_answer_count INTEGER NOT NULL DEFAULT 0,
    data_completeness_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    previous_comparable_run_id BIGINT REFERENCES geo_monitor_run(id) ON DELETE SET NULL,
    result_json JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_monitor_run_trigger_type CHECK (trigger_type IN ('manual', 'schedule', 'retry')),
    CONSTRAINT ck_geo_monitor_run_status CHECK (status IN ('pending', 'collecting', 'analyzing', 'reporting', 'completed', 'partial_success', 'failed', 'cancelled')),
    CONSTRAINT ck_geo_monitor_run_stage_status_collection CHECK (collection_status IN ('pending', 'running', 'completed', 'partial_success', 'failed', 'cancelled')),
    CONSTRAINT ck_geo_monitor_run_stage_status_analysis CHECK (analysis_status IN ('pending', 'running', 'completed', 'partial_success', 'failed', 'skipped')),
    CONSTRAINT ck_geo_monitor_run_stage_status_report CHECK (report_status IN ('pending', 'running', 'completed', 'failed', 'skipped'))
);

CREATE TABLE IF NOT EXISTS geo_query_task (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    prompt_id BIGINT NOT NULL REFERENCES geo_prompt(id),
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    idempotency_key VARCHAR(128) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    key_slot INTEGER,
    retry_count INTEGER NOT NULL DEFAULT 0,
    request_json JSONB,
    response_http_status INTEGER,
    error_code VARCHAR(100),
    error_message TEXT,
    latency_ms INTEGER,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_query_task UNIQUE (run_id, prompt_id, platform_code),
    CONSTRAINT ck_geo_query_task_status CHECK (status IN ('pending', 'queued', 'running', 'success', 'failed', 'cancelled')),
    CONSTRAINT ck_geo_query_task_retry_count CHECK (retry_count >= 0)
);

CREATE TABLE IF NOT EXISTS geo_answer (
    id BIGSERIAL PRIMARY KEY,
    query_task_id BIGINT NOT NULL UNIQUE REFERENCES geo_query_task(id) ON DELETE CASCADE,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    prompt_id BIGINT NOT NULL REFERENCES geo_prompt(id),
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    model_name VARCHAR(255),
    answer_text TEXT NOT NULL,
    answer_markdown TEXT,
    answer_html TEXT,
    raw_response JSONB,
    finish_reason VARCHAR(100),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    answer_hash VARCHAR(64),
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_answer_citation (
    id BIGSERIAL PRIMARY KEY,
    answer_id BIGINT NOT NULL REFERENCES geo_answer(id) ON DELETE CASCADE,
    citation_rank INTEGER NOT NULL,
    title TEXT,
    url TEXT,
    canonical_url TEXT,
    domain VARCHAR(255),
    source_name VARCHAR(255),
    snippet TEXT,
    published_at TIMESTAMPTZ,
    is_brand_related BOOLEAN,
    brand_related_confidence NUMERIC(6,4),
    source_type VARCHAR(50),
    raw_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_answer_citation_rank UNIQUE (answer_id, citation_rank)
);

CREATE TABLE IF NOT EXISTS geo_answer_brand_result (
    id BIGSERIAL PRIMARY KEY,
    answer_id BIGINT NOT NULL REFERENCES geo_answer(id) ON DELETE CASCADE,
    brand_id BIGINT NOT NULL REFERENCES geo_brand(id),
    raw_mention VARCHAR(500),
    mentioned BOOLEAN NOT NULL DEFAULT FALSE,
    mention_count INTEGER NOT NULL DEFAULT 0,
    first_position INTEGER,
    recommendation_rank INTEGER,
    is_first_recommendation BOOLEAN,
    evidence_text TEXT,
    confidence NUMERIC(6,4),
    detection_method VARCHAR(30) NOT NULL DEFAULT 'rule',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_answer_brand_result UNIQUE (answer_id, brand_id),
    CONSTRAINT ck_geo_answer_brand_result_method CHECK (detection_method IN ('rule', 'llm', 'hybrid', 'manual'))
);

CREATE TABLE IF NOT EXISTS geo_agent_execution (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32),
    agent_code VARCHAR(64) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    schema_version VARCHAR(20) NOT NULL DEFAULT '1.0',
    input_snapshot JSONB,
    output_json JSONB,
    model_provider VARCHAR(100),
    model_name VARCHAR(255),
    prompt_version VARCHAR(50),
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_agent_execution_status CHECK (status IN ('pending', 'running', 'success', 'failed', 'skipped'))
);

CREATE TABLE IF NOT EXISTS geo_platform_analysis (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    valid_answer_count INTEGER NOT NULL DEFAULT 0,
    data_completeness_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    brand_mention_count INTEGER NOT NULL DEFAULT 0,
    brand_mention_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    brand_first_count INTEGER NOT NULL DEFAULT 0,
    brand_first_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    brand_first_among_mentions_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    top_competitors JSONB NOT NULL DEFAULT '[]'::jsonb,
    top_sources JSONB NOT NULL DEFAULT '[]'::jsonb,
    prompt_competitiveness_summary JSONB NOT NULL DEFAULT '[]'::jsonb,
    improvement_json JSONB,
    summary_json JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_platform_analysis UNIQUE (run_id, platform_code),
    CONSTRAINT ck_geo_platform_analysis_status CHECK (status IN ('pending', 'running', 'completed', 'partial_success', 'failed'))
);

CREATE TABLE IF NOT EXISTS geo_metric_snapshot (
    id BIGSERIAL PRIMARY KEY,
    project_id BIGINT NOT NULL REFERENCES geo_monitor_project(id) ON DELETE CASCADE,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32),
    prompt_id BIGINT REFERENCES geo_prompt(id) ON DELETE SET NULL,
    metric_code VARCHAR(100) NOT NULL,
    numerator NUMERIC(18,4),
    denominator NUMERIC(18,4),
    metric_value NUMERIC(18,6),
    metric_json JSONB,
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    prompt_set_version VARCHAR(50) NOT NULL,
    is_comparable BOOLEAN NOT NULL DEFAULT TRUE,
    completeness_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_prompt_competitiveness (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    prompt_id BIGINT NOT NULL REFERENCES geo_prompt(id),
    platform_code VARCHAR(32) NOT NULL REFERENCES geo_ai_platform(platform_code),
    target_mentioned BOOLEAN NOT NULL DEFAULT FALSE,
    target_rank INTEGER,
    target_first BOOLEAN,
    competitors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    position_label VARCHAR(30),
    competitiveness_score NUMERIC(8,4),
    evidence_json JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT uq_geo_prompt_competitiveness UNIQUE (run_id, prompt_id, platform_code)
);

CREATE TABLE IF NOT EXISTS geo_source_stat (
    id BIGSERIAL PRIMARY KEY,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    platform_code VARCHAR(32),
    domain VARCHAR(255) NOT NULL,
    source_name VARCHAR(255),
    source_type VARCHAR(50),
    citation_count INTEGER NOT NULL DEFAULT 0,
    brand_related_count INTEGER NOT NULL DEFAULT 0,
    share_rate NUMERIC(8,4) NOT NULL DEFAULT 0,
    rank_no INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT
);

CREATE TABLE IF NOT EXISTS geo_report (
    id BIGSERIAL PRIMARY KEY,
    report_no VARCHAR(64) NOT NULL UNIQUE,
    run_id BIGINT NOT NULL REFERENCES geo_monitor_run(id) ON DELETE CASCADE,
    report_name VARCHAR(255) NOT NULL,
    template_version VARCHAR(50) NOT NULL DEFAULT '1.0',
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    html_path TEXT,
    pdf_path TEXT,
    file_size BIGINT,
    summary_json JSONB,
    error_message TEXT,
    generated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    tenant_id BIGINT,
    created_by BIGINT,
    updated_by BIGINT,
    CONSTRAINT ck_geo_report_status CHECK (status IN ('pending', 'generating', 'completed', 'failed'))
);

-- 关键查询索引
CREATE INDEX IF NOT EXISTS idx_geo_brand_project_type ON geo_brand(project_id, brand_type) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_brand_alias_name ON geo_brand_alias(alias_name) WHERE enabled = TRUE AND is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_prompt_set_project_status ON geo_prompt_set(project_id, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_prompt_prompt_set_enabled ON geo_prompt(prompt_set_id, enabled, sort_order) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_schedule_project_enabled ON geo_monitor_schedule(project_id, enabled) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_run_project_created ON geo_monitor_run(project_id, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_run_status ON geo_monitor_run(status, created_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_query_task_run_status ON geo_query_task(run_id, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_query_task_platform_status ON geo_query_task(platform_code, status) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_answer_run_platform ON geo_answer(run_id, platform_code) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_answer_prompt_platform ON geo_answer(prompt_id, platform_code, collected_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_citation_domain ON geo_answer_citation(domain) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_brand_result_brand_mentioned ON geo_answer_brand_result(brand_id, mentioned) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_agent_run_platform ON geo_agent_execution(run_id, platform_code, agent_code) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_metric_trend ON geo_metric_snapshot(project_id, metric_code, platform_code, snapshot_at DESC) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_prompt_comp_run_prompt ON geo_prompt_competitiveness(run_id, prompt_id) WHERE is_deleted = FALSE;
CREATE INDEX IF NOT EXISTS idx_geo_source_stat_run_rank ON geo_source_stat(run_id, platform_code, rank_no) WHERE is_deleted = FALSE;

-- 平台基础数据。base_url/model_name 可由环境变量或管理接口覆盖。
INSERT INTO geo_ai_platform (
    platform_code, platform_name, adapter_type, search_enabled,
    citation_supported, max_concurrency, timeout_seconds, enabled
) VALUES
    ('doubao', '豆包', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE),
    ('qwen', '通义千问', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE),
    ('yuanbao', '腾讯元宝', 'tencent', FALSE, FALSE, 2, 120, TRUE),
    ('deepseek', 'DeepSeek', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE),
    ('kimi', 'Kimi', 'openai_compatible', FALSE, FALSE, 2, 120, TRUE)
ON CONFLICT (platform_code) DO UPDATE SET
    platform_name = EXCLUDED.platform_name,
    adapter_type = EXCLUDED.adapter_type,
    search_enabled = EXCLUDED.search_enabled,
    citation_supported = EXCLUDED.citation_supported,
    updated_at = NOW();

COMMIT;
```

---

# 附录 B：一键执行脚本说明

Python 执行入口：

```bash
python scripts/init_geo_monitoring.py
```

其实现逻辑：

1. 加载仓库根目录或 `backend/.env`；
2. 读取 `DATABASE_URL` 或 `SQLALCHEMY_DATABASE_URI`；
3. 将 SQLAlchemy URL 转换为 psycopg2 URL；
4. 一次事务执行 `init_geo_monitoring.sql`；
5. 成功后提交，失败自动回滚；
6. 终端只显示脱敏数据库地址。

完整脚本随文档提供：

```text
init_geo_monitoring.py
init-geo-monitoring.sh
init-geo-monitoring.ps1
```
