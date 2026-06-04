# TASK-0308 文章清单前端页面

- 分支：feat/fe-article
- 范围：仅改动 frontend/；未触碰 backend/；未改动既有接口字段名
- 状态：已完成

## 变更要点

- 修改 `frontend/src/types/workspace.ts`：新增文章相关类型
  - `ArticleStatus`（generating / pending_review / normal / disabled / failed）
  - `ArticleEditableStatus`（人工可切换：pending_review / normal / disabled）
  - `ArticleItem`（id / writing_task_id / article_title / cover_image_url / status / content / error_message / created_at / updated_at，严格对齐契约）
  - `ArticleListQuery`（分页 + article_title 搜索 + status 筛选 + writing_task_id）
  - `ArticleUpdatePayload`（PUT 体：article_title / cover_image_url / content / status）
  - `ArticleStatusUpdatePayload`（POST /status 体：status）
- 修改 `frontend/src/utils/enums.ts`：新增 `ArticleStatusOptions`（全量，含系统态）/ `ArticleEditableStatusOptions`（待审核·正常·禁用）/ `ArticleStatusColorMap` / `getArticleStatusLabel`
- 新增 `frontend/src/api/article.ts`：`listArticles` / `getArticle` / `updateArticle` / `updateArticleStatus`
  - GET `/api/articles`、GET `/api/articles/{id}`、PUT `/api/articles/{id}`、POST `/api/articles/{id}/status`
- 新增 `frontend/src/pages/workspace/article/index.tsx`：文章列表页（`/workspace/articles`）
  - 页面标题、标题搜索、状态筛选、表格、封面缩略图（Image）、状态 Tag、分页、loading、空数据、错误 Alert+重试
  - 行内「状态切换」Dropdown（待审核/正常/禁用，当前态禁用项）走 POST `/status`，行级 loading
  - 点击标题或「编辑」跳转编辑页
- 新增 `frontend/src/pages/workspace/article/edit.tsx`：文章编辑页（`/workspace/articles/:id/edit`）
  - 返回按钮 + 当前状态 Tag；进入时 GET 详情回填，本地表单编辑，保存走 PUT
  - 标题（必填+长度）、封面图 URL（url 格式+长度校验）+ 实时封面预览（Image，含 fallback）、正文 TextArea（autoSize）、状态 Select（仅三种可切换态）
  - 系统态提示：generating 显示「生成中」info、failed 显示 error_message warning
  - 非法 id 兜底提示；loading（Spin）、保存成功/失败提示（失败由拦截器统一弹出，停留当前页）
- 修改 `frontend/src/router/index.tsx`：`/workspace/articles` 由占位页替换为 `ArticleListPage`，新增 `/workspace/articles/:id/edit` → `ArticleEditPage`

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）：
  - 文章字段用 `article_title` / `cover_image_url` / `content` / `status` / `writing_task_id` / `error_message`（非 dev 文档草案的 `title` / `content_html` / `content_json`）
  - 接口为 GET/PUT `/api/articles`、GET `/api/articles/{id}`、POST `/api/articles/{id}/status`
  - status 枚举取契约 5 值；人工可切换子集为 pending_review / normal / disabled（对应任务要求「待审核·正常·禁用」）
- 正文编辑：契约字段为单一 `content`，故采用 TextArea 编辑纯文本/HTML 字符串；项目当前无富文本编辑器依赖（dev 文档建议的 wangEditor/Tiptap 尚未引入），未新增依赖，后续可在不改字段名前提下升级为富文本。

## 实测

- `npm install`（成功）
- `npm run build`（tsc -b 类型检查 + vite 生产构建，3120 modules，built in ~6.6s）通过

## 备注 / 遗留

- 后端文章接口（articles CRUD + status）尚未开发，页面按契约封装，接口就绪后可直接联调。
- 任务要求「从写作任务详情页点击小任务进入文章编辑页」：写作任务详情页当前仍为占位页（TASK 未开发），编辑页路由 `/workspace/articles/:id/edit` 已就绪，待详情页开发时直接 `navigate` 即可衔接。
- 正文若后续需富文本（图片/表格），可引入编辑器组件替换 TextArea，`content` 字段名保持不变。
