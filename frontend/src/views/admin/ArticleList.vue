<template>
  <div class="article-manage-page">
    <div class="page-header-bar">
      <div>
        <h2 class="title">文章管理</h2>
        <p class="subtitle">管理博客发布、草稿状态并维护每篇博文的 RAG 向量切片</p>
      </div>
    </div>

    <!-- 筛选搜索栏（与前台搜索胶囊样式一致） -->
    <div class="filter-card">
      <div class="search-capsule">
        <el-icon class="capsule-icon"><Search /></el-icon>
        <input
          v-model="keyword"
          class="capsule-input"
          type="text"
          placeholder="搜索博文标题或正文关键字"
          spellcheck="false"
          autocomplete="off"
          @keydown.enter="handleSearch"
        />
        <button class="capsule-btn" @click="handleSearch">搜索</button>
      </div>
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
          </template>
        </el-table-column>

        <el-table-column label="置顶" width="80" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.is_top" size="small" type="danger">置顶</el-tag>
            <span v-else class="cell-muted">—</span>
          </template>
        </el-table-column>

        <el-table-column label="向量化状态" width="140" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.vector_status === 'indexed'" size="small" type="success">
              已索引
            </el-tag>
            <el-tag v-else size="small" type="info">未索引</el-tag>
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

        <el-table-column label="操作" width="180" align="center" fixed="right">
          <template #default="{ row }">
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
import { Search } from '@element-plus/icons-vue'
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
      published_only: false,
      order: 'id_asc',
      // 后台管理按标题搜索：避免正文全文匹配导致结果宽泛、看似未过滤
      title_only: true
    })
    articles.value = res.list
    total.value = res.total
  } finally {
    loading.value = false
  }
}

const handleSearch = () => {
  // 新搜索从第一页开始，避免停留在超出结果范围的页码
  currentPage.value = 1
  loadArticles()
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

/* 搜索胶囊：与前台导航栏搜索框样式一致 */
.search-capsule {
  width: 380px;
  max-width: 100%;
  height: 38px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 9999px;
  padding: 0 0 0 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  transition: all 0.2s ease;
}

.search-capsule:hover,
.search-capsule:focus-within {
  border-color: #18181b;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
}

.capsule-icon {
  color: #a1a1aa;
  font-size: 15px;
  flex-shrink: 0;
}

.capsule-input {
  flex: 1;
  min-width: 0;
  border: none;
  outline: none;
  background: transparent;
  font-size: 0.88rem;
  color: #18181b;
  font-family: inherit;
}

.capsule-input::placeholder {
  color: #a1a1aa;
}

.capsule-btn {
  height: 100%;
  padding: 0 16px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #18181b;
  background: #f4f4f5;
  border: none;
  border-left: 1px solid #e4e4e7;
  border-radius: 0 9999px 9999px 0;
  cursor: pointer;
  flex-shrink: 0;
  font-family: inherit;
  transition: all 0.2s ease;
}

.capsule-btn:hover {
  background: #ffffff;
  border-left-color: #d4d4d8;
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

.cell-muted {
  color: #d4d4d8;
}

.pagination-wrap {
  display: flex;
  justify-content: flex-end;
  margin-top: 1.25rem;
}
</style>
