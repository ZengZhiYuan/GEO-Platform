# TASK-0305 写作任务后端接口

- 分支：feat/be-writing-task
- 范围：仅改动 backend/（+ 本进度分片）；未触碰 frontend/；未接 MQ、未接 AI、未生成真实内容；未改动其他模块及既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `backend/app/models/writing_task.py`：`WritingTask`（表 `writing_task`），字段 `task_name`(String255,非空) / `content_category_id`(BigInteger,非空,索引) / `distill_keywords`(String255,非空) / `image_category_id`(BigInteger,可空) / `article_image_count`(Integer,默认0) / `brand_knowledge_id`(BigInteger,可空) / `content_rule_id`(BigInteger,非空) / `title_rule_id`(BigInteger,可空) / `article_result_status`(String64,默认 generating) / `ai_generate_count`(Integer,默认1) / `task_status`(String64,默认 pending)，公共字段继承 BaseModel；只读一对多导航 `articles`（viewonly，foreign() 注解，无 DB 外键）
- 新增 `backend/app/models/article.py`：`Article`（表 `article`），字段 `writing_task_id`(BigInteger,非空,索引) / `article_title`(String500,可空) / `cover_image_url`(Text,可空) / `status`(String64,默认 generating) / `content`(Text,可空) / `error_message`(Text,可空)，公共字段继承 BaseModel；只读多对一导航 `writing_task`（viewonly）
- 新增 `backend/app/schemas/writing_task.py`：`TaskStatus` StrEnum（draft/pending/running/completed/failed/cancelled）、`ArticleResultStatus` StrEnum（not_generated/generating/all_success/partial_success/failed）、`WritingTaskCreate`（task_name+distill_keywords field_validator strip 后非空；各 *_id ge=1；article_image_count 0..100；ai_generate_count 1..100；article_result_status/task_status 不入请求体）、`WritingTaskOut`（from_attributes，字段严格对齐契约 14 字段）
- 新增 `backend/app/schemas/article.py`：`ArticleStatus` StrEnum（generating/pending_review/normal/disabled/failed）、`ArticleOut`（基础输出 Schema，字段对齐契约 id/writing_task_id/article_title/cover_image_url/status/content/error_message/created_at/updated_at）。文章编辑/状态切换请求 Schema 留待 TASK-0307
- 新增 `backend/app/services/writing_task.py`：同步 SQLAlchemy 2.0
  - `create_writing_task`：service 层校验引用存在（content_category 必填、content_rule 必填、title_rule/image_category 可选；brand_knowledge 模块未实现暂不校验）→ 创建大任务（task_status=pending、article_result_status=generating）→ `db.flush()` 取 id → 同一事务内按 `ai_generate_count` 创建对应数量 `Article`（status=generating）→ commit。暂不投递 MQ
  - `get_writing_task` / `list_writing_tasks`（分页 + task_name ilike 模糊 + task_status 精确筛选，过滤 is_deleted，按 id desc）
  - `cancel_writing_task`：终态(completed/failed/cancelled)不可取消（否则抛 code=40010）；大任务置 cancelled，仍 generating 的小任务置 failed 并写 error_message="任务已取消"
  - `retry_writing_task`（占位）：failed 小任务回 generating 并清空 error_message，大任务回 pending、article_result_status 回 generating；MQ 投递待 TASK-0401/0402 补充
  - 记录不存在统一抛 `BusinessException(code=40400)`
- 新增 `backend/app/api/endpoints/writing_task.py`：`router(prefix="/writing-tasks", tags=["写作任务"])`，5 接口统一响应：GET `` 列表 / POST `` 创建 / GET `/{task_id}` 详情 / POST `/{task_id}/cancel` / POST `/{task_id}/retry`
- 新增迁移 `backend/alembic/versions/20260604_1700-f6a7b8c9d0e1_add_writing_task.py`：一次建 writing_task + article 两表，down_revision=e5f6a7b8c9d0(content_category)，含 `ix_writing_task_content_category_id`、`ix_article_writing_task_id` 索引
- 修改 `backend/app/models/__init__.py`：导入导出 `Article` / `WritingTask`
- 修改 `backend/app/api/router.py`：import 并 `include_router(writing_task.router)`

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）「写作任务」「文章清单」：
  - 写作任务路径 `GET/POST /api/writing-tasks`、`GET /api/writing-tasks/{task_id}`、`POST /api/writing-tasks/{task_id}/cancel`、`POST /api/writing-tasks/{task_id}/retry`（API_PREFIX=/api，无 DELETE）
  - 写作任务字段 `id/task_name/content_category_id/distill_keywords/image_category_id/article_image_count/brand_knowledge_id/content_rule_id/title_rule_id/article_result_status/ai_generate_count/task_status/created_at/updated_at`；`task_status` 枚举严格用契约 draft/pending/running/completed/failed/cancelled
  - 文章字段 `id/writing_task_id/article_title/cover_image_url/status/content/error_message/created_at/updated_at`；`status` 枚举严格用契约 generating/pending_review/normal/disabled/failed
- 与 dev 文档（claude-code-dev.md）差异取舍（一律以契约为准）：
  - 采用契约字段名 `content_category_id`/`distill_keywords`/`image_category_id`/`content_rule_id`，**非** dev 文档 `category_id`/`distilled_keyword`/`image_gallery_id`/`article_rule_id`
  - 文章正文采用契约单字段 `content`，**未**引入 dev 文档 `content_html/content_text/content_json`；表名用 `article`（非 dev 文档 `article_item`）
  - 未引入 dev 文档大任务进度统计列（total/pending/running/success/failed_count）——契约未列出，避免与契约发散；进度聚合留待 MQ 阶段（TASK-0403）按需补列
  - **小任务初始状态取 generating**（契约 article status 无 pending 态；任务要求允许 generating/pending）
  - **大任务初始状态取 pending**（暂未接 MQ；任务要求允许 pending/running）
  - 取消时小任务置 failed + error_message="任务已取消"：契约 article status 无独立 cancelled 态，failed 为可重试终态，避免小任务永久停留 generating
- 沿用代码库「无 DB 外键」约定：各 *_id 仅建索引，引用完整性在 service 层校验；ORM 一对多用 `relationship(viewonly=True, foreign())` 只读导航

## 实测

本 worktree 新建 `backend/.venv`（Python 3.14.5），`pip install -r requirements.txt` 成功。
- 导入检查：`import app.main` + 模型/Schema OK；`WritingTask.__tablename__='writing_task'`（cols 含全部契约字段）、`Article.__tablename__='article'`；relationship `WritingTask.articles -> Article`、`Article.writing_task -> WritingTask` 解析正确；4 条 writing-tasks 路由（5 接口）全部挂在 `/api/writing-tasks`
- `alembic history/heads`：`<base> -> baseline -> keyword -> title_inspiration -> image_library -> writing_rule -> content_category -> f6a7b8c9d0e1(head)` 单一线性头
- `alembic upgrade e5f6a7b8c9d0:f6a7b8c9d0e1 --sql`：离线生成正确 DDL（writing_task：task_name VARCHAR(255) NOT NULL、distill_keywords VARCHAR(255) NOT NULL、content_rule_id BIGINT NOT NULL、article_result_status VARCHAR(64) DEFAULT 'generating' NOT NULL、task_status VARCHAR(64) DEFAULT 'pending' NOT NULL + 索引；article：writing_task_id BIGINT NOT NULL、cover_image_url TEXT、status VARCHAR(64) DEFAULT 'generating' NOT NULL、content TEXT、error_message TEXT + 索引）
- 业务功能测试（SQLite 内存，测试进程内将 BigInteger 编译为 INTEGER 适配 sqlite 自增；提交代码未改）：
  - 创建大任务（ai_generate_count=5）→ task_status=pending / article_result_status=generating / task_name·distill_keywords 已 strip / **自动生成 5 个 article（status 全为 generating）**；relationship `task.articles` 计数=5、`article.writing_task.id` 回指正确
  - 引用校验：不存在的 content_category_id / content_rule_id 均抛 40400
  - 详情查询命中；列表 total=1；按 task_name 模糊命中=1、按 task_status='completed' 命中=0
  - 取消：task_status→cancelled，generating 小任务→failed 且 error_message='任务已取消'；已取消再取消抛 40010
  - 重试占位：failed 小任务→generating 且 error_message 清空，大任务→pending、article_result_status→generating
  - 详情不存在→40400
  - Schema 校验：空/纯空白 task_name、空 distill_keywords、content_category_id=0、ai_generate_count=0、ai_generate_count=101 均被 ValidationError 拒绝
  - 结论：全部通过（ALL OK）
- `app.openapi()`：components.schemas 含 `WritingTaskCreate`，paths 含 4 条 writing-tasks 路径（端点返回 dict 未声明 response_model，Out Schema 不注册为响应组件，与既有各模块一致）

## 备注 / 遗留

- 未接 MQ：`create` 仅落库不投递消息；`retry` 为占位仅做状态流转，二者的消息投递在 TASK-0401/0402 补充
- 未接真实 AI / 未生成真实内容：小任务建后停留 generating，正文/标题/封面由后续 Worker 生成
- brand_knowledge 模块尚未实现，`brand_knowledge_id` 暂不校验存在性，待该模块落地后在 `_validate_refs` 补校验
- 大任务进度统计列与 `content_category.article_count` 计数维护未在本任务落地（契约未列进度列），留待 MQ/聚合阶段（TASK-0403）
- 引入真实 PostgreSQL（TASK-0102）后需回归验证 `alembic upgrade head`（在线）与真实库读写
- 下一步建议：**TASK-0306（写作任务前端页面）**——列表页 + 创建页，按契约字段封装即可联调
