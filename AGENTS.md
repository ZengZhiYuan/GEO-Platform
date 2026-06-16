# AGENTS.md

## Windows / PowerShell 编码规则

本机项目中大量文档为中文 Markdown，统一按 UTF-8 处理。

在 Windows PowerShell / PowerShell 中读取中文文本、Markdown、需求文档时：

- 优先使用 `Get-Content -Encoding UTF8`
- 或使用 `[System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)`
- 不要使用未显式指定编码的 `type`、`cat`、`Get-Content` 读取中文文档
- 如果使用 Python 读取文件，必须显式指定 `encoding="utf-8"`

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

This project has a CodeGraph MCP server (`codegraph_*` tools) configured. CodeGraph is a tree-sitter-parsed knowledge graph of every symbol, edge, and file. Reads are sub-millisecond and return structural information grep cannot.

### When to prefer codegraph over native search

Use codegraph for structural questions: what calls what, what would break, where a symbol is defined, or what a signature/source is. Use native grep/read only for literal text queries or after a specific file is already identified.

### Rules of thumb

- For architecture or "how does X work" questions, call `codegraph_context` first, then at most one focused `codegraph_explore`.
- For a specific flow, use `codegraph_trace` rather than rebuilding the path with grep.
- Do not grep first when looking up a symbol by name; use `codegraph_search`.
- Do not loop `codegraph_node` over many symbols; use `codegraph_explore`.
- After editing files, allow for CodeGraph index debounce before re-querying.

