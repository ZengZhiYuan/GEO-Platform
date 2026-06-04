/**
 * 文章清单 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 *
 * 本任务（TASK-0306）仅实现列表查询，用于写作任务详情页展示小任务列表，
 * 不开发文章编辑相关接口与页面。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type { ArticleItem, ArticleListQuery } from '@/types/workspace'

/**
 * 分页查询文章（小任务）。
 * 注：api-contract.md 未文档化查询参数，此处沿用前端「按外键过滤」约定，
 * 通过 writing_task_id 拉取某写作任务下的小任务文章（待后端确认过滤参数）。
 */
export function listArticles(params: ArticleListQuery) {
  return request<PageData<ArticleItem>>({
    url: '/articles',
    method: 'get',
    params,
  })
}
