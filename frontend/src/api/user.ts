import { request } from './request'
import type { UserSearchItem, UserProfileItem } from '@/types'

/** 门户搜索页：按用户名/昵称模糊搜索用户（游客可访问） */
export const searchUsersApi = (q: string, limit: number = 8) => {
  return request<UserSearchItem[]>({
    url: '/users/search',
    method: 'GET',
    params: { q, limit }
  })
}

/** 个人主页：获取用户公开资料（昵称/签名/头像/博文数） */
export const getUserProfileApi = (userId: number) => {
  return request<UserProfileItem>({
    url: `/users/${userId}/profile`,
    method: 'GET'
  })
}
