<template>
  <div class="write-page" :class="{ 'is-embedded': embedded }">
    <Navbar v-if="!embedded" />

    <main class="write-container">
      <div class="write-card">
        <div class="write-header">
          <h2 class="write-title">{{ editId !== null ? '📝 编辑博文' : '✍️ 写一篇新博文' }}</h2>
        </div>

        <el-form label-position="top" class="write-form">
          <el-form-item label="文章标题 *">
            <el-input
              v-model="form.title"
              size="large"
              placeholder="起一个清晰有吸引力的标题"
              maxlength="255"
            />
          </el-form-item>

          <el-form-item label="技术标签">
            <el-select
              v-model="form.tag_ids"
              multiple
              placeholder="可多选标签"
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

          <el-form-item label="文章摘要">
            <el-input
              v-model="form.summary"
              type="textarea"
              :rows="2"
              placeholder="简要描述博文核心内容 (将展示在搜索结果列表中，可留空)"
            />
          </el-form-item>

          <el-row :gutter="16">
            <el-col :span="14">
              <el-form-item label="发布设置">
                <div class="switch-row">
                  <div class="public-switch">
                    <span class="switch-label">公开发布</span>
                    <el-switch v-model="form.is_published" />
                    <span class="switch-hint">{{ form.is_published ? '发布后出现在首页与检索中' : '未发布，仅自己在个人主页可见' }}</span>
                  </div>
                  <div class="visibility-opts">
                    <el-checkbox v-model="form.is_private" title="勾选后不进入首页、标签页与 AI 知识库，仅你本人可访问">
                      仅自己可见
                    </el-checkbox>
                    <el-checkbox v-if="userStore.isAdmin" v-model="form.is_manual_top">置顶精选</el-checkbox>
                  </div>
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <el-form-item label="正文内容 *">
            <el-tabs v-model="activeTab" type="border-card" class="editor-tabs">
              <el-tab-pane label="✏️ 编辑 Markdown" name="edit">
                <el-input
                  v-model="form.content"
                  type="textarea"
                  :rows="18"
                  placeholder="支持全套标准 Markdown 语法、代码块与数学公式"
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

          <div class="write-actions">
            <el-button class="uniform-btn" @click="router.back()">取消</el-button>
            <el-button
              class="uniform-btn"
              :loading="saving"
              :disabled="loadingArticle || !form.title.trim() || !form.content.trim()"
              @click="handleSave(false)"
            >
              保存
            </el-button>
            <el-button
              class="uniform-btn"
              :loading="saving"
              :disabled="loadingArticle || !form.title.trim() || !form.content.trim()"
              @click="handleSave(true)"
            >
              发布
            </el-button>
          </div>
        </el-form>
      </div>
    </main>

    <AiChatDrawer />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import Navbar from '@/components/Navbar.vue'
import AiChatDrawer from '@/components/AiChatDrawer.vue'
import MarkdownViewer from '@/components/MarkdownViewer.vue'
import { getTagsApi } from '@/api/tag'
import { createArticleApi, updateArticleApi, getArticleDetailApi } from '@/api/article'
import { useUserStore } from '@/stores/user'
import type { Tag } from '@/types'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()

// 同一页面承担新建与编辑：/write 与 /write/:id
const editId = computed(() => (route.params.id ? Number(route.params.id) : null))
// 后台侧栏内嵌复用同一组件时不再渲染门户导航栏
const embedded = computed(() => !!route.meta.embedded)

const tags = ref<Tag[]>([])
const saving = ref(false)
const loadingArticle = ref(false)
const activeTab = ref('edit')

const form = ref({
  title: '',
  tag_ids: [] as number[],
  summary: '',
  content: '',
  is_published: true,
  is_private: false,
  is_manual_top: false
})

const handleSave = async (publish: boolean) => {
  if (!form.value.title.trim() || !form.value.content.trim()) {
    ElMessage.warning('文章标题与正文不可为空')
    return
  }

  saving.value = true
  try {
    // slug 不接受手填：新建按时间戳生成保证唯一，编辑保持原 slug 不变
    const saved = editId.value !== null
      ? await updateArticleApi(editId.value, { ...form.value, is_published: publish })
      : await createArticleApi({ ...form.value, is_published: publish, slug: 'art-' + Date.now() })

    // 以服务端返回的落库结果为准组织提示，避免开关组合下说错话
    if (!saved.is_published) {
      ElMessage.success('已保存为未发布草稿，仅自己在个人主页可见')
    } else if (saved.is_private) {
      ElMessage.success('已发布，但仅自己可见：不进首页、检索与 AI 知识库')
    } else {
      ElMessage.success('博文公开发布成功，已自动切片并写入 RAG 知识库！')
    }
    // 后台内嵌时留在管理壳子里回列表，门户内则直接进正文
    if (embedded.value) router.push('/admin/articles')
    else router.push(`/article/${saved.slug}`)
  } catch {
    ElMessage.error('保存失败，请稍后重试')
  } finally {
    saving.value = false
  }
}

onMounted(async () => {
  try {
    tags.value = await getTagsApi()
  } catch {
    // 标签加载失败不阻塞写作
  }

  if (editId.value === null) return
  loadingArticle.value = true
  try {
    const a = await getArticleDetailApi(editId.value)
    form.value = {
      title: a.title,
      tag_ids: a.tags.map(t => t.id),
      summary: a.summary || '',
      content: a.content,
      is_published: a.is_published,
      is_private: a.is_private,
      is_manual_top: a.is_manual_top
    }
  } catch {
    ElMessage.error('博文加载失败，或你没有该文章的编辑权限')
  } finally {
    loadingArticle.value = false
  }
})
</script>

<style scoped>
.write-page {
  min-height: 100vh;
  background: transparent;
}

/* 后台侧栏内嵌时由 .admin-page-content 提供高度与留白 */
.write-page.is-embedded {
  min-height: auto;
}

.write-page.is-embedded .write-container {
  padding: 1.5rem;
}

/* 页面大小与首页/搜索页对齐 */
.write-container {
  max-width: 1520px;
  margin: 0 auto;
  padding: 2.25rem 2.5rem 5rem 2.5rem;
  display: flex;
  justify-content: center;
}

.write-card {
  width: 100%;
  max-width: 1080px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 14px;
  padding: 28px 36px 36px 36px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.write-header {
  display: flex;
  align-items: baseline;
  gap: 14px;
  margin-bottom: 8px;
}

.write-title {
  margin: 0;
  font-size: 1.4rem;
  font-weight: 800;
  color: #18181b;
  letter-spacing: -0.4px;
}

.editor-tabs {
  width: 100%;
  border-radius: 8px;
  overflow: hidden;
}

.code-textarea :deep(.el-textarea__inner) {
  font-family: 'JetBrains Mono', Consolas, Monaco, monospace;
  font-size: 0.86rem;
  line-height: 1.7;
}

.preview-panel {
  min-height: 380px;
  padding: 4px 8px;
}

.write-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding-top: 8px;
}

/* 两个操作按钮统一尺寸：白底、同高同宽 */
.uniform-btn {
  min-width: 128px;
  height: 38px;
  background: #ffffff;
  border: 1px solid #d4d4d8;
  color: #18181b;
  font-weight: 600;
}

.uniform-btn:hover {
  background: #f4f4f5;
  border-color: #18181b;
  color: #18181b;
}

.uniform-btn.is-disabled {
  background: #fafafa;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 20px;
  height: 32px;
  flex-wrap: wrap;
}

.public-switch {
  display: flex;
  align-items: center;
  gap: 8px;
}

.visibility-opts {
  display: flex;
  align-items: center;
  gap: 16px;
}

.switch-label {
  font-size: 0.86rem;
  color: #18181b;
}

.switch-hint {
  font-size: 0.74rem;
  color: #a1a1aa;
}
</style>
