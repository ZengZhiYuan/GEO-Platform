# AGENTS.md

## MVP V2 后端开发任务

后端 MVP 任务书：`docs/AI应用监测_MVP_Cursor实施任务V2.md`。用户下达 Task 开发指令时，**默认授权按任务书执行**，无需每次重复「先读任务文档」。

**节约 token 的读法：**

1. 先读 `docs/AI应用监测_MVP_V2_Task索引.md`（执行规则摘要 + Task 行号目录）。
2. 再按索引行号局部读取任务书对应 Task 章节；禁止通读全文。
3. 细则见 `.cursor/rules/mvp-v2-backend-tasks.mdc`。

**用户推荐指令格式：** `执行 V2 Task N：<简述>`

## Superpowers 开发技能（代码任务必用）

凡涉及**代码开发**的任务，Agent 必须启用 [Superpowers](https://github.com/obra/superpowers) 插件 skills，细则见 `.cursor/rules/superpowers-dev-workflow.mdc`。

**最低要求（每次开发任务）：**

1. **`using-superpowers`** — 会话开始或接到开发任务后，先 Read 该 skill，再决定后续 skills。
2. **`test-driven-development`** — 写/改实现前，先写失败测试（与任务书「测试先行」一致）。
3. **`verification-before-completion`** — 声称完成前，必须运行验收命令并用输出证明通过。

**常见扩展：**

| 场景 | Skill |
|------|-------|
| 新功能 / 行为变更 | `brainstorming` |
| 多步骤实施 | `writing-plans` → `executing-plans` |
| bug / 测试失败 | `systematic-debugging` |
| 并行独立子任务 | `dispatching-parallel-agents` |
| 大步骤完成 / 合并前 | `requesting-code-review` |
| 分支收尾 | `finishing-a-development-branch` |

优先级：用户当次指令 > 本文件 / `CLAUDE.md` / V2 任务书 > Superpowers skills。

## 文本编码规则（UTF-8 默认）

**原则：** 本仓库文档、源码、配置与命令输出一律以 **UTF-8** 为默认编码。Agent 读取文档或查看运行日志时，必须显式按 UTF-8 处理，避免在中文 Windows 下出现乱码（如 `����`、`��ǡ` 等）。

### 读取文档与源码

- **优先** 使用 Cursor `Read` 工具读取 Markdown / 源码（工具侧按 UTF-8 解码）。
- 在 Shell 中读取文本时：
  - `Get-Content -Encoding UTF8 <path>`
  - 或 `[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)`
- **禁止** 使用未指定编码的 `type`、`cat`、`Get-Content`（会落到系统 ANSI/GBK）。
- Python 读写文件必须 `encoding="utf-8"`；写入 Markdown / 配置 / 日志文件时同样使用 UTF-8。

### 查看命令输出与运行日志

在 **Windows PowerShell** 中执行可能输出中文的命令（pytest、git、alembic、应用日志等）前，先设置终端与 Python 为 UTF-8：

```powershell
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
```

- 读取已有日志文件：`Get-Content -Encoding UTF8 -Path <log-file>`
- 将命令输出落盘后再读：`... 2>&1 | Out-File -Encoding utf8 .\_run.log`（禁止 `-Encoding default` / `unicode` 以外的系统默认编码）
- **禁止** 依赖 PowerShell 默认代码页解读中文输出；若仍见乱码，改用 `Read` 工具直接读日志文件，或用 Python `-X utf8` / 上述环境变量重跑命令。

### Git 与其他 CLI

- Git 日志/差异含中文时，在同一 UTF-8 终端会话中执行，或配合 `git -c core.quotepath=false` 查看路径。
- 避免在旧版 PowerShell 中使用 `&&` 链接命令（语法错误消息本身也可能乱码）；改用 `;` 分步执行，或设置 `working_directory` 后单条命令运行。

### 写入与提交

- 新建或修改的中文 Markdown、`.env.example`、注释与测试夹具一律保存为 **UTF-8（无 BOM 优先）**。
- 发现乱码时，先检查是否用了错误编码读取/输出，**不要** 将乱码文本写回仓库。

## Python / 后端虚拟环境

- 本项目后端唯一指定虚拟环境为 `backend/.venv`。
- Codex 执行任何后端 Python、pytest、alembic、uvicorn、dramatiq、pip 相关命令前，必须使用该虚拟环境，不要使用系统 Python、其他项目虚拟环境或 Conda 环境。
- 在 Windows / PowerShell 中优先使用显式解释器路径，例如：
  - `backend\.venv\Scripts\python.exe -m pytest -v backend/tests`
  - `backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt`
  - `backend\.venv\Scripts\alembic.exe -c backend\alembic.ini heads`
- 如果命令需要在 `backend/` 目录下执行，则先切换工作目录到 `backend`，再使用：
  - `.venv\Scripts\python.exe -m pytest -v`
  - `.venv\Scripts\alembic.exe heads`
  - `.venv\Scripts\alembic.exe upgrade head --sql`
- 不要写成裸 `python`、`pip`、`pytest`、`alembic`，除非已经明确激活了 `backend/.venv` 且当前 shell 可验证 `python` 来自该目录。

## CodeGraph

本项目已配置 CodeGraph MCP（`codegraph_*` 工具）。CodeGraph 是基于 tree-sitter 的符号/调用关系图谱，适合结构查询。

### 何时优先用 CodeGraph

- 架构或「X 如何工作」：先 `codegraph_context`，至多一次 `codegraph_explore`
- 特定调用链：用 `codegraph_trace`，不要用 grep 拼路径
- 按符号名查找：用 `codegraph_search`，不要先 grep
- 不要对多个符号循环 `codegraph_node`；用 `codegraph_explore`

### MVP 任务收尾：更新项目地图与索引

每个 V2 开发 Task **通过验收后**，若改动了源码，在**仓库根目录**执行：

```powershell
codegraph status
codegraph sync
codegraph status
```

- 无 `.codegraph/` 或 `status` 提示未初始化：先 `codegraph init`，再 `codegraph sync`
- 日常收尾用 `sync`（增量）；仅在 `sync` 失败且索引明显异常时用 `codegraph index --force`
- 锁文件阻塞时可 `codegraph unlock` 后重试
- 索引失败不推翻已通过测试，但须在 Task 汇报中说明
- Task 0 且无代码改动可跳过

查询前若刚改过代码，应先 `sync`，再调用 MCP 工具（或 CLI：`codegraph query`、`codegraph explore`）。

