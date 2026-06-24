# AI 应用监测 API 接口文档

> 文档依据当前后端源码整理（`backend/app/api/router.py`、`backend/app/main.py`、`backend/app/geo_monitoring/api/`）。  
> 更新日期：2026-06-22  
> 在线 OpenAPI：`http://127.0.0.1:8000/docs`

---

## 目录

- [1. 通用说明](#1-通用说明)
- [2. 公共数据模型](#2-公共数据模型)
- [3. 探针接口](#3-探针接口)
- [4. 监测项目](#4-监测项目)
- [5. 品牌与别名](#5-品牌与别名)
- [6. 核心词](#6-核心词)
- [7. Prompt 词库](#7-prompt-词库)
- [8. 监测设置](#8-监测设置)
- [9. 提示词集与提示词](#9-提示词集与提示词)
- [10. AI 平台](#10-ai-平台)
- [11. 监测运行与任务](#11-监测运行与任务)
- [12. 调度](#12-调度)
- [13. 采集答案](#13-采集答案)
- [14. 分析与 Agent 审计](#14-分析与-agent-审计)
- [15. 看板与趋势](#15-看板与趋势)
- [16. 报告](#16-报告)
- [附录 A：错误码](#附录-a错误码)
- [附录 B：状态枚举](#附录-b状态枚举)

---

## 1. 通用说明

### 1.1 服务地址与路径前缀

| 项目 | 值 |
| --- | --- |
| 默认 Base URL | `http://127.0.0.1:8000` |
| 全局 API 前缀 | `/api` |
| 监测业务主前缀 | `/api/geo-monitoring` |
| 兼容前缀 | `/api/v1/geo-monitoring`（与主前缀挂载同一组接口） |

下文路径均以 **主前缀** `/api/geo-monitoring` 为例；全局探针使用 `/api`。

### 1.2 请求头

| 请求头 | 必填 | 说明 |
| --- | --- | --- |
| `Content-Type` | Body 为 JSON 时必填 | 建议 `application/json` |
| `Accept` | 否 | 建议 `application/json` |
| `X-Request-ID` | 否 | 自定义请求追踪 ID |

响应头：

| 响应头 | 说明 |
| --- | --- |
| `X-Request-ID` | 本次请求 ID |
| `X-Response-Time-Ms` | 服务端处理耗时（毫秒） |

当前业务接口**未配置鉴权**，测试/联调无需 `Authorization`。

### 1.3 统一 JSON 响应

**普通接口：**

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

**分页接口：**

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

**失败响应（业务异常，HTTP 通常为 200）：**

```json
{
  "code": 40400,
  "message": "监测项目不存在",
  "data": null
}
```

**参数校验失败（HTTP 200，`code=422`）：**

```json
{
  "code": 422,
  "message": "参数校验失败",
  "data": []
}
```

### 1.4 分页 Query 通用约定

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | `1` | 页码，≥ 1 |
| `page_size` | integer | 各接口不同 | 每页条数，见各接口说明 |

---

## 2. 公共数据模型

以下模型在多个接口中复用，字段说明集中于此，各接口章节引用模型名称。

### 2.1 ProjectOut（项目）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 项目 ID |
| `project_name` | string | 项目名称 |
| `industry` | string | 行业 |
| `description` | string/null | 描述 |
| `timezone` | string | 时区，如 `Asia/Shanghai` |
| `status` | string | 项目状态，见[附录 B](#附录-b状态枚举) |
| `official_domain` | string/null | 官方域名 |
| `report_title` | string/null | 报告标题 |
| `report_subtitle` | string/null | 报告副标题 |
| `default_platform_codes` | string[] | 项目默认监测平台编码列表 |
| `created_at` | string (ISO8601) | 创建时间 |
| `updated_at` | string (ISO8601) | 更新时间 |

### 2.2 BrandOut（品牌）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 品牌 ID |
| `project_id` | integer | 所属项目 ID |
| `brand_name` | string | 品牌名称 |
| `brand_type` | string | `target` / `competitor` / `candidate` |
| `official_domain` | string/null | 官方域名 |
| `description` | string/null | 描述 |
| `status` | string | `active` / `disabled` |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.3 BrandAliasOut（品牌别名）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 别名 ID |
| `brand_id` | integer | 所属品牌 ID |
| `alias_name` | string | 别名文本 |
| `match_mode` | string | `exact` / `contains` / `context` |
| `is_ambiguous` | boolean | 是否歧义别名 |
| `context_keywords` | string[] | 上下文关键词（`context` 模式使用） |
| `enabled` | boolean | 是否启用 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.4 CoreKeywordOut（核心词）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 核心词 ID |
| `project_id` | integer | 所属项目 ID |
| `keyword` | string | 核心词 |
| `description` | string/null | 说明 |
| `sort_order` | integer | 排序 |
| `enabled` | boolean | 是否启用 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.5 PromptLibraryOut（Prompt 词库模板）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 模板 ID |
| `prompt_code` | string | 模板编码，如 `LIB_RECOMMEND_001` |
| `prompt_text` | string | 模板问题文本 |
| `prompt_type` | string | 问题类型 |
| `industry` | string/null | 适用行业 |
| `scene_tag` | string/null | 场景标签 |
| `default_core_keyword` | string/null | 默认核心词 |
| `enabled` | boolean | 是否启用 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.6 PromptSetOut（提示词集）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 提示词集 ID |
| `project_id` | integer | 所属项目 ID |
| `set_name` | string | 名称 |
| `version_no` | string | 版本号，同项目内唯一 |
| `status` | string | `draft` / `active` / `archived` |
| `prompt_count` | integer | 提示词数量 |
| `checksum` | string/null | 激活后内容校验和 |
| `activated_at` | string/null | 激活时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.7 PromptOut（提示词）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 提示词 ID |
| `prompt_set_id` | integer | 所属提示词集 ID |
| `prompt_code` | string | 编码，同集内唯一 |
| `prompt_text` | string | 问题正文 |
| `prompt_type` | string | 如 `generic`、`recommendation`、`comparison`、`brand_visibility` |
| `scene_tag` | string/null | 场景标签 |
| `contains_brand` | boolean | 是否包含品牌 |
| `core_keyword_id` | integer/null | 关联核心词 ID |
| `enabled` | boolean | 是否启用 |
| `sort_order` | integer | 排序 |
| `content_hash` | string/null | 内容哈希 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.8 AIPlatformOut（AI 平台）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 平台 ID |
| `platform_code` | string | 平台编码，如 `qwen`、`deepseek` |
| `platform_name` | string | 平台名称 |
| `adapter_type` | string | 适配器类型 |
| `base_url` | string/null | API 地址 |
| `model_name` | string/null | 模型名称 |
| `search_enabled` | boolean | 是否启用联网搜索 |
| `citation_supported` | boolean | 是否支持引用 |
| `max_concurrency` | integer | 最大并发 |
| `timeout_seconds` | integer | 超时秒数 |
| `enabled` | boolean | 是否启用 |
| `extra_config` | object | 扩展配置 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.9 MonitorRunOut（监测运行）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 运行 ID |
| `run_no` | string | 运行编号 |
| `project_id` | integer | 项目 ID |
| `prompt_set_id` | integer | 使用的提示词集 ID |
| `prompt_set_version` | string | 提示词集版本号 |
| `trigger_type` | string | 触发类型，如 `manual`、`schedule` |
| `triggered_by` | integer/null | 触发来源 ID |
| `status` | string | 运行总状态 |
| `collection_status` | string | 采集阶段状态 |
| `analysis_status` | string | 分析阶段状态 |
| `report_status` | string | 报告阶段状态 |
| `collection_source` | string | 采集来源：`official` / `aidso` |
| `aidso_thinking_enabled_by_platform` | object | Aidso 数据源各平台端侧是否开启深度思考，键为平台编码，值为 boolean；未配置的平台默认开启 |
| `platform_codes` | string[] | 参与采集的平台 |
| `expected_query_count` | integer | 预期查询数 |
| `total_tasks` | integer | 总任务数 |
| `succeeded_tasks` | integer | 成功任务数 |
| `failed_tasks` | integer | 失败任务数 |
| `cancelled_tasks` | integer | 取消任务数 |
| `success_query_count` | integer | 成功查询数 |
| `failed_query_count` | integer | 失败查询数 |
| `valid_answer_count` | integer | 有效答案数 |
| `data_completeness_rate` | string (decimal) | 数据完整率 |
| `result_json` | object/null | 汇总结果 JSON |
| `error_message` | string/null | 错误信息 |
| `error_summary` | string/null | 错误摘要 |
| `started_at` | string/null | 开始时间 |
| `completed_at` | string/null | 完成时间 |
| `finished_at` | string/null | 结束时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

运行详情在此基础上额外包含 `progress_rate`（任务进度比例，decimal 字符串）。

### 2.10 QueryTaskOut（查询任务）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 任务 ID |
| `run_id` | integer | 所属运行 ID |
| `prompt_id` | integer | 提示词 ID |
| `platform_code` | string | 平台编码 |
| `idempotency_key` | string | 幂等键 |
| `status` | string | 任务状态 |
| `key_slot` | integer/null | API Key 槽位 |
| `retry_count` | integer | 重试次数 |
| `attempt_count` | integer | 已尝试次数 |
| `max_attempts` | integer | 最大尝试次数 |
| `request_json` | object/null | 请求快照 |
| `response_http_status` | integer/null | 上游 HTTP 状态 |
| `error_code` | string/null | 错误码 |
| `error_message` | string/null | 错误信息 |
| `last_error_code` | string/null | 最近一次错误码 |
| `last_error_message` | string/null | 最近一次错误信息 |
| `provider_request_id` | string/null | 上游请求 ID |
| `latency_ms` | integer/null | 延迟毫秒 |
| `queued_at` | string/null | 入队时间 |
| `started_at` | string/null | 开始时间 |
| `completed_at` | string/null | 完成时间 |
| `finished_at` | string/null | 结束时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.11 AnswerRead / AnswerDetailRead（答案）

`AnswerRead` 字段：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 答案 ID |
| `task_id` | integer | 关联任务 ID |
| `platform_code` | string | 平台编码 |
| `prompt_id` | integer | 提示词 ID |
| `raw_text` | string | 原始回答文本 |
| `normalized_text` | string/null | 规范化文本 |
| `model_name` | string/null | 模型名称 |
| `prompt_tokens` | integer | Prompt Token 数 |
| `completion_tokens` | integer | 完成 Token 数 |
| `total_tokens` | integer | 总 Token 数 |
| `latency_ms` | integer/null | 延迟毫秒 |
| `collected_at` | string | 采集时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

`AnswerDetailRead` 额外包含：

- `citations[]`：引用列表（`citation_no`、`title`、`url`、`domain`、`source_type`、`quoted_text`）
- `brand_results[]`：品牌识别（`brand_id`、`is_mentioned`、`mention_count`、`first_position`、`sentiment`、`context_json`）

### 2.12 ScheduleOut（调度）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 调度 ID |
| `project_id` | integer | 项目 ID |
| `name` | string | 调度名称，同项目内唯一 |
| `cron_expr` | string | Cron 表达式 |
| `timezone` | string | 时区 |
| `enabled` | boolean | 是否启用 |
| `misfire_policy` | string | `fire_once` / `ignore` |
| `next_run_at` | string/null | 下次执行时间 |
| `last_run_at` | string/null | 上次执行时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

### 2.13 ReportOut（报告元数据）

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | integer | 报告 ID |
| `project_id` | integer | 项目 ID |
| `run_id` | integer | 运行 ID |
| `status` | string | 报告状态 |
| `format` | string | `md` / `html` / `pdf` |
| `file_name` | string | 文件名 |
| `relative_storage_path` | string | 相对存储路径 |
| `file_size` | integer/null | 文件大小（字节） |
| `checksum` | string/null | 文件校验和 |
| `error_message` | string/null | 错误信息 |
| `completed_at` | string/null | 完成时间 |
| `created_at` | string | 创建时间 |
| `updated_at` | string | 更新时间 |

---

## 3. 探针接口

### 3.1 全局健康检查

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 全局健康检查 |
| **请求方式** | `GET` |
| **接口路径** | `/api/health` |

**入参：** 无

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | 固定 `ok` |
| `app` | string | 应用名称 |
| `env` | string | 运行环境 |

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/health"
```

**响应示例：**

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "status": "ok",
    "app": "ai-application-monitoring",
    "env": "dev"
  }
}
```

---

### 3.2 全局就绪检查

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 全局就绪检查 |
| **请求方式** | `GET` |
| **接口路径** | `/api/ready` |

**入参：** 无

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ready` 或 `not_ready` |
| `database` | object | `{ "ok": bool, "target": string }` |
| `redis` | object | `{ "ok": bool, "target": string }` |

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/ready"
```

---

### 3.3 监测服务健康检查

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 监测服务健康检查 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/health` |

**入参：** 无

**出参：** 同 [3.1](#31-全局健康检查)

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/geo-monitoring/health"
```

---

### 3.4 监测服务就绪检查

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 监测服务就绪检查 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/ready` |

**入参：** 无

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `status` | string | `ready` 或 `not_ready` |
| `database` | object | 数据库探测结果 |
| `redis` | object | Redis 探测结果 |
| `nacos` | object | 仅 `NACOS_ENABLED=true` 时返回 |

**HTTP 状态码：** 就绪时 `200`；未就绪时 `503`（响应体仍为统一 JSON）

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/geo-monitoring/ready"
```

---

## 4. 监测项目

### 4.1 分页查询监测项目

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询监测项目 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects` |

**Query 入参：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `page` | integer | 否 | `1` | 页码 |
| `page_size` | integer | 否 | `10` | 每页条数，1–100 |
| `project_name` | string | 否 | — | 项目名称模糊筛选 |
| `status` | string | 否 | — | `active` / `disabled` / `archived` |

**出参：** 分页结构，`items` 为 [ProjectOut](#21-projectout项目) 数组

**调用示例：**

```bash
curl -G "http://127.0.0.1:8000/api/geo-monitoring/projects" \
  --data-urlencode "page=1" \
  --data-urlencode "page_size=10" \
  --data-urlencode "status=active"
```

---

### 4.2 创建监测项目

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建监测项目 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/projects` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `project_name` | string | 是 | — | 项目名称，最大 100 |
| `industry` | string | 否 | `文旅演艺` | 行业 |
| `description` | string/null | 否 | — | 描述 |
| `timezone` | string | 否 | `Asia/Shanghai` | 时区 |
| `official_domain` | string/null | 否 | — | 官方域名 |
| `report_title` | string/null | 否 | — | 报告标题 |
| `report_subtitle` | string/null | 否 | — | 报告副标题 |

**出参 `data`：** [ProjectOut](#21-projectout项目)

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/projects" \
  -H "Content-Type: application/json" \
  -d '{"project_name":"杭州宋城文旅监测","industry":"文旅演艺","timezone":"Asia/Shanghai"}'
```

---

### 4.3 获取监测项目

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取监测项目 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}` |

**Path 入参：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | integer | 是 | 项目 ID，≥ 1 |

**出参 `data`：** [ProjectOut](#21-projectout项目)

**常见错误：** `40400` 项目不存在

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/geo-monitoring/projects/1"
```

---

### 4.4 更新监测项目

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新监测项目 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}` |

**Path 入参：** `project_id`（integer，≥ 1）

**Body 入参（均为可选）：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_name` | string | 项目名称 |
| `industry` | string | 行业 |
| `description` | string/null | 描述 |
| `timezone` | string | 时区 |
| `status` | string | `active` / `disabled` / `archived` |
| `official_domain` | string/null | 官方域名 |
| `report_title` | string/null | 报告标题 |
| `report_subtitle` | string/null | 报告副标题 |

**出参 `data`：** [ProjectOut](#21-projectout项目)

**调用示例：**

```bash
curl -X PUT "http://127.0.0.1:8000/api/geo-monitoring/projects/1" \
  -H "Content-Type: application/json" \
  -d '{"status":"active","description":"更新描述"}'
```

---

### 4.5 删除监测项目

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除监测项目 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}` |

**Path 入参：** `project_id`（integer，≥ 1）

**出参 `data`：** `{ "id": <project_id> }`

**常见错误：** 项目已被运行引用时 HTTP `409`，`code=40903`

**调用示例：**

```bash
curl -X DELETE "http://127.0.0.1:8000/api/geo-monitoring/projects/1"
```

---

## 5. 品牌与别名

### 5.1 分页查询项目品牌

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询项目品牌 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/brands` |

**Path 入参：** `project_id`（integer，≥ 1）

**Query 入参：**

| 参数 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `page` | integer | 否 | `1` | 页码 |
| `page_size` | integer | 否 | `10` | 1–100 |
| `brand_name` | string | 否 | — | 品牌名筛选 |
| `brand_type` | string | 否 | — | `target` / `competitor` / `candidate` |
| `status` | string | 否 | — | `active` / `disabled` |

**出参：** 分页 [BrandOut](#22-brandout品牌) 列表

**常见错误：** `40400` 项目不存在；`40001` 项目未启用

---

### 5.2 创建项目品牌

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建项目品牌 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/brands` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `brand_name` | string | 是 | — | 品牌名称 |
| `brand_type` | string | 否 | `competitor` | 品牌类型 |
| `official_domain` | string/null | 否 | — | 官方域名 |
| `description` | string/null | 否 | — | 描述 |
| `status` | string | 否 | `active` | 实体状态 |

**出参 `data`：** [BrandOut](#22-brandout品牌)

**常见错误：** `40010` 目标品牌重复；`40012` 同项目品牌名重复

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/projects/1/brands" \
  -H "Content-Type: application/json" \
  -d '{"brand_name":"杭州宋城","brand_type":"target"}'
```

---

### 5.3 获取品牌

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取品牌 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/brands/{brand_id}` |

**Path 入参：** `brand_id`（integer，≥ 1）

**出参 `data`：** [BrandOut](#22-brandout品牌)

---

### 5.4 更新品牌

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新品牌 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/brands/{brand_id}` |

**Body 入参（均可选）：** `brand_name`、`brand_type`、`official_domain`、`description`、`status`

**出参 `data`：** [BrandOut](#22-brandout品牌)

---

### 5.5 删除品牌

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除品牌 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/brands/{brand_id}` |

**出参 `data`：** `{ "id": <brand_id> }`

**常见错误：** 品牌已被答案引用 HTTP `409`，`code=40905`

---

### 5.6 分页查询品牌别名

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询品牌别名 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/brands/{brand_id}/aliases` |

**Query 入参：** `page`（默认 1）、`page_size`（默认 10，1–100）

**出参：** 分页 [BrandAliasOut](#23-brandaliasout品牌别名) 列表

---

### 5.7 创建品牌别名

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建品牌别名 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/brands/{brand_id}/aliases` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `alias_name` | string | 是 | — | 别名 |
| `match_mode` | string | 否 | `contains` | 匹配模式 |
| `is_ambiguous` | boolean | 否 | `false` | 是否歧义 |
| `context_keywords` | string[] | 否 | `[]` | 上下文关键词 |
| `enabled` | boolean | 否 | `true` | 是否启用 |

**出参 `data`：** [BrandAliasOut](#23-brandaliasout品牌别名)

**常见错误：** `40011` 同品牌别名重复

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/brands/1/aliases" \
  -H "Content-Type: application/json" \
  -d '{"alias_name":"宋城","match_mode":"contains"}'
```

---

### 5.8 更新品牌别名

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新品牌别名 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/brand-aliases/{alias_id}` |

**Body 入参（均可选）：** `alias_name`、`match_mode`、`is_ambiguous`、`context_keywords`、`enabled`

**出参 `data`：** [BrandAliasOut](#23-brandaliasout品牌别名)

---

### 5.9 删除品牌别名

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除品牌别名 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/brand-aliases/{alias_id}` |

**出参 `data`：** `{ "id": <alias_id> }`

---

## 6. 核心词

### 6.1 分页查询项目核心词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询项目核心词 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/core-keywords` |

**Query 入参：**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | `1` | 页码 |
| `page_size` | integer | `100` | 1–500 |
| `enabled` | boolean | — | 按启用状态筛选 |

**出参：** 分页 [CoreKeywordOut](#24-corekeywordout核心词) 列表

---

### 6.2 创建项目核心词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建项目核心词 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/core-keywords` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `keyword` | string | 是 | — | 核心词，最大 100 |
| `description` | string/null | 否 | — | 说明 |
| `sort_order` | integer | 否 | `0` | 排序 |
| `enabled` | boolean | 否 | `true` | 是否启用 |

**出参 `data`：** [CoreKeywordOut](#24-corekeywordout核心词)

**常见错误：** `40024` 同项目核心词重复

---

### 6.3 更新核心词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新核心词 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/core-keywords/{keyword_id}` |

**Body 入参（均可选）：** `keyword`、`description`、`sort_order`、`enabled`

**出参 `data`：** [CoreKeywordOut](#24-corekeywordout核心词)

---

### 6.4 删除核心词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除核心词 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/core-keywords/{keyword_id}` |

**出参 `data`：** `{ "id": <keyword_id> }`

---

## 7. Prompt 词库

### 7.1 分页查询 Prompt 词库

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询 Prompt 词库 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/prompt-library` |

**Query 入参：**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | `1` | 页码 |
| `page_size` | integer | `100` | 1–500 |
| `industry` | string | — | 按行业筛选 |

**出参：** 分页 [PromptLibraryOut](#25-promptlibraryoutprompt-词库模板) 列表

**调用示例：**

```bash
curl -G "http://127.0.0.1:8000/api/geo-monitoring/prompt-library" \
  --data-urlencode "industry=文旅演艺"
```

---

## 8. 监测设置

一次性配置目标品牌、竞品、核心词、AI 问题与监测平台。

### 8.1 获取监测设置

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取监测设置 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/monitor-setup` |

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `brand` | object/null | 目标品牌：`id`、`brand_name`、`official_domain`、`description`、`brand_words[]` |
| `competitors` | array | 竞品列表，含 `competitor_words[]` |
| `core_keywords` | array | 核心词列表 |
| `ai_questions` | array | AI 问题，含 `prompt_type`、`core_keyword`、`from_library` 等 |
| `available_platforms` | array | 可用平台摘要 |
| `selected_platform_codes` | string[] | 已选默认平台 |
| `draft_prompt_set_id` | integer/null | 草稿问题集 ID |
| `active_prompt_set_id` | integer/null | 激活问题集 ID |

---

### 8.2 保存监测设置

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 保存监测设置 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/monitor-setup` |

**Body 入参：**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `brand` | object | 否 | 目标品牌：`brand_name`、`official_domain`、`description`、`brand_words[]` |
| `competitors` | array | 否 | 竞品：`brand_name`、`competitor_words[]` |
| `core_keywords` | array | 否 | 核心词：`keyword`、`description`、`sort_order`、`enabled` |
| `ai_questions` | array | 否 | 问题：可填 `prompt_text` 或引用 `library_prompt_code` |
| `selected_platform_codes` | string[] | 否 | 监测平台编码 |
| `activate_prompt_set` | boolean | 否 | 默认 `false`；为 `true` 时保存后激活草稿问题集 |

**出参 `data`：** 同 [8.1 获取监测设置](#81-获取监测设置)

**常见错误：** `40028` 缺少品牌；`40025` 平台不可用；`40026` 问题文本为空；`40027` 核心词不存在

**调用示例：**

```bash
curl -X PUT "http://127.0.0.1:8000/api/geo-monitoring/projects/1/monitor-setup" \
  -H "Content-Type: application/json" \
  -d '{
    "brand": {
      "brand_name": "杭州宋城",
      "brand_words": ["宋城", "SEP"]
    },
    "core_keywords": [{"keyword": "环境检测", "sort_order": 1}],
    "ai_questions": [
      {"core_keyword": "环境检测", "prompt_text": "推荐国内靠谱的环境检测机构有哪些？"}
    ],
    "selected_platform_codes": ["qwen", "deepseek"],
    "activate_prompt_set": true
  }'
```

---

## 9. 提示词集与提示词

### 9.1 分页查询提示词集

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询提示词集 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/prompt-sets` |

**Query 入参：** `page`、`page_size`（默认 10）、`status`（`draft`/`active`/`archived`）

**出参：** 分页 [PromptSetOut](#26-promptsetout提示词集) 列表

---

### 9.2 创建提示词集

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建提示词集 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/prompt-sets` |

**Body 入参：**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `set_name` | string | 是 | 名称，最大 100 |
| `version_no` | string | 是 | 版本号，同项目唯一 |

**出参 `data`：** [PromptSetOut](#26-promptsetout提示词集)（默认 `status=draft`）

**常见错误：** `40023` 版本号重复

---

### 9.3 获取提示词集

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取提示词集 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/prompt-sets/{prompt_set_id}` |

**出参 `data`：** [PromptSetOut](#26-promptsetout提示词集)

---

### 9.4 更新提示词集

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新提示词集 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/prompt-sets/{prompt_set_id}` |

**Body 入参：** `set_name`（可选，仅草稿状态可改）

**常见错误：** `40020` 非草稿不可修改

---

### 9.5 删除提示词集

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除提示词集 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/prompt-sets/{prompt_set_id}` |

**出参 `data`：** `{ "id": <prompt_set_id> }`

**常见错误：** 已被运行引用 HTTP `409`，`code=40906`；非草稿 `40020`

---

### 9.6 激活提示词集

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 激活提示词集 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/prompt-sets/{prompt_set_id}/activate` |

**入参：** 无 Body

**出参 `data`：** [PromptSetOut](#26-promptsetout提示词集)（`status=active`）

**常见错误：** `40022` 空提示词集；`40020` 非草稿

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/prompt-sets/1/activate"
```

---

### 9.7 分页查询提示词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询提示词 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts` |

**Query 入参：** `page`（默认 1）、`page_size`（默认 100，1–500）

**出参：** 分页 [PromptOut](#27-promptout提示词) 列表

---

### 9.8 创建提示词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建提示词 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/prompt-sets/{prompt_set_id}/prompts` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `prompt_code` | string | 是 | — | 编码，同集唯一 |
| `prompt_text` | string | 是 | — | 问题正文 |
| `prompt_type` | string | 否 | `generic` | 问题类型 |
| `scene_tag` | string/null | 否 | — | 场景标签 |
| `contains_brand` | boolean | 否 | `false` | 是否含品牌 |
| `core_keyword_id` | integer/null | 否 | — | 关联核心词 |
| `enabled` | boolean | 否 | `true` | 是否启用 |
| `sort_order` | integer | 否 | `0` | 排序 |

**常见错误：** `40020` 非草稿集；`40021` 编码重复

---

### 9.9 更新提示词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新提示词 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/prompts/{prompt_id}` |

**Body 入参：** 同创建字段，均可选

**出参 `data`：** [PromptOut](#27-promptout提示词)

---

### 9.10 删除提示词

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除提示词 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/prompts/{prompt_id}` |

**常见错误：** 已被查询任务引用 HTTP `409`，`code=40907`

---

## 10. AI 平台

官方平台编码：`doubao`、`qwen`、`yuanbao`、`deepseek`、`kimi`。

Aidso 第三方数据源端侧平台编码：

| 平台编码 | 说明 |
| --- | --- |
| `aidso_doubao_web` | 豆包 Web 端 |
| `aidso_doubao_app` | 豆包 App 端 |
| `aidso_deepseek_web` | DeepSeek Web 端 |
| `aidso_deepseek_app` | DeepSeek App 端 |
| `aidso_kimi_web` | Kimi Web 端 |
| `aidso_yuanbao_web` | 元宝 Web 端 |
| `aidso_yuanbao_app` | 元宝 App 端 |
| `aidso_qwen_web` | 千问 Web 端 |
| `aidso_qwen_app` | 千问 App 端 |
| `aidso_baidu_web` | 百度 AI |
| `aidso_douyin_web` | 抖音 AI |
| `aidso_wenxin_web` | 文心一言 |

### 10.1 分页查询 AI 平台

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询 AI 平台 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/platforms` |

**Query 入参：** `page`、`page_size`（默认 10）、`enabled`（boolean，可选）

**出参：** 分页 [AIPlatformOut](#28-aiplatformoutai-平台) 列表

---

### 10.2 获取 AI 平台配置

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取 AI 平台配置 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/platforms/{platform_code}` |

**Path 入参：** `platform_code`（string，1–32 字符）

**出参 `data`：** [AIPlatformOut](#28-aiplatformoutai-平台)

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/geo-monitoring/platforms/qwen"
```

---

### 10.3 更新 AI 平台配置

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新 AI 平台配置 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/platforms/{platform_code}` |

**Body 入参（均可选）：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `platform_name` | string | 平台名称 |
| `adapter_type` | string | 适配器类型 |
| `base_url` | string/null | API 地址 |
| `model_name` | string/null | 模型名 |
| `search_enabled` | boolean | 联网搜索 |
| `citation_supported` | boolean | 引用支持 |
| `max_concurrency` | integer | 须 > 0 |
| `timeout_seconds` | integer | 须 > 0 |
| `enabled` | boolean | 是否启用 |
| `extra_config` | object/null | 扩展配置 |

**调用示例：**

```bash
curl -X PUT "http://127.0.0.1:8000/api/geo-monitoring/platforms/qwen" \
  -H "Content-Type: application/json" \
  -d '{"enabled": true, "max_concurrency": 5}'
```

---

## 11. 监测运行与任务

### 11.1 分页查询监测运行

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询监测运行 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs` |

**Query 入参：**

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `page` | integer | 页码，默认 1 |
| `page_size` | integer | 默认 10，1–100 |
| `project_id` | integer | 按项目筛选 |
| `status` | string | 运行状态 |
| `created_after` | datetime | 创建时间下限（ISO8601） |
| `created_before` | datetime | 创建时间上限 |

**出参：** 分页 [MonitorRunOut](#29-monitorrunout监测运行) 列表

---

### 11.2 创建监测运行

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建监测运行 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/runs` |

**Body 入参：**

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `project_id` | integer | 是 | 项目 ID，≥ 1 |
| `prompt_set_id` | integer/null | 否 | 指定提示词集；不传则用激活集 |
| `collection_source` | string | 否 | 采集来源，默认 `official`；可选 `official` / `aidso` |
| `aidso_thinking_enabled_by_platform` | object | 否 | Aidso 数据源各平台端侧是否开启深度思考，键为平台编码，值为 boolean；未配置的平台默认开启 |
| `platform_codes` | string[]/null | 否 | 指定平台；不传则用项目默认或全部启用平台 |

**出参 `data`：** [MonitorRunOut](#29-monitorrunout监测运行)

**常见错误：** `40030` 无激活提示词集；`40901` 无可用提示词；`40031`/`40902` 无可用平台

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/runs" \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "platform_codes": ["qwen", "deepseek"]}'
```

Aidso 数据源示例：

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/runs" \
  -H "Content-Type: application/json" \
  -d '{"project_id": 1, "collection_source": "aidso", "aidso_thinking_enabled_by_platform": {"aidso_doubao_web": false, "aidso_doubao_app": true}, "platform_codes": ["aidso_doubao_web", "aidso_doubao_app"]}'
```

---

### 11.3 获取监测运行详情

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取监测运行详情 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}` |

**出参 `data`：** [MonitorRunOut](#29-monitorrunout监测运行) + `progress_rate`

---

### 11.4 取消监测运行

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 取消监测运行 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/cancel` |

**入参：** 无 Body

**出参 `data`：** [MonitorRunOut](#29-monitorrunout监测运行)（`status=cancelled` 或保持终态）

---

### 11.5 重试失败任务

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 重试失败任务 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/retry-failed` |

**出参 `data`：** [MonitorRunOut](#29-monitorrunout监测运行) + `retried_count`（本次重置的失败任务数）

**常见错误：** `40040` 已取消运行不可重试

---

### 11.6 分页查询运行任务

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询运行任务 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/query-tasks` |

**Query 入参：**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | `1` | 页码 |
| `page_size` | integer | `100` | 1–500 |
| `status` | string | — | 任务状态 |
| `platform_code` | string | — | 平台编码 |

**出参：** 分页 [QueryTaskOut](#210-querytaskout查询任务) 列表

---

### 11.7 分页查询运行任务（别名）

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询运行任务（别名） |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/tasks` |

**说明：** 与 [11.6](#116-分页查询运行任务) 入参、出参完全一致，为兼容别名路由。

---

## 12. 调度

### 12.1 分页查询项目调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询项目调度 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/schedules` |

**出参：** 分页 [ScheduleOut](#212-scheduleout调度) 列表

---

### 12.2 创建监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建监测调度 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/schedules` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `name` | string | 是 | — | 调度名称，同项目唯一 |
| `cron_expr` | string | 是 | — | Cron 表达式 |
| `timezone` | string | 否 | `Asia/Shanghai` | 时区 |
| `enabled` | boolean | 否 | `true` | 是否启用 |
| `misfire_policy` | string | 否 | `fire_once` | 错过策略 |

**常见错误：** `40050` cron 无效；`40051` 时区无效；`40904` 名称重复

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/projects/1/schedules" \
  -H "Content-Type: application/json" \
  -d '{"name":"每日监测","cron_expr":"0 9 * * *","timezone":"Asia/Shanghai"}'
```

---

### 12.3 获取监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取监测调度 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/schedules/{schedule_id}` |

**出参 `data`：** [ScheduleOut](#212-scheduleout调度)

---

### 12.4 更新监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 更新监测调度 |
| **请求方式** | `PUT` |
| **接口路径** | `/api/geo-monitoring/schedules/{schedule_id}` |

**Body 入参（均可选）：** `name`、`cron_expr`、`timezone`、`enabled`、`misfire_policy`

---

### 12.5 删除监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除监测调度 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/schedules/{schedule_id}` |

**出参 `data`：** `{}`

---

### 12.6 启用监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 启用监测调度 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/schedules/{schedule_id}/enable` |

**出参 `data`：** [ScheduleOut](#212-scheduleout调度)（`enabled=true`）

---

### 12.7 停用监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 停用监测调度 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/schedules/{schedule_id}/disable` |

**出参 `data`：** [ScheduleOut](#212-scheduleout调度)（`enabled=false`）

---

### 12.8 立即触发监测调度

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 立即触发监测调度 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/schedules/{schedule_id}/trigger` |

**出参 `data`：** [MonitorRunOut](#29-monitorrunout监测运行)（`trigger_type=schedule`）

---

## 13. 采集答案

### 13.1 分页查询运行答案

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询运行答案 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/answers` |

**Query 入参：** `page`（默认 1）、`page_size`（默认 10）

**出参：** 分页 [AnswerRead](#211-answerread--answerdetailread答案) 列表

---

### 13.2 获取答案详情

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取答案详情 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/answers/{answer_id}` |

**出参 `data`：** [AnswerDetailRead](#211-answerread--answerdetailread答案)（含引用与品牌识别）

**调用示例：**

```bash
curl -X GET "http://127.0.0.1:8000/api/geo-monitoring/answers/1"
```

---

## 14. 分析与 Agent 审计

### 14.1 手工触发或重跑分析

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 手工触发或重跑分析 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/analyze` |

**入参：** 无 Body

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | integer | 运行 ID |
| `analysis_status` | string | 本次分析结果状态 |
| `skip_reason` | string/null | 跳过原因 |
| `run_analysis_status` | string | 运行当前分析状态 |

**常见错误：** 采集未完成 HTTP `409`，`code=40910`

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/runs/1/analyze"
```

---

### 14.2 获取运行平台指标与洞察

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取运行平台指标与洞察 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/analysis` |

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | integer | 运行 ID |
| `analysis_status` | string | 分析状态 |
| `platforms` | array | 各平台分析结果 |

**`platforms[]` 元素字段：**

| 字段 | 说明 |
| --- | --- |
| `platform_code` | 平台编码 |
| `status` | 分析状态 |
| `valid_answer_count` | 有效答案数 |
| `data_completeness_rate` | 数据完整率 |
| `brand_mention_count` / `brand_mention_rate` | 品牌提及次数/率 |
| `brand_first_count` / `brand_first_rate` | 品牌首推次数/率 |
| `brand_first_among_mentions_rate` | 提及中首推率 |
| `top_competitors` | 主要竞品 JSON |
| `top_sources` | 主要引用来源 JSON |
| `prompt_competitiveness_summary` | 问题竞争力摘要 |
| `improvement_json` | 改进建议 JSON |
| `summary_json` | 汇总 JSON |

---

### 14.3 分页查询 Agent 执行审计

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询 Agent 执行审计 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/agent-executions` |

**Query 入参：**

| 参数 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `page` | integer | `1` | 页码 |
| `page_size` | integer | `50` | 1–200 |
| `platform_code` | string | — | 平台筛选 |
| `agent_code` | string | — | Agent 编码筛选 |

**出参 `items[]` 字段：**

`id`、`run_id`、`platform_code`、`agent_code`、`status`、`schema_version`、`input_snapshot`、`output_json`、`model_name`、`prompt_version`、`prompt_tokens`、`completion_tokens`、`error_message`、`started_at`、`finished_at`

---

## 15. 看板与趋势

### 15.1 获取项目最新分析汇总

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取项目最新分析汇总 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/dashboard` |

**Query 入参：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `run_id` | integer | 否 | 指定运行 ID；不传则取最近已分析或已采集运行 |

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `project_id` | integer | 项目 ID |
| `latest_run` | object/null | 最近运行摘要 |
| `summary` | object/null | 跨平台汇总指标（分析完成后） |
| `platforms` | array | 分平台采集/分析明细 |

**`latest_run` 字段：** `run_id`、`run_no`、`status`、`collection_status`、`analysis_status`、`platform_codes`、`valid_answer_count`、`data_completeness_rate`、任务计数、`completed_at`

**调用示例：**

```bash
curl -G "http://127.0.0.1:8000/api/geo-monitoring/projects/1/dashboard" \
  --data-urlencode "run_id=1"
```

---

### 15.2 按指标查询趋势

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 按指标、平台和时间范围查询趋势 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/projects/{project_id}/trends` |

**Query 入参：**

| 参数 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `metric_code` | string | **是** | 指标编码 |
| `platform_code` | string | 否 | 平台编码 |
| `start_at` | datetime | 否 | 起始时间 |
| `end_at` | datetime | 否 | 结束时间 |
| `page` | integer | 否 | 默认 1 |
| `page_size` | integer | 否 | 默认 50，1–200 |

**出参 `items[]` 字段：**

| 字段 | 说明 |
| --- | --- |
| `run_id` | 运行 ID |
| `platform_code` | 平台编码 |
| `metric_code` | 指标编码 |
| `numerator` / `denominator` | 分子/分母 |
| `metric_value` | 指标值 |
| `prompt_set_version` | 提示词集版本 |
| `snapshot_at` | 快照时间 |
| `completeness_rate` | 完整率 |

**调用示例：**

```bash
curl -G "http://127.0.0.1:8000/api/geo-monitoring/projects/1/trends" \
  --data-urlencode "metric_code=brand_mention_rate"
```

---

## 16. 报告

### 16.1 创建并生成监测报告

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 创建并生成监测报告 |
| **请求方式** | `POST` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/reports` |

**Body 入参：**

| 字段 | 类型 | 必填 | 默认 | 说明 |
| --- | --- | --- | --- | --- |
| `formats` | string[] | 否 | `["md","html"]` | 支持 `md`、`html`、`pdf`，自动去重 |

**出参 `data` 字段：**

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `run_id` | integer | 运行 ID |
| `reports` | array | [ReportOut](#213-reportout报告元数据) 列表 |

**常见错误：** 分析未完成 HTTP `409`，`code=40920`；格式不支持 `40060`

**调用示例：**

```bash
curl -X POST "http://127.0.0.1:8000/api/geo-monitoring/runs/1/reports" \
  -H "Content-Type: application/json" \
  -d '{"formats": ["md", "html", "pdf"]}'
```

---

### 16.2 分页查询运行报告

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 分页查询运行报告 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/runs/{run_id}/reports` |

**Query 入参：** `page`（默认 1）、`page_size`（默认 20，1–100）

**出参：** 分页 [ReportOut](#213-reportout报告元数据) 列表

---

### 16.3 获取报告状态与元数据

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 获取报告状态与元数据 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/reports/{report_id}` |

**出参 `data`：** [ReportOut](#213-reportout报告元数据)

**常见错误：** HTTP `404`，`code=40420`

---

### 16.4 下载报告文件

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 下载报告文件 |
| **请求方式** | `GET` |
| **接口路径** | `/api/geo-monitoring/reports/{report_id}/download` |

**入参：** 无

**出参：** **非 JSON**，返回文件二进制/文本流

| 响应头 | 说明 |
| --- | --- |
| `Content-Type` | `text/markdown; charset=utf-8`、`text/html; charset=utf-8` 或 `application/pdf` |
| `Content-Disposition` | `attachment; filename="<file_name>"` |

**常见错误：** 报告未生成完成 HTTP `409`，`code=40921`

**调用示例：**

```bash
curl -O -J "http://127.0.0.1:8000/api/geo-monitoring/reports/1/download"
```

---

### 16.5 删除报告

| 项目 | 说明 |
| --- | --- |
| **接口名称** | 删除报告 |
| **请求方式** | `DELETE` |
| **接口路径** | `/api/geo-monitoring/reports/{report_id}` |

**出参 `data`：** 被删除报告的 [ReportOut](#213-reportout报告元数据)

---

## 附录 A：错误码

| code | HTTP | 说明 |
| --- | --- | --- |
| `0` | 200 | 成功 |
| `422` | 200 | 参数校验失败 |
| `40001` | 200 | 项目未启用 |
| `40010` | 200 | 目标品牌重复 |
| `40011` | 200 | 品牌别名重复 |
| `40012` | 200 | 品牌名重复 |
| `40020` | 200 | 非草稿提示词集不可修改 |
| `40021` | 200 | 提示词编码重复 |
| `40022` | 200 | 空提示词集不可激活 |
| `40023` | 200 | 提示词集版本重复 |
| `40024` | 200 | 核心词重复 |
| `40025` | 200 | 监测平台不可用 |
| `40026` | 200 | AI 问题文本为空 |
| `40027` | 200 | 核心词不存在 |
| `40028` | 200 | 监测设置缺少品牌 |
| `40030` | 200 | 无激活提示词集 |
| `40031` | 200 | AI 平台不可用 |
| `40040` | 200 | 已取消运行不可重试 |
| `40050` | 200 | Cron 表达式无效 |
| `40051` | 200 | 时区无效 |
| `40060` | 200 | 报告格式不支持 |
| `40400` | 200 | 资源不存在（项目/品牌/运行等） |
| `40420` | 404 | 报告不存在 |
| `40901` | 409 | 无可用提示词 |
| `40902` | 409 | 无可用平台 |
| `40903` | 409 | 项目已被运行引用 |
| `40904` | 409 | 调度名称重复 |
| `40905` | 409 | 品牌已被答案引用 |
| `40906` | 409 | 提示词集已被运行引用 |
| `40907` | 409 | 提示词已被任务引用 |
| `40910` | 409 | 采集未完成，不可分析 |
| `40920` | 409 | 分析未完成，不可生成报告 |
| `40921` | 409 | 报告未生成完成，不可下载 |
| `500` | 500 | 服务器内部错误 |

---

## 附录 B：状态枚举

| 枚举 | 可选值 |
| --- | --- |
| 项目状态 | `active`、`disabled`、`archived` |
| 品牌类型 | `target`、`competitor`、`candidate` |
| 实体状态 | `active`、`disabled` |
| 别名匹配模式 | `exact`、`contains`、`context` |
| 提示词集状态 | `draft`、`active`、`archived` |
| 运行状态 | `pending`、`collecting`、`analyzing`、`reporting`、`completed`、`partial_success`、`failed`、`cancelled` |
| 查询任务状态 | `pending`、`queued`、`running`、`success`、`failed`、`cancelled` |
| 调度错过策略 | `fire_once`、`ignore` |

---

## 相关文档

- 接口测试说明与用例：[API测试文档.md](./API测试文档.md)
- 全量自动化测试报告：[API全量接口测试报告.md](./API全量接口测试报告.md)
- 在线 Swagger UI：`http://127.0.0.1:8000/docs`
