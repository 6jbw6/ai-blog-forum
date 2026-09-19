import axios, { type AxiosRequestConfig, type AxiosResponse } from 'axios'
import { ElMessage } from 'element-plus'
import type { Result } from '@/types'

const service = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器：注入 JWT Bearer Token
service.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器：统一根据企业 Result<T> 状态码解包
service.interceptors.response.use(
  (response: AxiosResponse<Result>) => {
    const res = response.data
    // 如果返回的不是业务包裹对象，直接返回
    if (res.code === undefined) {
      return response.data as any
    }

    // 成功业务码
    if (res.code === 200) {
      return res.data
    }

    // 业务逻辑错误
    ElMessage.error(res.message || '操作失败')

    if (res.code === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
      // 如果当前不是在前台首页，可以提示重新登录
    }

    return Promise.reject(new Error(res.message || 'Error'))
  },
  (error) => {
    const status = error.response?.status
    const msg = error.response?.data?.message || error.message || '网络连接异常'

    if (status === 401) {
      ElMessage.warning('登录已过期，请重新登录')
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_info')
    } else if (status === 403) {
      ElMessage.error('权限不足：该操作仅系统管理员可执行')
    } else {
      ElMessage.error(msg)
    }

    return Promise.reject(error)
  }
)

export function request<T = any>(config: AxiosRequestConfig): Promise<T> {
  return service(config) as unknown as Promise<T>
}

export default service
