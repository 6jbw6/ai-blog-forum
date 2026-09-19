import { request } from './request'

export interface DashboardStats {
  metrics: {
    total_articles: number
    published_articles: number
    draft_articles: number
    total_views: number
    total_likes: number
    total_comments: number
    rag_chunks_indexed: number
  }
  category_distribution: Array<{ name: string; value: number }>
  top_articles: Array<{
    id: number
    title: string
    slug: string
    views: number
    likes: number
  }>
}

export const getDashboardStatsApi = () => {
  return request<DashboardStats>({
    url: '/statistics/dashboard',
    method: 'GET'
  })
}
