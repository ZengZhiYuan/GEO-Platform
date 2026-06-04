# TASK-0306 写作任务前端页面

- 分支：feat/fe-writing-task
- 范围：仅改动 frontend/（+ 本进度分片）；未触碰 backend/；未开发文章编辑页；未改动既有接口字段名
- 状态：已完成

## 变更要点

- 修改 `frontend/src/types/workspace.ts`：新增写作任务相关类型 `TaskStatus`（draft/pending/running/completed/failed/cancelled）、`WritingTaskItem`、`WritingTaskListQuery`、`WritingTaskCreatePayload`；新增文章相关类型 `ArticleStatus`（generating/pending_review/normal/disabled/failed）、`ArticleItem`、`ArticleListQuery`，字段严格对齐 api-contract.md
- 修改 `frontend/src/utils/enums.ts`：新增 `TaskStatusOptions` / `TaskStatusColorMap` / `getTaskStatusLabel` 与 `ArticleStatusOptions` / `ArticleStatusColorMap` / `getArticleStatusLabel`
- 新增 `frontend/src/api/writingTask.ts`：`listWritingTasks` / `getWritingTask` / `createWritingTask` / `cancelWritingTask` / `retryWritingTask`（GET|POST `/api/writing-tasks`、GET `/api/writing-tasks/{id}`、POST `/api/writing-tasks/{id}/cancel`、POST `/api/writing-tasks/{id}/retry`）
- 新增 `frontend/src/api/article.ts`：仅 `listArticles`（GET `/api/articles`，按 `writing_task_id` 过滤）——用于详情页小任务列表，不含文章编辑接口
- 新增 `frontend/src/pages/workspace/writing-task/index.tsx`：列表页（页面标题、任务名搜索、状态筛选、新增按钮、表格、任务名/操作列跳详情、AI 数量与状态 Tag、分页、loading、错误 Alert+重试）
- 新增 `frontend/src/pages/workspace/writing-task/create.tsx`：新增页（单独页面非弹窗，分区：基础信息/素材配置/写作指令/生成配置/操作区）。文章分类(必填)、画像图库(可选)、企业知识库(可选)、内容创作指令(必填)、标题创作指令(可选) 五个下拉一次性拉取选项（page_size=100）；蒸馏训练词输入、文章配图数量 InputNumber(0-50)、AI 创作数量 InputNumber(1-100)；必填/whitespace/长度校验、提交 loading、选项加载失败 Alert+重试；创建成功后 `navigate` 到任务详情页
- 新增 `frontend/src/pages/workspace/writing-task/detail.tsx`：详情页（任务基础信息 / 任务素材配置 / 生成进度 / 小任务文章列表 四区）。素材配置把外键 ID 映射为可读名称（一次性加载分类/图库/知识库/规范名称表，缺失回退 `#id`）；生成进度由小任务列表派生统计（总数/生成中/待审核/正常/禁用/失败）；任务处于 pending/running 时每 3 秒静默轮询刷新；pending/running 显示「取消任务」（二次确认），failed 或存在失败小任务时显示「重试失败项」；小任务标题点击跳 `/workspace/articles/:id/edit`（编辑页后续任务实现）；无效 ID 兜底、loading(Spin)、错误 Alert+重试
- 修改 `frontend/src/router/index.tsx`：`/workspace/writing-tasks` 由占位页替换为列表页，并新增 `/workspace/writing-tasks/create`（新增页）与 `/workspace/writing-tasks/:id`（详情页）

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）。与 dev 文档草案字段名冲突一律以契约为准：
  - `category_id` → `content_category_id`
  - `distilled_keyword` → `distill_keywords`
  - `image_gallery_id` → `image_category_id`
  - `article_rule_id` → `content_rule_id`
  - 大任务状态用契约 `pending`（非 dev 文档 `queued`）；重试端点用契约 `/retry`（非 dev 文档 `/retry-failed`）
- 写作规范下拉按 `creation_type` 过滤：内容创作指令取 `article_creation`，标题创作指令取 `title_creation`（取值对齐 TASK-0302）

## 实测

- `npm install`（本 worktree 新建 node_modules，成功，165 包）
- `npm run build`（`tsc -b` 类型检查 + vite 生产构建，3122 modules transformed）通过，退出码 0；仅有既有的 chunk >500kB 体积告警（非错误，历史任务一致）

## 备注 / 遗留

- ⚠️ 契约**未提供** `/api/writing-tasks/{id}/articles` 嵌套端点（dev 文档有、契约无）。详情页小任务列表改用 `GET /api/articles?writing_task_id={id}`，并**假设**后端 article 列表支持 `writing_task_id` 过滤参数（契约未文档化查询参数）。后端 TASK-0307/0308 就绪后需确认该过滤参数命名一致
- ⚠️ 契约 `writing_task` 对象未含进度计数字段（仅 `article_result_status`）。当前「生成进度」统计由前端按小任务列表派生；若后端后续在大任务返回体加入 total/pending/running/success/failed 计数，可切换为直接展示
- 不开发文章编辑页（按任务边界）；详情页小任务标题点击跳 `/workspace/articles/:id/edit`，该路由当前仍为占位页，待文章模块任务实现
- 后端写作任务接口（创建/详情/取消/重试）若尚未就绪，本页面按契约封装，接口可用后可直接联调
