<template>
  <el-dialog
    v-model="aiChatStore.isSearchOpen"
    width="680px"
    :show-close="true"
    :lock-scroll="false"
    custom-class="semantic-search-dialog"
    title="🔍 搜索"
  >
    <div class="search-modal-body">
      <!-- 检索输入框 -->
      <div class="search-input-box">
        <el-input
          v-model="searchQuery"
          size="large"
          placeholder="输入概念或自然问题，例如：显存不够如何微调？注意力缩放原理..."
          clearable
          :prefix-icon="Search"
          @keydown.enter="handleSearch"
        >
          <template #append>
            <el-button type="primary" :loading="loading" @click="handleSearch">
              搜索
            </el-button>
          </template>
        </el-input>
      </div>

      <!-- 快捷搜索推荐 -->
      <div class="search-tags-row">
        <span class="tags-label">热搜概念:</span>
        <el-tag
          v-for="kw in hotKeywords"
          :key="kw"
          class="clickable-tag"
          size="small"
          effect="plain"
          @click="quickSearch(kw)"
        >
          {{ kw }}
        </el-tag>
      </div>

      <!-- 检索结果列表 -->
      <div v-if="loading" class="search-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <div v-else-if="results.length > 0" class="search-results-list">
        <div
          v-for="item in results"
          :key="item.article_id"
          class="result-item-card"
          @click="selectArticle(item.slug)"
        >
          <div class="result-header">
            <h4 class="result-title">{{ item.title }}</h4>
            <span class="similarity-score-pill">
              相似度: {{ (item.similarity * 100).toFixed(1) }}%
            </span>
          </div>
          <p class="result-snippet" v-html="renderSnippet(item.matched_snippet)"></p>
          <div class="result-footer">
            <span class="click-hint">点击进入博文阅读全文 &rarr;</span>
          </div>
        </div>
      </div>

      <div v-else-if="searched" class="search-empty">
        <el-empty description="未检索到相似度达到阈值的博文切片，换个提问方式试试吧~" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from '@element-plus/icons-vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useAiChatStore } from '@/stores/aiChat'
import { semanticSearchApi, getHotKeywordsApi } from '@/api/ai'
import type { SemanticSearchResultItem } from '@/types'

const router = useRouter()
const aiChatStore = useAiChatStore()

const searchQuery = ref('')
const loading = ref(false)
const searched = ref(false)
const results = ref<SemanticSearchResultItem[]>([])

// 检索结果摘要净化渲染：清理 Markdown 标记并渲染 LaTeX 公式为 KaTeX
// 摘要是截断文本，只匹配成对的公式定界符，未闭合的定界符原样剥除避免漏出 $$
const renderSnippet = (raw: string): string => {
  if (!raw) return ''
  let text = raw
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')

  const maths: Array<{ tex: string; display: boolean }> = []
  const stash = (tex: string, display: boolean) => {
    const id = maths.length
    maths.push({ tex: tex.trim(), display })
    return `%%%SNIP_MATH_${id}%%%`
  }

  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, m) => stash(m, true))
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, m) => stash(m, true))
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, m) => stash(m, false))
  text = text.replace(/(?<!\$)\$([^\$\n]+?)\$(?!\$)/g, (_, m) => stash(m, false))
  text = text.replace(/(?<![a-zA-Z0-9_\\])sqrt\(([a-zA-Z0-9_]+)\)/g, (_, m) => stash(`\\sqrt{${m}}`, false))
  text = text.replace(/(?<!\\)\\sqrt\{([^}]+)\}/g, (_, m) => stash(`\\sqrt{${m}}`, false))

  // 剥除残留的未闭合公式定界符与常见 Markdown 行内标记
  text = text.replace(/\$\$/g, '').replace(/\\\[/g, '[').replace(/\\\]/g, ']')
  text = text.replace(/^#{1,6}\s*/gm, '')
  text = text.replace(/\*\*([^*]+)\*\*/g, '$1')
  text = text.replace(/`([^`]+)`/g, '$1')

  return text.replace(/%%%SNIP_MATH_(\d+)%%%/g, (_, idStr) => {
    const item = maths[Number(idStr)]
    if (!item) return ''
    try {
      return katex.renderToString(item.tex, {
        displayMode: item.display,
        throwOnError: false
      })
    } catch {
      return item.tex
    }
  })
}

const hotKeywords = ref<string[]>([
  'AI Agent 认知架构',
  'LangGraph 循环流控',
  'Multi-Agent 多智能体协同',
  'LoRA 显存优化'
])

const loadHotKeywords = async () => {
  try {
    const data = await getHotKeywordsApi(6)
    if (data && data.length > 0) {
      hotKeywords.value = data
    }
  } catch {
    // 保留默认推荐
  }
}

onMounted(() => {
  loadHotKeywords()
})

watch(() => aiChatStore.isSearchOpen, (isOpen) => {
  if (isOpen) {
    loadHotKeywords()
  }
})

const quickSearch = (kw: string) => {
  searchQuery.value = kw
  handleSearch()
}

const handleSearch = async () => {
  const q = searchQuery.value.trim()
  if (!q) return

  loading.value = true
  searched.value = true
  try {
    const data = await semanticSearchApi({ query: q, top_k: 6 })
    results.value = data
  } catch (e) {
    results.value = []
  } finally {
    loading.value = false
  }
}

const selectArticle = (slug: string) => {
  aiChatStore.closeSearch()
  router.push(`/article/${slug}`)
}
</script>

<style scoped>
.search-modal-body {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.search-tags-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  font-size: 0.85rem;
}

.tags-label {
  color: #6b7280;
  font-weight: 500;
}

.clickable-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.clickable-tag:hover {
  background: #f4f4f5;
  color: #18181b;
  border-color: #18181b;
}

.search-results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  max-height: 480px;
  overflow-y: auto;
  padding-right: 4px;
}

.result-item-card {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 10px;
  padding: 12px 16px;
  cursor: pointer;
  transition: all 0.2s;
}

.result-item-card:hover {
  border-color: #10b981;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  transform: translateY(-2px);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
}

.result-title {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 600;
  color: #18181b;
}

.similarity-score-pill {
  font-size: 0.72rem;
  font-weight: 700;
  background: #ecfdf5;
  color: #059669;
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid #a7f3d0;
}

.result-snippet {
  font-size: 0.82rem;
  color: #52525b;
  line-height: 1.5;
  margin: 0 0 6px 0;
}

.result-snippet :deep(.katex) {
  font-size: 1.02em;
}

.result-snippet :deep(.katex-display) {
  margin: 0.35em 0;
}

.result-footer {
  text-align: right;
}

.click-hint {
  font-size: 0.75rem;
  color: #059669;
  font-weight: 500;
}
</style>
