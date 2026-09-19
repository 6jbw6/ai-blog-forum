import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useUserStore } from '@/stores/user'
import { ElMessage } from 'element-plus'

const routes: RouteRecordRaw[] = [
  // 前台门户路由
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/portal/Home.vue'),
    meta: { title: '首页 - AI 博客论坛' }
  },
  {
    path: '/article/:idOrSlug',
    name: 'ArticleDetail',
    component: () => import('@/views/portal/ArticleDetail.vue'),
    meta: { title: '文章详情 - AI 博客论坛' }
  },
  {
    path: '/categories',
    name: 'Categories',
    component: () => import('@/views/portal/Categories.vue'),
    meta: { title: '技术标签分类 - AI 博客论坛' }
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
    meta: { title: '用户登录 - AI 博客论坛' }
  },

  // 后台与创作者路由 (RBAC 权限守卫)
  {
    path: '/admin',
    component: () => import('@/views/admin/AdminLayout.vue'),
    redirect: () => {
      const userStore = useUserStore()
      return userStore.isAdmin ? '/admin/dashboard' : '/admin/article/new'
    },
    children: [
      {
        path: 'dashboard',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { requiresAdmin: true, title: '运营看板 - AI 博客论坛' }
      },
      {
        path: 'articles',
        name: 'AdminArticles',
        component: () => import('@/views/admin/ArticleList.vue'),
        meta: { requiresAdmin: true, title: '文章管理 - AI 博客论坛' }
      },
      {
        path: 'article/new',
        name: 'AdminArticleNew',
        component: () => import('@/views/admin/ArticleEdit.vue'),
        meta: { title: '发布博文 (AI写作) - AI 博客论坛' }
      },
      {
        path: 'article/edit/:id',
        name: 'AdminArticleEdit',
        component: () => import('@/views/admin/ArticleEdit.vue'),
        meta: { title: '编辑博文 - AI 博客论坛' }
      },
      {
        path: 'categories-tags',
        name: 'AdminCategoryTag',
        component: () => import('@/views/admin/CategoryTagManage.vue'),
        meta: { requiresAdmin: true, title: '分类与标签运维 - AI 博客论坛' }
      },
      {
        path: 'comments',
        name: 'AdminComments',
        component: () => import('@/views/admin/CommentManage.vue'),
        meta: { requiresAdmin: true, title: '评论审核 - AI 博客论坛' }
      },
      {
        path: 'ai-settings',
        name: 'AdminAiSettings',
        component: () => import('@/views/admin/AiSettings.vue'),
        meta: { requiresAdmin: true, title: 'AI 引擎设置 - AI 博客论坛' }
      }
    ]
  },

  // 404 回退
  {
    path: '/:pathMatch(.*)*',
    redirect: '/'
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  }
})

// 企业级全局登录拦截与 RBAC 权限守卫
router.beforeEach((to, _from, next) => {
  if (to.meta.title) {
    document.title = to.meta.title as string
  }

  const userStore = useUserStore()

  // 未登录时，访问任何路由直接拦截跳转至登录页
  if (!userStore.isLoggedIn) {
    if (to.name !== 'Login') {
      next({ name: 'Login' })
      return
    }
  } else {
    // 已登录状态访问登录页，自动跳转至首页
    if (to.name === 'Login') {
      next({ name: 'Home' })
      return
    }
  }

  // 检查是否需要管理员权限
  const requiresAdmin = to.matched.some(record => record.meta.requiresAdmin)
  if (requiresAdmin) {
    if (!userStore.isAdmin) {
      ElMessage.warning('权限不足：请先以管理员身份登录系统')
      next({ name: 'Login' })
      return
    }
  }

  next()
})

export default router
