# TASK-0208 品牌知识库前端页面

- 分支：feat/fe-brand-knowledge
- 范围：仅改动 frontend/（+ 本分片）；未触碰 backend/；未开发其他页面；未改动既有接口字段名
- 状态：已完成

## 变更要点

- 修改 `frontend/src/types/material.ts`：新增 `BrandKnowledgeItem` / `BrandKnowledgeListQuery` / `BrandKnowledgeCreatePayload` / `BrandKnowledgeUpdatePayload`，字段严格对齐 api-contract.md（id/knowledge_name/company_name/company_short_name/creation_direction/copywriting_type/product_service/product_features/created_at/updated_at）
- 新增 `frontend/src/api/brandKnowledge.ts`：listBrandKnowledges / getBrandKnowledge / createBrandKnowledge / updateBrandKnowledge / deleteBrandKnowledge（GET|POST `/api/brand-knowledges`、GET|PUT|DELETE `/api/brand-knowledges/{id}`）
- 新增 `frontend/src/pages/material/brand-knowledge/BrandKnowledgeFormFields.tsx`：新增/编辑共用的 7 个表单字段；长文本 `creation_direction` / `product_service` / `product_features` 使用 TextArea（autoSize + showCount），`knowledge_name` / `company_name` 必填校验
- 新增 `frontend/src/pages/material/brand-knowledge/payload.ts`：`normalizeBrandKnowledgePayload`（必填 trim 保留、可选字段 trim 后空串则不下发）
- 新增 `frontend/src/pages/material/brand-knowledge/BrandKnowledgeFormDrawer.tsx`：新增表单 Drawer（字段多用抽屉承载，提交 loading、取消返回）
- 新增 `frontend/src/pages/material/brand-knowledge/index.tsx`：列表页（页面标题、知识库名/公司名双条件搜索、新增按钮、表格、分页、详情查看（只读 Drawer + Descriptions）、编辑跳转、删除二次确认、loading、empty、错误 Alert+重试、成功/失败提示）
- 新增 `frontend/src/pages/material/brand-knowledge/edit.tsx`：编辑页（`/:id/edit`，进入 GET 回填 → PUT 保存 → 返回列表；非法 id 兜底、详情加载 Spin、加载失败 Alert+重试、保存 loading、取消返回）
- 修改 `frontend/src/router/index.tsx`：`/material/brand-knowledge` 由占位页替换为 BrandKnowledgePage，并新增 `/material/brand-knowledge/:id/edit` → BrandKnowledgeEditPage

## 页面与路由

- 列表页：`/material/brand-knowledge`（左侧菜单「素材中心 / 品牌知识库」可访问）
- 编辑页：`/material/brand-knowledge/:id/edit`
- 新增：列表页「新增知识库」打开 Drawer 表单（无独立 create 路由，遵循任务给定的两条路径）
- 详情查看：列表页点击知识库名称或「详情」打开只读 Drawer

## 契约一致性

- 路径采用契约复数资源 `/api/brand-knowledges`（注意带 `s`）。
- 创作方向字段名采用契约 **`creation_direction`**（非 dev 文档 6.5 的 `writing_direction`）。
- 契约未包含 dev 文档的 `target_users` / `brand_tone` / `forbidden_words` / `extra_info`，依据「api-contract.md 为唯一权威源」决策**不引入**这些字段。
- 必填字段（knowledge_name / company_name）依据 dev 文档 8.7 的 NOT NULL 约束设为前端必填，其余为选填。

## 实测

- `npm install` 成功（165 包）
- `npm run build`（tsc -b 类型检查 + vite 生产构建，3111 modules）通过；仅有既有的「chunk > 500kB」体积告警（与历史任务一致，非本任务引入）

## 备注 / 遗留

- 后端品牌知识库接口（建议任务号 TASK-0207）尚未开发，本页面按契约封装，待后端就绪后可直接联调。
- 列表查询参数携带 `knowledge_name` / `company_name`，需后端支持对应模糊筛选（与既有素材模块筛选风格一致）。
