# Cursor 接口缺口开发任务书

> 面向 Cursor / Agent 进行后端接口开发使用。
> 事实来源：`docs/原型功能_API映射整合精简版.md`。该文档已替代 `docs/原型功能-API映射_v1.md` 与 `docs/原型功能_API映射与缺口清单.md` 中重复、冲突的口径。
> 更新日期：2026-06-26
> API 主前缀：`/api/geo-monitoring`；兼容前缀：`/api/v1/geo-monitoring`。
> 开发约束：后端命令必须使用 `backend/.venv`，测试先行，完成后同步 API 文档与测试文档。

## 1. 开发目标

当前后端已经具备 MVP 底层闭环：项目配置、监测运行 `run`、采集答案、平台分析快照、最新大盘、答案详情和报告生成。原型页面更需要“项目 + 时间范围 + 平台端筛选”的页面级聚合能力。

本任务书的目标是补齐原型六个页面落地所需的接口能力，并消除旧文档中不贴合当前项目的表述：

- 项目管理首页：所有项目列表、项目卡片聚合、进入监测详情、编辑配置、暂停/恢复、删除影响检查。
- 创建监测项目页：平台端元数据、Prompt 类型字典、AI 生成品牌词/竞品/问题。
- 数据大盘页：页面级总览、KPI、平台表现、竞品预览、信源预览、最近问题。
- 竞品分析页：当前 run 的目标品牌与竞品榜单，并为后续品牌维度趋势留好契约。
- AI 对话记录页：按问题聚合的主表、平台端指标、回答弹窗、导出。
- 信源引用分析页：信源 KPI、类型分布、站点影响力矩阵、类型趋势、导出。

2026-06-26 新版首页原型补充：

- 用户进入系统后直接展示所有项目，不再以顶部项目切换下拉作为首屏入口。
- 首页项目卡片必须展示项目名、当前/监测状态、品牌词、竞品、监测平台端图标与平台/端数量、问题数、更新时间。
- 每个项目卡片提供四类动作：`进入`、`编辑配置`、`暂停/监测`、`删除`。
- `GET /projects/overview` 是首页首屏主接口；`GET /projects/options` 仅保留给兼容场景或其它轻量选择器，不再作为首页必需接口。

优先级以 `docs/原型功能_API映射整合精简版.md` 的当前页面映射和本文 Task 定义为准：

- P0：补齐原型核心闭环。
- P1：统一指标口径与提升对接质量。
- P2：后续体验增强。

## 2. 开发前阅读规则

每个任务开始前只读相关章节，不通读无关文档。

| 文档或目录 | 作用 | 何时阅读 |
| --- | --- | --- |
| `docs/Cursor接口缺口开发任务书_Task索引.md` | 任务书 Task 行号目录、推荐顺序、原型文档章节映射 | **每个 Task 开始前先读** |
| `docs/原型功能_API映射整合精简版.md` | 当前唯一事实来源，包含统一口径、能力地图、页面映射、缺口优先级 | 每个任务开始前按任务读取对应章节 |
| `docs/API接口文档.md` | 当前已实现接口契约 | 新增或改造接口前 |
| `docs/API测试文档.md` | API 测试风格与用例约定 | 写接口测试前 |
| `docs/API全量接口测试报告.md` | 当前接口验收现状 | 需要确认既有行为时 |
| `backend/app/geo_monitoring/api/` | 现有 FastAPI 路由模式 | 新增路由时 |
| `backend/app/geo_monitoring/services/` | 业务聚合逻辑模式 | 新增服务函数时 |
| `backend/app/geo_monitoring/schemas.py` | Pydantic 入参/出参模型 | 新增 schema 时 |
| `backend/tests/geo_monitoring/` | 测试风格与 fixture | 写测试时 |

`docs/AI应用监测_MVP_Cursor实施任务V2.md` 中的任务已完成归档，当前接口缺口开发不再读取该任务书或 `docs/AI应用监测_MVP_V2_Task索引.md`。仅当用户明确要求追溯历史任务背景或审计已完成工作时，才按需局部查阅。

按任务快速定位 `docs/原型功能_API映射整合精简版.md`：

| 任务 | 必读章节 |
| --- | --- |
| 平台端、字典 | 1、2.1、3.1、3.2、3.6、5.P0/P1 |
| AI 生成 | 1、2.1、3.2、5.P0 |
| Dashboard overview | 1、2.2、3.3、5.P0/P1 |
| 竞品分析 | 1、2.2、3.4、5.P0/P1、6 |
| 对话记录 | 1、2.2、3.5、5.P0/P1、6 |
| 信源分析 | 1、2.2、3.6、5.P0/P1、6 |
| 项目概览 / 新版首页 | 1、2、3、4、12 |

## 3. 当前能力基线

### 3.1 已有接口

- 项目：`GET/POST /projects`、`GET/PUT/DELETE /projects/{project_id}`。
- 项目概览：`GET /projects/overview`、`GET /projects/options`、`POST /projects/{project_id}/pause`、`POST /projects/{project_id}/resume`、`GET /projects/{project_id}/delete-check`。
- 监测设置：`GET/PUT /projects/{project_id}/monitor-setup`。
- 平台：`GET /platforms`、`GET/PUT /platforms/{platform_code}`。
- Prompt：`GET /prompt-library`、`/projects/{project_id}/prompt-sets`、`/prompt-sets/{id}/prompts`、`/prompts/{id}`。
- 运行：`GET/POST /runs`、`GET /runs/{run_id}`、取消、重试、任务列表。
- 分析：`POST /runs/{run_id}/analyze`、`GET /runs/{run_id}/analysis`。
- Dashboard：`GET /projects/{project_id}/dashboard`、`GET /projects/{project_id}/trends`。
- 答案：`GET /runs/{run_id}/answers`、`GET /answers/{answer_id}`。
- 报告：`POST /runs/{run_id}/reports`、`GET /reports/{report_id}/download`。
- 调度：`/projects/{project_id}/schedules` 与 `/schedules/{schedule_id}`。

### 3.2 关键统一口径

- `dashboard` 当前默认取最近已分析或已终态 run，也支持指定 `run_id`；它不是时间范围聚合接口。
- 当前趋势写入的目标品牌可见度指标是 `brand_visibility`，不是旧文档里的 `brand_mention_rate`。
- `dashboard.summary.brand_mention_rate`、`platforms[].analysis.brand_mention_rate` 已可用于大盘提及率展示。
- 当前 `summary_json.metrics.brand_metrics[]` 有目标品牌和竞品的当前快照指标，可用于榜单；竞品历史趋势应使用 `GET /projects/{project_id}/trends?metric_code=...&brand_id=...` 查询品牌维度快照。
- `/runs/{run_id}/answers` 是答案粒度，即 prompt × platform；原型 AI 对话记录主表需要按问题聚合。
- Aidso 平台端已经通过 `aidso_*_web/app` 平台码承载端信息，但没有独立 `base_platform/endpoint_type/logo_url` 字段。
- 信源类型当前代码主要映射为 `web/official/media/social/video/ecommerce` 六类，原型展示需要统一字典和映射。
- 当前报告格式为 `md/html/pdf`；AI 对话记录和信源页导出已按 CSV 文件流落地，不是 Excel。

### 3.3 优先复用的数据源

- `MonitorProject.default_platform_codes`
- `AIPlatform.platform_code/platform_name/adapter_type/search_enabled/citation_supported/enabled/extra_config`
- `MonitorRun.platform_codes/status/collection_status/analysis_status/task_count/valid_answer_count`
- `QueryTask.prompt_id/platform_code/status`
- `Answer.raw_text/normalized_text/platform_code/prompt_id/collected_at/raw_response_json`
- `Citation.title/url/domain/source_type/quoted_text`
- `BrandResult.brand_id/is_mentioned/mention_count/first_position/sentiment/context_json`
- `PlatformAnalysis.brand_mention_rate/top_competitors/top_sources/summary_json`
- `MetricSnapshot.metric_code/platform_code/prompt_id/metric_value/snapshot_at`
- `SourceStat.run_id/platform_code/domain/source_type/citation_count/share_rate/rank_no`

除非接口无法稳定计算，否则先复用现有表和分析 JSON，不优先新增大表。

## 4. 统一开发规范

### 4.1 文件组织

新增聚合接口建议按页面域拆分：

| 功能域 | API 文件 | Service 文件 | 测试文件 |
| --- | --- | --- | --- |
| 平台端与字典 | `backend/app/geo_monitoring/api/metadata.py` | `backend/app/geo_monitoring/services/metadata.py` | `backend/tests/geo_monitoring/test_metadata_api.py` |
| AI 生成辅助 | `backend/app/geo_monitoring/api/ai_generation.py` | `backend/app/geo_monitoring/services/ai_generation.py` | `backend/tests/geo_monitoring/test_ai_generation_api.py` |
| Dashboard 总览 | 扩展 `backend/app/geo_monitoring/api/dashboard.py` | 扩展 `backend/app/geo_monitoring/services/dashboard.py` | 扩展 `backend/tests/geo_monitoring/test_dashboard_api.py` |
| 竞品分析 | `backend/app/geo_monitoring/api/competitor_analysis.py` | `backend/app/geo_monitoring/services/competitor_analysis.py` | `backend/tests/geo_monitoring/test_competitor_analysis_api.py` |
| 对话记录 | `backend/app/geo_monitoring/api/conversations.py` | `backend/app/geo_monitoring/services/conversations.py` | `backend/tests/geo_monitoring/test_conversations_api.py` |
| 信源分析 | `backend/app/geo_monitoring/api/source_analysis.py` | `backend/app/geo_monitoring/services/source_analysis.py` | `backend/tests/geo_monitoring/test_source_analysis_api.py` |
| 项目概览 | `backend/app/geo_monitoring/api/project_overview.py` | `backend/app/geo_monitoring/services/project_overview.py` | `backend/tests/geo_monitoring/test_project_overview_api.py` |

新增 API 文件后，必须在 `backend/app/geo_monitoring/api/__init__.py` 中导入 router 并加入 `_SUB_ROUTERS`。该聚合器会同时挂载主前缀和 v1 兼容前缀。

### 4.2 查询参数

多页面复用筛选参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | integer，可选 | 指定运行；不传时取项目最新已分析或已终态 run，逻辑与 dashboard 一致 |
| `platform_codes` | string，可重复 query | 平台端编码，例如 `platform_codes=aidso_doubao_web&platform_codes=aidso_doubao_app` |
| `start_at` / `end_at` | datetime，可选 | 时间范围，ISO8601；若接口 P0 暂不做跨 run 聚合，必须在文档中说明实际口径 |
| `page` / `page_size` | integer | 列表类接口必须支持 |
| `keyword` | string，可选 | 文本搜索 |

FastAPI 写法建议：

```python
platform_codes: list[str] | None = Query(None)
```

### 4.3 响应与数值格式

- 除文件下载外，统一响应 `{ code, message, data }`。
- 分页 `data` 统一为 `{ items, total, page, page_size }`。
- 比率返回 decimal 字符串，例如 `"0.3520"`，前端展示时乘 100。
- 无分母时返回 `null`，不要返回 `"0"` 伪装为真实 0。
- 时间返回 ISO8601 字符串。
- 平均排名返回 decimal 字符串，例如 `"2.4"`；未提及时返回 `null`。
- 导出接口返回文件流，不包统一 JSON。

### 4.4 错误码

沿用 `docs/API接口文档.md`：

| 场景 | code | HTTP |
| --- | --- | --- |
| 项目/运行/资源不存在 | `40400` | 200 |
| 项目未启用 | `40001` | 200 |
| 参数校验失败 | `422` | 200 |
| 分析未完成不可生成报告 | `40920` | 409 |

新增业务冲突优先复用现有错误码。确需新增错误码时，同步更新 `docs/API接口文档.md`。

### 4.5 测试命令

执行后端命令必须使用 `backend/.venv`：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring
```

单文件示例：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_conversations_api.py
```

## 5. P0 开发任务

P0 只覆盖 `docs/原型功能_API映射整合精简版.md` 明确列出的核心闭环缺口：平台端元数据、AI 生成、大盘页面级聚合、竞品页面级聚合、对话记录问题聚合、信源页面级聚合。

### Task P0-1：平台端元数据与基础字典接口

**目标：** 为全部页面提供稳定的平台端展示信息、Prompt 类型、信源类型字典，避免前端从 `platform_code` 猜分组、端类型、logo 和中文显示名。

**新增接口：**

- `GET /platform-endpoints`
- `GET /prompt-types`
- `GET /source-types`

**关键逻辑：**

1. `GET /platform-endpoints` 读取 `AIPlatform`，优先使用 `extra_config.base_platform/endpoint_type/endpoint_label/logo_url/thinking_mode`。
2. 历史数据缺少 `extra_config` 时，用 `platform_code/platform_name` 兼容解析。`aidso_*_web` 识别为网页端，`aidso_*_app` 识别为手机端。
3. 按 `base_platform` 分组，端顺序为 `web`、`app`、其他；返回时不修改数据库。
4. `GET /prompt-types` 返回原型五类问题意图，并保留旧中文值和 `comparison/recommendation` 等兼容值。
5. `GET /source-types` 返回原型展示用统一字典，并提供当前六类存储值到展示字典的映射能力；不要假设数据库里已经是新字典值。

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/metadata.py`
- Create: `backend/app/geo_monitoring/services/metadata.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_metadata_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

**验收命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_metadata_api.py
```

**验收点：**

- 返回结构化平台端分组，至少覆盖普通平台码和 Aidso 端码。
- `enabled` 参数能过滤停用平台。
- Prompt 类型返回 5 个原型意图类型。
- 信源类型返回统一展示字典，并能说明当前六类存储值的映射关系。
- 新 router 已注册到 `api/__init__.py`。

### Task P0-2：AI 生成辅助接口

**目标：** 支撑创建项目和编辑配置中的“AI 生成品牌词 / AI 生成竞品 / AI 智能生成问题”。MVP 阶段先实现 deterministic 规则生成，后续再替换或扩展为真实 LLM。

**新增接口：**

- `POST /projects/{project_id}/ai/brand-words:generate`
- `POST /projects/{project_id}/ai/competitors:generate`
- `POST /projects/{project_id}/ai/questions:generate`

**关键逻辑：**

1. 生成接口只返回候选，不写数据库；保存仍走 `PUT /projects/{project_id}/monitor-setup`。
2. 品牌词去重、去空白，必须包含 `brand_name`。
3. 竞品生成优先基于 `category/region` 的固定规则；没有命中时返回通用同类品牌候选。
4. 问题生成按五类意图模板生成：品牌情绪、品牌信息、品类情绪、竞品对比、品类推荐。
5. 生成结果按 `limit` 截断，测试必须稳定。

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/ai_generation.py`
- Create: `backend/app/geo_monitoring/services/ai_generation.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_ai_generation_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

**验收命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_ai_generation_api.py
```

**验收点：**

- 品牌名为空返回参数校验失败。
- 宋城/杭州旅游示例能返回贴合原型的品牌词、竞品和问题。
- 生成接口不改变数据库里的 monitor setup。

### Task P0-3：AI 对话记录问题聚合接口

**目标：** 支撑 AI 对话记录主表、行内平台端指标、回答弹窗。当前 `/runs/{run_id}/answers` 是答案粒度，不能直接当作原型主表。

**新增接口：**

- `GET /projects/{project_id}/conversation-questions`
- `GET /projects/{project_id}/conversation-questions/{prompt_id}/answers`

**关键逻辑：**

1. 最新 run 选择逻辑复用 dashboard；也支持指定 `run_id`。
2. 主表按 `prompt_id` 聚合，而不是按 answer 聚合。
3. 有效答案口径：关联任务成功且 `normalized_text/raw_text` 非空，可复用分析模块现有有效答案过滤逻辑。
4. 目标品牌来自项目 `brand_type=target`。
5. 可见度 = 目标品牌 `is_mentioned=true` 的有效答案数 / 有效答案数。
6. 提及次数 = 目标品牌 `mention_count` 求和。
7. 平均排名 MVP 可先使用目标品牌 `first_position` 的平均值。
8. Top1/Top3 按单答案 `first_position <= 1/3` 判断。
9. 情感按 `positive/neutral/negative` 聚合。
10. `reasoning_text/search_keywords` 当前未稳定暴露，P0 返回 `null/[]`；P1 再从安全子集或 `raw_response_json` 中补齐。

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/conversations.py`
- Create: `backend/app/geo_monitoring/services/conversations.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_conversations_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

**验收命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_conversations_api.py
```

**验收点：**

- 多个答案同 prompt 聚合成一行。
- `keyword` 能过滤问题文本。
- `platform_codes` 能过滤平台端指标。
- 回答详情返回引用和品牌名称。
- 无引用时 `citations=[]`，无品牌结果时 `brand_results=[]`。

### Task P0-4：信源引用分析页面级接口

**目标：** 支撑信源引用分析页 KPI、类型分布、站点 TOP10、平台端矩阵和指标口径切换。当前只有域名 Top 和单答案引用，不能完整支撑页面。

**新增接口：**

- `GET /projects/{project_id}/source-analysis`

**关键逻辑：**

1. 优先使用 `SourceStat` 做域名级聚合。
2. 文章数更推荐从 `Citation.url` 去重；如果 P0 只能用 `SourceStat` 估算，必须在 API 文档说明口径。
3. `citation_count` 为所选平台 `SourceStat.citation_count` 求和。
4. `site_count` 为所选平台 distinct domain。
5. 类型分布按统一信源字典聚合，旧存储值先映射到新展示类型。
6. 平台端矩阵按 domain/source_name 聚合，缺数据返回 `has_citation_data=false`。
7. `metric=links` 时 `display_value=link_count`；`metric=rate` 时 `display_value=citation_rate`。

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/source_analysis.py`
- Create: `backend/app/geo_monitoring/services/source_analysis.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_source_analysis_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

**验收命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_source_analysis_api.py
```

**验收点：**

- 无信源数据时 KPI 为 0、列表为空。
- 有多平台 `SourceStat` 时能返回矩阵列。
- `source_type`、`keyword`、`metric` 过滤和切换有效。
- `platform_codes` 只返回选中平台列并更新 KPI。

### Task P0-5：竞品分析页面级接口

**目标：** 支撑竞品分析页的本品牌 KPI、竞品榜单和趋势字段契约。当前后端有当前快照指标，但没有品牌维度历史趋势。

**新增接口：**

- `GET /projects/{project_id}/competitor-analysis`

**关键逻辑：**

1. 目标品牌来自项目 `brand_type=target`。
2. 竞品来自项目 `brand_type=competitor`。
3. 榜单优先基于 `PlatformAnalysis.summary_json.metrics.brand_metrics[]`；缺失时退化使用 `top_competitors` 和目标品牌指标。
4. `mention_count` 可从 `BrandResult.mention_count` 聚合。
5. `average_rank/share_of_voice` 当前有当前快照值时返回；没有可靠值时返回 `null` 或空榜，不要伪造。
6. 趋势字段保留，但 P0 如果没有 `brand_id` 维度快照，返回空数组，并在文档说明 P1 补齐。
7. 不要宣称可通过 `/trends` 直接获取竞品历史趋势，当前 `MetricSnapshot` 没有 `brand_id` 维度。

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/competitor_analysis.py`
- Create: `backend/app/geo_monitoring/services/competitor_analysis.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_competitor_analysis_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

**验收命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_competitor_analysis_api.py
```

**验收点：**

- 无分析数据时返回空榜，不报错。
- 有分析数据时目标品牌出现在 KPI 与榜单中，并 `is_target=true`。
- `brand_scope=top5/all` 参数校验有效。
- 趋势缺数据时返回空数组，不误用目标品牌 `/trends` 伪装竞品趋势。

### Task P0-6：Dashboard 页面级总览接口

**目标：** 支撑数据大盘首屏，返回 KPI、平台表现、竞品预览、信源预览、最近问题预览。该接口应复用 P0-3、P0-4、P0-5 中沉淀的聚合服务。

**新增接口：**

- `GET /projects/{project_id}/dashboard/overview`

**关键逻辑：**

1. 支持 `run_id/platform_codes/start_at/end_at`。
2. 未传 `run_id` 时取项目最新已分析或已终态 run。
3. KPI 优先使用当前 `dashboard` 已落地字段：`brand_mention_rate`、`brand_top1_mention_rate`、`brand_top3_mention_rate`、`valid_answer_count`、`brand_mention_count`。
4. `average_rank/share_of_voice/brand_mention_total_count` 当前可从 `summary_json.metrics.brand_metrics[]` 读取时返回；不能稳定读取时返回 `null`，由 P1 指标快照补齐。
5. 平台表现复用 `platforms[].analysis`。
6. 竞品预览复用竞品分析服务。
7. 信源预览复用信源分析服务。
8. 最近问题复用对话记录服务，只返回少量预览项。
9. 只有采集未分析 run 时，KPI 可为空/null，但接口不报错。

**涉及文件：**

- Modify: `backend/app/geo_monitoring/api/dashboard.py`
- Modify: `backend/app/geo_monitoring/services/dashboard.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_dashboard_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

**验收命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_dashboard_api.py
```

**验收点：**

- 无运行时返回 `run_id=null`、数组为空。
- 有 dashboard 数据时返回 KPI 和平台表现。
- `platform_codes` 能过滤平台列表和预览数据。
- 未分析 run 不报错。

## 6. P1 开发任务

### Task P1-1：补齐指标口径与快照

**目标：** 让大盘、竞品、对话记录中当前可能为 `null` 的核心指标变成稳定后端口径，并为竞品趋势准备品牌维度快照。

**新增或固化的指标：**

| 指标 | metric_code | 口径 |
| --- | --- | --- |
| 平均提及排名 | `average_mention_rank` | 目标品牌在提及答案中的排名平均值，越小越好 |
| SOV | `share_of_voice` | 目标品牌出现对话数 / 所有品牌出现对话总数 |
| Top10 提及率 | `brand_top10_mention_rate` | 目标品牌排名 <= 10 的有效回答数 / 有效回答数 |
| 品牌提及次数 | `brand_mention_total_count` | 目标品牌 `mention_count` 求和 |
| 正/中/负情感率 | `positive_rate`、`neutral_rate`、`negative_rate` | 对目标品牌提及答案按 sentiment 聚合 |

**关键逻辑：**

1. 在纯函数层先写测试，覆盖空分母、未提及、多品牌、多答案。
2. 分析写入阶段生成 `MetricSnapshot`，并同步写入 `PlatformAnalysis.summary_json.metrics`。
3. 如果要支撑竞品历史趋势，新增品牌维度快照字段或轻量表，至少包含 `brand_id`、`metric_code`、`platform_code`、`metric_value`、`snapshot_at`。
4. Dashboard、Competitor、Conversation 接口优先读取快照或 summary，不重复复杂计算。

**涉及文件：**

- Modify: `backend/app/geo_monitoring/analysis/metrics.py`
- Modify: `backend/app/geo_monitoring/analysis/brands.py`
- Modify: `backend/app/geo_monitoring/services/analysis.py`
- Modify: `backend/app/geo_monitoring/services/dashboard.py`
- Test: `backend/tests/geo_monitoring/analysis/test_metrics.py`
- Test: `backend/tests/geo_monitoring/test_dashboard_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

### Task P1-2：项目概览、暂停恢复与删除检查

**目标：** 支撑项目管理页基础卡片与管理动作。该项已覆盖“批量项目概览 + 暂停/恢复 + 删除检查”的后端基础能力；新版首页截图中的明细展示增强见 Task P1-5。

**接口：**

- `GET /projects/overview`
- `GET /projects/options`（兼容/辅助；新版首页首屏不再必需）
- `POST /projects/{project_id}/pause`
- `POST /projects/{project_id}/resume`
- `GET /projects/{project_id}/delete-check`

**关键逻辑：**

1. `projects/overview` 是项目管理首页首屏主接口，批量返回项目卡片摘要，避免前端对每个项目调用 `monitor-setup/dashboard`。
2. `projects/options` 仅作为兼容轻量项目选择器保留，不再作为新版首页入口依赖。
3. 平台数按 `base_platform` 去重，端数按 `selected_platform_codes.length`。
4. 暂停只影响调度和新运行，不删除项目、不禁用历史数据。
5. 删除检查返回运行数、报告数、调度数、是否可删除、阻塞原因。
6. 聚合查询必须避免 N+1。

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/project_overview.py`
- Create: `backend/app/geo_monitoring/services/project_overview.py`
- Modify: `backend/app/geo_monitoring/api/projects.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_project_overview_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`

### Task P1-3：回答详情扩展与导出接口

**目标：** 提升 AI 对话记录与信源页的对接质量，补齐导出能力。

**接口：**

- 扩展 `GET /answers/{answer_id}`
- `GET /projects/{project_id}/conversation-questions/export`
- `GET /projects/{project_id}/source-analysis/export`

**关键逻辑：**

1. `AnswerDetailRead` 增加 `prompt_text/prompt_type`。
2. 按脱敏策略暴露 `reasoning_text/search_keywords` 或 `raw_response_json` 的安全子集。
3. 导出 Query 与对应列表接口保持一致。
4. MVP 导出可先返回 CSV：`Content-Type: text/csv; charset=utf-8`。
5. CSV 使用 UTF-8 BOM 或明确 UTF-8，确保中文列名不乱码。

### Task P1-4：趋势指标编码兼容

**目标：** 消除旧前端或旧文档对 `brand_mention_rate` 趋势编码的误用风险。

**关键逻辑：**

1. `GET /projects/{project_id}/trends?metric_code=brand_mention_rate` 兼容映射到当前实际写入的 `brand_visibility`。
2. 响应中保留请求的 `metric_code` 还是返回实际编码，需要在 `docs/API接口文档.md` 明确。
3. 新代码和新文档优先使用 `brand_visibility`。

### Task P1-5：新版首页项目列表卡片增强

**目标：** 对齐 2026-06-26 新版首页原型。用户进入系统后直接看到所有项目列表；每个项目卡片直接展示品牌词、竞品、监测平台端、问题数和更新时间，并提供 `进入`、`编辑配置`、`暂停/监测`、`删除` 四个动作。

**接口：**

- 扩展 `GET /projects/overview`
- 复用 `GET /projects/{project_id}/monitor-setup`
- 复用 `POST /projects/{project_id}/pause`
- 复用 `POST /projects/{project_id}/resume`
- 复用 `GET /projects/{project_id}/delete-check`
- 复用 `DELETE /projects/{project_id}`

**建议扩展 `projects/overview.items[]` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `brand_words` | string[] | 首页“品牌词”标签；来自目标品牌启用别名，按稳定顺序返回，建议默认最多 10 个 |
| `competitors` | object[] | 首页“竞品”标签；每项至少含 `brand_id`、`brand_name`，默认返回全部启用竞品或限制前 10 个并给出总数 |
| `platform_endpoints` | object[] | 首页平台端图标列表；每项含 `platform_code`、`platform_name`、`base_platform`、`endpoint_type`、`endpoint_label`、`logo_url`、`enabled` |
| `homepage_badges` | object[] | 首页状态标签，如 `monitoring`、`paused`；`当前`标签如需持久化需先确认用户体系，否则由前端基于当前路由/本地状态处理 |
| `last_updated_at` | datetime | 首页“更新”时间；优先取最近 run 完成时间，否则取项目更新时间 |

**按钮动作契约：**

1. `进入`：前端跳转监测详情页，目标页调用 `GET /projects/{project_id}/dashboard/overview`，无需新增后端入口接口。
2. `编辑配置`：打开配置弹层或页面，先调 `GET /projects/{project_id}/monitor-setup`，保存走 `PUT /projects/{project_id}/monitor-setup`，保存后刷新 `GET /projects/overview`。
3. `暂停`：当 `monitoring_paused=false` 时调用 `POST /projects/{project_id}/pause`；成功后刷新当前页。
4. `监测`/`恢复监测`：当 `monitoring_paused=true` 时调用 `POST /projects/{project_id}/resume`；成功后刷新当前页。
5. `删除`：先调用 `GET /projects/{project_id}/delete-check`；`can_delete=true` 且用户二次确认后再调用 `DELETE /projects/{project_id}`。

**关键逻辑：**

1. 首页首屏只依赖 `GET /projects/overview`，不再强制调用 `GET /projects/options`。
2. `projects/overview` 需要批量加载目标品牌别名、竞品名称、激活问题数量、平台端元数据和最近运行，避免 N+1。
3. 平台图标信息优先复用 `platform-endpoints` 的解析规则，避免同一平台端在不同接口展示不一致。
4. 暂停项目的新运行和调度触发继续返回 `40054`；历史分析、报告和详情页不受影响。
5. “当前”标签不应为了首页强行引入用户偏好表；如果产品要求跨设备记忆，再回到 P2 用户偏好能力。

**涉及文件：**

- Modify: `backend/app/geo_monitoring/services/project_overview.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_project_overview_api.py`
- Docs: `docs/API接口文档.md`、`docs/API测试文档.md`、`docs/原型功能_API映射整合精简版.md`

## 7. P2 开发任务

### Task P2-1：一步创建完整项目

**目标：** 将 `POST /projects` 与 `PUT /monitor-setup` 包成事务接口，避免创建向导保存一半失败。

**接口：**

- `POST /projects:setup`
- 可选后续增强：`POST /projects:setup-and-run`

**关键逻辑：**

1. 入参包含 `project` 与 `monitor_setup`。
2. 任一保存步骤失败时数据库不留下半成品项目。
3. `run_after_create=true` 时返回新 run。
4. 不替代现有分步接口，作为创建向导体验增强。

### Task P2-2：创建向导草稿与用户偏好

**接口：**

- `POST/PUT /project-drafts`
- `GET/PUT /users/me/preferences/current-project`

**说明：**

- 草稿用于创建向导离开后恢复。
- 当前项目偏好用于跨页面记忆项目选择。
- 若当前项目尚无用户体系，可先延后，不要为了该项引入临时用户模型。

### Task P2-3：行业基准与评价标签

**接口或能力：**

- `GET /benchmarks`
- 高频评价标签聚类接口

**说明：**

- 支撑行业平均、市场地位、评价标签等增强项。
- 需要产品明确行业维度与样本来源后再做，不纳入 P0。

## 8. 文档更新要求

每完成一个任务，必须同步更新：

| 文档 | 更新内容 |
| --- | --- |
| `docs/API接口文档.md` | 新接口路径、入参、出参、错误码、示例 |
| `docs/API测试文档.md` | 新接口测试用例与命令 |
| `docs/API全量接口测试报告.md` | 若执行全量测试，追加或更新测试结果 |
| `docs/原型功能_API映射整合精简版.md` | 将已完成缺口标注为已覆盖，更新调用建议 |

旧文档 `docs/原型功能-API映射_v1.md` 与 `docs/原型功能_API映射与缺口清单.md` 只作为历史来源，不再作为新任务的直接开发依据。

## 9. 推荐开发顺序

1. P0-1 平台端元数据与基础字典接口。
2. P0-2 AI 生成辅助接口。
3. P0-3 AI 对话记录问题聚合接口。
4. P0-4 信源引用分析页面级接口。
5. P0-5 竞品分析页面级接口。
6. P0-6 Dashboard 页面级总览接口。
7. P1-1 补齐指标口径与快照。
8. P1-2 项目概览、暂停恢复与删除检查。
9. P1-5 新版首页项目列表卡片增强。
10. P1-3 回答详情扩展与导出接口。
11. P1-4 趋势指标编码兼容。
12. P2 系统体验增强。

说明：对话记录、信源、竞品接口会沉淀可复用聚合服务，Dashboard overview 应复用这些服务，因此放在 P0 最后完成。

## 10. 每次任务完成后的验收命令

单任务测试：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\<对应测试文件>.py
```

相关域回归：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring
```

全量后端回归：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests
```

API 文档边界测试：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\test_documentation_boundary.py backend\tests\test_api_contract.py
```

新版首页项目列表专项验收：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_project_overview_api.py
```

如果本次任务改动了源码且验收通过，按仓库规则更新 CodeGraph：

```powershell
codegraph status
codegraph sync
codegraph status
```

文档-only 任务无需运行 pytest，也无需更新 CodeGraph。

## 11. Cursor 执行提示词建议

推荐格式：

```text
执行 docs/Cursor接口缺口开发任务书.md 的 Task P0-1：平台端元数据与基础字典接口。
要求：
1. 先读本任务书中的 Task P0-1，以及 docs/原型功能_API映射整合精简版.md 的 1、2.1、3.1、3.2、3.6、5.P0/P1。
2. 再读 docs/API接口文档.md 对应平台、Prompt、信源章节，以及现有 platforms API 和测试。
3. 按 TDD：先写失败测试，再实现接口。
4. 使用 backend/.venv 执行 pytest。
5. 完成后更新 docs/API接口文档.md、docs/API测试文档.md，并在 docs/原型功能_API映射整合精简版.md 标注已覆盖缺口。
```

## 12. 风险与注意事项

- 不要再沿用“平台端完全无后端模型”的说法；当前 Aidso 端信息藏在平台码里，缺的是结构化端元数据。
- 不要再把趋势 `metric_code=brand_mention_rate` 当作当前事实；当前实际写入的是 `brand_visibility`。
- 不要宣称 `/trends` 已能返回竞品趋势；当前缺品牌维度快照。
- 不要说平均排名、SOV 完全没有；当前 `summary_json.metrics.brand_metrics[]` 有当前快照值，但缺稳定顶层字段和趋势快照。
- 不要把 `answers` 分页直接当作 AI 对话记录主表；原型需要问题聚合粒度。
- 不要把当前报告下载等同于 Excel 导出；报告格式是 `md/html/pdf`，导出需新增。
- 聚合接口必须避免 N+1 查询，尤其是项目概览、对话问题列表和信源矩阵。
- `platform_codes` 多选筛选只过滤聚合展示，不修改 run 原始平台集合。
- 当前 `reasoning_text/search_keywords` 没有明确稳定字段，P0 先返回 `null/[]`，不要伪造内容。
