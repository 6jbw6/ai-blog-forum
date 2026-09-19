import { request } from './request'
import type { ArticleDetail, ArticleListItem, PageResult } from '@/types'

export const getArticlesApi = (params: {
  page?: number
  size?: number
  keyword?: string
  category_id?: number
  tag_id?: number
  published_only?: boolean
}) => {
  return request<PageResult<ArticleListItem>>({
    url: '/articles',
    method: 'GET',
    params
  })
}

export const getArticleDetailApi = (idOrSlug: string | number) => {
  return request<ArticleDetail>({
    url: `/articles/${idOrSlug}`,
    method: 'GET'
  })
}

export const createArticleApi = (data: {
  title: string
  slug: string
  summary?: string
  content: string
  cover_image?: string
  is_published?: boolean
  is_top?: boolean
  category_id?: number
  tag_ids?: number[]
}) => {
  return request<ArticleDetail>({
    url: '/articles',
    method: 'POST',
    data
  })
}

export const updateArticleApi = (id: number, data: Partial<{
  title: string
  slug: string
  summary: string
  content: string
  cover_image: string
  is_published: boolean
  is_top: boolean
  category_id: number
  tag_ids: number[]
}>) => {
  return request<ArticleDetail>({
    url: `/articles/${id}`,
    method: 'PUT',
    data
  })
}

export const deleteArticleApi = (id: number) => {
  return request<null>({
    url: `/articles/${id}`,
    method: 'DELETE'
  })
}

export const likeArticleApi = (id: number) => {
  return request<{ liked: boolean; likes_count: number }>({
    url: `/articles/${id}/like`,
    method: 'POST'
  })
}

export const getArticleInteractionApi = (id: number) => {
  return request<{ is_liked: boolean; is_favorited: boolean; likes_count: number }>({
    url: `/articles/${id}/interaction`,
    method: 'GET'
  })
}

export const reindexArticleApi = (id: number) => {
  return request<number>({
    url: `/articles/${id}/reindex`,
    method: 'POST'
  })
}

export const getMyLikedArticlesApi = () => {
  return request<Array<{
    id: number
    title: string
    slug: string
    summary?: string
    category_name?: string
    views_count: number
    likes_count: number
    created_at: string
    liked_at: string
  }>>({
    url: '/articles/user/my-likes',
    method: 'GET'
  })
}

export const getMyCreatedArticlesApi = () => {
  return request<Array<{
    id: number
    title: string
    slug: string
    summary?: string
    category_name?: string
    is_published: boolean
    views_count: number
    likes_count: number
    created_at: string
    vector_status: string
  }>>({
    url: '/articles/user/my-created',
    method: 'GET'
  })
}
