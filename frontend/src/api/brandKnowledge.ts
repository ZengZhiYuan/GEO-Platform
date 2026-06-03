/**
 * 品牌知识库 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api，资源为复数 brand-knowledges）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  BrandKnowledgeCreatePayload,
  BrandKnowledgeItem,
  BrandKnowledgeListQuery,
  BrandKnowledgeUpdatePayload,
} from '@/types/material'

/** 分页查询品牌知识库。 */
export function listBrandKnowledges(params: BrandKnowledgeListQuery) {
  return request<PageData<BrandKnowledgeItem>>({
    url: '/brand-knowledges',
    method: 'get',
    params,
  })
}

/** 获取品牌知识库详情。 */
export function getBrandKnowledge(id: number) {
  return request<BrandKnowledgeItem>({
    url: `/brand-knowledges/${id}`,
    method: 'get',
  })
}

/** 新增品牌知识库。 */
export function createBrandKnowledge(payload: BrandKnowledgeCreatePayload) {
  return request<BrandKnowledgeItem>({
    url: '/brand-knowledges',
    method: 'post',
    data: payload,
  })
}

/** 更新品牌知识库。 */
export function updateBrandKnowledge(
  id: number,
  payload: BrandKnowledgeUpdatePayload,
) {
  return request<BrandKnowledgeItem>({
    url: `/brand-knowledges/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 删除品牌知识库。 */
export function deleteBrandKnowledge(id: number) {
  return request<void>({ url: `/brand-knowledges/${id}`, method: 'delete' })
}
