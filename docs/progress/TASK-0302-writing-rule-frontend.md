# TASK-0302 写作规范前端页面

- 分支：feat/fe-writing-rule
- 范围：仅改动 frontend/；未触碰 backend/；未开发其他页面；未改动既有接口字段名
- 状态：已完成

## 变更要点

- 新增 `frontend/src/types/workspace.ts`：写作工作台业务类型首个文件。`CreationType`（article_creation / title_creation / traffic_replication）、`WritingRuleItem`（id / rule_name / creation_type / instruction_content / created_at / updated_at）、`WritingRuleListQuery`（page / page_size / rule_name / creation_type）、`WritingRuleCreatePayload`、`WritingRuleUpdatePayload`（同新增）
- 修改 `frontend/src/types/index.ts`：新增 `export * from './workspace'`
- 修改 `frontend/src/utils/enums.ts`：新增 `CreationTypeOptions`（文章创作 / 标题创作 / 流量复刻）、`CreationTypeColorMap`、`getCreationTypeLabel`
- 新增 `frontend/src/api/writingRule.ts`：listWritingRules / getWritingRule / createWritingRule / updateWritingRule / deleteWritingRule（GET|POST `/api/writing-rules`、GET|PUT|DELETE `/api/writing-rules/{id}`）
- 新增 `frontend/src/pages/workspace/writing-rule/index.tsx`：写作规范列表页（页面标题、指令名称搜索、**按创作类型筛选**、新增按钮、表格、创作类型 Tag、指令内容两行省略+tooltip、分页、编辑、删除二次确认、loading、empty、错误 Alert+重试、成功/失败提示）
- 新增 `frontend/src/pages/workspace/writing-rule/WritingRuleFormModal.tsx`：新增/编辑指令弹窗（指令名称必填+长度校验、创作类型必选、**instruction_content 使用 Input.TextArea 长文本编辑**（autoSize 8~18 行 + showCount + maxLength 10000）、提交 loading、取消返回）
- 修改 `frontend/src/router/index.tsx`：`workspace/writing-rules` 由占位页替换为 `WritingRulePage`

## 契约一致性

- 字段/路径严格对齐 `docs/api-contract.md`（唯一权威源）：
  - 指令内容字段名采用契约 **`instruction_content`**（**非** dev 文档 §6.6 的 `rule_content`）
  - 创作类型枚举采用契约 **`article_creation` / `title_creation` / `traffic_replication`**（**非** dev 文档的 `article` / `title`）
  - 路径前缀 `/api`（非 `/api/v1`），与既有模块一致
- 页面路由 `/workspace/writing-rules` 对齐 `docs/frontend-pages.md`

## 实测

- `npm install` 成功（本 worktree 首次安装，2 moderate 漏洞为既有依赖状况）
- `npm run build`（`tsc -b` 类型检查 + `vite build` 生产构建，3114 modules transformed）通过，0 报错

## 备注 / 遗留

- 后端 TASK-0301 写作规范接口尚未开发，页面按契约封装，待后端接口就绪后可直接联调
- 按 CLAUDE.md 第 9 条与 `docs/progress/README.md` 分片约定，本任务在 `docs/progress/` 写分片，**未直接编辑 `docs/progress.md`**（该文件由主控终端合并后串行汇总）
- 下一步建议：**TASK-0301（写作规范后端接口）** 补齐前后端闭环；或 TASK-0303/0304（内容分类前后端）
