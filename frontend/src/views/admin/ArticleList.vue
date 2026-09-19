<template>
  <div class="article-manage-page">
    <div class="page-header-bar">
      <div>
        <h2 class="title">博文内容与知识库管理</h2>
        <p class="subtitle">管理博客发布、草稿状态并维护每篇博文的 RAG 向量切片</p>
      </div>
      <el-button type="primary" :icon="Plus" @click="$router.push('/admin/article/new')">
        撰写新博文 (AI 写作)
      </el-button>
    </div>

    <!-- 筛选搜索栏 -->
    <div class="filter-card">
      <el-input
        v-model="keyword"
        placeholder="搜索博文标题或正文关键字..."
        style="width: 320px"
        clearable
        @clear="loadArticles"
        @keydown.enter="loadArticles"
      />
      <el-button type="primary" @click="loadArticles">查询</el-button>
    </div>

    <!-- 数据表格 -->
    <div class="table-card">
      <el-table :data="articles" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="ID" width="70" align="center" />
        
        <el-table-column prop="title" label="博文标题" min-width="260">
          <template #default="{ row }">
            <span class="table-article-title" @click="$router.push(`/article/${row.slug}`)">
              {{ row.title }}
            </span>
            <el-tag v-if="row.is_top" size="small" type="danger" style="margin-left: 6px">置顶</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="category" label="分类" width="160">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.category?.name || '未分类' }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column label="向量化状态" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.vector_status === 'indexed'" size="small" type="success">
              ⚡ 向量已索引
            </el-tag>
            <el-tag v-else-if="row.vector_status === 'failed'" size="small" type="danger">
              切片失败
            </el-tag>
            <el-tag v-else size="small" type="warning">待索引</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="views_count" label="阅读/点赞" width="120" align="center">
          <template #default="{ row }">
            <span class="stat-cell">{{ row.views_count }} / {{ row.likes_count }}</span>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="创建时间" width="160" align="center">
          <template #default="{ row }">
            <span class="date-cell">{{ formatDate(row.created_at) }}</span>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="220" align="center" fixed="right">
          <template #default="{ row }">
            <el-button size="small" text type="primary" @click="$router.push(`/admin/article/edit/${row.id}`)">
              编辑
            </el-button>
            <el-button size="small" text type="warning" @click="handleReindex(row.id)">
              同步向量
            </el-button>
            <el-popconfirm title="确定要彻底删除该博文及关联向量切片吗？" @confirm="handleDelete(row.id)">
              <template #reference>
                <el-button size="small" text type="danger">删除</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-wrap">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :total="total"
          layout="total, prev, pager, next"
          @current-change="loadArticles"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Plus } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { getArticlesApi, deleteArticleApi, reindexArticleApi } from '@/api/article'
import type { ArticleListItem } from '@/types'

const articles = ref<ArticleListItem[]>([])
const loading = ref(false)
const keyword = ref('')
const currentPage = ref(1)
const pageSize = ref(10)
const total = ref(0)

const loadArticles = async () => {
  loading.value = true
  try {
    const res = await getArticlesApi({
      page: currentPage.value,
      size: pageSize.value,
      keyword: keyword.value || undefined,
      published_only: false
    })
    articles.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const handleReindex = async (id: number) => {
  try {
    const count = await reindexArticleApi(id)
    ElMessage.success(`文章切片重构成功，生成 ${count} 个向量块！`)
    loadArticles()
  } catch (e) {
    ElMessage.error('切片索引失败')
  }
}

const handleDelete = async (id: number) => {
  try {
    await deleteArticleApi(id)
    ElMessage.success('文章已彻底删除')
    loadArticles()
  } catch (e) {
    ElMessage.error('删除失败')
  }
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(() => {
  loadArticles()
})
</script>

<style scoped>
.article-manage-page {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

.page-header-bar {
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

.filter-card,
.table-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.25rem 1.5rem;
  border: 1px solid #e4e4e7;
}

.filter-card {
  display: flex;
  align-items: center;
  gap: 12px;
}

.table-article-title {
  font-weight: 600;
  color: #18181b;
  cursor: pointer;
}

.table-article-title:hover {
  color: #059669;
}

.stat-cell,
.date-cell {
  font-size: 0.82rem;
  color: #71717a;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.25rem;
}
</style>
