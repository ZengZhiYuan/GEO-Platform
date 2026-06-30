# Manual platform connectivity scripts

These scripts are for **local manual smoke / reverse-engineering only**. They are excluded from the production Docker image via `.dockerignore`.

Do not import them from `app.*` or run them in CI. Credentials must come from environment variables or a local `.env` file — never commit tokens to the repository.

| Script | Env vars |
| --- | --- |
| `doubao_test.py` | `ARK_API_KEY` / `DOUBAO_API_KEY`, `DOUBAO_MODEL` / `ARK_MODEL` |
| `qwen_test.py` | `DASHSCOPE_API_KEY` |
| `hunyuan_test.py` | `HUNYUAN_API_KEY` (via `.env` or env) |
| `kimi_web_chat.py` | `KIMI_WEB_JWT` or `KIMI_WEB_AUTH_TOKEN` |

Historical credentials that were previously hard-coded in git are considered **compromised** — rotate Kimi web sessions before reuse.
