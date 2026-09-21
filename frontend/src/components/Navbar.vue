<template>
  <header class="navbar-wrapper">
    <div class="navbar-container">
      <!-- 左侧区域：品牌 Logo + 主导航条目（极简现代居左排列布局） -->
      <div class="nav-left-group">
        <router-link to="/" class="brand-logo">
          <img src="/logo.png" alt="AI博客论坛 Logo" class="logo-img" />
          <span class="logo-text">AI博客论坛</span>
        </router-link>

        <nav class="nav-links">
          <router-link to="/" class="nav-item">首页</router-link>
          <router-link to="/tags" class="nav-item">技术标签</router-link>
        </nav>
      </div>

      <!-- 中间区域：胶囊搜索框（输入后回车跳转语义搜索结果页） -->
      <div class="nav-center-group">
        <div class="nav-search-capsule">
          <el-icon class="search-icon"><Search /></el-icon>
          <input
            v-model="searchKeyword"
            class="search-input"
            type="text"
            placeholder="搜索"
            @keydown.enter="goToSearch"
          />
        </div>
      </div>

      <!-- 右侧区域：快捷功能 + 控制台直连 + 用户态 -->
      <div class="nav-right-group">
        <!-- 快捷功能文本链接（极客控制台风格） -->
        <div class="quick-links">
          <button class="nav-action-link btn-ai-link" @click="openAiChat">
            <span class="pulse-dot"></span>
            <span>AI 智能体</span>
          </button>

          <router-link v-if="userStore.isAdmin" to="/admin/dashboard" class="nav-action-link">
            控制台
          </router-link>
        </div>

        <!-- 用户状态区：头像下拉菜单（个人主页 / 个人资料 / 写作 / 退出登录） -->
        <div class="nav-user-area">
          <template v-if="userStore.isLoggedIn">
            <el-dropdown trigger="click" @command="handleUserCommand">
              <button class="user-avatar-pill" title="用户菜单">
                <el-avatar :size="28" :src="userStore.user?.avatar || '/user-avatar.svg'" />
                <span class="user-name">{{ userStore.user?.username || userStore.user?.nickname }}</span>
                <span v-if="unreadCount > 0" class="avatar-unread-dot"></span>
              </button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="profile">
                    <el-icon><User /></el-icon> 个人主页
                  </el-dropdown-item>
                  <el-dropdown-item command="settings">
                    <el-icon><Setting /></el-icon> 个人资料
                  </el-dropdown-item>
                  <el-dropdown-item command="write">
                    <el-icon><EditPen /></el-icon> 写作
                  </el-dropdown-item>
                  <el-dropdown-item command="logout" divided>
                    <el-icon><SwitchButton /></el-icon> 退出登录
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>
          </template>

          <template v-else>
            <router-link to="/login" class="btn-login-pill">
              登录 / 注册
            </router-link>
          </template>
        </div>
      </div>
    </div>

    <!-- 个人资料编辑弹窗 -->
    <UserProfileModal ref="profileModalRef" />
  </header>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, User, Setting, EditPen, SwitchButton } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAiChatStore } from '@/stores/aiChat'
import { getUnreadNotificationCountApi } from '@/api/notification'
import UserProfileModal from '@/components/UserProfileModal.vue'

const userStore = useUserStore()
const aiChatStore = useAiChatStore()
const router = useRouter()
const route = useRoute()

// 顶部胶囊搜索框：输入后回车跳转语义搜索结果页
const searchKeyword = ref('')
const goToSearch = () => {
  const q = searchKeyword.value.trim()
  router.push(q ? { path: '/search', query: { q } } : { path: '/search' })
}

// 搜索词回显：进入搜索页（含新标签页直达 /search?q=）时把查询词填回搜索框，
// 离开搜索页或查询词变化时同步，保证「搜过的词不丢」
watch(() => route.query.q, (q) => {
  searchKeyword.value = ((q as string) || '').trim()
}, { immediate: true })

// AI 智能体答疑需登录：游客点击引导登录
const openAiChat = () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('登录后即可使用 AI 智能体答疑')
    router.push('/login')
    return
  }
  aiChatStore.openChat()
}
// 头像下拉菜单命令分发：个人主页 / 个人资料 / 写作 / 退出登录
const profileModalRef = ref<InstanceType<typeof UserProfileModal> | null>(null)

const handleUserCommand = (command: string | number | object) => {
  switch (command) {
    case 'profile':
      if (userStore.user?.id) {
        router.push(`/user/${userStore.user.id}`)
      }
      break
    case 'settings':
      profileModalRef.value?.open()
      break
    case 'write':
      router.push('/write')
      break
    case 'logout':
      userStore.logout()
      router.push('/')
      break
  }
}

const unreadCount = ref(0)

const refreshUnreadCount = async () => {
  if (!userStore.isLoggedIn) return
  try {
    const count = await getUnreadNotificationCountApi()
    unreadCount.value = count
  } catch {
    // ignore
  }
}

// 快捷键 Ctrl+K 聚焦顶部搜索框
const handleKeyDown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    const input = document.querySelector<HTMLInputElement>('.nav-search-capsule .search-input')
    input?.focus()
  }
}

onMounted(() => {
  refreshUnreadCount()
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeyDown)
})
</script>

<style scoped>
.navbar-wrapper {
  position: sticky;
  top: 0;
  z-index: 1000;
  background: rgba(255, 255, 255, 0.95);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border-bottom: 1px solid #e4e4e7;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.02);
}

.navbar-container {
  max-width: 1520px;
  margin: 0 auto;
  padding: 0 2rem;
  height: 58px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

/* 左侧 Logo + 菜单链接群组 */
.nav-left-group {
  display: flex;
  align-items: center;
  gap: 2.25rem;
  flex-shrink: 0;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
}

.logo-img {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: block;
  object-fit: cover;
}

.logo-text {
  font-size: 1.25rem;
  font-weight: 800;
  color: #18181b;
  letter-spacing: -0.4px;
}

.nav-links {
  display: flex;
  align-items: center;
  gap: 1.75rem;
}

.nav-item {
  color: #27272a;
  text-decoration: none;
  font-size: 0.92rem;
  font-weight: 500;
  cursor: pointer;
  transition: color 0.15s ease;
}

.nav-item:hover,
.nav-item.router-link-active {
  color: #059669;
}

/* 中间区域：拉伸搜索栏（连接技术标签右侧与AI智能体左侧） */
.nav-center-group {
  flex: 1;
  display: flex;
  align-items: center;
  margin: 0 1.75rem;
  min-width: 0;
}

/* 胶囊搜索栏 (自适应 100% 填满中间区域) */
.nav-search-capsule {
  width: 100%;
  height: 38px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 9999px;
  padding: 0 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s ease;
}

.nav-search-capsule:hover,
.nav-search-capsule:focus-within {
  border-color: #18181b;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

/* 右侧动作栏 */
.nav-right-group {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  flex-shrink: 0;
}

.search-icon {
  color: #71717a;
  font-size: 15px;
  flex-shrink: 0;
}

/* 胶囊内搜索输入框（无边框透明，融入胶囊背景） */
.search-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 0.84rem;
  color: #18181b;
}

.search-input::placeholder {
  color: #a1a1aa;
}

/* 快捷链接 */
.quick-links {
  display: flex;
  align-items: center;
  gap: 1rem;
}

.nav-action-link {
  background: transparent;
  border: none;
  font-size: 0.88rem;
  font-weight: 500;
  color: #27272a;
  text-decoration: none;
  cursor: pointer;
  padding: 5px 8px;
  border-radius: 6px;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: 6px;
}

.nav-action-link:hover {
  color: #059669;
}

.pulse-dot {
  width: 7px;
  height: 7px;
  background: #10b981;
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
  animation: pulse 1.6s infinite;
}

@keyframes pulse {
  0% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7); }
  70% { transform: scale(1); box-shadow: 0 0 0 6px rgba(16, 185, 129, 0); }
  100% { transform: scale(0.95); box-shadow: 0 0 0 0 rgba(16, 185, 129, 0); }
}

/* 用户状态区 */
.nav-user-area {
  display: flex;
  align-items: center;
}

.user-avatar-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 3px 10px 3px 4px;
  border-radius: 9999px;
  border: 1px solid #e4e4e7;
  background: #ffffff;
  transition: all 0.2s ease;
  position: relative;
  font-family: inherit;
}

.user-avatar-pill:hover {
  border-color: #10b981;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

/* 未读消息红点（头像右上角） */
.avatar-unread-dot {
  position: absolute;
  top: -2px;
  right: 2px;
  min-width: 16px;
  height: 16px;
  padding: 0 4px;
  border-radius: 9999px;
  background: #ef4444;
  color: #ffffff;
  font-size: 0.62rem;
  font-weight: 700;
  line-height: 16px;
  text-align: center;
}

.user-name {
  font-size: 0.85rem;
  font-weight: 600;
  color: #18181b;
}

.btn-login-pill {
  padding: 5px 14px;
  font-size: 0.85rem;
  font-weight: 600;
  color: #18181b;
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  border-radius: 9999px;
  text-decoration: none;
  transition: all 0.2s ease;
}

.btn-login-pill:hover {
  background: #18181b;
  color: #ffffff;
  border-color: #18181b;
}

@media (max-width: 900px) {
  .nav-center-group {
    display: none;
  }

  .nav-left-group {
    gap: 1rem;
  }

  .nav-links {
    gap: 1rem;
  }
}
</style>
