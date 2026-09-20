<template>
  <div class="categories-page">
    <Navbar />

    <main class="page-container">
      <div class="page-header">
        <h1 class="title">🏷️ 技术标签分类</h1>
        <p class="subtitle">按技术标签聚合全站博文，点击标签即可筛选相关文章</p>
      </div>

      <!-- 标签分类卡片网格（超过 7 个自动折叠，展开卡补齐末行避免右侧留空） -->
      <section ref="tagsGridRef" class="tags-grid">
        <div
          v-for="tag in visibleTags"
          :key="tag.id"
          class="tag-card"
          :class="{ active: selectedTagId === tag.id }"
          @click="selectTag(tag.id)"
        >
          <div class="tag-header">
            <span class="tag-dot" :style="{ backgroundColor: tag.color }"></span>
            <h3 class="tag-title">{{ tag.name }}</h3>
            <span class="tag-count-badge">{{ tag.article_count || 0 }} 篇</span>
          </div>
          <p class="tag-desc">点击探索该技术标签下的全部深度博文</p>
        </div>
        <div
          v-if="tags.length > TAG_COLLAPSE_LIMIT"
          class="tag-card expand-card"
          :style="{ gridColumn: `span ${expandCardSpan}` }"
          @click="tagsExpanded = !tagsExpanded"
        >
          <div class="tag-header">
            <h3 class="tag-title">{{ tagsExpanded ? '收起标签' : `展开全部标签 (${tags.length - TAG_COLLAPSE_LIMIT})` }}</h3>
          </div>
          <p class="tag-desc">{{ tagsExpanded ? '点击收起超出部分的标签卡片' : '点击展开查看其余技术标签' }}</p>
        </div>
      </section>

      <!-- 筛选结果列表 -->
      <section class="filtered-articles-section">
        <h2 class="section-title">
          <span>{{ currentFilterTitle }}</span>
          <el-button v-if="selectedTagId !== null" size="small" text @click="resetFilter">重置筛选</el-button>
        </h2>

        <div v-if="loading" class="loading-box">
          <el-skeleton :rows="4" animated />
        </div>

        <div v-else-if="articles.length > 0" class="articles-list">
          <div
            v-for="art in articles"
            :key="art.id"
            class="article-row-card"
            @click="$router.push(`/article/${art.slug}`)"
          >
            <span class="art-title">{{ art.title }}</span>
            <span class="art-date">{{ formatDate(art.created_at) }}</span>
          </div>
        </div>

        <div v-else class="empty-box">
          <el-empty description="该标签下暂无文章" />
        </div>
      </section>
    </main>

    <AiChatDrawer />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed, nextTick } from 'vue'
import Navbar from '@/components/Navbar.vue'
import AiChatDrawer from '@/components/AiChatDrawer.vue'
import { getTagsApi } from '@/api/tag'
import { getArticlesApi } from '@/api/article'
import type { Tag, ArticleListItem } from '@/types'

const tags = ref<Tag[]>([])
const articles = ref<ArticleListItem[]>([])
const loading = ref(false)

const selectedTagId = ref<number | null>(null)
const TAG_COLLAPSE_LIMIT = 7
const tagsExpanded = ref(false)

const visibleTags = computed(() =>
  tagsExpanded.value ? tags.value : tags.value.slice(0, TAG_COLLAPSE_LIMIT)
)

const tagsGridRef = ref<HTMLElement>()
const gridColumns = ref(1)

// 网格用 repeat(auto-fit, ...) 响应式排布，列数随视口变化且只能在运行时测得。
// 展开卡按「补齐末行剩余格子」取跨度，否则末行右侧会空出一格，视觉上不对称；
// 收起状态下卡片已展示全部标签，无需补齐，只占 1 格即可。
const expandCardSpan = computed(() => {
  if (tagsExpanded.value) return 1
  const cols = gridColumns.value
  const remainder = (visibleTags.value.length + 1) % cols
  return remainder === 0 ? 1 : cols - remainder + 1
})

const measureGridColumns = async () => {
  await nextTick()
  const el = tagsGridRef.value
  if (!el) return
  const tracks = getComputedStyle(el).gridTemplateColumns.split(' ').filter(Boolean).length
  if (tracks > 0) gridColumns.value = tracks
}

const currentFilterTitle = computed(() => {
  if (selectedTagId.value) {
    const t = tags.value.find(x => x.id === selectedTagId.value)
    return `标签：${t ? t.name : ''} 下的文章`
  }
  return '全部文章归档'
})

const loadMeta = async () => {
  tags.value = await getTagsApi()
  measureGridColumns()
  loadArticles()
}

const loadArticles = async () => {
  loading.value = true
  try {
    const res = await getArticlesApi({
      tag_id: selectedTagId.value || undefined,
      size: 50
    })
    articles.value = res.list
  } finally {
    loading.value = false
  }
}

const selectTag = (id: number) => {
  selectedTagId.value = selectedTagId.value === id ? null : id
  loadArticles()
}

const resetFilter = () => {
  selectedTagId.value = null
  loadArticles()
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadMeta()
  window.addEventListener('resize', measureGridColumns)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', measureGridColumns)
})
</script>

<style scoped>
.categories-page {
  min-height: 100vh;
  background: transparent;
}

.page-container {
  max-width: 1440px;
  margin: 0 auto;
  padding: 2.5rem 2.5rem 5rem 2.5rem;
}

.page-header {
  text-align: center;
  margin-bottom: 2.5rem;
}

.title {
  font-size: 2rem;
  font-weight: 800;
  color: #18181b;
  margin: 0 0 0.5rem 0;
}

.subtitle {
  font-size: 0.95rem;
  color: #71717a;
  margin: 0;
}

.tags-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.25rem;
  margin-bottom: 3rem;
}

.tag-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
  cursor: pointer;
  transition: all 0.2s;
}

.tag-card:hover {
  transform: translateY(-2px);
  border-color: #10b981;
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.05);
}

.tag-card.active {
  border-color: #059669;
  box-shadow: 0 0 0 2px rgba(5, 150, 105, 0.15);
}

.expand-card {
  border-style: dashed;
  border-color: #10b981;
  background: #ecfdf5;
}

.expand-card .tag-title {
  color: #059669;
}

.tag-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.tag-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
}

.tag-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #18181b;
}

.tag-count-badge {
  margin-left: auto;
  font-size: 0.75rem;
  font-weight: 700;
  background: #ecfdf5;
  color: #059669;
  padding: 2px 8px;
  border-radius: 6px;
}

.tag-desc {
  font-size: 0.85rem;
  color: #71717a;
  margin: 0;
  line-height: 1.5;
}

.section-title {
  font-size: 1.25rem;
  font-weight: 800;
  color: #18181b;
  margin: 0 0 1.25rem 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.articles-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.article-row-card {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 14px 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  transition: all 0.2s;
}

.article-row-card:hover {
  border-color: #10b981;
  transform: translateX(4px);
}

.art-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #18181b;
}

.art-date {
  font-size: 0.82rem;
  color: #71717a;
}
</style>
