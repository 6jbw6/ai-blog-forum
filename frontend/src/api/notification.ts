import { request } from './request'

export interface NotificationItem {
  id: number
  user_id: number
  /** article_comment: 评论了你的博文 | reply: 回复了你的评论 */
  kind: 'article_comment' | 'reply'
  sender_name: string
  sender_avatar?: string
  article_id: number
  article_title: string
  article_slug: string
  reply_content: string
  /** 回复型提醒带被回复原文；评论博文型为空串；源评论被删除时为「该评论已删除」 */
  parent_content: string
  is_read: boolean
  created_at: string
}

/** SSE 推送负载：未读数 + 新提醒（已读回执时 notification 为 null） */
export interface NotificationStreamPayload {
  count: number
  notification: NotificationItem | null
}

export const getMyNotificationsApi = () => {
  return request<NotificationItem[]>({
    url: '/notifications/my',
    method: 'GET'
  })
}

export const getUnreadNotificationCountApi = () => {
  return request<number>({
    url: '/notifications/unread-count',
    method: 'GET'
  })
}

export const markAllNotificationsAsReadApi = () => {
  return request<null>({
    url: '/notifications/read-all',
    method: 'PUT'
  })
}

export const markNotificationAsReadApi = (id: number) => {
  return request<null>({
    url: `/notifications/read/${id}`,
    method: 'PUT'
  })
}

/**
 * 站内提醒实时推送（SSE 长连接）
 *
 * 与 AI 对话同一套流式写法：fetch + ReadableStream + Authorization 头
 * （不用原生 EventSource，因为它无法携带鉴权头）。断线后指数退避自动重连，
 * 返回的函数用于主动关闭（组件卸载 / 退出登录）。
 */
export const openNotificationStream = (handlers: {
  onPayload: (payload: NotificationStreamPayload) => void
  onOpen?: () => void
  onClose?: () => void
}) => {
  const controller = new AbortController()
  let closed = false
  let retry = 0

  const run = async () => {
    while (!closed) {
      try {
        const token = localStorage.getItem('access_token')
        if (!token) throw new Error('未登录，跳过提醒推送')
        const response = await fetch('/api/v1/notifications/stream', {
          headers: { Authorization: `Bearer ${token}`, Accept: 'text/event-stream' },
          signal: controller.signal
        })
        if (!response.ok || !response.body) {
          throw new Error(`提醒推送连接失败 HTTP ${response.status}`)
        }

        retry = 0
        handlers.onOpen?.()

        const reader = response.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''

        while (!closed) {
          const { done, value } = await reader.read()
          if (done) break
          buffer += decoder.decode(value, { stream: true })
          const blocks = buffer.split('\n\n')
          buffer = blocks.pop() || ''
          for (const block of blocks) {
            const dataLine = block.split('\n').find(line => line.startsWith('data:'))
            if (!dataLine) continue // 「: keep-alive」心跳帧，仅用于保活
            try {
              handlers.onPayload(JSON.parse(dataLine.slice(5).trim()))
            } catch {
              // 忽略无法解析的帧
            }
          }
        }
      } catch {
        // 网络中断 / 后端重启：落到下面的退避重连
      }
      handlers.onClose?.()
      if (closed) break
      retry = Math.min(retry + 1, 5)
      await new Promise(resolve => setTimeout(resolve, Math.min(1000 * 2 ** retry, 20000)))
    }
  }

  run()
  return () => {
    closed = true
    controller.abort()
  }
}
