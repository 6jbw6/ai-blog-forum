<template>
  <el-dialog
    v-model="visible"
    title="📝 我的创作博文"
    width="720px"
    destroy-on-close
    append-to-body
    :lock-scroll="false"
    custom-class="my-articles-modal"
  >
    <div class="articles-container">
      <!-- 头部操作条 -->
      <div class="articles-header-bar">
        <span class="header-count">共创作 {{ articles.length }} 篇博文</span>
        <el-button type="primary" size="small" @click="createNewArticle">
          ✍️ 创作新博文 (AI 协同)
        </el-button>
      </div>

      <div v-if="loading" class="articles-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <div v-else-if="articles.length > 0" class="articles-list">
        <div
          v-for="item in articles"
          :key="item.id"
          class="article-card-item"
        >
          <div class="card-left">
            <div class="card-top">
              <span v-if="item.category_name" class="category-badge">
                {{ item.category_name }}
              </span>
              <span :class="['status-badge', item.is_published ? 'published' : 'draft']">
                {{ item.is_published ? '已发布' : '草稿' }}
              </span>
              <span v-if="item.vector_status === 'indexed'" class="rag-badge">
                ⚡ RAG 向量已索引
              </span>
              <h4 class="article-title" @click="goToArticle(item.slug)">{{ item.title }}</h4>
            </div>

            <p v-if="item.summary" class="article-summary">
              {{ item.summary }}
            </p>

            <div class="card-meta">
              <span class="meta-item">创建于 {{ formatDate(item.created_at) }}</span>
              <span class="meta-item">👁️ {{ item.views_count }} 浏览</span>
              <span class="meta-item">❤️ {{ item.likes_count }} 点赞</span>
            </div>
          </div>

          <div class="card-actions">
            <el-button
              size="small"
              type="primary"
              plain
              @click="goToArticle(item.slug)"
            >
              查看
            </el-button>
            <el-button
              size="small"
              type="info"
              plain
              @click="editArticle(item.id)"
            >
              编辑
            </el-button>
          </div>
        </div>
      </div>

      <div v-else class="articles-empty">
        <el-empty description="你尚未创作发布博文">
          <el-button type="primary" @click="createNewArticle">
            ✍️ 立即创作第一篇博文
          </el-button>
        </el-empty>
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { getMyCreatedArticlesApi } from '@/api/article'

interface CreatedArticleItem {
  id: number
  title: string
  slug: string
  summary?: string
  category_name?: string
  is_published: boolean
  views_count: number
  likes_count: number
  created_at: string
  vector_status: string
}

const router = useRouter()
const visible = ref(false)
const loading = ref(false)
const articles = ref<CreatedArticleItem[]>([])

const formatDate = (isoString?: string) => {
  if (!isoString) return '近期'
  try {
    const raw = isoString.endsWith('Z') || isoString.includes('+') ? isoString : `${isoString}Z`
    const d = new Date(raw)
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).format(d).replace(/\//g, '-')
  } catch {
    return isoString
  }
}

const loadArticles = async () => {
  loading.value = true
  try {
    const data = await getMyCreatedArticlesApi()
    articles.value = data
  } catch {
    articles.value = []
  } finally {
    loading.value = false
  }
}

const open = () => {
  visible.value = true
  loadArticles()
}

const goToArticle = (slug: string) => {
  visible.value = false
  router.push(`/article/${slug}`)
}

const editArticle = (id: number) => {
  visible.value = false
  router.push(`/admin/article/edit/${id}`)
}

const createNewArticle = () => {
  visible.value = false
  router.push('/admin/article/new')
}

defineExpose({
  open
})
</script>

<style scoped>
.articles-container {
  min-height: 200px;
  max-height: 540px;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.articles-header-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter, #e4e4e7);
}

.header-count {
  font-size: 0.85rem;
  color: var(--el-text-color-secondary, #71717a);
  font-weight: 500;
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.article-card-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #e4e4e7);
  background: var(--el-bg-color, #ffffff);
  transition: all 0.2s ease;
}

.article-card-item:hover {
  border-color: #10b981;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
}

.card-left {
  flex: 1;
  min-width: 0;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 6px;
}

.category-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #ecfdf5;
  color: #059669;
  font-weight: 600;
  white-space: nowrap;
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  font-weight: 600;
}

.status-badge.published {
  background: #f0fdf4;
  color: #16a34a;
}

.status-badge.draft {
  background: #f4f4f5;
  color: #71717a;
}

.rag-badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 4px;
  background: #18181b;
  color: #10b981;
  font-weight: 600;
}

.article-title {
  font-size: 15px;
  font-weight: 600;
  color: #18181b;
  margin: 0;
  cursor: pointer;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.article-title:hover {
  color: #10b981;
}

.article-summary {
  font-size: 13px;
  color: #71717a;
  line-height: 1.5;
  margin: 4px 0 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-meta {
  display: flex;
  align-items: center;
  gap: 14px;
  font-size: 12px;
  color: #a1a1aa;
}

.card-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.articles-empty {
  padding: 36px 0;
}
</style>
