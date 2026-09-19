<template>
  <div class="category-tag-page">
    <div class="page-title-row">
      <h2 class="title">分类与标签体系运维</h2>
      <p class="subtitle">统一归类技术文章领域，为 RAG 知识检索提供精准聚类维度</p>
    </div>

    <div class="dual-columns-grid">
      <!-- 左列：分类管理 -->
      <div class="section-card">
        <div class="card-header">
          <h3 class="card-title">📁 分类体系</h3>
          <el-button size="small" type="primary" :icon="Plus" @click="openCatModal()">添加分类</el-button>
        </div>

        <el-table :data="categories" stripe style="width: 100%">
          <el-table-column prop="name" label="分类名称" min-width="140" />
          <el-table-column prop="slug" label="别名 Slug" width="120" />
          <el-table-column prop="article_count" label="博文数" width="80" align="center" />
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openCatModal(row)">编辑</el-button>
              <el-popconfirm title="确定删除该分类？" @confirm="deleteCat(row.id)">
                <template #reference>
                  <el-button size="small" text type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- 右列：标签管理 -->
      <div class="section-card">
        <div class="card-header">
          <h3 class="card-title">🏷️ 标签库</h3>
          <el-button size="small" type="primary" :icon="Plus" @click="openTagModal()">添加标签</el-button>
        </div>

        <el-table :data="tags" stripe style="width: 100%">
          <el-table-column label="标签" min-width="140">
            <template #default="{ row }">
              <el-tag :color="row.color + '20'" :style="{ color: row.color, borderColor: row.color }">
                {{ row.name }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="slug" label="标识别名" width="120" />
          <el-table-column prop="article_count" label="博文数" width="80" align="center" />
          <el-table-column label="操作" width="120" align="center">
            <template #default="{ row }">
              <el-button size="small" text type="primary" @click="openTagModal(row)">编辑</el-button>
              <el-popconfirm title="确定删除该标签？" @confirm="deleteTag(row.id)">
                <template #reference>
                  <el-button size="small" text type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 分类弹窗 -->
    <el-dialog v-model="catModalVisible" :title="currentCat?.id ? '编辑分类' : '新建分类'" width="420px">
      <el-form label-position="top">
        <el-form-item label="分类名称 *">
          <el-input v-model="catForm.name" placeholder="例如：大模型架构" />
        </el-form-item>
        <el-form-item label="别名 Slug *">
          <el-input v-model="catForm.slug" placeholder="例如：llm-architecture" />
        </el-form-item>
        <el-form-item label="分类描述">
          <el-input v-model="catForm.description" type="textarea" placeholder="简要描述..." />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="catModalVisible = false">取消</el-button>
        <el-button type="primary" @click="saveCat">保存</el-button>
      </template>
    </el-dialog>

    <!-- 标签弹窗 -->
    <el-dialog v-model="tagModalVisible" :title="currentTag?.id ? '编辑标签' : '新建标签'" width="420px">
      <el-form label-position="top">
        <el-form-item label="标签名称 *">
          <el-input v-model="tagForm.name" placeholder="例如：Transformer" />
        </el-form-item>
        <el-form-item label="别名 Slug *">
          <el-input v-model="tagForm.slug" placeholder="例如：transformer" />
        </el-form-item>
        <el-form-item label="展示色彩">
          <el-color-picker
            v-model="tagForm.color"
            :predefine="['#059669', '#10b981', '#18181b', '#3f3f46', '#d97706', '#ea580c', '#dc2626']"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="tagModalVisible = false">取消</el-button>
        <el-button type="primary" @click="saveTag">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getCategoriesApi, createCategoryApi, updateCategoryApi, deleteCategoryApi } from '@/api/category'
import { getTagsApi, createTagApi, updateTagApi, deleteTagApi } from '@/api/tag'
import type { Category, Tag } from '@/types'

const categories = ref<Category[]>([])
const tags = ref<Tag[]>([])

const catModalVisible = ref(false)
const currentCat = ref<Category | null>(null)
const catForm = ref({ name: '', slug: '', description: '' })

const tagModalVisible = ref(false)
const currentTag = ref<Tag | null>(null)
const tagForm = ref({ name: '', slug: '', color: '#059669' })

const loadData = async () => {
  const [cats, tgs] = await Promise.all([getCategoriesApi(), getTagsApi()])
  categories.value = cats
  tags.value = tgs
}

const openCatModal = (cat?: Category) => {
  currentCat.value = cat || null
  if (cat) {
    catForm.value = { name: cat.name, slug: cat.slug, description: cat.description || '' }
  } else {
    catForm.value = { name: '', slug: '', description: '' }
  }
  catModalVisible.value = true
}

const saveCat = async () => {
  if (!catForm.value.name || !catForm.value.slug) {
    ElMessage.warning('请填写名称与别名')
    return
  }
  if (currentCat.value) {
    await updateCategoryApi(currentCat.value.id, catForm.value)
    ElMessage.success('分类已更新')
  } else {
    await createCategoryApi(catForm.value)
    ElMessage.success('分类已创建')
  }
  catModalVisible.value = false
  loadData()
}

const deleteCat = async (id: number) => {
  await deleteCategoryApi(id)
  ElMessage.success('分类已删除')
  loadData()
}

const openTagModal = (tag?: Tag) => {
  currentTag.value = tag || null
  if (tag) {
    tagForm.value = { name: tag.name, slug: tag.slug, color: tag.color }
  } else {
    tagForm.value = { name: '', slug: '', color: '#059669' }
  }
  tagModalVisible.value = true
}

const saveTag = async () => {
  if (!tagForm.value.name || !tagForm.value.slug) {
    ElMessage.warning('请填写标签名称与别名')
    return
  }
  if (currentTag.value) {
    await updateTagApi(currentTag.value.id, tagForm.value)
    ElMessage.success('标签已更新')
  } else {
    await createTagApi(tagForm.value)
    ElMessage.success('标签已创建')
  }
  tagModalVisible.value = false
  loadData()
}

const deleteTag = async (id: number) => {
  await deleteTagApi(id)
  ElMessage.success('标签已删除')
  loadData()
}

onMounted(() => {
  loadData()
})
</script>

<style scoped>
.category-tag-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
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

.dual-columns-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
}

.section-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 1.25rem;
}

.card-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 700;
  color: #18181b;
}
</style>
