<template>
  <div class="portal-home">
    <Navbar />

    <main class="home-main-container">
      <!-- 顶部 Hero 横幅 -->
      <section class="hero-banner">
        <div class="hero-content">
          <div class="hero-avatar-wrap">
            <el-avatar :size="80" src="/logo.png" />
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
            <ArticleCard
              v-for="art in articles"
              :key="art.id"
              :article="art"
              @open="goToArticle"
              @ask="askAiAboutArticle"
            />
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
import ArticleCard from '@/components/ArticleCard.vue'
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
</style>
