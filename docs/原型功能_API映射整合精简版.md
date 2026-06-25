# 原型功能 API 映射与缺口整合精简版

> 更新日期：2026-06-25  
> 整合来源：`docs/原型功能-API映射_v1.md`、`docs/原型功能_API映射与缺口清单.md`  
> 核对范围：`backend/app/geo_monitoring/api/`、`backend/app/geo_monitoring/schemas.py`、`backend/app/geo_monitoring/services/`、`backend/app/geo_monitoring/agents/nodes.py`、`backend/app/geo_monitoring/reports/renderer.py`

本文用于替代两份原型映射文档中的重复与冲突表述，作为当前项目最贴合的前后端对接基准。结论先行：

- 当前后端是以“项目配置 + 监测运行 run + 平台分析快照”为核心的 MVP 后端，已经能支撑创建项目、保存监测配置、启动采集、查看最新大盘、查看答案详情、生成报告。
- 原型是以“项目 + 时间范围 + 平台端筛选”为核心的页面级看板，很多页面需要一次返回聚合结果。当前后端更偏底层能力，前端可拼出部分效果，但会有 N+1 调用、口径分散和性能风险。
- 两份旧文档最大的歧义在平台端、趋势指标编码、竞品趋势、信源分类和对话记录聚合。本文统一采用当前代码实际实现作为基准。

## 1. 统一口径

| 主题 | 本文采用的统一描述 | 对接建议 |
| --- | --- | --- |
| API 前缀 | 业务接口主前缀为 `/api/geo-monitoring`，兼容前缀为 `/api/v1/geo-monitoring`；全局探针有 `/api/health`、`/api/ready`，监测域探针有 `/api/geo-monitoring/health`、`/api/geo-monitoring/ready`。 | 新页面优先使用 `/api/geo-monitoring`。 |
| 响应格式 | 除文件下载外，统一为 `{ code, message, data }`；分页 `data` 为 `{ items, total, page, page_size }`。 | 前端统一从 `data` 解包。 |
| 核心数据模型 | 后端以 `run_id` 为一次采集分析批次中心；`dashboard` 默认取最近已分析或已终态 run，也可指定 `run_id`。 | 页面“时间范围聚合”不能直接等同于 `dashboard`。 |
| 平台端 | 当前有普通平台码 `doubao/qwen/...`，也有 Aidso 平台端码 `aidso_doubao_web/app` 等；但 schema 中没有独立 `base_platform/endpoint_type/logo_url` 字段。 | 可以先把 Aidso 平台端码当展示键使用，长期建议补结构化平台端元数据。 |
| 大盘提及率字段 | `dashboard.summary.brand_mention_rate`、`platforms[].analysis.brand_mention_rate` 是已落地展示字段。 | 大盘 KPI 直接用该字段。 |
| 趋势 metric_code | 当前代码写入的目标品牌可见度趋势为 `brand_visibility`，不是旧文档中的 `brand_mention_rate`。同时写入 `brand_top1_mention_rate`、`brand_top3_mention_rate`、`citation_rate`、`source_coverage`、`recommendation_combined_rate`。 | 前端趋势先使用当前实际编码；如产品坚持 `brand_mention_rate`，后端应增加别名兼容。 |
| 竞品指标 | `summary_json.metrics.brand_metrics[]` 中有目标品牌和竞品的当前快照指标，包括 `mention_rate_percent`、`average_mention_rank`、`share_of_voice` 等。 | 可用于当前榜单；不能用于竞品历史趋势。 |
| 对话记录 | `/runs/{run_id}/answers` 是答案粒度，即 prompt × platform；不是“按 AI 问题聚合”的页面表。 | 原型表格需要新增聚合接口，避免前端全量拉取答案后自算。 |
| 信源分析 | 当前有答案引用 `citations[]` 和平台分析 `top_sources`；`source_type` 代码内主要映射 6 类。 | 原型 8 类信源需要统一字典和聚合接口。 |
| 报告与导出 | 报告支持 `md/html/pdf`；对话记录和信源页的 Excel 导出未落地。 | Excel 应作为独立导出端点或扩展报告格式。 |
| AI 生成 | 品牌词、竞品、监测问题的 AI 生成接口尚未实现；`prompt-library` 只是静态模板库。 | 创建向导可先用静态模板，原型体验需要补生成接口。 |

## 2. 当前接口能力地图

### 2.1 配置域

| 能力 | 已有接口 | 说明 |
| --- | --- | --- |
| 项目 CRUD | `GET/POST /projects`、`GET/PUT/DELETE /projects/{project_id}` | `status` 可改为 `active/disabled/archived`，但不等同独立“暂停监测”语义。 |
| 一站式监测配置 | `GET/PUT /projects/{project_id}/monitor-setup` | 当前创建向导和编辑配置最重要接口，覆盖品牌、品牌词、竞品、核心词、问题、默认平台。 |
| 品牌与别名 | `/projects/{project_id}/brands`、`/brands/{brand_id}/aliases` 等 | 可做细粒度编辑，但原型更适合使用 `monitor-setup` 整体保存。 |
| 核心词 | `/projects/{project_id}/core-keywords`、`/core-keywords/{keyword_id}` | 可支撑品类/核心关键词。 |
| Prompt 集与问题 | `/projects/{project_id}/prompt-sets`、`/prompt-sets/{id}/prompts`、`/prompts/{id}` | 支持问题集版本和激活。 |
| Prompt 模板库 | `GET /prompt-library` | 只能提供静态模板，不是 AI 生成。 |
| 平台列表 | `GET /platforms`、`GET/PUT /platforms/{platform_code}` | 返回 `platform_code/platform_name/adapter_type/search_enabled/citation_supported/extra_config`。 |

### 2.2 运行、采集、分析域

| 能力 | 已有接口 | 说明 |
| --- | --- | --- |
| 创建运行 | `POST /runs` | 可指定 `project_id/prompt_set_id/platform_codes/collection_source/aidso_thinking_enabled_by_platform`。 |
| 运行进度 | `GET /runs/{run_id}` | 返回阶段状态、任务数、有效答案数、完整度、错误摘要和 `progress_rate`。 |
| 运行任务 | `GET /runs/{run_id}/query-tasks` 或 `/tasks` | 支持按 `status/platform_code` 过滤。 |
| 答案列表与详情 | `GET /runs/{run_id}/answers`、`GET /answers/{answer_id}` | 详情包含原文、引用和品牌识别；未暴露 `raw_response_json`、问题文本和问题类型。 |
| 分析触发与结果 | `POST /runs/{run_id}/analyze`、`GET /runs/{run_id}/analysis` | 返回平台指标、竞品、信源、prompt 竞争力和 Agent 洞察。 |
| 项目大盘 | `GET /projects/{project_id}/dashboard?run_id=` | 当前是最新 run 或指定 run 的汇总，不支持 `start_at/end_at/platform_codes` 的页面级聚合。 |
| 大盘首屏总览 | `GET /projects/{project_id}/dashboard/overview?run_id=&platform_codes=&start_at=&end_at=` | 一次返回 KPI、平台表现、竞品/信源/问题预览；复用 P0-3/4/5 聚合服务。✅ 已覆盖 |
| 趋势 | `GET /projects/{project_id}/trends` | 支持单 `metric_code`、单 `platform_code`、时间范围和分页。 |

### 2.3 调度与报告域

| 能力 | 已有接口 | 说明 |
| --- | --- | --- |
| 定时调度 | `/projects/{project_id}/schedules`、`/schedules/{schedule_id}`、`enable/disable/trigger` | 后端已具备，原型六页未单独设计调度配置页。 |
| 报告生成 | `POST /runs/{run_id}/reports` | 同步生成 `md/html/pdf` 报告记录和文件。 |
| 报告下载 | `GET /reports/{report_id}/download` | 文件流下载。 |

## 3. 页面映射精简版

### 3.1 项目管理

当前可直接使用：

- `GET /projects` 获取项目分页列表。
- `GET /projects/{project_id}/monitor-setup` 获取品牌词、竞品、问题和默认平台。
- `GET /projects/{project_id}/dashboard` 获取最近运行状态和数据摘要。
- `PUT /projects/{project_id}` 更新项目基础信息或状态。
- `DELETE /projects/{project_id}` 删除项目。

需要前端临时拼装：

- 项目卡中的品牌词、竞品、平台数、问题数，需要 `projects + monitor-setup` 合成。
- “监测中”可暂按 `project.status=active` 与最近 run 状态判断，但这不是严格的监测开关。
- `GET /platform-endpoints`：平台端分组、端类型、logo 与展示名。
- `GET /prompt-types`：原型五类问题意图及兼容存储值。
- `GET /source-types`：信源展示字典及六类存储值映射。

建议补齐：

- `GET /projects/overview`：一次返回项目卡所需摘要，避免每个项目再调 `monitor-setup/dashboard`。
- `POST /projects/{project_id}/pause`、`POST /projects/{project_id}/resume`：区分暂停监测与禁用项目。
- `GET /projects/{project_id}/delete-check`：删除前返回关联 run、报告和调度影响。
- `GET /projects/options`：用于顶部项目切换器的轻量列表。

### 3.2 创建监测项目向导

当前推荐调用链：

1. `GET /platforms?enabled=true` 或 `GET /platform-endpoints?enabled=true` 获取平台候选。
2. 可选 `GET /prompt-library` 获取问题模板。
3. `POST /projects` 创建项目基础信息。
4. 可选 `POST /projects/{project_id}/ai/brand-words:generate`、`/ai/competitors:generate`、`/ai/questions:generate` 生成候选（不落库）。
5. `PUT /projects/{project_id}/monitor-setup` 保存品牌词、竞品、核心词、问题和默认平台，并按需传 `activate_prompt_set=true`。
6. 如需立即开始采集，调用 `POST /runs`。

需要消除的旧文档歧义：

- 「AI 生成品牌词/竞品/问题」不是 `prompt-library`，已通过 AI 生成辅助接口提供。✅ 已覆盖
- 「平台端」可通过 Aidso 平台码呈现，但缺少结构化端元数据，不能从 schema 直接拿到端类型、logo、分组。

建议补齐：

- `POST /projects/{project_id}/ai/brand-words:generate` ✅ 已覆盖
- `POST /projects/{project_id}/ai/competitors:generate` ✅ 已覆盖
- `POST /projects/{project_id}/ai/questions:generate` ✅ 已覆盖
- `POST /projects:setup`：把创建项目和保存配置包成事务，减少半成品项目。
- `POST/PUT /project-drafts`：支持向导草稿恢复，属于体验增强。

### 3.3 数据大盘

当前可直接使用：

- `GET /projects/{project_id}/dashboard` 展示最新 run 的 KPI、平台表现、最近运行状态。
- `GET /projects/{project_id}/trends?metric_code=brand_visibility` 展示目标品牌可见度趋势。
- `GET /projects/{project_id}/trends?metric_code=brand_top1_mention_rate`、`brand_top3_mention_rate`、`citation_rate` 等展示单指标趋势。
- `POST /runs/{run_id}/reports` 和 `GET /reports/{report_id}/download` 下载报告。

当前字段映射：

| 原型字段 | 当前字段 | 状态 |
| --- | --- | --- |
| 提及率 | `summary.brand_mention_rate` 或 `platforms[].analysis.brand_mention_rate` | 已覆盖 |
| Top1/首位提及率 | `summary.brand_top1_mention_rate` 或 `platforms[].analysis.brand_top1_mention_rate` | 已覆盖 |
| Top3/首屏提及率 | `summary.brand_top3_mention_rate` 或 `platforms[].analysis.brand_top3_mention_rate` | 已覆盖 |
| 对话次数 | `summary.valid_answer_count` | 可用，口径为有效回答数 |
| 提及对话数 | `summary.brand_mention_count` | 可用 |
| 平均提及排名 | `summary_json.metrics.brand_metrics[]` 中目标品牌行；overview `kpis.average_rank` | 可拼；overview 在可读取时稳定返回 |
| SOV | `summary_json.metrics.brand_metrics[]` 中目标品牌行；overview `kpis.share_of_voice` | 可拼；overview 在可读取时稳定返回 |
| 竞品预览 | `platforms[].analysis.top_competitors` 或 `brand_metrics[]`；overview `competitor_preview` | 可拼；overview 已覆盖 |
| 信源预览 | `platforms[].analysis.top_sources`；overview `source_preview` | 可拼；overview 已覆盖 |
| 最近问题 | 答案、任务、Prompt 多接口拼装；overview `recent_questions` | overview 已覆盖 |

建议补齐：

- `GET /projects/{project_id}/dashboard/overview?platform_codes=&start_at=&end_at=` ✅ 已覆盖
- 在 `dashboard` 或 overview 中稳定返回 `average_mention_rank/share_of_voice/brand_mention_total_count`（overview `kpis` 在可读取时返回，否则 `null`）✅ 已覆盖（P1-1）
- `GET /projects/{project_id}/conversation-questions/recent`：已由 overview `recent_questions` 预览替代。

### 3.4 竞品分析

当前可直接使用：

- `GET /projects/{project_id}/dashboard` 获取目标品牌摘要。
- `GET /runs/{run_id}/analysis` 或 `dashboard.platforms[].analysis.summary_json.metrics.brand_metrics[]` 获取当前 run 的品牌/竞品快照榜单。

当前限制：

- `competitor-analysis.trends` 仍返回空数组；历史趋势需通过 `GET /projects/{id}/trends?metric_code=...` 结合 `brand_id` 查询 `geo_metric_snapshot`。
- 行业平均、市场地位、历史基准不是当前后端能力。

建议补齐：

- `GET /projects/{project_id}/competitor-analysis?platform_codes=&start_at=&end_at=&brand_scope=top5|all` ✅ 已覆盖
- 为竞品/品牌维度新增指标快照，至少包含 `brand_id`、`mention_rate`、`mention_count`、`average_mention_rank`、`share_of_voice` ✅ 已覆盖（P1-1，`geo_metric_snapshot.brand_id` + 分析写入）
- 如暂不改表，可先做基于多 run 现有分析 JSON 的只读聚合服务，但要明确性能和口径限制。

### 3.5 AI 对话记录

当前可直接使用：

- `GET /runs/{run_id}/answers` 获取答案分页。
- `GET /answers/{answer_id}` 获取答案原文、引用 `citations[]`、品牌结果 `brand_results[]`。
- `GET /prompt-sets/{prompt_set_id}/prompts` 获取问题文本和类型。
- `GET /runs/{run_id}/query-tasks` 获取 prompt × platform 任务。

当前限制：

- 原型主表是“按 AI 问题聚合”，当前答案接口是单答案粒度。
- 答案详情未直接返回 `prompt_text/prompt_type`，需要另查 Prompt。
- `Answer` 模型保存了 `raw_response_json`，但 `AnswerDetailRead` 未暴露，因此深度思考过程和搜索关键词取不到。
- `/runs/{run_id}/answers` 没有关键词搜索参数。
- Excel 导出未落地。

建议补齐：

- `GET /projects/{project_id}/conversation-questions?run_id=&platform_codes=&start_at=&end_at=&keyword=&page=&page_size=` ✅ 已覆盖
- `GET /projects/{project_id}/conversation-questions/{prompt_id}/answers?run_id=&platform_codes=` ✅ 已覆盖
- `GET /projects/{project_id}/conversation-questions/export`
- `AnswerDetailRead` 增加 `prompt_text/prompt_type`，并按脱敏策略暴露 `reasoning_text/search_keywords` 或 `raw_response_json` 的安全子集。

### 3.6 信源引用分析

当前可直接使用：

- `GET /runs/{run_id}/analysis` 或 `dashboard.platforms[].analysis.top_sources` 获取平台内域名级 Top Sources。
- `GET /answers/{answer_id}` 获取单答案引用文章 `citations[]`。
- `GET /projects/{project_id}/trends?metric_code=citation_rate` 获取引用率趋势。

当前限制：

- `top_sources` 是域名级聚合，文章级 URL/title 去重需要从答案详情聚合。
- 信源类型当前主要是 `web/official/media/social/video/ecommerce` 这 6 类映射，和原型 8 类不一致。
- 缺少站点 × 平台端矩阵、信源类型趋势、链接数去重口径。
- DeepSeek 或其他平台“无引用时是否计入分母”的规则没有页面级接口显式表达。

建议补齐：

- `GET /projects/{project_id}/source-analysis?platform_codes=&start_at=&end_at=&source_type=&keyword=&metric=&page=&page_size=` ✅ 已覆盖
- `GET /projects/{project_id}/source-analysis/type-trends`
- `GET /projects/{project_id}/source-analysis/sites`
- `GET /source-types` 固化分类字典和中文显示名。✅ 已覆盖
- `GET /projects/{project_id}/source-analysis/export`

## 4. 端到端推荐调用链

```text
1. 创建项目
   POST /projects

2. 初始化配置页
   GET /platforms?enabled=true
   GET /prompt-library
   POST /projects/{id}/ai/brand-words:generate（可选）
   POST /projects/{id}/ai/competitors:generate（可选）
   POST /projects/{id}/ai/questions:generate（可选）

3. 保存完整监测配置
   PUT /projects/{project_id}/monitor-setup
   Body: brand + competitors + core_keywords + ai_questions + selected_platform_codes + activate_prompt_set

4. 启动监测
   POST /runs
   Body: project_id + prompt_set_id? + platform_codes? + collection_source + aidso_thinking_enabled_by_platform?

5. 轮询运行状态
   GET /runs/{run_id}

6. 查看分析结果
   GET /projects/{project_id}/dashboard?run_id={run_id}
   GET /runs/{run_id}/analysis
   GET /projects/{project_id}/trends?metric_code=brand_visibility

7. 查看答案和引用
   GET /runs/{run_id}/answers
   GET /answers/{answer_id}

8. 生成并下载报告
   POST /runs/{run_id}/reports
   GET /reports/{report_id}/download
```

## 5. 缺口优先级

### P0：补齐原型核心闭环

| 缺口 | 建议接口/改造 | 影响页面 | 说明 |
| --- | --- | --- | --- |
| 平台端元数据 | `GET /platform-endpoints` ✅ | 全部页面 | 已提供结构化 `base_platform/endpoint_type/endpoint_label/logo_url` 分组；Aidso 端码兼容解析。 |
| AI 生成 | `/ai/brand-words:generate`、`/ai/competitors:generate`、`/ai/questions:generate` ✅ | 创建项目、编辑配置 | MVP 确定性规则生成候选，保存仍走 monitor-setup。 |
| 大盘页面级聚合 | `GET /projects/{id}/dashboard/overview` | 数据大盘 | 解决时间范围、平台多选、竞品预览、信源预览、最近问题的一次性聚合。 |
| 竞品页面级聚合与品牌维度趋势 | `GET /projects/{id}/competitor-analysis` ✅（P0 榜单与 KPI；趋势 P1 补 `brand_id` 快照） | 竞品分析 | 当前只能做当前快照榜，不能做竞品趋势。 |
| 对话记录问题聚合 | `GET /projects/{id}/conversation-questions` ✅ | AI 对话记录 | 按 prompt 聚合主表与平台端指标；P0 单 run，`reasoning_text/search_keywords` 暂返回 null/[]。 |
| 信源页面级聚合 | `GET /projects/{id}/source-analysis` ✅ | 信源引用分析 | 已提供 KPI、类型分布、站点矩阵与 `metric` 口径切换；`article_count` 来自 `AnswerCitation.url` 去重。 |

### P1：统一指标口径与提升对接质量

| 缺口 | 建议接口/改造 | 影响页面 |
| --- | --- | --- |
| 趋势指标编码别名 | 支持 `brand_mention_rate` 作为 `brand_visibility` 的兼容别名，或文档统一改为 `brand_visibility` | 数据大盘、竞品分析 |
| 平均排名与 SOV 顶层化 | 在 dashboard/overview 返回稳定字段，并纳入快照 | 数据大盘、竞品分析、对话记录 |
| 项目卡聚合 | `GET /projects/overview` | 项目管理 |
| Prompt 类型字典 | `GET /prompt-types` ✅ | 创建项目、编辑配置 |
| 信源类型字典 | `GET /source-types` ✅ | 信源引用分析 |
| 回答详情扩展 | `prompt_text/prompt_type/reasoning_text/search_keywords` | AI 对话记录 |
| Excel 导出 | `conversation-questions/export`、`source-analysis/export` 或报告格式增加 `xlsx` | AI 对话记录、信源引用分析 |
| 暂停/恢复监测 | `POST /projects/{id}/pause/resume` | 项目管理 |
| 删除影响检查 | `GET /projects/{id}/delete-check` | 项目管理 |

### P2：后续体验增强

| 缺口 | 建议 | 说明 |
| --- | --- | --- |
| 创建向导草稿 | `POST/PUT /project-drafts` | 支持离开后恢复。 |
| 当前项目偏好 | `GET/PUT /users/me/preferences/current-project` | 支持跨页面记忆当前项目。 |
| 一步创建并运行 | `POST /projects:setup-and-run` | 把创建、配置、激活、运行做成事务或编排接口。 |
| 行业基准 | `GET /benchmarks` | 支撑行业平均、市场地位等参照卡。 |
| 高频评价标签 | LLM 聚类或规则聚类接口 | 原型增强项，成本较高。 |
| 调度配置页 | 复用现有 schedules 接口 | 后端已就绪，原型未覆盖。 |

## 6. 不再沿用的旧表述

以下说法在两份旧文档中容易造成误解，新对接中应避免直接引用：

- “平台端完全无后端模型”：不准确。当前 Aidso 已用 `aidso_*_web/app` 平台码承载端信息，但缺结构化 endpoint 字段。
- “趋势用 `metric_code=brand_mention_rate`”：不贴合当前代码。当前写入的是 `brand_visibility`，除非后端增加别名。
- “竞品趋势可由 trends 获取”：不准确。当前 `geo_metric_snapshot` 没有 `brand_id` 维度，竞品趋势取不到。
- “平均排名、SOV 完全没有”：不准确。当前 `summary_json.metrics.brand_metrics[]` 有当前快照值，但没有稳定顶层字段和趋势快照。
- “信源类型就是原型 8 类”：不准确。当前代码主要映射 6 类，需字典统一。
- “对话记录主表直接用 answers 分页”：不贴合原型。`answers` 是答案粒度，原型需要问题聚合粒度。
- “报告下载可覆盖 Excel 导出”：不准确。当前报告格式为 `md/html/pdf`，Excel 需要新增。

## 7. 一句话版本

当前后端已经具备监测 MVP 的底层闭环：配置项目、启动 run、采集答案、分析平台指标、查看最新大盘和生成报告。要让 6 个原型页以稳定、低成本、口径一致的方式落地，下一步最应该补的是页面级聚合接口、结构化平台端元数据、AI 生成能力，以及竞品/信源/对话记录这三类跨维度聚合能力。
