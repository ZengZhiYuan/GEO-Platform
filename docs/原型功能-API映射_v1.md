# 监测原型 v1 ×（项目A）GEO-Platform 后端 API 功能映射文档

> 目的：把 `监测原型v1/` 下 6 张原型图所包含的**系统功能**，与开源项目 A
> [`ZengZhiYuan/GEO-Platform`](https://github.com/ZengZhiYuan/GEO-Platform) 后端已实现的 **API 接口**逐一对应，
> 说明每个功能需要调哪些接口、调用顺序、数据如何展示、出入参字段与格式，并**标注后端缺失的能力**，
> 便于后续系统功能迭代与查漏补缺。
>
> - 项目 A 性质：**后端优先**的 AI 应用监测系统（FastAPI + PostgreSQL + Redis/Dramatiq + APScheduler + LangGraph Agent）。
> - 后端当前 Alembic head：`geo_monitoring_0007`；`frontend/` 仅保留管理端壳层，UI 与原型不对应（原型为另一套设计）。
> - 接口统一前缀：`/api/geo-monitoring`（兼容保留 `/api/v1/geo-monitoring`）。
> - 本文一切「字段名」均取自后端 `schemas.py` / 服务层真实返回，可直接对接。

---

## 0. 阅读前必读：全局口径与三处根本性差异

后端是**「运行（run）为中心」**的批处理模型，原型是**「项目 + 时间范围」为中心**的看板模型。映射时必须先理解以下落差，否则逐功能映射会误读：

| 维度 | 原型（v1） | 项目 A 后端 | 影响 / 处理 |
| --- | --- | --- | --- |
| **统一响应** | — | `{ "code": 0, "message": "success", "data": {...} }`；分页 `data = { items, total, page, page_size }` | 前端统一拆 `data` |
| **平台·端（12 键）** | 平台 × 端（网页/手机）共 12 个「平台·端」键，全页多选筛选 | **只有 `platform_code` 单一维度**，无「端」概念；端只能通过 `collection_source=aidso` + `aidso_thinking_enabled_by_platform` 间接体现 | ⚠️**重大缺口**：原型的「端侧」筛选无后端模型，详见 §8-缺口① |
| **时间范围** | 近 7 天 / 近 30 天 / 自定义 daterange，几乎每页都有 | 看板 `dashboard` 只接受 `run_id`（取最近一次已分析运行）；跨时间聚合只能用 `trends`（按单 `metric_code` 拉快照序列） | ⚠️看板类页面无「时间范围聚合」接口，只能逐指标拼趋势，详见 §8-缺口② |
| **指标主体** | 项目级最新快照 + 趋势 | 每个 run × platform 一行 `geo_platform_analysis`；趋势走 `geo_metric_snapshot`（只含**目标品牌** + platform + prompt 维度，**无竞品/无信源域名维度**） | ⚠️竞品趋势、信源趋势在后端**不存在**，详见 §8-缺口③④ |
| **AI 智能生成** | 品牌词 / 竞品 / 监测问题均有「AI 生成」按钮（原型为 `setTimeout` mock） | **无任何内容生成接口**；只有 `GET /prompt-library`（静态模板词库） | ⚠️最高优先级缺口，详见 §8-缺口⑤ |
| **黑盒指标** | 已主动删除：品牌得分、提及好感度、AI 认知指数、内容就绪度(EEAT) | 部分存在：`brand_score`、`positive_neutral_sentiment_percent` 在 `brand_metrics` 内 | 原型已剔除，后端有也可不展示 |

> 下文每页「缺口」列用 ⚠️ 标注。文末 §8 汇总所有缺失 API 并给优先级。

---

## 1. 后端 API 全量清单（59 个端点，按域分组）

> 全部已实现并挂载在 `/api/geo-monitoring` 下。出入参 Schema 见各页映射与 §7 字段速查。

### 1.1 项目配置域（对应原型 1、2 页）
| 方法 | 路径 | 说明 | 入参 Schema | 出参 |
| --- | --- | --- | --- | --- |
| GET | `/projects` | 分页查询项目 | `page,page_size` | `Paginated[ProjectOut]` |
| POST | `/projects` | 创建项目 | `ProjectCreate` | `ProjectOut` |
| GET | `/projects/{id}` | 项目详情 | — | `ProjectOut` |
| PUT | `/projects/{id}` | 更新项目（含暂停/归档=改 `status`） | `ProjectUpdate` | `ProjectOut` |
| DELETE | `/projects/{id}` | 删除项目 | — | — |
| **GET** | **`/projects/{id}/monitor-setup`** | **一站式取「品牌/竞品/核心词/问题/平台」配置** | — | 见 §1.6 |
| **PUT** | **`/projects/{id}/monitor-setup`** | **一站式保存全部配置（创建向导/编辑配置主接口）** | `MonitorSetupSave` | 同上 |
| GET/POST | `/projects/{id}/brands` | 品牌（含竞品）列表/新增 | `BrandCreate` | `BrandOut` |
| GET/PUT/DELETE | `/brands/{id}` | 品牌详情/改/删 | `BrandUpdate` | `BrandOut` |
| GET/POST | `/brands/{id}/aliases` | 品牌别名（=品牌词/竞品别名）列表/新增 | `BrandAliasCreate` | `BrandAliasOut` |
| PUT/DELETE | `/brand-aliases/{id}` | 别名改/删 | `BrandAliasUpdate` | — |
| GET/POST | `/projects/{id}/core-keywords` | 核心词列表/新增 | `CoreKeywordCreate` | `CoreKeywordOut` |
| PUT/DELETE | `/core-keywords/{id}` | 核心词改/删 | `CoreKeywordUpdate` | — |
| GET/POST | `/projects/{id}/prompt-sets` | 提示词集（=监测问题集，含版本） | `PromptSetCreate` | `PromptSetOut` |
| GET/PUT/DELETE | `/prompt-sets/{id}` | 提示词集详情/改/删 | `PromptSetUpdate` | `PromptSetOut` |
| POST | `/prompt-sets/{id}/activate` | 激活提示词集版本 | — | `PromptSetOut` |
| GET/POST | `/prompt-sets/{id}/prompts` | 提示词（=单条监测问题）列表/新增 | `PromptCreate` | `PromptOut` |
| PUT/DELETE | `/prompts/{id}` | 提示词改/删 | `PromptUpdate` | `PromptOut` |
| GET | `/prompt-library` | 全局 Prompt 词库（问题模板） | `page,page_size` | `Paginated[PromptLibraryOut]` |
| GET | `/platforms` | AI 平台列表（豆包/千问/元宝/DeepSeek/Kimi…） | `page,page_size` | `Paginated[AIPlatformOut]` |
| GET/PUT | `/platforms/{code}` | 平台配置详情/改 | `AIPlatformUpdate` | `AIPlatformOut` |

### 1.2 运行与采集域（驱动所有数据页的数据来源）
| 方法 | 路径 | 说明 | 入参 | 出参 |
| --- | --- | --- | --- | --- |
| GET | `/runs` | 分页查询运行（`project_id,status,created_after,created_before`） | query | `Paginated[MonitorRunOut]` |
| POST | `/runs` | 创建运行（自动扇出采集任务） | `RunCreate` | `MonitorRunOut` |
| GET | `/runs/{id}` | 运行详情（含进度 `progress_rate`） | — | `RunDetailRead` |
| POST | `/runs/{id}/cancel` | 取消运行 | — | — |
| POST | `/runs/{id}/retry-failed` | 重试失败任务 | — | — |
| GET | `/runs/{id}/query-tasks`（别名 `/tasks`） | 子任务列表（`status,platform_code`） | query | `Paginated[QueryTaskOut]` |
| GET | `/runs/{id}/answers` | 运行下答案分页 | `page,page_size` | `Paginated[AnswerRead]` |
| GET | `/answers/{id}` | 答案详情（含引用、品牌命中） | — | `AnswerDetailRead` |

### 1.3 分析与看板域（驱动大盘/竞品/信源页）
| 方法 | 路径 | 说明 | 出参关键字段 |
| --- | --- | --- | --- |
| POST | `/runs/{id}/analyze` | 手工触发/重跑分析 | `analysis_status` |
| GET | `/runs/{id}/analysis` | 运行各平台指标 + Agent 洞察 | `platforms[].{brand_mention_rate, brand_top1/top3, top_competitors, top_sources, prompt_competitiveness_summary, summary_json}` |
| GET | `/runs/{id}/agent-executions` | Agent 执行审计分页 | 审计记录 |
| **GET** | **`/projects/{id}/dashboard`** | **项目最新分析汇总（大盘主接口）** | `summary` + `platforms[]`，见 §3 |
| **GET** | **`/projects/{id}/trends`** | **按 `metric_code` 拉趋势快照序列（折线图主接口）** | 快照数组，见 §3 |

### 1.4 调度域（原型 v1 未直接出现，预留）
`GET/POST /projects/{id}/schedules`、`GET/PUT/DELETE /schedules/{id}`、`POST /schedules/{id}/{enable|disable|trigger}` — `ScheduleCreate(name, cron_expr, timezone, enabled, misfire_policy)`。
> 原型 v1 六页**未涉及定时调度 UI**，但项目卡「监测中」状态、定时刷新的数据来源依赖它。

### 1.5 报告域（对应大盘「下载报告」、对话/信源「导出」）
| 方法 | 路径 | 说明 |
| --- | --- | --- |
| POST | `/runs/{id}/reports` | 创建并生成报告，body `{ "formats": ["md","html","pdf"] }` |
| GET | `/runs/{id}/reports` | 报告列表 |
| GET | `/reports/{id}` | 报告状态/元数据（`status: pending\|generating\|completed\|failed`） |
| GET | `/reports/{id}/download` | 下载文件（md/html/pdf） |
| DELETE | `/reports/{id}` | 删除报告 |

### 1.6 `monitor-setup` 出入参（创建/编辑配置的核心接口，单列说明）
**GET 返回 `data`：**
```jsonc
{
  "brand": { "brand_name": "...", "official_domain": "...", "description": "...",
             "brand_words": ["宋城千古情", ...] },          // 目标品牌 + 品牌词(=别名)
  "competitors": [ { "brand_name": "印象西湖", "competitor_words": ["..."] } ],
  "core_keywords": [ { "id":1, "keyword":"杭州旅游", "description":null,
                       "sort_order":0, "enabled":true } ],
  "ai_questions": [ /* 由激活/草稿 PromptSet 的 prompts 序列化 */ ],
  "available_platforms": [ { "platform_code":"doubao", "platform_name":"豆包",
                             "enabled":true } ],
  "selected_platform_codes": ["doubao","qwen", ...],          // = project.default_platform_codes
  "draft_prompt_set_id": 12, "active_prompt_set_id": 11
}
```
**PUT body `MonitorSetupSave`：**
```jsonc
{
  "brand": { "brand_name":"杭州宋城", "official_domain":null, "description":null,
             "brand_words":["宋城千古情","宋城演艺",...] },
  "competitors": [ { "brand_name":"印象西湖", "competitor_words":["最忆是杭州"] } ],
  "core_keywords": [ { "keyword":"杭州旅游", "description":null, "sort_order":0, "enabled":true } ],
  "ai_questions": [ { "core_keyword":"杭州旅游", "prompt_text":"杭州有哪些必去的演艺秀？",
                      "prompt_type":"category_recommend", "prompt_code":null,
                      "library_prompt_code":null } ],
  "selected_platform_codes": ["doubao","qwen","yuanbao","deepseek","kimi"],
  "activate_prompt_set": true                                  // true=保存即激活该问题集版本
}
```
> 这一个 PUT 接口**同时落库**品牌、别名、竞品、核心词、PromptSet+Prompts、项目默认平台。原型 1/2 页几乎所有配置写操作都收敛到它。

---

## 2. 原型页 1 — 项目管理（`1项目管理v1.html`）

**页面定位**：账户级项目列表，查看/管理所有监测项目，并从卡片进入「编辑配置」（基础·品牌词·平台 / 竞品 / 监测问题 三 Tab）。

| # | 系统功能 | 触发 | 调用 API（顺序） | 入参 | 出参 → 前端字段 | 展示 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | 项目切换器 / 项目列表 | 加载 | `GET /projects` | `page,page_size` | `items[].{id, project_name, status, default_platform_codes[], industry, updated_at}` | 项目卡 | ✅ |
| 2 | 卡片「品牌词 / 竞品 / 监测平台」摘要 | 加载（每卡） | `GET /projects/{id}/monitor-setup` | — | `brand.brand_words[]`(品牌词)、`competitors[].brand_name`(竞品)、`selected_platform_codes[]`(监测平台) | 卡内 chip / logo | ⚠️ 端数无字段（§8①） |
| 3 | 卡片底部统计：问题数 / 平台数 / 更新时间 | 加载 | 复用 monitor-setup + `GET /prompt-sets/{active_id}` | — | 问题数=`PromptSetOut.prompt_count`；平台数=`selected_platform_codes.length`；更新时间=`project.updated_at`（或最近 run `completed_at`） | 数字 | ⚠️「端数」无来源 |
| 4 | 创建项目（入口） | 点击 | → 跳原型 2 页向导 | — | — | 按钮 | ✅ |
| 5 | 暂停 / 恢复监测 | 点击 | `PUT /projects/{id}` | `{ "status":"disabled" }` / `"active"` | `ProjectOut.status` | 按钮 | ✅ |
| 6 | 删除项目 | 点击 | `DELETE /projects/{id}` | — | — | 按钮 | ✅ |
| 7 | 编辑配置·Tab1（品牌/产品名 + 品牌词 + 监测平台 + 官网） | 切 Tab | `GET /projects/{id}/monitor-setup`；保存 `PUT …/monitor-setup` | `MonitorSetupSave.{brand, selected_platform_codes}` | 见 §1.6 | 表单 + 平台卡 | ⚠️ 平台「端/模式」无字段 |
| 8 | 编辑配置·Tab2（竞品 + 别名） | 切 Tab | 同上 PUT | `MonitorSetupSave.competitors[]` | `competitors[]` | chip 区 | ✅ |
| 9 | 编辑配置·Tab3（监测问题 20 条 + 意图分类） | 切 Tab | 同上 PUT；或细粒度 `…/prompts` CRUD | `ai_questions[].{prompt_text, prompt_type, core_keyword}` | `ai_questions[]` | 列表 + 分布条 | ⚠️「意图 5 类」分类口径见下 |
| 10 | 品牌词 chip 增删（手动） | 编辑 | 走 monitor-setup 整存，或 `POST/DELETE /brands/{id}/aliases` | `BrandAliasCreate.alias_name` | `BrandAliasOut` | chip | ✅ |
| 11 | **AI 生成品牌词 / AI 生成竞品 / AI 重新生成问题** | 点击 | **无接口** | — | — | 按钮 | ⚠️**缺失（§8⑤）** |
| 12 | 意图分布统计（品牌情绪/品牌信息/品类情绪/竞品对比/品类推荐 5 类） | computed | 前端按 `prompt_type` 聚合 | — | `PromptOut.prompt_type`（后端推断 `infer_prompt_type`） | 彩色图例 | ⚠️ 后端 `prompt_type` 取值未必=原型 5 类（口径需对齐，§8⑥） |

**调用顺序（编辑配置保存）**：`GET …/monitor-setup`（回填）→ 用户改 → `PUT …/monitor-setup`（整存，`activate_prompt_set` 决定是否激活问题集）。

---

## 3. 原型页 2 — 创建监测项目向导（`2创建监测项目v1.html`）

**页面定位**：三步向导（基础信息 → 竞品配置 → 监测问题），每步「AI 推荐 + 人工增删改」，完成出摘要态。

| # | 系统功能 | 触发 | 调用 API（顺序） | 入参 | 出参 → 前端 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | 进入向导先建项目 | 步骤1完成 | `POST /projects` | `ProjectCreate{ project_name, industry="文旅演艺", official_domain?, description? }` | `ProjectOut.id`（后续步骤都用它） | ✅ |
| 2 | 平台候选列表（步骤1平台多选） | 步骤1加载 | `GET /platforms` | — | `items[].{platform_code, platform_name, enabled, search_enabled, citation_supported}` | ⚠️ 端/模式无字段 |
| 3 | 步骤3 问题模板候选（AI 生成的底料） | 步骤3加载 | `GET /prompt-library` | `page,page_size` | `items[].{prompt_code, prompt_text, prompt_type, scene_tag, default_core_keyword}` | ✅（仅静态模板，非真正生成） |
| 4 | **一次性保存全部配置（品牌词/竞品/核心词/问题/平台）** | 完成创建 | `PUT /projects/{id}/monitor-setup` | `MonitorSetupSave`（全字段，`activate_prompt_set:true`） | 回写 setup | ✅ 核心接口 |
| 5 | 完成摘要态 4 数字砖（平台数/品牌词数/竞品数/问题数） | 完成后 | 复用 PUT 返回 或 `GET …/monitor-setup` | `selected_platform_codes.length` / `brand.brand_words.length` / `competitors.length` / `ai_questions.length` | ✅ |
| 6 | **AI 生成品牌词 / 竞品 / 20 条问题** | 点击 | **无接口**（原型 `setTimeout` mock） | — | — | ⚠️**缺失（§8⑤）** |
| 7 | 意图自动猜测（`qGuess` 正则） | 批量添加 | 前端本地；后端有 `infer_prompt_type` 但未单独暴露 | — | — | ⚠️ 可选：暴露推断接口 |

**典型时序**：`POST /projects` → `GET /platforms`（+`GET /prompt-library`）→ 用户配置/（缺）AI 生成 → `PUT /projects/{id}/monitor-setup` → （进入项目）`POST /runs` 启动首次采集。

> 💡向导完成后若要立刻「开始监测」，需追加 `POST /runs { project_id, prompt_set_id:active, platform_codes:selected }`，原型未画但闭环必需。

---

## 4. 原型页 3 — 数据大盘（`3数据大盘v1.html`）

**页面定位**：单项目 GEO 总览，8 KPI + 各平台×端表现 + 竞品对比概览 + 信源/对话预览。
**主数据源**：`GET /projects/{id}/dashboard`（取最近一次已分析 run）+ `GET /projects/{id}/trends`。

### 4.1 KPI 8 卡映射
`dashboard.summary` 字段：`{ valid_answer_count, brand_mention_count, brand_mention_rate, brand_first_count, brand_first_rate, brand_top1_mention_count, brand_top1_mention_rate, brand_top3_mention_count, brand_top3_mention_rate, data_completeness_rate, metrics[] }`

| 原型 KPI | 后端字段 | 状态 |
| --- | --- | --- |
| 提及率 35.2% | `summary.brand_mention_rate` | ✅ |
| Top1(首位)提及率 18.5% | `summary.brand_top1_mention_rate`（或 `brand_first_rate`） | ✅ |
| Top3(首屏)提及率 42.0% | `summary.brand_top3_mention_rate` | ✅ |
| 品牌提及次数 1,240 | `summary.brand_mention_count` | ✅ |
| 提及对话数 640 | `summary.brand_mention_count`（按「回答去重数」口径，对话=回答） | ✅ 口径需确认 |
| 对话次数 1,820 | `summary.valid_answer_count`（有效回答数） | ⚠️「对话次数」含无效回答时口径不同 |
| 平均提及排名 2.4 | ⚠️ summary **无此字段**；仅 `summary_json.metrics.brand_metrics[].average_mention_rank`（按品牌） | ⚠️ 需取目标品牌行（§8③） |
| SOV 27.8% | ⚠️ summary **无此字段**；仅 `brand_metrics[].share_of_voice`（按品牌） | ⚠️ 需取目标品牌行 |
| 环比涨跌（▲3.1pt） | ⚠️ 无；需用 `trends` 自行算前后两快照差 | ⚠️ 前端计算 |

### 4.2 平台表现卡（各平台）
`dashboard.platforms[]`：`{ platform_code, platform_name, collection{total_tasks,succeeded_tasks,failed_tasks,cancelled_tasks}, analysis{...}, metrics[] }`
`analysis` 内：`brand_mention_rate`(提及率)、`brand_top1_mention_rate`(首位)、`brand_top3_mention_rate`(top3)、`top_competitors`、`top_sources`、`summary_json.metrics`（含 `brand_visibility, citation_rate, source_coverage, competitor_advantage_gap` 等）。
- ✅ 提及率/首位/top3/有效回答数
- ⚠️ 「平均提及排名 rank / SOV / top10」按**平台**拆分时，需读 `summary_json.metrics.brand_metrics`（目标品牌行）；`top10` 后端无对应字段。
- ⚠️ 平台「端」拆分无字段（§8①）。

### 4.3 竞品核心指标对比榜（金银铜）
数据源：`dashboard.platforms[].analysis.summary_json.metrics.brand_metrics[]`（**含目标品牌+所有竞品**）。
每行 `BrandMetricsRow`：`{ brand_name, mention_rate_percent(提及率), average_mention_rank(平均排名), mention_count, share_of_voice, positive_neutral_sentiment_percent, brand_score }`。
- ✅ name / 提及率 / 平均排名 / 首位（首位需取 `top_competitors` 或 brand 级 first，见下）。
- ⚠️ brand_metrics 在**每个平台**的 summary_json 内；要「全平台合并榜」需前端跨平台聚合（后端 `summary` 顶层不含竞品级聚合，§8③）。
- ⚠️ 也可用 `analysis.top_competitors`（`CompetitorRow{brand_name, mention_answer_count, visibility_rate}`）做简版榜，但无平均排名/SOV。

### 4.4 品牌提及率趋势折线（5 品牌 × 7 天）
数据源：`GET /projects/{id}/trends?metric_code=brand_mention_rate&platform_code=&start_at=&end_at=`
返回每条：`{ run_id, platform_code, metric_code, numerator, denominator, metric_value, prompt_set_version, snapshot_at, completeness_rate }`。
- ✅ **目标品牌**的提及率趋势（按 snapshot_at 排序连点成线）。
- ⚠️**致命缺口**：`metric_snapshot` **无 brand_id 维度** → 印象西湖/横店等**竞品的趋势线后端取不到**（§8③）。原型 5 品牌折线只有 1 条能落地。

### 4.5 信源 TOP 预览 / 对话记录预览 / 下载报告
| 功能 | API | 出参 → 前端 | 缺口 |
| --- | --- | --- | --- |
| TOP 信源预览（nm/type/占比） | `dashboard.platforms[].analysis.top_sources`（`SourceStatRow{domain, citation_count, share_rate, rank_no}`，含 `source_type`） | 占比=`share_rate`，类型=`source_type` | ⚠️ 站点中文名(nm)、8 类映射，§8④ |
| 最近提问预览（q/可见度/排名/date） | `GET /runs/{id}/answers?page=1&page_size=5` + `GET /answers/{id}` | q=prompt 文本、date=`collected_at` | ⚠️ 可见度/排名需 join `brand_results`/`prompt_competitiveness` |
| 下载报告（PDF/Excel） | `POST /runs/{id}/reports {formats:["pdf"]}` → 轮询 `GET /reports/{id}` → `GET /reports/{id}/download` | `status`、文件流 | ⚠️ 仅 md/html/pdf，**无 Excel**（§8⑦） |
| 平台×端多选 / 时间范围筛选 | dashboard 无该参数；trends 有 `start_at/end_at` | — | ⚠️ §8①②（看板无 daterange 聚合） |

---

## 5. 原型页 4 — 竞品分析（`4竞品分析v2.html`）

**页面定位**：品牌 vs 竞品横向对比，每个指标一行（左榜单 + 右趋势）+ 本品牌参照卡。
**主数据源**：同大盘 —— `dashboard.platforms[].analysis.summary_json.metrics.brand_metrics[]`（榜单）+ `trends`（趋势）。

| # | 系统功能 | API | 出参 → 前端字段 | 缺口 |
| --- | --- | --- | --- | --- |
| 1 | 本品牌核心指标参照卡 ×4（提及率/提及次数/平均排名/首位率，+历史最高+行业平均+市场地位） | `dashboard.summary` + `brand_metrics`(目标品牌行) | 当前值=summary/brand_metrics；历史最高=`trends` 取序列 max | ⚠️「行业平均」无任何来源（§8⑧）；「全品牌第N」需前端排序 brand_metrics |
| 2 | 品牌提及率榜 Top10（金银铜） | `brand_metrics[].mention_rate_percent` | name + 提及率，按值排序、me 高亮 | ⚠️ 跨平台合并需前端聚合（§8③） |
| 3 | 提及率趋势（9 品牌 × 7 天，Top5/全部切换） | `trends?metric_code=brand_mention_rate` | 仅**目标品牌**可连线 | ⚠️**竞品趋势缺失**（§8③）—— 9 条线只有 1 条 |
| 4 | 平均提及排名榜 Top10 | `brand_metrics[].average_mention_rank` | name + 提及率 + 平均排名 | ⚠️ 同 §8③ |
| 5 | 平均提及排名趋势（Y 轴反转） | `trends?metric_code=`（**无 avg_rank 快照**） | — | ⚠️ §10.6 趋势清单**不含平均排名** → 趋势取不到（§8③） |
| 6 | 品牌提及次数榜 Top10（蓝条） | `brand_metrics[].mention_count` | name + 提及次数 | ⚠️ 同 §8③ |
| 7 | 提及次数趋势 | `trends?metric_code=brand_mention_count` | 仅目标品牌 | ⚠️ 竞品缺失 |
| 8 | 平台×端多选 / 时间范围 | dashboard 取 run_id；trends 取 daterange | — | ⚠️ §8①② |

> **结论**：竞品页「当前快照榜单」可由 `brand_metrics` 落地（含目标品牌+竞品）；但**所有竞品维度的「趋势折线」均缺后端支撑**，平均排名连快照都没存。这是竞品页最大改造点。

---

## 6. 原型页 5 — AI 对话记录（`5对话记录v0.html`）

**页面定位**：以「AI 问题」为行的对话明细表，可就地展开各平台×端指标，或弹窗看对话原文 + 引用来源。
**主数据源**：`GET /runs/{id}/answers`（列表）+ `GET /answers/{id}`（详情：raw_text、citations[]、brand_results[]）。

| # | 系统功能 | 触发 | API（顺序） | 出参 → 前端字段 | 缺口 |
| --- | --- | --- | --- | --- | --- |
| 1 | 极值卡 ×6（可见度/提及次数/排名/TOP3/正向最高/正向最低 + 对应问题） | 加载 | 前端基于 `answers + brand_results` 计算 | `brand_results.{mention_count, first_position, sentiment}` | ⚠️ 无现成极值接口，需拉全量自算 |
| 2 | 对话记录主表（AI问题/可见度/提及次数/排名/TOP1/TOP3/最近更新） | 加载 | `GET /runs/{id}/answers`（**注意：答案是 prompt×platform 粒度**） | q=prompt 文本、提及次数=`brand_results.mention_count`、最近更新=`collected_at` | ⚠️**按「AI 问题」聚合 + 跨平台合并**后端无接口（answers 是逐条答案）（§8⑨） |
| 3 | 品牌可见度 vis% / 品牌排名 #X / TOP1 / TOP3（每问题） | 加载 | join `prompt_competitiveness`（`target_rank, target_first`）+ `brand_results` | 排名=`target_rank`、TOP1=`target_first` | ⚠️ prompt 级指标只在 `summary_json.prompt_competitiveness_summary` / analysis，未独立分页接口 |
| 4 | 各模型指标就地展开（每平台×端：可见度/提及次数/排名/TOP1/TOP3，无数据显「无数据」） | 点击展开 | `analysis.summary_json.prompt_competitiveness_summary`（按 prompt×platform） | 每端一组指标 | ⚠️ 端维度无字段（§8①）；未覆盖端=后端无该 platform 行 |
| 5 | 查看回答弹窗（左平台列表 + 头部 KPI + 对话原文 + 引用来源表） | 点问题 | `GET /answers/{id}` | `raw_text`(原文)、`normalized_text`、`model_name`、`citations[]`、`brand_results[]` | ✅ 主体可落地 |
| 6 | 弹窗头部：提及品牌(2)、情感倾向(正/中/负)、引用网站数、引用文章数 | 弹窗 | `answers/{id}` 派生 | 情感=`brand_results.sentiment`、提及品牌=`brand_results[is_mentioned]`、引用文章数=`citations.length`、网站数=`distinct(citations.domain)` | ✅ |
| 7 | 引用来源表（序号/站点名/站点类型/标题，标题可跳原文） | 弹窗 | `citations[]` | `citation_no, title, url, domain, source_type` | ⚠️ 站点类型仅 6 类（§8④） |
| 8 | 深度思考过程 + 搜索关键词 chip | 弹窗 | `GET /answers/{id}` → 需 `raw_response_json`（思考/搜索词） | ⚠️ `AnswerDetailRead` **未暴露 `raw_response_json`**，思考过程/搜索词取不到 | ⚠️ 需扩展返回（§8⑩） |
| 9 | 高频评价标签（fac/factor，对回答聚类） | 弹窗 | **无接口**（原型前端聚类 mock） | — | ⚠️**缺失（§8⑪）** |
| 10 | 搜索框（按 AI 问题搜） | 输入 | `GET /runs/{id}/answers` **无 `keyword` 参数** | — | ⚠️ 需加搜索参数（§8⑨） |
| 11 | 导出 AI 对话记录（Excel） | 点击 | 无 Excel；仅报告 md/html/pdf | — | ⚠️ §8⑦ |
| 12 | 分页（total 20 / size 10） | 翻页 | `GET /runs/{id}/answers?page&page_size` | `total,page,page_size` | ✅ |

---

## 7. 原型页 6 — 信源引用分析（`6信源引用分析v3.html`）

**页面定位**：分析 AI 回答引用了哪些信源（站点/类型），含计数 KPI、类型分布、按平台分列的站点影响力矩阵。
**主数据源**：`dashboard.platforms[].analysis.top_sources` / `GET /runs/{id}/analysis`（`SourceStatRow`）+ 逐答案 `citations[]`。

| # | 系统功能 | API | 出参 → 前端字段 | 缺口 |
| --- | --- | --- | --- | --- |
| 1 | KPI 计数三卡（引用文章数/引用次数/引用网站） | `analysis` 聚合 `top_sources` + `citation_count` 快照 | 引用次数=Σ`citation_count`；引用网站=distinct domain 数 | ⚠️**引用文章数（文章级=distinct URL/title）** source_stat 只到 domain 级，需从 `citations[]` 聚合（§8④）；无专用 KPI 接口 |
| 2 | 信源类型分布·占比（甜甜圈 + 横条，8 类） | 前端 group `top_sources.source_type` | 占比按 citation_count 归一 | ⚠️ 后端 `source_type` 仅 6 类（web/official/media/social/video/ecommerce），原型 8 类（爱搜附录C）**不一致**（§8④） |
| 3 | 信源类型分布·趋势（8 类 × 7 天） | `trends`（**无 source_type 维度快照**） | — | ⚠️**缺失** —— metric_snapshot 无信源/类型维度（§8④） |
| 4 | 信源站点影响力矩阵 Top10（站点 × 平台×端，热力 + 金银铜） | `analysis.platforms[].top_sources`（每平台一组 `SourceStatRow{domain, citation_count, share_rate, rank_no}`） | 矩阵单元=各平台 `citation_count`；合计=Σ；排名=`rank_no` | ⚠️ 列是「平台×端」，端维度缺（§8①）；站点中文名缺（只有 domain） |
| 5 | 指标口径切换（引用次数/链接数/引用率） | `citation_count` / `share_rate` | 引用次数=`citation_count`，引用率=`share_rate` | ⚠️「链接数」=原型 `次数×0.7` mock，后端无独立字段 |
| 6 | 矩阵列由平台多选驱动（未选平台显「—」不计分母） | dashboard/analysis 按 run 平台返回 | 选中 `platform_code` 过滤 | ⚠️ 端维度缺；分母排除逻辑前端做 |
| 7 | 信源类型下拉筛选 + 搜索站点框 | 前端基于 `top_sources` 过滤 | `source_type` / `domain` | ✅（前端过滤） |

> **结论**：信源页「当前快照矩阵 + 占比」可由 `SourceStatRow` + `citations[]` 落地（域名级）；缺口集中在：①8 类 vs 6 类**分类口径不一致**、②**文章级**（URL）聚合无现成接口、③**信源趋势/类型趋势无快照维度**、④端维度。

---

## 8. 后端缺失能力汇总（迭代优先级）

> P0 = 不补则该页核心功能无法落地；P1 = 重要但有降级方案；P2 = 增强项。

| 编号 | 缺失能力 | 影响页面 | 现状 / 降级 | 建议方案 | 优先级 |
| --- | --- | --- | --- | --- | --- |
| ⑤ | **AI 智能生成**（品牌词 / 竞品 / 监测问题） | 1、2 | 仅 `GET /prompt-library` 静态模板；无生成 | 新增 `POST /projects/{id}/ai-suggest`（type=brand_words\|competitors\|questions，调 LLM） | **P0** |
| ③ | **竞品/品牌维度的指标快照与趋势** | 3、4 | `metric_snapshot` 无 `brand_id` 维度；`summary` 顶层无竞品聚合；**平均排名根本未存快照** | snapshot 增 `brand_id` 维度 + 存 `average_mention_rank/sov`；新增 `GET /projects/{id}/competitor-trends` | **P0** |
| ② | **看板时间范围聚合** | 3、4、5、6 | dashboard 只认单 `run_id`；跨 run 聚合缺 | dashboard 增 `start_at/end_at`，按区间聚合多 run | **P0** |
| ① | **平台「端侧」（网页/手机）维度** | 全部 | 仅 `platform_code` 单维 + aidso thinking 开关 | 模型层把 `platform_code` 扩为 `platform_code × endpoint`，或新增 `endpoint` 字段贯穿 task/answer/snapshot | **P0** |
| ④ | **信源：文章级聚合 + 8 类口径 + 信源趋势** | 6、3 | source_stat 仅 domain 级；`source_type` 6 类；无信源趋势快照 | 新增 `GET /runs/{id}/sources`（文章级 + 站点中文名 + 8 类映射表）；snapshot 增信源类型维度 | **P1** |
| ⑨ | **对话记录按「AI 问题」聚合 + 关键词搜索** | 5 | answers 是逐条答案（prompt×platform），无 group-by-prompt、无 `keyword` 参数 | 新增 `GET /runs/{id}/questions`（按 prompt 聚合各平台指标）+ answers 加 `keyword` 过滤 | **P1** |
| ⑩ | **答案详情暴露思考过程 / 搜索关键词** | 5 | `AnswerDetailRead` 未含 `raw_response_json` | detail 增字段（脱敏后）或新增 `GET /answers/{id}/raw` | P1 |
| ⑦ | **Excel 导出** | 3、5 | 仅 md/html/pdf | 报告 `formats` 增 `xlsx`，或独立导出端点 | P1 |
| ⑧ | **行业平均 / 历史最高 参照值** | 4 | 无行业基准；历史最高可由 trends 算 | 行业平均需外部基准库（产品决策）；历史最高前端用 trends max | P2 |
| ⑪ | **高频评价标签（factor 聚类）** | 5 | 无 | LLM 聚类，新增字段/接口（成本高，原型已标「可不做」） | P2 |
| ⑥ | **意图 5 类口径对齐** | 1、2 | 后端 `prompt_type`（`infer_prompt_type`）取值未必=原型 5 类 | 统一枚举（品牌情绪/品牌信息/品类情绪/竞品对比/品类推荐）并暴露推断接口 | P2 |
| — | **定时调度 UI 闭环** | （隐含） | 后端 `schedules` 已全实现，原型 v1 无 UI | 原型补调度页即可直接对接 | P2 |

---

## 9. 字段速查表（原型字段 ↔ 后端字段）

| 原型字段 / 指标 | 后端字段 | 来源接口 |
| --- | --- | --- |
| 提及率 mention/rate | `brand_mention_rate` | dashboard.summary / platforms[].analysis |
| 首位(Top1)提及率 first | `brand_top1_mention_rate`（兜底 `brand_first_rate`） | 同上 |
| Top3(首屏)提及率 | `brand_top3_mention_rate` | 同上 |
| 品牌提及次数 count | `brand_mention_count` | summary |
| 有效回答/对话次数 | `valid_answer_count` | summary / platform |
| 数据完整度 | `data_completeness_rate` | summary / run |
| 平均提及排名 rank | `brand_metrics[].average_mention_rank` | summary_json.metrics |
| SOV 声量份额 | `brand_metrics[].share_of_voice` | summary_json.metrics |
| 品牌得分(已剔除) | `brand_metrics[].brand_score` | summary_json.metrics |
| 正向提及率/好感度(已剔除) | `brand_metrics[].positive_neutral_sentiment_percent` | summary_json.metrics |
| 情感倾向 正/中/负 | `brand_results[].sentiment` | GET /answers/{id} |
| 品牌可见度 vis | `prompt_competitiveness.target_rank` 有值即可见 / `brand_results.is_mentioned` | analysis / answers |
| 品牌排名 #X | `prompt_competitiveness.target_rank` | analysis |
| 竞品榜（name/提及率/排名） | `brand_metrics[]` 或 `top_competitors[]`(`CompetitorRow`) | summary_json / analysis |
| 信源站点 site / 域名 | `SourceStatRow.domain`（中文名缺） | analysis.top_sources |
| 信源类型（8 类） | `source_type`（仅 6 类） | top_sources / citations |
| 引用次数 cites | `SourceStatRow.citation_count` | analysis.top_sources |
| 引用占比/引用率 | `SourceStatRow.share_rate` | analysis.top_sources |
| 引用文章（文章级 links） | `CitationRead.{title,url,domain}` | GET /answers/{id} |
| 对话原文 full | `Answer.raw_text` / `normalized_text` | GET /answers/{id} |
| 最近更新 date | `Answer.collected_at` / `run.completed_at` | answers / runs |
| 趋势折线（仅目标品牌） | trends 快照 `metric_value`×`snapshot_at` | GET /projects/{id}/trends |

**可用 `metric_code`（趋势/快照）**：`brand_mention_count, brand_mention_rate, brand_first_count, brand_first_rate, brand_first_among_mentions_rate, valid_answer_count, data_completeness_rate, citation_count, brand_related_citation_count, competitor_top1_count, prompt_competitiveness_avg`（另 summary 内含 `brand_top1_mention_rate, brand_top3_mention_rate`）。
> ⚠️ 注意：**无 `average_mention_rank` / `share_of_voice` / 竞品级 / 信源域名级**的趋势 `metric_code`（§8③④）。

---

## 10. 端到端典型调用时序（一次完整闭环）

```text
① 创建项目      POST /projects                         → project_id
② 取平台/模板    GET /platforms ; GET /prompt-library
③ 保存配置      PUT /projects/{id}/monitor-setup       （品牌/竞品/核心词/问题/平台, activate_prompt_set=true）
④ 启动监测      POST /runs { project_id, prompt_set_id, platform_codes, collection_source }   → run_id
                （后端自动扇出 Prompt×Platform 采集任务 → Worker 采集 → 自动入队分析）
⑤ 轮询进度      GET /runs/{run_id}        （status / progress_rate / *_tasks）
⑥ 看大盘        GET /projects/{id}/dashboard           → KPI + 平台 + 竞品 brand_metrics + top_sources
   看趋势        GET /projects/{id}/trends?metric_code=brand_mention_rate
⑦ 看对话        GET /runs/{run_id}/answers → GET /answers/{answer_id}   （原文 + 引用 + 品牌命中）
⑧ 看竞品/信源    复用 ⑥ 的 dashboard.platforms[].analysis.summary_json
⑨ 出报告        POST /runs/{run_id}/reports {formats:["pdf"]} → GET /reports/{id} → /download
```

**采集→分析状态机**（影响页面 loading 态）：
`run.status`: `pending → collecting → analyzing → (completed | partial_success | failed | cancelled)`；
`analysis_status`: `skipped/pending → ...completed`（采集全终态后自动入队分析）。前端轮询 `GET /runs/{id}` 的 `status` + `progress_rate` 控制大盘/竞品/信源页的「数据生成中」遮罩。

---

## 11. 一句话总结

- **配置域（页 1、2）**：除「AI 生成」外，全部可由 `projects` + `monitor-setup` 接口落地，**唯一硬缺口是内容生成（§8⑤）**。
- **数据域（页 3、4、5、6）**：当前**单次快照**几乎都能从 `dashboard` / `analysis(summary_json)` / `answers` 拼出；
  **真正缺的是四类「维度」**：①平台×端、②时间范围聚合、③竞品/品牌级趋势（连平均排名快照都没存）、④信源文章级 + 8 类口径 + 信源趋势。
- 后端**调度、报告**能力已完备，原型 v1 反而**未画**调度页与正式报告页，可作为下一轮原型补充。
