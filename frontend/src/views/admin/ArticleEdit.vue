<template>
  <div class="article-edit-page">
    <div class="page-header">
      <div>
        <h2 class="title">{{ isEdit ? '编辑技术博文' : '撰写新博文 (AI 协同创作)' }}</h2>
        <p class="subtitle">支持 Markdown 语法，保存时将自动执行标题感知分块并同步向量知识库</p>
      </div>
      <div class="header-buttons">
        <el-button @click="$router.push('/admin/articles')">返回列表</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">
          {{ isEdit ? '保存更新并同步向量' : '发布并自动录入知识库' }}
        </el-button>
      </div>
    </div>

    <!-- 编辑表单 -->
    <div class="edit-form-card">
      <el-form label-position="top">
        <el-row :gutter="20">
          <el-col :span="16">
            <el-form-item label="文章标题 *">
              <el-input v-model="form.title" size="large" placeholder="请输入博文标题..." />
            </el-form-item>
          </el-col>
          <el-col :span="8">
            <el-form-item label="URL 唯一别名 Slug *">
              <el-input v-model="form.slug" size="large" placeholder="例如：transformer-attention-guide" />
            </el-form-item>
          </el-col>
        </el-row>

        <el-row :gutter="20">
          <el-col :span="8">
            <el-form-item label="所属分类">
              <el-select v-model="form.category_id" placeholder="选择分类" style="width: 100%">
                <el-option
                  v-for="c in categories"
                  :key="c.id"
                  :label="c.name"
                  :value="c.id"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="10">
            <el-form-item label="技术标签">
              <el-select
                v-model="form.tag_ids"
                multiple
                placeholder="选择技术标签"
                style="width: 100%"
              >
                <el-option
                  v-for="t in tags"
                  :key="t.id"
                  :label="t.name"
                  :value="t.id"
                />
              </el-select>
            </el-form-item>
          </el-col>

          <el-col :span="6">
            <el-form-item label="发布与置顶设置">
              <div class="switch-row">
                <el-checkbox v-model="form.is_published">立即公开</el-checkbox>
                <el-checkbox v-model="form.is_top">置顶精选</el-checkbox>
              </div>
            </el-form-item>
          </el-col>
        </el-row>

        <!-- 核心 AI 特性：一键提取摘要与标签预测 -->
        <el-form-item>
          <template #label>
            <div class="summary-label-row">
              <span>文章核心摘要 TL;DR</span>
              <el-button
                size="small"
                type="primary"
                plain
                :loading="generatingAiSummary"
                @click="triggerAiSummary"
              >
                🤖 AI 一键智能提炼摘要与推荐标签
              </el-button>
            </div>
          </template>
          <el-input
            v-model="form.summary"
            type="textarea"
            :rows="3"
            placeholder="简要描述博文核心内容，也可点击右上角借助 AI 自动从正文中提炼..."
          />
        </el-form-item>

        <!-- Markdown 编辑区与实时预览 -->
        <el-form-item label="Markdown 正文内容 *">
          <el-tabs v-model="activeTab" type="border-card" class="editor-tabs">
            <el-tab-pane label="✏️ 编辑 Markdown" name="edit">
              <el-input
                v-model="form.content"
                type="textarea"
                :rows="22"
                placeholder="支持全套标准 Markdown 语法、代码块与数学公式..."
                class="code-textarea"
              />
            </el-tab-pane>
            <el-tab-pane label="👁️ 实时排版预览" name="preview">
              <div class="preview-panel">
                <MarkdownViewer :content="form.content || '*(暂无内容)*'" />
              </div>
            </el-tab-pane>
          </el-tabs>
        </el-form-item>
      </el-form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import { getCategoriesApi } from '@/api/category'
import { getTagsApi } from '@/api/tag'
import { getArticleDetailApi, createArticleApi, updateArticleApi } from '@/api/article'
import { generateSummaryApi } from '@/api/ai'
import type { Category, Tag } from '@/types'

const route = useRoute()
const router = useRouter()

const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])
const saving = ref(false)
const generatingAiSummary = ref(false)
const activeTab = ref('edit')

const isEdit = computed(() => !!route.params.id)

const form = ref({
  title: '',
  slug: '',
  category_id: undefined as number | undefined,
  tag_ids: [] as number[],
  summary: '',
  content: '',
  is_published: true,
  is_top: false
})

const loadMeta = async () => {
  const [cats, tgs] = await Promise.all([getCategoriesApi(), getTagsApi()])
  categories.value = cats
  tags.value = tgs

  if (isEdit.value) {
    const art = await getArticleDetailApi(route.params.id as string)
    form.value = {
      title: art.title,
      slug: art.slug,
      category_id: art.category?.id,
      tag_ids: art.tags.map(t => t.id),
      summary: art.summary || '',
      content: art.content,
      is_published: art.is_published,
      is_top: art.is_top
    }
  }
}

const triggerAiSummary = async () => {
  if (!form.value.content || form.value.content.length < 20) {
    ElMessage.warning('请先撰写一段正文内容，以便大模型提炼摘要')
    return
  }

  generatingAiSummary.value = true
  try {
    const res = await generateSummaryApi({
      content: form.value.content,
      title: form.value.title
    })
    form.value.summary = res.summary

    // 自动匹配推荐标签
    if (res.suggested_tags && res.suggested_tags.length > 0) {
      const matchedIds: number[] = []
      res.suggested_tags.forEach(st => {
        const found = tags.value.find(t => t.name.toLowerCase() === st.toLowerCase() || t.slug.toLowerCase() === st.toLowerCase())
        if (found && !form.value.tag_ids.includes(found.id)) {
          matchedIds.push(found.id)
        }
      })
      if (matchedIds.length > 0) {
        form.value.tag_ids = [...form.value.tag_ids, ...matchedIds]
      }
    }

    ElMessage.success('AI 成功提炼摘要并自动关联推荐标签！')
  } catch (e) {
    ElMessage.error('提炼失败，请检查 AI 引擎配置')
  } finally {
    generatingAiSummary.value = false
  }
}

const handleSave = async () => {
  if (!form.value.title.trim() || !form.value.content.trim()) {
    ElMessage.warning('文章标题与正文不可为空')
    return
  }

  // 自动根据标题生成 slug 如果未填
  if (!form.value.slug.trim()) {
    form.value.slug = 'art-' + Date.now()
  }

  saving.value = true
  try {
    if (isEdit.value) {
      await updateArticleApi(Number(route.params.id), form.value)
      ElMessage.success('博文已更新，向量特征切片已同步建立！')
    } else {
      await createArticleApi(form.value)
      ElMessage.success('博文发布成功，已自动切片并写入 RAG 知识库！')
    }
    router.push('/admin/articles')
  } finally {
    saving.value = false
  }
}

onMounted(() => {
  loadMeta()
})
</script>

<style scoped>
.article-edit-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.title {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 800;
  color: #18181b;
}

.subtitle {
  margin: 4px 0 0 0;
  font-size: 0.85rem;
  color: #71717a;
}

.header-buttons {
  display: flex;
  gap: 12px;
}

.edit-form-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 2rem;
  border: 1px solid #e4e4e7;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 16px;
  height: 40px;
}

.summary-label-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}

.editor-tabs {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
}

.code-textarea :deep(textarea) {
  font-family: "Fira Code", Consolas, Monaco, monospace;
  font-size: 0.95rem;
  line-height: 1.6;
}

.preview-panel {
  min-height: 460px;
  max-height: 600px;
  overflow-y: auto;
  padding: 1rem;
}
</style>
