# API 测试文档

本文档根据当前后端代码整理，覆盖 `backend/app/api/router.py`、`backend/app/main.py` 与 `backend/app/geo_monitoring/api/` 下已实现接口。

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
| 获取项目 | `GET` | `/api/geo-monitoring/projects/{project_id}` | Path：`project_id >= 1` | `ProjectOut` | `data.id = project_id` | 不存在返回 `code=40400`、`message=监测项目不存在` |
| 更新项目 | `PUT` | `/api/geo-monitoring/projects/{project_id}` | Path：`project_id >= 1`；Body：`ProjectUpdate` | `ProjectOut` | 返回字段已更新，`updated_at` 变化 | 不存在返回 `40400`；状态非法返回 `422` |
| 删除项目 | `DELETE` | `/api/geo-monitoring/projects/{project_id}` | Path：`project_id >= 1` | `{ "id": project_id }` | 返回删除 ID，后续获取返回不存在 | 项目已有监测运行引用时 HTTP `409`、`code=40903` |

创建示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/projects" \
  -H "Content-Type: application/json" \
  -d '{"project_name":"杭州宋城文旅监测","industry":"文旅演艺","timezone":"Asia/Shanghai"}'
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

自动化测试文件：`backend/tests/geo_monitoring/test_metadata_api.py`

覆盖场景：Aidso 端码分组、`extra_config` 覆盖、`enabled` 过滤、平台数超过 500 不截断、v1 兼容前缀可访问。

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_metadata_api.py
```

#### 5.4.7 AI 生成辅助接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| AI 生成品牌词 | `POST` | `/api/geo-monitoring/projects/{project_id}/ai/brand-words:generate` | Body：`brand_name`（必填）、`category`、`official_domain`、`limit` 默认 10 | `{ "brand_words": string[] }` | `code=0`；必含 `brand_name`；去重 | 项目不存在 `40400`；品牌名为空 `422` |
| AI 生成竞品 | `POST` | `/api/geo-monitoring/projects/{project_id}/ai/competitors:generate` | Body：`brand_name`（必填）、`category`、`region`、`limit` 默认 5 | `{ "competitors": [{ brand_name, competitor_words[], official_domain? }] }` | `code=0`；排除目标品牌自身 | 项目不存在 `40400` |
| AI 生成监测问题 | `POST` | `/api/geo-monitoring/projects/{project_id}/ai/questions:generate` | Body：`brand_name`（必填）、`category`、`region`、`core_keywords[]`、`competitors[]`、`limit` 默认 10 | `{ "questions": [{ prompt_text, prompt_type, core_keyword? }] }` | 五类意图模板；按 `limit` 截断 | 项目不存在 `40400` |

自动化测试文件：`backend/tests/geo_monitoring/test_ai_generation_api.py`

覆盖场景：宋城/杭州旅游示例、空品牌名校验、生成不落库、项目不存在。

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_ai_generation_api.py
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
| `platform_codes` | string[]/null | 否 | 指定平台代码；不传则使用项目 `default_platform_codes`；仍为空时使用全部已启用平台 |

运行响应字段：

`id`、`run_no`、`project_id`、`prompt_set_id`、`prompt_set_version`、`trigger_type`、`triggered_by`、`status`、`collection_status`、`analysis_status`、`report_status`、`platform_codes`、`expected_query_count`、`total_tasks`、`succeeded_tasks`、`failed_tasks`、`cancelled_tasks`、`success_query_count`、`failed_query_count`、`valid_answer_count`、`data_completeness_rate`、`result_json`、`error_message`、`error_summary`、`started_at`、`completed_at`、`finished_at`、`created_at`、`updated_at`。

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
| 创建监测运行 | `POST` | `/api/geo-monitoring/runs` | Body：`RunCreate` | `MonitorRunOut` | 返回新 `run_no`，`total_tasks = 可用提示词数 * 平台数`，状态进入 `collecting` 或后续终态 | 项目无激活提示词集 `40030`；无可用提示词 HTTP `409`、`40901`；AI 平台不可用 `40031`；无可用平台 HTTP `409`、`40902` |
| 获取运行详情 | `GET` | `/api/geo-monitoring/runs/{run_id}` | Path：`run_id` | `MonitorRunOut + progress_rate` | `data.id = run_id`，任务统计刷新 | 不存在 `40400` |
| 取消运行 | `POST` | `/api/geo-monitoring/runs/{run_id}/cancel` | Path：`run_id` | `MonitorRunOut` | 未终态运行返回 `status=cancelled`；已终态运行返回当前终态 | 不存在 `40400` |
| 重试失败任务 | `POST` | `/api/geo-monitoring/runs/{run_id}/retry-failed` | Path：`run_id` | `MonitorRunOut + retried_count` | `retried_count` 等于重置的失败任务数；有失败任务时状态回到 `collecting` | 已取消运行不可重试 `40040` |

### 8.3 查询任务接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询运行任务 | `GET` | `/api/geo-monitoring/runs/{run_id}/query-tasks` | Path：`run_id`；Query：`page`、`page_size` 默认 100 且 1-500、`status`、`platform_code` | 分页 `QueryTaskOut[]` | `code=0`，任务均属于该运行 | 运行不存在 `40400` |
| 分页查询运行任务别名 | `GET` | `/api/geo-monitoring/runs/{run_id}/tasks` | 同上 | 分页 `QueryTaskOut[]` | 与 `/query-tasks` 返回一致 | 同上 |

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
| `citations` | array | 引用来源，字段包括 `citation_no`、`title`、`url`、`domain`、`source_type`、`quoted_text` |
| `brand_results` | array | 品牌识别结果，字段包括 `brand_id`、`is_mentioned`、`mention_count`、`first_position`、`sentiment`、`context_json` |

### 10.2 答案接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 分页查询运行答案 | `GET` | `/api/geo-monitoring/runs/{run_id}/answers` | Path：`run_id`；Query：`page`、`page_size` | 分页 `AnswerRead[]` | `code=0`，答案均来自该运行 | 运行不存在 `40400` |
| 获取答案详情 | `GET` | `/api/geo-monitoring/answers/{answer_id}` | Path：`answer_id` | `AnswerDetailRead` | `data.id = answer_id`，包含 `citations` 与 `brand_results` 数组 | 答案不存在 `40400` |

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
| 按指标、平台和时间范围查询趋势 | `GET` | `/api/geo-monitoring/projects/{project_id}/trends` | Path：`project_id`；Query：必填 `metric_code`，可选 `platform_code`、`start_at`、`end_at`、`page`、`page_size` 默认 50 且 1-200 | 分页趋势点 | `code=0`，趋势点符合筛选条件 | 缺少 `metric_code` 返回 `422`；项目不存在 `40400` |

`latest_run` 字段：

`run_id`、`run_no`、`status`、`collection_status`、`analysis_status`、`platform_codes`、`valid_answer_count`、`data_completeness_rate`、`total_tasks`、`succeeded_tasks`、`failed_tasks`、`cancelled_tasks`、`completed_at`。

`summary` 字段（分析完成后跨平台汇总，`scope=all`）：

`valid_answer_count`、`brand_mention_count`、`brand_mention_rate`、`brand_first_count`、`brand_first_rate`、`data_completeness_rate`、`metrics[]`（按分子/分母加权汇总，非简单平均）。

`platforms[]` 字段（分 AI 平台明细）：

`platform_code`、`platform_name`、`collection`（`total_tasks`/`succeeded_tasks`/`failed_tasks`/`cancelled_tasks`）、`analysis`（分析指标，未完成时为 `null`）、`metrics[]`（该平台指标快照）。

可选 Query：`run_id` — 指定某次运行；不传则优先取最近已分析运行，否则取最近采集终态运行。

趋势点字段：

`run_id`、`platform_code`、`metric_code`、`numerator`、`denominator`、`metric_value`、`prompt_set_version`、`snapshot_at`、`completeness_rate`。

## 13. AI 对话记录模块

P0 按单次 run 聚合；`start_at`/`end_at` 仅过滤该 run 内答案采集时间。

### 13.1 对话记录接口

| 用途 | 方法 | 路径 | 入参 | 出参 | 验证成功 | 常见失败 |
| --- | --- | --- | --- | --- | --- | --- |
| 按 AI 问题聚合主表 | `GET` | `/api/geo-monitoring/projects/{project_id}/conversation-questions` | Path：`project_id`；Query：可选 `run_id`、`platform_codes[]`、`start_at`、`end_at`、`keyword`、`page`、`page_size` | `run_id`、`items[]`、分页 | 同 prompt 多平台答案聚合成一行；`keyword` 过滤问题文本；`platform_codes` 过滤平台指标 | 项目不存在 `40400`；无目标品牌 `40400` |
| 指定问题下各平台回答详情 | `GET` | `/api/geo-monitoring/projects/{project_id}/conversation-questions/{prompt_id}/answers` | Path：`project_id`、`prompt_id`；Query：同主表 | `run_id`、`prompt_id`、`items[]`、分页 | 含 `citations`、`brand_results[].brand_name`；无引用/品牌时为空数组；`reasoning_text=null`、`search_keywords=[]` | 问题不存在 `40400` |

**自动化测试：**

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring\test_conversations_api.py
```

主表 `items[]` 关键字段：`prompt_id`、`prompt_text`、`valid_answer_count`、`visibility_rate`、`mention_count`、`average_rank`、`top1_rate`、`top3_rate`、`sentiment`、`platform_metrics[]`。

详情 `items[]` 关键字段：`answer_id`、`platform_code`、`raw_text`、`citations[]`、`brand_results[]`、`reasoning_text`、`search_keywords`。

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

1. 创建项目：`POST /projects`。
2. **（推荐）保存监测设置**：`PUT /projects/{project_id}/monitor-setup`（品牌、竞品、核心词、AI 问题、平台一次配置）。
3. 或分步配置：
   - 创建目标品牌和竞品品牌：`POST /projects/{project_id}/brands`。
   - 给品牌创建别名：`POST /brands/{brand_id}/aliases`。
   - 创建核心词：`POST /projects/{project_id}/core-keywords`（可选，也可在 monitor-setup 中一并创建）。
   - 从词库选题：`GET /prompt-library`。
   - 创建提示词集：`POST /projects/{project_id}/prompt-sets`。
   - 创建至少一个启用提示词：`POST /prompt-sets/{prompt_set_id}/prompts`。
   - 激活提示词集：`POST /prompt-sets/{prompt_set_id}/activate`。
4. 查询或更新 AI 平台，保证至少一个平台 `enabled=true`。
5. 创建监测运行：`POST /runs`（可不传 `platform_codes`，使用项目默认平台）。
6. 查询运行任务：`GET /runs/{run_id}/query-tasks`。
7. 采集完成后查询答案：`GET /runs/{run_id}/answers`。
8. 运行终态后触发分析：`POST /runs/{run_id}/analyze`。
9. 查询分析结果：`GET /runs/{run_id}/analysis`。
10. 查询看板：`GET /projects/{project_id}/dashboard`。
11. 分析完成后生成报告：`POST /runs/{run_id}/reports`。
12. 下载报告：`GET /reports/{report_id}/download`。

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

## 15. 测试结果记录建议

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

## 16. 自动化全量测试

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

