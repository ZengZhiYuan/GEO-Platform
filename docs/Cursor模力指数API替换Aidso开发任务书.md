# Cursor 模力指数 API 替换 Aidso 开发任务书

> 面向 Cursor / Codex Agent 进行后端开发使用。
> 来源文档：
> 1. `GEO-Platform 替换第三方采集接口为「模力指数 API」代码功能修改任务书.md`
> 2. `任务书_molizhishu替换aidso.md`
> 生成日期：2026-06-27
> 适用范围：默认只改 `backend` 与 `docs`。前端仅列契约，不作为本任务默认开发范围。

## 1. 开发目标

当前 GEO-Platform 已经支持官方 AI 厂商 API 采集，以及第三方 Aidso 采集。当前任务目标是把新建第三方采集入口替换为模力指数 API（以下代码标识统一使用 `molizhishu`），同时保留官方采集链路和历史 Aidso 数据读取能力。

最终效果：

- 官方采集 `collection_source=official` 不受影响。
- 新建第三方采集使用 `collection_source=molizhishu`。
- 新任务不再引导或默认使用 Aidso；历史 Aidso 迁移与历史数据只读兼容。
- 模力指数答案、引用、原始响应、状态、错误信息能落入现有 `QueryTask`、`Answer`、`AnswerCitation`、`AnswerBrandResult` 与分析报告链路。
- 本地品牌指标仍由系统确定性逻辑计算，模力指数返回的品牌/情感/排名字段仅作为 provider evidence 保存，不直接覆盖本地指标。
- 后端测试使用 mock，不连接真实模力指数接口；真实接口只通过独立 smoke 脚本手动执行。

## 2. 执行规则

每个开发 Task 开始前：

1. 先读本任务书当前 Task 章节，不要一次性扩大到无关旧任务书。
2. 涉及接口契约时，局部读取 `docs/API接口文档.md` 相关章节。
3. 写接口或采集测试前，局部读取 `docs/API测试文档.md` 的测试风格。
4. 代码开发必须遵守 `.cursor/rules/superpowers-dev-workflow.mdc`：先 `using-superpowers`，实现前 `test-driven-development`，收尾前 `verification-before-completion`。
5. 后端命令必须使用 `backend/.venv`，Windows 读取中文文档或输出中文时显式 UTF-8。
6. 每个 Task 完成后同步 `docs/API接口文档.md`、`docs/API测试文档.md`；若影响原型映射，也同步 `docs/原型功能_API映射整合精简版.md`。
7. 改动 `backend/` 源码并验收通过后，在仓库根目录运行：

```powershell
codegraph status
codegraph sync
codegraph status
```

## 3. 综合分析与统一决策

两份来源文档在目标上一致，但在实现粒度上有差异。本文采用“先交付可验收后端闭环，再扩展批量 ProviderBatch”的路线。

### 3.1 当前代码基线

- Aidso 适配器位于 `backend/app/geo_monitoring/adapters/aidso.py`。
- 适配器统一协议为 `PlatformAdapter.query(PlatformQuery, credential) -> PlatformAnswer`。
- `services/collection.py` 已有 `PENDING` 轮询续跑机制，Aidso 元数据写入 `QueryTask.request_json`。
- `services/runs.py` 用 `collection_source` 过滤平台：Aidso run 仅允许 `adapter_type=aidso`，官方 run 排除 Aidso。
- `geo_monitor_run.collection_source` CHECK 当前为 `official/aidso`。
- `geo_monitor_run.aidso_thinking_enabled_by_platform` 当前保存 Aidso 平台思考开关。
- `geo_ai_platform` 当前通过 `aidso_*` 平台码承载第三方平台端信息。

### 3.2 模力指数接口特征

- Base URL：`https://business-api.molizhishu.com/api/business/monitor`
- 鉴权：`Authorization: Bearer <token>`
- 统一响应信封：`success/code/message/data`，成功条件为业务 `success=true` 且 `code=200`；不能只看 HTTP 状态码。
- 提交流程：`POST /task/batch/shared`
- 查询状态：`GET /task/status/{taskId}`
- 获取结果：`GET /task/result/{taskId}` 或 `GET /task/result/{taskId}/{subTaskId}`
- 停止任务：`PUT /task/{taskId}/stop`
- 区域列表：`GET /api/business/eip-edge/ports/city-info`，免鉴权。
- 子任务状态：`pending/assigned/processing/completed/stopped/failed/error`
- 主任务状态：`pending/processing/completed/partial_completed/failed/stopped`
- **结果就绪口径（生产兼容）：** 真实接口可能在子任务仍为 `pending/assigned/processing` 时先返回非空 `answerContent`。adapter 以「`answerContent` 非空」作为可落库/可返回的成功条件；仅当 pending 类状态且 `answerContent` 为空时才继续轮询。`raw_response_json` 仍保留 provider 原始 `status`（可能为 `processing`），本地 `QueryTask` 仍映射为 `success`。
- 结果字段重点：`answerContent`、`citationList`、`referenceList`、`reasoningProcess`、`recommendedQuestions`、`pageScreenshot`、`mediaContent`、`mentionPosition`、`mentionContext`、`sentiment`、`competitorRankings`、`allRankings`、`amount`、`errorMessage`。

### 3.3 本任务书默认决策

| 编号 | 决策 | 说明 |
| --- | --- | --- |
| D1 | 新增 `collection_source=molizhishu`，保留历史 `aidso` 值 | DB CHECK 先扩展为 `official/aidso/molizhishu`，避免已有 Aidso 行导致迁移失败；新建 Run 输入不再推荐 Aidso。 |
| D2 | P0 复用现有 `PlatformAdapter` 与单 QueryTask 轮询机制 | 每个 `QueryTask` 提交 1 prompt × 1 platform 到模力指数 batch endpoint，保存 `taskId/subTaskId` 后轮询子任务结果。 |
| D3 | P1/P2 再做 run 级 ProviderBatch | 若要把 50 prompt × 5 platform 合并为多个 provider batch，新增 `geo_provider_batch`，每批不超过 100 subtasks。 |
| D4 | 本地平台码使用 `molizhishu_*` 前缀 | 与现有 `aidso_*` 规则一致；真实 provider 平台码写入 `extra_config.molizhishu_platform`。 |
| D5 | 引用入库优先 `citationList`，为空再用 `referenceList` | `referenceList.summary` 可回填 `quoted_text`；完整 `referenceList` 保存在 `raw_response_json`。 |
| D6 | 品牌指标以本地计算为准 | Provider 的 `mentionPosition/sentiment/rankings` 只写入 raw 或 `context_json.provider_*`。 |
| D7 | 模式字段采用通用 `provider_mode_by_platform` | 替代 `aidso_thinking_enabled_by_platform`；值限定 `standard/reasoning/search/reasoning_search`。 |
| D8 | 前端不在本阶段默认开发 | 仅更新后端 API 契约与文档；除非用户明确要求，不改 `frontend/`。 |

## 4. 平台映射口径

`services/platforms.py` 新增 `MOLIZHISHU_PLATFORM_MAPPINGS`。以下表是平台码唯一口径，后续 Schema、迁移、测试、文档必须一致。

| 本地 platform_code | 模力指数 platform | 平台名 | base_platform | endpoint_type | 默认 mode |
| --- | --- | --- | --- | --- | --- |
| `molizhishu_deepseek_web` | `deepseek` | DeepSeek 网页端 | `deepseek` | `web` | `reasoning_search` |
| `molizhishu_deepseek_mobile` | `deepseek_mobile` | DeepSeek 手机端 | `deepseek` | `app` | `reasoning_search` |
| `molizhishu_doubao_web` | `doubao` | 豆包网页端 | `doubao` | `web` | `search` |
| `molizhishu_doubao_mobile` | `doubao_mobile` | 豆包手机端 | `doubao` | `app` | `search` |
| `molizhishu_yuanbao_web` | `yuanbao` | 腾讯元宝 | `yuanbao` | `web` | `search` |
| `molizhishu_kimi_web` | `kimi` | Kimi | `kimi` | `web` | `search` |
| `molizhishu_qianwen_web` | `qianwen` | 通义千问 | `qianwen` | `web` | `search` |
| `molizhishu_quark_web` | `quark` | 夸克 AI | `quark` | `web` | `search` |
| `molizhishu_baiduai_web` | `baiduai` | 百度 AI+ | `baiduai` | `web` | `search` |
| `molizhishu_weibo_zhisou_web` | `weibo_zhisou` | 微博智搜 | `weibo_zhisou` | `web` | `search` |
| `molizhishu_wenxinyiyan_web` | `wenxinyiyan` | 文心一言 | `wenxinyiyan` | `web` | `search` |

注意：

- 模力指数平台标识必须逐字使用供应商值，特别是 `qianwen`、`baiduai`、`weibo_zhisou`。
- 模力指数没有 Aidso 的 `douyin`；新增 `quark/weibo_zhisou`。
- 移动端是独立 provider 平台，但本地展示仍通过 `base_platform + endpoint_type` 归组。

## 5. Task 索引

| Task | 标题 | 优先级 |
| --- | --- | --- |
| M0 | 基线、决策记录与测试先行准备 | P0 |
| M1 | 新增模力指数配置项 | P0 |
| M2 | 平台映射与平台种子数据 | P0 |
| M3 | 数据库迁移与 ORM 模型 | P0 |
| M4 | Schema 与创建 Run 契约 | P0 |
| M5 | Molizhishu Client / Adapter | P0 |
| M6 | Registry、KeyPool 与采集凭证接入 | P0 |
| M7 | CollectionService 轮询续跑改造 | P0 |
| M8 | 结果归一化、入库与安全展示 | P0 |
| M9 | Run 路由、取消与停止任务 | P1 |
| M10 | Callback 接口与幂等处理 | P1 |
| M11 | RegionCode 与截图策略 | P1 |
| M12 | 分析、报告与页面聚合回归 | P1 |
| M13 | 测试套件迁移与真实接口 smoke 脚本 | P0/P1 |
| M14 | 文档、部署配置与 Aidso 运行期下线 | P1 |
| M15 | ProviderBatch 批量化正式版能力 | P2 |

## 6. 详细任务

### Task M0：基线、决策记录与测试先行准备

目的：锁定本文 D1-D8，不让后续实现反复切换方案，并记录改动前基线。

涉及文件：

- `docs/Cursor模力指数API替换Aidso开发任务书.md`
- 可新增 `docs/molizhishu-collection-source-design.md`

实现要点：

- 记录采用 `collection_source=molizhishu`、历史 Aidso 只读兼容、P0 单 QueryTask 轮询、P2 ProviderBatch 的决策。
- 执行基线测试，记录失败项但不混入本任务修复范围。
- 确认当前工作树状态，避免覆盖他人未提交改动。

验收标准：

- 决策文档或本任务书中 D1-D8 均明确。
- 已运行基线命令并记录结果。
- 没有进行业务代码改动。

建议命令：

```powershell
git -c core.quotepath=false status --short
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
```

#### M0 验收记录（2026-06-27）

| 项 | 结果 |
| --- | --- |
| D1–D8 决策 | 已写入任务书 §3.3 与 `docs/molizhishu-collection-source-design.md` |
| Git 工作树 | 干净；分支 `feat/third-party-collector-api-adapter` |
| 基线 pytest | `391 passed`，0 failed（2 warnings，非阻塞） |
| Alembic head | `geo_monitoring_0010` |
| 业务代码改动 | 无（仅文档） |

### Task M1：新增模力指数配置项

目的：把模力指数开关、地址、令牌、超时、轮询参数纳入统一 `Settings`，并确保 token 不泄漏。

涉及文件：

- `backend/app/core/config.py`
- `.env.example`
- `backend/tests/test_config.py`
- `docs/API接口文档.md`
- `docs/API测试文档.md`

实现要点：

- 新增配置：
  - `MOLIZHISHU_ENABLED: bool = False`
  - `MOLIZHISHU_BASE_URL: str = "https://business-api.molizhishu.com/api/business/monitor"`
  - `MOLIZHISHU_API_TOKEN: str = ""`
  - `MOLIZHISHU_REQUEST_TIMEOUT_SECONDS: int = 30`
  - `COLLECTION_MOLIZHISHU_MAX_POLLS: int = 360`
  - `COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS: int = 8`
  - `MOLIZHISHU_DEFAULT_SCREENSHOT: int = 0`
  - `MOLIZHISHU_CALLBACK_ENABLED: bool = False`
  - `MOLIZHISHU_CALLBACK_TOKEN: str = ""`
- `MOLIZHISHU_ENABLED=true` 时必须要求 `MOLIZHISHU_API_TOKEN` 非空。
- `runtime_summary()` 与连接摘要只输出 `enabled/base_url/has_token`，不得输出 token。
- 旧 `AIDSO_*` 配置本 Task 暂不强删，避免大范围破坏；M14 再做运行期下线清理。

测试先行：

- 先新增 `MOLIZHISHU_ENABLED=True` 且 token 为空会抛校验错误的测试。
- 先新增 runtime summary 不泄漏 token 的测试。

验收标准：

- 未启用时应用照常启动。
- 启用且 token 为空时抛出明确错误。
- summary 和日志不包含完整 token。
- `.env.example` 与代码字段一致。

### Task M2：平台映射与平台种子数据

目的：定义 11 个模力指数平台端，并让平台列表和 metadata 能识别其 base platform 与 endpoint。

涉及文件：

- `backend/app/geo_monitoring/services/platforms.py`
- `backend/app/geo_monitoring/services/metadata.py`
- `backend/tests/geo_monitoring/test_platforms.py`
- `backend/tests/geo_monitoring/test_metadata_api.py`

实现要点：

- 新增 `MOLIZHISHU_PLATFORM_MAPPINGS`，内容以本文第 4 节表格为准。
- 新增 `MOLIZHISHU_PLATFORMS`：
  - `adapter_type="molizhishu"`
  - `model_name=f"molizhishu:{molizhishu_platform}"`
  - `search_enabled=True`
  - `citation_supported=True`
  - `extra_config` 包含 `molizhishu_platform/base_platform/endpoint_type/default_mode/supported_modes`
- `DEFAULT_PLATFORMS` 改为 `(*OFFICIAL_PLATFORMS, *MOLIZHISHU_PLATFORMS)`，新建种子不再新增 Aidso 平台。
- `metadata.py` 优先读取 `extra_config.base_platform/endpoint_type`；新增中文标签 `qianwen/quark/baiduai/weibo_zhisou/wenxinyiyan`。

测试先行：

- 平台映射条数、平台码唯一、provider code 逐字正确。
- `/metadata/platform-endpoints` 能把 `molizhishu_doubao_web` 与 `molizhishu_doubao_mobile` 归到同一 `base_platform=doubao`。

验收标准：

- 平台列表含 5 个官方平台与 11 个模力指数平台。
- 新平台 `adapter_type` 均为 `molizhishu`。
- 新平台 `extra_config` 足够支撑展示分组与 adapter 请求。
- 官方平台 code 不变。

### Task M3：数据库迁移与 ORM 模型

目的：让数据库支持新采集源、通用 provider 字段、模力指数平台种子数据，并保留历史 Aidso 兼容。

涉及文件：

- `backend/alembic/versions/<new>_geo_monitoring_molizhishu_collection_source.py`
- `backend/app/geo_monitoring/models.py`
- `backend/tests/test_migrations.py`
- `backend/tests/test_migration_baseline.py`
- `backend/tests/geo_monitoring/test_models.py`

实现要点：

- 修改 `geo_monitor_run.collection_source` CHECK 为 `IN ('official', 'aidso', 'molizhishu')`。
- `geo_monitor_run` 新增：
  - `provider_mode_by_platform JSON`，默认 `{}`
  - `provider_screenshot INTEGER`，默认 `0`
  - `provider_callback_url VARCHAR(500)`，可空
  - `region_code VARCHAR(32)`，可空
- `geo_query_task` 新增：
  - `provider_name VARCHAR(64)`
  - `provider_task_id VARCHAR(128)`
  - `provider_subtask_id VARCHAR(128)`
  - `provider_platform_code VARCHAR(64)`
  - `provider_mode VARCHAR(64)`
  - `provider_status VARCHAR(64)`
  - `provider_result_json JSON`
  - `provider_error_message TEXT`
- 插入 11 个 `molizhishu_*` 平台种子数据。
- 不修改旧迁移文件；Aidso 历史迁移保留。
- 如 SQLite batch alter 需要特殊处理，按现有迁移测试模式实现。

测试先行：

- 新增 migration SQL 包含 `molizhishu` CHECK 与平台 seed。
- 新增模型默认值测试。
- 新增 `collection_source='molizhishu'` 可写入、`aidso` 历史值仍可存在的测试。

验收标准：

- `alembic heads` 单 head。
- `alembic upgrade head --sql` 能生成有效 SQL。
- 迁移测试通过。
- ORM 字段与迁移定义一致。

### Task M4：Schema 与创建 Run 契约

目的：让新建运行请求支持模力指数，并替换 Aidso 专用请求字段。

涉及文件：

- `backend/app/geo_monitoring/schemas.py`
- `backend/app/geo_monitoring/api/runs.py`
- `backend/app/geo_monitoring/services/runs.py`
- `backend/tests/geo_monitoring/test_models.py`
- `backend/tests/geo_monitoring/test_runs.py`
- `docs/API接口文档.md`
- `docs/API测试文档.md`

实现要点：

- 新建 Run 输入允许：
  - `collection_source`: `official` 或 `molizhishu`
  - `provider_mode_by_platform: dict[str, str] = {}`
  - `provider_screenshot: int = 0`
  - `region_code: str | None = None`
  - `provider_callback_url: str | None = None`
- `provider_mode_by_platform` 校验：
  - key 必须在 `MOLIZHISHU_PLATFORM_MAPPINGS` 中。
  - value 必须为 `standard/reasoning/search/reasoning_search`。
  - key 必须属于本次 `platform_codes`。
- `provider_screenshot` 只允许 `0/1/2`。
- `region_code` 若提供则非空，当前只允许一个 region code。
- 兼容读历史 run 时不要因为旧 `aidso_thinking_enabled_by_platform` 数据报错；新建请求不再使用该字段。

测试先行：

- `collection_source='molizhishu'` 与合法 mode 创建通过。
- 非法 mode、未知平台、mode 配置不属于本次平台均失败。
- 官方采集请求仍通过。
- 新建请求传旧 Aidso 字段时返回清晰错误或被忽略的行为必须在 API 文档中固定。

验收标准：

- 新建 Run 可以选择模力指数平台。
- 官方平台与模力指数平台不能在同一个 Run 混用，除非后续单独设计混采。
- API 文档已更新字段、示例和错误码。

### Task M5：Molizhishu Client / Adapter

目的：封装模力指数提交、轮询、结果解析和错误分类，满足现有采集执行器调用。

涉及文件：

- 新增 `backend/app/geo_monitoring/adapters/molizhishu.py`
- `backend/app/geo_monitoring/adapters/errors.py`
- `backend/app/geo_monitoring/adapters/__init__.py`
- 新增 `backend/tests/geo_monitoring/adapters/test_molizhishu.py`

实现要点：

- 新增 `MolizhishuPendingError(AdapterError)`，`category=ErrorCategory.PENDING`，携带 `pending_metadata`：
  - `molizhishu_task_id`
  - `molizhishu_subtask_id`
  - `molizhishu_platform`
  - `molizhishu_mode`
  - `molizhishu_status`
- 新增 `MolizhishuAdapter`，构造参数至少包含：
  - `code`
  - `molizhishu_platform`
  - `default_mode`
  - `base_url`
  - `timeout_seconds`
  - `raw_response_enabled`
- `query()` 流程：
  1. 从 `request.metadata` 读取已保存的 `molizhishu_task_id/subtask_id`、mode、region、screenshot。
  2. 无 subtask 时调用 `POST /task/batch/shared`，提交 1 prompt × 1 platform。
  3. 从响应中提取 `taskId` 与 `subTaskList[0].subTaskId`。
  4. 调用 `GET /task/result/{taskId}/{subTaskId}` 获取子任务结果。
  5. `pending/assigned/processing` 且 `answerContent` 为空时抛 `MolizhishuPendingError`。
  6. `pending/assigned/processing` 但 `answerContent` 非空，或 `completed` 时转为 `PlatformAnswer`（provider `status` 可能仍为 `processing`，见 §3.2 结果就绪口径）。
  7. `failed/error/stopped` 抛不可重试 `AdapterError`，并保留 provider 错误信息。
  8. result 轮询阶段若 HTTP 体非 JSON，视为临时上游异常，抛 `MolizhishuPendingError` 续轮询（不算失败 attempt）。
- HTTP 层必须同时检查 HTTP 状态和 body `success/code/message`。
- Token 失效归类为 `UNAUTHORIZED`，余额不足归类为不可重试错误，非 JSON 和网络超时分别归类。
- citation 映射：
  - 优先 `citationList`
  - 为空时使用 `referenceList`
  - `referenceList` 以 URL 建立 summary 映射，回填 `quoted_text`
- `raw_response` 保存 submit/result 的必要原始包，不包含 token。

测试先行：

- 成功提交并遇到 `processing` 且 `answerContent` 为空时抛 pending，metadata 完整。
- pending 后再次 query 复用 taskId/subTaskId。
- `processing` 且 `answerContent` 非空时直接返回 `PlatformAnswer`（真实接口常见）。
- completed 正确返回 `answerContent`、citations、provider_request_id。
- HTTP 200 但 `success=false` 被识别为失败。
- token 失效、余额不足、非 JSON、超时、failed/error/stopped 均有测试。

验收标准：

- `isinstance(MolizhishuAdapter(...), PlatformAdapter)` 为真。
- 单元测试覆盖提交、轮询、完成、失败、鉴权、异常响应。
- 错误消息不泄漏 token。

### Task M6：Registry、KeyPool 与采集凭证接入

目的：配置开启后注册 11 个模力指数适配器，并给每个平台提供同一个 provider token。

涉及文件：

- `backend/app/geo_monitoring/adapters/registry.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/tests/geo_monitoring/adapters/test_registry.py`
- `backend/tests/geo_monitoring/services/test_collection_key_pool.py`

实现要点：

- 新增 `_molizhishu_configured(settings)`。
- 配置完整时遍历 `MOLIZHISHU_PLATFORM_MAPPINGS` 注册 `MolizhishuAdapter`。
- `build_credential_key_pool` 使用 `MOLIZHISHU_API_TOKEN` 为所有 `molizhishu_*` 平台注册 `ApiKeyCredential`。
- Aidso 逻辑暂时不必物理删除，但新任务路径不得依赖 Aidso。

测试先行：

- 未启用 molizhishu 时不注册 `molizhishu_*`。
- 启用且 token 存在时注册 11 个适配器。
- key pool 能为 `molizhishu_doubao_web` acquire 到 token 凭证。

验收标准：

- 官方适配器注册不受影响。
- 模力指数配置开启后可以执行采集。
- 模力指数关闭后不会构建 provider adapter。

### Task M7：CollectionService 轮询续跑改造

目的：把 Aidso 专用 pending 续跑机制泛化到模力指数，使 1 prompt × 1 platform 的异步子任务能稳定收敛。

涉及文件：

- `backend/app/geo_monitoring/services/collection.py`
- `backend/app/worker/actors/collection.py`
- `backend/tests/worker/test_collection_actor.py`
- `backend/tests/geo_monitoring/test_collection_contract.py`

实现要点：

- `TaskSnapshot` 替换 Aidso 字段为：
  - `provider_mode`
  - `provider_screenshot`
  - `region_code`
  - `collection_source`
- `_collect_platform_answer` metadata 注入：
  - `provider_mode`
  - `provider_screenshot`
  - `region_code`
  - 已有 `request_json` 中的 `molizhishu_task_id/subtask_id/poll_count`
- `_is_aidso_pending_poll` 泛化为 provider-aware pending poll，模力指数依据：
  - `platform_code in MOLIZHISHU_PLATFORM_MAPPINGS`
  - `last_error_code == pending`
  - `request_json.molizhishu_subtask_id` 非空
- `_persist_pending_metadata` 保存 `molizhishu_poll_count`，并把 `provider_request_id` 设置为 subTaskId。
- `_should_retry_task` 对模力指数 pending 使用 `COLLECTION_MOLIZHISHU_MAX_POLLS`。
- actor 对 pending 重入队延迟使用 `COLLECTION_MOLIZHISHU_POLL_DELAY_SECONDS`，普通错误重试仍用现有 retry base。
- pending 轮询不递增 `attempt_count`，避免把正常轮询算作失败尝试。

测试先行：

- pending 首次保存 `taskId/subTaskId/poll_count`。
- pending 再次执行复用 metadata，不递增 `attempt_count`。
- 达到最大轮询次数后任务失败。
- actor 使用模力指数轮询延迟。

验收标准：

- 模力指数任务能从 pending 收敛到 success 或 failed。
- 子任务失败不影响同 run 其他任务继续执行。
- Run 终态聚合仍使用现有 `completed/partial_success/failed/cancelled`。

### Task M8：结果归一化、入库与安全展示

目的：把模力指数子任务结果落入现有答案、引用、品牌结果和详情展示结构。

涉及文件：

- `backend/app/geo_monitoring/adapters/molizhishu.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/app/geo_monitoring/services/answer_metadata.py`
- `backend/app/geo_monitoring/services/brand_matcher.py`
- `backend/tests/geo_monitoring/test_answer_metadata.py`
- `backend/tests/geo_monitoring/test_collection_contract.py`

字段映射：

| 模力指数字段 | 本地目标 |
| --- | --- |
| `answerContent` | `geo_answer.raw_text` / `normalized_text` |
| `citationList` | 优先写 `geo_answer_citation` |
| `referenceList` | citation 为空时备用；完整保存在 raw |
| `referenceList.summary` | `AnswerCitation.quoted_text` |
| `reasoningProcess` | `raw_response_json.reasoningProcess`，详情安全视图可提取 |
| `recommendedQuestions` | `raw_response_json.recommendedQuestions` |
| `pageScreenshot` | `raw_response_json.pageScreenshot` |
| `mediaContent` | `raw_response_json.mediaContent` |
| `mentionPosition/mentionContext/sentiment/rankings` | raw 或 `AnswerBrandResult.context_json.provider_*` |
| `amount` | `raw_response_json.amount` |
| `errorMessage` | `QueryTask.provider_error_message` |

实现要点：

- `_persist_success` 继续使用 `PlatformAnswer`，不要让 provider 直接写数据库。
- 采集成功后同步写 `QueryTask.provider_*` 字段。
- 品牌匹配仍调用本地 `match_brands_in_text`。
- `build_raw_response_safe` 新增 molizhishu 白名单，仅暴露安全字段：
  - `status`
  - `answerContent` 摘要或截断
  - `citationList[].title/url/site`
  - `referenceList[].title/url/site/summary`
  - `reasoningProcess.content` 截断
  - `recommendedQuestions`
  - `pageScreenshot`
  - `amount`
  - `errorMessage`
- 不暴露 token、proxy IP、内部调试字段。

测试先行：

- citationList 正常入库。
- citationList 为空时 referenceList 入库。
- 无引用时答案仍入库。
- provider 品牌字段不覆盖本地品牌指标。
- 安全视图不泄漏敏感字段。

验收标准：

- `Answer`、`AnswerCitation`、`AnswerBrandResult` 与现有分析服务兼容。
- 答案详情能展示安全化 provider 原始信息。
- source analysis 能统计模力指数引用来源。

### Task M9：Run 路由、取消与停止任务

目的：新建运行按采集源正确筛选平台，取消模力指数运行时调用 provider stop 能力。

涉及文件：

- `backend/app/geo_monitoring/services/runs.py`
- `backend/app/geo_monitoring/api/runs.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/app/geo_monitoring/adapters/molizhishu.py`
- `backend/tests/geo_monitoring/test_runs.py`

实现要点：

- `_platform_matches_collection_source`：
  - `molizhishu` 只允许 `adapter_type=="molizhishu"`。
  - `official` 排除 `molizhishu` 和 `aidso`。
  - 历史 `aidso` 可按旧逻辑只读兼容，是否允许新建由 Schema 决定。
- `create_run` 保存 `provider_mode_by_platform/provider_screenshot/region_code/provider_callback_url`。
- 取消 run 时：
  - 对已有 `provider_task_id` 的未终态模力指数任务调用 `PUT /task/{taskId}/stop`。
  - 已成功任务保留结果。
  - 未完成本地 QueryTask 标记为 `cancelled`。
- 模力指数 stop 只能停止未分配 pending 任务，已 assigned/processing 可能继续计费，文档要说明。

测试先行：

- molizhishu run 拒绝官方平台。
- official run 拒绝 molizhishu 平台。
- 取消带 provider taskId 的 run 会调用 stop。
- 已完成子任务不会被删除。

验收标准：

- 平台筛选和错误码清晰。
- 停止任务后本地状态可解释，日志包含 taskId/subTaskId。

### Task M10：Callback 接口与幂等处理

目的：接收模力指数回调，作为轮询的补充，并保证重复回调不会重复入库。

涉及文件：

- 新增 `backend/app/geo_monitoring/api/provider_callbacks.py`
- `backend/app/geo_monitoring/api/__init__.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/tests/geo_monitoring/test_molizhishu_callback.py`
- `docs/API接口文档.md`
- `docs/API测试文档.md`

接口：

```text
POST /api/geo-monitoring/provider-callbacks/molizhishu
```

实现要点：

- 默认用 `X-Callback-Token` 或 query `token` 校验，值来自 `MOLIZHISHU_CALLBACK_TOKEN`。
- 根据 `taskId/subTaskId` 查找本地 `QueryTask`。
- 回调 payload 与轮询结果走同一归一化和入库函数。
- 幂等键使用本地 `QueryTask.id` 与 `Answer.task_id` 唯一约束；成功终态不重复写。
- callback 与轮询并存时，任一先到都能完成入库，后到只更新必要状态或跳过。

测试先行：

- 非法 token 被拒绝。
- 完成回调能写入答案和引用。
- 重复回调不重复生成 Answer/Citation。
- 回调先于轮询、轮询先于回调都能收敛。

验收标准：

- 接口已注册到主前缀与 v1 兼容前缀。
- 回调失败不导致服务崩溃，有可定位日志。

### Task M11：RegionCode 与截图策略

目的：支持模力指数地域与截图能力，同时保持 MVP 默认参数简单。

涉及文件：

- `backend/app/geo_monitoring/adapters/molizhishu.py`
- `backend/app/geo_monitoring/api/metadata.py`
- `backend/app/geo_monitoring/services/metadata.py`
- `backend/tests/geo_monitoring/test_metadata_api.py`
- `docs/API接口文档.md`

实现要点：

- 提交任务时：
  - `region_code` 非空则发送 `regionCode: [region_code]`
  - `provider_screenshot` 发送到 platforms item 的 `screenshot`
- 新增区域接口：

```text
GET /api/geo-monitoring/providers/molizhishu/regions
```

- 区域接口调用免鉴权 city-info，建议本地短缓存；供应商不可用时返回清晰错误。
- `regionCode` 当前只允许一个，Schema 必须阻止多个值。

测试先行：

- region_code 能进入提交体。
- screenshot 只允许 0/1/2。
- metadata regions 能 mock 返回区域列表。

验收标准：

- 不传 region 时仍可提交。
- 传 region 时提交体为数组且长度为 1。
- API 文档说明地域接口为 provider 代理能力。

### Task M12：分析、报告与页面聚合回归

目的：确认模力指数入库数据能被现有分析、Dashboard、竞品、信源和报告链路消费。

涉及文件：

- `backend/app/geo_monitoring/services/analysis.py`
- `backend/app/geo_monitoring/services/source_analysis.py`
- `backend/app/geo_monitoring/services/competitor_analysis.py`
- `backend/app/geo_monitoring/reports/`
- `backend/tests/geo_monitoring/test_dashboard_api.py`
- `backend/tests/geo_monitoring/test_source_analysis_api.py`
- `backend/tests/geo_monitoring/test_competitor_analysis_api.py`
- `backend/tests/geo_monitoring/reports/`

实现要点：

- 搜索硬编码 `aidso` 或官方平台 code 的统计逻辑。
- 平台名称和端侧展示应来自 `AIPlatform` 与 `extra_config`。
- source statistics 使用 `AnswerCitation`，不依赖 provider 类型。
- 报告渲染仅展示安全后的原始信息，不能泄漏 token。

测试先行：

- 构造模力指数答案与 citation 后，source analysis 能统计域名和类型。
- 模力指数 run 完成后能触发分析。
- PDF/HTML/Markdown 报告不会因新平台码异常。

验收标准：

- 品牌提及率、首推率、竞品提及、引用来源统计可正常生成。
- 官方 run 与模力指数 run 的报告字段结构保持一致。

### Task M13：测试套件迁移与真实接口 smoke 脚本

目的：把 Aidso 相关测试迁移到模力指数，并提供可手动运行的真实接口验证脚本。

涉及文件：

- 新增 `backend/tests/geo_monitoring/adapters/test_molizhishu.py`
- 新增 `backend/tests/geo_monitoring/test_molizhishu_collection.py`
- 新增 `backend/tests/geo_monitoring/test_molizhishu_callback.py`
- 新增 `backend/scripts/molizhishu_smoke_test.py`
- 删除或改造 `backend/tests/geo_monitoring/adapters/test_aidso.py`
- 改造 `backend/tests/worker/test_collection_actor.py`

测试场景：

- Client/Adapter：提交成功、pending、completed、partial、failed、stopped、token 失效、余额不足、非 JSON、网络超时。
- Collection：1 prompt × 1 platform、pending 续跑、最大轮询失败、部分失败、取消任务。
- 入库：answerContent、citationList、referenceList fallback、provider raw、provider brand evidence。
- Callback：成功、重复推送、与轮询并发。
- Migration：upgrade SQL、seed、字段默认值。

Smoke 脚本要求：

- 读取 `MOLIZHISHU_API_TOKEN`，无 token 时直接退出并提示。
- 默认提交 1 prompt × 1 platform，默认 platform `qianwen`、mode `search`、screenshot `0`。
- 打印 taskId、subTaskId、状态、answerContent 摘要、citation/reference 数量。
- 不写业务数据库。
- 文档说明费用风险。

验收标准：

- Mock 测试不访问真实网络。
- smoke 脚本只有手动运行才访问真实接口。
- 旧官方 API 采集测试仍通过。

### Task M14：文档、部署配置与 Aidso 运行期下线

目的：让新开发人员按文档可以配置模力指数，并逐步移除运行期 Aidso 入口。

涉及文件：

- `README.md`
- `.env.example`
- `docs/API接口文档.md`
- `docs/API测试文档.md`
- `docs/采集任务生命周期说明.md`
- `docs/原型功能_API映射整合精简版.md`
- `backend/app/core/config.py`
- `backend/app/geo_monitoring/services/platforms.py`
- `backend/app/geo_monitoring/adapters/registry.py`

实现要点：

- 文档新增：
  - 模力指数配置说明
  - 平台映射说明
  - mode/screenshot/region 说明
  - pending 轮询说明
  - callback 配置说明
  - 错误码与 HTTP 200 业务失败说明
  - 费用与重试注意事项
- 新建任务不再展示 Aidso 字段。
- 历史迁移文件不得删除或改写。
- 是否删除 `adapters/aidso.py` 取决于是否仍需历史任务重试。若无法确认生产无历史 pending Aidso 任务，则只从新任务入口下线，不物理删除适配器。

验收标准：

- `.env.example` 与实际 Settings 完全一致。
- API 文档不再推荐 Aidso 创建参数。
- 历史 Aidso 数据查询不报错。
- 新建任务默认只出现官方与模力指数两类采集源。

### Task M15：ProviderBatch 批量化正式版能力

目的：当需要按 run 合并提交时，引入 provider batch，支持 50 prompt × 5 platform 这类超过 100 subtasks 的场景。

涉及文件：

- 新增 `backend/alembic/versions/<new>_geo_monitoring_provider_batch.py`
- `backend/app/geo_monitoring/models.py`
- 新增 `backend/app/geo_monitoring/repositories/provider_batches.py`
- `backend/app/geo_monitoring/services/collection.py`
- `backend/app/geo_monitoring/services/runs.py`
- `backend/tests/geo_monitoring/test_molizhishu_provider_batch.py`

实现要点：

- 新增表 `geo_provider_batch`：
  - `id`
  - `run_id`
  - `provider_name`
  - `provider_task_id`
  - `batch_no`
  - `status`
  - `total_items`
  - `completed_items`
  - `failed_items`
  - `submitted_at`
  - `completed_at`
  - `raw_submit_json`
  - `raw_status_json`
  - `raw_result_json`
  - `error_message`
- `geo_query_task` 增加 `provider_batch_id`。
- 按 `prompts × platforms <= 100` 自动拆批。
- callback 和轮询都以 batch 为单位更新，再逐个 subTask 回填 QueryTask。
- 任一 provider batch 失败不影响其他 batch 已完成结果。

测试先行：

- 50 prompt × 5 platform 拆成 3 个 batch。
- 每个 QueryTask 能映射到正确 batch 与 subTaskId。
- 部分 batch 失败时 Run 进入 `partial_success`。
- 单 batch 重试不重复写入已成功 QueryTask。

验收标准：

- 正式版支持多 provider taskId 聚合。
- 未来扩展到更多 prompt/platform 不需要重构主链路。

## 7. 状态与错误映射

### 7.1 子任务状态映射

| 模力指数子任务状态 | 本地 QueryTask 状态 |
| --- | --- |
| `pending` | `queued` |
| `assigned` | `running` |
| `processing` | `running` |
| `completed` | `success` |
| `failed` | `failed` |
| `error` | `failed` |
| `stopped` | `cancelled` |

**结果就绪与本地成功映射（§3.2）：** 上表描述 provider 子任务状态与本地 `QueryTask` 的常规对应关系。实际落库时，若 result 中 `answerContent` 已非空，即使 provider `status` 仍为 `pending/assigned/processing`，adapter 也会写入 `Answer` 并将 `QueryTask` 置为 `success`；`provider_result_json.status` 保留 provider 原值供排查。

### 7.2 主任务状态映射

| 模力指数主任务状态 | 本地 Run 状态建议 |
| --- | --- |
| `pending` | `collecting` |
| `processing` | `collecting` |
| `completed` | `completed` 或进入分析后的现有状态 |
| `partial_completed` | `partial_success` |
| `failed` | `failed` |
| `stopped` | `cancelled` |

### 7.3 错误处理

- HTTP 200 但 `success=false` 必须按失败处理。
- `Token失效` 归类为 `UNAUTHORIZED`，不可无限重试。
- 余额不足归类为不可重试错误。
- `pending/assigned/processing` 且 `answerContent` 为空时只走 pending 轮询，不算失败 attempt。
- result 轮询阶段非 JSON 响应按 pending 续轮询，不算失败 attempt。
- 子任务失败不应直接让整个 Run 失败，除非所有子任务都失败。
- 错误日志必须包含本地 task id、provider taskId、subTaskId、platform code。
- 日志、响应、raw safe view 不得泄漏 token。

## 8. MVP 验收标准

P0 完成后至少满足：

1. 后端配置支持 `MOLIZHISHU_API_TOKEN`，并能安全脱敏。
2. DB 支持 `collection_source='molizhishu'`。
3. 平台列表包含 11 个模力指数平台。
4. 可以创建 `collection_source='molizhishu'` 的 Run。
5. 可以提交 1 prompt × 1 platform 到模力指数 mock。
6. 可以 pending 轮询并复用 `taskId/subTaskId`。
7. `answerContent` 写入 `geo_answer`。
8. `citationList` 或 `referenceList` 写入 `geo_answer_citation`。
9. 模力指数原始结果写入 `raw_response_json` 或 provider 字段。
10. 本地品牌提及指标继续计算。
11. 官方 API 采集测试不受影响。
12. API 文档、测试文档、采集生命周期文档已同步。

## 9. 正式版验收标准

P1/P2 完成后进一步满足：

1. callback 与轮询互为兜底，重复结果幂等。
2. 支持停止未完成模力指数任务。
3. 支持 `regionCode` 与 screenshot 策略。
4. 支持 ProviderBatch 自动拆批，单批不超过 100 subtasks。
5. 支持 50 prompt × 5 platform 的多批聚合。
6. 支持 provider taskId/subTaskId/batch 状态追踪。
7. 支持完整分析与 PDF/HTML/Markdown 报告生成。
8. 所有新增核心逻辑有 mock 测试。
9. 线上可通过配置关闭模力指数采集，不影响官方采集。

## 10. 推荐验收命令

后端命令必须使用 `backend/.venv`。

```powershell
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_config.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring\adapters
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\worker\test_collection_actor.py
backend\.venv\Scripts\python.exe -m pytest -q backend\tests\test_migrations.py backend\tests\test_migration_baseline.py
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads
backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head --sql
```

如修改报告生成或下载相关测试，按仓库规则在 Windows 沙箱下使用工作区临时目录并申请提权：

```powershell
backend\.venv\Scripts\python.exe -m pytest -v backend\tests\geo_monitoring --basetemp .pytest-tmp
```

## 11. Cursor 推荐指令格式

```text
执行 docs/Cursor模力指数API替换Aidso开发任务书.md 的 Task M1：新增模力指数配置项。
```

或：

```text
执行 Task M5：Molizhishu Client / Adapter。
```

Agent 应自动按本任务书定位当前 Task，执行测试先行、最小实现、验收命令、文档同步和 CodeGraph 更新。

## 12. 风险与处理建议

1. 模力指数 HTTP 200 仍可能业务失败：所有 client 方法必须检查 body `success/code/message`。
2. 引用口径可能被污染：默认只把 `citationList` 当作真实被引来源，`referenceList` 只作 fallback 与 raw evidence。
3. 第三方品牌指标与本地指标口径不同：本地指标不得由 LLM 或 provider 字段直接覆盖。
4. 平台码一旦发布不应改名：本文第 4 节为唯一平台码口径。
5. 移动端与网页端不能混在一个平台维度：必须写 `base_platform/endpoint_type`。
6. 模力指数任务可能长时间 pending：P0 单任务轮询要调大最大轮询次数，并使用较长 poll delay。
7. callback 与轮询可能竞争：所有入库必须基于 `QueryTask` 和 `Answer.task_id` 幂等。
8. 真实接口会产生费用：自动测试不得访问真实接口，smoke 脚本必须手动执行。
9. 历史 Aidso 数据可能存在：不要改写旧迁移，不要让历史 run 详情因为新 Schema 失败。
10. ProviderBatch 是正式版增强：P0 不要为了批量化重写整个采集服务，先保证可验收闭环。
