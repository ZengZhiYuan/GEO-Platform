/**
 * 状态枚举字典统一管理。
 * 所有下拉/标签的状态选项集中在此，避免散落在页面或接口代码里。
 */
import type { OptimizeStatus } from '@/types/material'

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
