import { request } from './request'
import type { ArticleDetail, ArticleListItem, PageResult } from '@/types'

export const getArticlesApi = (params: {
  page?: number
  size?: number
  keyword?: string
  tag_id?: number
  author_id?: number
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
  is_private?: boolean
  is_manual_top?: boolean
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
  is_private: boolean
  is_manual_top: boolean
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

export interface LikedArticleItem extends ArticleListItem {
  liked_at: string
}

export const getMyLikedArticlesApi = () => {
  return request<LikedArticleItem[]>({
    url: '/articles/user/my-likes',
    method: 'GET'
  })
}

export const getMyCreatedArticlesApi = () => {
  return request<ArticleListItem[]>({
    url: '/articles/user/my-created',
    method: 'GET'
  })
}
