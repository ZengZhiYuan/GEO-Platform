/**
 * 关键词库 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  KeywordCreatePayload,
  KeywordItem,
  KeywordListQuery,
  KeywordUpdatePayload,
} from '@/types/material'

/** 分页查询关键词。 */
export function listKeywords(params: KeywordListQuery) {
  return request<PageData<KeywordItem>>({
    url: '/keywords',
    method: 'get',
    params,
  })
}

/** 获取关键词详情。 */
export function getKeyword(id: number) {
  return request<KeywordItem>({ url: `/keywords/${id}`, method: 'get' })
}

/** 新增关键词。 */
export function createKeyword(payload: KeywordCreatePayload) {
  return request<KeywordItem>({ url: '/keywords', method: 'post', data: payload })
}

/** 更新关键词。 */
export function updateKeyword(id: number, payload: KeywordUpdatePayload) {
  return request<KeywordItem>({
    url: `/keywords/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 删除关键词。 */
export function deleteKeyword(id: number) {
  return request<void>({ url: `/keywords/${id}`, method: 'delete' })
}
