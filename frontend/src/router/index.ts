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
    path: '/tags',
    name: 'Tags',
    component: () => import('@/views/portal/Tags.vue'),
    meta: { title: '技术标签 - AI 博客论坛' }
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('@/views/portal/SearchResults.vue'),
    meta: { title: '语义搜索 - AI 博客论坛' }
  },
  {
    path: '/user/:id',
    name: 'UserProfile',
    component: () => import('@/views/portal/UserProfile.vue'),
    meta: { title: '个人主页 - AI 博客论坛' }
  },
  {
    path: '/write',
    name: 'WriteArticle',
    component: () => import('@/views/portal/WriteArticle.vue'),
    meta: { title: '写作 - AI 博客论坛' }
  },
  {
    path: '/write/:id',
    name: 'WriteArticleEdit',
    component: () => import('@/views/portal/WriteArticle.vue'),
    meta: { title: '编辑博文 - AI 博客论坛' }
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
      return userStore.isAdmin ? '/admin/dashboard' : '/write'
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
        path: 'write',
        name: 'AdminWrite',
        component: () => import('@/views/portal/WriteArticle.vue'),
        meta: { requiresAdmin: true, embedded: true, title: '写作 - AI 博客论坛' }
      },
      {
        path: 'write/:id',
        name: 'AdminWriteEdit',
        component: () => import('@/views/portal/WriteArticle.vue'),
        meta: { requiresAdmin: true, embedded: true, title: '编辑博文 - AI 博客论坛' }
      },
      {
        path: 'tags',
        name: 'AdminTags',
        component: () => import('@/views/admin/TagManage.vue'),
        meta: { requiresAdmin: true, title: '标签库运维 - AI 博客论坛' }
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

// 门户浏览页面对游客开放，无需登录
const publicRouteNames = ['Home', 'ArticleDetail', 'Tags', 'Search', 'UserProfile', 'Login']

// 全局登录拦截与 RBAC 权限守卫
router.beforeEach((to, _from, next) => {
  if (to.meta.title) {
    document.title = to.meta.title as string
  }

  const userStore = useUserStore()

  // 已登录状态访问登录页，自动跳转至首页
  if (userStore.isLoggedIn && to.name === 'Login') {
    next({ name: 'Home' })
    return
  }

  // 门户浏览页面（首页/文章详情/标签/搜索）游客可直接访问
  if (publicRouteNames.includes(to.name as string)) {
    next()
    return
  }

  // 其余页面（后台/创作/个人中心）需登录
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录后再进行该操作')
    next({ name: 'Login' })
    return
  }

  // 检查是否需要管理员权限
  const requiresAdmin = to.matched.some(record => record.meta.requiresAdmin)
  if (requiresAdmin) {
    if (!userStore.isAdmin) {
      ElMessage.warning('权限不足：请先以管理员身份登录系统')
      next({ name: 'Home' })
      return
    }
  }

  next()
})

export default router
