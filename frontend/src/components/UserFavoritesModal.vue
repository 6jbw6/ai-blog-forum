<template>
  <el-dialog
    v-model="visible"
    title="⭐ 我的博文收藏"
    width="680px"
    destroy-on-close
    append-to-body
    :lock-scroll="false"
    custom-class="favorites-modal"
  >
    <div class="favorites-container">
      <div v-if="loading" class="favorites-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <div v-else-if="favorites.length > 0" class="favorites-list">
        <div
          v-for="item in favorites"
          :key="item.id"
          class="favorite-card"
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
              <span class="meta-item">收藏于 {{ formatDate(item.favorited_at) }}</span>
              <span class="meta-item">👁️ {{ item.views_count }} 浏览</span>
              <span class="meta-item">❤️ {{ item.likes_count }} 点赞</span>
            </div>
          </div>

          <div class="card-actions">
            <el-button
              size="small"
              type="danger"
              plain
              @click="handleRemoveFavorite(item.id)"
            >
              取消收藏
            </el-button>
          </div>
        </div>
      </div>

      <div v-else class="favorites-empty">
        <el-empty description="暂无收藏博文，快去阅读感兴趣的文章并收藏吧~" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { getMyFavoritesApi, toggleFavoriteApi, type FavoriteArticleItem } from '@/api/favorite'

const router = useRouter()
const visible = ref(false)
const loading = ref(false)
const favorites = ref<FavoriteArticleItem[]>([])

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

const loadFavorites = async () => {
  loading.value = true
  try {
    const data = await getMyFavoritesApi()
    favorites.value = data
  } catch (err) {
    favorites.value = []
  } finally {
    loading.value = false
  }
}

const open = () => {
  visible.value = true
  loadFavorites()
}

const goToArticle = (slug: string) => {
  visible.value = false
  router.push(`/article/${slug}`)
}

const handleRemoveFavorite = async (articleId: number) => {
  try {
    await toggleFavoriteApi(articleId)
    ElMessage.success('已取消收藏')
    favorites.value = favorites.value.filter(f => f.id !== articleId)
  } catch (err) {
    ElMessage.error('取消收藏失败，请稍后重试')
  }
}

defineExpose({
  open
})
</script>

<style scoped>
.favorites-container {
  min-height: 200px;
  max-height: 520px;
  overflow-y: auto;
  padding: 4px 8px 12px;
}

.favorites-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.favorite-card {
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

.favorite-card:hover {
  border-color: #10b981;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
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
  background: #ecfdf5;
  color: #059669;
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
  flex-shrink: 0;
}

.favorites-empty {
  padding: 36px 0;
}
</style>
