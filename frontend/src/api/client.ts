import axios, { type AxiosInstance } from 'axios'
import { message } from 'antd'

/**
 * 统一 Axios 客户端。
 * 后端统一响应结构：{ code, message, data }。
 * 拦截器在 code !== 0 时弹出错误提示并 reject，业务层只需处理 data。
 */
export interface ApiResponse<T = unknown> {
  code: number
  message: string
  data: T
}

const baseURL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api'

export const http: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
})

http.interceptors.response.use(
  (response) => {
    const body = response.data as ApiResponse
    if (body && typeof body.code === 'number' && body.code !== 0) {
      message.error(body.message || '请求失败')
      return Promise.reject(body)
    }
    return response
  },
  (error) => {
    const msg =
      error?.response?.data?.message || error?.message || '网络异常，请稍后重试'
    message.error(msg)
    return Promise.reject(error)
  },
)

/** 发起请求并直接返回 data 字段。 */
export async function request<T = unknown>(
  ...args: Parameters<AxiosInstance['request']>
): Promise<T> {
  const response = await http.request<ApiResponse<T>>(...args)
  return response.data.data
}
