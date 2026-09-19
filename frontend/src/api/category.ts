import { request } from './request'
import type { Category } from '@/types'

export const getCategoriesApi = () => {
  return request<Category[]>({
    url: '/categories',
    method: 'GET'
  })
}

export const createCategoryApi = (data: { name: string; slug: string; description?: string; sort_order?: number }) => {
  return request<Category>({
    url: '/categories',
    method: 'POST',
    data
  })
}

export const updateCategoryApi = (id: number, data: Partial<Category>) => {
  return request<Category>({
    url: `/categories/${id}`,
    method: 'PUT',
    data
  })
}

export const deleteCategoryApi = (id: number) => {
  return request<null>({
    url: `/categories/${id}`,
    method: 'DELETE'
  })
}
