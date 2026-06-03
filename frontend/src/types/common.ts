/**
 * 基础通用 API 类型。
 *
 * 仅包含与后端「统一响应 / 分页」契约对应的基础类型，
 * 不包含任何具体业务实体类型（业务类型在后续对应任务中再补充）。
 * 字段命名与 docs/api-contract.md 保持一致（snake_case）。
 */

// 统一响应结构的权威定义在 @/api/client，这里转出以便业务类型集中从 types 引入。
export type { ApiResponse } from '@/api/client'

/** 分页请求参数。 */
export interface PageParams {
  page?: number
  page_size?: number
}

/** 分页响应数据（对应统一响应中的 data 字段）。 */
export interface PageData<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/** 通用列表查询参数：分页参数 + 任意筛选条件。 */
export type ListQuery<T = Record<string, unknown>> = PageParams & T
