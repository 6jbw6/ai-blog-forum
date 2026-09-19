import { request } from './request'

export interface FavoriteArticleItem {
  id: number
  title: string
  slug: string
  summary?: string
  category_name?: string
  cover_image?: string
  views_count: number
  likes_count: number
  created_at: string
  favorited_at: string
}

export const toggleFavoriteApi = (articleId: number) => {
  return request<{ is_favorited: boolean; favorites_count: number }>({
    url: `/favorites/toggle/${articleId}`,
    method: 'POST'
  })
}

export const getMyFavoritesApi = () => {
  return request<FavoriteArticleItem[]>({
    url: '/favorites/my',
    method: 'GET'
  })
}
