# TASK-0303 内容分类后端接口

- 分支：feat/be-content-category
- 范围：仅改动 backend/（+ 本进度分片）；未触碰 frontend/；未接 MQ、未接 AI；未改动其他模块及既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `backend/app/models/content_category.py`：`ContentCategory`（表 `content_category`），字段 `group_name`(String255,非空) / `article_count`(Integer,server_default 0,非空)，公共字段继承 BaseModel
- 新增 `backend/app/schemas/content_category.py`：`ContentCategoryCreate`（group_name field_validator strip 后非空，max_length=255）/ `ContentCategoryUpdate`（字段可选，exclude_unset 局部更新）/ `ContentCategoryOut`（from_attributes，字段严格对齐契约：id/group_name/article_count/created_at/updated_at）。`article_count` 为只读统计字段，不进入 Create/Update
- 新增 `backend/app/services/content_category.py`：同步 SQLAlchemy 2.0 CRUD —— `list_content_categories`（分页 + `group_name` ilike 模糊搜索 + 过滤 is_deleted=False，按 id desc）、`get_content_category`、`create_content_category`、`update_content_category`、`delete_content_category`（软删除：is_deleted=True + deleted_at）；记录不存在抛 `BusinessException(message="内容分类不存在", code=40400)`
- 新增 `backend/app/api/endpoints/content_category.py`：`router(prefix="/content-categories", tags=["内容分类"])`，5 个接口全部统一响应（success/paginate），列表用 Query 接收 page/page_size/group_name
- 新增迁移 `backend/alembic/versions/20260604_1600-e5f6a7b8c9d0_add_content_category.py`：手写 create_table，down_revision=d4e5f6a7b8c9(writing_rule)，含 `ix_content_category_group_name` 索引
- 修改 `backend/app/models/__init__.py`：导入并导出 `ContentCategory`，供 Alembic 收集元数据
- 修改 `backend/app/api/router.py`：import 并 `include_router(content_category.router)`

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）「内容分类」：
  - 路径 `GET/POST /api/content-categories`、`GET/PUT/DELETE /api/content-categories/{category_id}`（API_PREFIX=/api）
  - 字段 `id / group_name / article_count / created_at / updated_at`
- `article_count` 定位为系统维护的只读统计字段（与关键词库 `question_count`、图库 `image_count` 一致），仅响应返回、不接受写入；后续由写作任务/文章模块维护。沿用代码库无 DB 外键约定。

## 实测

本 worktree 新建 `backend/.venv`（Python 3.14.5），`pip install -r requirements.txt` 成功。
- 导入检查：`import app.main` + 模型/Schema OK；`ContentCategory.__tablename__='content_category'`，columns 含 group_name/article_count；5 条 content-categories 路由全部挂在 `/api/content-categories`
- `alembic history/heads`：`<base> -> baseline -> keyword -> title_inspiration -> image_library -> writing_rule -> e5f6a7b8c9d0(head)` 单一线性头
- `alembic upgrade d4e5f6a7b8c9:e5f6a7b8c9d0 --sql`：离线生成正确 DDL（group_name VARCHAR(255) NOT NULL、article_count INTEGER DEFAULT '0' NOT NULL + `ix_content_category_group_name` 索引）
- 业务功能测试（SQLite 内存，测试进程内将 BigInteger 编译为 INTEGER 适配 sqlite 自增；提交代码未改）：create×3 / group_name strip / article_count 默认 0 / 列表降序 / total / group_name 模糊搜索（命中 2）/ 分页 / 详情 / 局部更新 / 软删除后查 404(code=40400) / 删后列表 total 减少 / 更新不存在 404 / 空与纯空白 group_name 被 ValidationError 拒绝 —— 全部通过
- `app.openapi()`：components.schemas 含 ContentCategoryCreate/ContentCategoryUpdate，paths 含 `/api/content-categories` 与 `/api/content-categories/{category_id}`（Swagger 可测试）

## 备注 / 遗留

- 引入真实 PostgreSQL（TASK-0102）后需回归验证 `alembic upgrade head`（在线）与真实库读写。
- `article_count` 计数维护逻辑将在写作任务/文章模块（TASK-0305/0307）落地，本任务仅暴露只读字段。
- 下一步建议：TASK-0304（内容分类前端页面），路由 `/workspace/content-categories`，按契约字段 group_name / article_count 封装即可联调。
