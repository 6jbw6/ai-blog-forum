<template>
  <div class="tag-manage-page">
    <div class="page-title-row">
      <h2 class="title">标签库</h2>
    </div>

    <div class="section-card">
      <div class="card-header">
        <h3 class="card-title">🏷️ 标签库</h3>
        <el-button type="primary" :icon="Plus" @click="openTagModal()">添加标签</el-button>
      </div>

      <el-table :data="tags" stripe style="width: 100%">
        <el-table-column label="标签" min-width="140">
          <template #default="{ row }">
            <el-tag :color="row.color + '20'" :style="{ color: row.color, borderColor: row.color }">
              {{ row.name }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="article_count" label="博文数" width="80" align="center" />
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <div class="row-actions">
              <el-button size="small" text type="primary" @click="openTagModal(row)">编辑</el-button>
              <el-popconfirm title="确定删除该标签？" hide-icon @confirm="deleteTag(row.id)">
                <template #reference>
                  <el-button size="small" text type="danger">删除</el-button>
                </template>
              </el-popconfirm>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog
      v-model="tagModalVisible"
      :title="currentTag?.id ? '编辑标签' : '新建标签'"
      width="420px"
      :lock-scroll="false"
    >
      <el-form label-position="top">
        <el-form-item label="标签名称 *">
          <el-input v-model="tagForm.name" placeholder="例如：Transformer" />
        </el-form-item>
        <el-form-item label="展示色彩">
          <!-- 全部可选颜色直接铺开，点一下即选中；不再提供自由取色，保证同一名称只有一种颜色 -->
          <div class="color-palette">
            <button
              v-for="c in TAG_COLOR_PALETTE"
              :key="c"
              type="button"
              class="color-swatch"
              :class="{ active: tagForm.color.toUpperCase() === c.toUpperCase() }"
              :style="{ background: c }"
              :title="c"
              @click="tagForm.color = c"
            />
          </div>
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
import { DEFAULT_TAG_COLOR, TAG_COLOR_PALETTE } from '@/utils/colorPalette'
import type { Tag } from '@/types'

const tags = ref<Tag[]>([])
const tagModalVisible = ref(false)
const currentTag = ref<Tag | null>(null)
const tagForm = ref({ name: '', color: DEFAULT_TAG_COLOR })

const loadData = async () => {
  tags.value = await getTagsApi()
}

const openTagModal = (tag?: Tag) => {
  currentTag.value = tag || null
  if (tag) {
    tagForm.value = { name: tag.name, color: tag.color }
  } else {
    tagForm.value = { name: '', color: DEFAULT_TAG_COLOR }
  }
  tagModalVisible.value = true
}

const saveTag = async () => {
  const name = tagForm.value.name.trim()
  if (!name) {
    ElMessage.warning('请填写标签名称')
    return
  }
  // 一个名称只能有一种颜色：同名标签（忽略大小写与首尾空格）直接拦下，避免出现两个同名不同色
  const duplicated = tags.value.find(
    t => t.name.trim().toLowerCase() === name.toLowerCase() && t.id !== currentTag.value?.id
  )
  if (duplicated) {
    ElMessage.warning(`标签「${duplicated.name}」已存在，同一名称只能保留一种颜色`)
    return
  }
  tagForm.value.name = name
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

/* 展示色彩：色板全部铺开（58 色），点一下即选中，当前色带描边高亮 */
.color-palette {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  width: 100%;
}

.color-swatch {
  width: 22px;
  height: 22px;
  padding: 0;
  border-radius: 5px;
  border: 1px solid rgba(24, 24, 27, 0.12);
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}

.color-swatch:hover {
  transform: translateY(-1px);
  box-shadow: 0 2px 6px rgba(24, 24, 27, 0.18);
}

.color-swatch.active {
  outline: 2px solid #18181b;
  outline-offset: 1px;
}

/* 操作列：两个按钮同一行居中，禁止换行，避免换行后按钮被外边距顶偏 */
.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}

/* 相邻按钮默认的 12px 左外边距在 flex 下会造成偏右，改由 gap 统一控制间距 */
.row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}
</style>
