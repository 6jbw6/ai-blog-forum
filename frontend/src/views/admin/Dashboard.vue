<template>
  <div class="dashboard-page">
    <div class="page-title-row">
      <div>
        <h2 class="page-title">运营看板</h2>
      </div>
      <el-button type="primary" :loading="loading" @click="loadData(true)">
        {{ loading ? '正在刷新…' : '刷新实时数据' }}
      </el-button>
    </div>

    <!-- 指标卡片网格 -->
    <section class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon-wrap icon-dark">📝</div>
        <div class="metric-info">
          <span class="metric-label">已发布博文总数</span>
          <span class="metric-value">{{ stats?.metrics.published_articles || 0 }}</span>
        </div>
      </div>

      <div class="metric-card card-ai-highlight">
        <div class="metric-icon-wrap icon-emerald">⚡</div>
        <div class="metric-info">
          <span class="metric-label">RAG 向量切片知识库</span>
          <span class="metric-value text-emerald">{{ stats?.metrics.rag_chunks_indexed || 0 }}</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon-wrap icon-green">👁️</div>
        <div class="metric-info">
          <span class="metric-label">全站总阅读浏览量</span>
          <span class="metric-value">{{ stats?.metrics.total_views || 0 }}</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon-wrap icon-pink">💬</div>
        <div class="metric-info">
          <span class="metric-label">读者评论互动</span>
          <span class="metric-value">{{ stats?.metrics.total_comments || 0 }}</span>
        </div>
      </div>
    </section>

    <!-- 热门文章排行（全宽） -->
    <div class="panel-card">
      <h3 class="panel-title">🔥 知识库最受关注博文 Top5</h3>
      <el-table :data="stats?.top_articles || []" stripe style="width: 100%">
        <el-table-column prop="title" label="博文标题" min-width="260">
          <template #default="{ row }">
            <span class="hot-title" title="点击查看博文" @click="$router.push(`/article/${row.slug}`)">
              {{ row.title }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="views" label="阅读量" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.views }} 次</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="likes" label="点赞数" width="100" align="center">
          <template #default="{ row }">
            <el-tag size="small" type="danger">{{ row.likes }} 赞</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getDashboardStatsApi, type DashboardStats } from '@/api/stats'

const stats = ref<DashboardStats | null>(null)
const loading = ref(false)

const loadData = async (showToast = false) => {
  loading.value = true
  try {
    stats.value = await getDashboardStatsApi()
    // 仅手动点击「刷新实时数据」时提示，进入页面静默加载
    if (showToast) {
      ElMessage.success('数据已刷新')
    }
  } catch (e: any) {
    ElMessage.error(e?.message || '刷新失败，请稍后重试')
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadData(false)
})
</script>

<style scoped>
.dashboard-page {
  display: flex;
  flex-direction: column;
  gap: 1.75rem;
}

.page-title-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.page-title {
  margin: 0;
  font-size: 1.45rem;
  font-weight: 800;
  color: #18181b;
}

.page-subtitle {
  margin: 4px 0 0 0;
  font-size: 0.85rem;
  color: #71717a;
}

.metrics-grid {
  display: grid;
  /* minmax(0, 1fr)：轨道可收缩到 0，避免内部 el-table 写死的像素宽度把轨道顶宽导致右侧内容被裁 */
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1.25rem;
}

.metric-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
  display: flex;
  align-items: center;
  gap: 1.25rem;
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.02);
  min-width: 0;
}

.card-ai-highlight {
  border-color: #a7f3d0;
  background: linear-gradient(135deg, #ffffff 0%, #ecfdf5 100%);
}

.metric-icon-wrap {
  width: 52px;
  height: 52px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.5rem;
}

.icon-dark { background: #f4f4f5; color: #18181b; }
.icon-emerald { background: #ecfdf5; color: #059669; }
.icon-green { background: #ecfdf5; }
.icon-pink { background: #fff1f2; }

.metric-info {
  display: flex;
  flex-direction: column;
}

.metric-label {
  font-size: 0.82rem;
  color: #71717a;
  font-weight: 500;
}

.metric-value {
  font-size: 1.6rem;
  font-weight: 800;
  color: #18181b;
  margin: 2px 0;
}

.text-emerald {
  color: #059669;
}

.metric-sub {
  font-size: 0.75rem;
  color: #71717a;
}

.panel-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
  min-width: 0;
}

.panel-title {
  margin: 0 0 1.25rem 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #18181b;
}

.hot-title {
  font-weight: 600;
  color: #18181b;
  cursor: pointer;
  transition: color 0.2s ease;
}

.hot-title:hover {
  color: #059669;
}
</style>
