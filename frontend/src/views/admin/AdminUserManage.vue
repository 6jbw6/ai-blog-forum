<template>
  <div class="user-manage-page">
    <div class="page-title-row">
      <h2 class="title">用户管理</h2>
    </div>

    <div class="section-card">
      <div class="toolbar">
        <div class="search-capsule">
          <el-icon class="capsule-icon"><Search /></el-icon>
          <input
            v-model="keyword"
            class="capsule-input"
            type="text"
            placeholder="输入用户名 / 用户ID 搜索"
            spellcheck="false"
            autocomplete="off"
            @keydown.enter="loadUsers"
          />
          <button class="capsule-btn" @click="loadUsers">搜索</button>
        </div>
      </div>

      <el-table :data="users" stripe v-loading="loading" style="width: 100%">
        <el-table-column prop="id" label="用户ID" width="90" align="center" />
        <el-table-column prop="username" label="用户名" min-width="140" />
        <el-table-column prop="email" label="邮箱" min-width="180" />
        <el-table-column label="角色" width="100" align="center">
          <template #default="{ row }">
            <el-tag v-if="row.role === 'admin'" size="small" type="warning">管理员</el-tag>
            <el-tag v-else size="small" type="info">读者</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="150" align="center">
          <template #default="{ row }">
            <el-tooltip v-if="!row.is_active" :content="row.ban_reason || ''" placement="top">
              <el-tag size="small" type="danger">已封禁</el-tag>
            </el-tooltip>
            <el-tag v-else size="small" type="success">正常</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="注册时间" width="130" align="center" />
        <el-table-column label="操作" width="160" align="center">
          <template #default="{ row }">
            <div v-if="row.id === userStore.user?.id" class="row-actions">
              <span class="cell-muted">当前登录账号</span>
            </div>
            <div v-else class="row-actions">
              <el-button size="small" text type="danger" @click="openBanBox(row)">
                封号
              </el-button>
              <el-button size="small" text type="success" @click="openUnbanBox(row)">
                解封
              </el-button>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { searchUsersAdminApi, banUserApi, unbanUserApi, type AdminUserItem } from '@/api/adminUsers'
import { useUserStore } from '@/stores/user'

const userStore = useUserStore()

const users = ref<AdminUserItem[]>([])
const loading = ref(false)
const keyword = ref('')

const loadUsers = async () => {
  loading.value = true
  try {
    users.value = await searchUsersAdminApi(keyword.value || undefined)
  } finally {
    loading.value = false
  }
}

const openBanBox = (row: AdminUserItem) => {
  ElMessageBox.prompt(
    `确认封禁用户「${row.username}」？`,
    '封禁账号',
    {
      confirmButtonText: '确认封禁',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入封禁原因',
      inputPattern: /\S{2,}/,
      inputErrorMessage: '封禁原因至少 2 个字符',
      type: 'warning',
      lockScroll: false
    }
  ).then(async ({ value }) => {
    await banUserApi(row.id, value.trim())
    ElMessage.success(`已封禁用户「${row.username}」`)
    loadUsers()
  }).catch(() => {})
}

const openUnbanBox = (row: AdminUserItem) => {
  ElMessageBox.prompt(
    `确认解封用户「${row.username}」？`,
    '解封账号',
    {
      confirmButtonText: '确认解封',
      cancelButtonText: '取消',
      inputPlaceholder: '请输入解封原因',
      inputPattern: /\S{2,}/,
      inputErrorMessage: '解封原因至少 2 个字符',
      type: 'success',
      lockScroll: false
    }
  ).then(async ({ value }) => {
    await unbanUserApi(row.id, value.trim())
    ElMessage.success(`已解封用户「${row.username}」`)
    loadUsers()
  }).catch(() => {})
}

onMounted(() => {
  loadUsers()
})
</script>

<style scoped>
.user-manage-page {
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

.section-card {
  background: #ffffff;
  border-radius: 14px;
  padding: 1.5rem;
  border: 1px solid #e4e4e7;
}

.toolbar {
  display: flex;
  justify-content: flex-start;
  margin-bottom: 1.25rem;
}

/* 搜索胶囊：与前台/文章管理同款 */
.search-capsule {
  width: 420px;
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

/* 操作列：封号/解封按钮同一行居中不换行 */
.row-actions {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  white-space: nowrap;
}

.row-actions :deep(.el-button + .el-button) {
  margin-left: 0;
}

.cell-muted {
  font-size: 0.8rem;
  color: #a1a1aa;
}
</style>
