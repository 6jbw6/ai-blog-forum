<template>
  <div class="login-page">
    <!-- 顶部极简导航栏 -->
    <header class="login-header">
      <div class="header-inner">
        <div class="brand-logo">
          <img src="/logo.png" alt="AI博客论坛 Logo" class="logo-badge" />
          <span class="brand-title-text">AI博客论坛</span>
        </div>
      </div>
    </header>

    <!-- 主体内容分栏：左侧特性矩阵 + 右侧独立白卡 -->
    <main class="login-main">
      <!-- 左侧：项目主题展示与 2x2 特性矩阵 -->
      <section class="brand-showcase">
        <div class="brand-heading">
          <h1 class="main-hero-title">
            欢迎来到 AI 博客论坛 <span class="sparkle-icon">✦</span>
          </h1>
          <p class="main-hero-subtitle">
            写博文 · 问 AI · 聊技术，一站式技术创作与交流社区
          </p>
        </div>

        <div class="features-matrix">
          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <el-icon :size="22" class="feature-icon"><EditPen /></el-icon>
            </div>
            <h3 class="feature-title">全民博主创作</h3>
            <p class="feature-desc">
              注册即成博主，Markdown 编辑器搭配分类与标签体系，让每一篇技术沉淀都被看见。
            </p>
          </div>

          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <el-icon :size="22" class="feature-icon"><ChatDotRound /></el-icon>
            </div>
            <h3 class="feature-title">AI 智能问答</h3>
            <p class="feature-desc">
              站内博文沉淀为专属知识库，技术疑问即问即答，每一句回答都附来源出处。
            </p>
          </div>

          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <el-icon :size="22" class="feature-icon"><Pointer /></el-icon>
            </div>
            <h3 class="feature-title">博友互动交流</h3>
            <p class="feature-desc">
              点赞、收藏、评论一键互动，消息提醒实时送达，与志同道合的博友畅聊技术。
            </p>
          </div>

          <div class="feature-card">
            <div class="feature-icon-wrapper">
              <el-icon :size="22" class="feature-icon"><DataAnalysis /></el-icon>
            </div>
            <h3 class="feature-title">热门内容发现</h3>
            <p class="feature-desc">
              搜索热词实时置顶，标签词云与热度榜单多维呈现，优质好文一秒直达。
            </p>
          </div>
        </div>
      </section>

      <!-- 右侧：认证白卡 -->
      <section class="login-card-container">
        <div class="auth-card">
          <div class="card-header">
            <h2 class="card-title">欢迎来到 AI 博客论坛</h2>
          </div>

          <!-- 模式切换标签页 (账号登录 / 注册) -->
          <div class="auth-tabs">
            <button
              type="button"
              class="tab-item"
              :class="{ active: !isRegister }"
              @click="isRegister = false"
            >
              账号登录
            </button>
            <button
              type="button"
              class="tab-item"
              :class="{ active: isRegister }"
              @click="isRegister = true"
            >
              账号注册
            </button>
          </div>

          <el-form :model="form" label-position="top" class="auth-form" @submit.prevent="handleSubmit">
            <el-form-item label="用户名">
              <el-input
                v-model="form.username"
                size="large"
                placeholder="请输入用户名"
                :prefix-icon="UserIcon"
              />
            </el-form-item>

            <el-form-item v-if="isRegister" label="电子邮箱">
              <el-input
                v-model="form.email"
                size="large"
                placeholder="请输入电子邮箱"
                :prefix-icon="MessageIcon"
              />
            </el-form-item>

            <el-form-item label="密码">
              <el-input
                v-model="form.password"
                size="large"
                type="password"
                placeholder="请输入密码"
                show-password
                :prefix-icon="LockIcon"
                @keydown.enter="handleSubmit"
              />
            </el-form-item>

            <div class="form-actions">
              <el-button
                type="primary"
                size="large"
                class="btn-submit"
                :loading="loading"
                @click="handleSubmit"
              >
                {{ isRegister ? '立即注册' : '登 录' }}
              </el-button>
            </div>

            <div class="card-footer">
              <span class="footer-hint">
                {{ isRegister ? '已有账号？' : '没有账号？' }}
              </span>
              <button type="button" class="btn-toggle" @click="isRegister = !isRegister">
                {{ isRegister ? '立即登录' : '立即注册' }}
              </button>
            </div>
          </el-form>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { User as UserIcon, Lock as LockIcon, Message as MessageIcon } from '@element-plus/icons-vue'
import { useUserStore } from '@/stores/user'
import { registerApi } from '@/api/auth'

const router = useRouter()
const userStore = useUserStore()

const isRegister = ref(false)
const loading = ref(false)

const form = ref({
  username: '',
  email: '',
  password: ''
})

const handleSubmit = async () => {
  if (!form.value.username || !form.value.password) {
    ElMessage.warning('请填写用户名与密码')
    return
  }

  loading.value = true
  try {
    if (isRegister.value) {
      if (!form.value.email) {
        ElMessage.warning('注册请填写电子邮箱')
        return
      }
      await registerApi({
        username: form.value.username,
        email: form.value.email,
        password: form.value.password
      })
      ElMessage.success('注册成功，正在为你自动登录...')
    }

    const user = await userStore.login({
      username: form.value.username,
      password: form.value.password
    })

    if (user.role === 'admin') {
      router.push('/admin/dashboard')
    } else {
      router.push('/')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  width: 100%;
  background: #f8fafc url('/login-bg.jpg?v=3') no-repeat center center;
  background-size: cover;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* 顶部栏 */
.login-header {
  width: 100%;
  padding: 1.25rem 2.5rem;
  z-index: 10;
}

.header-inner {
  max-width: 1480px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  text-decoration: none;
}

.logo-badge {
  width: 34px;
  height: 34px;
  border-radius: 8px;
  object-fit: cover;
  display: block;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.brand-title-text {
  font-size: 1.25rem;
  font-weight: 800;
  color: #18181b;
  letter-spacing: -0.3px;
}

.nav-link-home {
  font-size: 0.9rem;
  color: #52525b;
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
  display: flex;
  align-items: center;
  gap: 4px;
}

.nav-link-home:hover {
  color: #059669;
}

.arrow {
  transition: transform 0.2s;
}

.nav-link-home:hover .arrow {
  transform: translateX(3px);
}

/* 主体分栏容器 */
.login-main {
  flex: 1;
  max-width: 1480px;
  width: 100%;
  margin: 0 auto;
  padding: 2rem 2.5rem 3rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 4.5rem;
  z-index: 10;
}

/* 左侧品牌与特性网格 */
.brand-showcase {
  flex: 1;
  max-width: 780px;
}

.brand-heading {
  margin-bottom: 2rem;
}

.main-hero-title {
  font-size: 2.5rem;
  font-weight: 800;
  color: #18181b;
  margin: 0 0 0.75rem;
  letter-spacing: -0.5px;
  line-height: 1.2;
}

.sparkle-icon {
  color: #059669;
  font-size: 1.8rem;
  vertical-align: middle;
}

.main-hero-subtitle {
  font-size: 1.15rem;
  color: #71717a;
  margin: 0;
  font-weight: 500;
}

/* 2x2 特性矩阵卡片 */
.features-matrix {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1.25rem;
}

.feature-card {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(228, 228, 231, 0.8);
  border-radius: 16px;
  padding: 1.4rem 1.25rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.03);
  transition: all 0.25s ease;
}

.feature-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 24px -4px rgba(0, 0, 0, 0.06);
  border-color: #10b981;
}

.feature-icon-wrapper {
  width: 36px;
  height: 36px;
  background: #f4f4f5;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 0.85rem;
  color: #18181b;
}

.feature-card:hover .feature-icon-wrapper {
  background: #ecfdf5;
  color: #059669;
}

.feature-title {
  font-size: 1.02rem;
  font-weight: 700;
  color: #18181b;
  margin: 0 0 0.5rem;
}

.feature-desc {
  font-size: 0.82rem;
  color: #71717a;
  line-height: 1.5;
  margin: 0;
}

/* 右侧白卡面板 */
.login-card-container {
  width: 100%;
  max-width: 440px;
}

.auth-card {
  background: #ffffff;
  border-radius: 20px;
  box-shadow: 0 20px 45px -12px rgba(0, 0, 0, 0.08), 0 0 0 1px rgba(0, 0, 0, 0.04);
  border: 1px solid #f4f4f5;
  padding: 2.5rem 2.25rem;
}

.card-header {
  margin-bottom: 1.5rem;
}

.card-title {
  font-size: 1.5rem;
  font-weight: 800;
  color: #18181b;
  margin: 0;
  letter-spacing: -0.3px;
}

/* Tab 切换栏 */
.auth-tabs {
  display: flex;
  align-items: center;
  gap: 1.5rem;
  border-bottom: 1px solid #e4e4e7;
  margin-bottom: 1.75rem;
}

.tab-item {
  background: transparent;
  border: none;
  font-size: 0.95rem;
  font-weight: 600;
  color: #71717a;
  padding: 0.5rem 0.2rem 0.75rem;
  cursor: pointer;
  position: relative;
  transition: color 0.2s;
}

.tab-item:hover {
  color: #18181b;
}

.tab-item.active {
  color: #18181b;
}

.tab-item.active::after {
  content: '';
  position: absolute;
  bottom: -1px;
  left: 0;
  right: 0;
  height: 2px;
  background: #18181b;
  border-radius: 2px;
}

/* 表单样式 */
.auth-form :deep(.el-form-item) {
  margin-bottom: 1.25rem;
}

.auth-form :deep(.el-form-item__label) {
  font-weight: 600;
  color: #27272a;
  padding-bottom: 6px;
  font-size: 0.88rem;
  line-height: 1.2;
}

.auth-form :deep(.el-input__wrapper) {
  border-radius: 8px;
}

.auth-form :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 0 0 1px #18181b inset !important;
}

.form-actions {
  margin-top: 1rem;
}

.btn-submit {
  width: 100%;
  font-weight: 700;
  height: 44px;
  background: #18181b !important;
  color: #ffffff !important;
  border: 1px solid #18181b !important;
  border-radius: 8px;
  font-size: 0.95rem;
  transition: all 0.2s;
}

.btn-submit:hover {
  background: #27272a !important;
  border-color: #27272a !important;
}

.card-footer {
  margin-top: 1.5rem;
  text-align: center;
  font-size: 0.88rem;
}

.footer-hint {
  color: #71717a;
}

.btn-toggle {
  background: transparent;
  border: none;
  color: #18181b;
  font-weight: 700;
  font-size: 0.88rem;
  cursor: pointer;
  margin-left: 6px;
  transition: color 0.2s;
}

.btn-toggle:hover {
  color: #059669;
}

/* 响应式适配 */
@media (max-width: 960px) {
  .login-main {
    flex-direction: column;
    gap: 2.5rem;
    padding: 1.5rem;
  }

  .brand-showcase {
    max-width: 100%;
    text-align: center;
  }

  .features-matrix {
    grid-template-columns: 1fr;
  }

  .login-card-container {
    max-width: 100%;
  }
}
</style>
