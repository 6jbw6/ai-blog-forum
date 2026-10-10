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

export interface AuthorBrief {
  /** 文章作者公开信息（不含 email / is_active 等隐私字段） */
  id: number
  username: string
  nickname: string
  avatar?: string | null
  bio?: string
  role: string
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
  is_private: boolean
  is_top: boolean
  is_manual_top: boolean
  views_count: number
  likes_count: number
  vector_status: 'unprocessed' | 'indexed' | 'failed'
  tags: Tag[]
  // 作者公开信息：后端已改为不输出 email / is_active 的公开视角 schema
  author?: AuthorBrief
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
  user_id?: number | null
  user_name: string
  user_email: string
  user_avatar?: string
  content: string
  is_approved: boolean
  is_admin: boolean
  likes_count?: number
  is_liked?: boolean
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

export interface SemanticSearchResultItem extends ArticleListItem {
  article_id: number
  similarity: number
  matched_snippet: string
}

export interface UserSearchItem {
  id: number
  username: string
  nickname: string
  avatar?: string | null
  bio?: string
  article_count: number
  created_at?: string
}

export interface AdminUserItem {
  id: number
  username: string
  nickname: string
  email: string
  role: string
  is_active: boolean
  ban_reason?: string | null
  banned_at?: string | null
  created_at: string
}

export interface UserProfileItem {
  id: number
  username: string
  nickname: string
  avatar?: string | null
  bio?: string
  role: 'admin' | 'reader' | string
  article_count: number
  total_likes: number
  created_at: string
}

export interface MyCommentItem {
  id: number
  article_id: number
  article_title: string
  article_slug: string
  content: string
  is_approved: boolean
  created_at: string
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
