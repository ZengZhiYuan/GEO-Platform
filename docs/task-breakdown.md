# 实朴GEO开发任务拆解

## 任务执行原则

每次只执行一个任务编号，不允许跨阶段大范围开发。

---

## Phase 0：项目初始化

### TASK-0001：创建项目基础目录

目标：

- 创建 backend/
- 创建 frontend/
- 创建 docs/
- 创建 docker/
- 创建 scripts/
- 创建 .env.example
- 创建 README.md

验收：

- 项目目录结构清晰
- README 中包含启动说明占位
- 不实现具体业务

---

### TASK-0002：初始化后端 FastAPI

目标：

- 创建 FastAPI 应用
- 创建 main.py
- 创建 app/core/config.py
- 创建 app/core/response.py
- 创建 app/core/exceptions.py
- 创建健康检查接口 `/api/health`

验收：

- 后端可以启动
- 访问 `/api/health` 返回 success

---

### TASK-0003：初始化前端 React

目标：

- 使用 Vite + React + TypeScript
- 接入 React Router
- 接入 Ant Design
- 创建基础 Layout
- 创建左侧菜单
- 创建空页面路由

验收：

- 前端可以启动
- 左侧菜单包含素材中心、写作工作台
- 点击菜单可以切换页面

---

## Phase 1：数据库与基础设施

### TASK-0101：后端数据库基础

目标：

- 接入 PostgreSQL
- 配置 SQLAlchemy
- 配置 Alembic
- 创建通用 BaseModel
- 创建数据库 Session

验收：

- 可以运行 migration
- 可以连接数据库

---

### TASK-0102：Docker Compose

目标：

- 添加 PostgreSQL
- 添加 Redis
- 添加 backend
- 添加 frontend

验收：

- docker compose up 可以启动基础服务

---

## Phase 2：素材中心

### TASK-0201：关键词库后端接口

目标：

- 创建 keyword model
- 创建 keyword schema
- 创建 keyword CRUD
- 创建 keyword router
- 支持新增、编辑、删除、详情、分页列表

验收：

- Swagger 中可以测试完整 CRUD

---

### TASK-0202：关键词库前端页面

目标：

- 创建关键词库列表页
- 支持搜索、分页、新增、编辑、删除
- 对接后端接口

验收：

- 页面可以完整管理关键词

---

### TASK-0203：标题灵感后端接口

目标：

- 创建 title_inspiration model
- 创建 schema / CRUD / router
- 支持按主词筛选

验收：

- 可以维护主词对应的问题

---

### TASK-0204：标题灵感前端页面

目标：

- 创建标题灵感列表页
- 支持主词筛选、收录状态筛选
- 支持新增、编辑、删除

验收：

- 页面可以完整管理标题灵感

---

### TASK-0205：画像图库后端接口

目标：

- 创建 image_category
- 创建 image_asset
- 支持图库分类管理
- 支持图片详情管理
- 支持图片使用次数统计字段

验收：

- 可以创建图库分类
- 可以给分类添加图片

---

### TASK-0206：画像图库前端页面

目标：

- 创建图库分类列表页
- 创建图片详情页
- 支持图片预览、上传 URL、删除

验收：

- 可以维护图片素材

---

### TASK-0207：品牌知识库后端接口

目标：

- 创建 brand_knowledge model
- 字段包含知识库名称、公司名称、公司简称、创作方向、文案类型、产品服务、产品特点等
- 支持 CRUD

验收：

- 可以维护品牌知识库

---

### TASK-0208：品牌知识库前端页面

目标：

- 创建品牌知识库列表页
- 创建新增/编辑表单
- 长文本字段使用 TextArea

验收：

- 可以维护品牌知识库

---

## Phase 3：写作工作台

### TASK-0301：写作规范后端接口

目标：

- 创建 writing_rule model
- 创作类型枚举：article_creation、title_creation、traffic_replication
- 支持 CRUD

验收：

- 可以维护提示词指令

---

### TASK-0302：写作规范前端页面

目标：

- 创建写作规范列表页
- 支持按创作类型筛选
- 支持编辑长文本指令内容

验收：

- 可以维护提示词

---

### TASK-0303：内容分类后端接口

目标：

- 创建 content_category model
- 维护文章数量统计字段
- 支持 CRUD

验收：

- 可以维护文章分类

---

### TASK-0304：内容分类前端页面

目标：

- 创建内容分类列表页
- 支持新增、编辑、删除

验收：

- 可以维护分类

---

### TASK-0305：写作任务后端接口

目标：

- 创建 writing_task model
- 创建 article model
- 创建任务时根据 AI创作数量 创建 article 小任务
- 初始小任务状态为 generating 或 pending

验收：

- 创建一个大任务后，会生成对应数量的小任务

---

### TASK-0306：写作任务前端页面

目标：

- 创建写作任务列表页
- 创建任务新增页
- 表单中选择文章分类、蒸馏训练词、画像图库、企业知识库、内容创作指令、标题创作指令等

验收：

- 可以创建写作任务

---

### TASK-0307：文章清单后端接口

目标：

- 支持文章分页列表
- 支持查看详情
- 支持编辑内容
- 支持状态切换：待审核、正常、禁用

验收：

- 可以管理所有小任务文章

---

### TASK-0308：文章清单前端页面

目标：

- 创建文章列表页
- 创建文章详情/编辑页
- 支持富文本内容编辑
- 支持封面图展示
- 支持状态切换

验收：

- 可以审核和编辑文章

---

## Phase 4：MQ异步生成

### TASK-0401：接入 Redis + Worker

目标：

- 接入 Celery 或 Dramatiq
- 创建 worker 启动命令
- 创建测试任务

验收：

- Worker 可以正常消费任务

---

### TASK-0402：实现文章生成任务

目标：

- 创建 generate_article_task
- 根据 article_id 查询上下文
- 拼接关键词、知识库、写作规范、标题规范、图片素材
- 调用 AI 服务生成标题和正文
- 更新 article 状态

验收：

- 创建写作任务后，后台自动生成文章

---

### TASK-0403：大任务状态聚合

目标：

- 所有小任务完成后，大任务状态改为 completed
- 任意失败时记录失败数量
- 支持失败重试

验收：

- 大任务状态准确反映小任务进度