# 模力指数采集源设计决策与基线记录

> 对应任务：`Task M0：基线、决策记录与测试先行准备`  
> 主任务书：`docs/Cursor模力指数API替换Aidso开发任务书.md`  
> 记录日期：2026-06-27  
> 分支：`feat/third-party-collector-api-adapter`

## 1. 背景

GEO-Platform 当前支持官方 AI 厂商 API 采集（`collection_source=official`）与第三方 Aidso 采集（`collection_source=aidso`）。本分支目标是将**新建**第三方采集入口替换为模力指数 API（代码标识 `molizhishu`），同时保留官方链路与历史 Aidso 数据只读兼容。

本文锁定 D1–D8 决策，供 M1–M15 实现引用，避免后续反复切换方案。

本文是 M0 阶段的设计决策与基线快照，不替代主任务书和 Task 索引。后续开发必须继续以 `docs/Cursor模力指数API替换Aidso开发任务书.md` 和 `docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md` 为执行入口；若当前代码或测试结果与本文基线记录不同，以当次重新读取和重新运行的结果为准，并在对应 Task 汇报中说明差异。

## 2. 统一决策（D1–D8）

| 编号 | 决策 | 说明 |
| --- | --- | --- |
| D1 | 新增 `collection_source=molizhishu`，保留历史 `aidso` 值 | DB CHECK 先扩展为 `official/aidso/molizhishu`；已有 Aidso 行不导致迁移失败；新建 Run 输入不再推荐 Aidso。 |
| D2 | P0 复用现有 `PlatformAdapter` 与单 QueryTask 轮询机制 | 每个 `QueryTask` 提交 1 prompt × 1 platform 到模力指数 batch endpoint，保存 `taskId/subTaskId` 后轮询子任务结果。 |
| D3 | P1/P2 再做 run 级 ProviderBatch | 若要把 50 prompt × 5 platform 合并为多个 provider batch，新增 `geo_provider_batch`，每批不超过 100 subtasks。 |
| D4 | 本地平台码使用 `molizhishu_*` 前缀 | 与现有 `aidso_*` 规则一致；真实 provider 平台码写入 `extra_config.molizhishu_platform`。 |
| D5 | 引用入库优先 `citationList`，为空再用 `referenceList` | `referenceList.summary` 可回填 `quoted_text`；完整 `referenceList` 保存在 `raw_response_json`。 |
| D6 | 品牌指标以本地计算为准 | Provider 的 `mentionPosition/sentiment/rankings` 只写入 raw 或 `context_json.provider_*`，不覆盖本地确定性指标。 |
| D7 | 模式字段采用通用 `provider_mode_by_platform` | 替代 `aidso_thinking_enabled_by_platform`；值限定 `standard/reasoning/search/reasoning_search`。 |
| D8 | 前端不在本阶段默认开发 | 仅更新后端 API 契约与文档；除非用户明确要求，不改 `frontend/`。 |

## 3. 改动前代码基线（M0 快照）

### 3.1 采集源与 Run 契约

| 项 | 当前状态 |
| --- | --- |
| `CollectionSource` 枚举 | `official`、`aidso`（`schemas.py`） |
| `geo_monitor_run.collection_source` CHECK | `official/aidso`（迁移 `geo_monitoring_0007`） |
| Run 创建字段 | `aidso_thinking_enabled_by_platform: dict[str, bool]` |
| 平台过滤 | Aidso run 仅 `adapter_type=aidso`；官方 run 排除 Aidso（`services/runs.py`） |

### 3.2 Aidso 适配与轮询

| 项 | 当前状态 |
| --- | --- |
| 适配器 | `backend/app/geo_monitoring/adapters/aidso.py` |
| 协议 | `PlatformAdapter.query(PlatformQuery, credential) -> PlatformAnswer` |
| Pending | `AidsoPendingError` + `QueryTask.request_json` 保存 `aidso_req_id/aidso_task_id/aidso_platform_name/aidso_thinking_enabled/aidso_poll_count` |
| 轮询上限 | `COLLECTION_AIDSO_MAX_POLLS=120`（`config.py`） |
| Registry | `build_adapter_registry` 按 `AIDSO_ENABLED` 注册 Aidso 平台 |

### 3.3 Aidso 平台种子（12 个）

定义于 `services/platforms.py` 的 `AIDSO_PLATFORM_MAPPINGS`：

- `aidso_doubao_web/app`、`aidso_deepseek_web/app`、`aidso_kimi_web`
- `aidso_yuanbao_web/app`、`aidso_qwen_web/app`
- `aidso_baidu_web`、`aidso_douyin_web`、`aidso_wenxin_web`

模力指数侧将替换为 11 个 `molizhishu_*` 平台（见任务书 §4），不含 Aidso 的 `douyin`，新增 `quark`、`weibo_zhisou` 等。

### 3.4 配置项（Aidso，M1 前）

```
AIDSO_ENABLED=False
AIDSO_BASE_URL=https://odapi.aidso.com
AIDSO_API_TOKEN=""
COLLECTION_AIDSO_MAX_POLLS=120
```

模力指数配置（`MOLIZHISHU_*`）由 **Task M1** 引入，见 `backend/app/core/config.py` 与 `.env.example`。

### 3.5 数据库迁移 head

```
geo_monitoring_0010 (head)
```

### 3.6 相关测试文件（后续 M 系列需迁移/扩展）

| 区域 | 代表测试 |
| --- | --- |
| Aidso 适配器 | `backend/tests/geo_monitoring/adapters/test_aidso.py` |
| Run 创建 | `backend/tests/geo_monitoring/test_runs.py`（含 aidso run） |
| 模型 | `backend/tests/geo_monitoring/test_models.py` |
| Worker 轮询 | `backend/tests/worker/test_collection_actor.py`（含 pending/max_poll） |
| Registry | `backend/tests/geo_monitoring/adapters/test_registry.py` |

模力指数专用测试目录/文件在 M0 阶段**尚未创建**；自 M1 起按 TDD 逐 Task 新增。

## 4. M0 基线验收执行记录

执行环境：Windows，`backend/.venv`，UTF-8 终端。

> 说明：本节记录的是 M0 执行时的基线结果，不代表后续 Task 开始时的实时工作树状态。后续执行 M1+ 前仍需重新运行 `git -c core.quotepath=false status --short`，并按当前输出保护用户或其他 Agent 的未提交改动。

| 命令 | 结果 |
| --- | --- |
| `git -c core.quotepath=false status --short` | 工作树干净；分支 `feat/third-party-collector-api-adapter`，与 `origin` 同步 |
| `backend\.venv\Scripts\python.exe -m pytest -q backend\tests\geo_monitoring` | **391 passed**，2 warnings（Starlette httpx 弃用、LangGraph cache 弃用），**0 failed** |
| `backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads` | `geo_monitoring_0010 (head)` |

### 4.1 基线失败项

无。当前 `backend/tests/geo_monitoring` 全绿，M0 不修复、不改动业务代码。

### 4.2 M0 范围外已知后续工作（不在本 Task 修复）

以下由 M1–M15 按任务书顺序实现，此处仅作索引：

1. **M1** — `MOLIZHISHU_*` Settings 与校验
2. **M2** — `MOLIZHISHU_PLATFORM_MAPPINGS` 与 11 个平台种子
3. **M3** — CHECK 扩展、`provider_mode_by_platform` 字段迁移
4. **M4** — `RunCreate` 契约与 `CollectionSource.MOLIZHISHU`
5. **M5–M8** — Client/Adapter、Registry、Collection 轮询、结果归一化
6. **M9–M15** — Callback、Region、批量化、文档下线 Aidso 等

### 4.3 后续 Cursor 执行约束

1. 任何 M 系列开发任务都先读 Task 索引，再局部读取主任务书对应章节；本文只提供 M0 决策背景。
2. P0 阶段先复用现有 `PlatformAdapter` 与单 QueryTask pending 轮询机制，不提前重写为 ProviderBatch。
3. `molizhishu_*` 平台码、供应商平台标识、默认 mode 以主任务书 §4 为唯一口径。
4. 自动测试必须 mock 模力指数接口；真实接口联调只能通过 M13 smoke 脚本手动执行。
5. 历史 Aidso 数据与迁移保留兼容，新建第三方采集入口使用 `collection_source=molizhishu`。

## 5. 测试先行约定（供 M1+ 引用）

1. 所有 M 系列代码 Task 先写**失败测试**，再最小实现（见 `.cursor/rules/superpowers-dev-workflow.mdc`）。
2. 单元/集成测试使用 **mock/respx**，禁止自动访问真实模力指数 API。
3. 真实联调仅通过 **M13 smoke 脚本**手动执行，并明确费用风险。
4. pytest 默认范围：`backend/tests/geo_monitoring`；worker 相关见 `backend/tests/worker/`。
5. Windows 报告存储相关测试若遇权限问题，使用 `--basetemp .pytest-tmp` 并提权（见 `AGENTS.md`）。

## 6. 参考文档

- 主任务书：`docs/Cursor模力指数API替换Aidso开发任务书.md`
- Task 索引：`docs/Cursor模力指数API替换Aidso开发任务书_Task索引.md`
- 平台映射口径：任务书 §4
- 采集生命周期：`docs/采集任务生命周期说明.md`（M7/M10 起同步更新）
