<template>
  <div class="tag-manage-page">
    <div class="page-title-row">
      <h2 class="title">标签库运维</h2>
      <p class="subtitle">统一维护技术标签，为博文的聚合检索与 RAG 知识聚类提供维度</p>
    </div>

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
import { getTagsApi, createTagApi, updateTagApi, deleteTagApi } from '@/api/tag'
import type { Tag } from '@/types'

const tags = ref<Tag[]>([])
const tagModalVisible = ref(false)
const currentTag = ref<Tag | null>(null)
const tagForm = ref({ name: '', slug: '', color: '#059669' })

const loadData = async () => {
  tags.value = await getTagsApi()
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
.tag-manage-page {
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
