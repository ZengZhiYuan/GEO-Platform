# 原型功能 API 映射调用手册

> 更新日期：2026-06-30
> 本文定位：说明原型 6 个页面中每个入口、按钮、筛选和弹窗应该调用哪些后端接口，以及推荐调用顺序。
> 互补文档：接口字段、入参、出参、错误码以 `docs/API接口文档.md` 为准；验收口径和自动化命令以 `docs/API测试文档.md` 为准。

## 1. 当前结论

原型图中展示的核心功能已经基本具备后端接口支撑：

- 项目管理：首页直接展示所有项目；`GET /projects/overview` 已聚合品牌词/竞品/平台端图标/状态标签/更新时间，并支撑进入监测详情、编辑配置、暂停/恢复、删除前检查等动作。
- 创建监测项目：向导草稿、平台端字典、Prompt 类型字典、AI 生成品牌词/竞品/问题、一步创建与完整配置保存均已覆盖。
- 数据大盘：页面级总览、平台/时间筛选、趋势、竞品/信源/问题预览、报告生成下载均已覆盖。
- 竞品分析：页面级聚合、行业基准、品牌维度趋势快照查询均已覆盖。
- AI 对话记录：按问题聚合、问题下多平台回答详情、高频评价标签、CSV 导出均已覆盖。
- 信源引用分析：页面级聚合、信源类型字典、站点矩阵、指标切换、CSV 导出均已覆盖。

需要前端注意的现实差异：

- 对话记录和信源导出当前是 CSV 文件流，不是原型文案里的 Excel。
- 第三方采集：新建 Run 使用 `collection_source=molizhishu` 与 `molizhishu_*` 平台码（见 `GET /platform-endpoints`）；**不得**再传 `collection_source=aidso` 或 `aidso_thinking_enabled_by_platform`（返回 422）。历史 Aidso Run 详情仍可只读展示。
- `/projects/{project_id}/competitor-analysis` 的 `trends` 字段仍是空数组占位；竞品趋势图应直接调用 `/projects/{project_id}/trends`，并传 `brand_id`。
- `GET /projects/{project_id}/trends` 只支持单个 `platform_code`；多平台趋势图需要前端按平台分别请求，或不传平台取平台级汇总快照。
- AI 生成提供无 `project_id` 的全局路径 `/ai/*:generate`，**创建向导中途 AI 生成应优先使用该路径**，无需先 `POST /projects`；项目域路径 `/projects/{project_id}/ai/*:generate` 保留供已创建项目的编辑配置场景。

## 2. 全局页面初始化

### 2.1 所有业务页面通用

推荐页面壳加载顺序：

1. 用户进入系统后直接进入项目管理首页，调用 `GET /api/geo-monitoring/projects/overview?page=1&page_size=10`。
   - 首页不再展示顶部项目切换下拉。
   - `GET /projects/options` 仅作为兼容轻量列表保留，不作为首页首屏必需接口。
   - `GET /projects/overview` 已返回 `platform_endpoints[]`，首页无需再额外调用 `GET /platform-endpoints` 映射图标。
2. `GET /api/geo-monitoring/platform-endpoints?enabled=true`
   - 用于平台端多选控件、平台 Logo、Web/App 端展示（创建向导等场景仍需要）。
   - 官方平台码：`doubao`、`qwen` 等；第三方模力指数平台码：`molizhishu_*`（与 `collection_source=molizhishu` 配套）。
3. 按页面需要加载字典：
   - `GET /api/geo-monitoring/prompt-types`
   - `GET /api/geo-monitoring/source-types`
   - `GET /api/geo-monitoring/benchmarks?industry={industry}`
4. 进入具体页面后调用该页面的主聚合接口。

### 2.2 公共筛选动作

| 原型动作 | 推荐调用 |
| --- | --- |
| 进入系统首页 | `GET /projects/overview`，直接展示所有项目 |
| 平台端多选 | 当前页主接口追加 `platform_codes`；趋势接口如需多平台，按 `platform_code` 分多次请求 |
| 时间范围筛选 | 当前页主接口追加 `start_at`、`end_at` |
| 刷新按钮 | 保留当前筛选条件，重新请求当前页主接口及其趋势/预览接口 |
| 搜索框 | 项目页使用 `project_name`；对话记录使用 `keyword`；信源页使用 `keyword` |

## 3. 页面到主接口速查

| 原型页 | 首屏主接口 | 主要辅助接口 |
| --- | --- | --- |
| 项目管理 | `GET /projects/overview` | `/platform-endpoints`、`/monitor-setup`、`/pause`、`/resume`、`/delete-check`、`DELETE /projects/{project_id}` |
| 创建监测项目向导 | `PUT /project-drafts/current` 或 `POST /projects` 后 `PUT /monitor-setup` | `/platform-endpoints`、`/prompt-types`、`/prompt-library`、`/ai/*:generate`、`/projects:setup` |
| 数据大盘 | `GET /projects/{project_id}/dashboard/overview` | `/trends`、`/reports`、`/runs` |
| 竞品分析 | `GET /projects/{project_id}/competitor-analysis` | `/benchmarks`、`/trends` |
| AI 对话记录 | `GET /projects/{project_id}/conversation-questions` | `/conversation-questions/{prompt_id}/answers`、`/evaluation-tags`、`/export` |
| 信源引用分析 | `GET /projects/{project_id}/source-analysis` | `/source-types`、`/source-analysis/export`、`/trends?metric_code=citation_rate` |

## 4. 原型页 1：项目管理

### 4.1 进入页面

调用顺序：

1. `GET /projects/overview?page=1&page_size=10`

页面卡片优先使用 `GET /projects/overview`，它已经聚合：

- 项目基本信息。
- 目标品牌名。
- 品牌词数与 `brand_words[]` 标签明细。
- 竞品数与 `competitors[]` 标签明细。
- 已启用问题数。
- 基础平台数与平台端数。
- `platform_endpoints[]` 平台端图标列表。
- 最近一次运行摘要。
- `monitoring_paused` 暂停状态。
- `homepage_badges[]` 状态标签（`监测中` / `已暂停`）。
- `last_updated_at` 首页更新时间。

新版首页截图期望的卡片展示：

| 展示区域 | 接口字段 |
| --- | --- |
| 项目名称 / 行业 / 状态 | `project_name`、`industry`、`status`、`monitoring_paused`、`homepage_badges[]` |
| 品牌词标签 | `brand_word_count`、`brand_words[]` |
| 竞品标签 | `competitor_count`、`competitors[]` |
| 监测平台图标 | `platform_endpoints[]` |
| 问题数 / 平台数 / 端数 | `question_count`、`platform_count`、`endpoint_count` |
| 更新时间 | `last_updated_at` |

### 4.2 搜索、状态筛选、分页、刷新

| 原型动作 | 接口顺序 |
| --- | --- |
| 搜索项目名 | `GET /projects/overview?project_name={keyword}&page=1` |
| 状态筛选 | `GET /projects/overview?status=active|disabled|archived` |
| 翻页 | `GET /projects/overview?page={page}&page_size={page_size}` |
| 刷新 | 按当前筛选条件重新请求 `GET /projects/overview` |

### 4.3 创建项目按钮

按钮含义：进入创建监测项目向导。

推荐调用：

1. 前端生成 `draft_key`。
2. 可选：`POST /project-drafts` 创建空草稿。
3. 跳转到创建向导页。

如果前端不需要服务端草稿，也可以只跳转；最终保存仍走向导页调用链。

### 4.4 进入按钮

按钮含义：进入当前项目的数据大盘。

调用顺序：

1. 记录当前 `project_id`。
2. 跳转数据大盘。
3. 监测详情页调用 `GET /projects/{project_id}/dashboard/overview`；需要指定运行时追加 `run_id`。

### 4.5 编辑配置按钮

按钮含义：打开项目配置抽屉或弹窗。

打开弹窗调用顺序：

1. `GET /projects/{project_id}/monitor-setup`
2. `GET /platform-endpoints?enabled=true`
3. `GET /prompt-types`
4. 可选：`GET /prompt-library?page_size=100`

保存按钮：

1. 前端将三个 Tab 的本地草稿合并为一次配置。
2. `PUT /projects/{project_id}/monitor-setup`
3. 保存成功后刷新：
   - `GET /projects/overview`
   - 如当前项目已经打开数据页，再刷新对应数据页主接口。

### 4.6 编辑配置：品牌与平台 Tab

| 原型动作 | 接口顺序 |
| --- | --- |
| 回填品牌名、官网、品牌词、平台端 | 已由 `GET /monitor-setup` + `GET /platform-endpoints` 提供 |
| 手动新增/删除品牌词 chip | 前端先改本地草稿；点击保存时统一 `PUT /monitor-setup` |
| AI 生成品牌词 | `POST /projects/{project_id}/ai/brand-words:generate`，返回候选后由前端让用户勾选，再保存到 `monitor-setup` |
| 切换平台端 | 前端先改 `selected_platform_codes` 草稿；点击保存时统一 `PUT /monitor-setup` |
| 保存 | `PUT /projects/{project_id}/monitor-setup` |

细粒度别名接口 `/brands/{brand_id}/aliases` 仍可用于高级编辑，但原型配置抽屉推荐整存 `monitor-setup`。

### 4.7 编辑配置：竞品 Tab

| 原型动作 | 接口顺序 |
| --- | --- |
| 回填竞品和竞品词 | `GET /projects/{project_id}/monitor-setup` |
| 手动新增/删除竞品 | 前端先改本地草稿 |
| AI 生成竞品 | `POST /projects/{project_id}/ai/competitors:generate`，返回候选后由用户勾选 |
| 保存 | `PUT /projects/{project_id}/monitor-setup` |

### 4.8 编辑配置：监测问题 Tab

| 原型动作 | 接口顺序 |
| --- | --- |
| 回填问题列表和意图分类 | `GET /projects/{project_id}/monitor-setup` + `GET /prompt-types` |
| 从模板添加问题 | `GET /prompt-library` 获取模板，前端加入草稿 |
| AI 重新生成问题 | `POST /projects/{project_id}/ai/questions:generate`，返回候选后加入草稿 |
| 手动新增/编辑/删除问题 | 前端先改本地草稿 |
| 保存并启用新问题集 | `PUT /projects/{project_id}/monitor-setup`，传 `activate_prompt_set=true` |

如需独立维护 Prompt 集版本，可使用 `/projects/{project_id}/prompt-sets`、`/prompt-sets/{prompt_set_id}/prompts` 和 `/prompt-sets/{prompt_set_id}/activate`；原型的一站式配置体验优先使用 `monitor-setup`。

### 4.9 暂停 / 恢复监测按钮

| 原型动作 | 接口顺序 |
| --- | --- |
| 暂停监测 | 卡片显示“暂停”时调用 `POST /projects/{project_id}/pause`，成功后刷新 `GET /projects/overview` |
| 恢复监测 | 卡片显示“监测”或“恢复监测”时调用 `POST /projects/{project_id}/resume`，成功后刷新 `GET /projects/overview` |

暂停只阻止新运行和调度触发，不删除历史数据。

### 4.10 删除项目按钮

推荐调用顺序：

1. `GET /projects/{project_id}/delete-check`
2. 若 `can_delete=false`，展示 `blocking_reasons`，不调用删除。
3. 若 `can_delete=true`，用户二次确认后调用 `DELETE /projects/{project_id}`。
4. 删除成功后刷新 `GET /projects/overview`。

## 5. 原型页 2：创建监测项目向导

### 5.1 推荐总流程

创建向导推荐**全程不落库**，直到用户点击完成：

1. 进入向导：
   - `GET /platform-endpoints?enabled=true`
   - `GET /prompt-types`
   - `GET /prompt-library?page_size=100`
   - 可选：`GET /project-drafts/current?draft_key={draft_key}` 恢复草稿。
2. 各步骤填写与 AI 生成：
   - 中途 AI 生成按钮调用全局路径 `/ai/brand-words:generate`、`/ai/competitors:generate`、`/ai/questions:generate`（**无需 project_id**）。
   - 用户确认的候选写入草稿：`PUT /project-drafts/current`。
3. 第 3 步配置监测问题：
   - AI 生成问题调用 `/ai/questions:generate`。
   - 模板问题来自 `GET /prompt-library`。
4. 点击完成（推荐一步创建）：
   - `POST /projects:setup`，一次性创建项目并保存完整监测配置。
5. 如完成后立即开始监测：
   - 官方采集（默认）：`POST /runs`（`collection_source` 省略或 `official`）。
   - 模力指数采集：先确认 `.env` 已配置 `MOLIZHISHU_*`；`POST /runs` 传 `collection_source=molizhishu`、`platform_codes` 为所选 `molizhishu_*`；可选 `provider_mode_by_platform`、`provider_screenshot`、`region_code`（区域列表 `GET /providers/molizhishu/regions`）。
   - `GET /runs/{run_id}` 轮询进度。

**取消向导**：仅丢弃草稿，不会产生正式项目脏数据。

兼容流程（已创建项目的分步保存）：若向导第 1 步已调用 `POST /projects` 获取 `project_id`，后续 AI 生成可继续使用项目域路径 `/projects/{project_id}/ai/*:generate`；完成时调用 `PUT /projects/{project_id}/monitor-setup`。该流程在用户取消时可能留下未配置完的空项目，**不推荐用于新建向导**。

### 5.2 上一步 / 下一步按钮

| 原型动作 | 接口顺序 |
| --- | --- |
| 下一步 | 前端校验当前步骤；调用 `PUT /project-drafts/current` 保存草稿；**无需**为 AI 生成提前 `POST /projects` |
| 上一步 | 前端切换步骤；可选 `PUT /project-drafts/current` 保存当前草稿 |
| 离开后恢复 | `GET /project-drafts/current?draft_key={draft_key}` |

### 5.3 AI 生成按钮

| 原型按钮 | 接口顺序 |
| --- | --- |
| AI 生成品牌词 | `POST /ai/brand-words:generate`（推荐）或 `POST /projects/{project_id}/ai/brand-words:generate`（已创建项目） → 用户选择候选 → 写入草稿 `brand.brand_words` |
| AI 生成竞品 | `POST /ai/competitors:generate`（推荐）或 `POST /projects/{project_id}/ai/competitors:generate` → 用户选择候选 → 写入草稿 `competitors[]` |
| AI 生成监测问题 | `POST /ai/questions:generate`（推荐）或 `POST /projects/{project_id}/ai/questions:generate` → 用户选择候选 → 写入草稿 `ai_questions[]` |

生成接口只返回候选，不落库。真正保存发生在 `PUT /monitor-setup` 或 `POST /projects:setup`。

### 5.4 完成创建按钮

**推荐（无 project_id，事务式一步创建）：**

1. `POST /projects:setup`
2. 如果传 `run_after_create=true`，响应中可直接带 `run`。
3. 跳转项目管理或数据大盘。

兼容（已有 `project_id` 的分步保存）：

1. `PUT /projects/{project_id}/monitor-setup`
2. 如需启动首次运行：`POST /runs`
3. `GET /runs/{run_id}` 轮询。
4. 跳转数据大盘：`GET /projects/{project_id}/dashboard/overview?run_id={run_id}`

### 5.5 完成摘要

完成页数字砖优先使用保存接口的返回数据；刷新时调用：

1. `GET /projects/{project_id}/monitor-setup`
2. `GET /projects/overview` 获取卡片聚合数。

## 6. 原型页 3：数据大盘

### 6.1 进入页面

调用顺序：

1. 从首页“进入”按钮携带 `project_id` 进入监测详情页。
2. `GET /platform-endpoints?enabled=true`
3. `GET /projects/{project_id}/dashboard/overview`
4. 按图表需要调用趋势接口：
   - 品牌可见度：`GET /projects/{project_id}/trends?metric_code=brand_visibility`
   - Top1：`metric_code=brand_top1_mention_rate`
   - Top3：`metric_code=brand_top3_mention_rate`
   - Top10：`metric_code=brand_top10_mention_rate`
   - 引用率：`metric_code=citation_rate`

`dashboard/overview` 已一次返回 KPI、平台表现、竞品预览、信源预览和最近问题预览。

### 6.2 平台端筛选、时间筛选、刷新

| 原型动作 | 接口顺序 |
| --- | --- |
| 平台端多选 | `GET /dashboard/overview?platform_codes=...`；趋势图若展示分平台线条，按每个 `platform_code` 分别请求 `/trends` |
| 时间范围筛选 | `GET /dashboard/overview?start_at=...&end_at=...`；趋势图也追加同一时间范围 |
| 刷新 | 重新请求 `dashboard/overview` 和当前图表使用的 `/trends` |

### 6.3 KPI 卡片

KPI 直接来自 `GET /dashboard/overview` 的 `kpis`：

- 品牌提及率。
- Top1 / Top3 / Top10 提及率。
- 有效回答数。
- 提及对话数。
- 平均提及排名。
- SOV。
- 品牌提及总次数。
- 正/中/负情感率。

无运行、无分析或无分母时，相关比率可能为 `null`，前端显示为 `--`。

### 6.4 平台表现卡

平台表现来自 `dashboard/overview.platforms[]`。

点击平台卡后，如需要查看该平台的趋势：

1. `GET /projects/{project_id}/trends?metric_code=brand_visibility&platform_code={platform_code}`
2. 其它指标按当前图表切换替换 `metric_code`。

### 6.5 竞品预览区

首屏预览来自 `dashboard/overview.competitor_preview`。

| 原型动作 | 接口顺序 |
| --- | --- |
| 点击“查看更多竞品分析” | 跳转竞品分析页，调用 `GET /projects/{project_id}/competitor-analysis` |
| 点击某个竞品查看趋势 | 在竞品分析页使用该行 `brand_id` 调 `/trends?metric_code=brand_mention_rate&brand_id={brand_id}` |

### 6.6 信源预览区

首屏预览来自 `dashboard/overview.source_preview`。

| 原型动作 | 接口顺序 |
| --- | --- |
| 点击“查看更多信源” | 跳转信源引用分析页，调用 `GET /projects/{project_id}/source-analysis` |
| 点击站点 | 跳转信源页并用 `keyword={domain 或 source_name}` 重新查询 |

### 6.7 最近问题预览

首屏预览来自 `dashboard/overview.recent_questions`。

| 原型动作 | 接口顺序 |
| --- | --- |
| 点击“查看更多对话记录” | 跳转 AI 对话记录页，调用 `GET /projects/{project_id}/conversation-questions` |
| 点击某个问题 | 调用 `GET /projects/{project_id}/conversation-questions/{prompt_id}/answers` 打开回答详情 |

### 6.8 下载报告按钮

推荐调用顺序：

1. 从 `dashboard/overview.run_id` 取得当前运行；如果为空，提示暂无可生成报告的数据。
2. `POST /runs/{run_id}/reports`，推荐 body 使用 `formats=["pdf"]`。
3. `GET /reports/{report_id}` 查询状态。
4. `GET /reports/{report_id}/download` 下载文件。

报告下载是文件流，不是统一 JSON。

### 6.9 立即监测 / 重新运行按钮

如果页面提供手动运行入口，调用顺序：

1. `POST /runs`
2. `GET /runs/{run_id}` 轮询采集、分析、报告阶段进度。
3. 运行到终态后刷新 `GET /dashboard/overview?run_id={run_id}`。

## 7. 原型页 4：竞品分析

### 7.1 进入页面

调用顺序：

1. `GET /projects/{project_id}/competitor-analysis`
2. `GET /benchmarks?industry={project.industry}`，用于行业平均和市场地位参照。
3. 如页面展示历史趋势，使用 `competitor-analysis.boards` 中的 `brand_id` 继续调用 `/trends`。

### 7.2 平台、时间、范围筛选

| 原型动作 | 接口顺序 |
| --- | --- |
| 平台端筛选 | `GET /competitor-analysis?platform_codes=...` |
| 时间范围筛选 | `GET /competitor-analysis?start_at=...&end_at=...` |
| Top5 / 全部切换 | `GET /competitor-analysis?brand_scope=top5|all` |
| 刷新 | 保留筛选条件重新请求 `competitor-analysis`；如有趋势图，也重新请求 `/trends` |

### 7.3 KPI 与榜单

| 原型模块 | 数据来源 |
| --- | --- |
| 目标品牌 KPI | `competitor-analysis.kpis` |
| 目标品牌信息 | `competitor-analysis.target_brand` |
| 提及率榜 | `competitor-analysis.boards.mention_rate[]` |
| 平均排名榜 | `competitor-analysis.boards.average_rank[]` |
| 提及次数榜 | `competitor-analysis.boards.mention_count[]` |
| 行业平均 | `GET /benchmarks?industry={industry}` |

榜单行中的 `is_target=true` 用于高亮目标品牌。

### 7.4 趋势图

不要使用 `competitor-analysis.trends` 作为图表数据源；该字段目前仍为占位空数组。

推荐调用：

| 趋势图 | 接口 |
| --- | --- |
| 品牌提及率趋势 | `GET /projects/{project_id}/trends?metric_code=brand_mention_rate&brand_id={brand_id}` |
| 平均排名趋势 | `GET /projects/{project_id}/trends?metric_code=average_mention_rank&brand_id={brand_id}` |
| 提及次数趋势 | `GET /projects/{project_id}/trends?metric_code=brand_mention_total_count&brand_id={brand_id}` |
| SOV 趋势 | `GET /projects/{project_id}/trends?metric_code=share_of_voice&brand_id={brand_id}` |

若原型展示目标品牌和多个竞品的多条折线，前端按每个品牌分别请求一次。

### 7.5 点击竞品行

可选交互：

1. 记录选中 `brand_id`。
2. 调用对应指标的 `/trends` 刷新右侧趋势。
3. 如需查看该竞品出现在哪些问题中，跳转 AI 对话记录页，并用关键词搜索该品牌名：`GET /conversation-questions?keyword={brand_name}`。

## 8. 原型页 5：AI 对话记录

### 8.1 进入页面

调用顺序：

1. `GET /projects/{project_id}/conversation-questions`
2. `GET /platform-endpoints?enabled=true`，用于表格平台列展示。

主表以 AI 问题为一行，不再使用答案粒度的 `/runs/{run_id}/answers` 拼装。

### 8.2 搜索、筛选、分页、导出

| 原型动作 | 接口顺序 |
| --- | --- |
| 按问题搜索 | `GET /conversation-questions?keyword={keyword}&page=1` |
| 平台端筛选 | `GET /conversation-questions?platform_codes=...` |
| 时间范围筛选 | `GET /conversation-questions?start_at=...&end_at=...` |
| 分页 | `GET /conversation-questions?page={page}&page_size={page_size}` |
| 导出当前结果 | `GET /conversation-questions/export`，带上当前筛选条件 |
| 刷新 | 重新请求 `GET /conversation-questions` |

导出当前为 CSV，前端按钮文案建议为“导出 CSV”或“导出表格”。

### 8.3 展开问题行

主表 `items[].platform_metrics` 已包含该问题在各平台端的指标：

- 有效回答数。
- 可见度。
- 提及次数。
- 平均排名。
- Top1 / Top3 / Top10。
- SOV。
- 情感率。

展开行时如果只展示指标，可直接使用主表返回；如果要展示回答正文，调用详情接口。

### 8.4 查看回答弹窗

点击问题行或“查看回答”按钮：

1. `GET /projects/{project_id}/conversation-questions/{prompt_id}/answers`
2. 可选：`GET /projects/{project_id}/conversation-questions/{prompt_id}/evaluation-tags`

回答详情接口返回同一问题下各平台回答，包含：

- 回答正文。
- 平台端编码。
- Prompt 文本和类型。
- 引用来源。
- 品牌识别结果。
- 安全提取的 `reasoning_text`。
- 安全提取的 `search_keywords`。

### 8.5 弹窗内按钮和 Tab

| 原型动作 | 接口顺序 |
| --- | --- |
| 切换平台回答 | 优先使用已返回的 `answers.items[]`；如分页未取全，带 `page/page_size` 再请求详情接口 |
| 查看引用来源 | 使用详情接口返回的 `citations[]` |
| 查看提及品牌 | 使用详情接口返回的 `brand_results[]` |
| 查看深度思考 / 搜索关键词 | 使用详情接口返回的 `reasoning_text`、`search_keywords` |
| 查看高频评价标签 | `GET /conversation-questions/{prompt_id}/evaluation-tags` |
| 打开引用原文 | 前端打开 `citations[].url`，后端不代理外链 |

## 9. 原型页 6：信源引用分析

### 9.1 进入页面

调用顺序：

1. `GET /source-types`
2. `GET /platform-endpoints?enabled=true`
3. `GET /projects/{project_id}/source-analysis`

页面主接口已经返回：

- KPI：引用数、站点数、文章数、引用率。
- 信源类型分布。
- 平台端矩阵列。
- 站点影响力矩阵分页。

### 9.2 筛选、搜索、指标切换、分页

| 原型动作 | 接口顺序 |
| --- | --- |
| 平台端筛选 | `GET /source-analysis?platform_codes=...` |
| 时间范围筛选 | `GET /source-analysis?start_at=...&end_at=...` |
| 信源类型下拉 | `GET /source-analysis?source_type={source_type}` |
| 搜索站点 | `GET /source-analysis?keyword={domain_or_name}` |
| 链接数 / 引用率切换 | `GET /source-analysis?metric=links|rate` |
| 矩阵分页 | `GET /source-analysis?page={page}&page_size={page_size}` |
| 刷新 | 保留筛选条件重新请求 `GET /source-analysis` |

### 9.3 类型分布图

类型字典来自 `GET /source-types`；类型分布数据来自 `source-analysis.type_distribution[]`。

点击某个类型切片：

1. 将该类型 code 写入筛选条件。
2. `GET /source-analysis?source_type={source_type}`。

### 9.4 站点影响力矩阵

矩阵数据来自 `source-analysis.sites.items[]`：

- 行：站点域名和站点名称。
- 列：平台端。
- 单元格：`platform_values[].display_value`，随 `metric=links|rate` 切换。

点击站点行可选交互：

1. 用该站点作为 `keyword` 重新查询矩阵。
2. 或跳转 AI 对话记录页，按问题/回答详情查看具体引用。

### 9.5 导出按钮

调用：

1. `GET /projects/{project_id}/source-analysis/export`
2. 带上当前筛选条件：`run_id`、`platform_codes`、`start_at`、`end_at`、`source_type`、`keyword`、`metric`。

当前返回 CSV 文件流。

### 9.6 引用率趋势

如原型展示引用率趋势：

1. `GET /projects/{project_id}/trends?metric_code=citation_rate`
2. 如需分平台线条，按 `platform_code` 分别请求。

## 10. 运行、采集、分析、报告闭环

该流程支撑“监测中”“数据生成中”“下载报告”等状态。

### 10.1 手动发起一次监测

推荐调用顺序：

1. `GET /projects/{project_id}/monitor-setup`
   - 确认有目标品牌、启用问题、默认平台。
2. `POST /runs`
   - 默认 `collection_source=official`，`platform_codes` 为官方码或项目默认。
   - 第三方模力指数：传 `collection_source=molizhishu` 与 `molizhishu_*` 平台；勿混用官方码。
3. `GET /runs/{run_id}` 轮询进度。
4. `GET /runs/{run_id}/query-tasks` 查看任务明细。
5. `GET /runs/{run_id}/answers` 查看答案粒度数据。
6. 如果运行终态后需要手工重跑分析：`POST /runs/{run_id}/analyze`。
7. `GET /projects/{project_id}/dashboard/overview?run_id={run_id}` 刷新数据页。

### 10.2 取消与重试

| 原型动作 | 接口顺序 |
| --- | --- |
| 取消运行 | `POST /runs/{run_id}/cancel`（模力指数 Run 可能产生 provider 侧计费，见 API 文档 §11.4） |
| 重试失败任务 | `POST /runs/{run_id}/retry-failed` |
| 查看任务 | `GET /runs/{run_id}/query-tasks` 或 `GET /runs/{run_id}/tasks` |

### 10.3 报告

| 原型动作 | 接口顺序 |
| --- | --- |
| 生成报告 | `POST /runs/{run_id}/reports` |
| 查询报告列表 | `GET /runs/{run_id}/reports` |
| 查询报告状态 | `GET /reports/{report_id}` |
| 下载报告 | `GET /reports/{report_id}/download` |
| 删除报告 | `DELETE /reports/{report_id}` |

## 11. 调度能力

原型 6 页没有单独调度配置页，但后端已具备调度接口，可用于后续设置页。

| 功能 | 接口 |
| --- | --- |
| 查询项目调度 | `GET /projects/{project_id}/schedules` |
| 创建调度 | `POST /projects/{project_id}/schedules` |
| 获取调度 | `GET /schedules/{schedule_id}` |
| 更新调度 | `PUT /schedules/{schedule_id}` |
| 删除调度 | `DELETE /schedules/{schedule_id}` |
| 启用调度 | `POST /schedules/{schedule_id}/enable` |
| 停用调度 | `POST /schedules/{schedule_id}/disable` |
| 立即触发调度 | `POST /schedules/{schedule_id}/trigger` |

## 12. 推荐前端调用原则

- 页面首屏优先调用页面级聚合接口，不要用底层列表接口在前端做 N+1 聚合。
- 配置编辑优先使用 `GET/PUT /monitor-setup` 整体回填和保存。
- AI 生成结果只作为候选，必须经用户确认后再保存。
- 数据页统一使用 `run_id`、`platform_codes`、`start_at`、`end_at` 作为筛选状态。
- 趋势图统一使用 `/trends`，平台级品牌可见度使用 `brand_visibility`；传 `brand_id` 时使用品牌维度指标编码。
- 文件下载接口不是统一 JSON；前端按 Blob / 文件流处理。
- 比率和平均排名都是 decimal 字符串或 `null`；无分母时显示 `--`。

## 13. 一句话版本

这份文档现在不再是缺口清单，而是原型 6 页的接口调用手册：页面主数据走聚合接口，按钮动作走项目、配置、运行、导出和报告接口，字段契约继续查 `docs/API接口文档.md`。
