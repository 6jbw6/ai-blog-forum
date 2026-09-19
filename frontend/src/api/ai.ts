import { request } from './request'
import type { AiChatMessageItem, AiSummaryResponse, CitationItem, LlmConfig, SemanticSearchResultItem } from '@/types'

export const generateSummaryApi = (data: { content: string; title?: string }) => {
  return request<AiSummaryResponse>({
    url: '/ai/summary',
    method: 'POST',
    data
  })
}

export const semanticSearchApi = (data: { query: string; top_k?: number }) => {
  return request<SemanticSearchResultItem[]>({
    url: '/ai/semantic-search',
    method: 'POST',
    data
  })
}

export const reindexAllApi = () => {
  return request<{ articles_indexed: number; total_chunks: number }>({
    url: '/ai/reindex-all',
    method: 'POST'
  })
}

export const getAiConfigApi = () => {
  return request<LlmConfig>({
    url: '/ai/config',
    method: 'GET'
  })
}

export const updateAiConfigApi = (data: LlmConfig) => {
  return request<null>({
    url: '/ai/config',
    method: 'PUT',
    data
  })
}

export const fetchModelsApi = (data: { base_url: string; api_key?: string }) => {
  return request<string[]>({
    url: '/ai/models',
    method: 'POST',
    data
  })
}

export const getRecommendedQuestionsApi = (limit: number = 8, refresh: boolean = false) => {
  return request<string[]>({
    url: '/ai/recommended-questions',
    method: 'GET',
    params: { limit, refresh }
  })
}

export const getHotKeywordsApi = (limit: number = 6) => {
  return request<string[]>({
    url: '/ai/hot-keywords',
    method: 'GET',
    params: { limit }
  })
}

export const getChatHistoryApi = (limit: number = 10) => {
  return request<AiChatMessageItem[]>({
    url: '/ai/history',
    method: 'GET',
    params: { limit }
  })
}

export const clearChatHistoryApi = () => {
  return request<null>({
    url: '/ai/history',
    method: 'DELETE'
  })
}

/**
 * 前端原生 SSE 流式读取器 (用于 AI 智能体 / RAG 知识库问答)
 */
export async function streamRagChat(
  question: string,
  history: Array<{ role: string; content: string }>,
  onToken: (token: string) => void,
  onCitations: (citations: CitationItem[]) => void,
  onDone: () => void,
  onError: (err: any) => void
) {
  try {
    const headers: Record<string, string> = {
      'Content-Type': 'application/json'
    }
    const token = localStorage.getItem('access_token')
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    const response = await fetch('/api/v1/ai/ask', {
      method: 'POST',
      headers,
      body: JSON.stringify({ question, history })
    })

    if (!response.ok) {
      throw new Error(`SSE 连接失败 HTTP ${response.status}`)
    }

    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('浏览器无法创建 ReadableStream reader')
    }

    const decoder = new TextDecoder('utf-8')
    let buffer = ''

    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n\n')
      buffer = lines.pop() || ''

      for (const block of lines) {
        for (const line of block.split('\n')) {
          if (line.startsWith('data: ')) {
            const jsonStr = line.slice(6).trim()
            try {
              const data = JSON.parse(jsonStr)
              if (data.type === 'token') {
                onToken(data.content)
              } else if (data.type === 'citations') {
                onCitations(data.citations)
              } else if (data.type === 'done') {
                onDone()
                return
              }
            } catch (e) {
              // 忽略个别未完全接收的包
            }
          }
        }
      }
    }
    onDone()
  } catch (err) {
    onError(err)
  }
}
