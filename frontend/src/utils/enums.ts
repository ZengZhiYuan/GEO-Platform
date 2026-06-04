/**
 * 状态枚举字典统一管理。
 * 所有下拉/标签的状态选项集中在此，避免散落在页面或接口代码里。
 */
import type { CollectStatus, OptimizeStatus } from '@/types/material'
import type {
  ArticleEditableStatus,
  ArticleStatus,
  CreationType,
} from '@/types/workspace'

export interface SelectOption<T extends string = string> {
  label: string
  value: T
}

/** 关键词优化状态选项。 */
export const OptimizeStatusOptions: SelectOption<OptimizeStatus>[] = [
  { label: '未优化', value: 'not_optimized' },
  { label: '优化中', value: 'optimizing' },
  { label: '已优化', value: 'optimized' },
]

/** 优化状态对应的 antd Tag 颜色。 */
export const OptimizeStatusColorMap: Record<OptimizeStatus, string> = {
  not_optimized: 'default',
  optimizing: 'processing',
  optimized: 'success',
}

/** 根据枚举值取中文文案，未命中时回退原值。 */
export function getOptimizeStatusLabel(value: string): string {
  return OptimizeStatusOptions.find((o) => o.value === value)?.label ?? value
}

/** 标题灵感收录状态选项。 */
export const CollectStatusOptions: SelectOption<CollectStatus>[] = [
  { label: '未收录', value: 'not_included' },
  { label: '已收录', value: 'included' },
]

/** 收录状态对应的 antd Tag 颜色。 */
export const CollectStatusColorMap: Record<CollectStatus, string> = {
  not_included: 'default',
  included: 'success',
}

/** 根据枚举值取中文文案，未命中时回退原值。 */
export function getCollectStatusLabel(value: string): string {
  return CollectStatusOptions.find((o) => o.value === value)?.label ?? value
}

/** 写作规范创作类型选项。 */
export const CreationTypeOptions: SelectOption<CreationType>[] = [
  { label: '文章创作', value: 'article_creation' },
  { label: '标题创作', value: 'title_creation' },
  { label: '流量复刻', value: 'traffic_replication' },
]

/** 创作类型对应的 antd Tag 颜色。 */
export const CreationTypeColorMap: Record<CreationType, string> = {
  article_creation: 'blue',
  title_creation: 'green',
  traffic_replication: 'orange',
}

/** 根据枚举值取中文文案，未命中时回退原值。 */
export function getCreationTypeLabel(value: string): string {
  return CreationTypeOptions.find((o) => o.value === value)?.label ?? value
}

/** 文章状态全量选项（含系统态 generating / failed，用于列表筛选与展示）。 */
export const ArticleStatusOptions: SelectOption<ArticleStatus>[] = [
  { label: '生成中', value: 'generating' },
  { label: '待审核', value: 'pending_review' },
  { label: '正常', value: 'normal' },
  { label: '禁用', value: 'disabled' },
  { label: '生成失败', value: 'failed' },
]

/**
 * 人工可切换的文章状态选项（待审核 / 正常 / 禁用）。
 * 用于编辑页状态选择与列表行内状态切换，不含生成流程产生的系统态。
 */
export const ArticleEditableStatusOptions: SelectOption<ArticleEditableStatus>[] =
  [
    { label: '待审核', value: 'pending_review' },
    { label: '正常', value: 'normal' },
    { label: '禁用', value: 'disabled' },
  ]

/** 文章状态对应的 antd Tag 颜色。 */
export const ArticleStatusColorMap: Record<ArticleStatus, string> = {
  generating: 'processing',
  pending_review: 'warning',
  normal: 'success',
  disabled: 'default',
  failed: 'error',
}

/** 根据枚举值取中文文案，未命中时回退原值。 */
export function getArticleStatusLabel(value: string): string {
  return ArticleStatusOptions.find((o) => o.value === value)?.label ?? value
}
