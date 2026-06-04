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
