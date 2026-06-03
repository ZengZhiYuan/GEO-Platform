/**
 * 画像图库分类 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  ImageCategoryCreatePayload,
  ImageCategoryItem,
  ImageCategoryListQuery,
  ImageCategoryUpdatePayload,
} from '@/types/material'

/** 分页查询图库分类。 */
export function listImageCategories(params: ImageCategoryListQuery) {
  return request<PageData<ImageCategoryItem>>({
    url: '/image-categories',
    method: 'get',
    params,
  })
}

/** 获取图库分类详情。 */
export function getImageCategory(id: number) {
  return request<ImageCategoryItem>({
    url: `/image-categories/${id}`,
    method: 'get',
  })
}

/** 新增图库分类。 */
export function createImageCategory(payload: ImageCategoryCreatePayload) {
  return request<ImageCategoryItem>({
    url: '/image-categories',
    method: 'post',
    data: payload,
  })
}

/** 更新图库分类。 */
export function updateImageCategory(
  id: number,
  payload: ImageCategoryUpdatePayload,
) {
  return request<ImageCategoryItem>({
    url: `/image-categories/${id}`,
    method: 'put',
    data: payload,
  })
}

/** 删除图库分类。 */
export function deleteImageCategory(id: number) {
  return request<void>({ url: `/image-categories/${id}`, method: 'delete' })
}
