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
          <router-link to="/categories" class="nav-item">技术标签</router-link>
        </nav>
      </div>

      <!-- 中间区域：胶囊搜索框（自适应拉伸，填满技术标签右侧至AI智能体左侧的全部空间） -->
      <div class="nav-center-group">
        <div class="nav-search-capsule" @click="aiChatStore.openSearch()">
          <el-icon class="search-icon"><Search /></el-icon>
          <span class="search-placeholder">搜索博文与知识库切片...</span>
        </div>
      </div>

      <!-- 右侧区域：快捷功能 + 控制台直连 + 用户态 -->
      <div class="nav-right-group">
        <!-- 快捷功能文本链接（极客控制台风格） -->
        <div class="quick-links">
          <button class="nav-action-link btn-ai-link" @click="aiChatStore.openChat()">
            <span class="pulse-dot"></span>
            <span>AI 智能体</span>
          </button>

          <router-link v-if="userStore.isAdmin" to="/admin/dashboard" class="nav-action-link">
            控制台
          </router-link>
        </div>

        <!-- 用户认证与头像徽章（右侧圆形状态徽标） -->
        <div class="nav-user-area">
          <template v-if="userStore.isLoggedIn">
            <el-dropdown trigger="click">
              <div class="user-avatar-pill">
                <el-avatar :size="28" :src="userStore.user?.avatar || '/user-avatar.svg'" />
                <span class="user-name">{{ userStore.user?.username || userStore.user?.nickname }}</span>
              </div>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item @click="profileModalRef?.open()">
                    <el-icon><User /></el-icon> 个人资料
                  </el-dropdown-item>
                  <el-dropdown-item @click="favoritesModalRef?.open()">
                    <el-icon><Star /></el-icon> 我的收藏
                  </el-dropdown-item>
                  <el-dropdown-item @click="likesModalRef?.open()">
                    <el-icon><Pointer /></el-icon> 我的点赞
                  </el-dropdown-item>
                  <el-dropdown-item @click="articlesModalRef?.open()">
                    <el-icon><Document /></el-icon> 我的创作
                  </el-dropdown-item>
                  <el-dropdown-item @click="notificationsModalRef?.open()">
                    <el-icon><Bell /></el-icon>
                    <span>消息提醒</span>
                    <el-badge v-if="unreadCount > 0" :value="unreadCount" :max="99" class="dropdown-badge" />
                  </el-dropdown-item>
                  <el-dropdown-item @click="$router.push('/admin/article/new')">
                    <el-icon><EditPen /></el-icon> 发布博文 (AI写作)
                  </el-dropdown-item>
                  <el-dropdown-item v-if="userStore.isAdmin" divided @click="$router.push('/admin/dashboard')">
                    <el-icon><DataAnalysis /></el-icon> 运营看板
                  </el-dropdown-item>
                  <el-dropdown-item divided @click="userStore.logout()">
                    退出登录
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

    <!-- 个人资料弹窗 -->
    <UserProfileModal ref="profileModalRef" />
    <!-- 个人收藏弹窗 -->
    <UserFavoritesModal ref="favoritesModalRef" />
    <!-- 我的点赞弹窗 -->
    <UserLikesModal ref="likesModalRef" />
    <!-- 我的创作弹窗 -->
    <UserArticlesModal ref="articlesModalRef" />
    <!-- 消息回复提醒弹窗 -->
    <UserNotificationsModal ref="notificationsModalRef" @updated="refreshUnreadCount" />
  </header>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Search, DataAnalysis, EditPen, User, Star, Pointer, Document, Bell } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAiChatStore } from '@/stores/aiChat'
import { getUnreadNotificationCountApi } from '@/api/notification'
import UserProfileModal from '@/components/UserProfileModal.vue'
import UserFavoritesModal from '@/components/UserFavoritesModal.vue'
import UserLikesModal from '@/components/UserLikesModal.vue'
import UserArticlesModal from '@/components/UserArticlesModal.vue'
import UserNotificationsModal from '@/components/UserNotificationsModal.vue'

const userStore = useUserStore()
const aiChatStore = useAiChatStore()
const profileModalRef = ref<InstanceType<typeof UserProfileModal> | null>(null)
const favoritesModalRef = ref<InstanceType<typeof UserFavoritesModal> | null>(null)
const likesModalRef = ref<InstanceType<typeof UserLikesModal> | null>(null)
const articlesModalRef = ref<InstanceType<typeof UserArticlesModal> | null>(null)
const notificationsModalRef = ref<InstanceType<typeof UserNotificationsModal> | null>(null)

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

// 快捷键 Ctrl+K 打开语义搜索
const handleKeyDown = (e: KeyboardEvent) => {
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    aiChatStore.openSearch()
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
  cursor: pointer;
  transition: all 0.2s ease;
}

.nav-search-capsule:hover {
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
}

.search-placeholder {
  font-size: 0.84rem;
  color: #a1a1aa;
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
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
}

.user-avatar-pill:hover {
  border-color: #10b981;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
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

.dropdown-badge {
  margin-left: 8px;
}
</style>
