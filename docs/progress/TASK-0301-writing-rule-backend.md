# TASK-0301 写作规范后端接口

- 分支：feat/be-writing-rule
- 范围：仅改动 backend/；未触碰 frontend/；未接 MQ、未接 AI；未改动其他模块及既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `backend/app/models/writing_rule.py`：`WritingRule`（表 `writing_rule`），字段 `rule_name`(String255,非空) / `creation_type`(String32,非空) / `instruction_content`(Text,非空)，公共字段继承 BaseModel
- 新增 `backend/app/schemas/writing_rule.py`：`CreationType` StrEnum（article_creation/title_creation/traffic_replication）、`WritingRuleCreate`（rule_name + instruction_content 经 field_validator strip 后非空校验，creation_type 必填）、`WritingRuleUpdate`（字段可选，exclude_unset 局部更新）、`WritingRuleOut`（from_attributes，字段严格对齐契约：id/rule_name/creation_type/instruction_content/created_at/updated_at）
- 新增 `backend/app/services/writing_rule.py`：同步 CRUD —— `list_writing_rules`（分页 + `rule_name` ilike 模糊搜索 + `creation_type` 精确筛选，过滤 is_deleted=False，按 id desc）、`get_writing_rule`、`create_writing_rule`、`update_writing_rule`、`delete_writing_rule`（软删除：is_deleted=True + deleted_at）；记录不存在抛 `BusinessException(code=40400)`
- 新增 `backend/app/api/endpoints/writing_rule.py`：`router(prefix="/writing-rules")`，5 个接口全部统一响应（success/paginate），列表用 Query 接收 page/page_size/rule_name/creation_type
- 新增迁移 `backend/alembic/versions/20260604_1500-d4e5f6a7b8c9_add_writing_rule.py`：手写 create_table，down_revision=c3d4e5f6a7b8(image_library)，含 `ix_writing_rule_creation_type` 索引
- 修改 `backend/app/models/__init__.py`：导入并导出 `WritingRule`，供 Alembic 收集元数据
- 修改 `backend/app/api/router.py`：`include_router(writing_rule.router)`
- 接口路径（API_PREFIX=/api）：GET/POST `/api/writing-rules`、GET/PUT/DELETE `/api/writing-rules/{rule_id}`

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）写作规范段：路径 `/api/writing-rules`，字段 id/rule_name/creation_type/instruction_content/created_at/updated_at；creation_type 枚举 article_creation/title_creation/traffic_replication 一致。
- creation_type 取值约束放在应用层（Schema StrEnum），DB 列为 VARCHAR(32) + 索引，沿用代码库无 DB 外键/无 DB 级 CHECK 约定。

## 实测

本 worktree 新建 `backend/.venv`（Python 3.14，`python -m venv` + `pip install -r requirements.txt` 成功）：

- 导入检查：`import app.main` + models/schemas/services OK；table=writing_rule，columns 含 rule_name/creation_type/instruction_content；CreationType=['article_creation','title_creation','traffic_replication']；5 条 writing-rules 路由全部挂在 `/api/writing-rules`
- `alembic history`：`<base> -> baseline -> keyword -> title_inspiration -> image_library -> d4e5f6a7b8c9(head)` 单一线性头；`alembic upgrade c3d4e5f6a7b8:d4e5f6a7b8c9 --sql` 离线生成正确 DDL（rule_name VARCHAR(255) NOT NULL、creation_type VARCHAR(32) NOT NULL、instruction_content TEXT NOT NULL + `ix_writing_rule_creation_type` 索引）
- 业务功能测试（SQLite 内存，测试进程内将 BigInteger 主键编译为 INTEGER 以适配 sqlite 自增；提交代码未改）：create×3（三种 creation_type）/列表降序/total/`rule_name` 模糊搜索/`creation_type` 精确筛选/分页/详情/局部更新（仅改 creation_type 保留 rule_name 与 instruction_content；再改 instruction_content）/软删除/删后查 404(code=40400)/更新不存在 404/空 rule_name、空 instruction_content、非法 creation_type 均被 ValidationError 拒绝 —— 全部通过（`ALL FUNCTIONAL TESTS PASSED`）
- `app.openapi()`：paths 含 `/api/writing-rules` 与 `/api/writing-rules/{rule_id}`，components.schemas 含 CreationType / WritingRuleCreate / WritingRuleUpdate（Swagger 可测试）

## 备注 / 遗留

- 引入真实 PostgreSQL（TASK-0102）后需回归验证 `alembic upgrade head`（在线）与真实库读写。
- 前端写作规范页面（TASK-0302）尚未开发，可在本接口就绪后按契约直接联调。
