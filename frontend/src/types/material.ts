/**
 * 素材中心业务类型。
 *
 * 字段命名严格对齐 docs/api-contract.md（snake_case，前后端一致）。
 * 当前包含「关键词库」（TASK-0202）与「标题灵感」（TASK-0204）相关类型。
 */

/** 关键词优化状态枚举值。 */
export type OptimizeStatus = 'not_optimized' | 'optimizing' | 'optimized'

/** 关键词库列表/详情记录（对应 GET /api/keywords 返回项）。 */
export interface KeywordItem {
  id: number
  main_word: string
  question_count: number
  optimize_status: OptimizeStatus
  created_at: string
  updated_at: string
}

/** 关键词库列表查询参数：分页 + 主词搜索 + 优化状态筛选。 */
export interface KeywordListQuery {
  page?: number
  page_size?: number
  main_word?: string
  optimize_status?: OptimizeStatus
}

/** 新增关键词请求体（POST /api/keywords）。 */
export interface KeywordCreatePayload {
  main_word: string
  optimize_status: OptimizeStatus
}

/** 更新关键词请求体（PUT /api/keywords/{id}），字段同新增。 */
export type KeywordUpdatePayload = KeywordCreatePayload

/**
 * 标题灵感收录状态枚举值。
 * 字段名以 docs/api-contract.md 为准（collect_status）；契约未列举取值，
 * 沿用 docs/claude-code-dev.md 设计：not_included（未收录）/ included（已收录）。
 */
export type CollectStatus = 'not_included' | 'included'

/** 标题灵感列表/详情记录（对应 GET /api/title-inspirations 返回项）。 */
export interface TitleInspirationItem {
  id: number
  main_word: string
  question: string
  collect_status: CollectStatus
  created_at: string
  updated_at: string
}

/** 标题灵感列表查询参数：分页 + 主词筛选 + 收录状态筛选。 */
export interface TitleInspirationListQuery {
  page?: number
  page_size?: number
  main_word?: string
  collect_status?: CollectStatus
}

/** 新增标题灵感请求体（POST /api/title-inspirations）。 */
export interface TitleInspirationCreatePayload {
  main_word: string
  question: string
  collect_status: CollectStatus
}

/** 更新标题灵感请求体（PUT /api/title-inspirations/{id}），字段同新增。 */
export type TitleInspirationUpdatePayload = TitleInspirationCreatePayload
