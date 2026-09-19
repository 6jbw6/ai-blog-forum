<template>
  <div class="dashboard-page">
    <div class="page-title-row">
      <div>
        <h2 class="page-title">系统运营与知识库大屏</h2>
        <p class="page-subtitle">实时监控博文吞吐、RAG 向量特征索引及读者互动数据</p>
      </div>
      <el-button type="primary" @click="loadData">刷新实时数据</el-button>
    </div>

    <!-- 指标卡片网格 -->
    <section class="metrics-grid">
      <div class="metric-card">
        <div class="metric-icon-wrap icon-dark">📝</div>
        <div class="metric-info">
          <span class="metric-label">已发布博文总数</span>
          <span class="metric-value">{{ stats?.metrics.published_articles || 0 }}</span>
          <span class="metric-sub">草稿箱: {{ stats?.metrics.draft_articles || 0 }} 篇</span>
        </div>
      </div>

      <div class="metric-card card-ai-highlight">
        <div class="metric-icon-wrap icon-emerald">⚡</div>
        <div class="metric-info">
          <span class="metric-label">RAG 向量切片知识库</span>
          <span class="metric-value text-emerald">{{ stats?.metrics.rag_chunks_indexed || 0 }}</span>
          <span class="metric-sub">TF-IDF 词法特征向量就绪</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon-wrap icon-green">👁️</div>
        <div class="metric-info">
          <span class="metric-label">全站总阅读浏览量</span>
          <span class="metric-value">{{ stats?.metrics.total_views || 0 }}</span>
          <span class="metric-sub">PV 累计防刷统计</span>
        </div>
      </div>

      <div class="metric-card">
        <div class="metric-icon-wrap icon-pink">💬</div>
        <div class="metric-info">
          <span class="metric-label">读者评论互动</span>
          <span class="metric-value">{{ stats?.metrics.total_comments || 0 }}</span>
          <span class="metric-sub">点赞数: {{ stats?.metrics.total_likes || 0 }} 次</span>
        </div>
      </div>
    </section>

    <!-- 中间区域：技术架构指标 + 热门博文 -->
    <div class="dashboard-split-grid">
      <!-- 热门文章排行 -->
      <div class="panel-card">
        <h3 class="panel-title">🔥 知识库最受关注博文 Top 5</h3>
        <el-table :data="stats?.top_articles || []" stripe style="width: 100%">
          <el-table-column prop="title" label="博文标题" min-width="260">
            <template #default="{ row }">
              <span class="hot-title">{{ row.title }}</span>
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

      <!-- 企业级架构指标卡片 -->
      <div class="panel-card">
        <h3 class="panel-title">🛡️ 企业级工程与 AI 技术栈指标</h3>
        <div class="tech-stack-list">
          <div class="tech-item">
            <span class="tech-label">后端核心框架</span>
            <span class="tech-val">Python 3.13 + FastAPI (异步高并发)</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">数据库持久化</span>
            <span class="tech-val">MySQL 8.0 (InnoDB + 索引覆盖优化)</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">向量检索算法</span>
            <span class="tech-val">TF-IDF 词法向量 + 余弦相似度 + BM25 多路重排 + 覆盖率门控</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">交互传输协议</span>
            <span class="tech-val">SSE (Server-Sent Events) 打字机流式推送</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">前端工程框架</span>
            <span class="tech-val">Vue 3 + Vite + TypeScript + Pinia</span>
          </div>
          <div class="tech-item">
            <span class="tech-label">鉴权与安全</span>
            <span class="tech-val">JWT 无状态令牌 + Bcrypt 加盐哈希 + RBAC</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getDashboardStatsApi, type DashboardStats } from '@/api/stats'

const stats = ref<DashboardStats | null>(null)

const loadData = async () => {
  const data = await getDashboardStatsApi()
  stats.value = data
}

onMounted(() => {
  loadData()
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
  grid-template-columns: repeat(4, 1fr);
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

.dashboard-split-grid {
  display: grid;
  grid-template-columns: 1.2fr 1fr;
  gap: 1.5rem;
}

.panel-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
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
}

.tech-stack-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.tech-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #f4f4f5;
  border-radius: 8px;
  border: 1px solid #e4e4e7;
}

.tech-label {
  font-size: 0.85rem;
  font-weight: 600;
  color: #3f3f46;
}

.tech-val {
  font-size: 0.82rem;
  color: #059669;
  font-weight: 500;
}
</style>
