# TASK-0307 文章清单后端接口

- 分支：feat/be-article
- 范围：仅改动 backend/（新增 article 模块）；未触碰 frontend/；未接 MQ、未接真实 AI；未改动其他模块及既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `backend/app/models/article.py`：`Article`（表 `article`），字段严格对齐契约：`writing_task_id`(BigInteger,非空,索引) / `article_title`(String500,可空) / `cover_image_url`(Text,可空) / `status`(String32,默认 `generating`) / `content`(Text,可空，富文本 HTML 或 JSON 字符串) / `error_message`(Text,可空)，公共字段继承 BaseModel。沿用代码库**无 DB 外键**约定：`writing_task_id` 仅建索引（`ix_article_writing_task_id`），引用完整性留待写作任务/Worker 模块在 service 层校验。
- 新增 `backend/app/schemas/article.py`：
  - `ArticleStatus` StrEnum（5 态：generating/pending_review/normal/disabled/failed，用于列表筛选与输出说明）
  - `ArticleSwitchStatus` StrEnum（4 态：pending_review/normal/disabled/failed，**状态切换接口仅允许人工目标态**，排除系统态 generating）
  - `ArticleUpdate`（编辑请求体，仅 `article_title`/`cover_image_url`/`content` 可选，局部更新；article_title 经 field_validator strip 后非空校验）
  - `ArticleStatusUpdate`（状态切换请求体，status 限定 `ArticleSwitchStatus`）
  - `ArticleOut`（from_attributes，字段严格对齐契约：id/writing_task_id/article_title/cover_image_url/status/content/error_message/created_at/updated_at）
- 新增 `backend/app/services/article.py`：同步 SQLAlchemy 2.0 CRUD —— `list_articles`（分页 + `writing_task_id` 精确筛选 + `status` 精确筛选 + `article_title` ilike 模糊搜索，全部过滤 is_deleted=False，按 id desc）、`get_article`、`update_article`（局部更新标题/封面/正文，用 `in data` 判定以支持显式置空封面/正文）、`update_article_status`（切换状态）；记录不存在抛 `BusinessException(code=40400)`。**不提供新增/删除接口**（文章由写作任务/Worker 生成，契约亦无 POST/DELETE /api/articles）。
- 新增 `backend/app/api/endpoints/article.py`：`router(prefix="/articles")`，4 个接口全部统一响应。
- 新增迁移 `backend/alembic/versions/20260604_1700-f6a7b8c9d0e1_add_article.py`：手写 create_table，down_revision=e5f6a7b8c9d0(content_category)，含 `ix_article_writing_task_id` 索引。
- 修改 `backend/app/models/__init__.py`：导入导出 `Article`。
- 修改 `backend/app/api/router.py`：include `article.router`。

## 接口（API_PREFIX=/api）

- `GET  /api/articles`（Query：page/page_size/writing_task_id/status/article_title）分页列表
- `GET  /api/articles/{article_id}` 详情
- `PUT  /api/articles/{article_id}` 编辑标题/封面图/正文
- `POST /api/articles/{article_id}/status` 切换状态（pending_review/normal/disabled/failed）

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）文章清单段：单 `content` 字段（非 dev 文档的 content_html/content_json/content_text 拆分），`status` 单字段（非 dev 文档 review_status/generate_status 拆分），FK 字段名 `writing_task_id`（非 dev 文档 `task_id`）。
- 与 dev 文档（8.11 article_item）冲突处一律以契约为准：未引入 category_id/generation_index/retry_count/content_text 等草案字段。
- status 切换接口按本任务目标（pending_review/normal/disabled/failed 四态）限制目标态；generating 为系统生成中态，不可人工切换（请求会被 422 拒绝）。
- TASK-0305（writing_task + article 建模）尚未实施，本任务按无外键约定独立建 article 表，writing_task_id 仅索引，不阻塞后续 writing_task 接入。

## 实测

本 worktree 新建 `backend/.venv`（Python 3.14）：
- `python -m venv .venv` + `pip install -r requirements.txt` 成功；测试用临时安装 `httpx`（未写入 requirements.txt）。
- 导入检查：`import app.main` + Article/schemas/service OK；表名 `article`，列含 writing_task_id/article_title/cover_image_url/status/content/error_message，索引 `ix_article_writing_task_id`；4 条 article 路由正确挂载。
- `alembic history/heads`：`<base> -> baseline -> keyword -> title_inspiration -> image_library -> writing_rule -> content_category -> f6a7b8c9d0e1(head)` 单一线性头；`alembic upgrade e5f6a7b8c9d0:f6a7b8c9d0e1 --sql` 离线生成正确 DDL（writing_task_id BIGINT NOT NULL、article_title VARCHAR(500)、cover_image_url TEXT、status VARCHAR(32) DEFAULT 'generating' NOT NULL、content TEXT、error_message TEXT + 索引）。
- 业务功能测试（SQLite 内存，测试进程内将 BigInteger 编译为 INTEGER 适配自增；提交代码未改）：默认 status=generating / 列表降序+total / writing_task_id 筛选 / status 筛选 / article_title 模糊搜索 / 详情 / 编辑（标题+封面+正文，status 保留）/ 仅改 content 保留标题 / 4 态切换 / 软删除后列表过滤 / 详情·更新·切换不存在均 404(code=40400) / 空标题被 ValidationError 拒绝 / generating 作为切换目标被 ValidationError 拒绝 —— 全部通过。
- HTTP 层测试（FastAPI TestClient + StaticPool 共享 sqlite）：LIST 200 分页结构正确，item 含全部 9 个契约字段；DETAIL 200；PUT 200（cover+content 生效）；STATUS 200（normal 生效）；STATUS 传 generating → code=422；详情 99999 → code=40400；`GET /api/health` code=0；`app.openapi()` 含 3 条 article 路径与 ArticleUpdate/ArticleStatusUpdate/ArticleStatus/ArticleSwitchStatus schema（Swagger 可测试）。

## 备注 / 遗留

- 引入真实 PostgreSQL（TASK-0102）后需回归 `alembic upgrade head`（在线）与真实库读写。
- 文章的生成与新增由 TASK-0305（写作任务）/ Phase 4（MQ Worker）负责写入，本任务仅提供清单查询/编辑/状态切换；`writing_task_id` 引用完整性待 writing_task 模块就绪后在 service 层补校验。
- 测试用 `httpx` 为临时安装，未加入 requirements.txt（如需将 TestClient 纳入正式测试可后续单独评估 dev 依赖）。
