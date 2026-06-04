/**
 * 写作规范 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  WritingRuleCreatePayload,
  WritingRuleItem,
  WritingRuleListQuery,
  WritingRuleUpdatePayload,
} from '@/types/workspace'

/** 分页查询写作规范。 */
export function listWritingRules(params: WritingRuleListQuery) {
  return request<PageData<WritingRuleItem>>({
    url: '/writing-rules',
    method: 'get',
    params,
  })
}

/** 获取写作规范详情。 */
export function getWritingRule(id: number) {
  return request<WritingRuleItem>({ url: `/writing-rules/${id}`, method: 'get' })
}

/** 新增写作规范。 */
export function createWritingRule(payload: WritingRuleCreatePayload) {
  return request<WritingRuleItem>({
    url: '/writing-rules',
    method: 'post',
    data: payload,
  })
}

/** 更新写作规范。 */
export function updateWritingRule(id: number, payload: WritingRuleUpdatePayload) {
  return request<WritingRuleItem>({
    url: `/writing-rules/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 删除写作规范。 */
export function deleteWritingRule(id: number) {
  return request<void>({ url: `/writing-rules/${id}`, method: 'delete' })
}
