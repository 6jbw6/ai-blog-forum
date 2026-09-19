<template>
  <div class="article-detail-page">
    <Navbar />

    <div v-if="loading" class="detail-loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <main v-else-if="article" class="detail-main-container">
      <!-- 面包屑导航 -->
      <nav class="breadcrumb-nav">
        <router-link to="/">首页</router-link>
        <span class="separator">/</span>
        <router-link to="/categories">技术标签</router-link>
        <span class="separator">/</span>
        <span class="current-crumb">{{ article.title }}</span>
      </nav>

      <!-- 文章卡片主体 -->
      <article class="article-paper">
        <!-- 头部信息 -->
        <header class="article-header">
          <div class="article-meta-top">
            <span class="rag-badge">⚡ RAG 向量知识库已索引</span>
            <span class="date-text">{{ formatDate(article.created_at) }}</span>
          </div>

          <h1 class="article-main-title">{{ article.title }}</h1>

          <div class="article-author-row">
            <el-avatar :size="36" src="/bot-avatar.svg" />
            <div class="author-info">
              <span class="author-name">{{ article.author?.username || article.author?.nickname || '博主' }}</span>
              <span class="stats-text">阅读量 {{ article.views_count }} · 点赞 {{ article.likes_count }}</span>
            </div>

            <!-- 作者或管理员编辑按钮 -->
            <el-button
              v-if="userStore.user && (article.author?.id === userStore.user.id || userStore.isAdmin)"
              size="small"
              type="info"
              plain
              @click="$router.push(`/admin/article/edit/${article.id}`)"
            >
              ✏️ 编辑博文
            </el-button>

            <!-- 向 AI 提问按钮 -->
            <button class="btn-ask-ai-detail" @click="askAiThisArticle">
              🤖 问问 AI 智能体对本文的见解
            </button>
          </div>

          <!-- AI 智能提炼 TL;DR 摘要面板 -->
          <div v-if="article.summary" class="ai-summary-callout">
            <div class="summary-header">
              <span class="ai-chip">🤖 AI 智能提炼 · TL;DR</span>
              <span class="summary-note">根据大模型与知识切片自动生成</span>
            </div>
            <p class="summary-content">{{ article.summary }}</p>
          </div>
        </header>

        <!-- Markdown 正文 -->
        <div class="article-content-body">
          <MarkdownViewer :content="article.content" />
        </div>

        <!-- 文章标签与点赞操作栏 -->
        <footer class="article-footer-bar">
          <div class="footer-tags">
            <span
              v-for="t in article.tags"
              :key="t.id"
              class="tag-pill"
              :style="{ color: t.color, borderColor: t.color }"
            >
              {{ t.name }}
            </span>
          </div>

          <div class="like-action-wrap">
            <button
              :class="['btn-like', hasLiked ? 'liked' : '']"
              @click="handleLike"
            >
              <span class="heart-icon">{{ hasLiked ? '❤️' : '🤍' }}</span>
              <span>{{ hasLiked ? '已点赞' : '点赞支持' }} ({{ article.likes_count }})</span>
            </button>

            <button
              :class="['btn-favorite', hasFavorited ? 'favorited' : '']"
              @click="handleFavorite"
            >
              <span class="fav-icon">{{ hasFavorited ? '⭐' : '☆' }}</span>
              <span>{{ hasFavorited ? '已收藏' : '收藏博文' }}</span>
            </button>
          </div>
        </footer>
      </article>

      <!-- 评论互动区 -->
      <section class="comments-section">
        <h3 class="section-title">💬 读者互动与讨论 ({{ comments.length }})</h3>

        <!-- 发表评论表单（仅登录用户可用） -->
        <div v-if="userStore.isLoggedIn" class="comment-form-card">
          <div class="comment-user-header">
            <el-avatar :size="28" :src="userStore.user?.avatar || '/user-avatar.svg'" />
            <span class="current-username">{{ userStore.user?.username || userStore.user?.nickname }}</span>
            <span class="comment-as-label">发表见解</span>
          </div>
          <el-input
            v-model="commentForm.content"
            type="textarea"
            :rows="3"
            placeholder="欢迎理性交流技术与算法实现细节..."
            resize="none"
          />
          <div class="form-submit-row">
            <el-button type="primary" :loading="submittingComment" @click="submitComment">
              提交评论
            </el-button>
          </div>
        </div>

        <div v-else class="comment-form-card not-logged-in-card">
          <div class="login-prompt-box">
            <span class="lock-icon">🔒</span>
            <p class="prompt-text">仅登录用户可参与技术讨论与评论，登录后共同交流算法细节与技术经验。</p>
            <router-link to="/login" class="btn-prompt-login">立即登录 / 注册</router-link>
          </div>
        </div>

        <!-- 评论列表 -->
        <div v-if="comments.length > 0" class="comments-list">
          <div v-for="c in comments" :key="c.id" class="comment-item">
            <el-avatar :size="40" :src="c.user_avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=c'" />
            <div class="comment-main">
              <div class="comment-author-row">
                <span class="author-name">{{ c.user_name }}</span>
                <span v-if="c.is_admin" class="badge-blogger">博主</span>
                <span class="comment-time">{{ formatDate(c.created_at) }}</span>
              </div>
              <p class="comment-text">{{ c.content }}</p>

              <!-- 子级嵌套回复列表 -->
              <div v-if="c.replies && c.replies.length > 0" class="replies-tree">
                <div v-for="reply in c.replies" :key="reply.id" class="reply-item">
                  <el-avatar :size="28" :src="reply.user_avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=r'" />
                  <div class="reply-main">
                    <div class="comment-author-row">
                      <span class="author-name">{{ reply.user_name }}</span>
                      <span v-if="reply.is_admin" class="badge-blogger">博主回复</span>
                      <span class="comment-time">{{ formatDate(reply.created_at) }}</span>
                    </div>
                    <p class="comment-text">{{ reply.content }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div v-else class="empty-comments">
          <p>暂无评论，快来抢沙发吧！</p>
        </div>
      </section>
    </main>

    <AiChatDrawer />
    <SemanticSearchModal />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AiChatDrawer from '@/components/AiChatDrawer.vue'
import SemanticSearchModal from '@/components/SemanticSearchModal.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import { getArticleDetailApi, likeArticleApi, getArticleInteractionApi } from '@/api/article'
import { toggleFavoriteApi } from '@/api/favorite'
import { getArticleCommentsApi, postCommentApi } from '@/api/comment'
import { useAiChatStore } from '@/stores/aiChat'
import { useUserStore } from '@/stores/user'
import type { ArticleDetail, Comment } from '@/types'

const route = useRoute()
const router = useRouter()
const aiChatStore = useAiChatStore()
const userStore = useUserStore()

const article = ref<ArticleDetail | null>(null)
const comments = ref<Comment[]>([])
const loading = ref(true)
const hasLiked = ref(false)
const hasFavorited = ref(false)
const submittingComment = ref(false)

const commentForm = ref({
  content: ''
})

const loadArticle = async () => {
  loading.value = true
  const idOrSlug = route.params.idOrSlug as string
  try {
    const art = await getArticleDetailApi(idOrSlug)
    article.value = art
    loadComments(art.id)
    if (userStore.isLoggedIn) {
      loadInteraction(art.id)
    }
  } finally {
    loading.value = false
  }
}

const loadInteraction = async (articleId: number) => {
  try {
    const inter = await getArticleInteractionApi(articleId)
    hasLiked.value = inter.is_liked
    hasFavorited.value = inter.is_favorited
    if (article.value) {
      article.value.likes_count = inter.likes_count
    }
  } catch {
    // 游客态或加载异常忽略
  }
}

const loadComments = async (articleId: number) => {
  const comms = await getArticleCommentsApi(articleId)
  comments.value = comms
}

const handleLike = async () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录后再点赞')
    router.push('/login')
    return
  }
  if (!article.value) return
  try {
    const res = await likeArticleApi(article.value.id)
    hasLiked.value = res.liked
    article.value.likes_count = res.likes_count
    ElMessage.success(res.liked ? '感谢点赞与认可！' : '已取消点赞')
  } catch (e) {
    ElMessage.error('点赞失败，请稍后重试')
  }
}

const handleFavorite = async () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录后再收藏博文')
    router.push('/login')
    return
  }
  if (!article.value) return
  try {
    const res = await toggleFavoriteApi(article.value.id)
    hasFavorited.value = res.is_favorited
    ElMessage.success(res.is_favorited ? '已加入我的收藏！' : '已取消收藏')
  } catch (e) {
    ElMessage.error('收藏操作失败，请重试')
  }
}

const askAiThisArticle = () => {
  if (!article.value) return
  aiChatStore.openChat(`我想向你请教文章《${article.value.title}》中的核心技术细节，请基于知识库为我讲解一下！`)
}

const submitComment = async () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录后再发表评论')
    router.push('/login')
    return
  }
  if (!article.value) return
  if (!commentForm.value.content.trim()) {
    ElMessage.warning('请填写评论内容')
    return
  }

  submittingComment.value = true
  try {
    await postCommentApi({
      article_id: article.value.id,
      user_name: userStore.user?.username || userStore.user?.nickname || '技术读者',
      user_email: userStore.user?.email || 'reader@ai-blog.local',
      content: commentForm.value.content
    })
    ElMessage.success('评论发表成功')
    commentForm.value.content = ''
    loadComments(article.value.id)
  } finally {
    submittingComment.value = false
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadArticle()
})
</script>

<style scoped>
.article-detail-page {
  min-height: 100vh;
  background: transparent;
}

.detail-main-container,
.detail-loading-container {
  max-width: 1180px;
  margin: 0 auto;
  padding: 2.25rem 2.5rem 5rem 2.5rem;
}

.breadcrumb-nav {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.85rem;
  color: #71717a;
  margin-bottom: 1.5rem;
}

.breadcrumb-nav a {
  color: #18181b;
  text-decoration: none;
}

.breadcrumb-nav a:hover {
  color: #059669;
}

.current-crumb {
  color: #18181b;
  font-weight: 500;
  max-width: 380px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.article-paper {
  background: #ffffff;
  border-radius: 16px;
  padding: 2.5rem;
  border: 1px solid #e4e4e7;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.03);
}

.article-meta-top {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.rag-badge {
  background: #ecfdf5;
  color: #059669;
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 0.8rem;
  font-weight: 600;
}

.date-text {
  margin-left: auto;
  font-size: 0.85rem;
  color: #71717a;
}

.article-main-title {
  font-size: 2rem;
  font-weight: 800;
  color: #18181b;
  line-height: 1.4;
  margin: 0 0 1.5rem 0;
}

.article-author-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding-bottom: 1.5rem;
  border-bottom: 1px solid #f4f4f5;
  margin-bottom: 1.5rem;
}

.author-info {
  display: flex;
  flex-direction: column;
}

.author-name {
  font-size: 0.95rem;
  font-weight: 700;
  color: #18181b;
}

.stats-text {
  font-size: 0.8rem;
  color: #71717a;
  margin-top: 2px;
}

.btn-ask-ai-detail {
  margin-left: auto;
  background: #18181b;
  color: #ffffff;
  border: none;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(24, 24, 27, 0.2);
  transition: all 0.2s;
}

.btn-ask-ai-detail:hover {
  background: #27272a;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(24, 24, 27, 0.3);
}

.ai-summary-callout {
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  border-radius: 12px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 2rem;
}

.summary-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.ai-chip {
  font-size: 0.78rem;
  font-weight: 700;
  background: #18181b;
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 6px;
}

.summary-note {
  font-size: 0.75rem;
  color: #059669;
}

.summary-content {
  margin: 0;
  font-size: 0.92rem;
  color: #374151;
  line-height: 1.6;
}

.article-content-body {
  padding: 1rem 0 2rem 0;
}

.article-footer-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #f4f4f5;
  padding-top: 1.5rem;
  margin-top: 2rem;
}

.footer-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.tag-pill {
  font-size: 0.8rem;
  border: 1px solid;
  padding: 3px 10px;
  border-radius: 6px;
  font-weight: 500;
}

.like-action-wrap {
  display: flex;
  align-items: center;
  gap: 12px;
}

.btn-like,
.btn-favorite {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 30px;
  font-size: 0.9rem;
  font-weight: 600;
  color: #374151;
  cursor: pointer;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.04);
  transition: all 0.2s;
}

.btn-like:hover,
.btn-like.liked {
  border-color: #f43f5e;
  color: #e11d48;
  background: #fff1f2;
}

.btn-favorite:hover,
.btn-favorite.favorited {
  border-color: #f59e0b;
  color: #d97706;
  background: #fffbeb;
}

/* 评论互动 */
.comments-section {
  margin-top: 2.5rem;
}

.section-title {
  font-size: 1.3rem;
  font-weight: 800;
  color: #18181b;
  margin-bottom: 1.25rem;
}

.comment-form-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
  margin-bottom: 2rem;
}

.comment-user-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 12px;
}

.current-username {
  font-weight: 600;
  font-size: 0.92rem;
  color: #18181b;
}

.comment-as-label {
  font-size: 0.8rem;
  color: #a1a1aa;
}

.not-logged-in-card {
  text-align: center;
  padding: 2.2rem 1.5rem;
  background: #fafafa;
}

.login-prompt-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
}

.lock-icon {
  font-size: 26px;
}

.prompt-text {
  font-size: 0.95rem;
  color: #71717a;
  margin: 0;
}

.btn-prompt-login {
  display: inline-block;
  margin-top: 6px;
  padding: 8px 22px;
  background: #10b981;
  color: #ffffff;
  font-weight: 600;
  font-size: 0.9rem;
  border-radius: 8px;
  text-decoration: none;
  transition: background 0.2s;
}

.btn-prompt-login:hover {
  background: #059669;
}

.form-title {
  margin: 0 0 12px 0;
  font-size: 1rem;
  font-weight: 700;
  color: #18181b;
}

.form-inputs-row {
  display: flex;
  gap: 12px;
  margin-bottom: 12px;
}

.form-submit-row {
  margin-top: 12px;
  text-align: right;
}

.comments-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.comment-item {
  background: #ffffff;
  border-radius: 12px;
  padding: 1.25rem;
  border: 1px solid #e4e4e7;
  display: flex;
  gap: 14px;
}

.comment-main {
  flex: 1;
}

.comment-author-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.comment-author-row .author-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: #18181b;
}

.badge-blogger {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
}

.comment-time {
  margin-left: auto;
  font-size: 0.75rem;
  color: #71717a;
}

.comment-text {
  margin: 0;
  font-size: 0.88rem;
  color: #374151;
  line-height: 1.6;
}

.replies-tree {
  margin-top: 12px;
  background: #f4f4f5;
  border-radius: 8px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.reply-item {
  display: flex;
  gap: 10px;
}

.reply-main {
  flex: 1;
}

.empty-comments {
  text-align: center;
  color: #94a3b8;
  padding: 2rem;
}
</style>
