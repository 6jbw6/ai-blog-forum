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

      <!-- 中间区域：胶囊搜索框（热搜词实时映射 placeholder + 聚焦显示搜索记录/热搜） -->
      <div class="nav-center-group">
        <div class="nav-search-capsule" :class="{ 'is-focused': searchFocused }">
          <el-icon class="search-icon"><Search /></el-icon>
          <input
            v-model="searchKeyword"
            class="search-input"
            type="text"
            :placeholder="searchPlaceholder"
            spellcheck="false"
            autocomplete="off"
            autocorrect="off"
            autocapitalize="off"
            @keydown.enter="goToSearch"
            @focus="searchFocused = true"
            @blur="handleSearchBlur"
          />
          <button class="search-btn" title="搜索" @click="goToSearch">搜索</button>

          <!-- 聚焦下拉：搜索记录（超量折叠、可单条删除）+ 一行热搜词 -->
          <div v-if="searchFocused" class="search-dropdown">
            <div v-if="searchHistory.length > 0" class="dropdown-section">
              <div class="section-head">
                <span class="section-title">搜索记录</span>
                <button class="link-btn" @mousedown.prevent @click="clearSearchHistory">清空</button>
              </div>
              <div class="history-list">
                <div
                  v-for="h in visibleHistory"
                  :key="h"
                  class="history-item"
                  @mousedown.prevent
                  @click="selectKeyword(h)"
                >
                  <span class="history-icon">🕘</span>
                  <span class="history-text">{{ h }}</span>
                  <button
                    class="history-remove"
                    title="删除该记录"
                    @mousedown.prevent
                    @click.stop="removeHistoryItem(h)"
                  >
                    ×
                  </button>
                </div>
              </div>
              <button
                v-if="searchHistory.length > HISTORY_PREVIEW"
                class="link-btn expand-btn"
                @mousedown.prevent
                @click="historyExpanded = !historyExpanded"
              >
                {{ historyExpanded ? '收起' : `展开全部 (${searchHistory.length})` }}
              </button>
            </div>

            <div v-if="hotKeywords.length > 0" class="dropdown-section">
              <div class="section-head">
                <span class="section-title">热搜</span>
              </div>
              <div class="hot-row">
                <button
                  v-for="k in hotKeywords"
                  :key="k"
                  class="hot-chip"
                  @mousedown.prevent
                  @click="selectKeyword(k)"
                >
                  {{ k }}
                </button>
              </div>
            </div>
          </div>
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Search, User, Setting, EditPen, SwitchButton } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { useAiChatStore } from '@/stores/aiChat'
import { getUnreadNotificationCountApi } from '@/api/notification'
import { getHotKeywordsApi } from '@/api/ai'
import UserProfileModal from '@/components/UserProfileModal.vue'

const userStore = useUserStore()
const aiChatStore = useAiChatStore()
const router = useRouter()
const route = useRoute()

// 顶部胶囊搜索框：空输入时 placeholder 实时轮播热搜词，杜绝空搜索
const searchKeyword = ref('')

// ---------- 热搜词 ----------
const hotKeywords = ref<string[]>([])
const placeholderIdx = ref(0)

// 未输入时 placeholder 直接映射当前热搜词（实时变换）
const searchPlaceholder = computed(() =>
  searchKeyword.value.trim() === ''
    ? (hotKeywords.value[placeholderIdx.value] || '搜索')
    : '搜索'
)

let placeholderTimer: number | undefined

const rotatePlaceholder = () => {
  if (hotKeywords.value.length > 1) {
    placeholderIdx.value = (placeholderIdx.value + 1) % hotKeywords.value.length
  }
}

const loadHotKeywords = async () => {
  try {
    const list = await getHotKeywordsApi(10)
    // 热搜来自真实搜索日志，可能混入长问句；只保留短词条用于输入框映射与热搜 chips
    hotKeywords.value = list.filter(k => k.length <= 10).slice(0, 6)
  } catch {
    hotKeywords.value = []
  }
}

// ---------- 搜索记录（localStorage 持久化，超量折叠） ----------
const HISTORY_KEY = 'search_history'
const HISTORY_PREVIEW = 6
const HISTORY_MAX = 20

const searchHistory = ref<string[]>([])
const historyExpanded = ref(false)

try {
  const rawHistory = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]')
  searchHistory.value = Array.isArray(rawHistory) ? rawHistory.slice(0, HISTORY_MAX) : []
} catch {
  searchHistory.value = []
}

const visibleHistory = computed(() =>
  historyExpanded.value ? searchHistory.value : searchHistory.value.slice(0, HISTORY_PREVIEW)
)

const pushSearchHistory = (q: string) => {
  searchHistory.value = [q, ...searchHistory.value.filter(item => item !== q)].slice(0, HISTORY_MAX)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(searchHistory.value))
}

const clearSearchHistory = () => {
  searchHistory.value = []
  historyExpanded.value = false
  localStorage.removeItem(HISTORY_KEY)
}

const removeHistoryItem = (q: string) => {
  searchHistory.value = searchHistory.value.filter(item => item !== q)
  localStorage.setItem(HISTORY_KEY, JSON.stringify(searchHistory.value))
}

// ---------- 聚焦面板 ----------
const searchFocused = ref(false)

const handleSearchBlur = () => {
  // 延迟关闭，保证下拉项的 click 先于失焦生效
  window.setTimeout(() => {
    searchFocused.value = false
  }, 150)
}

const selectKeyword = (k: string) => {
  searchKeyword.value = k
  searchFocused.value = false
  goToSearch()
}

const goToSearch = () => {
  let q = searchKeyword.value.trim()
  // 空输入：直接采用输入框内当前映射的热搜词，杜绝空搜索
  if (!q) {
    q = hotKeywords.value[placeholderIdx.value] || ''
  }
  if (!q) {
    ElMessage.warning('请输入搜索关键词')
    return
  }
  pushSearchHistory(q)
  searchFocused.value = false
  router.push({ path: '/search', query: { q } })
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
  loadHotKeywords()
  // 热搜词实时映射：每 3.5 秒轮换输入框内的 placeholder
  placeholderTimer = window.setInterval(rotatePlaceholder, 3500)
  window.addEventListener('keydown', handleKeyDown)
})

onUnmounted(() => {
  if (placeholderTimer) window.clearInterval(placeholderTimer)
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
  position: relative;
  width: 100%;
  height: 38px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 9999px;
  padding: 0 0 0 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s ease;
}

/* 搜索按钮：撑满高度贴合胶囊右端弧边，左侧以分隔线与输入区分隔 */
.search-btn {
  margin-left: 8px;
  height: 100%;
  padding: 0 16px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #18181b;
  background: #f4f4f5;
  border: none;
  border-left: 1px solid #e4e4e7;
  border-radius: 0 9999px 9999px 0;
  cursor: pointer;
  flex-shrink: 0;
  font-family: inherit;
  transition: all 0.2s ease;
}

/* 不使用黑色：悬停改为白底 + 深色描边文字 */
.search-btn:hover {
  background: #ffffff;
  color: #18181b;
  border-left-color: #d4d4d8;
}

/* ---------- 聚焦下拉：搜索记录 + 热搜词 ---------- */
.search-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  left: 0;
  right: 0;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 14px;
  box-shadow: 0 12px 28px rgba(24, 24, 27, 0.08);
  padding: 12px 14px;
  display: flex;
  flex-direction: column;
  gap: 12px;
  z-index: 1200;
}

.dropdown-section {
  display: flex;
  flex-direction: column;
}

.section-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.section-title {
  font-size: 0.74rem;
  font-weight: 600;
  color: #a1a1aa;
}

.link-btn {
  background: none;
  border: none;
  font-size: 0.72rem;
  color: #71717a;
  cursor: pointer;
  padding: 0;
  font-family: inherit;
}

.link-btn:hover {
  color: #18181b;
}

.expand-btn {
  align-self: flex-start;
  margin-top: 4px;
  color: #059669;
}

.history-list {
  display: flex;
  flex-direction: column;
}

.history-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  background: none;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  color: #3f3f46;
}

.history-item:hover {
  background: #f4f4f5;
}

.history-item .history-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.history-icon {
  font-size: 0.75rem;
  opacity: 0.6;
}

.history-remove {
  margin-left: auto;
  width: 20px;
  height: 20px;
  line-height: 18px;
  text-align: center;
  border: none;
  border-radius: 9999px;
  background: none;
  color: #a1a1aa;
  font-size: 0.9rem;
  cursor: pointer;
  flex-shrink: 0;
  padding: 0;
  font-family: inherit;
  transition: all 0.15s ease;
}

.history-remove:hover {
  background: #e4e4e7;
  color: #dc2626;
}

/* 热搜词单行排列，超出横向滚动 */
.hot-row {
  display: flex;
  flex-wrap: nowrap;
  gap: 8px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.hot-chip {
  padding: 4px 12px;
  border-radius: 9999px;
  border: 1px solid #e4e4e7;
  background: #fafafa;
  font-size: 0.78rem;
  color: #18181b;
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  font-family: inherit;
  transition: all 0.2s ease;
}

.hot-chip:hover {
  background: #ffffff;
  border-color: #18181b;
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
