# AI 应用监测 MVP V2 任务索引

> **用途：** 供 Agent 快速定位任务书章节，避免通读 `AI应用监测_MVP_Cursor实施任务V2.md` 全文。  
> **任务书路径：** `docs/AI应用监测_MVP_Cursor实施任务V2.md`

## 执行规则摘要（§1，行 15–88）

- **范围：** 仅 `backend` MVP；暂不开发/验收 `frontend`。
- **环境：** PostgreSQL、Redis、Nacos 用本地 `.env` 连接服务器；单元测试以 mock/fake 为主。
- **标记：** `[S]` 串行 · `[P]` 可并行 · `[B]` 阻塞 · `[M]` 主 Agent 独占 · `[H]` 需用户操作。
- **迁移：** Task 2、9、14 在同一集成分支顺序创建；禁止并行 worktree 各自写 Alembic revision。
- **公共文件：** 迁移链、`backend/app/core/config.py`、`.env.example`、依赖清单等由主 Agent 维护。
- **密钥：** 不读取/打印/提交 `.env` 真实值。
- **默认验证：**
  ```powershell
  backend/.venv/Scripts/python.exe -m pytest backend/tests -q
  backend/.venv/Scripts/alembic.exe -c backend/alembic.ini heads
  backend/.venv/Scripts/alembic.exe -c backend/alembic.ini upgrade head --sql
  ```
- **CodeGraph（任务收尾，有代码改动时）：**
  ```powershell
  codegraph status
  codegraph sync
  codegraph status
  ```
  未初始化时先 `codegraph init`。详见 `AGENTS.md` CodeGraph 节。

## 依赖链

```text
Task 0 → 1 → 2 → 3 → 4 → 5 → 6A–6E → 7 → 8
  → 9 → 10 → 11 → 12 → 13 → 14 → 15/16 → 17 → 18
```

## 任务目录

| Task | 标题 | 行号（约） | 备注 |
|------|------|-----------|------|
| 0 | 确认 V2 范围与执行基线 | 90–142 | 无代码改动 |
| 1 | 服务器 PostgreSQL/Redis/Nacos 本地运行契约 | 143–195 | `[M][H]` |
| 2 | 数据库采集迁移 | 196–251 | `[M]` 迁移 |
| 3 | 采集模型、Schema 与仓储契约 | 252–316 | `[M]` |
| 4 | 后端依赖、环境变量与 Nacos 契约 | 317–432 | `[M][H]` |
| 5 | 平台适配器与密钥池基础设施 | 433–498 | |
| 6A–6E | 五个官方平台适配器 | 499–638 | `[P][H]` 可并行 |
| 7 | 采集 Worker Actor | 639–693 | |
| 8 | 运行聚合、重试、取消与采集 API | 694–752 | |
| 9 | 分析域迁移 | 753–811 | `[M]` 迁移 |
| 10 | 确定性指标计算 | 812–869 | `[P]` |
| 11 | 统一 Agent LLM 客户端 | 870–922 | `[P][H]` |
| 12 | LangGraph 分析 Agent | 923–981 | |
| 13 | 分析 Actor 与结果 API | 982–1032 | |
| 14 | 调度与报告迁移 | 1033–1083 | `[M]` 迁移 |
| 15 | 独立 APScheduler 进程 | 1084–1136 | `[P]` |
| 16 | 报告生成与本地存储 | 1137–1190 | `[P]` |
| 17 | 后端端到端、可观测性与安全 | 1191–1262 | `[M]` |
| 18 | 后端部署、发布与回滚 | 1263–1328 | `[M][H]` |
| — | 最终验收清单 | 1329–末 | |

## Agent 读取示例

执行 Task 7 时：

1. 读本索引（本文件）。
2. 读任务书 `offset=639, limit=55`（Task 7 章节）。
3. 若涉及迁移/公共文件冲突，再读 `offset=15, limit=74`（§1 执行规则）。

## 相关权威文档

| 文档 | 何时读取 |
|------|----------|
| `CLAUDE.md` | 工程边界、验证命令、禁止事项 |
| `AI应用监测_技术开发文档.md` | 架构/领域口径争议时 |
| `docs/superpowers/specs/`、`plans/` | 当前阶段已批准设计与计划 |
