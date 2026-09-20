<template>
  <div class="profile-page">
    <Navbar />

    <main class="profile-container">
      <!-- 用户信息头部卡 -->
      <div v-if="profile" class="profile-header-card">
        <el-avatar :size="84" :src="profile.avatar || '/user-avatar.svg'" class="profile-avatar" />
        <div class="profile-meta">
          <div class="profile-name-row">
            <h2 class="profile-nickname">{{ profile.nickname }}</h2>
            <span class="profile-username">@{{ profile.username }}</span>
            <span v-if="profile.role === 'admin'" class="role-badge">博主</span>
          </div>
          <p class="profile-bio">{{ profile.bio || '这位用户还没有写下签名' }}</p>
          <div class="profile-stats-row">
            <span class="stat-item"><b>{{ profile.article_count }}</b> 博文</span>
            <span class="stat-divider"></span>
            <span class="stat-item"><b>{{ profile.total_likes }}</b> 获赞</span>
            <span class="stat-divider"></span>
            <span class="stat-item">注册于 {{ formatDate(profile.created_at) }}</span>
            <span class="stat-divider"></span>
            <span class="stat-item">{{ profile.email }}</span>
          </div>
        </div>
      </div>

      <div v-if="profileNotFound" class="profile-missing">
        <el-empty description="用户不存在或已注销" />
      </div>

      <template v-if="profile">
        <!-- 内容维度 tabs：博文/评论公开，其余仅本人可见 -->
        <div class="profile-tabs-row">
          <button
            v-for="t in visibleTabs"
            :key="t.key"
            class="profile-tab"
            :class="{ active: activeTab === t.key }"
            @click="switchTab(t.key)"
          >
            {{ t.label }}
            <span
              v-if="t.key === 'notifications' && isOwner && unreadCount > 0"
              class="tab-badge"
            >{{ unreadCount > 99 ? '99+' : unreadCount }}</span>
          </button>
        </div>

        <!-- 博文（公开） -->
        <section v-show="activeTab === 'articles'" class="tab-panel">
          <div v-if="loadingArticles" class="panel-loading">
            <el-skeleton :rows="5" animated />
          </div>
          <template v-else>
          <div v-if="articles.length > 0" class="card-list">
            <div
              v-for="a in articles"
              :key="a.id"
              class="article-card"
              @click="goArticle(a.slug)"
            >
              <div class="article-main">
                <div class="article-title-row">
                  <h4 class="article-title">{{ a.title }}</h4>
                  <span
                    v-if="isOwner"
                    class="pub-badge"
                    :class="a.is_published ? 'published' : 'draft'"
                  >{{ a.is_published ? '已发布' : '未发布 · 私有' }}</span>
                </div>
                <p class="article-summary">{{ a.summary || '暂无文章摘要' }}</p>
                <div class="article-meta-row">
                  <span v-if="a.category" class="meta-category">{{ a.category.name }}</span>
                  <span class="meta-item">{{ formatDate(a.created_at) }}</span>
                  <span class="meta-item">{{ a.views_count }} 浏览</span>
                  <span class="meta-item">{{ a.likes_count }} 点赞</span>
                </div>
              </div>
              <div v-if="a.tags && a.tags.length > 0" class="article-tags">
                <span v-for="t in a.tags.slice(0, 3)" :key="t.id" class="tag-chip">{{ t.name }}</span>
              </div>
            </div>
          </div>
            <div v-else class="panel-empty">
              <el-empty description="TA 还没有发布博文" />
            </div>
            <div v-if="total > pageSize" class="pagination-row">
              <el-pagination
                layout="prev, pager, next"
                :total="total"
                :page-size="pageSize"
                :current-page="page"
                @current-change="onPageChange"
              />
            </div>
          </template>
        </section>

        <!-- 评论（公开） -->
        <section v-show="activeTab === 'comments'" class="tab-panel">
          <div v-if="loadingComments" class="panel-loading">
            <el-skeleton :rows="4" animated />
          </div>
          <template v-else>
            <div v-if="comments.length > 0" class="card-list">
              <div
                v-for="c in comments"
                :key="c.id"
                class="comment-card"
                @click="goArticle(c.article_slug)"
              >
                <div class="comment-top">
                  <span class="comment-article">💬 《{{ c.article_title }}》</span>
                  <span class="comment-date">{{ formatDate(c.created_at) }}</span>
                </div>
                <p class="comment-content">{{ c.content }}</p>
                <div class="comment-footer">
                  <span class="meta-item">{{ isOwner && !c.is_approved ? '待展示' : '' }}</span>
                  <span class="click-hint">查看原文 &rarr;</span>
                </div>
              </div>
            </div>
            <div v-else class="panel-empty">
              <el-empty :description="isOwner ? '你还没有发表过评论，去文章下方参与讨论吧~' : 'TA 还没有发表过评论'" />
            </div>
          </template>
        </section>

        <!-- 收藏（仅本人） -->
        <section v-if="isOwner" v-show="activeTab === 'favorites'" class="tab-panel">
          <div v-if="loadingFavorites" class="panel-loading">
            <el-skeleton :rows="4" animated />
          </div>
          <template v-else>
            <div v-if="favorites.length > 0" class="card-list">
              <div v-for="f in favorites" :key="f.id" class="article-card">
                <div class="article-main" @click="goArticle(f.slug)">
                  <h4 class="article-title">{{ f.title }}</h4>
                  <p class="article-summary">{{ f.summary || '暂无文章摘要' }}</p>
                  <div class="article-meta-row">
                    <span v-if="f.category_name" class="meta-category">{{ f.category_name }}</span>
                    <span class="meta-item">收藏于 {{ formatDate(f.favorited_at) }}</span>
                    <span class="meta-item">{{ f.views_count }} 浏览</span>
                    <span class="meta-item">{{ f.likes_count }} 点赞</span>
                  </div>
                </div>
                <div class="card-side-action">
                  <el-button size="small" type="danger" plain @click="removeFavorite(f.id)">
                    取消收藏
                  </el-button>
                </div>
              </div>
            </div>
            <div v-else class="panel-empty">
              <el-empty description="暂无收藏博文，快去阅读感兴趣的文章并收藏吧~" />
            </div>
          </template>
        </section>

        <!-- 点赞（仅本人） -->
        <section v-if="isOwner" v-show="activeTab === 'likes'" class="tab-panel">
          <div v-if="loadingLikes" class="panel-loading">
            <el-skeleton :rows="4" animated />
          </div>
          <template v-else>
            <div v-if="likedArticles.length > 0" class="card-list">
              <div
                v-for="l in likedArticles"
                :key="l.id"
                class="article-card"
                @click="goArticle(l.slug)"
              >
                <div class="article-main">
                  <h4 class="article-title">{{ l.title }}</h4>
                  <p class="article-summary">{{ l.summary || '暂无文章摘要' }}</p>
                  <div class="article-meta-row">
                    <span v-if="l.category_name" class="meta-category">{{ l.category_name }}</span>
                    <span class="meta-item">点赞于 {{ formatDate(l.liked_at) }}</span>
                    <span class="meta-item">{{ l.views_count }} 浏览</span>
                    <span class="meta-item">{{ l.likes_count }} 点赞</span>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="panel-empty">
              <el-empty description="暂无点赞博文，快去为喜欢的文章点赞吧~" />
            </div>
          </template>
        </section>

        <!-- 消息提醒（仅本人） -->
        <section v-if="isOwner" v-show="activeTab === 'notifications'" class="tab-panel">
          <div v-if="loadingNotifications" class="panel-loading">
            <el-skeleton :rows="4" animated />
          </div>
          <template v-else>
            <div class="panel-toolbar" v-if="notifications.length > 0">
              <el-button size="small" @click="markAllRead">全部标为已读</el-button>
            </div>
            <div v-if="notifications.length > 0" class="card-list">
              <div
                v-for="n in notifications"
                :key="n.id"
                class="notification-card"
                :class="{ unread: !n.is_read }"
                @click="goArticle(n.article_slug)"
              >
                <div class="notif-main">
                  <div class="notif-line1">
                    <span class="notif-sender">{{ n.sender_name }}</span>
                    <span class="notif-action">回复了你的评论</span>
                    <span class="notif-date">{{ formatDate(n.created_at) }}</span>
                    <span v-if="!n.is_read" class="unread-dot"></span>
                  </div>
                  <p class="notif-reply">「{{ n.reply_content }}」</p>
                  <p class="notif-parent">回复原文：{{ n.parent_content }}</p>
                  <p class="notif-article">来自文章：《{{ n.article_title }}》</p>
                </div>
                <el-button
                  v-if="!n.is_read"
                  size="small"
                  text
                  type="primary"
                  @click.stop="markRead(n)"
                >
                  标为已读
                </el-button>
              </div>
            </div>
            <div v-else class="panel-empty">
              <el-empty description="暂无消息提醒，有人回复你的评论时会出现在这里~" />
            </div>
          </template>
        </section>
      </template>
    </main>

    <AiChatDrawer />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AiChatDrawer from '@/components/AiChatDrawer.vue'
import { getUserProfileApi } from '@/api/user'
import { getArticlesApi } from '@/api/article'
import { getMyFavoritesApi, toggleFavoriteApi, type FavoriteArticleItem } from '@/api/favorite'
import { getMyLikedArticlesApi } from '@/api/article'
import { getMyNotificationsApi, markAllNotificationsAsReadApi, markNotificationAsReadApi, getUnreadNotificationCountApi, type NotificationItem } from '@/api/notification'
import { getMyCommentsApi } from '@/api/comment'
import { useUserStore } from '@/stores/user'
import type { UserProfileItem, ArticleListItem, MyCommentItem } from '@/types'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

const profile = ref<UserProfileItem | null>(null)
const profileNotFound = ref(false)

const userId = computed(() => Number(route.params.id))
const isOwner = computed(
  () => userStore.isLoggedIn && userStore.user?.id === userId.value
)

const loadProfile = async () => {
  profile.value = null
  profileNotFound.value = false
  try {
    profile.value = await getUserProfileApi(userId.value)
  } catch {
    profileNotFound.value = true
    ElMessage.error('用户不存在或已注销')
  }
}

// 内容维度：博文对访客公开（本人可见含未发布的全部文章）；评论/收藏/点赞/消息提醒仅本人可见
type TabKey = 'articles' | 'comments' | 'favorites' | 'likes' | 'notifications'
const activeTab = ref<TabKey>('articles')
const allTabs: Array<{ key: TabKey; label: string }> = [
  { key: 'articles', label: '博文' },
  { key: 'comments', label: '评论' },
  { key: 'favorites', label: '收藏' },
  { key: 'likes', label: '点赞' },
  { key: 'notifications', label: '消息提醒' }
]
const visibleTabs = computed(() =>
  allTabs.filter(t => isOwner.value || t.key === 'articles')
)

// ---------- 博文（分页；本人可见含未发布的全部文章，访客仅已发布） ----------
const articles = ref<ArticleListItem[]>([])
const loadingArticles = ref(true)
const page = ref(1)
const pageSize = 10
const total = ref(0)

const loadArticles = async () => {
  loadingArticles.value = true
  try {
    const data = await getArticlesApi({
      page: page.value,
      size: pageSize,
      author_id: userId.value,
      // 本人查看自己主页时包含未发布（私有）文章，访客仅已发布
      published_only: !isOwner.value
    })
    articles.value = data.list
    total.value = data.total
  } catch {
    articles.value = []
    total.value = 0
  } finally {
    loadingArticles.value = false
  }
}

const onPageChange = (p: number) => {
  page.value = p
  loadArticles()
}

// ---------- 评论（仅本人，/comments/my 返回登录用户本人数据） ----------
const comments = ref<MyCommentItem[]>([])
const commentsLoaded = ref(false)
const loadingComments = ref(false)

const loadComments = async () => {
  if (commentsLoaded.value) return
  loadingComments.value = true
  try {
    comments.value = await getMyCommentsApi()
    commentsLoaded.value = true
  } catch {
    comments.value = []
  } finally {
    loadingComments.value = false
  }
}

// ---------- 收藏（仅本人） ----------
const favorites = ref<FavoriteArticleItem[]>([])
const favoritesLoaded = ref(false)
const loadingFavorites = ref(false)

const loadFavorites = async () => {
  if (favoritesLoaded.value) return
  loadingFavorites.value = true
  try {
    favorites.value = await getMyFavoritesApi()
    favoritesLoaded.value = true
  } catch {
    favorites.value = []
  } finally {
    loadingFavorites.value = false
  }
}

const removeFavorite = async (articleId: number) => {
  try {
    await toggleFavoriteApi(articleId)
    ElMessage.success('已取消收藏')
    favorites.value = favorites.value.filter(f => f.id !== articleId)
  } catch {
    ElMessage.error('取消收藏失败，请稍后重试')
  }
}

// ---------- 点赞（仅本人） ----------
const likedArticles = ref<Array<{
  id: number; title: string; slug: string; summary?: string
  category_name?: string; views_count: number; likes_count: number
  created_at: string; liked_at: string
}>>([])
const likesLoaded = ref(false)
const loadingLikes = ref(false)

const loadLikes = async () => {
  if (likesLoaded.value) return
  loadingLikes.value = true
  try {
    likedArticles.value = await getMyLikedArticlesApi()
    likesLoaded.value = true
  } catch {
    likedArticles.value = []
  } finally {
    loadingLikes.value = false
  }
}

// ---------- 消息提醒（仅本人） ----------
const notifications = ref<NotificationItem[]>([])
const notificationsLoaded = ref(false)
const loadingNotifications = ref(false)
const unreadCount = ref(0)

const loadNotifications = async () => {
  if (notificationsLoaded.value) return
  loadingNotifications.value = true
  try {
    notifications.value = await getMyNotificationsApi()
    notificationsLoaded.value = true
    const count = await getUnreadNotificationCountApi()
    unreadCount.value = count
  } catch {
    notifications.value = []
  } finally {
    loadingNotifications.value = false
  }
}

const markRead = async (n: NotificationItem) => {
  if (n.is_read) return
  try {
    await markNotificationAsReadApi(n.id)
    n.is_read = true
    unreadCount.value = Math.max(0, unreadCount.value - 1)
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

const markAllRead = async () => {
  try {
    await markAllNotificationsAsReadApi()
    notifications.value.forEach(n => { n.is_read = true })
    unreadCount.value = 0
    ElMessage.success('已全部标为已读')
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}

// ---------- 通用 ----------
const switchTab = (key: TabKey) => {
  activeTab.value = key
  if (key === 'comments') loadComments()
  if (key === 'favorites') loadFavorites()
  if (key === 'likes') loadLikes()
  if (key === 'notifications') loadNotifications()
}

const goArticle = (slug: string) => {
  router.push(`/article/${slug}`)
}

const formatDate = (iso?: string) => {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric'
  })
}

// 编辑资料保存后 userStore.user 引用更新，同步刷新主页展示（签名/头像等）
watch(() => userStore.user, () => {
  if (isOwner.value) {
    loadProfile()
  }
})

// 进入页面与路由内用户切换时重新加载（评论/收藏等懒加载状态随之重置）
watch(userId, () => {
  page.value = 1
  activeTab.value = 'articles'
  profile.value = null
  profileNotFound.value = false
  commentsLoaded.value = false
  favoritesLoaded.value = false
  likesLoaded.value = false
  notificationsLoaded.value = false

  loadProfile()
  loadArticles()
  if (isOwner.value) {
    loadComments()
    loadFavorites()
    loadLikes()
    loadNotifications()
  }
}, { immediate: true })
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background: transparent;
}

/* 页面大小与首页/搜索页对齐 */
.profile-container {
  max-width: 1520px;
  margin: 0 auto;
  padding: 2.25rem 2.5rem 5rem 2.5rem;
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* 用户信息头部卡 */
.profile-header-card {
  display: flex;
  align-items: center;
  gap: 24px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 14px;
  padding: 28px 32px;
}

.profile-avatar {
  flex-shrink: 0;
  border: 3px solid #ecfdf5;
}

.profile-meta {
  flex: 1;
  min-width: 0;
}

.profile-name-row {
  display: flex;
  align-items: baseline;
  gap: 12px;
  flex-wrap: wrap;
}

.profile-nickname {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 800;
  color: #18181b;
  letter-spacing: -0.4px;
}

.profile-username {
  font-size: 0.9rem;
  color: #a1a1aa;
}

.role-badge {
  font-size: 0.72rem;
  font-weight: 700;
  color: #059669;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
  padding: 2px 10px;
  border-radius: 9999px;
}

.profile-bio {
  margin: 8px 0 12px 0;
  font-size: 0.9rem;
  color: #52525b;
  line-height: 1.5;
}

.profile-stats-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 0.84rem;
  color: #71717a;
  flex-wrap: wrap;
}

.stat-item b {
  color: #18181b;
  font-weight: 700;
}

.stat-divider {
  width: 1px;
  height: 12px;
  background: #e4e4e7;
}

.profile-missing {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 14px;
  padding: 30px;
}

/* 内容维度 tabs */
.profile-tabs-row {
  display: flex;
  align-items: center;
  gap: 6px;
  border-bottom: 1px solid #e4e4e7;
  padding: 0 4px;
}

.profile-tab {
  background: transparent;
  border: none;
  cursor: pointer;
  font-size: 0.92rem;
  font-weight: 500;
  color: #71717a;
  padding: 10px 18px;
  position: relative;
  transition: color 0.15s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.profile-tab:hover {
  color: #18181b;
}

.profile-tab.active {
  color: #18181b;
  font-weight: 700;
}

.profile-tab.active::after {
  content: '';
  position: absolute;
  left: 14px;
  right: 14px;
  bottom: -1px;
  height: 2px;
  background: #18181b;
  border-radius: 2px;
}

.tab-badge {
  font-size: 0.68rem;
  font-weight: 700;
  color: #ffffff;
  background: #ef4444;
  border-radius: 9999px;
  padding: 1px 7px;
  line-height: 1.4;
}

.tab-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.panel-loading {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 20px;
}

.panel-empty {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 20px;
}

.panel-toolbar {
  display: flex;
  justify-content: flex-end;
  padding: 0 4px;
}

.card-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 博文卡片 */
.article-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 16px 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.article-card:hover {
  border-color: #10b981;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.article-main {
  flex: 1;
  min-width: 0;
}

.article-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
}

.article-title {
  margin: 0 0 6px 0;
  font-size: 1.02rem;
  font-weight: 650;
  color: #18181b;
}

.pub-badge {
  font-size: 0.7rem;
  font-weight: 700;
  padding: 2px 9px;
  border-radius: 9999px;
  flex-shrink: 0;
}

.pub-badge.published {
  color: #059669;
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}

.pub-badge.draft {
  color: #a16207;
  background: #fefce8;
  border: 1px solid #fde68a;
}

.article-summary {
  margin: 0 0 10px 0;
  font-size: 0.84rem;
  color: #52525b;
  line-height: 1.55;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.article-meta-row {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 0.76rem;
  color: #a1a1aa;
  flex-wrap: wrap;
}

.meta-category {
  color: #059669;
  font-weight: 600;
}

.article-tags {
  display: flex;
  gap: 6px;
  margin-top: 10px;
  flex-wrap: wrap;
}

.tag-chip {
  font-size: 0.72rem;
  color: #52525b;
  background: #f4f4f5;
  border-radius: 6px;
  padding: 2px 8px;
}

.card-side-action {
  flex-shrink: 0;
  align-self: center;
}

/* 评论卡片 */
.comment-card {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 14px 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.comment-card:hover {
  border-color: #10b981;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.comment-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.comment-article {
  font-size: 0.8rem;
  font-weight: 600;
  color: #059669;
}

.comment-date {
  font-size: 0.74rem;
  color: #a1a1aa;
}

.comment-content {
  margin: 0 0 8px 0;
  font-size: 0.88rem;
  color: #18181b;
  line-height: 1.6;
}

.comment-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.click-hint {
  font-size: 0.74rem;
  color: #059669;
  font-weight: 500;
}

/* 消息提醒卡片 */
.notification-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 14px 20px;
  cursor: pointer;
  transition: all 0.2s;
}

.notification-card.unread {
  background: #f0fdf4;
  border-color: #a7f3d0;
}

.notification-card:hover {
  border-color: #10b981;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.notif-main {
  flex: 1;
  min-width: 0;
}

.notif-line1 {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.84rem;
}

.notif-sender {
  font-weight: 700;
  color: #18181b;
}

.notif-action {
  color: #52525b;
}

.notif-date {
  color: #a1a1aa;
  font-size: 0.74rem;
}

.unread-dot {
  width: 7px;
  height: 7px;
  background: #ef4444;
  border-radius: 50%;
  flex-shrink: 0;
}

.notif-reply {
  margin: 8px 0 4px 0;
  font-size: 0.86rem;
  color: #18181b;
  line-height: 1.55;
}

.notif-parent {
  margin: 0 0 4px 0;
  font-size: 0.78rem;
  color: #71717a;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.notif-article {
  margin: 0;
  font-size: 0.75rem;
  color: #a1a1aa;
}

.pagination-row {
  display: flex;
  justify-content: center;
  padding-top: 6px;
}
</style>
