<template>
  <div class="admin-layout">
    <!-- 侧边栏 -->
    <aside class="admin-sidebar">
      <div class="sidebar-brand">
        <img src="/logo.png" alt="AI博客论坛 Logo" class="brand-icon" />
        <div class="brand-info">
          <span class="brand-name">AI博客论坛</span>
          <span class="brand-tag">{{ userStore.isAdmin ? '管理中台' : '创作者中心' }}</span>
        </div>
      </div>

      <nav class="sidebar-menu">
        <router-link v-if="userStore.isAdmin" to="/admin/dashboard" class="menu-link">
          <el-icon><DataAnalysis /></el-icon>
          <span>运营看板</span>
        </router-link>

        <router-link v-if="userStore.isAdmin" to="/admin/articles" class="menu-link">
          <el-icon><Document /></el-icon>
          <span>文章管理</span>
        </router-link>

        <router-link to="/admin/write" class="menu-link">
          <el-icon><EditPen /></el-icon>
          <span>写作</span>
        </router-link>

        <router-link v-if="userStore.isAdmin" to="/admin/tags" class="menu-link">
          <el-icon><PriceTag /></el-icon>
          <span>标签库</span>
        </router-link>

        <router-link v-if="userStore.isAdmin" to="/admin/comments" class="menu-link">
          <el-icon><ChatLineSquare /></el-icon>
          <span>评论审核</span>
        </router-link>

        <router-link v-if="userStore.isAdmin" to="/admin/ai-settings" class="menu-link">
          <el-icon><Cpu /></el-icon>
          <span>AI 引擎与大模型设置</span>
        </router-link>
      </nav>
    </aside>

    <!-- 右侧主体内容 -->
    <div class="admin-main-wrap">
      <!-- 顶栏 -->
      <header class="admin-topbar">
        <div class="topbar-left">
          <span class="page-current-title">{{ userStore.isAdmin ? '企业级控制台 · 权限管理中枢' : 'AI 博客论坛 · 创作者中心' }}</span>
        </div>

        <div class="topbar-right">
          <el-tag type="success" effect="light" round>
            🟢 MySQL 8.0 运行中
          </el-tag>
          <el-tag type="success" effect="plain" round>
            ⚡ 向量知识库就绪
          </el-tag>

          <el-dropdown trigger="click">
            <div class="admin-profile-pill">
              <el-avatar :size="30" :src="userStore.user?.avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=admin'" />
              <span class="admin-nickname">{{ userStore.user?.nickname || '管理员' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="profileModalRef?.open()">
                  <el-icon><Setting /></el-icon> 个人资料
                </el-dropdown-item>
                <el-dropdown-item @click="$router.push('/')">
                  <el-icon><HomeFilled /></el-icon> 返回博客首页
                </el-dropdown-item>
                <el-dropdown-item divided @click="handleLogout">
                  <el-icon><SwitchButton /></el-icon> 退出登录
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </header>

      <!-- 动态路由页面内容 -->
      <main class="admin-page-content">
        <router-view />
      </main>
    </div>

    <!-- 个人资料弹窗 -->
    <UserProfileModal ref="profileModalRef" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  DataAnalysis,
  Document,
  EditPen,
  PriceTag,
  ChatLineSquare,
  Cpu,
  Setting,
  HomeFilled,
  SwitchButton
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import UserProfileModal from '@/components/UserProfileModal.vue'

const router = useRouter()
const userStore = useUserStore()
const profileModalRef = ref<InstanceType<typeof UserProfileModal> | null>(null)

const handleLogout = () => {
  userStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.admin-layout {
  min-height: 100vh;
  display: flex;
  background: transparent;
}

.admin-sidebar {
  width: 260px;
  background: #18181b;
  color: #ffffff;
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 0;
  bottom: 0;
  left: 0;
  z-index: 100;
  border-right: 1px solid #27272a;
}

.sidebar-brand {
  height: 64px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 1.5rem;
  border-bottom: 1px solid #27272a;
}

.brand-icon {
  width: 34px;
  height: 34px;
  border-radius: 9px;
  object-fit: cover;
}

.brand-info {
  display: flex;
  flex-direction: column;
}

.brand-name {
  font-size: 1.15rem;
  font-weight: 800;
  color: #ffffff;
}

.brand-tag {
  font-size: 0.7rem;
  color: #71717a;
}

.sidebar-menu {
  flex: 1;
  padding: 1.25rem 0.75rem;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.menu-link {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 8px;
  color: #a1a1aa;
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.2s;
}

.menu-link:hover {
  background: #27272a;
  color: #ffffff;
}

.menu-link.router-link-active {
  background: #27272a;
  color: #10b981;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.admin-main-wrap {
  flex: 1;
  margin-left: 260px;
  display: flex;
  flex-direction: column;
  min-height: 100vh;
}

.admin-topbar {
  height: 64px;
  background: rgba(255, 255, 255, 0.88);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(228, 228, 231, 0.8);
  padding: 0 2rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 90;
}

.page-current-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: #18181b;
}

.topbar-right {
  display: flex;
  align-items: center;
  gap: 16px;
}

.admin-profile-pill {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px 10px;
  border-radius: 20px;
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
}

.admin-nickname {
  font-size: 0.85rem;
  font-weight: 600;
  color: #18181b;
}

.admin-page-content {
  flex: 1;
  padding: 2rem;
}
</style>
