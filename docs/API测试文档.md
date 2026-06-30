# API 测试文档

本文档根据当前后端代码整理，覆盖 `backend/app/api/router.py`、`backend/app/main.py` 与 `backend/app/geo_monitoring/api/` 下已实现接口。

> 更新日期：2026-06-27
> 原型页面按钮与调用顺序见 `docs/原型功能_API映射整合精简版.md`；接口字段契约见 `docs/API接口文档.md`。

## 1. 通用约定

### 1.1 服务地址与前缀

- 默认服务地址：`http://127.0.0.1:8000`
- 全局 API 前缀：`/api`
- AI 应用监测主前缀：`/api/geo-monitoring`
- 兼容前缀：`/api/v1/geo-monitoring`

除健康检查外，本文档默认使用主前缀 `/api/geo-monitoring`。兼容前缀下会挂载同一组业务接口，例如：

```text
GET /api/geo-monitoring/projects
GET /api/v1/geo-monitoring/projects
```

### 1.2 鉴权与请求头

当前已实现路由未配置接口鉴权依赖，测试时不需要传 `Authorization` 或 API Key。

建议统一请求头：

```http
Content-Type: application/json
Accept: application/json
X-Request-ID: 可选，自定义请求 ID
```

后端会在响应头返回：

- `X-Request-ID`
- `X-Response-Time-Ms`

### 1.3 统一 JSON 响应

大多数接口返回统一结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页接口的 `data` 结构：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 0,
    "page": 1,
    "page_size": 10
  }
}
```

失败响应通常为：

```json
{
  "code": 40400,
  "message": "监测项目不存在",
  "data": null
}
```

参数校验失败固定为：

```json
{
  "code": 422,
  "message": "参数校验失败",
  "data": []
}
```

### 1.4 通用验证标准

接口验证成功：

- HTTP 状态码为 `200`，或报告下载接口为 `200` 且返回文件内容。
- JSON 接口响应体 `code = 0`。
- `message = "success"`。
- `data` 中关键字段与请求入参或业务预期一致。
- 创建、更新、删除类接口可通过后续查询接口验证数据状态。

接口验证失败：

- HTTP 状态码为 `4xx` / `5xx`，或 JSON 响应体 `code != 0`。
- 参数校验错误返回 `code = 422`。
- 业务冲突、资源不存在、状态不允许等返回对应业务错误码。
- 响应结构缺少 `code`、`message`、`data`，或字段类型不符合预期。

## 2. 状态枚举与常用字段

### 2.1 项目状态

| 字段 | 可选值 |
| --- | --- |
| `ProjectStatus` | `active`、`disabled`、`archived` |

### 2.2 品牌状态与类型

| 字段 | 可选值 |
| --- | --- |
| `BrandType` | `target`、`competitor`、`candidate` |
| `EntityStatus` | `active`、`disabled` |
| `AliasMatchMode` | `exact`、`contains`、`context` |

### 2.3 提示词集状态

| 字段 | 可选值 |
| --- | --- |
| `PromptSetStatus` | `draft`、`active`、`archived` |

### 2.4 运行与任务状态

| 字段 | 可选值 |
| --- | --- |
| `RunStatus` | `pending`、`collecting`、`analyzing`、`reporting`、`completed`、`partial_success`、`failed`、`cancelled` |
| `QueryTaskStatus` | `pending`、`queued`、`running`、`success`、`failed`、`cancelled` |

### 2.5 调度策略

| 字段 | 可选值 |
| --- | --- |
| `MisfirePolicy` | `fire_once`、`ignore` |

## 3. 基础探针接口

### 3.1 全局健康检查

| 项目 | 内容 |
| --- | --- |
| 用途 | 检查后端应用进程是否可响应 |
| 方法 | `GET` |
| 路径 | `/api/health` |
| 入参 | 无 |
| 出参 | `status`、`app`、`env` |

验证成功：

- HTTP `200`。
- `code = 0`。
- `data.status = "ok"`。

验证失败：

- 服务无法连接、HTTP 非 `200`、或 `data.status` 不是 `ok`。

### 3.2 全局就绪检查

| 项目 | 内容 |
| --- | --- |
| 用途 | 检查数据库、Redis 等依赖是否就绪 |
| 方法 | `GET` |
| 路径 | `/api/ready` |
| 入参 | 无 |
| 出参 | `status`、`database`、`redis` |

验证成功：

- HTTP `200`。
- `code = 0`。
- `data.status = "ready"`。
- `data.database.ok = true` 且 `data.redis.ok = true`。

验证失败：

- 依赖连接失败。
- `data.status = "not_ready"`。
- HTTP `500` 或响应体 `code != 0`。

### 3.3 监测服务健康检查

| 项目 | 内容 |
| --- | --- |
| 用途 | 检查 AI 应用监测模块是否可响应 |
| 方法 | `GET` |
| 路径 | `/api/geo-monitoring/health` |
| 入参 | 无 |
| 出参 | `status`、`app`、`env` |

验证成功：

- HTTP `200`。
- `code = 0`。
- `data.status = "ok"`。

验证失败：

- 服务无法连接、HTTP 非 `200`、或 `data.status` 不是 `ok`。

### 3.4 监测服务就绪检查

| 项目 | 内容 |
| --- | --- |
| 用途 | 检查监测模块依赖是否就绪，启用 Nacos 时额外检查 Nacos |
| 方法 | `GET` |
| 路径 | `/api/geo-monitoring/ready` |
| 入参 | 无 |
| 出参 | `status`、`database`、`redis`、可选 `nacos` |

验证成功：

- HTTP `200`。
- `code = 0`。
- `data.status = "ready"`。

验证失败：

- HTTP `503` 且 `data.status = "not_ready"`。
- 任一依赖 `ok = false`。

## 4. 项目模块

### 4.1 项目字段

创建项目请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_name` | string | 是 | 项目名称，最大 100 |
| `industry` | string | 否 | 行业，默认 `文旅演艺`，最大 100 |
| `description` | string/null | 否 | 项目描述 |
| `timezone` | string | 否 | 时区，默认 `Asia/Shanghai`，最大 64 |
| `official_domain` | string/null | 否 | 官方域名，最大 255 |
| `report_title` | string/null | 否 | 报告标题，最大 255 |
| `report_subtitle` | string/null | 否 | 报告副标题，最大 500 |

更新项目请求体均为可选字段，额外支持：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | enum | `active`、`disabled`、`archived` |

项目响应字段：

`id`、`project_name`、`industry`、`description`、`timezone`、`status`、`official_domain`、`report_title`、`report_subtitle`、`default_platform_codes`（项目默认监测平台，字符串数组）、`created_at`、`updated_at`。

### 4.2 项目接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询项目 | `GET` | `/api/geo-monitoring/projects` | Query：`page` 默认 1，`page_size` 默认 10 且 1-100，`project_name`，`status` | 分页 `ProjectOut[]` | `code=0`，`data.items` 为数组，分页字段正确 | `status` 非枚举值返回 `422` |
| 创建项目 | `POST` | `/api/geo-monitoring/projects` | Body：`ProjectCreate` | `ProjectOut` | 返回新 `id`，字段与请求一致，默认 `status=active` | 必填字段为空或超长返回 `422` |
| 一步创建项目并保存监测设置 | `POST` | `/api/geo-monitoring/projects:setup` | Body：`project`（ProjectCreate）、`monitor_setup`（MonitorSetupSave）、`run_after_create` 默认 false | `{ project, monitor_setup, run? }` | 项目与监测配置同事务落库；`run_after_create=true` 且已激活问题集时返回 `run` | 监测设置校验失败（如 `40025`）时项目不会创建；`run_after_create=true` 需 `activate_prompt_set=true` 且有问题，且平台须兼容默认 official 采集源（`40055`/`40901`/`40031`），否则同事务回滚 |
| 创建向导草稿 | `POST` | `/api/geo-monitoring/project-drafts` | Body：`draft_key?`、`current_step`（1–3）、`project`、`monitor_setup` | `ProjectDraftOut` | 保存未完成向导数据 | `draft_key` 供客户端恢复 |
| 按 key 更新或创建草稿 | `PUT` | `/api/geo-monitoring/project-drafts` | Body 同创建；`draft_key` 必填 | `ProjectDraftOut` | upsert（与 `current` 等价） | `draft_key` 为空 `422` |
| 更新向导草稿 | `PUT` | `/api/geo-monitoring/project-drafts/{draft_id}` | Query：`draft_key` 必填；Body 可选字段 | `ProjectDraftOut` | 与已有草稿递归深度合并 | `40400` 不存在或 key 不匹配 |
| 获取向导草稿 | `GET` | `/api/geo-monitoring/project-drafts/{draft_id}` | Query：`draft_key` 必填 | `ProjectDraftOut` | 按 ID + key 恢复 | `40400` |
| 获取最新向导草稿 | `GET` | `/api/geo-monitoring/project-drafts/current` | Query：`draft_key` | `ProjectDraftOut` | 按会话 key 取最新一条 | `40400` |
| 按 key 更新或创建草稿 | `PUT` | `/api/geo-monitoring/project-drafts/current` | Body 同创建；`draft_key` 必填 | `ProjectDraftOut` | upsert | `draft_key` 为空 `422` |
| 获取项目 | `GET` | `/api/geo-monitoring/projects/{project_id}` | Path：`project_id >= 1` | `ProjectOut` | `data.id = project_id` | 不存在返回 `code=40400`、`message=监测项目不存在` |
| 更新项目 | `PUT` | `/api/geo-monitoring/projects/{project_id}` | Path：`project_id >= 1`；Body：`ProjectUpdate` | `ProjectOut` | 返回字段已更新，`updated_at` 变化 | 不存在返回 `40400`；状态非法返回 `422` |
| 删除项目 | `DELETE` | `/api/geo-monitoring/projects/{project_id}` | Path：`project_id >= 1` | `{ "id": project_id }` | 返回删除 ID，后续获取返回不存在 | 项目已有监测运行引用时 HTTP `409`、`code=40903` |
| 项目轻量列表（兼容/可选） | `GET` | `/api/geo-monitoring/projects/options` | — | `{ "items": ProjectOption[] }` | `code=0`；每项含 `id/project_name/status/monitoring_paused`；新版首页首屏不依赖该接口 | — |
| 首页项目卡片概览 | `GET` | `/api/geo-monitoring/projects/overview` | Query：`page`、`page_size`、`project_name`、`status` | 分页项目卡片摘要 | 返回所有项目卡片；含 `brand_words/competitors/platform_endpoints/homepage_badges/last_updated_at`；`platform_endpoints` 与 `GET /platform-endpoints` 口径一致；`platform_count` 按 `base_platform` 去重 | — |
| 暂停监测 | `POST` | `/api/geo-monitoring/projects/{project_id}/pause` | Path：`project_id` | `ProjectOut` | `monitoring_paused=true` | 不存在 `40400` |
| 恢复监测 | `POST` | `/api/geo-monitoring/projects/{project_id}/resume` | Path：`project_id` | `ProjectOut` | `monitoring_paused=false` | 不存在 `40400` |
| 删除前检查 | `GET` | `/api/geo-monitoring/projects/{project_id}/delete-check` | Path：`project_id` | `run_count/report_count/schedule_count/can_delete/blocking_reasons` | 有运行则 `can_delete=false`；`blocking_reasons` 仅含运行阻塞 | 不存在 `40400` |
| 暂停后调度触发 | `POST` | `/api/geo-monitoring/schedules/{schedule_id}/trigger` | Path：`schedule_id`（项目已暂停） | — | — | `code=40054`，消息含「暂停」 |
| 暂停后创建运行 | `POST` | `/api/geo-monitoring/runs` | Body：`project_id`（已暂停项目） | — | — | `code=40054`，消息含「暂停」 |

**新版首页项目卡片增强验收（Task P1-5 已实现）：**

- `GET /projects/overview` 首屏返回分页项目列表，不要求先调用 `/projects/options`。
- `items[]` 含 `brand_words[]`，可直接渲染“品牌词”标签。
- `items[]` 含 `competitors[]`（`brand_id`、`brand_name`），可直接渲染“竞品”标签。
- `items[]` 含 `platform_endpoints[]`，与 `GET /platform-endpoints` 解析口径一致。
- `items[]` 含 `homepage_badges[]`，输出 `监测中` / `已暂停`；`当前` 标签由前端本地状态处理，不验后端。
- `last_updated_at` 优先取最近 run 的 `completed_at`，否则回退 `updated_at`。
- 首页按钮动作按“进入 / 编辑配置 / 暂停或监测 / 删除”四条调用链分别验证。

创建示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/projects" \
  -H "Content-Type: application/json" \
  -d '{"project_name":"杭州宋城文旅监测","industry":"文旅演艺","timezone":"Asia/Shanghai"}'
```

专项 pytest：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_project_setup_api.py --basetemp .pytest-tmp
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_project_drafts_api.py
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_project_overview_api.py
```

## 5. 品牌与别名模块

### 5.1 品牌字段

创建品牌请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `brand_name` | string | 是 | 品牌名称，最大 255 |
| `brand_type` | enum | 否 | 默认 `competitor` |
| `official_domain` | string/null | 否 | 官方域名 |
| `description` | string/null | 否 | 描述 |
| `status` | enum | 否 | 默认 `active` |

品牌响应字段：

`id`、`project_id`、`brand_name`、`brand_type`、`official_domain`、`description`、`status`、`created_at`、`updated_at`。

品牌别名创建请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `alias_name` | string | 是 | 别名，最大 255 |
| `match_mode` | enum | 否 | 默认 `contains` |
| `is_ambiguous` | boolean | 否 | 默认 `false` |
| `context_keywords` | string[] | 否 | 上下文关键词，自动去重并过滤空字符串 |
| `enabled` | boolean | 否 | 默认 `true` |

别名响应字段：

`id`、`brand_id`、`alias_name`、`match_mode`、`is_ambiguous`、`context_keywords`、`enabled`、`created_at`、`updated_at`。

### 5.2 品牌接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询项目品牌 | `GET` | `/api/geo-monitoring/projects/{project_id}/brands` | Path：`project_id`；Query：`page`、`page_size`、`brand_name`、`brand_type`、`status` | 分页 `BrandOut[]` | `code=0`，品牌均属于该项目 | 项目不存在 `40400`；项目未启用 `40001` |
| 创建品牌 | `POST` | `/api/geo-monitoring/projects/{project_id}/brands` | Body：`BrandCreate` | `BrandOut` | 返回新 `id` 和 `project_id` | 同项目品牌名重复 `40012`；目标品牌重复 `40010` |
| 获取品牌 | `GET` | `/api/geo-monitoring/brands/{brand_id}` | Path：`brand_id` | `BrandOut` | `data.id = brand_id` | 不存在 `40400` |
| 更新品牌 | `PUT` | `/api/geo-monitoring/brands/{brand_id}` | Body：`BrandUpdate` | `BrandOut` | 返回字段已更新 | 重名 `40012`；目标品牌重复 `40010` |
| 删除品牌 | `DELETE` | `/api/geo-monitoring/brands/{brand_id}` | Path：`brand_id` | `{ "id": brand_id }` | 返回删除 ID，后续查询不存在 | 品牌已被答案引用 HTTP `409`、`code=40905` |

### 5.3 品牌别名接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询品牌别名 | `GET` | `/api/geo-monitoring/brands/{brand_id}/aliases` | Path：`brand_id`；Query：`page`、`page_size` | 分页 `BrandAliasOut[]` | `code=0`，别名均属于该品牌 | 品牌不存在 `40400` |
| 创建品牌别名 | `POST` | `/api/geo-monitoring/brands/{brand_id}/aliases` | Body：`BrandAliasCreate` | `BrandAliasOut` | 返回新 `id` 和 `brand_id` | 同品牌别名重复 `40011` |
| 更新品牌别名 | `PUT` | `/api/geo-monitoring/brand-aliases/{alias_id}` | Body：`BrandAliasUpdate` | `BrandAliasOut` | 返回字段已更新 | 别名不存在 `40400`；重复 `40011` |
| 删除品牌别名 | `DELETE` | `/api/geo-monitoring/brand-aliases/{alias_id}` | Path：`alias_id` | `{ "id": alias_id }` | 返回删除 ID，后续列表不再出现 | 别名不存在 `40400` |

### 5.4 核心词、Prompt 词库与监测设置

品牌诊断/监控向导相关接口：支持一次性配置目标品牌、竞品、核心词、AI 问题与监测平台。

#### 5.4.1 核心词字段

创建核心词请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `keyword` | string | 是 | 核心词，最大 100，同项目内不能重复 |
| `description` | string/null | 否 | 说明 |
| `sort_order` | integer | 否 | 排序，默认 0 |
| `enabled` | boolean | 否 | 默认 `true` |

核心词响应字段：

`id`、`project_id`、`keyword`、`description`、`sort_order`、`enabled`、`created_at`、`updated_at`。

#### 5.4.2 Prompt 词库字段

词库为全局只读模板（迁移种子数据预置 3 条），响应字段：

`id`、`prompt_code`、`prompt_text`、`prompt_type`、`industry`、`scene_tag`、`default_core_keyword`、`enabled`、`created_at`、`updated_at`。

预置编码示例：`LIB_RECOMMEND_001`、`LIB_COMPARE_001`、`LIB_VISIBILITY_001`。

#### 5.4.3 监测设置字段

保存监测设置请求体 `MonitorSetupSave`：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `brand` | object | 是 | 目标品牌：`brand_name`、`official_domain`、`description`、`brand_words`（写入品牌别名） |
| `competitors` | array | 否 | 竞品列表，每项含 `brand_name`、`competitor_words`；空数组表示不预配置竞品 |
| `core_keywords` | array | 否 | 核心词列表，每项含 `keyword`、`description`、`sort_order`、`enabled` |
| `ai_questions` | array | 否 | AI 问题，每项可填 `core_keyword`、`prompt_text`；或引用词库 `library_prompt_code`；可选 `prompt_type`、`prompt_code` |
| `selected_platform_codes` | string[] | 否 | 用户选择的监测平台，须为已启用平台 |
| `activate_prompt_set` | boolean | 否 | 默认 `false`；为 `true` 时保存后激活草稿问题集 |

获取监测设置响应 `data` 额外字段：

| 字段 | 说明 |
| --- | --- |
| `brand` | 目标品牌及 `brand_words`，未配置时为 `null` |
| `competitors` | 已配置竞品及 `competitor_words` |
| `core_keywords` | 项目核心词列表 |
| `ai_questions` | 草稿或激活问题集中的问题，含 `prompt_type`（自动推断）、`core_keyword`、`from_library` |
| `available_platforms` | 当前可用平台摘要 |
| `selected_platform_codes` | 项目已保存的默认平台 |
| `draft_prompt_set_id` / `active_prompt_set_id` | 草稿/激活问题集 ID |

`prompt_type` 自动推断规则（未显式传入时）：

| 类型 | 触发条件（摘要） |
| --- | --- |
| `comparison` | 含「对比」「比较」「哪个更好」等 |
| `recommendation` | 含「推荐」「有哪些」等 |
| `brand_visibility` | 问题文本含目标品牌名或核心词 |
| `generic` | 其他 |

#### 5.4.4 核心词接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询项目核心词 | `GET` | `/api/geo-monitoring/projects/{project_id}/core-keywords` | Path：`project_id`；Query：`page` 默认 1，`page_size` 默认 100 且 1-500，`enabled` | 分页 `CoreKeywordOut[]` | `code=0` | 项目不存在 `40400`；项目未启用 `40001` |
| 创建核心词 | `POST` | `/api/geo-monitoring/projects/{project_id}/core-keywords` | Body：`CoreKeywordCreate` | `CoreKeywordOut` | 返回新 `id` | 同项目核心词重复 `40024` |
| 更新核心词 | `PUT` | `/api/geo-monitoring/core-keywords/{keyword_id}` | Body：`CoreKeywordUpdate` | `CoreKeywordOut` | 字段已更新 | 不存在 `40400`；重复 `40024` |
| 删除核心词 | `DELETE` | `/api/geo-monitoring/core-keywords/{keyword_id}` | Path：`keyword_id` | `{ "id": keyword_id }` | 软删除成功 | 不存在 `40400` |

#### 5.4.5 Prompt 词库接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询 Prompt 词库 | `GET` | `/api/geo-monitoring/prompt-library` | Query：`page`、`page_size` 默认 100 且 1-500，`industry` | 分页 `PromptLibraryOut[]` | `code=0`，至少返回种子模板 | `page_size` 超限 `422` |

#### 5.4.6 平台端元数据与基础字典接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 获取平台端元数据分组 | `GET` | `/api/geo-monitoring/platform-endpoints` | Query：`enabled` 可选 | `groups[]`，含 `base_platform`、`endpoints[]` | `code=0`；Aidso 端码解析为 `web`/`app`；同组内 `web` 排在 `app` 前 | 无 |
| 获取 Prompt 意图类型字典 | `GET` | `/api/geo-monitoring/prompt-types` | 无 | `items[]` 共 5 项，含 `compatible_values` | `code=0`；含 `comparison`、`recommendation` 等兼容值 | 无 |
| 获取信源类型展示字典 | `GET` | `/api/geo-monitoring/source-types` | 无 | `items[]` 与 `storage_mappings[]` | `code=0`；六类存储值均可映射到展示字典 | 无 |
| 获取行业基准参照 | `GET` | `/api/geo-monitoring/benchmarks` | Query：可选 `industry` | 列表或单行业 `metrics` + `market_position_thresholds` | `code=0`；含「文旅演艺」；`sample_source=static_config` | 未知行业 `40400` |

自动化测试文件：`backend/tests/geo_monitoring/test_metadata_api.py`、`backend/tests/geo_monitoring/test_benchmarks_api.py`

覆盖场景：Aidso 端码分组、`extra_config` 覆盖、`enabled` 过滤、平台数超过 500 不截断、v1 兼容前缀可访问、行业基准列表与单行业查询。

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_metadata_api.py backend/tests/geo_monitoring/test_benchmarks_api.py
```

#### 5.4.7 AI 生成辅助接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| AI 生成品牌词（创建向导推荐） | `POST` | `/api/geo-monitoring/ai/brand-words:generate` | Body：`brand_name`（必填）、`category`、`official_domain`、`limit` 默认 10 | `{ "brand_words": string[] }` | `code=0`；必含 `brand_name`；去重；**不落库** | 品牌名为空 `422` |
| AI 生成竞品（创建向导推荐） | `POST` | `/api/geo-monitoring/ai/competitors:generate` | Body：`brand_name`（必填）、`category`、`region`、`limit` 默认 5 | `{ "competitors": [{ brand_name, competitor_words[], official_domain? }] }` | `code=0`；排除目标品牌自身；**不落库** | 品牌名为空 `422` |
| AI 生成监测问题（创建向导推荐） | `POST` | `/api/geo-monitoring/ai/questions:generate` | Body：`brand_name`（必填）、`category`、`region`、`core_keywords[]`、`competitors[]`、`limit` 默认 10 | `{ "questions": [{ prompt_text, prompt_type, core_keyword? }] }` | 五类意图模板；按 `limit` 截断；**不落库** | 品牌名为空 `422` |
| AI 生成品牌词（项目域兼容） | `POST` | `/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate` | 同上 | 同上 | `code=0` | 项目不存在 `40400`；品牌名为空 `422` |
| AI 生成竞品（项目域兼容） | `POST` | `/api/geo-monitoring/projects/{project_id}/ai/competitors:generate` | 同上 | 同上 | `code=0` | 项目不存在 `40400` |
| AI 生成监测问题（项目域兼容） | `POST` | `/api/geo-monitoring/projects/{project_id}/ai/questions:generate` | 同上 | 同上 | 五类意图模板；按 `limit` 截断 | 项目不存在 `40400` |

v1 兼容：上述路径均可替换前缀为 `/api/v1/geo-monitoring/...`。

自动化测试文件：`backend/tests/geo_monitoring/test_ai_generation_api.py`

覆盖场景：宋城/杭州旅游示例、空品牌名校验、**无 project_id 全局路径**、v1 全局路径、全局生成不创建项目、项目域生成不落库、项目不存在 `40400`。

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_ai_generation_api.py backend/tests/geo_monitoring/test_project_setup_api.py backend/tests/geo_monitoring/test_project_drafts_api.py
```

#### 5.4.8 监测设置接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 获取监测设置 | `GET` | `/api/geo-monitoring/projects/{project_id}/monitor-setup` | Path：`project_id` | 见 §5.4.3 响应结构 | `code=0` | 项目不存在 `40400`；项目未启用 `40001` |
| 保存监测设置 | `PUT` | `/api/geo-monitoring/projects/{project_id}/monitor-setup` | Body：`MonitorSetupSave` | 同 GET 响应结构 | 品牌/竞品/核心词/问题/平台一并落库；可选激活问题集 | 品牌为空 `40028`；平台不可用 `40025`；核心词不存在 `40027`；AI 问题文本为空 `40026`；词库编码不存在 `40400` |

保存监测设置示例：

```bash
curl -X PUT "http://127.0.0.1:8000/api/geo-monitoring/projects/1/monitor-setup" \
  -H "Content-Type: application/json" \
  -d '{
    "brand": {
      "brand_name": "杭州宋城",
      "official_domain": "https://www.example.com",
      "description": "第三方检测机构",
      "brand_words": ["宋城", "SEP"]
    },
    "competitors": [
      {"brand_name": "竞品A", "competitor_words": ["竞品A"]}
    ],
    "core_keywords": [
      {"keyword": "环境检测", "sort_order": 1}
    ],
    "ai_questions": [
      {"core_keyword": "环境检测", "prompt_text": "推荐国内靠谱的环境检测机构有哪些？"},
      {"library_prompt_code": "LIB_RECOMMEND_001", "core_keyword": "环境检测"}
    ],
    "selected_platform_codes": ["qwen", "deepseek"],
    "activate_prompt_set": true
  }'
```

## 6. 提示词集与提示词模块

### 6.1 提示词集字段

创建提示词集请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `set_name` | string | 是 | 名称，最大 100 |
| `version_no` | string | 是 | 版本号，最大 50，同项目内不能重复 |

更新提示词集请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `set_name` | string | 否 | 仅草稿状态允许更新 |

提示词集响应字段：

`id`、`project_id`、`set_name`、`version_no`、`status`、`prompt_count`、`checksum`、`activated_at`、`created_at`、`updated_at`。

### 6.2 提示词字段

创建提示词请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `prompt_code` | string | 是 | 编码，最大 64，同提示词集内不能重复 |
| `prompt_text` | string | 是 | 提示词正文 |
| `prompt_type` | string | 否 | 默认 `generic`，最大 50 |
| `scene_tag` | string/null | 否 | 场景标签，最大 100 |
| `contains_brand` | boolean | 否 | 默认 `false` |
| `core_keyword_id` | integer/null | 否 | 关联项目核心词 ID |
| `enabled` | boolean | 否 | 默认 `true` |
| `sort_order` | integer | 否 | 默认 0 |

常见 `prompt_type` 值：`generic`、`recommendation`、`comparison`、`brand_visibility`。

提示词响应字段：

`id`、`prompt_set_id`、`prompt_code`、`prompt_text`、`prompt_type`、`scene_tag`、`contains_brand`、`core_keyword_id`、`enabled`、`sort_order`、`content_hash`、`created_at`、`updated_at`。

### 6.3 提示词集接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询提示词集 | `GET` | `/api/geo-monitoring/projects/{project_id}/prompt-sets` | Path：`project_id`；Query：`page`、`page_size`、`status` | 分页 `PromptSetOut[]` | `code=0`，均属于该项目 | 项目不存在 `40400`；项目未启用 `40001` |
| 创建提示词集 | `POST` | `/api/geo-monitoring/projects/{project_id}/prompt-sets` | Body：`PromptSetCreate` | `PromptSetOut` | 默认 `status=draft`，`prompt_count=0` | 版本重复 `40023` |
| 获取提示词集 | `GET` | `/api/geo-monitoring/prompt-sets/{prompt_set_id}` | Path：`prompt_set_id` | `PromptSetOut` | `data.id = prompt_set_id` | 不存在 `40400` |
| 更新提示词集 | `PUT` | `/api/geo-monitoring/prompt-sets/{prompt_set_id}` | Body：`PromptSetUpdate` | `PromptSetOut` | 草稿集名称更新成功 | 非草稿返回 `40020` |
| 删除提示词集 | `DELETE` | `/api/geo-monitoring/prompt-sets/{prompt_set_id}` | Path：`prompt_set_id` | `{ "id": prompt_set_id }` | 草稿集删除成功 | 已被运行引用 HTTP `409`、`40906`；非草稿 `40020` |
| 激活提示词集 | `POST` | `/api/geo-monitoring/prompt-sets/{prompt_set_id}/activate` | Path：`prompt_set_id` | `PromptSetOut` | `status=active`，`activated_at` 非空，`checksum` 非空 | 空提示词集 `40022`；非草稿 `40020` |

### 6.4 提示词接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询提示词 | `GET` | `/api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts` | Path：`prompt_set_id`；Query：`page` 默认 1，`page_size` 默认 100 且 1-500 | 分页 `PromptOut[]` | `code=0`，均属于该提示词集 | 提示词集不存在 `40400` |
| 创建提示词 | `POST` | `/api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts` | Body：`PromptCreate` | `PromptOut` | 返回新 `id`，`content_hash` 非空 | 非草稿集 `40020`；编码重复 `40021` |
| 更新提示词 | `PUT` | `/api/geo-monitoring/prompts/{prompt_id}` | Body：`PromptUpdate` | `PromptOut` | 字段更新；改正文时 `content_hash` 变化 | 非草稿集 `40020`；编码重复 `40021` |
| 删除提示词 | `DELETE` | `/api/geo-monitoring/prompts/{prompt_id}` | Path：`prompt_id` | `{ "id": prompt_id }` | 删除后列表不再出现 | 已被查询任务引用 HTTP `409`、`40907` |

## 7. AI 平台模块

### 7.1 平台字段

平台更新请求体均为可选字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform_name` | string | 平台名称，最大 100 |
| `adapter_type` | string | 适配器类型，最大 50 |
| `base_url` | string/null | 请求地址，最大 500 |
| `model_name` | string/null | 模型名，最大 255 |
| `search_enabled` | boolean | 是否启用搜索 |
| `citation_supported` | boolean | 是否支持引用 |
| `max_concurrency` | integer | 大于 0 |
| `timeout_seconds` | integer | 大于 0 |
| `enabled` | boolean | 是否启用 |
| `extra_config` | object/null | 扩展配置 |

平台响应字段：

`id`、`platform_code`、`platform_name`、`adapter_type`、`base_url`、`model_name`、`search_enabled`、`citation_supported`、`max_concurrency`、`timeout_seconds`、`enabled`、`extra_config`、`created_at`、`updated_at`。

### 7.2 平台接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询 AI 平台 | `GET` | `/api/geo-monitoring/platforms` | Query：`page`、`page_size`、`enabled` | 分页 `AIPlatformOut[]` | `code=0`，列表返回平台配置 | `page_size` 超限返回 `422` |
| 获取 AI 平台配置 | `GET` | `/api/geo-monitoring/platforms/{platform_code}` | Path：`platform_code`，1-32 字符 | `AIPlatformOut` | `data.platform_code` 等于路径参数 | 不存在 `40400` |
| 更新 AI 平台配置 | `PUT` | `/api/geo-monitoring/platforms/{platform_code}` | Body：`AIPlatformUpdate` | `AIPlatformOut` | 返回字段已更新 | 不存在 `40400`；并发数或超时小于等于 0 返回 `422` |

默认平台代码包括：`doubao`、`qwen`、`yuanbao`、`deepseek`、`kimi`。

## 8. 监测运行与任务模块

### 8.1 运行字段

创建运行请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | integer | 是 | 项目 ID，必须大于等于 1 |
| `prompt_set_id` | integer/null | 否 | 指定提示词集；不传则使用项目当前激活提示词集 |
| `collection_source` | string | 否 | 采集来源，默认 `official`；新建可选 `official` / `molizhishu` |
| `provider_mode_by_platform` | object | 否 | 模力指数平台模式映射 |
| `provider_screenshot` | integer | 否 | 模力指数截图策略，默认 `0`，仅 `0/1/2` |
| `region_code` | string/null | 否 | 模力指数区域编码 |
| `provider_callback_url` | string/null | 否 | 模力指数回调地址 |
| `platform_codes` | string[]/null | 否 | 指定平台代码；不传则使用项目 `default_platform_codes`；仍为空时使用全部已启用平台 |

**废弃字段：** `aidso_thinking_enabled_by_platform`、`collection_source=aidso` 在新建请求中返回 `422`。

运行响应字段：

`id`、`run_no`、`project_id`、`prompt_set_id`、`prompt_set_version`、`trigger_type`、`triggered_by`、`status`、`collection_status`、`analysis_status`、`report_status`、`collection_source`、`aidso_thinking_enabled_by_platform`（历史 Aidso 只读）、`provider_mode_by_platform`、`provider_screenshot`、`region_code`、`provider_callback_url`、`platform_codes`、`expected_query_count`、`total_tasks`、`succeeded_tasks`、`failed_tasks`、`cancelled_tasks`、`success_query_count`、`failed_query_count`、`valid_answer_count`、`data_completeness_rate`、`result_json`、`error_message`、`error_summary`、`started_at`、`completed_at`、`finished_at`、`created_at`、`updated_at`。

运行详情额外返回：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `progress_rate` | decimal/string | 已完成任务数占总任务数比例 |

任务响应字段：

`id`、`run_id`、`prompt_id`、`platform_code`、`idempotency_key`、`status`、`key_slot`、`retry_count`、`attempt_count`、`max_attempts`、`request_json`、`response_http_status`、`error_code`、`error_message`、`last_error_code`、`last_error_message`、`provider_request_id`、`latency_ms`、`queued_at`、`started_at`、`completed_at`、`finished_at`、`created_at`、`updated_at`。

### 8.2 运行接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询监测运行 | `GET` | `/api/geo-monitoring/runs` | Query：`page`、`page_size`、`project_id`、`status`、`created_after`、`created_before` | 分页 `MonitorRunOut[]` | `code=0`，筛选条件生效 | 状态非法或时间格式非法返回 `422` |
| 创建监测运行 | `POST` | `/api/geo-monitoring/runs` | Body：`RunCreate` | `MonitorRunOut` | 返回新 `run_no`，`total_tasks = 可用提示词数 * 平台数`，状态进入 `collecting` 或后续终态；模力指数 run 持久化 `provider_*` 字段 | 项目无激活提示词集 `40030`；无可用提示词 HTTP `409`、`40901`；AI 平台不可用 `40031`；无可用平台 HTTP `409`、`40902`；非法 mode/废弃 Aidso 字段 `422` |
| 获取运行详情 | `GET` | `/api/geo-monitoring/runs/{run_id}` | Path：`run_id` | `MonitorRunOut + progress_rate` | `data.id = run_id`，任务统计刷新 | 不存在 `40400` |
| 取消运行 | `POST` | `/api/geo-monitoring/runs/{run_id}/cancel` | Path：`run_id` | `MonitorRunOut` | 未终态运行返回 `status=cancelled`；已终态运行返回当前终态；模力指数运行本地先落库，后台调度 provider stop | 不存在 `40400` |
| 重试失败任务 | `POST` | `/api/geo-monitoring/runs/{run_id}/retry-failed` | Path：`run_id` | `MonitorRunOut + retried_count` | `retried_count` 等于重置的失败任务数；有失败任务时状态回到 `collecting` | 已取消运行不可重试 `40040` |

### 8.3 查询任务接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询运行任务 | `GET` | `/api/geo-monitoring/runs/{run_id}/query-tasks` | Path：`run_id`；Query：`page`、`page_size` 默认 100 且 1-500、`status`、`platform_code` | 分页 `QueryTaskOut[]` | `code=0`，任务均属于该运行 | 运行不存在 `40400` |
| 分页查询运行任务别名 | `GET` | `/api/geo-monitoring/runs/{run_id}/tasks` | 同上 | 分页 `QueryTaskOut[]` | 与 `/query-tasks` 返回一致 | 同上 |

### 8.4 模力指数 Provider 回调

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 模力指数子任务完成回调 | `POST` | `/api/geo-monitoring/provider-callbacks/molizhishu` | Header：`X-Callback-Token` 或 Query：`token`；Body：模力指数子任务结果 JSON（含 `taskId`、`subTaskId`、`status`、`answerContent` 等） | `{ outcome, task_id, message }` | `code=0` 且 `outcome=processed` 写入答案；重复推送 `outcome=duplicate` 不重复入库 | token 无效 HTTP `401`；未配置 token HTTP `503`；找不到任务 `40401`；payload 非法 `42201` |

**pytest：**

```bash
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_molizhishu_callback.py
```

**说明：**

- 回调与轮询互为兜底；幂等键为本地 `QueryTask.id` 与 `Answer.task_id` 唯一约束。
- 兼容前缀：`/api/v1/geo-monitoring/provider-callbacks/molizhishu`。
- `MOLIZHISHU_CALLBACK_TOKEN` 须与部署环境一致；勿写入仓库或日志。

创建运行示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/runs" \
  -H "Content-Type: application/json" \
  -d '{"project_id":1,"platform_codes":["doubao","qwen"]}'
```

## 9. 调度模块

### 9.1 调度字段

创建调度请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `name` | string | 是 | 调度名称，最大 100，同项目内唯一 |
| `cron_expr` | string | 是 | crontab 表达式，最大 100 |
| `timezone` | string | 否 | 默认 `Asia/Shanghai` |
| `enabled` | boolean | 否 | 默认 `true` |
| `misfire_policy` | enum | 否 | 默认 `fire_once` |

调度响应字段：

`id`、`project_id`、`name`、`cron_expr`、`timezone`、`enabled`、`misfire_policy`、`next_run_at`、`last_run_at`、`created_at`、`updated_at`。

### 9.2 调度接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询项目调度 | `GET` | `/api/geo-monitoring/projects/{project_id}/schedules` | Path：`project_id`；Query：`page`、`page_size` | 分页 `ScheduleOut[]` | `code=0`，均属于该项目 | 项目不存在 `40400`；项目未启用 `40001` |
| 创建监测调度 | `POST` | `/api/geo-monitoring/projects/{project_id}/schedules` | Body：`ScheduleCreate` | `ScheduleOut` | 返回新 `id`，`next_run_at` 已计算 | cron 无效 `40050`；时区无效 `40051`；名称重复 HTTP `409`、`40904` |
| 获取监测调度 | `GET` | `/api/geo-monitoring/schedules/{schedule_id}` | Path：`schedule_id` | `ScheduleOut` | `data.id = schedule_id` | 不存在 `40400` |
| 更新监测调度 | `PUT` | `/api/geo-monitoring/schedules/{schedule_id}` | Body：`ScheduleUpdate` | `ScheduleOut` | 字段更新；修改 cron/时区后 `next_run_at` 重新计算 | cron 无效 `40050`；时区无效 `40051`；名称重复 `40904` |
| 删除监测调度 | `DELETE` | `/api/geo-monitoring/schedules/{schedule_id}` | Path：`schedule_id` | `{}` | 返回 `code=0`，后续查询不存在 | 不存在 `40400` |
| 启用监测调度 | `POST` | `/api/geo-monitoring/schedules/{schedule_id}/enable` | Path：`schedule_id` | `ScheduleOut` | `enabled=true`，`next_run_at` 已更新 | 不存在 `40400` |
| 停用监测调度 | `POST` | `/api/geo-monitoring/schedules/{schedule_id}/disable` | Path：`schedule_id` | `ScheduleOut` | `enabled=false` | 不存在 `40400` |
| 立即触发监测调度 | `POST` | `/api/geo-monitoring/schedules/{schedule_id}/trigger` | Path：`schedule_id` | `MonitorRunOut` | 返回新运行，`trigger_type=schedule`，`triggered_by=schedule_id` | 项目未启用 `40001`；无激活提示词集 `40030`；无平台或提示词时返回对应运行错误 |

## 10. 答案模块

### 10.1 答案字段

答案列表响应字段：

`id`、`task_id`、`platform_code`、`prompt_id`、`raw_text`、`normalized_text`、`model_name`、`prompt_tokens`、`completion_tokens`、`total_tokens`、`latency_ms`、`collected_at`、`created_at`、`updated_at`。

答案详情额外返回：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `prompt_text` | string | 关联问题文本 |
| `prompt_type` | string | 问题类型 |
| `reasoning_text` | string/null | 从 `raw_response_json` 提取的思考过程 |
| `search_keywords` | string[] | 从 `raw_response_json` 提取的搜索关键词 |
| `raw_response_safe` | object/null | 白名单原始响应安全子集（不含 cookie/token/正文等敏感字段）；模力指数采集额外暴露 `status`、`answerContent`（截断）、`citationList`/`referenceList` 标题与 URL、`reasoningProcess.content`（截断）、`recommendedQuestions`、`pageScreenshot`、`amount` |
| `citations` | array | 引用来源，字段包括 `citation_no`、`title`、`url`、`domain`、`source_type`、`quoted_text`；模力指数优先 `citationList`，为空时回退 `referenceList.summary` → `quoted_text` |
| `brand_results` | array | 品牌识别结果，字段包括 `brand_id`、`is_mentioned`、`mention_count`、`first_position`、`sentiment`、`context_json`；本地规则匹配为准，模力指数 provider 品牌字段仅写入 `context_json.provider_*` |

### 10.2 答案接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询运行答案 | `GET` | `/api/geo-monitoring/runs/{run_id}/answers` | Path：`run_id`；Query：`page`、`page_size` | 分页 `AnswerRead[]` | `code=0`，答案均来自该运行 | 运行不存在 `40400` |
| 获取答案详情 | `GET` | `/api/geo-monitoring/answers/{answer_id}` | Path：`answer_id` | `AnswerDetailRead` | 含 `prompt_text`、`reasoning_text`、`search_keywords`、`citations`、`brand_results` | 答案不存在 `40400` |

## 11. 分析与 Agent 审计模块

### 11.1 分析接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 手工触发或重跑分析 | `POST` | `/api/geo-monitoring/runs/{run_id}/analyze` | Path：`run_id` | `run_id`、`analysis_status`、`skip_reason`、`run_analysis_status` | 运行已处于终态时返回 `code=0`，`analysis_status` 表示分析结果 | 采集未完成 HTTP `409`、`code=40910`；运行不存在 `40400`；Agent LLM 配置或调用异常可能返回 `500` |
| 获取运行平台指标与洞察 | `GET` | `/api/geo-monitoring/runs/{run_id}/analysis` | Path：`run_id` | `run_id`、`analysis_status`、`platforms[]` | `code=0`，返回平台指标数组 | 运行不存在 `40400` |
| 分页查询 Agent 执行审计 | `GET` | `/api/geo-monitoring/runs/{run_id}/agent-executions` | Path：`run_id`；Query：`page`、`page_size` 默认 50 且 1-200、`platform_code`、`agent_code` | 分页审计记录 | `code=0`，筛选条件生效 | 运行不存在 `40400` |

平台分析字段包括：

`platform_code`、`status`、`valid_answer_count`、`data_completeness_rate`、`brand_mention_count`、`brand_mention_rate`、`brand_first_count`、`brand_first_rate`、`brand_first_among_mentions_rate`、`top_competitors`、`top_sources`、`prompt_competitiveness_summary`、`improvement_json`、`summary_json`。

Agent 审计字段包括：

`id`、`run_id`、`platform_code`、`agent_code`、`status`、`schema_version`、`input_snapshot`、`output_json`、`model_name`、`prompt_version`、`prompt_tokens`、`completion_tokens`、`error_message`、`started_at`、`finished_at`。

## 12. 看板与趋势模块

### 12.1 看板接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 获取项目最新分析汇总 | `GET` | `/api/geo-monitoring/projects/{project_id}/dashboard` | Path：`project_id` | `project_id`、`latest_run`、`platforms[]` | `code=0`；有运行时 `latest_run` 非空，无运行时为 `null` | 项目不存在 `40400`；项目未启用 `40001` |
| 数据大盘页面级总览 | `GET` | `/api/geo-monitoring/projects/{project_id}/dashboard/overview` | Path：`project_id`；Query：可选 `run_id`、`platform_codes[]`、`start_at`、`end_at` | `run_id`、`kpis`、`platforms[]`、`competitor_preview`、`source_preview`、`recent_questions` | 无运行 `run_id=null`、数组为空；有分析数据时 KPI 与平台表现非空；`platform_codes` 过滤平台与预览；未分析 run 不报错 | 项目不存在 `40400` |
| 按指标、平台和时间范围查询趋势 | `GET` | `/api/geo-monitoring/projects/{project_id}/trends` | Path：`project_id`；Query：必填 `metric_code`，可选 `brand_id`、`platform_code`、`start_at`、`end_at`、`page`、`page_size` 默认 50 且 1-200 | 分页趋势点 | `code=0`，趋势点符合筛选条件；平台级 `brand_mention_rate` 与 `brand_visibility` 返回相同数据，响应 `metric_code` 为 `brand_visibility`；带 `brand_id` 时 `brand_mention_rate` 查询品牌维度快照 | 缺少 `metric_code` 返回 `422`；项目不存在 `40400` |

`latest_run` 字段：

`run_id`、`run_no`、`status`、`collection_status`、`analysis_status`、`platform_codes`、`valid_answer_count`、`data_completeness_rate`、`total_tasks`、`succeeded_tasks`、`failed_tasks`、`cancelled_tasks`、`completed_at`。

`summary` 字段（分析完成后跨平台汇总，`scope=all`）：

`valid_answer_count`、`brand_mention_count`、`brand_mention_rate`、`brand_first_count`、`brand_first_rate`、`brand_top10_mention_count`、`brand_top10_mention_rate`、`brand_mention_total_count`、`positive_rate`、`neutral_rate`、`negative_rate`、`data_completeness_rate`、`metrics[]`（按分子/分母加权汇总，非简单平均；`metrics[]` 不含 `brand_id` 维度快照）。

**趋势指标编码兼容验收：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_dashboard_api.py::test_project_trends_brand_mention_rate_alias_maps_to_brand_visibility backend\tests\geo_monitoring\test_dashboard_api.py::test_project_trends_brand_mention_rate_with_brand_id_queries_brand_snapshots --basetemp .pytest-tmp
```

**指标快照验收：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\analysis\test_metrics.py backend\tests\geo_monitoring\analysis\test_brands.py backend\tests\geo_monitoring\test_dashboard_api.py::test_analyze_persists_extended_metric_snapshots --basetemp .pytest-tmp
```

分析完成后应能在 `geo_metric_snapshot` 查到平台级 `average_mention_rank`、`share_of_voice`、`brand_top10_mention_rate`、`brand_mention_total_count`、`positive_rate`/`neutral_rate`/`negative_rate`，以及带 `brand_id` 的品牌维度快照。

`platforms[]` 字段（分 AI 平台明细）：

`platform_code`、`platform_name`、`collection`（`total_tasks`/`succeeded_tasks`/`failed_tasks`/`cancelled_tasks`）、`analysis`（分析指标，未完成时为 `null`）、`metrics[]`（该平台指标快照）。

可选 Query：`run_id` — 指定某次运行；不传则优先取最近已分析运行，否则取最近采集终态运行。

**overview 自动化测试：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_dashboard_api.py
```

`overview` 关键字段：`kpis`（含 `average_rank`/`share_of_voice`/`brand_mention_total_count`，与竞品分析目标品牌 KPI 一致；无分析时为 `null`）、`competitor_preview.boards`、`source_preview.items`、`recent_questions.items`。`start_at`/`end_at` 会重算 `kpis` 与预览；`platforms[].analysis` 仍为 run 快照。

趋势点字段：

`run_id`、`platform_code`、`metric_code`、`numerator`、`denominator`、`metric_value`、`prompt_set_version`、`snapshot_at`、`completeness_rate`。

## 13. 页面级聚合、导出与竞品分析模块

以下接口支撑原型的数据大盘预览、AI 对话记录、信源引用分析和竞品分析页面。当前页面级聚合默认按单次 run 聚合；`start_at`/`end_at` 过滤该 run 内答案采集时间。

### 13.1 对话记录接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 按 AI 问题聚合主表 | `GET` | `/api/geo-monitoring/projects/{project_id}/conversation-questions` | Path：`project_id`；Query：可选 `run_id`、`platform_codes[]`、`start_at`、`end_at`、`keyword`、`page`、`page_size` | `run_id`、`items[]`、分页 | 同 prompt 多平台答案聚合成一行；`keyword` 过滤问题文本；`platform_codes` 过滤平台指标 | 项目不存在 `40400`；无目标品牌 `40400` |
| 指定问题下各平台回答详情 | `GET` | `/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/answers` | Path：`project_id`、`prompt_id`；Query：同主表 | `run_id`、`prompt_id`、`items[]`、分页 | 含 `citations`、`brand_results[].brand_name`；无引用/品牌时为空数组；`reasoning_text`/`search_keywords` 从 `raw_response_json` 提取 | 问题不存在 `40400` |
| 导出对话记录主表 CSV | `GET` | `/api/geo-monitoring/projects/{project_id}/conversation-questions/export` | Query 同主表（无分页） | CSV 文件流 | `Content-Type: text/csv; charset=utf-8`；UTF-8 BOM；列与主表指标一致 | 项目不存在 `40400` |
| 高频评价标签规则聚类 | `GET` | `/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/evaluation-tags` | Path：`project_id`、`prompt_id`；Query：可选 `run_id`、`platform_codes[]`、`start_at`、`end_at`、`limit` | `cluster_method`、`answer_count`、`items[]` | `cluster_method=rule`；按命中次数降序；`share_rate` 为 decimal 字符串 | 问题不存在 `40400` |

**自动化测试：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_conversations_api.py backend/tests/geo_monitoring/test_answer_export_api.py backend/tests/geo_monitoring/test_answer_metadata.py backend/tests/geo_monitoring/test_evaluation_tags_api.py
```

主表 `items[]` 关键字段：`prompt_id`、`prompt_text`、`valid_answer_count`、`visibility_rate`、`mention_count`、`average_rank`、`top1_rate`、`top3_rate`、`sentiment`、`platform_metrics[]`。

详情 `items[]` 关键字段：`answer_id`、`platform_code`、`raw_text`、`citations[]`、`brand_results[]`、`reasoning_text`、`search_keywords`。

### 13.2 信源引用分析接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 信源引用分析页面级聚合 | `GET` | `/api/geo-monitoring/projects/{project_id}/source-analysis` | Path：`project_id`；Query：可选 `run_id`、`platform_codes[]`、`start_at`、`end_at`、`source_type`、`keyword`、`metric`、`page`、`page_size` | `run_id`、`kpi`、`type_distribution`、`platform_columns`、`sites` | 无信源时 KPI 为 0、列表为空；多平台返回矩阵列；`source_type`/`keyword`/`metric`/`platform_codes` 过滤有效 | 项目不存在 `40400` |
| 导出信源引用分析 CSV | `GET` | `/api/geo-monitoring/projects/{project_id}/source-analysis/export` | Query 同聚合接口（无分页） | CSV 文件流 | `Content-Type: text/csv; charset=utf-8`；UTF-8 BOM；含站点矩阵列 | 项目不存在 `40400` |

**自动化测试：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_source_analysis_api.py backend\tests\geo_monitoring\test_answer_export_api.py
```

关键字段：

- `kpi`：`citation_count`、`site_count`、`article_count`（`AnswerCitation.url` 去重）、`citation_rate`
- `type_distribution[]`：`source_type`、`link_count`、`citation_rate`、`display_value`
- `sites.items[]`：`domain`、`source_name`、`link_count`、`platform_values[]`（含 `has_citation_data`）
- `metric=links` 时 `display_value` 为链接数；`metric=rate` 时为 `citation_rate`
- 传入 `start_at`/`end_at` 后 KPI/矩阵改按 `AnswerCitation` 重聚合；矩阵按 `(domain, source_name)` 分行

补充回归用例：`start_at` 排除全部答案、同域名不同 `source_name`、`run_id` 跨项目、`page/page_size` 分页。

### 13.3 竞品分析接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 竞品分析页面级聚合 | `GET` | `/api/geo-monitoring/projects/{project_id}/competitor-analysis` | Path：`project_id`；Query：可选 `run_id`、`platform_codes[]`、`start_at`、`end_at`、`brand_scope` | `run_id`、`target_brand`、`kpis`、`boards`、`trends` | 无分析时榜单为空不报错；有分析时目标品牌 `is_target=true`；`trends` 为空数组；未分析 run 带时间过滤仍为空榜；不含 candidate 品牌 | 项目/运行/目标品牌不存在 `40400`；`brand_scope` 非法或 `start_at > end_at` 为 `422` |

**自动化测试：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_competitor_analysis_api.py
```

关键字段：

- `kpis`：`mention_rate`、`mention_count`、`average_rank`、`top1_rate`、`share_of_voice`
- `boards.mention_rate[]` / `boards.average_rank[]` / `boards.mention_count[]`：含 `is_target`
- `trends`：本接口固定 `{ days: [], mention_rate: [], average_rank: [], mention_count: [] }`；竞品历史趋势需另测 `GET /projects/{project_id}/trends?metric_code=...&brand_id=...`

补充回归用例：未分析 run + `start_at/end_at` 仍为空榜；`summary_json` 含 candidate 品牌时不入榜；多平台混合 `brand_metrics`/`top_competitors` 快照均参与聚合；`start_at > end_at` 返回 `422`；时间过滤后 `top1_rate` 与过滤答案口径一致，且目标品牌 `first_position=10`、竞品 `first_position=30` 时仍计为 Top1。

## 14. 报告模块

### 14.1 报告字段

创建报告请求体：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `formats` | string[] | 否 | 默认 `["md", "html"]`，支持 `md`、`html`、`pdf`，会去重 |

报告元数据字段：

`id`、`project_id`、`run_id`、`status`、`format`、`file_name`、`relative_storage_path`、`file_size`、`checksum`、`error_message`、`completed_at`、`created_at`、`updated_at`。

### 14.2 报告接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 创建并生成监测报告 | `POST` | `/api/geo-monitoring/runs/{run_id}/reports` | Path：`run_id`；Body：`ReportCreateRequest` | `run_id`、`reports[]` | 返回报告列表，报告 `status=completed`，`file_size` 和 `checksum` 非空 | 分析未完成 HTTP `409`、`40920`；格式不支持 `40060`；运行不存在 `40400` |
| 分页查询运行报告 | `GET` | `/api/geo-monitoring/runs/{run_id}/reports` | Path：`run_id`；Query：`page`、`page_size` 默认 20 且 1-100 | 分页报告元数据 | `code=0`，报告均属于该运行 | 运行不存在 `40400` |
| 获取报告状态与元数据 | `GET` | `/api/geo-monitoring/reports/{report_id}` | Path：`report_id` | 报告元数据 | `data.id = report_id` | 报告不存在 HTTP `404`、`code=40420` |
| 下载报告文件 | `GET` | `/api/geo-monitoring/reports/{report_id}/download` | Path：`report_id` | 文件二进制/文本响应，不是统一 JSON | HTTP `200`，`Content-Disposition` 包含文件名，`Content-Type` 为 `text/markdown; charset=utf-8`、`text/html; charset=utf-8` 或 `application/pdf` | 报告未生成完成 HTTP `409`、`40921`；报告不存在 HTTP `404`、`40420` |
| 删除报告 | `DELETE` | `/api/geo-monitoring/reports/{report_id}` | Path：`report_id` | 报告元数据 | `code=0`，后续查询不存在 | 报告不存在 HTTP `404`、`40420` |

创建报告示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/runs/1/reports" \
  -H "Content-Type: application/json" \
  -d '{"formats":["md","html","pdf"]}'
```

## 15. 推荐测试流程

### 15.1 基础连通性

1. 调用 `/api/health`，确认应用可响应。
2. 调用 `/api/ready`，确认数据库和 Redis 可用。
3. 调用 `/api/geo-monitoring/health` 与 `/api/geo-monitoring/ready`，确认监测模块可用。

### 15.2 主业务正向流程

1. 查询新版首页项目列表：`GET /projects/overview`。`GET /projects/options` 仅作为兼容轻量列表单独验证，不作为首页首屏依赖。
2. 创建项目：
   - 交互式向导：`POST /projects` → `PUT /project-drafts/current` 保存草稿 → `PUT /projects/{project_id}/monitor-setup`。
   - 事务式提交：`POST /projects:setup`。
3. 初始化配置候选：`GET /platform-endpoints?enabled=true`、`GET /prompt-types`、`GET /prompt-library`。
4. 验证 AI 生成候选不落库：创建向导使用 `POST /ai/brand-words:generate`、`/ai/competitors:generate`、`/ai/questions:generate`（全局路径，调用前后 `GET /projects` 的 `total` 不变）；已创建项目场景仍可用项目域路径。
5. 保存完整监测设置：`PUT /projects/{project_id}/monitor-setup`，建议传 `activate_prompt_set=true`。
6. 查询或更新 AI 平台，保证至少一个平台 `enabled=true`。
7. 创建监测运行：`POST /runs`（可不传 `platform_codes`，使用项目默认平台）。
8. 查询运行详情和任务：`GET /runs/{run_id}`、`GET /runs/{run_id}/query-tasks`。
9. 采集完成后查询答案：`GET /runs/{run_id}/answers`、`GET /answers/{answer_id}`。
10. 运行终态后触发或重跑分析：`POST /runs/{run_id}/analyze`。
11. 查询分析和基础看板：`GET /runs/{run_id}/analysis`、`GET /projects/{project_id}/dashboard`。
12. 验证首页卡片动作：
    - 进入：使用卡片 `project_id` 跳转后调用 `GET /projects/{project_id}/dashboard/overview`。
    - 编辑配置：`GET /projects/{project_id}/monitor-setup` → `PUT /projects/{project_id}/monitor-setup` → 刷新 `GET /projects/overview`。
    - 暂停/监测：`POST /projects/{project_id}/pause` 或 `POST /projects/{project_id}/resume` → 刷新 `GET /projects/overview`。
    - 删除：`GET /projects/{project_id}/delete-check` → 可删除时 `DELETE /projects/{project_id}`。
13. 验证原型页面级聚合：
    - 数据大盘：`GET /projects/{project_id}/dashboard/overview`。
    - 竞品分析：`GET /projects/{project_id}/competitor-analysis`、`GET /benchmarks?industry={industry}`。
    - AI 对话记录：`GET /projects/{project_id}/conversation-questions`、`GET /projects/{project_id}/conversation-questions/{prompt_id}/answers`。
    - 高频评价标签：`GET /projects/{project_id}/conversation-questions/{prompt_id}/evaluation-tags`。
    - 信源引用分析：`GET /projects/{project_id}/source-analysis`。
14. 验证趋势接口：
    - 平台级品牌可见度：`GET /projects/{project_id}/trends?metric_code=brand_visibility`。
    - 品牌维度竞品趋势：`GET /projects/{project_id}/trends?metric_code=brand_mention_rate&brand_id={brand_id}`。
15. 验证导出：
    - `GET /projects/{project_id}/conversation-questions/export`。
    - `GET /projects/{project_id}/source-analysis/export`。
16. 分析完成后生成报告：`POST /runs/{run_id}/reports`。
17. 下载报告：`GET /reports/{report_id}/download`。

### 15.3 重点反向测试

| 场景 | 操作 | 预期 |
| --- | --- | --- |
| 参数校验失败 | `page=0` 或枚举传非法值 | `code=422` |
| 查询不存在资源 | 查询不存在的 `project_id`、`brand_id`、`run_id` | `code=40400` 或报告 `40420` |
| 项目未启用 | 将项目状态改为 `disabled` 后查询品牌/提示词/调度/看板 | `code=40001` |
| 重复目标品牌 | 同项目创建第二个 `brand_type=target` 品牌 | `code=40010` |
| 重复品牌名 | 同项目创建同名品牌 | `code=40012` |
| 重复别名 | 同品牌创建同名别名 | `code=40011` |
| 重复核心词 | 同项目创建同名核心词 | `code=40024` |
| 监测设置平台不可用 | `monitor-setup` 传入未启用或不存在的平台 | `code=40025` |
| 监测设置缺少品牌 | `monitor-setup` 未传 `brand` | `code=40028` |
| 空提示词集激活 | 未添加提示词时激活提示词集 | `code=40022` |
| 非草稿提示词集修改 | 激活后修改提示词集或提示词 | `code=40020` |
| 无激活提示词集创建运行 | 项目未激活提示词集时创建运行 | `code=40030` |
| 无可用平台创建运行 | 所有平台禁用后创建运行 | HTTP `409`，`code=40902` |
| 采集未完成触发分析 | 非终态运行调用 `/analyze` | HTTP `409`，`code=40910` |
| 分析未完成生成报告 | `analysis_status` 不是 `completed` 或 `partial_success` | HTTP `409`，`code=40920` |
| 下载未完成报告 | 报告 `status` 不是 `completed` | HTTP `409`，`code=40921` |

## 16. 测试结果记录建议

每个接口建议记录：

| 字段 | 说明 |
| --- | --- |
| 测试时间 | 执行接口测试的时间 |
| 环境 | 本地、测试、预发等 |
| 请求方法与 URL | 完整 URL |
| 请求参数 | Path、Query、Body |
| HTTP 状态码 | 实际状态码 |
| 响应体 | 完整 JSON 或关键字段 |
| 成功判定 | 是否满足本文档“验证成功”标准 |
| 失败原因 | 若失败，记录 `code`、`message`、异常日志或依赖状态 |

## 17. 自动化全量测试

仓库提供脚本 [`backend/scripts/run_api_full_test.py`](../backend/scripts/run_api_full_test.py)，按本文档模块顺序调用已实现接口并生成报告 [`docs/API全量接口测试报告.md`](./API全量接口测试报告.md)。

**前置条件：**

- API 进程：`http://127.0.0.1:8000`
- PostgreSQL、Redis 可用（`/api/ready` 通过）
- 至少一个 AI 平台 `enabled=true`（脚本会自动尝试启用 `qwen` 等）
- 采集链路需 Dramatiq worker；完整采集/分析/报告依赖外部 AI 密钥与 Agent LLM

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe backend/scripts/run_api_full_test.py
```

**最近全量测试结果（2026-06-22）：** 83 用例，80 通过，通过率 96.4%。未通过项主要为环境限制：采集 120 秒内未终态（`collecting`）、分析前置未满足（`40910`）、清理阶段删除已被运行引用的提示词集（`40906`）。配置域接口（含 §5.4 监测设置）全部通过。

## 18. Settings 配置单元测试（模力指数 M1）

覆盖 `backend/app/core/config.py` 中模力指数相关 `Settings` 字段、启动校验与 `runtime_summary()` 脱敏行为。与 HTTP 接口无关，使用 pytest 直接构造 `Settings` 实例。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| 未启用且无 token | `test_molizhishu_disabled_without_token_starts_ok` | 应用配置可正常实例化 |
| 启用但 token 为空 | `test_enabled_molizhishu_requires_token` | `ValidationError`，提示 `MOLIZHISHU_API_TOKEN` |
| runtime summary 脱敏 | `test_runtime_summary_redacts_all_secrets` | `platforms.molizhishu` 仅含 `enabled` / `base_url` / `has_token`，不含 token 明文 |
| screenshot 取值 | `test_molizhishu_default_screenshot_must_be_zero_or_one` | 非 0/1 抛出 `ValidationError` |
| `.env.example` 字段一致 | `test_env_example_uses_placeholders_without_real_connection_values` | 含全部 `MOLIZHISHU_*` / `COLLECTION_MOLIZHISHU_*` 键 |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_config.py
```

**验收点（Task M1）：**

- 未启用时应用照常启动。
- 启用且 token 为空时抛出明确错误。
- summary 和日志不包含完整 token。
- `.env.example` 与代码字段一致。

## 19. 模力指数适配器单元测试（Task M5）

覆盖 `backend/app/geo_monitoring/adapters/molizhishu.py` 的提交、轮询、完成、失败与错误分类。使用 `respx` mock HTTP，不访问真实模力指数接口。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| 协议兼容 | `test_molizhishu_adapter_satisfies_platform_adapter_protocol` | `isinstance(MolizhishuAdapter(...), PlatformAdapter)` |
| 首次提交后 processing | `test_molizhishu_submits_then_pending_carries_metadata` | 抛 `MolizhishuPendingError`，`pending_metadata` 含 taskId/subTaskId/platform/mode/status |
| 复用 taskId/subTaskId | `test_molizhishu_reuses_existing_task_and_subtask_without_resubmitting` | 不重复 POST `/task/batch/shared` |
| 完成归一化 | `test_molizhishu_completed_returns_answer_and_citations` | `answerContent`、citations、`provider_request_id=subTaskId` |
| referenceList fallback | `test_molizhishu_uses_reference_list_when_citation_list_empty` | `referenceList.summary` 回填 `quoted_text` |
| HTTP 200 业务失败 | `test_molizhishu_http_200_business_failure_is_rejected` | `success=false` 抛 `AdapterError` |
| Token 失效 | `test_molizhishu_token_expired_is_unauthorized` | `ErrorCategory.UNAUTHORIZED`，消息不含 token |
| 余额不足 | `test_molizhishu_insufficient_balance_is_non_retryable` | `ErrorCategory.INVALID_REQUEST` |
| 非 JSON / 超时 | `test_molizhishu_non_json_response_is_classified`、`test_molizhishu_timeout_is_network_error` | 提交阶段非 JSON 归类为无效响应；轮询阶段见下行 |
| 轮询非 JSON 续跑 | `test_molizhishu_result_non_json_during_poll_raises_pending_then_completes` | result 先返回非 JSON 抛 `MolizhishuPendingError`，下次轮询 completed |
| processing 已有答案 | `test_molizhishu_processing_with_answer_content_returns_completed` | `status=processing` 且 `answerContent` 非空时直接返回结果（生产口径：答案就绪优先于 provider status） |
| 子任务终态失败 | `test_molizhishu_terminal_failure_status_raises_adapter_error` | `failed/error/stopped` 抛不可重试错误 |
| regionCode 提交 | `test_molizhishu_submit_includes_region_code_when_provided` | 提交体含 `regionCode: [code]` |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters\test_molizhishu.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters
```

**验收点（Task M5）：**

- 单元测试覆盖提交、轮询、完成、失败、鉴权、异常响应。
- 错误消息不泄漏 token。
- `raw_response` 仅保存 submit/result 原始包，不含 token。
- **结果就绪口径：** `pending/assigned/processing` 且无 `answerContent` 时 pending；有 `answerContent` 时即使 provider `status` 非 `completed` 也返回成功（与任务书 §3.2、§7.1 一致）。

## 20. CollectionService 轮询续跑测试（Task M7）

覆盖 `backend/app/geo_monitoring/services/collection.py` 与 `backend/app/worker/actors/collection.py` 对模力指数 pending 子任务的 metadata 持久化、轮询上限与 Actor 重入队延迟。Aidso 既有 pending 行为保持兼容。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| 首次 pending 保存 task/subTask | `test_molizhishu_pending_persists_task_and_subtask_ids_and_reuses_on_retry` | `request_json` 含 `molizhishu_task_id` / `molizhishu_subtask_id` / `molizhishu_poll_count=1`，`provider_request_id=subTaskId` |
| pending 复用 metadata | 同上 | 第二次调用 metadata 含 `molizhishu_subtask_id`，`attempt_count` 仍为 1 |
| provider 上下文注入 | 同上 | metadata 含 `provider_mode` / `provider_screenshot` / `region_code` |
| 轮询上限 | `test_molizhishu_pending_respects_configured_max_poll_limit` | 达到 `COLLECTION_MOLIZHISHU_MAX_POLLS` 后任务 `failed`，`retry_count=0` |
| Actor 轮询延迟 | `test_molizhishu_pending_reenqueue_uses_configured_poll_delay` | pending 重入队 delay 为 `COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS × 1000` ms |
| 普通错误退避 | `test_retry_reenqueue_uses_configured_backoff` | 非 pending 重试仍用 `COLLECTION_RETRY_BASE_SECONDS` |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\worker\test_collection_actor.py
```

**验收点（Task M7）：**

- 模力指数 pending 能从 `taskId/subTaskId` 收敛到 success 或 failed。
- pending 轮询不递增 `attempt_count`。
- 子任务失败不影响同 run 其他任务（Run 聚合逻辑不变）。

## 21. 结果归一化、入库与安全展示测试（Task M8）

覆盖 `molizhishu.py` 引用归一化、`collection.py` 成功落库与 provider 字段同步、`answer_metadata.py` 模力指数安全视图、`brand_matcher.py` provider 品牌上下文合并。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| citationList 入库 | `test_molizhishu_success_persists_citation_list` | `geo_answer_citation` 写入 title/url/quoted_text |
| referenceList 回退 | `test_molizhishu_success_falls_back_to_reference_list` | citation 为空时 reference summary 写入 quoted_text |
| 无引用仍落库 | `test_molizhishu_success_without_citations_still_persists_answer` | `geo_answer.raw_text` 写入，citations 为空 |
| provider 品牌不覆盖本地指标 | `test_molizhishu_provider_brand_fields_do_not_override_local_brand_metrics` | `is_mentioned/mention_count/first_position` 仍由本地匹配；`context_json.provider_*` 保留 provider 字段 |
| provider 字段同步 | `test_molizhishu_success_syncs_provider_task_fields` | `QueryTask.provider_*` 与 `provider_result_json` 写入 |
| 失败 errorMessage | `test_molizhishu_failure_sets_provider_error_message` | `QueryTask.provider_error_message` 写入 provider 原文 |
| 安全视图白名单 | `test_build_raw_response_safe_molizhishu_whitelists_safe_fields` | 仅暴露安全字段，不含 token/proxy/品牌指标 |
| 对象型 recommendedQuestions | `test_build_raw_response_safe_molizhishu_ignores_object_recommended_questions` | 仅保留字符串或对象 `question`/`title` 字段，丢弃 debug/token |
| provider 品牌上下文 sanitize | `test_molizhishu_provider_brand_context_is_sanitized_for_api` | 字符串截断、rankings 限 20 条且仅白名单字段 |
| 思考与追问提取 | `test_extract_molizhishu_reasoning_process_and_recommended_questions` | `reasoningProcess.content` → `reasoning_text`；`recommendedQuestions` → `search_keywords` |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_answer_metadata.py backend\tests\geo_monitoring\test_collection_contract.py -k molizhishu
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters\test_molizhishu.py
```

**验收点（Task M8）：**

- `Answer`、`AnswerCitation`、`AnswerBrandResult` 与现有分析服务兼容。
- 答案详情可展示安全化 provider 原始信息。
- source analysis 可统计模力指数引用来源。

## 22. Run 路由、取消与停止任务测试（Task M9）

覆盖 `backend/app/geo_monitoring/services/runs.py`、`backend/app/geo_monitoring/services/collection.py`、`backend/app/geo_monitoring/adapters/molizhishu.py` 的平台筛选、模力指数 run 创建与取消时 provider stop。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| 模力指数 run 拒绝官方平台 | `test_molizhishu_run_rejects_official_platform` | `code=40031` |
| 官方 run 拒绝模力指数平台 | `test_official_run_rejects_molizhishu_platform` | `code=40031` |
| 官方默认平台排除 molizhishu | `test_official_run_defaults_exclude_molizhishu_when_all_platforms_enabled` | `platform_codes` 不含 `molizhishu_*` |
| 模力指数 run 持久化 provider 字段 | `test_create_molizhishu_run_persists_provider_fields` | `provider_mode_by_platform` 等字段落库 |
| provider stop API | `test_molizhishu_stop_task_calls_put_endpoint` | `PUT /task/{taskId}/stop` |
| 取消模力指数 run 后台调度 stop | `test_cancel_molizhishu_run_schedules_provider_stop_after_local_cancel` | 本地先 `cancelled`，`schedule_molizhishu_provider_stop` 被调用 |
| stop 目标收集 | `test_collect_molizhishu_provider_stop_targets_filters_dedupes_and_skips_blank` | 排除终态、去重 taskId、跳过空白 taskId |
| stop 失败不阻断 | `test_stop_molizhishu_provider_tasks_continues_after_adapter_error` | 部分 `AdapterError` 后仍 stop 其他 taskId |
| 取消保留已完成子任务 | `test_cancel_molizhishu_run_preserves_successful_tasks` | `success` 与 `cancelled` 共存 |
| 通用取消行为 | `test_cancel_run_cancels_incomplete_tasks` | 仅未完成子任务变 `cancelled` |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_runs.py backend\tests\geo_monitoring\test_run_lifecycle.py -k "molizhishu or cancel"
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters\test_molizhishu.py::test_molizhishu_stop_task_calls_put_endpoint
```

**验收点（Task M9）：**

- 平台筛选与错误码清晰（`40031` / `40902`）。
- 取消带 `provider_task_id` 的模力指数运行会尝试 provider stop。
- 已完成子任务不会被删除或覆盖。

## 23. RegionCode 与截图策略测试（Task M11）

覆盖 `molizhishu.py` 提交体中的 `regionCode` / `screenshot`、`RunCreate` 校验，以及模力指数区域列表代理接口。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| regionCode 提交 | `test_molizhishu_submit_includes_region_code_when_provided` | 提交体含 `regionCode: [code]` |
| 无 region 仍可提交 | `test_molizhishu_submit_omits_region_code_when_not_provided` | 提交体不含 `regionCode` |
| screenshot 提交 | `test_molizhishu_submit_includes_screenshot_when_provided` | `platforms[].screenshot` 为 `0/1/2` |
| screenshot 校验 | `test_run_create_rejects_invalid_provider_screenshot` | `provider_screenshot=3` 返回校验错误 |
| bool 截图拒绝 | `test_run_create_rejects_bool_provider_screenshot` | `provider_screenshot=true` 返回 `422` |
| 默认截图策略 | `test_run_create_applies_molizhishu_default_screenshot_when_omitted` | 未传字段时使用 `MOLIZHISHU_DEFAULT_SCREENSHOT` |
| 区域列表缓存 TTL | `test_molizhishu_regions_cache_expires_after_ttl` | TTL 过期后重新请求上游 |
| TTL=0 不缓存 | `test_molizhishu_regions_skips_cache_when_ttl_zero` | 每次请求都打上游 |
| 模力指数 run 持久化 | `test_create_molizhishu_run_persists_provider_fields` | `provider_screenshot` / `region_code` 落库 |
| 区域列表代理 | `test_molizhishu_regions_returns_normalized_list` | 返回 `items[].province/region_code` |
| 区域列表缓存 | `test_molizhishu_regions_uses_local_cache` | 短缓存内不重复请求上游 |
| 上游不可用 | `test_molizhishu_regions_returns_clear_error_when_upstream_unavailable` | `code=50210` 且消息可定位 |
| v1 兼容前缀 | `test_metadata_routes_available_on_v1_prefix` | `/api/v1/geo-monitoring/providers/molizhishu/regions` 可用 |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_metadata_api.py -k molizhishu_regions
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters\test_molizhishu.py -k "region or screenshot"
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_models.py -k provider_screenshot
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_runs.py::test_create_molizhishu_run_persists_provider_fields
```

**验收点（Task M11）：**

- 不传 `region_code` 时模力指数提交仍可成功。
- 传 `region_code` 时提交体为长度为 1 的 `regionCode` 数组。
- `provider_screenshot` 仅允许 `0/1/2`，并写入 `platforms[].screenshot`。
- 区域接口为 provider 代理能力，上游失败返回清晰错误。

## 24. 分析、报告与页面聚合回归测试（Task M12）

覆盖模力指数入库数据在分析触发、Dashboard、竞品分析、信源分析与 Markdown/HTML/PDF 报告链路的消费兼容性。验证分析/报告服务不硬编码 `aidso` 或官方平台 code，平台展示名来自 `AIPlatform`，信源统计基于 `AnswerCitation`/`SourceStat`，报告不泄漏 token。

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| 分析触发与落库 | `test_molizhishu_run_triggers_analysis_and_persists_platform_analysis` | `POST /runs/{id}/analyze` 返回 `completed`；`PlatformAnalysis` 写入模力指数 platform_code |
| 信源分析 | `test_molizhishu_source_analysis_counts_domains_and_types` | 域名 `example.com`/`news.example.com` 与类型分布可统计；`platform_columns` 含 `molizhishu_*` |
| 竞品分析 | `test_molizhishu_competitor_analysis_boards_and_kpis` | KPI 与 boards 含目标品牌；`top1_rate` 可计算 |
| Dashboard | `test_molizhishu_dashboard_uses_platform_catalog_name` | `platform_name` 来自 `AIPlatform.platform_name`，非裸 code |
| 报告渲染 | `test_molizhishu_report_renders_without_token_leak` | Markdown/HTML/PDF 含指标与引用；PDF 以 `%PDF` 开头；各格式均不含 `Authorization`/token/proxyIp |
| 结构一致性 | `test_molizhishu_and_official_run_report_field_structure_match` | 官方 run 与模力指数 run 的 analysis/dashboard/report context 字段结构一致 |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_molizhishu_analysis_regression.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_dashboard_api.py backend\tests\geo_monitoring\test_source_analysis_api.py backend\tests\geo_monitoring\test_competitor_analysis_api.py backend\tests\geo_monitoring\reports backend\tests\geo_monitoring\test_molizhishu_analysis_regression.py
```

**验收点（Task M12）：**

- 品牌提及率、首推率、竞品提及、引用来源统计可正常生成。
- 官方 run 与模力指数 run 的报告字段结构保持一致。
- 分析/聚合链路不依赖 `collection_source` 或 provider 类型分支。

## 25. 测试套件迁移与真实接口 smoke 脚本（Task M13）

覆盖模力指数采集集成测试、callback/adapter 既有 mock 套件、迁移校验，以及可手动执行的真实接口 smoke 脚本。pytest 默认使用 `respx` mock，不访问真实模力指数网络；smoke 脚本仅手动运行。

### 25.1 模力指数采集集成测试

文件：`backend/tests/geo_monitoring/test_molizhishu_collection.py`

| 场景 | 测试函数 | 预期 |
| --- | --- | --- |
| 1 prompt × 1 platform | `test_one_prompt_one_platform_collects_answer_with_citations` | 任务 `success`，答案与 citation/brand 入库，run `completed` |
| pending 续跑 | `test_pending_poll_resume_reuses_submitted_task` | 首次 `processing` 后复用 taskId/subTaskId，仅提交一次 |
| 轮询上限 | `test_max_poll_limit_marks_task_failed` | 达到 `COLLECTION_MOLIZHISHU_MAX_POLLS` 后 `failed`，无答案 |
| 部分失败 | `test_partial_success_when_one_subtask_fails` | 两子任务一成功一失败，run `partial_success` |
| 取消任务 | `test_cancelled_task_does_not_call_provider` | `cancelled` 任务不调用 provider submit |
| provider raw 入库 | `test_completed_answer_persists_provider_raw_response` | `raw_response_json` 含 submit/result，不含 token |
| smoke 无 token 退出 | `test_smoke_script_exits_without_token_from_repo_root_command` | 按 README 根目录命令执行，返回非 0 并提示 `MOLIZHISHU_API_TOKEN` |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_molizhishu_collection.py
```

### 25.2 适配器 / Callback / Worker / 迁移（M13 回归范围）

| 范围 | 文件 | 说明 |
| --- | --- | --- |
| 适配器单元 | `backend/tests/geo_monitoring/adapters/test_molizhishu.py` | 提交、pending、完成、失败、token/余额/超时等 |
| Callback 幂等 | `backend/tests/geo_monitoring/test_molizhishu_callback.py` | 成功、重复推送、与轮询并发 |
| Worker 轮询 | `backend/tests/worker/test_collection_actor.py` | pending metadata、轮询上限、重入队延迟 |
| 入库契约 | `backend/tests/geo_monitoring/test_collection_contract.py` | citation/reference、provider 品牌上下文 |
| 迁移 | `backend/tests/test_migrations.py` | `collection_source` 扩展、seed 11 平台、provider 字段 |
| Aidso 历史兼容 | `backend/tests/geo_monitoring/adapters/test_aidso.py` | 保留历史 adapter mock，不访问真实 Aidso |

**执行命令：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters\test_molizhishu.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\test_molizhishu_callback.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\worker\test_collection_actor.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_migrations.py backend\tests\test_migration_baseline.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters\test_qwen.py backend\tests\geo_monitoring\adapters\test_doubao.py
```

### 25.3 真实接口 smoke 脚本（手动）

文件：`backend/scripts/molizhishu_smoke_test.py`

- 读取 `.env` / 环境中的 `MOLIZHISHU_API_TOKEN`；无 token 时直接退出并提示。
- 默认提交 1 prompt × 1 platform：`platform=qianwen`、`mode=search`、`screenshot=0`。
- 轮询打印 `taskId`、`subTaskId`、`status`、`answerContent` 摘要、citation/reference 数量。
- **不写业务数据库**，不经过采集 worker。
- **可能产生费用**；仅用于上线前或密钥变更后的手动连通性验证。

**执行命令（需已配置真实 token）：**

```powershell
backend\.venv\Scripts\python.exe backend\scripts\molizhishu_smoke_test.py
backend\.venv\Scripts\python.exe backend\scripts\molizhishu_smoke_test.py --prompt "100w汽车推荐" --platform qianwen --mode search --screenshot 0
```

**验收点（Task M13）：**

- Mock 测试不访问真实网络。
- smoke 脚本只有手动运行才访问真实接口。
- 旧官方 API 采集测试（`test_qwen.py`、`test_doubao.py` 等）仍通过。
- 真实 smoke 成功时，provider `status` 可能仍为 `processing`；以 `answerContent` 非空为准，与 adapter 生产口径一致。
