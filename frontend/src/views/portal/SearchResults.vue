<template>
  <div class="search-page">
    <Navbar />

    <main class="search-container">
      <!-- 工具栏：筛选 tabs + 统计 + 筛选按钮（排序第二行由筛选按钮掌控展开） -->
      <div class="toolbar-wrapper">
        <div class="results-toolbar">
          <div class="content-tabs">
            <button
              v-for="t in contentTabs"
              :key="t.key"
              class="content-tab"
              :class="{ active: contentType === t.key }"
              @click="contentType = t.key"
            >
              {{ t.label }}
            </button>
          </div>

          <div class="toolbar-right">
            <span v-if="searched && !loading" class="results-count">{{ countText }}</span>
            <button
              v-if="contentType !== 'users'"
              class="filter-toggle"
              :class="{ open: showFilter }"
              @click="showFilter = !showFilter"
            >
              筛选
              <el-icon class="filter-arrow"><ArrowDown /></el-icon>
            </button>
          </div>
        </div>

        <!-- 第二行：排序 tabs（点击「筛选」展开，默认综合；用户维度无排序意义） -->
        <div v-if="showFilter && contentType !== 'users'" class="sort-row">
          <div class="sort-tabs">
            <button
              v-for="opt in sortOptions"
              :key="opt.key"
              class="sort-tab"
              :class="{ active: sortKey === opt.key }"
              @click="sortKey = opt.key"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="loading" class="search-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <template v-else>
        <!-- 用户结果（全部 / 用户维度） -->
        <div v-if="contentType !== 'articles' && userResults.length > 0" class="user-results-list">
          <div class="section-label">用户</div>
          <div
            v-for="u in userResults"
            :key="u.id"
            class="user-item-card"
            @click="goUserProfile(u.id)"
          >
            <el-avatar :size="42" :src="u.avatar || '/user-avatar.svg'" />
            <div class="user-info">
              <div class="user-line1">
                <span class="user-nickname">{{ u.nickname }}</span>
                <span class="user-username">@{{ u.username }}</span>
              </div>
              <p class="user-bio">{{ u.bio || '这位用户还没有写下签名' }}</p>
            </div>
            <span class="user-articles-count">{{ u.article_count }} 篇博文</span>
          </div>
        </div>

        <!-- 博文结果列表（全部 / 博文维度） -->
        <div v-if="contentType !== 'users' && sortedResults.length > 0" class="search-results-list">
          <div v-if="contentType === 'all'" class="section-label">博文</div>
          <ArticleCard
            v-for="item in sortedResults"
            :key="item.article_id"
            :article="item"
            :similarity="item.similarity"
            clickable-card
            @open="selectArticle"
            @ask="askAiAboutArticle"
          />
        </div>

        <!-- 空态 -->
        <div v-if="searched && !hasAnyResult" class="search-empty">
          <el-empty description="未检索到相关博文或用户，换个提问方式试试吧~" />
        </div>
        <div v-if="!searched" class="search-empty">
          <el-empty description="在顶部搜索框输入问题，开始搜索" />
        </div>
      </template>
    </main>

    <AiChatDrawer />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AiChatDrawer from '@/components/AiChatDrawer.vue'
import ArticleCard from '@/components/ArticleCard.vue'
import { semanticSearchApi } from '@/api/ai'
import { searchUsersApi } from '@/api/user'
import { useUserStore } from '@/stores/user'
import { useAiChatStore } from '@/stores/aiChat'
import type { SemanticSearchResultItem, UserSearchItem } from '@/types'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const aiChatStore = useAiChatStore()

const loading = ref(false)
const searched = ref(false)
const results = ref<SemanticSearchResultItem[]>([])
const userResults = ref<UserSearchItem[]>([])

// 内容类型：全部=用户+博文聚合展示；博文/用户=单一维度
type ContentType = 'all' | 'articles' | 'users'
const contentType = ref<ContentType>('all')
const contentTabs: Array<{ key: ContentType; label: string }> = [
  { key: 'all', label: '全部' },
  { key: 'articles', label: '博文' },
  { key: 'users', label: '用户' }
]

// 博文排序：综合=相关度降序（后端默认序，默认选中）、最新=发布时间、热门=浏览量
type SortKey = 'relevance' | 'latest' | 'hot'
const sortKey = ref<SortKey>('relevance')
const sortOptions: Array<{ key: SortKey; label: string }> = [
  { key: 'relevance', label: '综合' },
  { key: 'latest', label: '最新' },
  { key: 'hot', label: '热门' }
]

// 排序第二行默认收起，点击「筛选」按钮展开/收起
const showFilter = ref(false)

const countText = computed(() => {
  if (contentType.value === 'users') return `用户 ${userResults.value.length} 个`
  if (contentType.value === 'articles') return `博文 ${results.value.length} 篇`
  return `博文 ${results.value.length} 篇 · 用户 ${userResults.value.length} 个`
})

const sortedResults = computed(() => {
  const list = [...results.value]
  if (sortKey.value === 'latest') {
    list.sort((a, b) => {
      const ta = new Date(a.created_at || 0).getTime()
      const tb = new Date(b.created_at || 0).getTime()
      return tb - ta
    })
  } else if (sortKey.value === 'hot') {
    list.sort((a, b) => {
      const diff = (b.views_count || 0) - (a.views_count || 0)
      return diff !== 0 ? diff : (b.likes_count || 0) - (a.likes_count || 0)
    })
  }
  return list
})

const hasAnyResult = computed(
  () => results.value.length > 0 || userResults.value.length > 0
)

const runSearch = async (q: string) => {
  loading.value = true
  searched.value = true
  try {
    // 用户检索独立降级：用户接口异常不影响博文结果展示
    const [arts, users] = await Promise.all([
      semanticSearchApi({ query: q, top_k: 8 }),
      searchUsersApi(q).catch(() => [] as UserSearchItem[])
    ])
    results.value = arts
    userResults.value = users
  } catch {
    results.value = []
    userResults.value = []
  } finally {
    loading.value = false
  }
}

const selectArticle = (slug: string) => {
  router.push(`/article/${slug}`)
}

const askAiAboutArticle = (title: string) => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('登录后即可向 AI 智能体提问')
    router.push('/login')
    return
  }
  aiChatStore.openChat(`请结合你的博客知识库，详细解读一下文章《${title}》的核心要点与工程价值`)
}

const goUserProfile = (id: number) => {
  router.push(`/user/${id}`)
}

// 从 URL query 读取检索词并自动检索（支持 Navbar 跳转与刷新还原）
onMounted(() => {
  const q = (route.query.q as string) || ''
  if (q) {
    runSearch(q)
  }
})

// 同一页面上 query 变化（如 Navbar 在搜索页再次搜索）时重新检索
watch(() => route.query.q, (q) => {
  const query = (q as string) || ''
  if (query) {
    runSearch(query)
  }
})
</script>

<style scoped>
.search-page {
  min-height: 100vh;
  background: transparent;
}

.search-container {
  /* 页面大小参照首页 .home-main-container */
  max-width: 1520px;
  margin: 0 auto;
  padding: 2.25rem 2.5rem 5rem 2.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

/* 工具栏：第一行筛选 tabs + 统计 + 筛选按钮；第二行排序（点击筛选展开）。
   两行共享一条底部分隔线，行间不再额外画线 */
.toolbar-wrapper {
  border-bottom: 1px solid #e4e4e7;
  margin-top: 0.25rem;
}

.results-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 0 4px 12px 4px;
}

.content-tabs {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.content-tab {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.92rem;
  font-weight: 500;
  color: #71717a;
  padding: 7px 18px;
  border-radius: 9999px;
  transition: all 0.15s ease;
}

.content-tab:hover {
  color: #18181b;
  background: #f4f4f5;
}

.content-tab.active {
  color: #ffffff;
  background: #18181b;
  font-weight: 600;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.results-count {
  font-size: 0.8rem;
  color: #a1a1aa;
}

/* 筛选按钮：点击展开/收起第二行排序 */
.filter-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.88rem;
  font-weight: 500;
  color: #52525b;
  padding: 6px 12px;
  border-radius: 8px;
  transition: all 0.15s ease;
}

.filter-toggle:hover {
  color: #18181b;
  background: #f4f4f5;
}

.filter-toggle.open {
  color: #18181b;
  font-weight: 600;
}

.filter-arrow {
  font-size: 14px;
  transition: transform 0.2s ease;
}

.filter-toggle.open .filter-arrow {
  transform: rotate(180deg);
}

/* 第二行：排序 tabs */
.sort-row {
  display: flex;
  align-items: center;
  padding: 0 4px 12px 4px;
}

.sort-tabs {
  display: flex;
  align-items: center;
  gap: 4px;
}

.sort-tab {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.9rem;
  font-weight: 500;
  color: #71717a;
  padding: 6px 14px;
  border-radius: 8px;
  position: relative;
  transition: color 0.15s ease;
}

.sort-tab:hover {
  color: #18181b;
}

.sort-tab.active {
  color: #18181b;
  font-weight: 700;
}

.sort-tab.active::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: -13px;
  height: 2px;
  background: #18181b;
  border-radius: 2px;
}

/* 分组小标签（全部维度下区分「用户」「博文」区块） */
.section-label {
  font-size: 0.78rem;
  font-weight: 600;
  color: #a1a1aa;
  letter-spacing: 0.05em;
  padding-left: 4px;
}

/* 用户结果卡片 */
.user-results-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 0.5rem;
}

.user-item-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.user-item-card:hover {
  border-color: #10b981;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.user-info {
  flex: 1;
  min-width: 0;
}

.user-line1 {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.user-nickname {
  font-size: 0.95rem;
  font-weight: 600;
  color: #18181b;
}

.user-username {
  font-size: 0.78rem;
  color: #a1a1aa;
}

.user-bio {
  font-size: 0.8rem;
  color: #52525b;
  line-height: 1.45;
  margin: 2px 0 0 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.user-articles-count {
  font-size: 0.75rem;
  font-weight: 600;
  color: #059669;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  padding: 3px 10px;
  border-radius: 9999px;
  flex-shrink: 0;
}

/* 博文结果列表 */
.search-results-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  margin-top: 0.5rem;
}

.search-empty,
.search-loading {
  margin-top: 2rem;
}
</style>
