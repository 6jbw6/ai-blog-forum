import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { User } from '@/types'
import { loginApi, getMeApi } from '@/api/auth'
import { ElMessage } from 'element-plus'

export const useUserStore = defineStore('user', () => {
  const token = ref<string>(localStorage.getItem('access_token') || '')
  
  const storedUser = localStorage.getItem('user_info')
  const user = ref<User | null>(storedUser ? JSON.parse(storedUser) : null)

  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  async function login(credentials: { username: string; password: string }) {
    const res = await loginApi(credentials)
    token.value = res.access_token
    user.value = res.user

    localStorage.setItem('access_token', res.access_token)
    localStorage.setItem('user_info', JSON.stringify(res.user))
    ElMessage.success(`欢迎回来，${res.user.nickname}！`)
    return res.user
  }

  async function fetchProfile() {
    if (!token.value) return null
    try {
      const u = await getMeApi()
      user.value = u
      localStorage.setItem('user_info', JSON.stringify(u))
      return u
    } catch (e) {
      logout()
      return null
    }
  }

  function setUser(newUser: User) {
    user.value = newUser
    localStorage.setItem('user_info', JSON.stringify(newUser))
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_info')
    ElMessage.info('已安全退出登录')
  }

  return {
    token,
    user,
    isLoggedIn,
    isAdmin,
    login,
    fetchProfile,
    setUser,
    logout
  }
})
