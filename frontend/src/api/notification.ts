import { request } from './request'

export interface NotificationItem {
  id: number
  user_id: number
  sender_name: string
  sender_avatar?: string
  article_id: number
  article_title: string
  article_slug: string
  reply_content: string
  parent_content: string
  is_read: boolean
  created_at: string
}

export const getMyNotificationsApi = () => {
  return request<NotificationItem[]>({
    url: '/notifications/my',
    method: 'GET'
  })
}

export const getUnreadNotificationCountApi = () => {
  return request<number>({
    url: '/notifications/unread-count',
    method: 'GET'
  })
}

export const markAllNotificationsAsReadApi = () => {
  return request<null>({
    url: '/notifications/read-all',
    method: 'PUT'
  })
}

export const markNotificationAsReadApi = (id: number) => {
  return request<null>({
    url: `/notifications/read/${id}`,
    method: 'PUT'
  })
}
