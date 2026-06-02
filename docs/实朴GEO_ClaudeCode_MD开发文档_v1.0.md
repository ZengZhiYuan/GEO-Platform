# 实朴GEO Web应用 Claude Code 开发文档 v1.0

> 项目名称：实朴GEO  
> 项目类型：自媒体内容生成 Web 应用  
> 初始版本范围：素材中心 + 写作工作台  
> 目标使用者：内容运营人员、品牌文案人员、SEO/GEO内容生产人员、审核编辑人员  
> 文档用途：作为 Claude Code / 前端开发 / 后端开发的统一开发说明书，可直接用于拆分任务、生成代码、联调接口和验收功能。  
> 推荐技术栈：前端 Vue3 + Vite + TypeScript + Element Plus；后端 FastAPI + PostgreSQL + Redis + RabbitMQ/Celery；AI能力通过可插拔 LLM Provider 接入。

---

## 1. 项目总体说明

### 1.1 项目背景

实朴GEO 是一个面向小红书、知乎、微信公众号等自媒体平台的内容生成系统。系统的核心目标不是单纯调用大模型生成文章，而是通过“素材沉淀 + 写作规范 + 品牌知识 + 批量任务 + 审核编辑”的方式，形成可持续复用的内容生产工作流。

初始版本聚焦两个一级模块：

1. **素材中心**
   - 关键词库
   - 标题灵感
   - 画像图库
   - 品牌知识库

2. **写作工作台**
   - 写作规范
   - 内容分类
   - 写作任务
   - 文章清单

### 1.2 系统核心闭环

```mermaid
flowchart LR
    A[关键词库] --> B[标题灵感]
    C[画像图库] --> F[写作任务]
    D[品牌知识库] --> F
    E[写作规范] --> F
    G[内容分类] --> F
    F --> H[MQ异步生成小任务]
    H --> I[文章清单]
    I --> J[人工编辑/审核]
    J --> K[可发布内容]
```

### 1.3 初始版本边界

#### 需要实现

- 素材中心 4 个子模块的增删改查、列表筛选、详情查看。
- 写作工作台 4 个子模块的增删改查、任务创建、任务详情、文章编辑。
- 写作任务创建后，根据 AI创作数量 拆分为多个小任务。
- 小任务通过 MQ 在后台异步执行。
- 小任务生成完成后写入文章标题、封面图、正文内容、状态。
- 所有小任务完成后，大任务状态更新为完成。
- 文章清单统一管理所有生成出来的小任务文章。
- 支持文章正文富文本编辑，正文可以包含文字、表格、图片。
- 前后端分离，前后端可并行开发。

#### 暂不实现，但需要预留

- 多租户体系。
- 完整 RBAC 权限。
- 小红书/知乎/微信公众号一键发布。
- 爬虫自动采集标题灵感。
- 自动 SEO/GEO 效果分析。
- 文章数据看板。
- 复杂 AI Agent 编排。

---

## 2. 推荐技术架构

### 2.1 整体架构

```mermaid
flowchart TB
    subgraph FE[前端 Web]
        FE1[Vue3 页面]
        FE2[API Client]
        FE3[状态管理 Pinia]
        FE4[富文本编辑器]
    end

    subgraph BE[后端 API 服务]
        BE1[FastAPI Router]
        BE2[Service 业务层]
        BE3[SQLAlchemy ORM]
        BE4[AI Service]
        BE5[Task Service]
    end

    subgraph MQ[异步任务层]
        MQ1[RabbitMQ/Redis Broker]
        MQ2[Celery Worker]
        MQ3[任务重试/失败记录]
    end

    subgraph STORAGE[存储层]
        DB[(PostgreSQL)]
        REDIS[(Redis)]
        FILE[(本地文件/OSS)]
    end

    subgraph LLM[AI模型服务]
        LLM1[OpenAI兼容接口]
        LLM2[通义千问/DeepSeek/其他LLM]
    end

    FE --> BE
    BE --> DB
    BE --> REDIS
    BE --> FILE
    BE --> MQ1
    MQ1 --> MQ2
    MQ2 --> DB
    MQ2 --> FILE
    MQ2 --> LLM
```

### 2.2 推荐技术选型

#### 前端

| 类型 | 技术 | 说明 |
|---|---|---|
| 框架 | Vue 3 | 适合后台管理类系统 |
| 构建工具 | Vite | 启动快，适合 Claude Code 生成 |
| 语言 | TypeScript | 提升接口约束能力 |
| UI组件库 | Element Plus | 表格、表单、弹窗、分页成熟 |
| 状态管理 | Pinia | 管理用户信息、全局字典、任务状态 |
| 路由 | Vue Router | 管理模块页面跳转 |
| 请求库 | Axios | 统一封装 token、错误处理 |
| 富文本编辑器 | wangEditor 或 Tiptap | 文章正文编辑，支持图片、表格 |
| 图标 | @element-plus/icons-vue | 后台菜单图标 |
| 代码规范 | ESLint + Prettier | 保持代码一致 |

#### 后端

| 类型 | 技术 | 说明 |
|---|---|---|
| Web框架 | FastAPI | 适合前后端分离和 OpenAPI 自动文档 |
| ORM | SQLAlchemy 2.x | 数据库模型管理 |
| 数据校验 | Pydantic v2 | 请求/响应 DTO |
| 数据库 | PostgreSQL | 支持 JSONB、全文字段、复杂查询 |
| 迁移工具 | Alembic | 数据库版本迁移 |
| 缓存 | Redis | 任务状态缓存、热点数据缓存 |
| MQ | RabbitMQ + Celery | 文章生成小任务异步执行 |
| 文件存储 | 本地存储 / MinIO / OSS | 图片上传、封面图、图库图片 |
| AI接入 | OpenAI-compatible client | 可接通 OpenAI、Qwen、DeepSeek、本地模型 |
| 日志 | Loguru / structlog | 结构化日志 |
| 配置 | pydantic-settings | 环境变量配置 |

---

## 3. 仓库结构设计

建议使用单仓库 monorepo，便于 Claude Code 一次性理解项目结构，也方便前后端独立运行。

```text
shipu-geo/
├── README.md
├── DEVELOPMENT.md
├── docker-compose.yml
├── .env.example
├── docs/
│   ├── claude-code-dev.md
│   ├── api-contract.md
│   ├── database-design.md
│   └── frontend-routes.md
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router/index.ts
│       ├── stores/
│       ├── api/
│       ├── components/
│       ├── views/
│       ├── types/
│       └── utils/
└── backend/
    ├── pyproject.toml
    ├── alembic.ini
    ├── app/
    │   ├── main.py
    │   ├── core/
    │   ├── db/
    │   ├── models/
    │   ├── schemas/
    │   ├── api/v1/endpoints/
    │   ├── services/
    │   ├── workers/
    │   └── utils/
    ├── tests/
    └── alembic/versions/
```

### 3.1 前端详细目录

```text
frontend/src/
├── api/
│   ├── request.ts
│   ├── keyword.ts
│   ├── titleInspiration.ts
│   ├── imageGallery.ts
│   ├── brandKnowledge.ts
│   ├── writingRule.ts
│   ├── contentCategory.ts
│   ├── writingTask.ts
│   ├── article.ts
│   └── file.ts
├── components/
│   ├── AppLayout/
│   ├── SearchForm/
│   ├── DataTable/
│   ├── RichTextEditor/
│   ├── ImageUploader/
│   ├── StatusTag/
│   └── TaskProgress/
├── views/
│   ├── material/
│   │   ├── keyword/
│   │   ├── title-inspiration/
│   │   ├── image-gallery/
│   │   └── brand-knowledge/
│   └── workspace/
│       ├── writing-rule/
│       ├── content-category/
│       ├── writing-task/
│       └── article/
├── types/
│   ├── common.ts
│   ├── material.ts
│   └── workspace.ts
└── utils/
    ├── format.ts
    ├── enums.ts
    └── validate.ts
```

### 3.2 后端详细目录

```text
backend/app/
├── main.py
├── core/
│   ├── config.py
│   ├── security.py
│   ├── logging.py
│   └── exceptions.py
├── db/
│   ├── session.py
│   ├── base.py
│   └── init_db.py
├── models/
│   ├── keyword.py
│   ├── title_inspiration.py
│   ├── image_gallery.py
│   ├── brand_knowledge.py
│   ├── writing_rule.py
│   ├── content_category.py
│   ├── writing_task.py
│   ├── article.py
│   └── file_asset.py
├── schemas/
├── api/v1/endpoints/
├── services/
│   ├── prompt_assembler.py
│   ├── ai_generate_service.py
│   └── task_service.py
└── workers/
    ├── celery_app.py
    ├── article_generate_worker.py
    └── task_callback.py
```

---

## 4. 业务模块总览

| 一级模块 | 子模块 | 主要职责 |
|---|---|---|
| 素材中心 | 关键词库 | 管理内容创作主词，统计问题数量，跟踪优化状态 |
| 素材中心 | 标题灵感 | 管理围绕主词的用户提问/选题灵感 |
| 素材中心 | 画像图库 | 管理文章生成时可使用的图片素材 |
| 素材中心 | 品牌知识库 | 管理品牌、公司、产品、服务、文案方向等上下文知识 |
| 写作工作台 | 写作规范 | 管理文章创作、标题创作、流量复刻等提示词指令 |
| 写作工作台 | 内容分类 | 管理文章分组，便于文章沉淀 |
| 写作工作台 | 写作任务 | 组合素材和指令，批量生成文章 |
| 写作工作台 | 文章清单 | 管理所有小任务生成出来的文章 |

### 4.1 核心实体关系

```mermaid
erDiagram
    keyword_library ||--o{ title_inspiration : "主词关联"
    image_gallery ||--o{ image_asset : "包含图片"
    content_category ||--o{ writing_task : "任务归类"
    image_gallery ||--o{ writing_task : "任务选用图库"
    brand_knowledge ||--o{ writing_task : "任务选用知识库"
    writing_rule ||--o{ writing_task : "文章/标题指令"
    writing_task ||--o{ article_item : "拆分小任务"
```

---

## 5. 前端架构设计

### 5.1 前端设计原则

1. 页面按业务模块拆分：素材中心和写作工作台独立目录。
2. API 按后端资源拆分：每个业务实体一个 API 文件。
3. 表格页统一结构：搜索区 + 操作区 + 表格 + 分页 + 新增/编辑弹窗。
4. 复杂页面独立组件化：写作任务创建页、任务详情页、文章编辑页单独维护。
5. 状态枚举集中管理：所有状态字段放在 `utils/enums.ts`。
6. 接口类型集中维护：所有请求/响应类型放在 `types/` 下。

### 5.2 前端路由设计

```ts
const routes = [
  { path: '/', redirect: '/material/keywords' },
  {
    path: '/material',
    name: 'MaterialCenter',
    meta: { title: '素材中心' },
    children: [
      { path: 'keywords', name: 'KeywordLibrary', meta: { title: '关键词库' } },
      { path: 'title-inspirations', name: 'TitleInspiration', meta: { title: '标题灵感' } },
      { path: 'image-galleries', name: 'ImageGallery', meta: { title: '画像图库' } },
      { path: 'image-galleries/:id', name: 'ImageGalleryDetail', meta: { title: '图库详情' } },
      { path: 'brand-knowledge', name: 'BrandKnowledge', meta: { title: '品牌知识库' } }
    ]
  },
  {
    path: '/workspace',
    name: 'WritingWorkspace',
    meta: { title: '写作工作台' },
    children: [
      { path: 'writing-rules', name: 'WritingRule', meta: { title: '写作规范' } },
      { path: 'content-categories', name: 'ContentCategory', meta: { title: '内容分类' } },
      { path: 'writing-tasks', name: 'WritingTask', meta: { title: '写作任务' } },
      { path: 'writing-tasks/create', name: 'WritingTaskCreate', meta: { title: '创建写作任务' } },
      { path: 'writing-tasks/:id', name: 'WritingTaskDetail', meta: { title: '写作任务详情' } },
      { path: 'articles', name: 'ArticleList', meta: { title: '文章清单' } },
      { path: 'articles/:id/edit', name: 'ArticleEdit', meta: { title: '文章编辑' } }
    ]
  }
]
```

### 5.3 左侧菜单结构

```text
实朴GEO
├── 素材中心
│   ├── 关键词库
│   ├── 标题灵感
│   ├── 画像图库
│   └── 品牌知识库
└── 写作工作台
    ├── 写作规范
    ├── 内容分类
    ├── 写作任务
    └── 文章清单
```

### 5.4 页面跳转设计

```mermaid
flowchart TD
    A[关键词库] -->|查看主词相关问题| B[标题灵感]
    C[画像图库] -->|点击图库名称| D[图库详情]
    E[写作任务列表] -->|新增任务| F[创建写作任务]
    F -->|提交成功| G[写作任务详情]
    E -->|点击任务名称| G
    G -->|查看文章| H[文章编辑页]
    I[文章清单] -->|编辑| H
    H -->|保存| I
```

### 5.5 通用前端组件

| 组件 | 作用 |
|---|---|
| AppLayout | 后台整体布局，包含菜单、顶部栏、内容区 |
| SearchForm | 列表查询条件复用 |
| DataTable | 统一表格、分页、loading、空状态 |
| RichTextEditor | 文章正文富文本编辑 |
| ImageUploader | 图片上传、预览、删除、URL返回 |
| StatusTag | 枚举状态统一展示 |
| TaskProgress | 写作任务进度条和统计卡片 |

---

## 6. 前端页面功能设计

### 6.1 关键词库

路径：`/material/keywords`

功能：

- 查询关键词。
- 新增关键词。
- 编辑关键词。
- 删除关键词。
- 查看问题数量。
- 更新优化状态。
- 点击“问题数量”跳转标题灵感页面，并按主词过滤。

列表字段：

| 字段 | 说明 |
|---|---|
| 主词 | 关键词名称 |
| 问题数量 | 标题灵感中该主词关联的问题数量 |
| 优化状态 | 未优化、优化中、已优化 |
| 创建时间 | 创建时间 |
| 操作 | 编辑、删除、查看问题 |

表单字段：

```ts
interface KeywordForm {
  main_word: string
  optimize_status: 'not_optimized' | 'optimizing' | 'optimized'
}
```

### 6.2 标题灵感

路径：`/material/title-inspirations`

功能：

- 管理与主词相关的提问问题。
- 支持按主词筛选。
- 支持新增、编辑、删除。
- 支持修改收录状态。
- 可从关键词库跳转过来并自动带入主词筛选条件。

字段：主词、问题、收录状态、创建时间、操作。

```ts
interface TitleInspirationForm {
  main_word: string
  question: string
  included_status: 'not_included' | 'included'
}
```

### 6.3 画像图库

路径：`/material/image-galleries`

功能：

- 管理图库分类。
- 查看每个图库的图片数量。
- 新增图库分类。
- 编辑图库分类。
- 删除图库分类。
- 点击图库进入图库详情。

```ts
interface ImageGalleryForm {
  category_name: string
}
```

### 6.4 图库详情

路径：`/material/image-galleries/:id`

功能：

- 查看当前图库下的图片。
- 上传图片。
- 删除图片。
- 查看图片使用次数。
- 复制图片 URL。
- 图片预览。

```ts
interface ImageAssetForm {
  gallery_id: number
  image_url: string
}
```

### 6.5 品牌知识库

路径：`/material/brand-knowledge`

功能：

- 管理品牌/公司知识库。
- 用于文章生成时提供品牌上下文。
- 支持新增、编辑、删除、详情查看。
- 内容字段较多，建议新增/编辑使用抽屉或单独弹窗。

```ts
interface BrandKnowledgeForm {
  knowledge_name: string
  company_name: string
  company_short_name?: string
  writing_direction?: string
  copywriting_type?: string
  product_service?: string
  product_features?: string
  target_users?: string
  brand_tone?: string
  forbidden_words?: string
  extra_info?: string
}
```

### 6.6 写作规范

路径：`/workspace/writing-rules`

功能：

- 管理内容生成提示词指令。
- 创作类型包括：文章创作、标题创作、流量复刻。
- 写作任务创建时可选择不同类型的指令。
- 指令内容建议使用大文本输入框或代码编辑器样式。

```ts
interface WritingRuleForm {
  rule_name: string
  creation_type: 'article' | 'title' | 'traffic_replication'
  rule_content: string
}
```

### 6.7 内容分类

路径：`/workspace/content-categories`

功能：

- 管理文章分组。
- 创建写作任务时必须选择文章分类。
- 文章清单可按分类筛选。
- 统计分类下文章数量。

```ts
interface ContentCategoryForm {
  group_name: string
}
```

### 6.8 写作任务

路径：`/workspace/writing-tasks`

功能：

- 查看大任务列表。
- 创建大任务。
- 查看任务生成进度。
- 查看任务下所有小任务文章。
- 支持取消未完成任务。
- 支持失败任务重试。

创建任务字段：

```ts
interface WritingTaskCreateForm {
  task_name: string
  category_id: number
  distilled_keyword: string
  image_gallery_id?: number
  article_image_count: number
  brand_knowledge_id?: number
  article_rule_id: number
  title_rule_id?: number
  ai_generate_count: number
}
```

创建任务交互要求：

1. 用户点击“新增任务”。
2. 进入 `/workspace/writing-tasks/create`。
3. 填写任务名称、文章分类、蒸馏训练词。
4. 选择画像图库。
5. 填写文章配图数量。
6. 选择企业知识库。
7. 选择内容创作指令。
8. 选择标题创作指令。
9. 填写 AI 创作数量。
10. 点击“确认添加”。
11. 后端创建大任务和多个小任务。
12. 跳转任务详情页面查看进度。

### 6.9 写作任务详情

路径：`/workspace/writing-tasks/:id`

页面结构：

```text
写作任务详情
├── 任务基础信息
├── 任务素材配置
├── 生成进度
└── 小任务文章列表
```

要求：

- 展示任务状态。
- 展示总数量、待处理、生成中、成功、失败数量。
- 展示小任务列表。
- 支持失败小任务重试。
- 点击文章标题进入文章编辑页。
- 当任务处于 queued/running 时，每 3 秒轮询一次详情。

### 6.10 文章清单

路径：`/workspace/articles`

功能：

- 管理所有小任务生成的文章。
- 支持筛选分类、任务、状态、标题。
- 支持编辑文章。
- 支持禁用/恢复文章。
- 支持删除文章。
- 支持查看封面图。

### 6.11 文章编辑页

路径：`/workspace/articles/:id/edit`

功能：

- 编辑文章标题。
- 编辑封面图 URL。
- 编辑正文内容。
- 修改文章状态。
- 保存草稿。
- 预览文章。

```ts
interface ArticleEditForm {
  title: string
  cover_image_url?: string
  status: 'pending_review' | 'normal' | 'disabled'
  content_html: string
  content_json?: unknown
}
```

---

## 7. 后端架构设计

### 7.1 后端分层

```text
API Router 层
  负责接收 HTTP 请求、参数校验、权限入口、响应封装

Service 业务层
  负责业务规则、任务创建、状态流转、AI生成逻辑编排

Repository/CRUD 层
  负责数据库读写，可直接用 SQLAlchemy Session 实现

Model 层
  负责数据库表结构定义

Schema 层
  负责请求/响应 DTO 定义

Worker 层
  负责 MQ 异步小任务生成文章

AI Service 层
  负责封装大模型调用、提示词组装、结果解析
```

### 7.2 后端模块职责

| 模块 | 职责 |
|---|---|
| keywords | 关键词库 CRUD、问题数量统计 |
| title_inspirations | 标题灵感 CRUD、按主词筛选 |
| image_galleries | 图库分类 CRUD |
| image_assets | 图库图片 CRUD、使用次数更新 |
| brand_knowledge | 品牌知识库 CRUD |
| writing_rules | 写作规范 CRUD |
| content_categories | 内容分类 CRUD、文章数量统计 |
| writing_tasks | 大任务创建、状态管理、进度统计 |
| articles | 小任务文章管理、正文编辑、审核状态 |
| files | 文件上传、图片 URL 返回 |
| workers | 消费小任务生成文章 |
| ai_generate_service | AI 标题/正文生成 |
| prompt_assembler | 根据任务素材组装 Prompt |

### 7.3 API 统一响应格式

```json
{
  "code": 0,
  "message": "success",
  "data": {}
}
```

分页响应：

```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [],
    "total": 100,
    "page": 1,
    "page_size": 20
  }
}
```

错误响应：

```json
{
  "code": 40001,
  "message": "参数错误：任务名称不能为空",
  "data": null
}
```

---

## 8. 数据库设计

### 8.1 公共字段约定

所有业务表建议包含以下公共字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| id | BIGSERIAL | 主键 |
| created_at | TIMESTAMP | 创建时间 |
| updated_at | TIMESTAMP | 更新时间 |
| deleted_at | TIMESTAMP NULL | 软删除时间 |
| is_deleted | BOOLEAN | 是否删除 |
| tenant_id | BIGINT NULL | 租户ID，初始可为空 |
| created_by | BIGINT NULL | 创建人ID |
| updated_by | BIGINT NULL | 更新人ID |

### 8.2 表结构总览

| 表名 | 说明 |
|---|---|
| keyword_library | 关键词库 |
| title_inspiration | 标题灵感 |
| image_gallery | 画像图库分类 |
| image_asset | 图库图片详情 |
| brand_knowledge | 品牌知识库 |
| writing_rule | 写作规范 |
| content_category | 内容分类 |
| writing_task | 写作大任务 |
| article_item | 小任务文章 |
| file_asset | 文件资源 |

### 8.3 关键词库表 keyword_library

```sql
CREATE TABLE keyword_library (
    id BIGSERIAL PRIMARY KEY,
    main_word VARCHAR(255) NOT NULL,
    question_count INTEGER NOT NULL DEFAULT 0,
    optimize_status VARCHAR(32) NOT NULL DEFAULT 'not_optimized',
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.4 标题灵感表 title_inspiration

```sql
CREATE TABLE title_inspiration (
    id BIGSERIAL PRIMARY KEY,
    main_word VARCHAR(255) NOT NULL,
    keyword_id BIGINT NULL,
    question TEXT NOT NULL,
    included_status VARCHAR(32) NOT NULL DEFAULT 'not_included',
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.5 图库分类表 image_gallery

```sql
CREATE TABLE image_gallery (
    id BIGSERIAL PRIMARY KEY,
    category_name VARCHAR(255) NOT NULL,
    image_count INTEGER NOT NULL DEFAULT 0,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.6 图库图片表 image_asset

```sql
CREATE TABLE image_asset (
    id BIGSERIAL PRIMARY KEY,
    gallery_id BIGINT NOT NULL REFERENCES image_gallery(id),
    image_url TEXT NOT NULL,
    usage_count INTEGER NOT NULL DEFAULT 0,
    file_name VARCHAR(255) NULL,
    file_size BIGINT NULL,
    mime_type VARCHAR(128) NULL,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.7 品牌知识库表 brand_knowledge

```sql
CREATE TABLE brand_knowledge (
    id BIGSERIAL PRIMARY KEY,
    knowledge_name VARCHAR(255) NOT NULL,
    company_name VARCHAR(255) NOT NULL,
    company_short_name VARCHAR(255) NULL,
    writing_direction TEXT NULL,
    copywriting_type VARCHAR(128) NULL,
    product_service TEXT NULL,
    product_features TEXT NULL,
    target_users TEXT NULL,
    brand_tone TEXT NULL,
    forbidden_words TEXT NULL,
    extra_info TEXT NULL,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.8 写作规范表 writing_rule

```sql
CREATE TABLE writing_rule (
    id BIGSERIAL PRIMARY KEY,
    rule_name VARCHAR(255) NOT NULL,
    creation_type VARCHAR(64) NOT NULL,
    rule_content TEXT NOT NULL,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.9 内容分类表 content_category

```sql
CREATE TABLE content_category (
    id BIGSERIAL PRIMARY KEY,
    group_name VARCHAR(255) NOT NULL,
    article_count INTEGER NOT NULL DEFAULT 0,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.10 写作大任务表 writing_task

```sql
CREATE TABLE writing_task (
    id BIGSERIAL PRIMARY KEY,
    task_name VARCHAR(255) NOT NULL,
    category_id BIGINT NOT NULL REFERENCES content_category(id),
    distilled_keyword VARCHAR(255) NOT NULL,
    image_gallery_id BIGINT NULL REFERENCES image_gallery(id),
    article_image_count INTEGER NOT NULL DEFAULT 0,
    brand_knowledge_id BIGINT NULL REFERENCES brand_knowledge(id),
    article_rule_id BIGINT NOT NULL REFERENCES writing_rule(id),
    title_rule_id BIGINT NULL REFERENCES writing_rule(id),
    article_result_status VARCHAR(64) NOT NULL DEFAULT 'not_generated',
    ai_generate_count INTEGER NOT NULL DEFAULT 1,
    task_status VARCHAR(64) NOT NULL DEFAULT 'queued',
    total_count INTEGER NOT NULL DEFAULT 0,
    pending_count INTEGER NOT NULL DEFAULT 0,
    running_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.11 小任务文章表 article_item

```sql
CREATE TABLE article_item (
    id BIGSERIAL PRIMARY KEY,
    task_id BIGINT NOT NULL REFERENCES writing_task(id),
    category_id BIGINT NOT NULL REFERENCES content_category(id),
    article_title VARCHAR(500) NULL,
    cover_image_url TEXT NULL,
    review_status VARCHAR(64) NOT NULL DEFAULT 'pending_review',
    generate_status VARCHAR(64) NOT NULL DEFAULT 'pending',
    content_html TEXT NULL,
    content_text TEXT NULL,
    content_json JSONB NULL,
    generation_index INTEGER NOT NULL DEFAULT 1,
    retry_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    updated_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

### 8.12 文件资源表 file_asset

```sql
CREATE TABLE file_asset (
    id BIGSERIAL PRIMARY KEY,
    file_name VARCHAR(255) NOT NULL,
    file_url TEXT NOT NULL,
    file_size BIGINT NULL,
    mime_type VARCHAR(128) NULL,
    storage_type VARCHAR(64) NOT NULL DEFAULT 'local',
    business_type VARCHAR(64) NULL,
    tenant_id BIGINT NULL,
    created_by BIGINT NULL,
    is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at TIMESTAMP NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);
```

---

## 9. 核心数据流转设计

### 9.1 素材沉淀流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端
    participant API as 后端API
    participant DB as PostgreSQL

    U->>FE: 新增关键词/标题/图库/品牌知识
    FE->>API: POST 对应资源接口
    API->>API: 参数校验
    API->>DB: 写入业务表
    DB-->>API: 返回记录
    API-->>FE: 返回创建结果
    FE-->>U: 列表刷新
```

### 9.2 写作任务创建流程

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端
    participant API as 后端API
    participant DB as PostgreSQL
    participant MQ as MQ Broker

    U->>FE: 填写写作任务表单
    FE->>API: POST /writing-tasks
    API->>DB: 校验分类/图库/知识库/指令是否存在
    API->>DB: 创建 writing_task 大任务
    loop 根据 AI创作数量
        API->>DB: 创建 article_item 小任务
        API->>MQ: 投递 article_generate_job
    end
    API->>DB: 更新大任务统计字段
    API-->>FE: 返回 task_id
    FE->>FE: 跳转任务详情页
```

### 9.3 小任务异步生成流程

```mermaid
sequenceDiagram
    participant MQ as MQ Broker
    participant W as Celery Worker
    participant DB as PostgreSQL
    participant AI as AI Service
    participant FILE as 图片/文件服务

    MQ->>W: 消费 article_generate_job
    W->>DB: 查询 article_item 与 writing_task
    W->>DB: 更新 article_item.generate_status=running
    W->>DB: 更新 writing_task.running_count
    W->>DB: 查询品牌知识库/写作规范/图库图片
    W->>AI: 生成标题
    W->>AI: 生成正文
    W->>FILE: 选择/绑定封面图
    W->>DB: 保存标题、封面、正文
    W->>DB: 更新 article_item.generate_status=success
    W->>DB: 更新 writing_task 进度
    W->>DB: 判断是否所有小任务完成
    alt 全部完成
        W->>DB: writing_task.task_status=completed
    else 仍有小任务
        W->>DB: writing_task.task_status=running
    end
```

### 9.4 文章审核编辑流程

```mermaid
flowchart TD
    A[小任务生成文章] --> B[文章状态: 待审核]
    B --> C[用户进入文章编辑页]
    C --> D[修改标题/封面/正文]
    D --> E[保存]
    E --> F{是否通过?}
    F -->|正常| G[文章状态: 正常]
    F -->|不使用| H[文章状态: 禁用]
```

---

## 10. MQ 异步任务设计

### 10.1 消息体设计

```json
{
  "job_type": "article_generate",
  "task_id": 1001,
  "article_id": 90001,
  "generation_index": 1,
  "retry_count": 0,
  "created_at": "2026-06-02T10:00:00"
}
```

### 10.2 小任务状态机

```mermaid
stateDiagram-v2
    [*] --> pending
    pending --> running
    running --> success
    running --> failed
    failed --> pending: retry
    pending --> cancelled
    running --> cancelled
    success --> [*]
    cancelled --> [*]
```

### 10.3 大任务状态机

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running
    running --> completed
    running --> failed
    running --> cancelled
    failed --> running: retry failed items
    completed --> [*]
    cancelled --> [*]
```

### 10.4 任务进度更新规则

每次小任务状态变更后，需要重新统计大任务：

```sql
SELECT
  COUNT(*) AS total_count,
  COUNT(*) FILTER (WHERE generate_status = 'pending') AS pending_count,
  COUNT(*) FILTER (WHERE generate_status = 'running') AS running_count,
  COUNT(*) FILTER (WHERE generate_status = 'success') AS success_count,
  COUNT(*) FILTER (WHERE generate_status = 'failed') AS failed_count
FROM article_item
WHERE task_id = :task_id
AND is_deleted = FALSE;
```

更新逻辑：

```text
如果 success_count = total_count，则大任务状态为 completed，文章结果状态为 all_success。
如果 failed_count > 0 且 pending_count = 0 且 running_count = 0 且 success_count = 0，则大任务状态为 failed，文章结果状态为 failed。
如果 failed_count > 0 且 success_count > 0 且 pending_count = 0 且 running_count = 0，则大任务状态为 completed，文章结果状态为 partial_success。
如果 running_count > 0 或 pending_count > 0，则大任务状态为 running，文章结果状态为 generating。
```

### 10.5 重试设计

- 小任务失败后记录 `error_message`。
- 小任务最多重试 3 次。
- 用户可在任务详情页点击“重试失败项”。
- 重试时将失败小任务状态改为 `pending`，再次投递 MQ。
- 大任务状态从 `failed/completed` 改为 `running`。

---

## 11. AI 生成设计

### 11.1 AI Service 抽象

后端不要在 Worker 中直接写死某个模型，应该抽象为 `AiGenerateService`。

```python
class AiGenerateService:
    async def generate_title(self, prompt: str) -> str:
        ...

    async def generate_article(self, prompt: str) -> dict:
        ...
```

返回建议：

```json
{
  "title": "生成后的文章标题",
  "content_html": "<h1>...</h1><p>...</p>",
  "content_text": "纯文本内容",
  "cover_image_url": "https://xxx.com/cover.png"
}
```

### 11.2 Prompt 组装输入

| 来源 | 字段 |
|---|---|
| 写作任务 | 任务名称、蒸馏训练词、文章配图数量、AI创作序号 |
| 内容分类 | 分组名 |
| 品牌知识库 | 公司名称、简称、创作方向、文案类型、产品服务、产品特点 |
| 写作规范 | 内容创作指令、标题创作指令 |
| 画像图库 | 图片 URL 列表 |
| 标题灵感 | 与主词相关的问题，初始版本可选做 |

### 11.3 标题生成 Prompt 模板

```text
你是一个擅长小红书、知乎、微信公众号内容选题的标题策划专家。

【创作平台/类型】
{copywriting_type}

【主创作词】
{distilled_keyword}

【品牌信息】
公司名称：{company_name}
公司简称：{company_short_name}
创作方向：{writing_direction}
产品服务：{product_service}
产品特点：{product_features}

【标题创作指令】
{title_rule_content}

【要求】
1. 生成一个适合自媒体传播的标题。
2. 标题要围绕主创作词展开。
3. 不要夸大承诺，不要出现违规表达。
4. 只返回标题本身，不要返回解释。
```

### 11.4 文章生成 Prompt 模板

```text
你是一个专业的新媒体内容写作专家，请根据以下信息生成一篇可发布的文章。

【文章标题】
{article_title}

【创作关键词】
{distilled_keyword}

【文章分类】
{category_name}

【品牌知识】
公司名称：{company_name}
公司简称：{company_short_name}
创作方向：{writing_direction}
文案类型：{copywriting_type}
产品服务：{product_service}
产品特点：{product_features}
目标用户：{target_users}
品牌语气：{brand_tone}
禁用词：{forbidden_words}
补充信息：{extra_info}

【内容创作指令】
{article_rule_content}

【配图要求】
文章需要使用 {article_image_count} 张图片。
可用图片URL：
{image_urls}

【输出要求】
请返回 JSON，格式如下：
{
  "title": "文章标题",
  "content_html": "HTML格式正文，允许包含h2、p、ul、ol、table、img标签",
  "content_text": "纯文本正文",
  "suggested_cover_image_url": "建议封面图URL"
}
```

### 11.5 AI 结果解析

1. 优先解析 JSON。
2. 如果 JSON 解析失败，尝试提取代码块中的 JSON。
3. 如果仍失败，将大模型原始输出作为 `content_text`，并用简单段落转换成 HTML。
4. 如果标题为空，则使用标题生成结果或默认标题。
5. 如果封面图为空，则从图库中随机选择一张。
6. 如果内容为空，则标记小任务失败。

---

## 12. 后端 API 设计

### 12.1 关键词库 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/keywords` | 分页查询关键词 |
| POST | `/api/v1/keywords` | 新增关键词 |
| GET | `/api/v1/keywords/{id}` | 获取关键词详情 |
| PUT | `/api/v1/keywords/{id}` | 更新关键词 |
| DELETE | `/api/v1/keywords/{id}` | 删除关键词 |

创建请求：

```json
{
  "main_word": "工业数字化",
  "optimize_status": "not_optimized"
}
```

### 12.2 标题灵感 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/title-inspirations` | 分页查询标题灵感 |
| POST | `/api/v1/title-inspirations` | 新增标题灵感 |
| GET | `/api/v1/title-inspirations/{id}` | 获取详情 |
| PUT | `/api/v1/title-inspirations/{id}` | 更新 |
| DELETE | `/api/v1/title-inspirations/{id}` | 删除 |

### 12.3 画像图库 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/image-galleries` | 查询图库分类 |
| POST | `/api/v1/image-galleries` | 新增图库分类 |
| GET | `/api/v1/image-galleries/{id}` | 获取图库详情 |
| PUT | `/api/v1/image-galleries/{id}` | 更新图库 |
| DELETE | `/api/v1/image-galleries/{id}` | 删除图库 |
| GET | `/api/v1/image-galleries/{id}/images` | 查询图库图片 |
| POST | `/api/v1/image-galleries/{id}/images` | 新增图库图片 |
| DELETE | `/api/v1/image-galleries/{id}/images/{image_id}` | 删除图库图片 |

### 12.4 品牌知识库 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/brand-knowledge` | 分页查询品牌知识 |
| POST | `/api/v1/brand-knowledge` | 新增品牌知识 |
| GET | `/api/v1/brand-knowledge/{id}` | 获取详情 |
| PUT | `/api/v1/brand-knowledge/{id}` | 更新 |
| DELETE | `/api/v1/brand-knowledge/{id}` | 删除 |

### 12.5 写作规范 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/writing-rules` | 分页查询写作规范 |
| POST | `/api/v1/writing-rules` | 新增写作规范 |
| GET | `/api/v1/writing-rules/{id}` | 获取详情 |
| PUT | `/api/v1/writing-rules/{id}` | 更新 |
| DELETE | `/api/v1/writing-rules/{id}` | 删除 |

### 12.6 内容分类 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/content-categories` | 查询内容分类 |
| POST | `/api/v1/content-categories` | 新增分类 |
| GET | `/api/v1/content-categories/{id}` | 获取详情 |
| PUT | `/api/v1/content-categories/{id}` | 更新分类 |
| DELETE | `/api/v1/content-categories/{id}` | 删除分类 |

### 12.7 写作任务 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/writing-tasks` | 查询大任务列表 |
| POST | `/api/v1/writing-tasks` | 创建大任务并投递小任务 |
| GET | `/api/v1/writing-tasks/{id}` | 获取大任务详情 |
| GET | `/api/v1/writing-tasks/{id}/articles` | 查询任务下文章 |
| POST | `/api/v1/writing-tasks/{id}/cancel` | 取消任务 |
| POST | `/api/v1/writing-tasks/{id}/retry-failed` | 重试失败小任务 |
| DELETE | `/api/v1/writing-tasks/{id}` | 删除任务 |

创建请求：

```json
{
  "task_name": "工业数字化公众号文章批量生成",
  "category_id": 1,
  "distilled_keyword": "工业数字化",
  "image_gallery_id": 1,
  "article_image_count": 2,
  "brand_knowledge_id": 1,
  "article_rule_id": 1,
  "title_rule_id": 2,
  "ai_generate_count": 10
}
```

### 12.8 文章清单 API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/articles` | 分页查询文章 |
| GET | `/api/v1/articles/{id}` | 获取文章详情 |
| PUT | `/api/v1/articles/{id}` | 更新文章标题、封面、正文、状态 |
| POST | `/api/v1/articles/{id}/disable` | 禁用文章 |
| POST | `/api/v1/articles/{id}/enable` | 恢复文章 |
| POST | `/api/v1/articles/{id}/retry` | 重试该文章生成 |
| DELETE | `/api/v1/articles/{id}` | 删除文章 |

### 12.9 文件上传 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/v1/files/upload` | 上传文件 |
| POST | `/api/v1/files/upload-image` | 上传图片 |

---

## 13. 前后端并行开发约定

### 13.1 接口 Mock 优先

前端可以先根据本文件中的 API 契约写 Mock 数据，不等待后端完成。

```text
frontend/src/api/mock/
├── keyword.mock.ts
├── titleInspiration.mock.ts
├── imageGallery.mock.ts
├── brandKnowledge.mock.ts
├── writingRule.mock.ts
├── contentCategory.mock.ts
├── writingTask.mock.ts
└── article.mock.ts
```

### 13.2 类型先行

前端先定义类型：

```text
frontend/src/types/material.ts
frontend/src/types/workspace.ts
frontend/src/types/common.ts
```

后端先定义 Pydantic Schema：

```text
backend/app/schemas/*.py
```

两边字段必须保持一致，统一使用 snake_case 返回给前端。前端 TypeScript 类型也直接使用 snake_case，避免字段转换增加复杂度。

### 13.3 字段命名约定

| 规则 | 示例 |
|---|---|
| 后端字段 | `main_word` |
| 前端字段 | `main_word` |
| API路径 | `/api/v1/title-inspirations` |
| 数据库表 | `title_inspiration` |
| Python模型 | `TitleInspiration` |
| Vue组件 | `TitleInspirationPage` |

### 13.4 分页参数约定

请求：

```text
page=1&page_size=20
```

响应：

```json
{
  "items": [],
  "total": 100,
  "page": 1,
  "page_size": 20
}
```

---

## 14. 后端实现重点

### 14.1 创建写作任务的事务要求

创建写作大任务和小任务必须在同一个数据库事务中完成。

```python
def create_writing_task(db: Session, payload: WritingTaskCreate):
    validate_category_exists(db, payload.category_id)
    validate_rule_exists(db, payload.article_rule_id)

    task = WritingTask(
        task_name=payload.task_name,
        category_id=payload.category_id,
        distilled_keyword=payload.distilled_keyword,
        image_gallery_id=payload.image_gallery_id,
        article_image_count=payload.article_image_count,
        brand_knowledge_id=payload.brand_knowledge_id,
        article_rule_id=payload.article_rule_id,
        title_rule_id=payload.title_rule_id,
        ai_generate_count=payload.ai_generate_count,
        total_count=payload.ai_generate_count,
        pending_count=payload.ai_generate_count,
        task_status="queued",
        article_result_status="generating",
    )
    db.add(task)
    db.flush()

    articles = []
    for i in range(payload.ai_generate_count):
        article = ArticleItem(
            task_id=task.id,
            category_id=payload.category_id,
            generation_index=i + 1,
            generate_status="pending",
            review_status="pending_review",
        )
        db.add(article)
        db.flush()
        articles.append(article)

    db.commit()

    for article in articles:
        send_article_generate_job(task.id, article.id, article.generation_index)

    return task
```

### 14.2 Worker 幂等性

Worker 消费消息时必须检查小任务状态，避免重复消费导致重复写入。

```text
如果 article.generate_status = success，则直接忽略。
如果 article.generate_status = cancelled，则直接忽略。
如果 article 不存在或已删除，则直接忽略。
如果 task 已取消，则将 article 置为 cancelled。
```

### 14.3 Worker 错误处理

```python
try:
    generate_article(article_id)
except Exception as e:
    mark_article_failed(article_id, str(e))
    refresh_task_progress(task_id)
```

### 14.4 取消任务

取消任务时：

1. 大任务状态改为 `cancelled`。
2. 所有 `pending` 小任务改为 `cancelled`。
3. 正在运行的小任务无法强行杀掉时，可以让 Worker 在写入前检查大任务状态，如果已取消则不保存结果。
4. 前端展示“已取消”。

### 14.5 删除策略

初始版本使用软删除：

- `is_deleted = true`
- `deleted_at = now()`

删除大任务时，不物理删除小任务文章，只将大任务和文章一并软删除。

---

## 15. 前端实现重点

### 15.1 列表页通用模式

每个列表页建议保持一致：

```vue
<template>
  <PageContainer>
    <SearchForm />
    <div class="toolbar">
      <el-button type="primary">新增</el-button>
    </div>
    <DataTable />
    <EditDialog />
  </PageContainer>
</template>
```

### 15.2 写作任务创建页

该页面是初始版本最核心页面，不能做成简单弹窗，应使用单独页面。

页面区域：

```text
创建写作任务
├── 基础信息
│   ├── 任务名称
│   ├── 文章分类
│   └── 蒸馏训练词
├── 素材配置
│   ├── 画像图库
│   ├── 文章配图数量
│   └── 企业知识库
├── 写作指令
│   ├── 内容创作指令
│   └── 标题创作指令
├── 生成配置
│   └── AI创作数量
└── 操作区
    ├── 取消
    └── 确认添加
```

### 15.3 任务详情页轮询

任务详情页需要轮询任务状态：

```ts
let timer: number | null = null

onMounted(() => {
  fetchTaskDetail()
  timer = window.setInterval(() => {
    if (['queued', 'running'].includes(task.value.task_status)) {
      fetchTaskDetail()
      fetchTaskArticles()
    }
  }, 3000)
})

onBeforeUnmount(() => {
  if (timer) clearInterval(timer)
})
```

### 15.4 文章编辑页

文章编辑页必须避免直接修改列表数据，应该：

1. 进入页面时 GET 文章详情。
2. 编辑本地表单。
3. 点击保存时 PUT 更新。
4. 保存成功后提示并返回文章清单或停留当前页。

---

## 16. 枚举字典统一设计

### 16.1 前端枚举

```ts
export const OptimizeStatusOptions = [
  { label: '未优化', value: 'not_optimized' },
  { label: '优化中', value: 'optimizing' },
  { label: '已优化', value: 'optimized' }
]

export const IncludedStatusOptions = [
  { label: '未收录', value: 'not_included' },
  { label: '已收录', value: 'included' }
]

export const CreationTypeOptions = [
  { label: '文章创作', value: 'article' },
  { label: '标题创作', value: 'title' },
  { label: '流量复刻', value: 'traffic_replication' }
]

export const TaskStatusOptions = [
  { label: '草稿', value: 'draft' },
  { label: '排队中', value: 'queued' },
  { label: '运行中', value: 'running' },
  { label: '已完成', value: 'completed' },
  { label: '失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' }
]

export const ArticleReviewStatusOptions = [
  { label: '待审核', value: 'pending_review' },
  { label: '正常', value: 'normal' },
  { label: '禁用', value: 'disabled' }
]

export const GenerateStatusOptions = [
  { label: '待生成', value: 'pending' },
  { label: '生成中', value: 'running' },
  { label: '生成成功', value: 'success' },
  { label: '生成失败', value: 'failed' },
  { label: '已取消', value: 'cancelled' }
]
```

### 16.2 后端枚举

```python
from enum import StrEnum

class OptimizeStatus(StrEnum):
    NOT_OPTIMIZED = "not_optimized"
    OPTIMIZING = "optimizing"
    OPTIMIZED = "optimized"

class CreationType(StrEnum):
    ARTICLE = "article"
    TITLE = "title"
    TRAFFIC_REPLICATION = "traffic_replication"

class TaskStatus(StrEnum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
```

---

## 17. 开发顺序建议

### 17.1 后端开发顺序

```text
第 1 步：初始化 FastAPI 项目、数据库连接、统一响应、异常处理。
第 2 步：定义所有 SQLAlchemy Models。
第 3 步：配置 Alembic 并生成数据库迁移。
第 4 步：实现素材中心 CRUD。
第 5 步：实现写作规范、内容分类 CRUD。
第 6 步：实现文章清单 CRUD。
第 7 步：实现写作任务创建逻辑，不接 MQ，先同步创建大任务和小任务。
第 8 步：接入 Celery/RabbitMQ，实现小任务异步消费。
第 9 步：实现 AI Service Mock，先返回假文章。
第 10 步：接入真实 LLM Provider。
第 11 步：实现文件上传。
第 12 步：补充测试和接口文档。
```

### 17.2 前端开发顺序

```text
第 1 步：初始化 Vue3 + Vite + TypeScript + Element Plus 项目。
第 2 步：完成 Layout、左侧菜单、顶部栏、路由。
第 3 步：封装 Axios、分页表格、搜索表单、状态标签。
第 4 步：实现素材中心四个模块页面。
第 5 步：实现写作规范、内容分类页面。
第 6 步：实现写作任务列表和创建页。
第 7 步：实现写作任务详情页和轮询进度。
第 8 步：实现文章清单。
第 9 步：实现文章编辑页和富文本编辑器。
第 10 步：实现图片上传、预览、复制 URL。
第 11 步：联调后端接口。
第 12 步：统一处理 loading、错误提示、空状态。
```

### 17.3 前后端并行拆分

| 阶段 | 前端 | 后端 |
|---|---|---|
| 阶段1 | 搭建页面框架、路由、Mock API | 搭建 FastAPI、DB、基础 CRUD |
| 阶段2 | 完成素材中心页面 | 完成素材中心接口 |
| 阶段3 | 完成写作工作台基础页 | 完成写作规范、分类、文章接口 |
| 阶段4 | 完成任务创建/详情/轮询 | 完成任务创建、MQ、Worker |
| 阶段5 | 完成文章编辑和图片上传 | 完成文件上传、AI生成接入 |
| 阶段6 | 联调、修复交互 | 联调、补充日志和异常处理 |

---

## 18. Claude Code 执行提示词建议

### 18.1 初始化项目提示词

```text
请基于当前目录创建一个名为 shipu-geo 的前后端分离项目。

要求：
1. frontend 使用 Vue3 + Vite + TypeScript + Element Plus。
2. backend 使用 FastAPI + SQLAlchemy + PostgreSQL + Alembic。
3. 按 docs/claude-code-dev.md 中的项目结构创建目录。
4. 先不要实现全部业务，只完成项目骨架、路由、数据库连接、统一响应格式。
5. 保证前端和后端都可以独立启动。
```

### 18.2 后端 CRUD 开发提示词

```text
请根据 docs/claude-code-dev.md 中的数据库设计和 API 设计，完成素材中心模块的后端接口。

范围：
1. 关键词库 keyword_library CRUD。
2. 标题灵感 title_inspiration CRUD。
3. 画像图库 image_gallery 和 image_asset CRUD。
4. 品牌知识库 brand_knowledge CRUD。

要求：
1. 使用 SQLAlchemy 2.x ORM。
2. 使用 Pydantic v2 定义请求和响应 Schema。
3. 所有列表接口支持分页。
4. 所有删除使用软删除。
5. 所有接口使用统一响应格式。
6. 补充必要的参数校验和错误处理。
```

### 18.3 前端页面开发提示词

```text
请根据 docs/claude-code-dev.md 的前端页面设计，完成素材中心模块页面。

范围：
1. /material/keywords 关键词库。
2. /material/title-inspirations 标题灵感。
3. /material/image-galleries 画像图库。
4. /material/image-galleries/:id 图库详情。
5. /material/brand-knowledge 品牌知识库。

要求：
1. 使用 Element Plus 表格、表单、弹窗、分页。
2. 每个页面支持查询、新增、编辑、删除。
3. API 请求封装到 src/api 下。
4. TypeScript 类型定义放到 src/types。
5. 状态枚举统一从 src/utils/enums.ts 引入。
```

### 18.4 写作任务开发提示词

```text
请实现写作任务模块，重点完成大任务创建、小任务拆分、MQ异步生成和任务进度统计。

要求：
1. POST /api/v1/writing-tasks 创建大任务。
2. 根据 ai_generate_count 创建对应数量的 article_item 小任务。
3. 每个小任务投递一条 Celery 消息。
4. Worker 消费后调用 AiGenerateService 生成文章。
5. AiGenerateService 先实现 Mock 返回，后续再接真实大模型。
6. 每个小任务完成后更新大任务统计字段。
7. 所有小任务完成后更新大任务状态为 completed。
8. 支持失败小任务重试。
```

---

## 19. 环境变量设计

### 19.1 后端 .env.example

```env
APP_NAME=shipu-geo
APP_ENV=development
DEBUG=true
API_PREFIX=/api/v1
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/shipu_geo
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//
CELERY_RESULT_BACKEND=redis://localhost:6379/1
UPLOAD_DIR=./static/uploads
STATIC_URL_PREFIX=http://localhost:8000/static/uploads
LLM_PROVIDER=openai_compatible
LLM_API_BASE=https://api.openai.com/v1
LLM_API_KEY=replace-me
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=120
```

### 19.2 前端 .env.example

```env
VITE_APP_TITLE=实朴GEO
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_UPLOAD_URL=http://localhost:8000/api/v1/files/upload-image
```

---

## 20. Docker Compose 设计

```yaml
version: "3.9"

services:
  postgres:
    image: postgres:16
    container_name: shipu_geo_postgres
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: shipu_geo
    ports:
      - "5432:5432"
    volumes:
      - shipu_geo_pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7
    container_name: shipu_geo_redis
    ports:
      - "6379:6379"

  rabbitmq:
    image: rabbitmq:3-management
    container_name: shipu_geo_rabbitmq
    ports:
      - "5672:5672"
      - "15672:15672"
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest

volumes:
  shipu_geo_pgdata:
```

---

## 21. 验收标准

### 21.1 素材中心验收

- 可以新增、编辑、删除关键词。
- 可以新增、编辑、删除标题灵感。
- 关键词列表中的问题数量能正确统计。
- 可以创建图库分类。
- 可以上传或录入图片 URL。
- 图库图片数量能正确统计。
- 可以创建品牌知识库。
- 品牌知识库内容可在写作任务中选择。

### 21.2 写作工作台验收

- 可以创建文章创作、标题创作、流量复刻三类写作规范。
- 可以创建内容分类。
- 可以创建写作任务。
- 写作任务提交后自动生成对应数量的小任务。
- 小任务能通过 Worker 异步生成文章。
- 大任务详情能看到实时进度。
- 所有小任务完成后大任务状态变为已完成。
- 文章清单能看到所有生成文章。
- 文章可以编辑标题、封面图和正文。
- 文章可以切换待审核、正常、禁用状态。

### 21.3 技术验收

- 前端能独立启动。
- 后端能独立启动。
- 数据库迁移能正常执行。
- OpenAPI 文档可访问。
- 所有列表接口支持分页。
- 所有删除接口为软删除。
- Worker 重启后仍能继续消费消息。
- AI 生成失败时小任务状态为失败，并记录错误信息。
- 失败小任务可重试。

---

## 22. 后续扩展方向

### 22.1 内容平台扩展

- 小红书内容模板。
- 知乎问答模板。
- 微信公众号长文模板。
- 抖音短视频脚本文案。
- B站视频脚本文案。

### 22.2 GEO 能力扩展

- 品牌关键词覆盖分析。
- 问题库自动扩展。
- 搜索意图聚类。
- 内容主题评分。
- AI 搜索可见性分析。
- 竞品内容复刻。
- 平台分发效果追踪。

### 22.3 AI 能力扩展

- 多模型切换。
- Prompt 版本管理。
- 生成结果评分。
- 生成内容查重。
- 敏感词检测。
- 违规内容检测。
- 自动生成配图。
- AI Agent 多步骤写作流程。

### 22.4 权限体系扩展

- 用户管理。
- 角色管理。
- 租户管理。
- 菜单权限。
- 数据权限。
- 知识库权限。
- 任务操作权限。

---

## 23. Claude Code 开发注意事项

1. 不要一次性让 Claude Code 生成全项目所有代码，应该按模块拆分。
2. 先生成项目骨架，再生成数据库模型，再生成接口，再生成页面。
3. 每完成一个模块就运行测试和启动验证。
4. 前端页面先用 Mock 数据，后端接口完成后再联调。
5. 写作任务和 MQ 是核心复杂点，需要单独开发和测试。
6. AI Service 初期必须做 Mock，避免真实模型不稳定影响主流程。
7. 富文本编辑器先保存 HTML，后续再扩展结构化 JSON。
8. 图片上传初期可使用本地目录，后续再换 OSS/MinIO。
9. 所有状态枚举必须统一管理，不要散落在页面或接口代码里。
10. 所有接口返回格式必须统一，方便前端全局拦截处理。
