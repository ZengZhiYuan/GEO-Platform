# AI 应用监测领域替换重构设计

## 1. 背景与目标

当前仓库是一个内容生成管理系统，包含关键词库、标题灵感、画像图库、品牌知识库、写作规范、写作任务、文章和 Mock AI 生成 Worker。新的产品目标是只提供 AI 应用监测能力，不再保留内容生成业务。

本次重构采用“领域替换”方式：保留可复用基础设施，删除旧业务领域，以根目录 `AI应用监测_技术开发文档.md` 为上位业务规格，建立 AI 应用监测的配置域和运行骨架。

本轮目标：

1. 保留 FastAPI、SQLAlchemy、Alembic、PostgreSQL、Redis/Dramatiq 配置、统一响应、异常处理和 React 管理端基础壳。
2. 删除全部旧内容生成业务代码和页面。
3. 重建数据库迁移基线，不兼容旧业务数据库原地升级。
4. 实现监测项目、品牌、Prompt 集、Prompt、AI 平台、监测运行和查询子任务的后端基础。
5. 创建监测运行时，只在数据库生成“启用 Prompt × 启用平台”的查询子任务，不投递消息、不调用外部平台。
6. 清理旧文档并重写 `CLAUDE.md`。

## 2. 非目标

以下能力不在本轮实现：

- 真实 AI 平台 API 调用和密钥管理。
- Dramatiq 采集 Actor、并发限流、失败重试执行。
- Answer、Citation、品牌识别结果入库。
- LangChain/LangGraph 多 Agent 分析。
- 指标快照、趋势、定时任务、HTML/PDF 报告。
- AI 应用监测的具体前端管理页面。
- 旧内容生成数据迁移或旧接口兼容层。

## 3. 总体方案

### 3.1 保留的基础设施

后端保留并按需调整：

- `app/main.py`：FastAPI 应用工厂、CORS、全局异常处理和路由注册。
- `app/core/config.py`：应用、数据库和 Redis 配置。删除旧文章生成专属配置。
- `app/core/database.py`：同步 SQLAlchemy 引擎、Session 工厂和声明式 Base。
- `app/core/response.py`：统一 `code/message/data` 响应和分页结构。
- `app/core/exceptions.py`：业务异常与全局异常处理。
- `app/models/base.py`：公共主键、时间、软删除、租户和操作人字段。
- Alembic、PostgreSQL 16、Redis 7 和 Docker Compose。
- Dramatiq 依赖和通用 Broker 配置可以保留，但本轮不注册业务 Actor。

前端保留：

- Vite、React、TypeScript、Ant Design、React Router、Axios。
- 应用入口、统一请求客户端、基础布局、404 页面。
- 左侧菜单仅保留“AI 应用监测”入口，首页使用明确的建设中占位页。

### 3.2 删除的旧业务

后端删除：

- keyword、title_inspiration、image_category、image_asset、brand_knowledge、writing_rule、content_category、writing_task、article 相关 Model、Schema、Service 和 Endpoint。
- 文章生成上下文、Prompt 组装、MockAIWriter、文章 Actor 和旧任务聚合逻辑。
- 旧业务 Alembic 迁移。

前端删除：

- `src/pages/material/` 和 `src/pages/workspace/` 下全部旧页面。
- 旧业务 API 文件、业务 types、枚举和仅服务旧页面的工具代码。
- 旧菜单、旧路由和旧产品文案。

文档清理：

- 实施阶段删除 `docs/` 下原有全部旧文档和进度分片。
- `docs/` 目录最终只保留本次重构新建的 `docs/superpowers/specs/` 和 `docs/superpowers/plans/`。
- 根目录 `AI应用监测_技术开发文档.md` 保留。

## 4. 后端领域设计

新增独立领域包 `app/geo_monitoring/`，按领域内聚，而不是继续把所有业务拆散到全局 models/schemas/services/endpoints 目录。

建议结构：

```text
backend/app/geo_monitoring/
  __init__.py
  api.py
  models.py
  schemas.py
  services/
    __init__.py
    projects.py
    brands.py
    prompts.py
    platforms.py
    runs.py
```

公共基础设施仍位于 `app/core/` 和 `app/models/base.py`。`geo_monitoring` 可以依赖 core 和 BaseModel，core 不依赖业务域。

### 4.1 MonitorProject

表名：`geo_monitor_project`

关键字段：

- `project_name`
- `industry`，默认 `文旅演艺`
- `description`
- `timezone`，默认 `Asia/Shanghai`
- `status`：`active | disabled | archived`
- `official_domain`
- `report_title`
- `report_subtitle`

项目采用软删除。删除项目时，本轮不物理级联删除关联数据；Service 必须阻止已删除项目继续创建配置或运行。

### 4.2 Brand 与 BrandAlias

表名：`geo_brand`、`geo_brand_alias`

Brand：

- 属于一个项目。
- `brand_type`：`target | competitor | candidate`。
- 每个未删除项目最多存在一个未删除的目标品牌。
- 同一项目内品牌名称唯一。
- `status`：`active | disabled`。

BrandAlias：

- 属于一个品牌。
- `match_mode`：`exact | contains | context`。
- 支持 `is_ambiguous`、`context_keywords` 和 `enabled`。
- 同一品牌内别名唯一。

### 4.3 PromptSet 与 Prompt

表名：`geo_prompt_set`、`geo_prompt`

PromptSet：

- 属于一个项目。
- `version_no` 在项目内唯一。
- `status`：`draft | active | archived`。
- 每个项目最多存在一个 active Prompt 集。
- `prompt_count` 由 Prompt Service 在新增、删除时维护。
- 激活时计算 `checksum`，记录 `activated_at`，并将该项目原 active 集归档。

Prompt：

- 属于一个 Prompt 集。
- `prompt_code` 在 Prompt 集内唯一。
- 包含 `prompt_text`、`prompt_type`、`scene_tag`、`contains_brand`、`enabled`、`sort_order` 和 `content_hash`。
- active 或 archived Prompt 集禁止修改 Prompt，避免历史运行口径漂移。

### 4.4 AIPlatform

表名：`geo_ai_platform`

关键字段：

- `platform_code`，全局唯一且创建后不可修改。
- `platform_name`
- `adapter_type`
- `base_url`
- `model_name`
- `search_enabled`
- `citation_supported`
- `max_concurrency`，必须大于 0。
- `timeout_seconds`，必须大于 0。
- `enabled`
- `extra_config` JSON。

新基线预置 `doubao`、`qwen`、`yuanbao`、`deepseek`、`kimi` 五个平台。本轮不保存明文 API Key，不实现连接测试。

### 4.5 MonitorRun 与 QueryTask

表名：`geo_monitor_run`、`geo_query_task`

MonitorRun：

- 属于项目和 Prompt 集。
- `run_no` 全局唯一，由服务生成。
- 本轮只允许 `trigger_type=manual`。
- 初始 `status=pending`、`collection_status=pending`。
- `analysis_status=skipped`、`report_status=skipped`，明确本轮不执行分析和报告。
- 保存 `platform_codes`、Prompt 集版本快照、预期查询数和进度统计字段。

QueryTask：

- 属于一次运行，引用一个 Prompt 和一个平台代码。
- 初始 `status=pending`。
- `idempotency_key` 全局唯一，格式为 `run:{run_id}:prompt:{prompt_id}:platform:{platform_code}`。
- 同一运行内 `(prompt_id, platform_code)` 唯一。
- 预留 `retry_count`、`request_json`、HTTP 状态、错误、耗时和起止时间。

## 5. 运行创建规则

创建运行的请求包含：

- `project_id`
- `prompt_set_id`，可省略；省略时使用项目当前 active Prompt 集。
- `platform_codes`，可省略；省略时使用全部 enabled 平台。

Service 在一个数据库事务中执行：

1. 校验项目存在、未删除且状态为 active。
2. 校验 Prompt 集属于该项目，状态为 active。
3. 查询 Prompt 集下全部未删除且 enabled 的 Prompt，至少一条。
4. 校验平台代码存在、未删除且 enabled，至少一个。
5. 创建 MonitorRun 并取得 ID。
6. 为每个 Prompt 和平台组合创建 QueryTask。
7. 写入 `expected_query_count = prompt_count × platform_count`。
8. 一次提交事务。

任何校验或写入失败必须整体回滚，不得留下半成品 Run 或 QueryTask。本轮提交后不调用 Dramatiq。

## 6. API 设计

统一前缀：`/api/geo-monitoring`

项目：

- `POST /projects`
- `GET /projects`
- `GET /projects/{project_id}`
- `PUT /projects/{project_id}`
- `DELETE /projects/{project_id}`

品牌与别名：

- `POST /projects/{project_id}/brands`
- `GET /projects/{project_id}/brands`
- `GET /brands/{brand_id}`
- `PUT /brands/{brand_id}`
- `DELETE /brands/{brand_id}`
- `POST /brands/{brand_id}/aliases`
- `GET /brands/{brand_id}/aliases`
- `PUT /brand-aliases/{alias_id}`
- `DELETE /brand-aliases/{alias_id}`

Prompt 集和 Prompt：

- `POST /projects/{project_id}/prompt-sets`
- `GET /projects/{project_id}/prompt-sets`
- `GET /prompt-sets/{prompt_set_id}`
- `PUT /prompt-sets/{prompt_set_id}`
- `DELETE /prompt-sets/{prompt_set_id}`
- `POST /prompt-sets/{prompt_set_id}/activate`
- `POST /prompt-sets/{prompt_set_id}/prompts`
- `GET /prompt-sets/{prompt_set_id}/prompts`
- `PUT /prompts/{prompt_id}`
- `DELETE /prompts/{prompt_id}`

平台：

- `GET /platforms`
- `GET /platforms/{platform_code}`
- `PUT /platforms/{platform_code}`

运行：

- `POST /runs`
- `GET /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/query-tasks`

所有接口继续使用统一响应结构。列表接口支持分页，过滤条件按实体状态、名称、项目、运行状态或平台代码提供。

## 7. 数据库与迁移策略

项目尚未正式投产，本次选择全新基线：

1. 删除 `backend/alembic/versions/` 下全部旧业务迁移。
2. 创建单一 baseline revision。
3. baseline 一次创建本轮 8 张表及必要索引、唯一约束和检查约束。
4. baseline 插入五个平台基础数据。
5. 不提供从旧内容生成表升级到新监测表的迁移路径。

已有本地数据库需要删除并重建数据卷，不能直接对旧库执行新 baseline。

## 8. 前端目标形态

前端本轮只保留应用壳：

- 产品名称改为“AI 应用监测”。
- 左侧仅保留一个“监测概览”菜单。
- `/` 重定向到 `/monitoring`。
- `/monitoring` 显示建设中页面，说明配置管理和运行管理将在后续阶段接入。
- Axios 客户端保留，Base URL 继续默认为 `http://localhost:8000/api`。
- 删除所有旧业务 API、types、页面和枚举。

## 9. CLAUDE.md 重写要求

新的 `CLAUDE.md` 必须：

- 将项目定位改为 AI 应用监测平台。
- 指定 `AI应用监测_技术开发文档.md` 为业务设计来源，本设计和实施计划为当前阶段执行依据。
- 描述新的领域边界、分层、接口前缀和运行状态规则。
- 明确数值指标未来必须由程序确定性计算，LLM 只承担语义分析和建议生成。
- 明确采集、分析、报告分阶段解耦，不在数据库长事务中调用外部 API 或 LLM。
- 明确新增功能必须有测试和迁移，禁止恢复旧内容生成模块。
- 删除旧任务编号、旧页面规则和旧进度分片约定。

## 10. 测试策略

后端新增正式测试目录和依赖，至少覆盖：

- 应用启动、健康检查和统一响应。
- 旧业务路由不存在。
- 项目 CRUD 和软删除。
- 单项目唯一目标品牌。
- 品牌别名唯一性。
- Prompt 集激活及单 active 约束。
- active Prompt 集禁止修改 Prompt。
- 平台更新校验。
- 创建运行时生成正确的 Prompt × 平台笛卡尔积。
- 指定平台、默认平台和默认 active Prompt 集。
- 无 Prompt、无平台、跨项目 Prompt 集等失败场景。
- 创建运行异常时事务整体回滚。

前端验收：

- TypeScript 类型检查和 Vite 生产构建通过。
- 旧业务路由和菜单不可访问。
- `/monitoring` 可正常渲染管理端壳和占位内容。

迁移验收：

- Alembic 只有一个 head。
- 离线 SQL 可完整生成。
- 在空 PostgreSQL 上可执行 `upgrade head`。

## 11. 完成标准

满足以下条件才视为本轮完成：

1. 仓库中不存在旧内容生成业务的可执行后端代码和前端页面。
2. 新监测领域 8 张表、Schema、Service 和 API 可用。
3. 运行创建严格只落库，并正确创建查询子任务。
4. 新 baseline 可在空库初始化。
5. 前端只保留 AI 应用监测管理壳。
6. `docs/` 只保留本次 spec 和 plan。
7. `CLAUDE.md` 已与新系统一致。
8. 后端测试、前端构建和迁移验证均有新鲜的通过证据。
