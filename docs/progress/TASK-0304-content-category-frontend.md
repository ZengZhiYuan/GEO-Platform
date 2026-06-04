# TASK-0304 内容分类前端页面

- 分支：feat/fe-content-category
- 范围：仅改动 frontend/（+ 本进度分片）；未触碰 backend/；未开发其他页面；未改动既有接口字段名
- 状态：已完成

## 变更要点

- 修改 `frontend/src/types/workspace.ts`：新增 `ContentCategoryItem` / `ContentCategoryListQuery` / `ContentCategoryCreatePayload` / `ContentCategoryUpdatePayload`，字段对齐 api-contract.md（`group_name` / `article_count`）；`article_count` 定位为只读统计字段，不进入 Create/Update 表单
- 新增 `frontend/src/api/contentCategory.ts`：`listContentCategories` / `getContentCategory` / `createContentCategory` / `updateContentCategory` / `deleteContentCategory`（GET|POST `/api/content-categories`、GET|PUT|DELETE `/api/content-categories/{id}`）
- 新增 `frontend/src/pages/workspace/content-category/index.tsx`：列表页（页面标题、分类名搜索、新增按钮、表格、文章数量 Tag、分页、编辑、删除二次确认、loading、empty、错误 Alert+重试、成功/失败提示；删当前页最后一条自动回退一页）
- 新增 `frontend/src/pages/workspace/content-category/ContentCategoryFormModal.tsx`：新增/编辑弹窗（分类名必填 + whitespace + 长度 ≤255 校验、提交 loading、取消返回、destroyOnClose）
- 修改 `frontend/src/router/index.tsx`：`/workspace/content-categories` 由占位页替换为 `ContentCategoryPage`（左侧菜单「写作工作台 / 内容分类」已存在，现可访问）

## 契约一致性

- 路径与字段严格对齐 `docs/api-contract.md`（唯一权威源）：资源 `/api/content-categories`，字段 `id` / `group_name` / `article_count` / `created_at` / `updated_at`
- 与 dev 文档草案 `ContentCategoryForm { group_name }` 一致；`article_count` 与关键词 `question_count`、图库 `image_count` 一样定位为只读输出字段，前端仅展示不提交（计数由后端写作任务/文章模块维护）

## 实测

- `npm install`（成功，165 包）
- `npm run build`（`tsc -b` 类型检查 + vite 生产构建，3117 modules transformed）通过，退出码 0

## 备注 / 遗留

- 后端 TASK-0303 内容分类接口若尚未就绪，本页面按契约封装，接口可用后可直接联调
- 代码风格完全对齐既有写作规范页（TASK-0302）：list 页结构、FormModal、api 封装、错误态/分页/二次确认一致
