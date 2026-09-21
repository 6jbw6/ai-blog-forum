import { request } from './request'
import type { ArticleListItem } from '@/types'

export interface FavoriteArticleItem extends ArticleListItem {
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
