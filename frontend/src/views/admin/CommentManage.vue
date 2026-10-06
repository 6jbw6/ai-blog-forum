<template>
  <div class="comments-manage-page">
    <div class="page-title-row">
      <h2 class="title">评论审核</h2>
    </div>

    <div class="table-card">
      <el-table
        :data="comments"
        stripe
        v-loading="loading"
        style="width: 100%"
        empty-text="暂未发现违规评论，全部评论均合规"
      >
        <el-table-column label="ID" width="70" align="center">
          <template #default="{ $index }">
            {{ (page - 1) * size + $index + 1 }}
          </template>
        </el-table-column>
        
        <el-table-column label="评论人" width="180">
          <template #default="{ row }">
            <div class="commenter-cell">
              <el-avatar :size="28" :src="row.user_avatar || '/user-avatar.svg'" />
              <div>
                <div class="name">{{ row.user_name }}</div>
                <div class="email">{{ row.user_email }}</div>
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column prop="content" label="评论正文" min-width="240">
          <template #default="{ row }">
            <p class="comment-content-cell">{{ row.content }}</p>
          </template>
        </el-table-column>

        <el-table-column label="所属文章" min-width="200">
          <template #default="{ row }">
            <span
              v-if="row.article_slug"
              class="article-link"
              title="点击查看博文"
              @click="$router.push(`/article/${row.article_slug}`)"
            >
              {{ row.article_title }}
            </span>
            <span v-else class="article-link muted">文章已删除</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="时间" width="160" align="center">
          <template #default="{ row }">
            <span class="date-text">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="100" align="center">
          <template #default="{ row }">
            <el-popconfirm title="确定彻底删除此评论？" hide-icon @confirm="deleteComment(row.id)">
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="size"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadComments"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getAdminCommentsApi, deleteCommentApi } from '@/api/comment'
import type { Comment } from '@/types'

const comments = ref<Comment[]>([])
const loading = ref(false)
const page = ref(1)
const size = ref(10)
const total = ref(0)

const loadComments = async () => {
  loading.value = true
  try {
    const res = await getAdminCommentsApi({ page: page.value, size: size.value })
    comments.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const deleteComment = async (id: number) => {
  try {
    await deleteCommentApi(id)
    ElMessage.success('评论已彻底删除')
    loadComments()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

onMounted(() => {
  loadComments()
})
</script>

<style scoped>
.comments-manage-page {
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

.table-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
}

.commenter-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.commenter-cell .name {
  font-weight: 600;
  font-size: 0.85rem;
  color: #18181b;
}

.commenter-cell .email {
  font-size: 0.75rem;
  color: #71717a;
}

.comment-content-cell {
  margin: 0;
  font-size: 0.85rem;
  color: #27272a;
  line-height: 1.5;
}

.article-link {
  font-size: 0.82rem;
  font-weight: 600;
  color: #18181b;
  cursor: pointer;
  transition: color 0.2s ease;
}

.article-link:hover {
  color: #059669;
}

.article-link.muted {
  color: #a1a1aa;
  font-weight: 400;
  cursor: default;
}

.date-text {
  font-size: 0.8rem;
  color: #71717a;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.25rem;
}
</style>
