/**
 * 内容分类 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  ContentCategoryCreatePayload,
  ContentCategoryItem,
  ContentCategoryListQuery,
  ContentCategoryUpdatePayload,
} from '@/types/workspace'

/** 分页查询内容分类。 */
export function listContentCategories(params: ContentCategoryListQuery) {
  return request<PageData<ContentCategoryItem>>({
    url: '/content-categories',
    method: 'get',
    params,
  })
}

/** 获取内容分类详情。 */
export function getContentCategory(id: number) {
  return request<ContentCategoryItem>({
    url: `/content-categories/${id}`,
    method: 'get',
  })
}

/** 新增内容分类。 */
export function createContentCategory(payload: ContentCategoryCreatePayload) {
  return request<ContentCategoryItem>({
    url: '/content-categories',
    method: 'post',
    data: payload,
  })
}

/** 更新内容分类。 */
export function updateContentCategory(
  id: number,
  payload: ContentCategoryUpdatePayload,
) {
  return request<ContentCategoryItem>({
    url: `/content-categories/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 删除内容分类。 */
export function deleteContentCategory(id: number) {
  return request<void>({ url: `/content-categories/${id}`, method: 'delete' })
}
