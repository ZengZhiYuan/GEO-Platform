/**
 * 写作任务 API 封装。
 * 路径与字段严格对齐 docs/api-contract.md（Base URL = /api）。
 */
import { request } from '@/api/client'
import type { PageData } from '@/types/common'
import type {
  WritingTaskCreatePayload,
  WritingTaskItem,
  WritingTaskListQuery,
} from '@/types/workspace'

/** 分页查询写作任务（大任务列表）。 */
export function listWritingTasks(params: WritingTaskListQuery) {
  return request<PageData<WritingTaskItem>>({
    url: '/writing-tasks',
    method: 'get',
    params,
  })
}

/** 获取写作任务详情。 */
export function getWritingTask(id: number) {
  return request<WritingTaskItem>({
    url: `/writing-tasks/${id}`,
    method: 'get',
  })
}

/** 创建写作大任务（后端据此拆分并投递小任务）。 */
export function createWritingTask(payload: WritingTaskCreatePayload) {
  return request<WritingTaskItem>({
    url: '/writing-tasks',
    method: 'post',
    data: payload,
  })
}

/** 取消未完成任务。 */
export function cancelWritingTask(id: number) {
  return request<WritingTaskItem>({
    url: `/writing-tasks/${id}/cancel`,
    method: 'post',
  })
}

/** 重试失败任务（重新投递失败小任务）。 */
export function retryWritingTask(id: number) {
  return request<WritingTaskItem>({
    url: `/writing-tasks/${id}/retry`,
    method: 'post',
  })
}
