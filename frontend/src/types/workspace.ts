/**
 * 写作工作台业务类型。
 *
 * 字段命名严格对齐 docs/api-contract.md（snake_case，前后端一致）。
 * 当前包含「写作规范」（TASK-0302）相关类型。
 */

/**
 * 写作规范创作类型枚举值。
 * 取值以 docs/api-contract.md 为准：article_creation / title_creation /
 * traffic_replication（与 dev 文档草案 article / title 不一致时以契约为准）。
 */
export type CreationType =
  | 'article_creation'
  | 'title_creation'
  | 'traffic_replication'

/** 写作规范列表/详情记录（对应 GET /api/writing-rules 返回项）。 */
export interface WritingRuleItem {
  id: number
  rule_name: string
  creation_type: CreationType
  instruction_content: string
  created_at: string
  updated_at: string
}

/** 写作规范列表查询参数：分页 + 名称搜索 + 创作类型筛选。 */
export interface WritingRuleListQuery {
  page?: number
  page_size?: number
  rule_name?: string
  creation_type?: CreationType
}

/** 新增写作规范请求体（POST /api/writing-rules）。 */
export interface WritingRuleCreatePayload {
  rule_name: string
  creation_type: CreationType
  instruction_content: string
}

/** 更新写作规范请求体（PUT /api/writing-rules/{id}），字段同新增。 */
export type WritingRuleUpdatePayload = WritingRuleCreatePayload

/**
 * 内容分类列表/详情记录（对应 GET /api/content-categories 返回项）。
 * 字段对齐 docs/api-contract.md：group_name / article_count。
 * article_count 为只读统计字段（分类下文章数量，由后端维护），不进入表单。
 */
export interface ContentCategoryItem {
  id: number
  group_name: string
  article_count: number
  created_at: string
  updated_at: string
}

/** 内容分类列表查询参数：分页 + 分组名搜索。 */
export interface ContentCategoryListQuery {
  page?: number
  page_size?: number
  group_name?: string
}

/** 新增内容分类请求体（POST /api/content-categories）。 */
export interface ContentCategoryCreatePayload {
  group_name: string
}

/** 更新内容分类请求体（PUT /api/content-categories/{id}），字段同新增。 */
export type ContentCategoryUpdatePayload = ContentCategoryCreatePayload

/**
 * 文章状态枚举值（对应 GET/PUT /api/articles 的 status 字段）。
 * 取值以 docs/api-contract.md 为准：
 * generating（生成中）/ pending_review（待审核）/ normal（正常）/
 * disabled（禁用）/ failed（生成失败）。
 * 其中 generating / failed 由生成流程产生（只读展示），
 * 人工可切换的目标状态为 pending_review / normal / disabled。
 */
export type ArticleStatus =
  | 'generating'
  | 'pending_review'
  | 'normal'
  | 'disabled'
  | 'failed'

/** 人工可切换的文章状态（待审核 / 正常 / 禁用）。 */
export type ArticleEditableStatus = 'pending_review' | 'normal' | 'disabled'

/** 文章列表/详情记录（对应 GET /api/articles 返回项）。 */
export interface ArticleItem {
  id: number
  writing_task_id: number
  article_title: string
  cover_image_url: string | null
  status: ArticleStatus
  content: string | null
  error_message: string | null
  created_at: string
  updated_at: string
}

/** 文章列表查询参数：分页 + 标题搜索 + 状态筛选 + 按写作任务筛选。 */
export interface ArticleListQuery {
  page?: number
  page_size?: number
  article_title?: string
  status?: ArticleStatus
  writing_task_id?: number
}

/**
 * 更新文章请求体（PUT /api/articles/{id}）。
 * 支持编辑标题、封面图、正文与状态。
 */
export interface ArticleUpdatePayload {
  article_title: string
  cover_image_url?: string | null
  content?: string | null
  status: ArticleEditableStatus
}

/** 文章状态切换请求体（POST /api/articles/{id}/status）。 */
export interface ArticleStatusUpdatePayload {
  status: ArticleEditableStatus
}
