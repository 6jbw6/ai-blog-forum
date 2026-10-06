import { request } from './request'
import type { AdminUserItem } from '@/types'

export type { AdminUserItem }

export const searchUsersAdminApi = (keyword?: string) => {
  return request<AdminUserItem[]>({
    url: '/admin/users',
    method: 'GET',
    params: keyword ? { keyword } : {}
  })
}

export const banUserApi = (id: number, reason: string) => {
  return request<AdminUserItem>({
    url: `/admin/users/${id}/ban`,
    method: 'POST',
    data: { reason }
  })
}

export const unbanUserApi = (id: number, reason: string) => {
  return request<AdminUserItem>({
    url: `/admin/users/${id}/unban`,
    method: 'POST',
    data: { reason }
  })
}
