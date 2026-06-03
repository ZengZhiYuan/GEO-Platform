import type { BrandKnowledgeCreatePayload } from '@/types/material'

/**
 * 规范化品牌知识库表单值：
 * - 必填字段（knowledge_name / company_name）trim 后保留；
 * - 可选字段 trim 后若为空串则不下发（避免把空字符串写入后端）。
 */
export function normalizeBrandKnowledgePayload(
  values: BrandKnowledgeCreatePayload,
): BrandKnowledgeCreatePayload {
  const trimOptional = (v?: string | null) => {
    const t = (v ?? '').trim()
    return t === '' ? undefined : t
  }

  const payload: BrandKnowledgeCreatePayload = {
    knowledge_name: (values.knowledge_name ?? '').trim(),
    company_name: (values.company_name ?? '').trim(),
  }

  const companyShortName = trimOptional(values.company_short_name)
  if (companyShortName !== undefined) payload.company_short_name = companyShortName

  const copywritingType = trimOptional(values.copywriting_type)
  if (copywritingType !== undefined) payload.copywriting_type = copywritingType

  const creationDirection = trimOptional(values.creation_direction)
  if (creationDirection !== undefined) payload.creation_direction = creationDirection

  const productService = trimOptional(values.product_service)
  if (productService !== undefined) payload.product_service = productService

  const productFeatures = trimOptional(values.product_features)
  if (productFeatures !== undefined) payload.product_features = productFeatures

  return payload
}
