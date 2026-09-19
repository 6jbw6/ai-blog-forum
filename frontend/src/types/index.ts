export interface Result<T = any> {
  code: number
  message: string
  data: T
}

export interface PageResult<T = any> {
  list: T[]
  total: number
  page: number
  size: number
  total_pages: number
}

export interface User {
  id: number
  username: string
  email: string
  nickname: string
  avatar?: string
  bio?: string
  role: 'admin' | 'reader'
  is_active: boolean
  created_at: string
}

export interface TokenOut {
  access_token: string
  token_type: string
  user: User
}

export interface Category {
  id: number
  name: string
  slug: string
  description?: string
  sort_order: number
  article_count?: number
  created_at: string
}

export interface Tag {
  id: number
  name: string
  slug: string
  color: string
  article_count?: number
  created_at: string
}

export interface ArticleListItem {
  id: number
  title: string
  slug: string
  summary?: string
  cover_image?: string
  is_published: boolean
  is_top: boolean
  views_count: number
  likes_count: number
  vector_status: 'unprocessed' | 'indexed' | 'failed'
  category?: Category
  tags: Tag[]
  author?: User
  created_at: string
  updated_at: string
}

export interface ArticleDetail extends ArticleListItem {
  content: string
}

export interface Comment {
  id: number
  article_id: number
  parent_id?: number
  user_name: string
  user_email: string
  user_avatar?: string
  content: string
  is_approved: boolean
  is_admin: boolean
  created_at: string
  replies?: Comment[]
}

export interface CitationItem {
  citation_index: number
  chunk_id: number
  article_id: number
  article_title: string
  article_slug: string
  similarity: number
  snippet: string
}

export interface SemanticSearchResultItem {
  article_id: number
  title: string
  slug: string
  summary?: string
  similarity: number
  matched_snippet: string
}

export interface AiSummaryResponse {
  summary: string
  suggested_tags: string[]
}

export interface LlmConfig {
  provider: string
  api_key?: string
  base_url?: string
  model?: string
  top_k: number
  similarity_threshold: number
}

export interface AiChatMessageItem {
  id: number
  role: 'user' | 'assistant'
  content: string
  citations?: CitationItem[]
  created_at?: string
}
