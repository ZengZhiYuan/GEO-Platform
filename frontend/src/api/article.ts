/**
 * 文章清单 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  ArticleItem,
  ArticleListQuery,
  ArticleStatusUpdatePayload,
  ArticleUpdatePayload,
} from '@/types/workspace'

/** 分页查询文章。 */
export function listArticles(params: ArticleListQuery) {
  return request<PageData<ArticleItem>>({
    url: '/articles',
    method: 'get',
    params,
  })
}

/** 获取文章详情。 */
export function getArticle(id: number) {
  return request<ArticleItem>({
    url: `/articles/${id}`,
    method: 'get',
  })
}

/** 更新文章标题、封面图、正文与状态。 */
export function updateArticle(id: number, payload: ArticleUpdatePayload) {
  return request<ArticleItem>({
    url: `/articles/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 切换文章状态（待审核 / 正常 / 禁用）。 */
export function updateArticleStatus(
  id: number,
  payload: ArticleStatusUpdatePayload,
) {
  return request<ArticleItem>({
    url: `/articles/${id}/status`,
    method: 'post',
    data: payload,
  })
}
