# CLAUDE.md

## 项目定位

本项目是 AI 应用监测平台，用于配置监测项目和 Prompt，采集多个 AI 平台回答，计算确定性指标，并通过 Agent 生成语义分析和改进建议。

## 权威文档

1. `AI应用监测_技术开发文档.md`
2. 当前阶段 `docs/superpowers/specs/` 下已批准的设计
3. 当前阶段 `docs/superpowers/plans/` 下的实施计划

## MVP V2 任务书（后端）

- 完整任务书：`docs/AI应用监测_MVP_Cursor实施任务V2.md`
- **Agent 入口索引：** `docs/AI应用监测_MVP_V2_Task索引.md`（先读索引，再按行号读单个 Task 章节；禁止通读任务书全文）

## 当前阶段边界

- 已实现配置域和只落库的运行骨架。
- 未实现真实采集、Agent 分析、指标快照、调度和报告。
- 禁止恢复已移除的内容生产业务域。

## 技术栈

- 后端：Python、FastAPI、Pydantic、SQLAlchemy、Alembic、PostgreSQL、Redis、Dramatiq。
- 前端：React、TypeScript、Vite、Ant Design、React Router、Axios。

## 后端虚拟环境

- 后端唯一指定虚拟环境为 `backend/.venv`。
- 执行任何后端 Python、pytest、alembic、uvicorn、dramatiq、pip 相关命令前，必须使用该虚拟环境。
- Windows / PowerShell 中优先使用显式路径，例如 `backend\.venv\Scripts\python.exe -m pytest -v backend/tests`。
- 如已切换到 `backend/` 目录，则使用 `.venv\Scripts\python.exe -m pytest -v`、`.venv\Scripts\alembic.exe heads`。
- 不要使用系统 Python、其他项目虚拟环境、Conda 环境，或裸 `python` / `pip` / `pytest` / `alembic` 命令，除非已确认它们来自 `backend/.venv`。

## 后端边界

- 通用基础设施位于 `backend/app/core/`、`backend/app/models/base.py` 和 `backend/app/workers/`。
- 监测业务位于 `backend/app/geo_monitoring/`。
- 对外接口统一使用 `/api/geo-monitoring`。

## 当前领域模型

- `MonitorProject`：监测项目。
- `Brand`、`BrandAlias`：目标品牌、竞品和别名。
- `PromptSet`、`Prompt`：版本化问题集。
- `AIPlatform`：AI 平台配置。
- `MonitorRun`、`QueryTask`：监测运行和查询子任务。

## 核心工程规则

- 采集、分析、报告分阶段解耦。
- 外部 API 和 LLM 调用不得运行在数据库长事务内。
- 数值指标必须由 SQL/Python 确定性计算；LLM 不得修改数值结果。
- 平台失败相互隔离，未来运行允许 `partial_success`。
- 趋势比较必须限定同一 Prompt 集版本。
- 所有新增表结构必须有 Alembic 迁移。
- 所有行为变更必须先写失败测试，再实现并验证。
- **文本编码：** 文档、日志与命令输出默认 UTF-8；读取中文 Markdown、查看 pytest/git 输出前在 PowerShell 中设置 UTF-8 终端（见 `AGENTS.md`「文本编码规则」），禁止用系统默认编码读文件或解读日志。

## 验证要求

- 后端：`backend\.venv\Scripts\python.exe -m pytest -v backend/tests`
- 迁移：`backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads`、`backend\.venv\Scripts\alembic.exe -c backend\alembic.ini upgrade head --sql`
- 前端：`npm test`、`npm run build`

## 统一响应

普通接口返回 `{ "code": 0, "message": "success", "data": {} }`。分页接口的 `data` 包含 `items`、`total`、`page`、`page_size`。

## 数据与状态规则

- 所有业务表继承公共主键、时间、软删除、租户和操作人字段。
- 项目状态：`active | disabled | archived`。
- 品牌类型：`target | competitor | candidate`，每个项目最多一个有效目标品牌。
- Prompt 集状态：`draft | active | archived`，每个项目最多一个 active 版本。
- 运行状态预留：`pending | collecting | analyzing | reporting | completed | partial_success | failed | cancelled`。
- 查询任务状态预留：`pending | queued | running | success | failed | cancelled`。

## 文本编码（UTF-8）

- 仓库内中文文档、配置示例与 Agent 可读日志 **默认 UTF-8**。
- Agent 通过 Shell 查看输出或读文件时，遵循 `AGENTS.md` 中的「文本编码规则（UTF-8 默认）」：显式 `-Encoding UTF8` / `PYTHONIOENCODING=utf-8` / `chcp 65001`，避免中文 Windows 下乱码。

## 开发流程

1. 若执行 MVP V2 Task：先读 `docs/AI应用监测_MVP_V2_Task索引.md`，再局部读取任务书对应该 Task 的章节；否则阅读本文件、业务技术文档、当前批准的 spec 和 plan。
2. **代码开发任务：** 按 `.cursor/rules/superpowers-dev-workflow.mdc` 启用 Superpowers skills（至少 `using-superpowers`、`test-driven-development`、`verification-before-completion`）。
3. 检查现有代码与迁移，明确单次任务边界。
4. 先写失败测试并确认失败原因正确。
5. 实现最小行为，运行相关测试。
6. 运行完整后端测试、迁移验证和前端构建。
7. 若 Task 改动了源码：在仓库根目录执行 `codegraph sync` 更新项目地图（见 `AGENTS.md`）。
8. 说明修改文件、验证命令、CodeGraph 同步结果和剩余限制。

## 禁止事项

- 禁止恢复已移除的内容生产业务域。
- 禁止在数据库事务中调用外部 AI 平台或 LLM。
- 禁止让 LLM 生成或修改确定性统计指标。
- 禁止提交没有测试、没有迁移或无法验证的业务变更。
- 禁止在日志、数据库普通配置字段或仓库中保存明文平台密钥。
