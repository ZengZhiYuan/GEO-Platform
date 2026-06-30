# 线上版本代码优化整改 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将当前以 MVP、mock 验证和本地联调为主的 AI 应用监测后端，整改为可上线运行、可真实采集、可真实 Agent 分析、可审计的生产版本。

**Architecture:** 保留现有 FastAPI / SQLAlchemy / Dramatiq / APScheduler / LangGraph 结构，优先做安全清理、配置前置校验、真实 provider 闭环和线上 smoke。规则型 MVP 能力先明确标识与验收边界，再按业务价值替换为真实 LLM 或生产级规则服务。

**Tech Stack:** Python, FastAPI, Pydantic Settings, SQLAlchemy 2.0, Alembic, Redis, Dramatiq, APScheduler, LangGraph, OpenAI-compatible / DashScope Agent LLM, httpx, React 18, Vite, Ant Design.

---

## 一、审计结论摘要

结论：当前代码已具备后端闭环和模力指数真实 adapter 基础，但仍是“接近联调版”的状态，不建议直接作为线上版本发布。

主要原因：

1. 当前 `.env` 中第三方采集与 Agent LLM 的真实凭证已经配置，但 `MOLIZHISHU_ENABLED=false`，官方平台 `*_ENABLED=false`，真实采集不会按预期注册 adapter。
2. Agent LLM 生产路径存在测试默认值兜底：`AGENT_LLM_*` 为空时会退到 `https://agent-llm.test/v1`、`test-agent-key`、`agent-model`。
3. `backend/app/test/kimi_web_chat.py` 存在硬编码网页端 JWT / device/session 标识，且 Dockerfile 会复制整个 `backend` 目录进入镜像。
4. 业务 API 当前未配置鉴权，API 文档明确写着联调无需 `Authorization`。
5. 若干功能仍是 MVP 规则实现或占位实现：AI 生成、评价标签聚类、前端首页、用户偏好。
6. 自动化测试大量使用 StubBroker、respx mock、FakeLLMClient，这是正确的单元/集成测试策略，但目前缺少生产配置 preflight 与真实 smoke 的自动化门禁。

---

## 二、当前发现分类

### A. 仅用于 MVP 或阶段性占位的模块

| 模块 | 文件 | 当前状态 | 线上风险 |
|---|---|---|---|
| AI 生成品牌词 / 竞品 / 问题 | `backend/app/geo_monitoring/services/ai_generation.py` | 文档与代码均说明为 MVP 确定性规则；固定词库、通用竞品、五类问题模板 | 用户以为是“AI 生成”，实际不调用 Agent LLM，覆盖行业极窄 |
| 高频评价标签 | `backend/app/geo_monitoring/services/evaluation_tags.py` | `cluster_method=rule`，关键词规则聚类 | 可解释但不智能，复杂语义与新行业效果有限 |
| 管理端首页 | `frontend/src/pages/MonitoringHomePage.tsx` | 仅显示“基础架构已就绪”，页面后续接入 | 不是可用管理端，线上只适合作后端 API 版本 |
| 当前项目偏好 | `docs/API接口文档.md` | 因 MVP 无用户认证而延后 | 多用户/多租户场景不可用 |
| 鉴权与用户体系 | `docs/API接口文档.md` | 明确当前业务接口未配置鉴权 | 线上 P0 安全缺口 |
| 竞品基准卡 | `docs/API接口文档.md` | 行业均值等为 `static_config` | 运营指标可能被误认为真实行业基准 |

### B. 仅为 mock 测试或最小验证而存在的模块

| 模块 | 文件 | 当前状态 | 是否可保留 |
|---|---|---|---|
| Stub broker | `backend/tests/**`, `backend/app/worker/broker.py` | pytest 默认 `DRAMATIQ_BROKER=stub`；生产 `.env` 为 redis | 测试可保留，生产需禁止 stub |
| Fake Agent LLM | `backend/tests/geo_monitoring/agents/test_graph.py` 及引用测试 | 用于分析链路测试 | 测试可保留，生产路径不可兜底到假配置 |
| respx mock 平台 HTTP | `backend/tests/geo_monitoring/adapters/*`, `test_molizhishu_*` | 单元测试不访问真实 API | 正确做法，应保留 |
| e2e mock 流水线 | `backend/tests/e2e/test_monitoring_mvp.py` | mock 平台 + Fake Agent | 可保留为快速回归，但需要新增真实 smoke 分层 |
| 手工厂商脚本 | `backend/app/test/*.py` | 手工测试/逆向研究脚本混入 app 包 | 不应进入生产镜像；Kimi 脚本含硬编码凭证，必须清理 |
| 旧 worker 空入口 | `backend/app/workers/*` | 历史兼容/空 bootstrap；正式部署用 `app.worker.actors.*` | 建议归档或删除，避免启动歧义 |

### C. 未实际用到当前 `.env` 已配置的真实第三方采集 API 的位置

| 位置 | 证据 | 影响 |
|---|---|---|
| 模力指数开关 | `.env` 中 `MOLIZHISHU_API_TOKEN` 有值，但 `MOLIZHISHU_ENABLED=false` | `build_adapter_registry()` 不注册 `MolizhishuAdapter`，key pool 也不注册 token |
| 平台数据库与运行配置不一致 | 迁移将 `molizhishu_*` 平台种子设为 `enabled=true`，但运行时 adapter 受 `.env` 开关控制 | 用户可创建平台任务，但 worker 执行时可能才失败 |
| Run 创建前置校验不足 | `runs.prepare_run_create()` 只按 DB 平台 enabled 校验，不校验 adapter registry / credentials | 错误延迟到异步采集阶段，线上体验差 |
| ProviderBatch 默认值 | `Settings.MOLIZHISHU_PROVIDER_BATCH_ENABLED=True`，但当前 `.env` 缺该键 | 运行使用代码默认值；生产配置显式性不足 |
| 真实 smoke | `backend/scripts/molizhishu_smoke_test.py` 可手动真实调用，但不写业务库、不触发 worker | 只能验证 adapter，不能证明线上采集闭环 |

### D. 未严格使用真实 Agent 模型 URL / API key 的位置

| 位置 | 证据 | 影响 |
|---|---|---|
| Agent 配置默认兜底 | `backend/app/geo_monitoring/services/analysis.py` 中 `build_agent_llm_config()` 对空配置使用 test URL/key/model | 生产漏配时不会 fail fast，而是尝试请求测试地址 |
| 分析 API 同步调用 | `backend/app/geo_monitoring/api/analysis.py` 直接同步触发 `run_analysis()` | 真实 LLM 可能耗时 20-120 秒，同步 API 易超时 |
| 分析 worker | `backend/app/worker/actors/analysis.py` 使用真实 settings 构建 LLM client | 当前 `.env` 有真实 Agent 值会使用；但缺少 prod 必填校验 |
| Fake LLM 测试覆盖多 | 多个 API 与报表测试 patch `FakeLLMClient` | 单测合理，但缺少真实 Agent smoke 与超时/成本门禁 |

---

## 三、整改 Task 拆分

### Task O0：生产安全清理与密钥止血

**目标：** 清理所有会进入镜像的开发脚本、硬编码凭证和逆向研究代码。

**Files:**
- Modify: `backend/app/test/kimi_web_chat.py`
- Modify: `backend/app/test/doubao_test.py`
- Modify: `backend/app/test/hunyuan_test.py`
- Modify: `backend/app/test/qwen_test.py`
- Modify: `.dockerignore`
- Modify: `Dockerfile`
- Test: `backend/tests/test_deployment_contract.py`
- Test: `backend/tests/test_security.py`

- [ ] 删除或迁移 `backend/app/test`。建议迁到 `backend/scripts/manual/`，并确保 Docker 镜像不复制该目录。
- [ ] 移除 `kimi_web_chat.py` 中硬编码 JWT、device_id、session_id、traffic_id，改为从环境变量读取；历史凭证视为已泄露，需要立即轮换。
- [ ] `.dockerignore` 或 Docker build 中排除 `backend/app/test`、`backend/scripts/manual`、本地报告、临时测试目录。
- [ ] 新增安全测试：扫描 `backend/app` 内不得出现 `JWT = (`、`kimi-auth=`、长 Bearer token、私有协议手工脚本。
- [ ] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/test_security.py backend/tests/test_deployment_contract.py`。

### Task O1：生产配置 fail-fast 与环境画像

**目标：** 线上启动时明确拒绝测试配置、空配置和 stub broker。

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `README.md`
- Test: `backend/tests/test_config.py`

- [ ] 增加生产环境校验：当 `APP_ENV=prod` 时，`DRAMATIQ_BROKER` 必须为 `redis`，不得为 `stub`。
- [ ] 增加 Agent LLM 生产必填校验：`AGENT_LLM_BASE_URL`、`AGENT_LLM_API_KEY`、`AGENT_LLM_MODEL` 不能为空。
- [ ] 增加第三方采集生产显式校验：若希望线上启用模力指数，则 `.env` 必须显式提供 `MOLIZHISHU_ENABLED=true`、`MOLIZHISHU_API_TOKEN`、`MOLIZHISHU_PROVIDER_BATCH_ENABLED`。
- [ ] `runtime_summary()` 输出增加 `provider_batch_enabled`、`callback_enabled`、`regions_cache_seconds`，仍不得输出 token。
- [ ] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/test_config.py`。

### Task O2：Agent LLM 真实配置强制使用

**目标：** 生产分析不得回退到 test URL/key/model。

**Files:**
- Modify: `backend/app/geo_monitoring/services/analysis.py`
- Modify: `backend/app/worker/actors/analysis.py`
- Modify: `backend/app/geo_monitoring/api/analysis.py`
- Test: `backend/tests/geo_monitoring/agents/test_llm.py`
- Test: `backend/tests/worker/test_analysis_actor.py`

- [ ] 移除 `build_agent_llm_config()` 的测试默认值兜底；测试中显式构造 `AgentLLMConfig` 或 patch settings。
- [ ] 配置为空时抛出业务错误，错误信息不得包含 key 明文。
- [ ] 将手动分析 API 改为异步入队或增加超时策略，避免真实 LLM 同步阻塞 HTTP 请求。
- [ ] 新增测试：空 Agent 配置在 prod 下启动失败；dev/test 可通过显式 FakeLLMClient 测试。
- [ ] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/agents backend/tests/worker/test_analysis_actor.py`。

### Task O3：模力指数真实采集闭环前置校验

**目标：** `collection_source=molizhishu` 创建 Run 前就能确认真实 provider 可用。

**Files:**
- Modify: `backend/app/geo_monitoring/services/runs.py`
- Modify: `backend/app/geo_monitoring/services/collection.py`
- Modify: `backend/app/geo_monitoring/adapters/registry.py`
- Modify: `backend/app/geo_monitoring/services/provider_batches.py`
- Test: `backend/tests/geo_monitoring/test_molizhishu_collection.py`
- Test: `backend/tests/geo_monitoring/test_molizhishu_provider_batch.py`
- Test: `backend/tests/geo_monitoring/test_runs.py`

- [ ] 在 `prepare_run_create()` 中校验 collection_source 与 runtime adapter registry 一致：平台在 DB enabled 但 adapter 未注册时，直接返回 409/422。
- [ ] 对 `molizhishu_*` 平台校验 `MOLIZHISHU_ENABLED=true` 且 token 可用。
- [ ] 对官方平台校验对应 `*_ENABLED=true`、model、key/credential 完整。
- [ ] 增加配置诊断接口或扩展 `/ready`，显示平台 “db_enabled / runtime_configured / credential_count / adapter_registered” 的脱敏状态。
- [ ] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_runs.py backend/tests/geo_monitoring/test_molizhishu_collection.py backend/tests/geo_monitoring/test_molizhishu_provider_batch.py`。

### Task O4：真实第三方采集 smoke 分层

**目标：** 区分 mock 回归、真实 provider 只读 smoke、真实业务闭环 smoke。

**Files:**
- Modify: `backend/scripts/molizhishu_smoke_test.py`
- Create: `backend/scripts/run_production_smoke_test.py`
- Modify: `docs/API测试文档.md`
- Modify: `README.md`

- [ ] 保留 `molizhishu_smoke_test.py` 为 adapter 层真实接口验证，明确可能产生费用。
- [ ] 新增业务闭环 smoke：创建最小项目/品牌/prompt set，创建 `collection_source=molizhishu` Run，等待 worker 完成，触发分析，生成报告。
- [ ] smoke 默认 dry-run 检查配置；必须显式 `--allow-paid-provider` 才真实调用。
- [ ] 输出不包含 token、完整 prompt 响应或敏感业务数据。
- [ ] 验收命令：mock 使用 pytest；真实 smoke 仅手动执行并记录结果。

### Task O5：MVP AI 生成替换为真实 Agent LLM

**目标：** “AI 生成品牌词/竞品/问题”不再只是固定规则模板。

**Files:**
- Modify: `backend/app/geo_monitoring/services/ai_generation.py`
- Modify: `backend/app/geo_monitoring/api/ai_generation.py`
- Modify: `backend/app/geo_monitoring/agents/prompts.py`
- Modify: `backend/app/geo_monitoring/agents/schemas.py`
- Test: `backend/tests/geo_monitoring/test_ai_generation_api.py`

- [ ] 增加 LLM 生成模式，输出结构化 schema：品牌词、竞品、问题列表。
- [ ] 保留 deterministic fallback，但响应中返回 `generation_method=llm|rule_fallback`。
- [ ] 增加成本/超时控制：limit、max_input_chars、超时、失败降级。
- [ ] 测试覆盖 LLM 成功、LLM 失败回退、结构化输出非法、敏感信息脱敏。
- [ ] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_ai_generation_api.py`。

### Task O6：评价标签从规则聚类升级为生产可用分析

**目标：** 当前 `cluster_method=rule` 作为基础能力保留，同时支持 LLM/离线聚类策略。

**Files:**
- Modify: `backend/app/geo_monitoring/services/evaluation_tags.py`
- Modify: `backend/app/geo_monitoring/schemas.py`
- Modify: `docs/API接口文档.md`
- Test: `backend/tests/geo_monitoring/test_evaluation_tags_api.py`

- [ ] 增加 `cluster_method` 入参：`rule`、`llm`、`auto`。
- [ ] `auto` 默认先规则命中，样本量足够时走 LLM 聚类。
- [ ] LLM 聚类结果写入可复用缓存或分析 JSON，避免重复请求。
- [ ] 文档明确规则口径、LLM 口径、成本和失败回退。
- [ ] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/geo_monitoring/test_evaluation_tags_api.py`。

### Task O7：鉴权、租户与权限边界

**目标：** 线上 API 不再裸奔，项目/品牌/Run/报告按用户或租户隔离。

**Files:**
- Create/Modify: `backend/app/core/security.py`
- Modify: `backend/app/geo_monitoring/api/*.py`
- Modify: `backend/app/geo_monitoring/models.py`
- Create: Alembic migration for user/tenant ownership fields
- Test: `backend/tests/test_security.py`
- Test: `backend/tests/geo_monitoring/*`

- [x] 引入统一认证依赖，至少支持 Bearer token / API token。
- [x] 为项目、品牌、prompt set、run、report 增加 owner/tenant 字段或访问控制策略。
- [x] 回调接口继续使用 `X-Callback-Token`，不得混用普通用户鉴权。
- [x] API 文档更新：移除“业务接口未配置鉴权”的说明。
- [x] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/test_security.py backend/tests/geo_monitoring`。

### Task O8：前端从占位页升级为线上管理端

**目标：** 替换 `MonitoringHomePage` 占位页，接入项目、品牌、Prompt、平台、Run、报告核心工作流。

**Files:**
- Modify: `frontend/src/pages/MonitoringHomePage.tsx`
- Create/Modify: `frontend/src/api/*`
- Create/Modify: `frontend/src/router/index.tsx`
- Test: `frontend` 相关测试

- [ ] 首页直接展示项目列表、运行状态、创建运行入口。
- [ ] 平台配置页展示 DB enabled 与 runtime configured 状态。
- [ ] Run 详情页展示任务、采集来源、ProviderBatch、分析状态和报告下载。
- [ ] 前端接入鉴权 token 与 API 错误处理。
- [ ] 验收命令：`npm test`、`npm run build`。

### Task O9：部署入口与镜像瘦身

**目标：** 镜像只包含生产运行必需文件，启动入口唯一清晰。

**Files:**
- Modify: `Dockerfile`
- Modify: `.dockerignore`
- Modify: `docker-compose.yml`
- Modify: `backend/app/workers/*`
- Test: `backend/tests/test_deployment_contract.py`

- [x] 移除或归档 `app.workers` 历史空入口。
- [x] Dockerfile 避免复制测试、手工脚本、缓存、临时目录。
- [x] Compose smoke 从 “mock run” 升级为 “config preflight + ready + optional real smoke”。
- [x] 验收命令：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests/test_deployment_contract.py`。

### Task O10：上线验收与观测

**目标：** 建立线上发布前的固定验收清单。

**Files:**
- Modify: `README.md`
- Modify: `docs/采集任务生命周期说明.md`
- Modify: `docs/API测试文档.md`
- Modify: `backend/scripts/run_api_full_test.py`

- [x] 增加生产 preflight 命令：配置摘要、adapter registry、credential count、Redis/DB ready。
- [x] 增加 worker 消费检查：collection / analysis / report 三队列。
- [x] 增加模力指数 provider batch 指标：submitted、processing、completed、failed、poll_count。
- [x] 增加 Agent LLM 观测：调用次数、失败分类、token usage、耗时分布。
- [x] 验收命令：`backend\.venv\Scripts\python.exe backend\scripts\run_api_full_test.py --base-url http://127.0.0.1:8000`，真实 provider smoke 手动开启。

---

## 四、建议执行顺序

1. O0 安全清理：先处理硬编码 JWT 与镜像包含测试脚本问题。
2. O1/O2 配置强约束：让生产环境不能用假配置启动。
3. O3/O4 真实采集闭环：解决 `.env` 已配但实际不调用的问题。
4. O7 鉴权：上线前必须完成。
5. O5/O6/O8 产品化增强：把 MVP 规则和占位页逐步替换为真实能力。
6. O9/O10 工程发布：镜像、部署、观测和 smoke 固化。

---

## 五、当前 `.env` 配置快照（脱敏）

| 配置项 | 当前状态 | 结论 |
|---|---|---|
| `DRAMATIQ_BROKER` | `redis` | 符合生产方向 |
| `MOLIZHISHU_API_TOKEN` | 已配置 | 具备真实第三方采集 token |
| `MOLIZHISHU_ENABLED` | `false` | 真实模力指数 adapter 不会注册 |
| `MOLIZHISHU_PROVIDER_BATCH_ENABLED` | 未显式配置 | 使用代码默认 true，生产建议显式配置 |
| `AGENT_LLM_BASE_URL` | 已配置 | Agent 可使用真实 URL |
| `AGENT_LLM_API_KEY` | 已配置 | Agent 可使用真实 key |
| `AGENT_LLM_MODEL` | 已配置 | Agent 可使用真实模型 |
| `AGENT_LLM_PROVIDER` | 未显式配置 | 使用默认 `openai_compatible`；若 URL 为 DashScope 原生 API，需人工确认 provider 是否应为 `dashscope` |
| 官方平台 `*_ENABLED` | 均为 false 或不完整 | 官方平台真实采集不会注册对应 adapter |

---

## 六、上线前最低验收门槛

- [ ] 仓库和镜像不包含硬编码 JWT、API key、网页端私有 token。
- [ ] `APP_ENV=prod` 下缺失真实 Agent LLM 配置会启动失败。
- [ ] `MOLIZHISHU_ENABLED=true` 且 token 配置后，`collection_source=molizhishu` 的 Run 能从创建、ProviderBatch、轮询/回调、落库、分析、报告完整闭环。
- [ ] `MOLIZHISHU_ENABLED=false` 时，用户无法创建 `collection_source=molizhishu` Run，错误在同步 API 阶段返回。
- [ ] 业务 API 有鉴权，项目/Run/报告有访问隔离。
- [ ] pytest mock 回归通过，真实 provider smoke 手动记录通过。
- [ ] 文档同步更新 `.env.example`、README、API 文档和测试文档。
