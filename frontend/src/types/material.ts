/**
 * 素材中心业务类型。
 *
 * 字段命名严格对齐 docs/api-contract.md（snake_case，前后端一致）。
 * 本文件当前仅包含「关键词库」相关类型（TASK-0202）。
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
