import { request } from './request'
import type { Tag } from '@/types'

export const getTagsApi = () => {
  return request<Tag[]>({
    url: '/tags',
    method: 'GET'
  })
}

export const createTagApi = (data: { name: string; slug: string; color?: string }) => {
  return request<Tag>({
    url: '/tags',
    method: 'POST',
    data
  })
}

export const updateTagApi = (id: number, data: Partial<Tag>) => {
  return request<Tag>({
    url: `/tags/${id}`,
    method: 'PUT',
    data
  })
}

export const deleteTagApi = (id: number) => {
  return request<null>({
    url: `/tags/${id}`,
    method: 'DELETE'
  })
}
