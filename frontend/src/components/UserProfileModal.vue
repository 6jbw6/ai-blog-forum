<template>
  <el-dialog
    v-model="visible"
    title="个人资料"
    width="500px"
    align-center
    destroy-on-close
    append-to-body
    :lock-scroll="false"
    class="profile-dialog"
  >
    <div v-if="userStore.user" class="profile-modal-content">
      <!-- 顶部信息摘要 -->
      <div class="user-header-card">
        <div class="avatar-upload-wrap">
          <el-avatar :size="64" :src="userStore.user.avatar || '/user-avatar.svg'" class="avatar-box" />
          <button class="avatar-edit-btn" :disabled="uploading" @click="triggerAvatarPick">
            {{ uploading ? '上传中' : '更换头像' }}
          </button>
          <input
            ref="avatarInputRef"
            type="file"
            accept="image/jpeg,image/png,image/webp,image/gif"
            class="avatar-file-input"
            @change="handleAvatarFile"
          />
        </div>
        <div class="header-info">
          <div class="name-row">
            <h3 class="display-name">{{ userStore.user.username }}</h3>
          </div>
          <p class="user-sub">
            账号 ID: {{ userStore.user.id }} · 状态: <span class="active-dot">🟢 正常</span>
          </p>
          <p v-if="userStore.user.bio" class="user-bio-preview">
            {{ userStore.user.bio }}
          </p>
        </div>
      </div>

      <!-- 资料表单 -->
      <el-form :model="form" label-position="top" class="profile-form">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" maxlength="32" clearable />
        </el-form-item>

        <el-form-item label="绑定电子邮箱">
          <el-input :model-value="userStore.user.email" disabled />
        </el-form-item>

        <el-form-item label="个人签名">
          <el-input
            v-model="form.bio"
            type="textarea"
            :rows="2"
            maxlength="120"
            show-word-limit
            placeholder="写下您的个性签名，展现独特态度..."
          />
        </el-form-item>

        <el-form-item label="修改新密码 (选填)">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            placeholder="若不修改密码请留空"
            clearable
          />
        </el-form-item>

        <div class="meta-date-row">
          <span>注册时间：{{ formatDate(userStore.user.created_at) }}</span>
        </div>
      </el-form>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <el-button @click="visible = false">关闭</el-button>
        <el-button type="primary" :loading="saving" @click="handleSave">保存修改</el-button>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useUserStore } from '@/stores/user'
import { updateProfileApi, uploadAvatarApi } from '@/api/auth'

const userStore = useUserStore()
const visible = ref(false)
const saving = ref(false)
const uploading = ref(false)
const avatarInputRef = ref<HTMLInputElement>()

const AVATAR_ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp', 'image/gif']
const AVATAR_MAX_SIZE = 2 * 1024 * 1024

const triggerAvatarPick = () => {
  avatarInputRef.value?.click()
}

const handleAvatarFile = async (event: Event) => {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return

  if (!AVATAR_ALLOWED_TYPES.includes(file.type)) {
    ElMessage.warning('仅支持 JPG、PNG、WebP、GIF 格式的头像图片')
    return
  }
  if (file.size > AVATAR_MAX_SIZE) {
    ElMessage.warning('头像图片不能超过 2MB')
    return
  }

  uploading.value = true
  try {
    const updatedUser = await uploadAvatarApi(file)
    if (updatedUser) {
      userStore.setUser(updatedUser)
    }
    ElMessage.success('头像更新成功')
  } catch (err: any) {
    ElMessage.error(err.message || '头像上传失败')
  } finally {
    uploading.value = false
  }
}

const form = reactive({
  username: '',
  bio: '',
  password: ''
})

const syncFormFromStore = () => {
  if (userStore.user) {
    form.username = userStore.user.username || ''
    form.bio = userStore.user.bio || ''
    form.password = ''
  }
}

const open = () => {
  syncFormFromStore()
  visible.value = true
}

watch(visible, (val) => {
  if (val) {
    syncFormFromStore()
  }
})

const formatDate = (dateStr?: string) => {
  if (!dateStr) return '-'
  const isoStr = (dateStr.endsWith('Z') || dateStr.includes('+')) ? dateStr : `${dateStr}Z`
  const d = new Date(isoStr)
  if (isNaN(d.getTime())) {
    const fallback = new Date(dateStr)
    return isNaN(fallback.getTime()) ? dateStr : fallback.toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai', hour12: false })
  }
  return d.toLocaleString('zh-CN', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
  }).replace(/\//g, '-')
}

const handleSave = async () => {
  if (!form.username.trim()) {
    ElMessage.warning('用户名不能为空')
    return
  }

  saving.value = true
  try {
    const payload: { username: string; nickname?: string; bio?: string; password?: string } = {
      username: form.username.trim(),
      nickname: form.username.trim(),
      bio: form.bio.trim()
    }
    if (form.password.trim()) {
      if (form.password.trim().length < 6) {
        ElMessage.warning('新密码至少需要 6 个字符')
        saving.value = false
        return
      }
      payload.password = form.password.trim()
    }

    const updatedUser = await updateProfileApi(payload)
    if (updatedUser) {
      userStore.setUser(updatedUser)
    }
    ElMessage.success('个人资料已成功更新')
    visible.value = false
  } catch (err: any) {
    ElMessage.error(err.message || '更新个人资料失败')
  } finally {
    saving.value = false
  }
}

defineExpose({ open })
</script>

<style scoped>
.profile-modal-content {
  padding: 0.25rem 0.5rem;
}

.user-header-card {
  display: flex;
  align-items: center;
  gap: 1.25rem;
  background: #f8fafc;
  border: 1px solid #e4e4e7;
  border-radius: 16px;
  padding: 1.25rem 1.5rem;
  margin-bottom: 1.5rem;
}

.avatar-box {
  background: #18181b;
  border: 2px solid #e4e4e7;
}

.avatar-upload-wrap {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
}

.avatar-file-input {
  display: none;
}

.avatar-edit-btn {
  background: #f4f4f5;
  color: #18181b;
  border: 1px solid #e4e4e7;
  border-radius: 9999px;
  padding: 2px 10px;
  font-size: 0.72rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.avatar-edit-btn:hover:not(:disabled) {
  background: #18181b;
  color: #ffffff;
}

.avatar-edit-btn:disabled {
  opacity: 0.6;
  cursor: wait;
}

.header-info {
  flex: 1;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 4px;
}

.display-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: #18181b;
  margin: 0;
}

.user-sub {
  font-size: 0.8rem;
  color: #71717a;
  margin: 0;
}

.user-bio-preview {
  font-size: 0.82rem;
  color: #059669;
  margin: 6px 0 0 0;
  word-break: break-all;
}

.active-dot {
  color: #059669;
  font-weight: 600;
}

.profile-form {
  margin-bottom: 0.5rem;
}

.meta-date-row {
  font-size: 0.78rem;
  color: #a1a1aa;
  margin-top: -4px;
  margin-bottom: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
