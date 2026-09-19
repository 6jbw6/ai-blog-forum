import { request } from './request'
import type { TokenOut, User } from '@/types'

export const loginApi = (data: { username: string; password: string }) => {
  return request<TokenOut>({
    url: '/auth/login',
    method: 'POST',
    data
  })
}

export const registerApi = (data: { username: string; password: string; email: string; nickname?: string; bio?: string }) => {
  return request<User>({
    url: '/auth/register',
    method: 'POST',
    data
  })
}

export const getMeApi = () => {
  return request<User>({
    url: '/auth/me',
    method: 'GET'
  })
}

export const updateProfileApi = (data: { username?: string; nickname?: string; avatar?: string; bio?: string; password?: string }) => {
  return request<User>({
    url: '/auth/me',
    method: 'PUT',
    data
  })
}

export const uploadAvatarApi = (file: File) => {
  const formData = new FormData()
  formData.append('file', file)
  return request<User>({
    url: '/auth/avatar',
    method: 'POST',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000
  })
}
