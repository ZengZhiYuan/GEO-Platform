# Cursor 接口缺口开发任务书

> 面向 Cursor / Agent 进行后端接口开发使用。  
> 来源文档：`docs/原型功能_API映射与缺口清单.md`、`docs/API接口文档.md`、6 个高保真原型页面功能梳理。  
> 更新日期：2026-06-24  
> API 主前缀：`/api/geo-monitoring`；兼容前缀：`/api/v1/geo-monitoring`。  
> 开发约束：后端命令必须使用 `backend/.venv`，测试先行，完成后更新 API 文档与测试文档。

## 1. 开发目标

补齐原型页面落地所需的后端聚合接口和字典接口，让前端不再依赖大量 N+1 请求或本地复杂计算即可完成以下页面：

- 项目管理页：项目卡片聚合、平台端元数据、项目暂停/恢复。
- 创建监测项目页：AI 生成品牌词、竞品、监测问题；一步创建项目与配置。
- 数据大盘页：页面级总览、KPI、平台表现、预览数据、趋势。
- 竞品分析页：竞品 Top10 榜单、核心 KPI、趋势。
- AI 对话记录页：按问题聚合的对话列表、平台端指标、回答弹窗、导出。
- 信源引用分析页：信源 KPI、类型分布、站点影响力矩阵、趋势。

本任务书按优先级拆为 P0、P1、P2。建议先完成 P0，确保原型主流程可跑通，再补 P1/P2。

## 2. 开发前必须阅读的文档

每个任务开始前，Cursor 需要按下表读取相关资料。不要通读无关文档。

| 文档名称 | 作用 | 何时阅读 |
| --- | --- | --- |
| `docs/原型功能_API映射与缺口清单.md` | 原型功能与现有 API/缺口的完整映射 | 每个任务开始前先定位对应章节 |
| `docs/API接口文档.md` | 当前已实现接口契约 | 新增或改造接口前 |
| `docs/API测试文档.md` | API 测试风格与用例约定 | 写接口测试前 |
| `docs/API全量接口测试报告.md` | 当前接口验收现状 | 需要确认既有行为时 |
| `docs/AI应用监测_MVP_V2_Task索引.md` | V2 任务索引与执行规则 | 如任务归入 MVP V2 Task 时 |
| `docs/AI应用监测_MVP_Cursor实施任务V2.md` | MVP V2 详细任务书 | 只按索引局部阅读相关 Task |
| `backend/app/geo_monitoring/api/` | 现有 FastAPI 路由模式 | 新增路由时 |
| `backend/app/geo_monitoring/services/` | 业务聚合逻辑模式 | 新增服务函数时 |
| `backend/app/geo_monitoring/schemas.py` | Pydantic 入参/出参模型 | 新增 schema 时 |
| `backend/tests/geo_monitoring/` | 测试风格与 fixture | 写测试时 |

## 3. 现有能力基线

已有接口：

- 项目：`GET/POST/PUT/DELETE /projects`
- 统一监测设置：`GET/PUT /projects/{project_id}/monitor-setup`
- 平台：`GET /platforms`、`GET/PUT /platforms/{platform_code}`
- 运行：`GET/POST /runs`、`GET /runs/{run_id}`、取消、重试、任务列表
- 分析：`POST /runs/{run_id}/analyze`、`GET /runs/{run_id}/analysis`
- Dashboard：`GET /projects/{project_id}/dashboard`、`GET /projects/{project_id}/trends`
- 答案：`GET /runs/{run_id}/answers`、`GET /answers/{answer_id}`
- 报告：`POST/GET /runs/{run_id}/reports`、`GET /reports/{report_id}/download`
- 调度：`/projects/{project_id}/schedules` 与 `/schedules/{schedule_id}`

已有可复用数据源：

- `MonitorProject.default_platform_codes`
- `AIPlatform.platform_code/platform_name/enabled/extra_config`
- `MonitorRun.platform_codes/status/*_status/task_count`
- `QueryTask.prompt_id/platform_code/status`
- `Answer.raw_text/normalized_text/platform_code/prompt_id/collected_at`
- `Citation.title/url/domain/source_type/quoted_text`
- `BrandResult.brand_id/is_mentioned/mention_count/first_position/sentiment/context_json`
- `PlatformAnalysis.brand_mention_rate/top_competitors/top_sources/summary_json`
- `MetricSnapshot.metric_code/platform_code/prompt_id/metric_value/snapshot_at`
- `SourceStat.run_id/platform_code/domain/source_type/citation_count/share_rate/rank_no`

优先复用以上表和服务。除非接口无法稳定计算，否则不要先新增数据库表。

## 4. 统一开发规范

### 4.1 文件组织

新增聚合接口建议按页面域拆分：

| 功能域 | API 文件 | Service 文件 | 测试文件 |
| --- | --- | --- | --- |
| 平台端与字典 | `backend/app/geo_monitoring/api/metadata.py` | `backend/app/geo_monitoring/services/metadata.py` | `backend/tests/geo_monitoring/test_metadata_api.py` |
| 项目概览 | `backend/app/geo_monitoring/api/project_overview.py` | `backend/app/geo_monitoring/services/project_overview.py` | `backend/tests/geo_monitoring/test_project_overview_api.py` |
| AI 生成辅助 | `backend/app/geo_monitoring/api/ai_generation.py` | `backend/app/geo_monitoring/services/ai_generation.py` | `backend/tests/geo_monitoring/test_ai_generation_api.py` |
| Dashboard 总览 | 扩展 `api/dashboard.py` | 扩展 `services/dashboard.py` | 扩展 `test_dashboard_api.py` |
| 竞品分析 | `backend/app/geo_monitoring/api/competitor_analysis.py` | `backend/app/geo_monitoring/services/competitor_analysis.py` | `backend/tests/geo_monitoring/test_competitor_analysis_api.py` |
| 对话记录 | `backend/app/geo_monitoring/api/conversations.py` | `backend/app/geo_monitoring/services/conversations.py` | `backend/tests/geo_monitoring/test_conversations_api.py` |
| 信源分析 | `backend/app/geo_monitoring/api/source_analysis.py` | `backend/app/geo_monitoring/services/source_analysis.py` | `backend/tests/geo_monitoring/test_source_analysis_api.py` |

新增 API 文件后，必须在 `backend/app/geo_monitoring/api/__init__.py` 中导入并加入 `_SUB_ROUTERS`。

### 4.2 查询参数约定

多页面复用筛选参数：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | integer，可选 | 指定运行；不传时取项目最新已分析运行，逻辑与 dashboard 一致 |
| `platform_codes` | string，可重复 query | 平台端编码，例如 `platform_codes=qwen&platform_codes=deepseek` |
| `start_at` / `end_at` | datetime，可选 | 时间范围，ISO8601 |
| `page` / `page_size` | integer | 分页，列表类接口必须支持 |
| `keyword` | string，可选 | 文本搜索 |

FastAPI 写法建议：

```python
platform_codes: list[str] | None = Query(None)
```

### 4.3 比率、金额、时间格式

- 比率返回 decimal 字符串，如 `"0.3520"`，前端展示时乘 100。
- 无分母时返回 `null`，不要返回 `"0"` 伪装为真实 0。
- 时间返回 ISO8601 字符串。
- 排名使用 decimal 字符串，如 `"2.4"`；未提及返回 `null`。

### 4.4 错误码约定

沿用 `docs/API接口文档.md`：

| 场景 | code | HTTP |
| --- | --- | --- |
| 项目/运行/资源不存在 | `40400` | 200 |
| 项目未启用 | `40001` | 200 |
| 参数校验失败 | `422` | 200 |
| 分析未完成不可生成报告 | `40920` | 409 |

新增业务冲突优先复用现有错误码。确需新增错误码时同步更新 `docs/API接口文档.md`。

### 4.5 测试命令约定

在仓库根目录执行：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring
```

单文件测试示例：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_conversations_api.py
```

全量后端回归：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests
```

## 5. P0 开发任务

### Task P0-1：平台端元数据与基础字典接口

**目标：** 为全部页面提供稳定的平台端展示信息、Prompt 类型、信源类型字典，避免前端从 `platform_code` 猜端类型、logo、深度思考模式。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：2.3、11.3、11.4
- `docs/API接口文档.md`：10. AI 平台

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/metadata.py`
- Create: `backend/app/geo_monitoring/services/metadata.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_metadata_api.py`
- Docs: `docs/API接口文档.md`

**接口 1：平台端分组**

`GET /platform-endpoints`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `enabled` | boolean/null | `null` | 只返回启用平台端 |

Response `data`:

```json
[
  {
    "base_platform": "豆包",
    "logo_url": "平台logo/豆包.jpeg",
    "endpoints": [
      {
        "platform_code": "aidso_doubao_web",
        "platform_name": "豆包·网页",
        "endpoint_type": "web",
        "endpoint_label": "网页",
        "display_name": "豆包·网页",
        "thinking_mode": "专家",
        "enabled": true,
        "citation_supported": true,
        "search_enabled": true
      }
    ]
  }
]
```

主要逻辑：

1. 读取 `AIPlatform` 列表。
2. 优先从 `extra_config` 读取 `base_platform`、`endpoint_type`、`endpoint_label`、`logo_url`、`thinking_mode`。
3. 如果历史数据没有 `extra_config`，用 `platform_name` 或 `platform_code` 做兼容解析。
4. 按 `base_platform` 分组，端顺序为 `web`、`app`、其他。
5. 返回时不要修改数据库。

兼容解析建议：

| 线索 | 推导 |
| --- | --- |
| `platform_name` 包含 `网页` 或 `_web` | `endpoint_type=web`、`endpoint_label=网页` |
| `platform_name` 包含 `手机`、`APP` 或 `_app` | `endpoint_type=app`、`endpoint_label=手机` |
| `platform_code` 包含 `doubao` | `base_platform=豆包` |
| `platform_code` 包含 `deepseek` | `base_platform=Deepseek` |
| `platform_code` 包含 `yuanbao` | `base_platform=元宝` |
| `platform_code` 包含 `qwen` | `base_platform=千问` |

**接口 2：Prompt 类型字典**

`GET /prompt-types`

Response `data`:

```json
[
  {
    "code": "brand_sentiment",
    "label": "品牌情绪类",
    "legacy_values": ["品牌情绪类"],
    "description": "评价、口碑、是否值得等品牌判断问题"
  },
  {
    "code": "brand_info",
    "label": "品牌信息类",
    "legacy_values": ["品牌信息类"],
    "description": "价格、地址、营业时间、门票等事实信息问题"
  },
  {
    "code": "category_sentiment",
    "label": "品类情绪类",
    "legacy_values": ["品类情绪类"],
    "description": "对品类整体是否值得、好不好玩的判断问题"
  },
  {
    "code": "competitor_comparison",
    "label": "竞品对比类",
    "legacy_values": ["竞品对比类", "comparison"],
    "description": "品牌与竞品二选一、多品牌比较问题"
  },
  {
    "code": "category_recommendation",
    "label": "品类推荐类",
    "legacy_values": ["品类推荐类", "recommendation"],
    "description": "推荐清单、攻略、去哪玩等品类问题"
  }
]
```

**接口 3：信源类型字典**

`GET /source-types`

Response `data`:

```json
[
  { "code": "official_vertical", "label": "官网/独立站/行业垂直" },
  { "code": "portal_media", "label": "门户/自媒体平台" },
  { "code": "ecommerce", "label": "电商平台" },
  { "code": "government", "label": "政府/公共机构" },
  { "code": "video", "label": "视频平台" },
  { "code": "mainstream_media", "label": "央媒/主流媒体" },
  { "code": "community", "label": "社区/论坛/博客" },
  { "code": "local_media", "label": "地方媒体/新闻" },
  { "code": "other", "label": "其它" }
]
```

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_metadata_api.py
```

验收点：

- `GET /platform-endpoints` 返回分组结构，至少覆盖测试平台 `qwen/deepseek`。
- `GET /prompt-types` 返回 5 个原型意图类型。
- `GET /source-types` 返回 9 个信源类型。
- `backend/app/geo_monitoring/api/__init__.py` 已注册新 router。

### Task P0-2：项目管理聚合接口

**目标：** 支撑项目管理页卡片，不再由前端对每个项目调用 `monitor-setup` 和 `dashboard`。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：3.1、10.P0
- `docs/API接口文档.md`：4. 监测项目、8. 监测设置、15. 看板与趋势

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/project_overview.py`
- Create: `backend/app/geo_monitoring/services/project_overview.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_project_overview_api.py`
- Docs: `docs/API接口文档.md`

**接口：项目卡片聚合列表**

`GET /projects/overview`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | `1` | 页码 |
| `page_size` | integer | `10` | 1-100 |
| `project_name` | string/null | null | 项目名模糊搜索 |
| `status` | string/null | null | `active` / `disabled` / `archived` |

Response `data`:

```json
{
  "items": [
    {
      "id": 1,
      "project_name": "杭州宋城",
      "industry": "文旅演艺",
      "status": "active",
      "monitoring_status": "monitoring",
      "brand": {
        "id": 1,
        "brand_name": "杭州宋城",
        "brand_words": ["杭州宋城", "宋城千古情"]
      },
      "competitors": [
        { "id": 2, "brand_name": "印象西湖" }
      ],
      "selected_platform_codes": ["aidso_doubao_web", "aidso_doubao_app"],
      "platform_count": 1,
      "endpoint_count": 2,
      "question_count": 20,
      "latest_run": {
        "run_id": 10,
        "status": "completed",
        "collection_status": "completed",
        "analysis_status": "completed",
        "completed_at": "2026-06-24T10:00:00"
      },
      "updated_at": "2026-06-24T10:00:00"
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

主要逻辑：

1. 复用项目分页查询条件。
2. 批量查询项目目标品牌、品牌别名、竞品、最新运行、激活/草稿 PromptSet 的问题数。
3. 平台数按 `platform_code` 映射到 `base_platform` 去重；端数为 `selected_platform_codes.length`。
4. `monitoring_status`：
   - `project.status != active` -> `disabled`
   - 最新运行 `status in collecting/analyzing/reporting/pending` -> `running`
   - 无运行但项目 active -> `monitoring`
   - 后续实现暂停后支持 `paused`
5. 严禁循环调用 service 造成 N+1；用批量查询或少量聚合查询。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_project_overview_api.py
```

验收点：

- 空项目时返回分页空列表。
- 有品牌词、竞品、问题集、默认平台时字段正确。
- 有最新运行时返回 `latest_run`。
- 删除项目不出现在列表。

### Task P0-3：AI 生成辅助接口

**目标：** 支撑创建项目和编辑配置中的“AI 生成品牌词 / AI 生成竞品 / AI 智能生成问题”。MVP 阶段可先实现规则生成，后续再接真实 LLM。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：3.2、4.1、10.P0
- `docs/API接口文档.md`：7. Prompt 词库、8. 监测设置

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/ai_generation.py`
- Create: `backend/app/geo_monitoring/services/ai_generation.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_ai_generation_api.py`
- Docs: `docs/API接口文档.md`

**接口 1：生成品牌词**

`POST /projects/{project_id}/ai/brand-words:generate`

Body:

```json
{
  "brand_name": "杭州宋城",
  "category": "杭州旅游",
  "official_domain": "https://www.hzsongcheng.com",
  "limit": 10
}
```

Response:

```json
{
  "brand_words": ["杭州宋城", "宋城千古情", "宋城演艺", "杭州宋城景区", "千古情"]
}
```

**接口 2：生成竞品**

`POST /projects/{project_id}/ai/competitors:generate`

Body:

```json
{
  "brand_name": "杭州宋城",
  "category": "杭州旅游",
  "region": "杭州",
  "limit": 10
}
```

Response:

```json
{
  "competitors": [
    {
      "brand_name": "印象西湖",
      "competitor_words": ["印象西湖演出", "印象西湖秀"],
      "official_domain": null,
      "reason": "同城演艺/文旅竞争对象"
    }
  ]
}
```

**接口 3：生成监测问题**

`POST /projects/{project_id}/ai/questions:generate`

Body:

```json
{
  "brand_name": "杭州宋城",
  "category": "杭州旅游",
  "competitors": ["印象西湖", "横店"],
  "core_keywords": ["杭州旅游"],
  "intent_distribution": {
    "brand_sentiment": 5,
    "brand_info": 5,
    "category_sentiment": 2,
    "competitor_comparison": 4,
    "category_recommendation": 4
  },
  "limit": 20
}
```

Response:

```json
{
  "questions": [
    {
      "prompt_text": "杭州宋城怎么样？",
      "prompt_type": "品牌情绪类",
      "core_keyword": "杭州旅游",
      "reason": "覆盖品牌口碑评价"
    }
  ]
}
```

主要逻辑：

1. 先实现 deterministic 规则生成，确保测试稳定。
2. 品牌词去重、去空白，必须包含 `brand_name`。
3. 竞品生成优先基于 category/region 的固定规则；如果没有命中，返回通用同类品牌。
4. 问题生成按 5 类意图模板生成，去重后按 `limit` 截断。
5. 不直接写数据库；只返回候选，保存仍走 `PUT /monitor-setup`。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_ai_generation_api.py
```

验收点：

- 品牌名为空返回参数校验失败。
- 宋城/杭州旅游示例返回原型中的品牌词、竞品、问题类型。
- 生成接口不改变数据库里的 monitor setup。

### Task P0-4：Dashboard 页面级总览接口

**目标：** 支撑数据大盘首屏，返回 KPI、平台表现、竞品预览、信源预览、最近问题预览。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：5.1、10.P0/P1
- `docs/API接口文档.md`：14. 分析与 Agent 审计、15. 看板与趋势

**涉及文件：**

- Modify: `backend/app/geo_monitoring/api/dashboard.py`
- Modify: `backend/app/geo_monitoring/services/dashboard.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_dashboard_api.py`
- Docs: `docs/API接口文档.md`

**接口：大盘页面级总览**

`GET /projects/{project_id}/dashboard/overview`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `run_id` | integer/null | null | 指定运行 |
| `platform_codes` | string[]/null | null | 平台端筛选 |
| `start_at` / `end_at` | datetime/null | null | 趋势/预览时间范围 |

Response:

```json
{
  "project_id": 1,
  "run_id": 10,
  "kpis": {
    "mention_rate": { "value": "0.3520", "delta": null },
    "top1_rate": { "value": "0.1850", "delta": null },
    "top3_rate": { "value": "0.4200", "delta": null },
    "average_rank": { "value": null, "delta": null },
    "sov": { "value": null, "delta": null },
    "conversation_count": { "value": 1820, "delta": null },
    "mentioned_conversation_count": { "value": 640, "delta": null },
    "brand_mention_count": { "value": 1240, "delta": null }
  },
  "platforms": [
    {
      "platform_code": "aidso_doubao_web",
      "platform_name": "豆包·网页",
      "mention_rate": "0.5310",
      "top1_rate": "0.2650",
      "top3_rate": "0.4100",
      "top10_rate": null,
      "sov": null,
      "conversation_count": 312,
      "average_rank": null
    }
  ],
  "competitor_preview": [
    {
      "brand_id": 1,
      "brand_name": "杭州宋城",
      "mention_rate": "0.3520",
      "average_rank": null,
      "top1_rate": "0.1850",
      "is_target": true
    }
  ],
  "source_preview": [
    {
      "rank": 1,
      "site": "携程旅行",
      "source_type": "电商平台",
      "share_rate": "0.1230",
      "citation_count": 20
    }
  ],
  "recent_questions": [
    {
      "prompt_id": 1,
      "prompt_text": "杭州有哪些必去的演艺项目？",
      "brand_visibility_rate": "1.0000",
      "average_rank": "1.3",
      "latest_collected_at": "2026-06-23T10:00:00"
    }
  ]
}
```

主要逻辑：

1. 复用 `build_project_dashboard` 获取 latest run、summary、platform analysis。
2. `platform_codes` 只过滤返回展示，不改变底层 run。
3. `mention_rate/top1/top3/conversation_count/mentioned_conversation_count` 从现有 summary 计算。
4. `average_rank/sov/top10_rate` 当前可返回 `null`，并在 P1 指标任务补齐。
5. `source_preview` 优先查询 `SourceStat`，没有时退化到 `PlatformAnalysis.top_sources`。
6. `recent_questions` 可复用 Task P0-6 的 service；若 Task P0-6 未做，先返回空数组并测试说明。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_dashboard_api.py
```

验收点：

- 已分析 run 返回 KPI 和平台表现。
- 只有采集未分析 run 时，KPI 可为空/null，但不报错。
- `platform_codes` 能过滤平台列表。
- 没有运行时返回 `run_id=null`、数组为空。

### Task P0-5：竞品分析页面级接口

**目标：** 支撑竞品分析页的本品牌 KPI、Top10 榜单、趋势。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：6、10.P0/P1
- `docs/API接口文档.md`：14、15

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/competitor_analysis.py`
- Create: `backend/app/geo_monitoring/services/competitor_analysis.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_competitor_analysis_api.py`
- Docs: `docs/API接口文档.md`

**接口：竞品分析**

`GET /projects/{project_id}/competitor-analysis`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `run_id` | integer/null | null | 指定运行 |
| `platform_codes` | string[]/null | null | 平台端筛选 |
| `start_at` / `end_at` | datetime/null | null | 趋势时间 |
| `brand_scope` | `top5` / `all` | `top5` | 趋势品牌范围 |

Response:

```json
{
  "project_id": 1,
  "run_id": 10,
  "target_brand": {
    "brand_id": 1,
    "brand_name": "杭州宋城"
  },
  "kpis": {
    "mention_rate": "0.3520",
    "mention_count": 1240,
    "average_rank": null,
    "top1_rate": "0.1850",
    "historical_best": {},
    "industry_average": {},
    "market_position": {
      "mention_rate_rank": 1,
      "mention_count_rank": 1,
      "average_rank_rank": null,
      "top1_rate_rank": 1
    }
  },
  "boards": {
    "mention_rate": [
      { "brand_id": 1, "brand_name": "杭州宋城", "value": "0.3520", "is_target": true, "rank": 1 }
    ],
    "average_rank": [],
    "mention_count": [
      { "brand_id": 1, "brand_name": "杭州宋城", "value": 1240, "is_target": true, "rank": 1 }
    ]
  },
  "trends": {
    "days": [],
    "mention_rate": [],
    "average_rank": [],
    "mention_count": []
  }
}
```

主要逻辑：

1. 目标品牌来自项目 `brand_type=target`。
2. 竞品来自项目 `brand_type=competitor`。
3. 榜单优先基于 `PlatformAnalysis.summary_json.metrics.brand_metrics` 或 `top_competitors`；如果当前分析 JSON 没有全品牌数据，则至少返回目标品牌 + top competitors 的 mention rate。
4. `mention_count` 可从 `BrandResult.mention_count` 聚合；如数据量大，后续 P1 增加指标快照。
5. `average_rank` 当前若没有可靠计算，返回空榜/`null`，但接口字段保留。
6. 趋势先复用 `MetricSnapshot`；没有多品牌趋势时返回空数组。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_competitor_analysis_api.py
```

验收点：

- 无分析数据时返回空榜，不报错。
- 有分析数据时目标品牌出现在 KPI 与榜单中，并 `is_target=true`。
- `brand_scope=top5/all` 参数校验有效。

### Task P0-6：AI 对话记录聚合接口

**目标：** 支撑 AI 对话记录主表、行内平台端指标、回答弹窗。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：7、10.P0/P1
- `docs/API接口文档.md`：11、13

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/conversations.py`
- Create: `backend/app/geo_monitoring/services/conversations.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_conversations_api.py`
- Docs: `docs/API接口文档.md`

**接口 1：问题聚合列表**

`GET /projects/{project_id}/conversation-questions`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `run_id` | integer/null | null | 指定运行 |
| `platform_codes` | string[]/null | null | 平台端筛选 |
| `start_at` / `end_at` | datetime/null | null | 回答采集时间 |
| `keyword` | string/null | null | 搜索 AI 问题 |
| `page` | integer | 1 | 页码 |
| `page_size` | integer | 10 | 每页条数 |

Response:

```json
{
  "items": [
    {
      "prompt_id": 1,
      "prompt_text": "杭州有哪些必去的演艺项目？",
      "prompt_type": "品类推荐类",
      "brand_visibility_rate": "1.0000",
      "mention_count": 12,
      "average_rank": "1.3",
      "top1_rate": "0.8333",
      "top3_rate": "1.0000",
      "positive_rate": "0.9250",
      "neutral_rate": "0.0750",
      "negative_rate": "0.0000",
      "latest_collected_at": "2026-06-23T10:00:00",
      "platform_metrics": [
        {
          "platform_code": "aidso_doubao_web",
          "platform_name": "豆包·网页",
          "visibility_rate": "1.0000",
          "mention_count": 4,
          "average_rank": "2.0",
          "top1_rate": "0.5000",
          "top3_rate": "1.0000",
          "answer_count": 1
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

**接口 2：问题回答聚合**

`GET /projects/{project_id}/conversation-questions/{prompt_id}/answers`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `run_id` | integer/null | null | 指定运行 |
| `platform_codes` | string[]/null | null | 平台端筛选 |

Response:

```json
{
  "project_id": 1,
  "run_id": 10,
  "prompt_id": 1,
  "prompt_text": "杭州有哪些必去的演艺项目？",
  "answers": [
    {
      "answer_id": 100,
      "platform_code": "aidso_doubao_web",
      "platform_name": "豆包·网页",
      "model_name": "doubao",
      "raw_text": "推荐杭州宋城...",
      "normalized_text": "推荐杭州宋城...",
      "reasoning_text": null,
      "search_keywords": [],
      "collected_at": "2026-06-23T10:00:00",
      "brand_results": [
        {
          "brand_id": 1,
          "brand_name": "杭州宋城",
          "is_mentioned": true,
          "mention_count": 4,
          "first_position": 2,
          "sentiment": "positive",
          "context_json": {}
        }
      ],
      "citations": [
        {
          "citation_no": 1,
          "site": "携程旅行",
          "title": "杭州宋城旅游攻略",
          "url": "https://example.com/a",
          "domain": "example.com",
          "source_type": "电商平台",
          "quoted_text": null
        }
      ]
    }
  ]
}
```

主要逻辑：

1. 最新 run 选择逻辑复用 dashboard。
2. 主表按 `prompt_id` 聚合，而不是按 answer 聚合。
3. 有效答案：关联任务成功且 `normalized_text/raw_text` 非空。可复用 `analysis.metrics.filter_valid_answers` 思路。
4. 目标品牌：项目 `brand_type=target`。
5. 可见度：目标品牌 `is_mentioned=true` 的答案数 / 有效答案数。
6. 提及次数：目标品牌 `mention_count` 求和。
7. 平均排名：目标品牌 `first_position` 存在时按位置排序或直接用 `first_position` 的平均；MVP 可先用 `first_position` 平均。
8. Top1/Top3：平均前先按单答案 `first_position <= 1/3` 判断。
9. 情感：`sentiment=positive/neutral/negative` 聚合。
10. `reasoning_text/search_keywords` 当前无字段，先返回 `null/[]`；后续采集扩展。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_conversations_api.py
```

验收点：

- 多个答案同 prompt 聚合成一行。
- `keyword` 能过滤问题文本。
- `platform_codes` 能过滤平台端指标。
- 回答详情返回引用和品牌名称。
- 无引用时 `citations=[]`，无品牌结果时 `brand_results=[]`。

### Task P0-7：信源引用分析页面级接口

**目标：** 支撑信源引用分析页 KPI、类型分布、站点 TOP10、平台端矩阵、指标口径切换。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：8、10.P0/P1
- `docs/API接口文档.md`：13、14、15

**涉及文件：**

- Create: `backend/app/geo_monitoring/api/source_analysis.py`
- Create: `backend/app/geo_monitoring/services/source_analysis.py`
- Modify: `backend/app/geo_monitoring/api/__init__.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Test: `backend/tests/geo_monitoring/test_source_analysis_api.py`
- Docs: `docs/API接口文档.md`

**接口：信源分析总览**

`GET /projects/{project_id}/source-analysis`

Query:

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `run_id` | integer/null | null | 指定运行 |
| `platform_codes` | string[]/null | null | 平台端筛选 |
| `start_at` / `end_at` | datetime/null | null | 时间范围 |
| `source_type` | string | `all` | 信源类型 |
| `keyword` | string/null | null | 站点搜索 |
| `metric` | `cites` / `links` / `rate` | `cites` | 指标口径 |
| `page` | integer | 1 | 页码 |
| `page_size` | integer | 10 | 每页条数 |

Response:

```json
{
  "project_id": 1,
  "run_id": 10,
  "kpis": {
    "article_count": 156,
    "citation_count": 623,
    "site_count": 87
  },
  "type_distribution": [
    {
      "source_type": "官网/独立站/行业垂直",
      "citation_count": 293,
      "rate": "0.4700"
    }
  ],
  "type_trends": [
    {
      "date": "2026-06-22",
      "source_type": "官网/独立站/行业垂直",
      "rate": "0.4700"
    }
  ],
  "sites": {
    "items": [
      {
        "rank": 1,
        "site": "携程旅行",
        "domain": "ctrip.com",
        "source_type": "电商平台",
        "total_citation_count": 54,
        "total_link_count": 38,
        "citation_rate": "0.0867",
        "display_value": 54,
        "platform_values": [
          {
            "platform_code": "aidso_doubao_web",
            "platform_name": "豆包·网页",
            "citation_count": 16,
            "link_count": 11,
            "citation_rate": "0.1200",
            "display_value": 16,
            "has_citation_data": true
          }
        ]
      }
    ],
    "total": 10,
    "page": 1,
    "page_size": 10
  }
}
```

主要逻辑：

1. 优先使用 `SourceStat` 聚合。
2. `article_count`：可先按引用 URL 去重计算；若只用 `SourceStat` 无 URL 粒度，则 MVP 用 `sum(link_count估算)`，并在字段注释说明。更推荐从 `Citation.url` 查询去重。
3. `citation_count`：所选平台 `SourceStat.citation_count` 求和。
4. `site_count`：所选平台下 distinct domain。
5. `type_distribution`：按 `source_type` 聚合 citation_count，rate = 类型引用次数 / 总引用次数。
6. `type_trends`：MVP 可基于 `MetricSnapshot` 或当前 run 返回单日数据；后续补完整趋势。
7. `sites.items`：按 domain/source_name 聚合，支持类型和 keyword 过滤。
8. `platform_values`：每个平台端一列，缺数据返回 `has_citation_data=false`、数值为 0/null。
9. `metric=links` 时 `display_value=link_count`；`metric=rate` 时 `display_value=citation_rate`。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_source_analysis_api.py
```

验收点：

- 无信源数据时 KPI 为 0、列表为空。
- 有多平台 `SourceStat` 时能返回矩阵列。
- `source_type`、`keyword`、`metric` 过滤/切换有效。
- `platform_codes` 只返回选中平台列并更新 KPI。

## 6. P1 开发任务

### Task P1-1：补齐指标口径与快照

**目标：** 让大盘、竞品、对话记录中当前 `null` 的核心指标变成稳定后端口径。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：5.1、6、7、10.P1
- `docs/API接口文档.md`：14、15

**涉及文件：**

- Modify: `backend/app/geo_monitoring/analysis/metrics.py`
- Modify: `backend/app/geo_monitoring/analysis/brands.py`
- Modify: `backend/app/geo_monitoring/services/analysis.py`
- Modify: `backend/app/geo_monitoring/services/dashboard.py`
- Test: `backend/tests/geo_monitoring/analysis/test_metrics.py`
- Test: `backend/tests/geo_monitoring/test_dashboard_api.py`
- Docs: `docs/API接口文档.md`

需要新增/固化的 `metric_code`：

| 指标 | metric_code | 计算口径 |
| --- | --- | --- |
| 平均提及排名 | `average_mention_rank` | 目标品牌在提及答案中的排名平均值，越小越好 |
| SOV | `share_of_voice` | 目标品牌出现对话数 / 所有品牌出现对话总数 |
| Top10 提及率 | `brand_top10_mention_rate` | 目标品牌排名 <= 10 的有效回答数 / 有效回答数 |
| 品牌提及次数 | `brand_mention_total_count` | 目标品牌 `mention_count` 求和 |
| 正/中/负情感率 | `positive_rate`、`neutral_rate`、`negative_rate` | 对目标品牌提及答案按 sentiment 聚合 |

主要逻辑：

1. 在纯函数层写测试，先覆盖空分母、未提及、多个品牌、多条答案。
2. 在分析写入阶段生成 `MetricSnapshot`，同时写入 `PlatformAnalysis.summary_json.metrics`。
3. Dashboard/Competitor/Conversation 接口优先读取快照或 summary，不重复复杂计算。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\analysis\test_metrics.py
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_dashboard_api.py
```

验收点：

- 新指标在单平台、多平台分析后出现在 `GET /dashboard` 的 `summary.metrics`。
- 大盘 overview 中 `average_rank/sov/top10_rate/brand_mention_count` 不再恒为 null。

### Task P1-2：导出接口

**目标：** 支撑原型中“AI 对话记录导出 Excel”和后续信源导出。

**涉及文档：**

- `docs/原型功能_API映射与缺口清单.md`：7、8、10.P1

**涉及文件：**

- Modify: `backend/app/geo_monitoring/api/conversations.py`
- Modify: `backend/app/geo_monitoring/services/conversations.py`
- Modify: `backend/app/geo_monitoring/api/source_analysis.py`
- Modify: `backend/app/geo_monitoring/services/source_analysis.py`
- Test: `backend/tests/geo_monitoring/test_conversations_api.py`
- Test: `backend/tests/geo_monitoring/test_source_analysis_api.py`

接口：

- `GET /projects/{project_id}/conversation-questions/export`
- `GET /projects/{project_id}/source-analysis/export`

Query 与对应列表接口一致。

返回：

- `Content-Type: text/csv; charset=utf-8` 作为 MVP。
- 后续如要真正 Excel，再切换为 `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`。

测试验证：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_conversations_api.py::test_export_conversation_questions_csv
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_source_analysis_api.py::test_export_source_analysis_csv
```

验收点：

- 响应不是统一 JSON，而是文件流。
- CSV 包含 UTF-8 BOM 或明确 UTF-8，中文列名不乱码。
- 筛选条件与列表接口一致。

## 7. P2 开发任务

### Task P2-1：一步创建完整项目

**目标：** 将 `POST /projects` 与 `PUT /monitor-setup` 包成一个事务接口，避免创建向导保存一半失败。

**接口：**

`POST /projects:setup`

Body:

```json
{
  "project": {
    "project_name": "杭州宋城",
    "industry": "文旅演艺",
    "timezone": "Asia/Shanghai",
    "official_domain": "https://www.hzsongcheng.com"
  },
  "monitor_setup": {
    "brand": {
      "brand_name": "杭州宋城",
      "brand_words": ["杭州宋城", "宋城千古情"]
    },
    "competitors": [],
    "core_keywords": [{ "keyword": "杭州旅游" }],
    "ai_questions": [],
    "selected_platform_codes": ["qwen"],
    "activate_prompt_set": true
  },
  "run_after_create": false
}
```

Response:

```json
{
  "project": {},
  "monitor_setup": {},
  "run": null
}
```

验收点：

- 任一保存步骤失败时数据库不留下半成品项目。
- `run_after_create=true` 时返回新 run。

### Task P2-2：项目暂停/恢复与删除检查

接口：

- `POST /projects/{project_id}/pause`
- `POST /projects/{project_id}/resume`
- `GET /projects/{project_id}/delete-check`

建议逻辑：

- 暂停只影响调度和新运行，不删除项目、不禁用历史数据。
- 恢复后允许手动运行和调度运行。
- 删除检查返回运行数、报告数、调度数、是否可删除、阻塞原因。

## 8. 文档更新要求

每完成一个任务，必须同步更新：

| 文档 | 更新内容 |
| --- | --- |
| `docs/API接口文档.md` | 新接口路径、入参、出参、错误码、示例 |
| `docs/API测试文档.md` | 新接口测试用例与命令 |
| `docs/API全量接口测试报告.md` | 若执行全量测试，追加或更新测试结果 |
| `docs/原型功能_API映射与缺口清单.md` | 将已完成缺口标注为已覆盖，更新调用建议 |

## 9. 推荐开发顺序

1. P0-1 平台端元数据与字典接口。
2. P0-2 项目管理聚合接口。
3. P0-3 AI 生成辅助接口。
4. P0-6 AI 对话记录聚合接口。
5. P0-7 信源引用分析接口。
6. P0-5 竞品分析接口。
7. P0-4 Dashboard overview 接口。
8. P1-1 指标口径与快照补齐。
9. P1-2 导出接口。
10. P2-1/P2-2 系统体验增强。

说明：对话记录、信源、竞品接口会沉淀可复用聚合服务，Dashboard overview 可以直接复用它们，因此建议先做 P0-6/P0-7/P0-5，再做 P0-4 的完整预览聚合。

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

如果本次任务改动了源码且验收通过，按仓库规则更新 CodeGraph：

```powershell
codegraph status
codegraph sync
codegraph status
```

## 11. Cursor 执行提示词建议

可在 Cursor 中按以下格式下达任务：

```text
执行 docs/Cursor接口缺口开发任务书.md 的 Task P0-1：平台端元数据与基础字典接口。
要求：
1. 先读任务书中的 Task P0-1、docs/API接口文档.md 对应 AI 平台章节、现有 platforms API 和测试。
2. 按 TDD：先写失败测试，再实现接口。
3. 使用 backend/.venv 执行 pytest。
4. 完成后更新 docs/API接口文档.md、docs/API测试文档.md，并汇报缺口清单中哪些项已覆盖。
```

## 12. 风险与注意事项

- 不要为了页面聚合接口过早新增大量表；先复用现有分析表、答案表、引用表和快照表。
- 聚合接口必须避免 N+1 查询，尤其是项目概览、对话问题列表和信源矩阵。
- 比率字段保持 decimal 字符串，前端统一格式化百分比。
- 新接口应同时挂载到 `/api/geo-monitoring` 和 `/api/v1/geo-monitoring`，通过 `api/__init__.py` 的 router 聚合自动实现。
- 导出接口返回文件流，不使用统一 JSON 响应。
- `platform_codes` 多选筛选要明确：只过滤聚合展示，不修改 run 原始平台集合。
- 当前 `reasoning_text/search_keywords` 没有明确存储字段，P0 先返回 `null/[]`，不要伪造内容。
- 如果新增错误码，必须同步 `docs/API接口文档.md` 附录。
