<template>
  <div class="portal-home">
    <Navbar />

    <main class="home-main-container">
      <!-- 顶部 Hero 横幅 -->
      <section class="hero-banner">
        <div class="hero-content">
          <div class="hero-avatar-wrap">
            <el-avatar :size="80" src="/bot-avatar.svg" />
            <span class="pulse-tag">AI Agent 就绪</span>
          </div>
          <div class="hero-text">
            <h1 class="hero-title">欢迎来到 AI博客论坛</h1>
            <p class="hero-desc">
              专注 <strong>AI 大模型应用开发</strong> 与 <strong>企业级软件工程架构</strong> 实战。
              本论坛所有文章均已接入自研向量知识库，配有 <strong>AI 智能体</strong>，随时为你答疑解惑！
            </p>
          </div>
        </div>
      </section>

      <!-- 文章主体布局 -->
      <div class="content-layout">
        <!-- 文章流 -->
        <section class="articles-section">
          <!-- 文章列表 -->
          <div v-if="loading" class="loading-box">
            <el-skeleton :rows="5" animated />
          </div>

          <div v-else-if="articles.length > 0" class="articles-list">
            <article
              v-for="art in articles"
              :key="art.id"
              class="article-card"
            >
              <div class="card-header">
                <span v-if="art.is_top" class="top-tag">📌 置顶精选</span>
                <span class="vector-status-tag" title="已拆分向量切片并录入 RAG 知识库">
                  ⚡ RAG 向量已索引
                </span>
                <span class="date-text">{{ formatDate(art.created_at) }}</span>
              </div>

              <h2 class="card-title" @click="goToArticle(art.slug)">
                {{ art.title }}
              </h2>

              <p class="card-summary">{{ art.summary || '点击阅读全文了解更多技术细节...' }}</p>

              <div class="card-footer">
                <div class="card-tags">
                  <span
                    v-for="t in art.tags"
                    :key="t.id"
                    class="article-tag"
                    :style="{ color: t.color, borderColor: t.color }"
                  >
                    {{ t.name }}
                  </span>
                </div>

                <div class="card-meta">
                  <span v-if="art.author" class="meta-item author-name-meta">✍️ {{ art.author.username || art.author.nickname }}</span>
                  <span class="meta-item">👁️ {{ art.views_count }}</span>
                  <span class="meta-item">❤️ {{ art.likes_count }}</span>
                  <button class="btn-ask-ai" @click.stop="askAiAboutArticle(art.title)">
                    🤖 AI 快速答疑
                  </button>
                </div>
              </div>
            </article>
          </div>

          <div v-else class="empty-box">
            <el-empty description="暂无文章" />
          </div>
        </section>
      </div>
    </main>

    <!-- 核心 AI 悬浮抽屉 -->
    <AiChatDrawer />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AiChatDrawer from '@/components/AiChatDrawer.vue'
import { getArticlesApi } from '@/api/article'
import { useAiChatStore } from '@/stores/aiChat'
import { useUserStore } from '@/stores/user'
import type { ArticleListItem } from '@/types'

const router = useRouter()
const aiChatStore = useAiChatStore()
const userStore = useUserStore()

const articles = ref<ArticleListItem[]>([])
const loading = ref(true)

const loadData = async () => {
  loading.value = true
  try {
    const artsRes = await getArticlesApi({ page: 1, size: 20 })
    articles.value = artsRes.list
  } finally {
    loading.value = false
  }
}

const goToArticle = (slug: string) => {
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

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.portal-home {
  min-height: 100vh;
  background: transparent;
}

.home-main-container {
  max-width: 1520px;
  margin: 0 auto;
  padding: 2.25rem 2.5rem 5rem 2.5rem;
}

.hero-banner {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 24px;
  padding: 2.5rem 3.5rem;
  color: #18181b;
  margin-bottom: 2.5rem;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.04);
}

.hero-content {
  display: flex;
  align-items: center;
  gap: 2.5rem;
}

.hero-avatar-wrap {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.pulse-tag {
  margin-top: 8px;
  font-size: 0.72rem;
  background: #10b981;
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 9999px;
  font-weight: 600;
}

.hero-title {
  font-size: 2.25rem;
  font-weight: 800;
  margin: 0 0 0.85rem 0;
  letter-spacing: -0.5px;
  color: #18181b;
}

.hero-desc {
  font-size: 1.05rem;
  color: #52525b;
  line-height: 1.7;
  margin: 0;
  max-width: 980px;
}

.hero-desc strong {
  color: #18181b;
  font-weight: 600;
}

.content-layout {
  display: grid;
  grid-template-columns: 1fr;
  gap: 2.5rem;
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.article-card {
  background: #ffffff;
  border-radius: 18px;
  padding: 1.75rem 2rem;
  border: 1px solid #e4e4e7;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
}

.article-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.06);
  border-color: #10b981;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
  font-size: 0.8rem;
}

.top-tag {
  background: #fef2f2;
  color: #dc2626;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 700;
  border: 1px solid #fecaca;
}

.vector-status-tag {
  background: #ecfdf5;
  color: #059669;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 600;
}

.date-text {
  margin-left: auto;
  color: #71717a;
}

.card-title {
  margin: 0 0 10px 0;
  font-size: 1.25rem;
  font-weight: 700;
  color: #18181b;
  cursor: pointer;
  transition: color 0.2s;
}

.card-title:hover {
  color: #059669;
}

.card-summary {
  font-size: 0.9rem;
  color: #52525b;
  line-height: 1.6;
  margin: 0 0 1rem 0;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-top: 1px solid #f4f4f5;
  padding-top: 12px;
}

.card-tags {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.article-tag {
  font-size: 0.78rem;
  border: 1px solid;
  padding: 2px 8px;
  border-radius: 6px;
  font-weight: 500;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 0.85rem;
  color: #71717a;
}

.btn-ask-ai {
  background: #f4f4f5;
  color: #18181b;
  border: 1px solid #e4e4e7;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 0.78rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.btn-ask-ai:hover {
  background: #18181b;
  color: #ffffff;
}
</style>
