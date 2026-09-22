<template>
  <div class="comment-node">
    <el-avatar :size="depth ? 28 : 40" :src="comment.user_avatar || 'https://api.dicebear.com/7.x/bottts/svg?seed=c'" />

    <div class="node-main">
      <div class="node-author-row">
        <span class="node-name">{{ comment.user_name }}</span>
        <span v-if="comment.is_admin" class="node-badge">{{ depth ? '博主回复' : '博主' }}</span>
        <span class="node-time">{{ formatDateISO(comment.created_at) }}</span>
      </div>

      <p class="node-text">{{ comment.content }}</p>

      <button class="node-reply-btn" @click="toggleReply">回复</button>

      <div v-if="replying" class="node-reply-box">
        <el-input
          v-model="replyText"
          type="textarea"
          :rows="2"
          resize="none"
          :placeholder="`回复 @${comment.user_name}：`"
        />
        <div class="node-reply-actions">
          <el-button size="small" text @click="replying = false">取消</el-button>
          <el-button size="small" type="primary" :loading="submitting" @click="submitReply">
            发表回复
          </el-button>
        </div>
      </div>

      <div v-if="comment.replies && comment.replies.length > 0" class="node-children">
        <CommentItem
          v-for="r in comment.replies"
          :key="r.id"
          :comment="r"
          :article-id="articleId"
          :depth="depth + 1"
          @posted="emit('posted')"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { postCommentApi } from '@/api/comment'
import { useUserStore } from '@/stores/user'
import { formatDateISO } from '@/utils/date'
import type { Comment } from '@/types'

const props = defineProps<{
  comment: Comment
  articleId: number
  depth?: number
}>()

const emit = defineEmits<{ (e: 'posted'): void }>()

const router = useRouter()
const userStore = useUserStore()

const depth = props.depth ?? 0
const replying = ref(false)
const submitting = ref(false)
const replyText = ref('')

const toggleReply = () => {
  if (!userStore.isLoggedIn) {
    ElMessage.warning('请先登录后再回复评论')
    router.push('/login')
    return
  }
  replying.value = !replying.value
}

const submitReply = async () => {
  if (!replyText.value.trim()) {
    ElMessage.warning('请填写回复内容')
    return
  }

  submitting.value = true
  try {
    await postCommentApi({
      article_id: props.articleId,
      parent_id: props.comment.id,
      user_name: userStore.user?.username || userStore.user?.nickname || '技术读者',
      user_email: userStore.user?.email || 'reader@ai-blog.local',
      content: replyText.value.trim()
    })
    ElMessage.success('回复发表成功')
    replyText.value = ''
    replying.value = false
    emit('posted')
  } finally {
    submitting.value = false
  }
}
</script>

<style scoped>
.comment-node {
  display: flex;
  gap: 14px;
}

.node-main {
  flex: 1;
  min-width: 0;
}

.node-author-row {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.node-name {
  font-size: 0.9rem;
  font-weight: 700;
  color: #18181b;
}

.node-badge {
  background: #ecfdf5;
  color: #059669;
  border: 1px solid #a7f3d0;
  font-size: 0.72rem;
  font-weight: 700;
  padding: 1px 6px;
  border-radius: 4px;
}

.node-time {
  margin-left: auto;
  font-size: 0.75rem;
  color: #71717a;
}

.node-text {
  margin: 0;
  font-size: 0.88rem;
  color: #374151;
  line-height: 1.6;
}

.node-reply-btn {
  margin-top: 6px;
  padding: 2px 0;
  border: none;
  background: none;
  font-size: 0.78rem;
  font-weight: 600;
  color: #71717a;
  cursor: pointer;
  transition: color 0.2s;
}

.node-reply-btn:hover {
  color: #059669;
}

.node-reply-box {
  margin-top: 8px;
}

.node-reply-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}

/* 子级回复整体缩进并带一条竖向导轨，逐层递归渲染 */
.node-children {
  margin-top: 12px;
  padding-left: 14px;
  border-left: 2px solid #e4e4e7;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
</style>
