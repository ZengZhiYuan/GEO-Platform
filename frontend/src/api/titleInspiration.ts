/**
 * 标题灵感 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  TitleInspirationCreatePayload,
  TitleInspirationItem,
  TitleInspirationListQuery,
  TitleInspirationUpdatePayload,
} from '@/types/material'

/** 分页查询标题灵感。 */
export function listTitleInspirations(params: TitleInspirationListQuery) {
  return request<PageData<TitleInspirationItem>>({
    url: '/title-inspirations',
    method: 'get',
    params,
  })
}

/** 获取标题灵感详情。 */
export function getTitleInspiration(id: number) {
  return request<TitleInspirationItem>({
    url: `/title-inspirations/${id}`,
    method: 'get',
  })
}

/** 新增标题灵感。 */
export function createTitleInspiration(payload: TitleInspirationCreatePayload) {
  return request<TitleInspirationItem>({
    url: '/title-inspirations',
    method: 'post',
    data: payload,
  })
}

/** 更新标题灵感。 */
export function updateTitleInspiration(
  id: number,
  payload: TitleInspirationUpdatePayload,
) {
  return request<TitleInspirationItem>({
    url: `/title-inspirations/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 删除标题灵感。 */
export function deleteTitleInspiration(id: number) {
  return request<void>({ url: `/title-inspirations/${id}`, method: 'delete' })
}
