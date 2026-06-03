/**
 * 画像图库图片资源 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 * 列表通过 category_id 过滤出指定分类下的图片。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  ImageAssetCreatePayload,
  ImageAssetItem,
  ImageAssetListQuery,
} from '@/types/material'

/** 分页查询图片资源（按 category_id 过滤所属分类）。 */
export function listImageAssets(params: ImageAssetListQuery) {
  return request<PageData<ImageAssetItem>>({
    url: '/image-assets',
    method: 'get',
    params,
  })
}

/** 新增图片资源（录入图片 URL）。 */
export function createImageAsset(payload: ImageAssetCreatePayload) {
  return request<ImageAssetItem>({
    url: '/image-assets',
    method: 'post',
    data: payload,
  })
}

/** 删除图片资源。 */
export function deleteImageAsset(id: number) {
  return request<void>({ url: `/image-assets/${id}`, method: 'delete' })
}
