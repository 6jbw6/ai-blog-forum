<template>
  <el-dialog
    v-model="visible"
    title="🔔 评论回复消息提醒"
    width="680px"
    destroy-on-close
    append-to-body
    :lock-scroll="false"
    custom-class="notifications-modal"
  >
    <div class="notifications-container">
      <!-- 头部操作条 -->
      <div v-if="notifications.length > 0" class="modal-top-bar">
        <span class="count-tip">共 {{ notifications.length }} 条回复提醒</span>
        <el-button
          v-if="hasUnread"
          size="small"
          text
          type="primary"
          @click="handleMarkAllAsRead"
        >
          全部标为已读
        </el-button>
      </div>

      <div v-if="loading" class="notifications-loading">
        <el-skeleton :rows="4" animated />
      </div>

      <div v-else-if="notifications.length > 0" class="notifications-list">
        <div
          v-for="item in notifications"
          :key="item.id"
          :class="['notification-card', { unread: !item.is_read }]"
          @click="goToArticle(item.article_slug, item.id)"
        >
          <div class="card-avatar">
            <el-avatar :size="40" :src="item.sender_avatar || '/user-avatar.svg'" />
          </div>

          <div class="card-body">
            <div class="card-head-row">
              <div class="head-user-action">
                <strong class="sender-name">{{ item.sender_name }}</strong>
                <span class="action-desc">回复了你在博文</span>
                <span class="article-ref">《{{ item.article_title }}》</span>
                <span class="action-desc">下的评论</span>
              </div>
              <span class="time-stamp">{{ formatDate(item.created_at) }}</span>
            </div>

            <!-- 对方回复的内容 -->
            <div class="reply-content-box">
              <span class="reply-label">回复内容：</span>
              <span class="reply-text">{{ item.reply_content }}</span>
            </div>

            <!-- 你的原评论内容 -->
            <div class="parent-content-box">
              <span class="parent-label">你的原评：</span>
              <span class="parent-text">{{ item.parent_content }}</span>
            </div>

            <div class="card-footer-row">
              <span v-if="!item.is_read" class="unread-dot-badge">● 未读</span>
              <span v-else class="read-badge">已读</span>
              <span class="jump-hint">点击进入博文查看完整讨论 &rarr;</span>
            </div>
          </div>
        </div>
      </div>

      <div v-else class="notifications-empty">
        <el-empty description="暂无新的评论回复提醒，去博文发表你的见解吧~" />
      </div>
    </div>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  getMyNotificationsApi,
  markAllNotificationsAsReadApi,
  markNotificationAsReadApi,
  type NotificationItem
} from '@/api/notification'

const emit = defineEmits<{
  (e: 'updated'): void
}>()

const router = useRouter()
const visible = ref(false)
const loading = ref(false)
const notifications = ref<NotificationItem[]>([])

const hasUnread = computed(() => notifications.value.some(n => !n.is_read))

const formatDate = (isoString?: string) => {
  if (!isoString) return '近期'
  try {
    const raw = isoString.endsWith('Z') || isoString.includes('+') ? isoString : `${isoString}Z`
    const d = new Date(raw)
    return new Intl.DateTimeFormat('zh-CN', {
      timeZone: 'Asia/Shanghai',
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    }).format(d).replace(/\//g, '-')
  } catch {
    return isoString
  }
}

const loadNotifications = async () => {
  loading.value = true
  try {
    const data = await getMyNotificationsApi()
    notifications.value = data
  } catch {
    notifications.value = []
  } finally {
    loading.value = false
  }
}

const open = () => {
  visible.value = true
  loadNotifications()
}

const goToArticle = async (slug: string, id: number) => {
  visible.value = false
  // 标记为已读
  try {
    await markNotificationAsReadApi(id)
    emit('updated')
  } catch {
    // ignore
  }
  router.push(`/article/${slug}`)
}

const handleMarkAllAsRead = async () => {
  try {
    await markAllNotificationsAsReadApi()
    notifications.value.forEach(n => (n.is_read = true))
    ElMessage.success('全部提醒已标记为已读')
    emit('updated')
  } catch {
    ElMessage.error('标记失败，请重试')
  }
}

defineExpose({
  open
})
</script>

<style scoped>
.notifications-container {
  min-height: 200px;
  max-height: 540px;
  overflow-y: auto;
  padding: 0 4px 12px;
}

.modal-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 10px;
  margin-bottom: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter, #f4f4f5);
}

.count-tip {
  font-size: 12px;
  color: #a1a1aa;
}

.notifications-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.notification-card {
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 10px;
  border: 1px solid var(--el-border-color-lighter, #e4e4e7);
  background: var(--el-bg-color, #ffffff);
  cursor: pointer;
  transition: all 0.2s ease;
}

.notification-card:hover {
  border-color: #10b981;
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.08);
  transform: translateY(-1px);
}

.notification-card.unread {
  background: #f0fdf4;
  border-color: #a7f3d0;
}

.card-avatar {
  flex-shrink: 0;
  margin-top: 2px;
}

.card-body {
  flex: 1;
  min-width: 0;
}

.card-head-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 10px;
  margin-bottom: 8px;
}

.head-user-action {
  font-size: 14px;
  line-height: 1.4;
  color: #3f3f46;
}

.sender-name {
  color: #18181b;
  font-weight: 700;
  margin-right: 4px;
}

.article-ref {
  color: #059669;
  font-weight: 600;
  margin: 0 2px;
}

.action-desc {
  color: #71717a;
}

.time-stamp {
  font-size: 11px;
  color: #a1a1aa;
  white-space: nowrap;
}

.reply-content-box {
  background: #ffffff;
  border-radius: 6px;
  padding: 8px 12px;
  border: 1px solid #e4e4e7;
  font-size: 13px;
  line-height: 1.5;
  color: #18181b;
  margin-bottom: 6px;
}

.reply-label {
  color: #10b981;
  font-weight: 600;
}

.parent-content-box {
  background: #fafafa;
  border-radius: 6px;
  padding: 6px 12px;
  border-left: 3px solid #d4d4d8;
  font-size: 12px;
  color: #71717a;
  margin-bottom: 8px;
}

.parent-label {
  color: #a1a1aa;
}

.card-footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 11px;
}

.unread-dot-badge {
  color: #e11d48;
  font-weight: 700;
}

.read-badge {
  color: #a1a1aa;
}

.jump-hint {
  color: #059669;
  font-weight: 500;
}

.notifications-empty {
  padding: 36px 0;
}
</style>
