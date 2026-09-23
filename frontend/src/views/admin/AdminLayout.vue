<template>
  <div class="admin-layout">
    <!-- 遮罩：侧边栏展开时覆盖内容区，点击收起 -->
    <div v-if="!sidebarCollapsed" class="sidebar-mask" @click="sidebarCollapsed = true" />

    <!-- 侧边栏（浮层覆盖式，可收起） -->
    <aside class="admin-sidebar" :class="{ collapsed: sidebarCollapsed }">
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

      <div class="sidebar-footer">
        <router-link to="/" class="btn-return-portal">
          <el-icon><HomeFilled /></el-icon>
          <span>返回博客首页</span>
        </router-link>
      </div>
    </aside>

    <!-- 右侧主体内容 -->
    <div class="admin-main-wrap">
      <!-- 顶栏 -->
      <header class="admin-topbar">
        <div class="topbar-left">
          <button class="sidebar-toggle-btn" :title="sidebarCollapsed ? '展开侧边栏' : '收起侧边栏'" @click="sidebarCollapsed = !sidebarCollapsed">
            <el-icon :size="18">
              <Expand v-if="sidebarCollapsed" />
              <Fold v-else />
            </el-icon>
          </button>
          <span class="page-current-title">
            <img src="/logo.png" alt="AI博客论坛" class="topbar-logo" />
            AI博客论坛控制台
          </span>
        </div>

        <div class="topbar-right">
          <el-tag type="success" effect="light" round>
            MySQL 8.0 运行中
          </el-tag>
          <el-tag type="success" effect="plain" round>
            向量知识库就绪
          </el-tag>

          <el-dropdown trigger="click">
            <div class="admin-profile-pill">
              <el-avatar :size="30" :src="userStore.user?.avatar || '/user-avatar.svg'" />
              <span class="admin-nickname">{{ userStore.user?.nickname || '管理员' }}</span>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item @click="$router.push(`/user/${userStore.user?.id}`)">
                  <el-icon><User /></el-icon> 个人主页
                </el-dropdown-item>
                <el-dropdown-item @click="profileModalRef?.open()">
                  <el-icon><Setting /></el-icon> 个人资料
                </el-dropdown-item>
                <el-dropdown-item @click="$router.push('/admin/write')">
                  <el-icon><EditPen /></el-icon> 写作
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
  SwitchButton,
  User,
  Fold,
  Expand
} from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import UserProfileModal from '@/components/UserProfileModal.vue'

const router = useRouter()
const userStore = useUserStore()
const profileModalRef = ref<InstanceType<typeof UserProfileModal> | null>(null)

// 侧边栏折叠状态：进入控制台默认收起，仅显示图标
const sidebarCollapsed = ref(true)

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
  background: #ffffff;
  color: #18181b;
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 64px;
  bottom: 0;
  left: 0;
  z-index: 110;
  box-shadow: 8px 0 24px rgba(24, 24, 27, 0.1);
  transition: transform 0.25s ease;
  overflow: hidden;
}

/* 收起态：整体滑出屏幕左侧 */
.admin-sidebar.collapsed {
  transform: translateX(-100%);
  box-shadow: none;
}

/* 遮罩：浮层展开时压暗内容区（顶栏以下），点击收起 */
.sidebar-mask {
  position: fixed;
  top: 64px;
  inset: 64px 0 0 0;
  background: rgba(24, 24, 27, 0.35);
  z-index: 105;
  animation: mask-fade-in 0.25s ease;
}

@keyframes mask-fade-in {
  from { opacity: 0; }
  to { opacity: 1; }
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
  color: #52525b;
  text-decoration: none;
  font-size: 0.9rem;
  font-weight: 500;
  transition: all 0.25s ease;
}

.menu-link .el-icon {
  flex-shrink: 0;
}

.menu-link span {
  white-space: nowrap;
  transition: opacity 0.2s ease;
}

.menu-link:hover {
  background: #f4f4f5;
  color: #18181b;
}

.menu-link.router-link-active {
  background: #ecfdf5;
  color: #059669;
  font-weight: 600;
  box-shadow: 0 2px 8px rgba(16, 185, 129, 0.12);
}

.sidebar-footer {
  padding: 1rem 0.75rem;
}

.btn-return-portal {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  background: #f4f4f5;
  color: #18181b;
  padding: 10px;
  border-radius: 8px;
  text-decoration: none;
  font-size: 0.85rem;
  font-weight: 500;
  transition: all 0.25s ease;
}

.btn-return-portal span {
  white-space: nowrap;
  transition: opacity 0.2s ease;
}

.btn-return-portal:hover {
  background: #e4e4e7;
  color: #18181b;
}

.admin-main-wrap {
  flex: 1;
  margin-left: 0;
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
  padding: 0 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  z-index: 120;
}

.topbar-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sidebar-toggle-btn {
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  color: #52525b;
  cursor: pointer;
  transition: all 0.2s;
}

.sidebar-toggle-btn:hover {
  background: #ffffff;
  border-color: #18181b;
  color: #18181b;
}

.topbar-logo {
  width: 26px;
  height: 26px;
  border-radius: 7px;
  object-fit: cover;
}

.page-current-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 0.95rem;
  font-weight: 700;
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
