import { request } from './request'
import type { Comment, MyCommentItem, PageResult } from '@/types'

export const getArticleCommentsApi = (articleId: number) => {
  return request<Comment[]>({
    url: `/comments/article/${articleId}`,
    method: 'GET'
  })
}

/** 个人主页「评论」维度：当前登录用户的评论时间线 (需登录) */
export const getMyCommentsApi = () => {
  return request<MyCommentItem[]>({
    url: '/comments/my',
    method: 'GET'
  })
}

export const postCommentApi = (data: {
  article_id: number
  parent_id?: number
  user_name: string
  user_email: string
  content: string
}) => {
  return request<Comment>({
    url: '/comments',
    method: 'POST',
    data
  })
}

export const getAdminCommentsApi = (params: { page: number; size: number }) => {
  return request<PageResult<Comment>>({
    url: '/comments/admin/list',
    method: 'GET',
    params
  })
}

export const toggleCommentApprovalApi = (id: number) => {
  return request<null>({
    url: `/comments/admin/${id}/approve`,
    method: 'PUT'
  })
}

export const deleteCommentApi = (id: number) => {
  return request<null>({
    url: `/comments/admin/${id}`,
    method: 'DELETE'
  })
}

/** 点赞/取消点赞评论，服务端维护计数并返回最新状态 */
export const likeCommentApi = (id: number) => {
  return request<{ liked: boolean; likes_count: number }>({
    url: `/comments/${id}/like`,
    method: 'POST'
  })
}

/** 作者本人修改评论内容 */
export const updateCommentApi = (id: number, content: string) => {
  return request<Comment>({
    url: `/comments/${id}`,
    method: 'PUT',
    data: { content }
  })
}

/** 作者本人或管理员删除评论，服务端级联清理其下整条回复线程 */
export const deleteMyCommentApi = (id: number) => {
  return request<null>({
    url: `/comments/${id}`,
    method: 'DELETE'
  })
}
