<template>
  <el-dialog
    v-model="visible"
    title="❤️ 我的博文点赞"
    width="680px"
    destroy-on-close
    append-to-body
    :lock-scroll="false"
    custom-class="likes-modal"
  >
    <div class="likes-container">
      <div v-if="loading" class="likes-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <div v-else-if="likes.length > 0" class="likes-list">
        <div
          v-for="item in likes"
          :key="item.id"
          class="like-card"
        >
          <div class="card-info" @click="goToArticle(item.slug)">
            <div class="card-top">
              <span v-if="item.category_name" class="category-badge">
                {{ item.category_name }}
              </span>
              <h4 class="article-title">{{ item.title }}</h4>
            </div>

            <p v-if="item.summary" class="article-summary">
              {{ item.summary }}
            </p>

            <div class="card-meta">
              <span class="meta-item">点赞于 {{ formatDate(item.liked_at) }}</span>
              <span class="meta-item">👁️ {{ item.views_count }} 浏览</span>
              <span class="meta-item">❤️ {{ item.likes_count }} 点赞</span>
            </div>
          </div>

          <div class="card-actions">
            <el-button
              size="small"
              type="danger"
              plain
              @click="handleUnlike(item.id)"
            >
              取消点赞
            </el-button>
          </div>
        </div>
      </div>

      <div v-else class="likes-empty">
        <el-empty description="暂无点赞博文，阅读时点击红心即可记录你的技术认可~" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMyLikedArticlesApi, likeArticleApi } from '@/api/article'

interface LikedArticleItem {
  id: number
  title: string
  slug: string
  summary?: string
  category_name?: string
  views_count: number
  likes_count: number
  created_at: string
  liked_at: string
}

const router = useRouter()
const visible = ref(false)
const loading = ref(false)
const likes = ref<LikedArticleItem[]>([])

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

const loadLikes = async () => {
  loading.value = true
  try {
    const data = await getMyLikedArticlesApi()
    likes.value = data
  } catch {
    likes.value = []
  } finally {
    loading.value = false
  }
}

const open = () => {
  visible.value = true
  loadLikes()
}

const goToArticle = (slug: string) => {
  visible.value = false
  router.push(`/article/${slug}`)
}

const handleUnlike = async (articleId: number) => {
  try {
    await likeArticleApi(articleId)
    ElMessage.success('已取消点赞')
    likes.value = likes.value.filter(item => item.id !== articleId)
  } catch {
    ElMessage.error('取消点赞失败，请稍后重试')
  }
}

defineExpose({
  open
})
</script>

<style scoped>
.likes-container {
  min-height: 200px;
  max-height: 520px;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.likes-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.like-card {
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

.like-card:hover {
  border-color: #f43f5e;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(244, 63, 94, 0.08);
}

.card-info {
  flex: 1;
  cursor: pointer;
  min-width: 0;
}

.card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.category-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: #fff1f2;
  color: #e11d48;
  font-weight: 600;
  white-space: nowrap;
}

.article-title {
  font-size: 15px;
  font-weight: 600;
  color: #18181b;
  margin: 0;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.article-title:hover {
  color: #e11d48;
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
  flex-shrink: 0;
}

.likes-empty {
  padding: 36px 0;
}
</style>
