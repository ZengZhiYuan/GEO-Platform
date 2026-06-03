# 实朴GEO开发进度记录

## 当前阶段

Phase 0（项目初始化）已全部完成（TASK-0001 / 0002 / 0003）。Phase 1 中 TASK-0101（后端数据库基础）已完成；剩余 TASK-0102（Docker Compose）。Phase 2 中 TASK-0201（关键词库后端接口）已完成。

## 决策记录

- 2026-06-03：接口契约以 `docs/api-contract.md` 为**唯一权威源**，`docs/claude-code-dev.md` 仅作设计参考。当字段名/路径前缀/枚举值冲突时一律以契约为准（路径用 `/api/...` 而非 `/api/v1/...`；具体冲突字段见 api-contract.md）。后端 Schema、前端 types/api 全部按契约字段拼写。
- 2026-06-03：后端 ORM 采用**同步 SQLAlchemy 2.x**（同步 Session + `get_db` 依赖），不使用异步引擎。所有 CRUD、Worker 按同步写法实现。
- 2026-06-03：异步任务 broker 采用 **Redis**（Celery broker + backend 均走 Redis），**不引入 RabbitMQ**。Phase 1 的 docker-compose 只编排 postgres + redis。

## 已完成

- 已整理 docs 开发文档
- 已创建 CLAUDE.md
- 技术栈确认：以 CLAUDE.md 为准（React + TS + Vite + Ant Design + Zustand/Redux；后端 FastAPI + Celery/Dramatiq）
- TASK-0001：已创建项目基础目录 backend/ frontend/ docker/ scripts/，新增根 .gitignore；.env.example、README.md 已就绪
- TASK-0002：已初始化后端 FastAPI 应用（app/main.py、core/config.py、core/response.py、core/exceptions.py、api/router.py、requirements.txt），健康检查接口 /api/health 已可用并实测返回统一 success 响应
- TASK-0003：已初始化前端 React（Vite + React + TS + Ant Design + React Router + Axios + Zustand 依赖），含 MainLayout 左侧菜单（素材中心 / 写作工作台共 8 个子项）、占位页与空路由、统一 axios 客户端、基础 API 类型目录 `src/types/`；实测 `npm run build` 通过、dev 服务器可正常响应
- TASK-0101：已接入数据库基础设施（同步 SQLAlchemy 2.0 + Alembic）。新增 `core/database.py`（engine / SessionLocal / Base / get_db 依赖）、`models/base.py`（通用 BaseModel：id、created_at、updated_at、deleted_at、is_deleted、tenant_id、created_by、updated_by）、`models/__init__.py`；新增 Alembic（`alembic.ini`、`alembic/env.py` 从 settings.DATABASE_URL 读取连接、`alembic/script.py.mako`、`alembic/versions/` 含 baseline 迁移）；`core/config.py` 增加 DATABASE_URL 及引擎参数；`requirements.txt` 增加 sqlalchemy/alembic/psycopg2-binary。实测：venv 安装依赖成功、应用与模型导入无误、`alembic history/heads` 正常、`alembic upgrade head --sql` 离线生成正确 PostgreSQL DDL
- TASK-0201：已实现关键词库后端接口（仅改动 backend/）。新增 `models/keyword.py`（Keyword，表 `keyword_library`，字段 main_word/question_count/optimize_status + 公共字段）、`schemas/keyword.py`（OptimizeStatus 枚举 + KeywordCreate/Update/Out，main_word 非空校验）、`services/keyword.py`（list/get/create/update/delete，软删除 + 模糊搜索 + 状态筛选 + 分页）、`api/endpoints/keyword.py`（5 个 REST 接口，统一响应）；首条业务迁移 `alembic/versions/...add_keyword_library.py` 挂在 baseline 之后；接入 `models/__init__.py` 与 `api/router.py`。接口路径（API_PREFIX=/api）：GET/POST `/api/keywords`、GET/PUT/DELETE `/api/keywords/{id}`。实测见“最近一次变更”

## 正在进行

- Phase 2：TASK-0201 已完成。下一步可执行 TASK-0202（关键词库前端页面）或继续 TASK-0203（标题灵感后端接口）。在引入真实 PostgreSQL（TASK-0102）之前，关键词库的在线迁移与真实库读写需待容器就绪后回归验证

## 待完成

### 第一阶段：项目骨架

- [x] 创建项目基础目录骨架（backend/ frontend/ docker/ scripts/）+ .gitignore（TASK-0001）
- [x] 创建 .env.example
- [x] 创建 README.md
- [x] 创建 backend FastAPI 项目结构（TASK-0002）
- [x] 创建 frontend React + Vite 项目结构（TASK-0003）
- [ ] 创建 docker-compose.yml（TASK-0102）
- [x] 后端健康检查接口（TASK-0002）
- [x] 前端基础布局和路由（TASK-0003）

### 第二阶段：数据库基础

- [x] SQLAlchemy 基础配置（core/database.py：engine / SessionLocal / Base / get_db）
- [x] Alembic 初始化（alembic.ini + env.py + script.py.mako + versions/baseline）
- [x] PostgreSQL 连接（DATABASE_URL 配置就绪；实际连接待 TASK-0102 起容器验证）
- [x] 通用 BaseModel（models/base.py，含公共字段）
- [x] 通用分页模型（已在 TASK-0002 的 core/response.py 提供 PageData / paginate）

### 第三阶段：素材中心

- [x] 关键词库（后端接口 TASK-0201 + 前端页面 TASK-0202 均已完成）
- [ ] 标题灵感
- [ ] 画像图库
- [ ] 品牌知识库

### 第四阶段：写作工作台

- [ ] 写作规范
- [ ] 内容分类
- [ ] 写作任务
- [ ] 文章清单

### 第五阶段：异步生成

- [ ] Redis
- [ ] Celery/Dramatiq Worker
- [ ] 小任务生成
- [ ] 大任务状态聚合
- [ ] 失败重试

## 最近一次变更（TASK-0202 关键词库前端页面，仅改动 frontend/ + 本文件）

TASK-0202 完成（关键词库前端页面，路由 `/material/keywords`，左侧菜单「素材中心 / 关键词库」可访问）：
- 新增 `frontend/src/types/material.ts`：KeywordItem / KeywordListQuery / KeywordCreatePayload / KeywordUpdatePayload / OptimizeStatus，字段对齐 api-contract.md（main_word / question_count / optimize_status / created_at / updated_at）
- 新增 `frontend/src/utils/enums.ts`：OptimizeStatusOptions（未优化/优化中/已优化）、颜色映射、label 取值
- 新增 `frontend/src/utils/format.ts`：formatDateTime 时间格式化
- 新增 `frontend/src/api/keyword.ts`：listKeywords / getKeyword / createKeyword / updateKeyword / deleteKeyword（GET|POST /api/keywords、GET|PUT|DELETE /api/keywords/{id}）
- 新增 `frontend/src/pages/material/keyword/index.tsx`：列表页（页面标题、主词搜索、优化状态筛选、新增按钮、表格、分页、编辑、删除二次确认、loading、empty、错误 Alert+重试、成功/失败提示）
- 新增 `frontend/src/pages/material/keyword/KeywordFormModal.tsx`：新增/编辑弹窗（必填 + 长度校验、提交 loading、取消返回）
- 修改 `frontend/src/router/index.tsx`：`/material/keywords` 由占位页替换为 KeywordPage
- 修改 `frontend/src/types/index.ts`：导出 material 类型
- 实测：`npm install` 成功（165 包）；`npm run build`（tsc -b 类型检查 + vite 生产构建）通过；`npm run lint` 因项目未安装 eslint 依赖而不可用（lint 脚本存在但 eslint 未在 devDependencies，属既有项目状况，类型检查由 tsc 覆盖）
- 范围限制：仅改动 frontend/ 与 docs/progress.md，未触碰 backend/，未开发其他素材页面，未改动接口字段名
- 备注：后端 TASK-0201 关键词接口若尚未就绪，页面按契约封装可在接口可用后直接联调



TASK-0201 完成（关键词库后端接口，仅改动 backend/ + docs/progress.md）：
- 新增 `backend/app/models/keyword.py`：`Keyword`（`__tablename__="keyword_library"`），字段 `main_word`(String255,非空) / `question_count`(Integer,默认0,由标题灵感模块维护) / `optimize_status`(String32,默认 not_optimized)，公共字段继承 BaseModel
- 新增 `backend/app/schemas/__init__.py`、`backend/app/schemas/keyword.py`：`OptimizeStatus` StrEnum（not_optimized/optimizing/optimized）、`KeywordCreate`（main_word 经 field_validator strip 后非空校验）、`KeywordUpdate`（字段可选，exclude_unset 局部更新）、`KeywordOut`（from_attributes，字段严格对齐 api-contract：id/main_word/question_count/optimize_status/created_at/updated_at）
- 新增 `backend/app/services/__init__.py`、`backend/app/services/keyword.py`：同步 CRUD —— `list_keywords`（分页 + `main_word` ilike 模糊搜索 + `optimize_status` 精确筛选，全部过滤 is_deleted=False，按 id desc）、`get_keyword`、`create_keyword`、`update_keyword`、`delete_keyword`（软删除：is_deleted=True + deleted_at）；记录不存在抛 `BusinessException(code=40400)`
- 新增 `backend/app/api/endpoints/__init__.py`、`backend/app/api/endpoints/keyword.py`：`router(prefix="/keywords")`，5 个接口全部统一响应（success/paginate），列表用 Query 接收 page/page_size/main_word/optimize_status
- 新增迁移 `backend/alembic/versions/20260603_1400-a1b2c3d4e5f6_add_keyword_library.py`：手写 create_table（无在线 DB，autogenerate 不可用），down_revision=baseline(327ce9fdb8a5)，含 `ix_keyword_library_main_word` 索引
- 修改 `backend/app/models/__init__.py`：导入并导出 `Keyword`，供 Alembic 收集元数据
- 修改 `backend/app/api/router.py`：`include_router(keyword.router)`
- 实测命令（backend/.venv，Python 3.14）：
  - `pip install -r requirements.txt`（成功）
  - 导入检查：`import app.main / app.models / schemas / services / endpoints`（OK，table=keyword_library，5 条 keyword 路由全部挂在 /api/keywords）
  - `alembic history`：`<base> -> 327ce9fdb8a5(baseline) -> a1b2c3d4e5f6(head)` 单一线性头；`alembic upgrade head --sql` 离线生成正确 keyword_library DDL + 索引
  - 业务逻辑功能测试（SQLite 内存，测试进程内将 BigInteger 主键临时降为 Integer 以适配 SQLite 自增；提交代码未改）：create/列表降序/模糊搜索/状态筛选/分页/详情/更新（仅改状态保留 main_word）/软删除/删后查 404(code=40400)/更新不存在 404/空 main_word 被 ValidationError 拒绝 —— 全部通过
  - `uvicorn app.main:app`（127.0.0.1:8011）启动成功：`GET /api/health` → `{"code":0,"message":"success","data":{"status":"ok",...}}` HTTP 200；`/openapi.json` 含 GET/POST `/api/keywords` 与 GET/PUT/DELETE `/api/keywords/{keyword_id}`；`/docs` HTTP 200（Swagger 可测试）

TASK-0101 完成（数据库基础，仅改动 backend/ + docs + README）：
- 新增 `backend/app/core/database.py`：同步 SQLAlchemy 引擎、SessionLocal 会话工厂、声明式 Base、`get_db` FastAPI 依赖
- 新增 `backend/app/models/base.py`：抽象 BaseModel，含公共字段 id / created_at / updated_at / deleted_at / is_deleted / tenant_id / created_by / updated_by（SQLAlchemy 2.0 Mapped 风格）
- 新增 `backend/app/models/__init__.py`：导出 Base / BaseModel，供 Alembic 收集元数据
- 新增 `backend/alembic.ini`（ASCII-only，规避 Windows GBK 读取报错；script_location=alembic、prepend_sys_path=.）
- 新增 `backend/alembic/env.py`：从 settings.DATABASE_URL 读取连接，target_metadata=Base.metadata，支持离线/在线模式
- 新增 `backend/alembic/script.py.mako`、`backend/alembic/versions/`（含 baseline 空迁移 + .gitkeep）
- 修改 `backend/app/core/config.py`：新增 DATABASE_URL（默认值对齐 .env.example 的 psycopg2 串）及 DB_ECHO / DB_POOL_SIZE / DB_MAX_OVERFLOW / DB_POOL_PRE_PING
- 修改 `backend/requirements.txt`：新增 sqlalchemy>=2.0、alembic>=1.13、psycopg2-binary
- 更新 README 数据库迁移说明
- 实测命令：`python -m venv .venv` + `pip install -r requirements.txt`（成功，psycopg2-binary 2.9.12 cp314 wheel）；`python -c "import app.main, app.core.database, app.models"`（OK，engine URL 正确）；`alembic history/heads`（OK）；`alembic upgrade head --sql`（离线生成 alembic_version 建表 DDL，OK）；uvicorn 启动 + `GET /api/health` 返回 `{"code":0,"message":"success","data":{"status":"ok",...}}`，HTTP 200

> 备注：TASK-0002 在本轮开始前已由历史进度完成，本轮仅复核其健康检查接口仍可用，未重复创建文件。

TASK-0003 补充（2026-06-03）：
- 新增基础 API 类型目录 `frontend/src/types/`：`common.ts`（ApiResponse 转出 + PageParams / PageData / ListQuery，分页字段对齐 api-contract.md：items/total/page/page_size）、`index.ts`（类型统一出口）
- 不包含任何业务实体类型，业务类型在后续对应任务补充
- 未改动任何既有已提交文件；实测 `npm run build`（tsc -b 类型检查 + vite 生产构建）通过

TASK-0003 完成：
- 新增前端工程配置：package.json、tsconfig.json、tsconfig.node.json、vite.config.ts、index.html、.env.example
- 新增 src/main.tsx（挂载 RouterProvider + antd ConfigProvider 中文 locale）
- 新增 src/router/index.tsx（createBrowserRouter，素材中心 4 + 写作工作台 4 共 8 条路由，根路径重定向到 /material/keywords，通配 404）
- 新增 src/layout/MainLayout.tsx（Sider 左侧菜单 + Header + Content Outlet，菜单点击导航、选中态随路由派生）
- 新增 src/pages/PlaceholderPage.tsx、NotFoundPage.tsx（占位页与 404 页）
- 新增 src/api/client.ts（axios 实例 + 响应拦截器，按统一响应解包 data、错误 message 提示）
- 新增 src/vite-env.d.ts，移除占位 frontend/.gitkeep
- 实测：npm install 成功；npm run build（tsc 类型检查 + vite 生产构建）通过；dev 服务器 / 与 /material/keywords 均返回 200

## 下一步建议

TASK-0201（关键词库后端接口）已完成。下一步可选：
- **TASK-0202：关键词库前端页面**（列表 / 搜索 / 分页 / 新增 / 编辑 / 删除，对接本次后端接口）——补齐关键词库前后端闭环；
- 或继续 **TASK-0203：标题灵感后端接口**（与关键词库共用本次确立的 model/schema/service/router 代码风格）。

另：**TASK-0102：Docker Compose**（PostgreSQL + Redis）仍未完成。容器内 PostgreSQL 起来后，需回归验证关键词库的 `alembic upgrade head`（在线）与真实数据库读写。