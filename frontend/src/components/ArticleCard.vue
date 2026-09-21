<template>
  <article class="post-card" :class="{ 'card-clickable': clickableCard }" @click="onCardClick">
    <div class="card-header">
      <span v-if="article.is_top" class="top-tag">📌 置顶精选</span>
      <span
        v-if="article.vector_status === 'indexed'"
        class="vector-status-tag"
        title="已拆分向量切片并录入 RAG 知识库"
      >
        ⚡ RAG 向量已索引
      </span>
      <span
        v-if="showOwnerBadge"
        class="pub-badge"
        :class="article.is_published ? 'published' : 'draft'"
      >{{ article.is_published ? '已发布' : '未发布 · 私有' }}</span>
      <span class="date-text">{{ formatDateISO(article.created_at) }}</span>
    </div>

    <h2 class="card-title" @click.stop="emit('open', article.slug)">
      {{ article.title }}
    </h2>

    <p class="card-summary">{{ article.summary || '点击阅读全文了解更多技术细节...' }}</p>

    <div class="card-footer">
      <div class="card-tags">
        <span
          v-for="t in article.tags"
          :key="t.id"
          class="article-tag"
          :style="{ color: t.color, borderColor: t.color }"
        >
          {{ t.name }}
        </span>
      </div>

      <div class="card-meta">
        <span v-if="article.author" class="meta-item author-name-meta">✍️ {{ article.author.username || article.author.nickname }}</span>
        <span class="meta-item">👁️ {{ article.views_count }}</span>
        <span class="meta-item">❤️ {{ article.likes_count }}</span>
        <span v-if="metaNote" class="meta-item">{{ metaNote }}</span>
        <button class="btn-ask-ai" @click.stop="emit('ask', article.title)">
          🤖 AI 快速答疑
        </button>
        <slot name="actions" />
      </div>
    </div>
  </article>
</template>

<script setup lang="ts">
import type { ArticleListItem } from '@/types'
import { formatDateISO } from '@/utils/date'

const props = defineProps<{
  article: ArticleListItem
  showOwnerBadge?: boolean
  clickableCard?: boolean
  metaNote?: string
}>()

const emit = defineEmits<{
  (e: 'open', slug: string): void
  (e: 'ask', title: string): void
}>()

const onCardClick = () => {
  if (props.clickableCard) emit('open', props.article.slug)
}
</script>

<style scoped>
.post-card {
  background: #ffffff;
  border-radius: 18px;
  padding: 1.75rem 2rem;
  border: 1px solid #e4e4e7;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
}

.post-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.06);
  border-color: #10b981;
}

.card-clickable {
  cursor: pointer;
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
