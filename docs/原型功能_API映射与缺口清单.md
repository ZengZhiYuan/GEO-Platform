# 原型功能 API 映射与缺口清单

> 基于 `docs/API接口文档.md`、`backend/app/geo_monitoring/api/`、`backend/app/geo_monitoring/schemas.py`、`backend/app/geo_monitoring/services/` 与 6 个高保真原型页面整理。  
> 更新日期：2026-06-24  
> 主前缀：`/api/geo-monitoring`；兼容前缀：`/api/v1/geo-monitoring`。  
> 统一响应：除报告下载外，均为 `{ "code": 0, "message": "success", "data": ... }`；分页接口 `data` 为 `{ items, total, page, page_size }`。

## 1. 覆盖状态总览

| 原型页面 | 功能模块 | 当前 API 支撑状态 | 说明 |
| --- | --- | --- | --- |
| 项目管理 | 项目列表、项目切换、创建入口、编辑配置、暂停/删除 | 部分覆盖 | 项目 CRUD 已有；项目卡汇总、暂停语义、项目切换下拉所需轻量列表需补强 |
| 创建监测项目 | 三步向导、品牌词、竞品、监测问题、平台端选择、完成摘要 | 部分覆盖 | 项目创建 + `monitor-setup` 可保存核心配置；AI 生成品牌词/竞品/问题尚无后端接口 |
| 数据大盘 | KPI、平台表现、竞品预览、信源预览、最近问题、下载报告 | 部分覆盖 | Dashboard/Analysis/Trend/Report 已有；页面级聚合、时间/平台筛选、竞品/信源预览接口不足 |
| 竞品分析 | 本品牌核心指标、Top10 榜单、趋势、Top5/全部切换 | 部分覆盖 | 底层分析含 `top_competitors` 和品牌指标，但缺页面级竞品 Top10/趋势接口 |
| AI 对话记录 | 问题表、平台端明细、回答弹窗、引用来源、导出 | 部分覆盖 | 答案详情有原文、引用、品牌识别；缺按问题聚合列表、平台端指标、弹窗聚合与导出接口 |
| 信源引用分析 | KPI、类型分布、类型趋势、站点影响力矩阵、指标切换 | 部分覆盖 | 分析结果有 `top_sources` 与引用明细；缺页面级信源分析接口、类型聚合、矩阵、筛选 |

状态说明：

- **可直接调用**：现有接口响应字段基本满足原型展示。
- **前端聚合可实现**：可通过多个底层接口拼出，但调用多、计算复杂、口径容易不一致。
- **缺口 API**：当前没有明确接口或字段，建议后端补齐。

## 2. 通用数据与页面初始化

### 2.1 全局健康与就绪

| 功能 | API | 入参 | 出参展示 |
| --- | --- | --- | --- |
| 服务健康检查 | `GET /api/health` 或 `GET /api/geo-monitoring/health` | 无 | `status/app/env`，用于运维或前端启动探测 |
| 服务就绪检查 | `GET /api/ready` 或 `GET /api/geo-monitoring/ready` | 无 | `status/database/redis/nacos` |

### 2.2 顶部项目切换器

原型位置：所有业务页右上角“杭州宋城”项目选择器。

推荐调用顺序：

1. `GET /projects?page=1&page_size=100&status=active`
2. 前端选中当前 `project_id`，后续页面请求都带该项目 ID。
3. 切换项目时刷新当前页面的数据接口。

接口字段：

| API | 入参 | 出参字段 | 原型展示 |
| --- | --- | --- | --- |
| `GET /projects` | `page`、`page_size`、`project_name?`、`status?` | `items[].id`、`project_name`、`status`、`default_platform_codes`、`updated_at` | 项目下拉名称、当前项目、默认平台 |

缺口 API：

| 缺口 | 建议接口 | 用途 |
| --- | --- | --- |
| 项目切换器轻量列表 | `GET /projects/options` | 只返回 `id/project_name/status/is_current`，避免拉完整分页模型 |
| 当前项目记忆 | `GET/PUT /users/me/preferences/current-project` | 原型有“统一项目切换器”，当前项目应跨页面保持；当前后端未见账号偏好接口 |

### 2.3 平台端选择器

原型统一使用“平台 × 端”：豆包、Deepseek、元宝、千问含网页/手机；百度AI、文心、KIMI、AI抖音仅网页。

现有接口：

| API | 入参 | 出参字段 | 原型展示 |
| --- | --- | --- | --- |
| `GET /platforms?page=1&page_size=100&enabled=true` | `enabled?` | `platform_code`、`platform_name`、`adapter_type`、`search_enabled`、`citation_supported`、`extra_config` | 平台多选候选项 |
| `PUT /platforms/{platform_code}` | 平台配置字段 | `AIPlatformOut` | 管理后台启停或配置平台 |

缺口 API/字段：

| 缺口 | 建议 | 影响 |
| --- | --- | --- |
| 平台端结构化字段 | 在 `AIPlatformOut` 增加 `base_platform`、`endpoint_type`、`display_name`、`logo_url`、`thinking_mode` | 前端不应从 `platform_code` 猜“豆包·网页/手机”和 logo |
| 平台端分组接口 | `GET /platform-endpoints` | 直接返回原型所需分组：`[{ base, logo_url, endpoints:[{ code, end, enabled, thinking_mode }] }]` |

## 3. 项目管理页

### 3.1 项目列表卡

原型功能：

- 展示项目列表数量。
- 项目卡展示：项目名、当前、监测中、品牌词、竞品、监测平台 logo、平台数、端数、问题数、更新时间。
- 项目操作：编辑配置、暂停、删除。

推荐调用顺序：

1. `GET /projects?page=1&page_size=10`
2. 对每个项目调用 `GET /projects/{project_id}/monitor-setup`
3. 如需最近状态，调用 `GET /projects/{project_id}/dashboard`
4. 前端合成项目卡。

字段映射：

| 原型字段 | API 来源 | 字段路径/计算 |
| --- | --- | --- |
| 项目名 | `GET /projects` | `items[].project_name` |
| 当前项目 | 前端状态 | 当前选择的 `project_id` |
| 监测中 | `GET /projects` + `GET /dashboard` | `status=active` 且 `latest_run.status` 非失败/取消；当前没有单独监测开关 |
| 品牌词 | `GET /monitor-setup` | `brand.brand_words[]` |
| 竞品 | `GET /monitor-setup` | `competitors[].brand_name` |
| 平台数/端数 | `GET /monitor-setup` | `selected_platform_codes.length`，端/平台分组需前端根据平台编码或新增平台端字段计算 |
| 问题数 | `GET /monitor-setup` | `ai_questions.length` |
| 更新时间 | `GET /projects` | `updated_at` |

当前可用 API：

| API | 入参 | 出参字段 |
| --- | --- | --- |
| `GET /projects` | `page`、`page_size`、`project_name?`、`status?` | 分页 `ProjectOut[]` |
| `GET /projects/{project_id}` | `project_id` | `ProjectOut` |
| `PUT /projects/{project_id}` | `ProjectUpdate` | `ProjectOut` |
| `DELETE /projects/{project_id}` | `project_id` | `{ id }` |
| `GET /projects/{project_id}/monitor-setup` | `project_id` | 品牌、竞品、核心词、问题、平台配置 |
| `GET /projects/{project_id}/dashboard` | `run_id?` | 最近运行与分析汇总 |

缺口 API：

| 缺口 | 建议接口/改造 | 说明 |
| --- | --- | --- |
| 项目卡聚合接口 | `GET /projects/overview` | 返回项目列表 + 品牌词摘要 + 竞品摘要 + 平台端数 + 问题数 + 最近运行状态，避免 N+1 调用 |
| 暂停/恢复监测 | `POST /projects/{project_id}/pause`、`POST /projects/{project_id}/resume` 或 `PUT /projects/{id}` 增加 `monitoring_enabled` | 现有 `status=disabled` 更像项目停用，不等同“暂停监测任务” |
| 删除前影响检查 | `GET /projects/{project_id}/delete-check` | 当前删除被运行引用会 `40903`，但原型需要更友好的确认提示 |

### 3.2 编辑配置抽屉/弹层

原型功能：

- Tab 1：基础、品牌词、平台、深度思考、官网。
- Tab 2：竞品配置。
- Tab 3：监测问题、意图分布、批量添加、编辑分类、删除。

推荐调用顺序：

1. 打开编辑配置：`GET /projects/{project_id}/monitor-setup`
2. 前端编辑本地草稿。
3. 保存：`PUT /projects/{project_id}/monitor-setup`
4. 如果问题需要立即生效，传 `activate_prompt_set=true`。

`GET /monitor-setup` 出参格式：

```json
{
  "brand": {
    "id": 1,
    "brand_name": "杭州宋城",
    "official_domain": "https://www.hzsongcheng.com",
    "description": null,
    "brand_words": ["杭州宋城", "宋城千古情"]
  },
  "competitors": [
    { "id": 2, "brand_name": "印象西湖", "competitor_words": ["印象西湖演出"] }
  ],
  "core_keywords": [
    { "id": 1, "keyword": "杭州旅游", "description": null, "sort_order": 0, "enabled": true }
  ],
  "ai_questions": [
    {
      "prompt_id": 1,
      "prompt_code": "Q001",
      "prompt_text": "杭州宋城怎么样？",
      "prompt_type": "品牌情绪类",
      "core_keyword": "杭州旅游",
      "core_keyword_id": 1,
      "from_library": false
    }
  ],
  "available_platforms": [
    { "platform_code": "aidso_doubao_web", "platform_name": "豆包·网页", "enabled": true }
  ],
  "selected_platform_codes": ["aidso_doubao_web"],
  "draft_prompt_set_id": 10,
  "active_prompt_set_id": 9
}
```

`PUT /monitor-setup` 入参格式：

```json
{
  "brand": {
    "brand_name": "杭州宋城",
    "official_domain": "https://www.hzsongcheng.com",
    "description": null,
    "brand_words": ["杭州宋城", "宋城千古情", "千古情"]
  },
  "competitors": [
    { "brand_name": "印象西湖", "competitor_words": ["印象西湖演出", "印象西湖秀"] }
  ],
  "core_keywords": [
    { "keyword": "杭州旅游", "description": null, "sort_order": 10, "enabled": true }
  ],
  "ai_questions": [
    {
      "prompt_code": "Q001",
      "prompt_text": "杭州宋城怎么样？",
      "prompt_type": "品牌情绪类",
      "core_keyword": "杭州旅游"
    }
  ],
  "selected_platform_codes": ["aidso_doubao_web", "aidso_doubao_app"],
  "activate_prompt_set": true
}
```

展示规则：

| 原型控件 | API 字段 | 备注 |
| --- | --- | --- |
| 品牌/产品名称 | `brand.brand_name` | 保存到目标品牌 |
| 监测品类关键字 | `core_keywords[].keyword` | 当前接口支持多核心词，原型展示单个品类关键字 |
| 品牌词标签 | `brand.brand_words[]` | 保存为品牌别名，`match_mode=contains` |
| 官网地址 | `brand.official_domain` 和项目 `official_domain` | `save_monitor_setup` 会同步项目官网 |
| 竞品标签 | `competitors[].brand_name` | 竞品别名为 `competitor_words[]` |
| 监测问题 | `ai_questions[].prompt_text` | 保存为 Prompt |
| 意图分类 | `ai_questions[].prompt_type` | 当前为字符串；需与前端枚举对齐 |
| 平台端 | `selected_platform_codes[]` | 需要平台端分组元数据辅助展示 |

缺口 API：

| 缺口 | 建议接口 | 说明 |
| --- | --- | --- |
| AI 生成品牌词 | `POST /projects/{project_id}/ai/brand-words:generate` | 入参 `brand_name/category/official_domain`，出参 `brand_words[]` |
| AI 生成竞品 | `POST /projects/{project_id}/ai/competitors:generate` | 入参 `brand_name/category/region`，出参 `{ brand_name, competitor_words, official_domain? }[]` |
| AI 生成监测问题 | `POST /projects/{project_id}/ai/questions:generate` | 入参品牌、竞品、核心词、目标数量、意图配比；出参问题列表 |
| 意图分类字典 | `GET /prompt-types` | 返回 5 类原型意图与后端 `prompt_type` 编码映射 |
| 单项局部保存 | 可选补 `PATCH /monitor-setup/brand-words` 等 | 现有统一保存适合“保存配置”，不适合每个标签即时保存 |

## 4. 创建监测项目向导

### 4.1 三步创建推荐调用链

原型三步：

1. 基础信息：项目名、品类、品牌词、平台端、官网。
2. 竞品配置。
3. 监测问题。
4. 完成摘要并进入项目。

推荐调用顺序：

1. 页面初始化：`GET /platforms?enabled=true`，可选 `GET /prompt-library?industry=文旅演艺`
2. 第一步点下一步前，前端本地校验 `project_name`、至少一个平台端。
3. 第三步点完成：
   1. `POST /projects`
   2. `PUT /projects/{project_id}/monitor-setup`
   3. 如需立即运行，额外 `POST /runs`
4. 完成页展示保存结果。

`POST /projects` 入参：

```json
{
  "project_name": "杭州宋城",
  "industry": "文旅演艺",
  "description": null,
  "timezone": "Asia/Shanghai",
  "official_domain": "https://www.hzsongcheng.com",
  "report_title": null,
  "report_subtitle": null
}
```

`POST /projects` 出参关键字段：

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `id` | integer | 后续保存监测设置的 `project_id` |
| `project_name` | string | 完成页项目名 |
| `status` | string | 项目状态 |
| `default_platform_codes` | string[] | 默认平台，创建时通常为空，需后续 `monitor-setup` 保存 |

完成摘要字段来源：

| 摘要项 | 来源 |
| --- | --- |
| 监测平台 | `PUT /monitor-setup` 返回 `selected_platform_codes`，按平台端元数据聚合 |
| 品牌词 | `brand.brand_words.length` |
| 竞品 | `competitors.length` |
| 监测问题 | `ai_questions.length` |

缺口 API：

| 缺口 | 建议接口 | 说明 |
| --- | --- | --- |
| 一步创建完整项目 | `POST /projects:setup` | 将 `POST /projects` + `PUT /monitor-setup` 包为事务，避免项目已创建但配置保存失败 |
| 创建向导草稿 | `POST/PUT /project-drafts` | 原型步骤可来回跳转；当前只能前端本地保存草稿 |
| 完成创建后自动触发 | `POST /projects:setup-and-run` 或前端调用 `POST /runs` | 原型说“配置将于下次运行开始监测”，是否立即运行需要产品确定 |

## 5. 数据大盘页

### 5.1 页面初始化和筛选

原型筛选：平台端多选、时间范围、下载报告。

推荐调用顺序：

1. `GET /projects/{project_id}/dashboard`
2. `GET /projects/{project_id}/trends?metric_code=brand_mention_rate&start_at=...&end_at=...`
3. 可选按需拉取 `brand_top1_mention_rate`、`brand_top3_mention_rate`、`citation_rate`、`recommendation_rate`
4. 信源预览、竞品预览优先从 `dashboard.platforms[].analysis.top_sources/top_competitors` 聚合；不足时提示缺口。
5. 最近问题预览需要调用答案/任务/Prompt 底层接口拼接，目前缺页面级接口。

现有 `GET /projects/{project_id}/dashboard` 出参结构：

```json
{
  "project_id": 1,
  "latest_run": {
    "run_id": 1,
    "run_no": "RUN202606240001",
    "status": "completed",
    "collection_status": "completed",
    "analysis_status": "completed",
    "platform_codes": ["aidso_doubao_web"],
    "valid_answer_count": 100,
    "data_completeness_rate": "1.0000",
    "total_tasks": 100,
    "succeeded_tasks": 100,
    "failed_tasks": 0,
    "cancelled_tasks": 0,
    "completed_at": "2026-06-24T10:00:00"
  },
  "summary": {
    "scope": "all",
    "valid_answer_count": 100,
    "brand_mention_count": 35,
    "brand_mention_rate": "0.350000",
    "brand_first_count": 18,
    "brand_first_rate": "0.180000",
    "brand_top1_mention_count": 18,
    "brand_top1_mention_rate": "0.180000",
    "brand_top3_mention_count": 42,
    "brand_top3_mention_rate": "0.420000",
    "data_completeness_rate": "1.0000",
    "metrics": []
  },
  "platforms": [
    {
      "platform_code": "aidso_doubao_web",
      "platform_name": "豆包·网页",
      "collection": {
        "total_tasks": 20,
        "succeeded_tasks": 20,
        "failed_tasks": 0,
        "cancelled_tasks": 0
      },
      "analysis": {
        "brand_mention_count": 10,
        "brand_mention_rate": "0.5000",
        "brand_top1_mention_rate": "0.2500",
        "brand_top3_mention_rate": "0.4000",
        "top_competitors": [],
        "top_sources": [],
        "summary_json": {}
      },
      "metrics": []
    }
  ]
}
```

KPI 映射：

| 原型 KPI | API 字段 | 当前状态 |
| --- | --- | --- |
| 提及率 | `summary.brand_mention_rate` | 可直接展示，前端转百分比 |
| Top1/首位提及率 | `summary.brand_top1_mention_rate` 或 `summary.brand_first_rate` | 可直接展示 |
| Top3/首屏提及率 | `summary.brand_top3_mention_rate` | 可直接展示 |
| 平均提及排名 | 无稳定汇总字段 | 缺口 |
| SOV | 无稳定汇总字段 | 缺口 |
| 对话次数 | `summary.valid_answer_count` 或 `latest_run.valid_answer_count` | 可展示为有效回答数；原型“对话次数”是否含失败任务需明确 |
| 提及对话数 | `summary.brand_mention_count` | 可直接展示 |
| 品牌提及次数 | `brand_results[].mention_count` 聚合或 `summary_json` | 缺页面级字段 |

平台表现映射：

| 原型字段 | API 字段 |
| --- | --- |
| 平台/端 | `platforms[].platform_name` 或平台端元数据 |
| 提及率 | `platforms[].analysis.brand_mention_rate` |
| 首位提及率 | `platforms[].analysis.brand_top1_mention_rate` 或 `brand_first_rate` |
| Top3 | `platforms[].analysis.brand_top3_mention_rate` |
| 对话次数 | `platforms[].analysis.valid_answer_count` 或 `collection.succeeded_tasks` |
| SOV/Top10/平均排名 | 当前缺字段 |

趋势接口：

| API | 入参 | 出参字段 | 展示 |
| --- | --- | --- | --- |
| `GET /projects/{project_id}/trends` | `metric_code` 必填，`platform_code?`、`start_at?`、`end_at?`、分页 | `items[].metric_value`、`snapshot_at`、`platform_code` | 折线图 |

常用 `metric_code` 建议：

- `brand_mention_rate`
- `brand_top1_mention_rate`
- `brand_top3_mention_rate`
- `citation_rate`
- `recommendation_rate`

报告下载调用链：

1. `POST /runs/{run_id}/reports`，Body：`{ "formats": ["pdf", "html", "md"] }`
2. 从返回 `reports[]` 选择 `format=pdf` 或需要的格式。
3. `GET /reports/{report_id}/download` 下载文件。

缺口 API：

| 缺口 | 建议接口 | 说明 |
| --- | --- | --- |
| 大盘页面级接口 | `GET /projects/{project_id}/dashboard/overview?platform_codes=&start_at=&end_at=` | 一次返回 KPI、平台表现、竞品预览、信源预览、最近问题 |
| 时间/平台筛选进入 Dashboard 聚合 | 给 `GET /dashboard` 增加 `platform_codes/start_at/end_at` | 当前 Dashboard 主要按最新 run 聚合，筛选不完整 |
| 平均提及排名 | 后端新增 `average_mention_rank` 指标快照与汇总字段 | 大盘和竞品页都需要 |
| SOV | 后端新增 `share_of_voice` 指标 | 原型明确展示 |
| Top10 提及率 | 后端新增 `brand_top10_mention_rate` | 平台卡展示 |
| 最近问题预览 | `GET /projects/{project_id}/conversation-questions/recent` | 返回问题、可见度、平均排名、更新时间 |

## 6. 竞品分析页

原型功能：

- 本品牌核心指标：提及率、提及次数、平均提及排名、首位提及率。
- 榜单 + 趋势：品牌提及率、平均提及排名、品牌提及次数。
- Top5/全部切换，本品牌高亮。

当前可用 API：

| 功能 | API | 当前可取字段 |
| --- | --- | --- |
| 本品牌提及率/首位/Top3 | `GET /projects/{project_id}/dashboard` | `summary.*` |
| 分平台竞品 Top | `GET /runs/{run_id}/analysis` | `platforms[].top_competitors` |
| 趋势 | `GET /projects/{project_id}/trends` | 单指标趋势 |
| 底层答案聚合 | `GET /runs/{run_id}/answers` + `GET /answers/{answer_id}` | 可自行计算品牌提及率/次数，但成本高 |

推荐临时调用顺序：

1. `GET /projects/{project_id}/dashboard`
2. 取 `latest_run.run_id`
3. `GET /runs/{run_id}/analysis`
4. 前端聚合 `platforms[].top_competitors`，形成 Top 榜单。
5. 对趋势图分别调用 `GET /trends?metric_code=brand_mention_rate` 等。

缺口 API：

| 缺口 | 建议接口 | 出参建议 |
| --- | --- | --- |
| 竞品页聚合接口 | `GET /projects/{project_id}/competitor-analysis` | `kpis`、`boards.rate`、`boards.rank`、`boards.count`、`trends.rate/rank/count` |
| Top10 品牌提及率榜 | 同上 | `{ brand_id, brand_name, mention_answer_count, mention_rate, is_target }[]` |
| 平均提及排名榜 | 同上 | `{ brand_id, avg_rank, mention_rate, is_target }[]` |
| 品牌提及次数榜 | 同上 | `{ brand_id, mention_count, is_target }[]` |
| 历史最高/行业平均/市场地位 | 同上或 `GET /benchmarks` | 原型 KPI 参照卡需要，现有接口没有 |
| 趋势 Top5/全部 | 同上 | 避免前端对每个品牌循环请求趋势 |

建议 `GET /projects/{project_id}/competitor-analysis` 入参：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `platform_codes` | string[] | 可多选平台端 |
| `start_at` / `end_at` | datetime | 时间范围 |
| `brand_scope` | `top5` / `all` | 趋势品牌范围 |

建议出参：

```json
{
  "target_brand": { "brand_id": 1, "brand_name": "杭州宋城" },
  "kpis": {
    "mention_rate": "0.3520",
    "mention_count": 1240,
    "average_rank": "2.4",
    "top1_rate": "0.1850"
  },
  "boards": {
    "mention_rate": [],
    "average_rank": [],
    "mention_count": []
  },
  "trends": {
    "days": ["06-17", "06-18"],
    "mention_rate": [],
    "average_rank": [],
    "mention_count": []
  }
}
```

## 7. AI 对话记录页

### 7.1 问题列表

原型展示：

- 按 AI 问题聚合，而不是按单条答案。
- 每行展示品牌可见度、提及次数、平均排名、Top1、Top3、最近更新。
- 支持平台端筛选、时间筛选、关键词搜索、分页、导出。

当前可用 API：

| API | 入参 | 出参字段 | 局限 |
| --- | --- | --- | --- |
| `GET /runs/{run_id}/answers` | `page`、`page_size` | `AnswerRead[]` | 按答案分页，不是按问题聚合；缺 prompt 文本 |
| `GET /answers/{answer_id}` | `answer_id` | `raw_text`、`citations[]`、`brand_results[]` | 可展示弹窗详情；需要先知道 answer_id |
| `GET /runs/{run_id}/query-tasks` | `status?`、`platform_code?`、分页 | `prompt_id`、`platform_code`、任务状态 | 缺 prompt 文本和指标 |
| `GET /prompt-sets/{prompt_set_id}/prompts` | `prompt_set_id` | `prompt_text`、`prompt_type` | 可补问题文本 |

临时拼装调用顺序：

1. `GET /projects/{project_id}/dashboard` 获取 `latest_run.run_id`、`prompt_set_id` 需要再从 `GET /runs/{run_id}` 获取。
2. `GET /runs/{run_id}` 获取 `prompt_set_id`、`platform_codes`。
3. `GET /prompt-sets/{prompt_set_id}/prompts?page_size=500` 获取问题文本。
4. `GET /runs/{run_id}/query-tasks?page_size=500` 获取 prompt × platform 任务。
5. `GET /runs/{run_id}/answers?page_size=100` 获取答案列表。
6. 需要引用和品牌识别时，对相关答案调用 `GET /answers/{answer_id}`。
7. 前端按 `prompt_id` 聚合成问题行。

问题行字段计算：

| 原型字段 | 计算方式 |
| --- | --- |
| AI问题 | `PromptOut.prompt_text` |
| 品牌可见度 | 同一 `prompt_id` 下 `brand_results[target].is_mentioned=true` 的答案数 / 有效答案数 |
| 提及次数 | 同一 `prompt_id` 下 `brand_results[target].mention_count` 求和 |
| 品牌排名 | 同一 `prompt_id` 下 `brand_results[target].first_position` 换算排名后取平均；当前没有直接字段 |
| TOP1/TOP3 | 同一 `prompt_id` 下目标品牌排名 <= 1 / <= 3 的比例 |
| 最近更新 | 相关答案 `collected_at` 最大值 |

缺口 API：

| 缺口 | 建议接口 | 说明 |
| --- | --- | --- |
| 对话记录问题聚合列表 | `GET /projects/{project_id}/conversation-questions` | 原型主表核心接口 |
| 行内各模型指标 | `GET /conversation-questions/{question_id}/platform-metrics` 或包含在列表中 | 返回每个平台端可见度、排名、Top1、Top3 |
| 回答弹窗聚合 | `GET /conversation-questions/{question_id}/answers` | 返回该问题下所有平台回答、引用、情感、品牌结果 |
| 搜索与筛选 | 上述接口支持 `platform_codes/start_at/end_at/keyword/page/page_size` | 避免前端全量拉取 |
| Excel 导出 | `GET /projects/{project_id}/conversation-questions/export` | 原型有“导出当前 AI 对话记录（Excel）” |
| 深度思考过程/搜索关键词 | 采集模型需存储 `reasoning_text/search_keywords` 或 `answer_metadata` | 当前 `AnswerDetailRead` 无明确字段 |

建议 `GET /projects/{project_id}/conversation-questions` 出参：

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
      "latest_collected_at": "2026-06-23T10:00:00",
      "platform_metrics": [
        {
          "platform_code": "aidso_doubao_web",
          "platform_name": "豆包·网页",
          "visibility_rate": "1.0000",
          "mention_count": 4,
          "average_rank": "2.0",
          "top1_rate": "0.5000",
          "top3_rate": "1.0000"
        }
      ]
    }
  ],
  "total": 1,
  "page": 1,
  "page_size": 10
}
```

### 7.2 回答弹窗与引用来源

当前 `GET /answers/{answer_id}` 可直接提供：

| 原型区域 | API 字段 |
| --- | --- |
| 对话原文/回答正文 | `raw_text`、`normalized_text` |
| 平台 | `platform_code`、`model_name` |
| 引用来源 | `citations[].title/url/domain/source_type/quoted_text` |
| 品牌识别 | `brand_results[].brand_id/is_mentioned/mention_count/first_position/sentiment/context_json` |
| Token/耗时 | `prompt_tokens/completion_tokens/total_tokens/latency_ms`，原型暂未展示 |

缺口字段：

| 缺口字段 | 建议 |
| --- | --- |
| AI 问题文本 | `AnswerDetailRead` 增加 `prompt_text/prompt_type`，或弹窗聚合接口返回 |
| 平台展示名/端类型/logo | 使用平台端元数据接口 |
| 深度思考过程 | `AnswerDetailRead` 增加 `reasoning_text` 或 `metadata.reasoning_text` |
| 搜索关键词 | `AnswerDetailRead` 增加 `search_keywords[]` |
| 提及品牌列表 | 当前可用 `brand_results` + 品牌接口补名称；建议详情直接带 `brand_name` |

## 8. 信源引用分析页

原型功能：

- KPI：引用文章数、引用次数、引用网站。
- 信源类型分布：占比/趋势。
- 信源站点影响力 TOP10：类型筛选、站点搜索、指标口径切换、平台端矩阵。
- 指标口径：引用次数、链接数、引用率。

当前可用数据来源：

| 数据 | API/字段 |
| --- | --- |
| 单答案引用 | `GET /answers/{answer_id}` -> `citations[]` |
| 平台分析 Top Sources | `GET /runs/{run_id}/analysis` -> `platforms[].top_sources` |
| Dashboard 平台分析 | `GET /projects/{project_id}/dashboard` -> `platforms[].analysis.top_sources` |
| 引用率趋势 | `GET /projects/{project_id}/trends?metric_code=citation_rate` |

当前局限：

- 没有按项目/时间/平台聚合的引用站点接口。
- `citations.source_type` 有字段，但没有信源类型分布聚合接口。
- 没有站点 × 平台端矩阵。
- 没有链接数去重口径接口。
- Deepseek“未返回引用不计入分母”这种口径尚未通过 API 明确表达。

缺口 API：

| 缺口 | 建议接口 | 说明 |
| --- | --- | --- |
| 信源分析总览 | `GET /projects/{project_id}/source-analysis` | 页面级接口，返回 KPI、类型分布、站点矩阵 |
| 信源类型趋势 | `GET /projects/{project_id}/source-analysis/type-trends` | 返回各类型随时间占比 |
| 信源站点影响力 | `GET /projects/{project_id}/source-analysis/sites` | 支持类型、关键词、指标、平台、时间、分页 |
| 信源导出 | `GET /projects/{project_id}/source-analysis/export` | 如后续需要 |
| 来源类型字典 | `GET /source-types` | 固化“官网/独立站/行业垂直”等分类 |

建议 `GET /projects/{project_id}/source-analysis` 入参：

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `platform_codes` | string[] | 平台端多选 |
| `start_at` / `end_at` | datetime | 时间范围 |
| `source_type` | string | 信源类型，默认全部 |
| `keyword` | string | 站点搜索 |
| `metric` | `cites` / `links` / `rate` | 指标口径 |
| `page` / `page_size` | integer | TOP10 或分页 |

建议出参：

```json
{
  "kpis": {
    "article_count": 156,
    "citation_count": 623,
    "site_count": 87
  },
  "type_distribution": [
    { "source_type": "官网/独立站/行业垂直", "citation_count": 293, "rate": "0.4700" }
  ],
  "type_trends": [
    { "date": "2026-06-22", "source_type": "官网/独立站/行业垂直", "rate": "0.4700" }
  ],
  "sites": {
    "items": [
      {
        "rank": 1,
        "site": "携程旅行",
        "source_type": "电商平台",
        "total_citation_count": 54,
        "total_link_count": 38,
        "citation_rate": "0.0867",
        "platform_values": [
          { "platform_code": "aidso_doubao_web", "citation_count": 16, "link_count": 11, "citation_rate": "0.1200", "has_citation_data": true }
        ]
      }
    ],
    "total": 10
  }
}
```

## 9. 监测运行、采集、分析与报告流程

虽然这些流程不是 6 个原型页的首屏重点，但它们支撑“监测中”“数据大盘”“下载报告”等功能。

### 9.1 手动发起监测

调用顺序：

1. 确保项目配置完成：`GET /projects/{project_id}/monitor-setup`
2. 确保有激活问题集：`active_prompt_set_id != null`；否则保存配置时传 `activate_prompt_set=true`
3. `POST /runs`
4. 轮询 `GET /runs/{run_id}`
5. 采集完成后 `POST /runs/{run_id}/analyze`
6. 轮询/查询 `GET /runs/{run_id}/analysis`
7. 生成报告：`POST /runs/{run_id}/reports`

`POST /runs` 入参：

```json
{
  "project_id": 1,
  "prompt_set_id": null,
  "platform_codes": ["aidso_doubao_web", "aidso_doubao_app"],
  "collection_source": "aidso",
  "aidso_thinking_enabled_by_platform": {
    "aidso_doubao_web": true,
    "aidso_doubao_app": true
  }
}
```

`GET /runs/{run_id}` 展示字段：

| 字段 | 用途 |
| --- | --- |
| `status` | 运行总状态 |
| `collection_status` / `analysis_status` / `report_status` | 分阶段状态 |
| `progress_rate` | 进度条 |
| `total_tasks/succeeded_tasks/failed_tasks/cancelled_tasks` | 任务统计 |
| `valid_answer_count` / `data_completeness_rate` | 数据质量 |
| `error_summary/error_message` | 失败提示 |

运行操作：

| 功能 | API |
| --- | --- |
| 取消运行 | `POST /runs/{run_id}/cancel` |
| 重试失败任务 | `POST /runs/{run_id}/retry-failed` |
| 查看任务 | `GET /runs/{run_id}/query-tasks` 或 `/tasks` |
| 重跑分析 | `POST /runs/{run_id}/analyze` |

### 9.2 定时调度

现有接口可支撑后续“定时监测”配置页：

| 功能 | API |
| --- | --- |
| 查询项目调度 | `GET /projects/{project_id}/schedules` |
| 创建调度 | `POST /projects/{project_id}/schedules` |
| 更新调度 | `PUT /schedules/{schedule_id}` |
| 删除调度 | `DELETE /schedules/{schedule_id}` |
| 启用/停用 | `POST /schedules/{schedule_id}/enable`、`/disable` |
| 立即触发 | `POST /schedules/{schedule_id}/trigger` |

## 10. 缺口 API 汇总与优先级建议

### P0：原型核心页面闭环必须补

| 缺口 | 建议接口 | 影响页面 |
| --- | --- | --- |
| 项目卡聚合列表 | `GET /projects/overview` | 项目管理 |
| 平台端元数据 | `GET /platform-endpoints` 或扩展 `AIPlatformOut` | 全部页面 |
| 创建向导 AI 生成 | `/ai/brand-words:generate`、`/ai/competitors:generate`、`/ai/questions:generate` | 创建项目、编辑配置 |
| 大盘页面级聚合 | `GET /projects/{project_id}/dashboard/overview` | 数据大盘 |
| 对话记录问题聚合 | `GET /projects/{project_id}/conversation-questions` | AI 对话记录 |
| 回答弹窗聚合 | `GET /conversation-questions/{prompt_id}/answers` | AI 对话记录 |
| 信源页面级聚合 | `GET /projects/{project_id}/source-analysis` | 信源引用分析 |
| 竞品页面级聚合 | `GET /projects/{project_id}/competitor-analysis` | 竞品分析 |

### P1：提升体验与口径一致性

| 缺口 | 建议接口/字段 | 影响 |
| --- | --- | --- |
| 平均提及排名指标 | `average_mention_rank` 指标快照与汇总 | 大盘、竞品、对话记录 |
| SOV 指标 | `share_of_voice` 指标快照与汇总 | 大盘 |
| Top10 提及率 | `brand_top10_mention_rate` | 大盘平台表现 |
| 品牌提及次数汇总 | `brand_mention_total_count` | 大盘、竞品 |
| 情感倾向聚合 | `positive_rate/neutral_rate/negative_rate` | 对话记录 |
| 信源类型字典 | `GET /source-types` | 信源引用分析 |
| Prompt 类型字典 | `GET /prompt-types` | 创建项目、编辑配置 |
| Excel 导出 | `conversation-questions/export`、`source-analysis/export` | 对话记录、信源页 |

### P2：后续系统化能力

| 缺口 | 建议 | 说明 |
| --- | --- | --- |
| 一步创建完整项目 | `POST /projects:setup` | 保证项目和配置事务一致 |
| 创建向导草稿 | `POST/PUT /project-drafts` | 支持离开后恢复 |
| 项目暂停/恢复监测 | `POST /projects/{id}/pause/resume` | 与项目禁用区分 |
| 当前项目偏好 | `GET/PUT /users/me/preferences/current-project` | 支持统一项目切换器 |
| 删除影响检查 | `GET /projects/{id}/delete-check` | 提升删除确认体验 |
| 报告“生成并下载”快捷接口 | `POST /runs/{run_id}/reports:download` | 减少前端两步调用 |

## 11. 前端展示格式约定建议

### 11.1 比率字段

后端当前多数比率返回 decimal 字符串，如 `"0.3520"`。前端展示：

- 百分比：`Number(value) * 100`，保留 1 位或 2 位。
- 空值：`null` 或无分母时展示 `—`。

### 11.2 时间字段

后端时间为 ISO8601 字符串。原型展示：

- 列表更新时间：`MM-DD HH:mm`
- 趋势横轴：`MM-DD`
- 详情时间：`YYYY-MM-DD HH:mm:ss`

### 11.3 平台端字段

建议统一使用：

```json
{
  "platform_code": "aidso_doubao_web",
  "base_platform": "豆包",
  "endpoint_type": "web",
  "endpoint_label": "网页",
  "display_name": "豆包·网页",
  "logo_url": "/assets/platforms/doubao.jpeg",
  "thinking_mode": "专家"
}
```

### 11.4 原型意图分类与后端 `prompt_type`

原型 5 类：

- `品牌情绪类`
- `品牌信息类`
- `品类情绪类`
- `竞品对比类`
- `品类推荐类`

建议后端字典返回同时包含中文显示名与稳定编码，例如：

```json
{
  "code": "brand_sentiment",
  "label": "品牌情绪类",
  "description": "评价、口碑、是否值得等品牌判断问题"
}
```

## 12. 页面到接口速查

| 页面 | 初始化接口 | 主数据接口 | 操作接口 | 明确缺口 |
| --- | --- | --- | --- | --- |
| 项目管理 | `GET /projects` | `GET /monitor-setup`、`GET /dashboard` | `POST /projects`、`PUT /monitor-setup`、`DELETE /projects/{id}` | `GET /projects/overview`、暂停/恢复 |
| 创建项目 | `GET /platforms`、`GET /prompt-library` | 前端草稿 | `POST /projects`、`PUT /monitor-setup` | AI 生成、一步创建 |
| 数据大盘 | `GET /dashboard` | `GET /trends`、`GET /analysis` | `POST /reports`、`GET /reports/{id}/download` | 页面级 overview、SOV、平均排名 |
| 竞品分析 | `GET /dashboard` | `GET /analysis`、`GET /trends` | 无 | `GET /competitor-analysis` |
| AI 对话记录 | `GET /dashboard`、`GET /runs/{id}` | `GET /answers`、`GET /answers/{id}`、`GET /prompts` | 导出缺失 | `GET /conversation-questions`、弹窗聚合、导出 |
| 信源引用分析 | `GET /dashboard` | `GET /analysis`、`GET /answers/{id}` | 无 | `GET /source-analysis`、类型趋势、站点矩阵 |
