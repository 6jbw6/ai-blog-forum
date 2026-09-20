<template>
  <div>
    <!-- 右下角常驻悬浮 AI 按钮 -->
    <div class="floating-ai-trigger" @click="openDrawer">
      <div class="ai-button-glow"></div>
      <div class="ai-button-inner">
        <img src="/bot-avatar.svg" alt="AI" class="trigger-bot-icon" />
      </div>
      <div class="ai-badge-label">
        <span class="emerald-dot"></span>
        <span>AI 智能体</span>
      </div>
    </div>

    <!-- AI 对话抽屉 -->
    <el-drawer
      v-model="aiChatStore.isChatOpen"
      direction="rtl"
      size="480px"
      :show-close="true"
      :lock-scroll="false"
      custom-class="ai-chat-drawer"
    >
      <template #header>
        <div class="drawer-header">
          <div class="header-avatar-box">
            <el-avatar :size="40" src="/bot-avatar.svg" />
            <span class="online-indicator"></span>
          </div>
          <div class="header-info">
            <h3 class="header-title">AI 智能体</h3>
            <p class="header-subtitle">基于 RAG 知识库与大模型驱动 · 实时语义对齐</p>
          </div>
          <el-button size="small" text type="danger" @click="clearHistory">清空对话</el-button>
        </div>
      </template>

      <!-- 对话消息区域 -->
      <div class="chat-messages" ref="messagesContainer">
        <!-- 初始欢迎问候卡片 -->
        <div class="welcome-card">
          <div class="welcome-badge">✦ RAG 知识库智能助手</div>
          <p class="welcome-text">
            你好！我是博客论坛的 <strong>AI 智能体</strong> 🤖。我已全面索引了关于 <strong>AI Agent 架构、Transformer 原理、LoRA 微调、RAG 向量检索</strong> 等领域的深度技术博文。
          </p>
          <div class="recommend-header">
            <span class="welcome-hint">你可以随时向我提问，或探索热度推荐：</span>
            <button
              type="button"
              class="refresh-btn"
              :class="{ 'is-refreshing': isRefreshingPrompts }"
              @click="refreshRecommendations"
              title="换一批推荐问题"
            >
              <el-icon class="refresh-icon" :class="{ 'is-rotating': isRefreshingPrompts }"><Refresh /></el-icon>
              <span>换一批</span>
            </button>
          </div>
          
          <div class="quick-questions">
            <button
              v-for="(q, idx) in displayedPrompts"
              :key="idx"
              class="quick-tag"
              @click="sendQuickQuestion(q)"
            >
              <span class="hot-badge">✦</span>
              <span class="quick-text" v-html="renderPromptMath(q)"></span>
            </button>
          </div>
        </div>

        <!-- 历史消息列表 -->
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message-row', msg.role === 'user' ? 'row-user' : 'row-assistant']"
        >
          <div class="message-avatar">
            <el-avatar
              :size="32"
              :src="msg.role === 'user' ? (userStore.user?.avatar || '/user-avatar.svg') : '/bot-avatar.svg'"
            />
          </div>

          <div class="message-bubble-wrapper">
            <div class="message-bubble">
              <!-- 用户消息原生对齐，杜绝 Markdown 的 <p> 标签产生顶部 1em 冗余空行，同时支持 KaTeX 数学公式 -->
              <div v-if="msg.role === 'user'" class="user-text-content" v-html="renderUserMessage(msg.content)"></div>

              <!-- Assistant 消息 -->
              <template v-else>
                <!-- AI 思考中动效状态展示 -->
                <div v-if="isStreaming && index === messages.length - 1 && !msg.content" class="ai-thinking-state">
                  <div class="thinking-header-row">
                    <span class="thinking-sparkle">✦</span>
                    <span class="thinking-label">思考中</span>
                    <span class="thinking-pulse-dots">
                      <span class="dot dot-1"></span>
                      <span class="dot dot-2"></span>
                      <span class="dot dot-3"></span>
                    </span>
                  </div>
                  <div class="thinking-desc">正在检索博文知识库切片并组织推理...</div>
                </div>

                <!-- 正式回复内容渲染 (集成数学公式 KaTeX 与紧凑 Chat 排版) -->
                <MarkdownViewer v-else :content="msg.content" chat-mode />
                <span v-if="isStreaming && index === messages.length - 1 && msg.content" class="cursor-blink">|</span>
              </template>
            </div>

            <!-- 溯源引用卡片 (RAG 核心亮点) -->
            <div v-if="msg.citations && msg.citations.length > 0" class="citations-container">
              <div class="citation-header">
                <span>知识库溯源引用 ({{ msg.citations.length }} 处)</span>
              </div>
              <div
                v-for="c in msg.citations"
                :key="c.chunk_id"
                class="citation-card"
                @click="jumpToArticle(c.article_slug)"
              >
                <div class="citation-title">
                  <span class="citation-num">{{ c.citation_index }}</span>
                  <span class="citation-name">《{{ c.article_title }}》</span>
                  <span class="similarity-badge">{{ (c.similarity * 100).toFixed(1) }}% 相关度</span>
                </div>
                <div class="citation-snippet">{{ cleanSnippet(c.snippet) }}</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- 底部输入框 -->
      <template #footer>
        <div class="chat-input-wrapper">
          <el-input
            v-model="inputText"
            type="textarea"
            :rows="3"
            placeholder="输入你的技术问题 (Enter 发送, Shift+Enter 换行)"
            resize="none"
            :disabled="isStreaming"
            @keydown.enter.prevent="handleEnter"
          />
          <div class="input-actions">
            <span class="model-tag">当前接入: {{ llmModelLabel }}</span>
            <el-button
              type="primary"
              :loading="isStreaming"
              :disabled="!inputText.trim()"
              @click="handleSend"
            >
              发送提问
            </el-button>
          </div>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Refresh } from '@element-plus/icons-vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'
import { useAiChatStore } from '@/stores/aiChat'
import { useUserStore } from '@/stores/user'
import { streamRagChat, getRecommendedQuestionsApi, getChatHistoryApi, clearChatHistoryApi } from '@/api/ai'
import type { CitationItem } from '@/types'
import MarkdownViewer from './MarkdownViewer.vue'

const router = useRouter()
const aiChatStore = useAiChatStore()
const userStore = useUserStore()

const inputText = ref('')
const isStreaming = ref(false)
const messagesContainer = ref<HTMLElement | null>(null)
const llmModelLabel = ref('自研轻量RAG / DeepSeek')

interface ChatMsg {
  role: 'user' | 'assistant'
  content: string
  citations?: CitationItem[]
}

const messages = ref<ChatMsg[]>([])

const defaultPrompts = [
  'Transformer 自注意力为什么要除以 $\\sqrt{d_k}$？',
  '显存不够怎么微调大语言模型？',
  '多路召回相比单一向量检索有什么优势？',
  'LoRA 微调为什么在推理阶段零延迟？'
]

// 渲染推荐按钮中的数学公式与开根号符号 (支持 $\sqrt{d_k}$ 或兼容 sqrt(d_k))
const renderPromptMath = (text: string): string => {
  if (!text) return ''
  let normalized = text.replace(/(?<![a-zA-Z0-9_\$\\])sqrt\(([a-zA-Z0-9_]+)\)/g, '$\\sqrt{$1}$')
  normalized = normalized.replace(/(?<![\$\\])\\sqrt\{([^}]+)\}(?!\$)/g, '$\\sqrt{$1}$')
  return normalized.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), {
        displayMode: false,
        throwOnError: false
      })
    } catch {
      return math
    }
  })
}

// 溯源引用片段净化：片段是后端按 200 字硬截断的切片原文，含 Markdown 标记
// （### 标题、**加粗**、` 行内代码、表格竖线）与未闭合的 LaTeX 定界符，
// 纯文本插值展示时必须剥掉这些符号，避免 「### 核心亮点」这类原文残留
const cleanSnippet = (raw: string): string => {
  if (!raw) return ''

  // 1) 按代码围栏分段：丢弃围栏内的代码/mermaid 源码（截断未闭合的尾部一并丢弃）
  let text = raw.split(/```/).filter((_, i) => i % 2 === 0).join(' ')

  // 2) 剥除 HTML 标签与 HTML 实体
  text = text
    .replace(/<[^>]*>/g, ' ')
    .replace(/&[a-zA-Z#0-9]+;/g, ' ')

  // 3) 剥除 LaTeX 公式定界符（\(...\) \[...\] $$..$$ 与单 $；截断未闭合的原样留文）
  text = text
    .replace(/\\\(/g, '')
    .replace(/\\\)/g, '')
    .replace(/\\\[/g, '')
    .replace(/\\\]/g, '')
    .replace(/\$\$/g, '')
    .replace(/\$/g, '')

  // 4) 剥除 Markdown 标记：标题、加粗、斜体、删除线、行内代码、引用、列表、表格
  text = text
    .replace(/^#{1,6}\s*/gm, '')
    .replace(/\*\*([^*]+)\*\*/g, '$1')
    .replace(/__([^_]+)__/g, '$1')
    .replace(/(?<![a-zA-Z0-9_])\*([^*\n]+)\*(?![a-zA-Z0-9_])/g, '$1')
    .replace(/(?<![a-zA-Z0-9_])_([^_\n]+)_(?![a-zA-Z0-9_])/g, '$1')
    .replace(/~~([^~]+)~~/g, '$1')
    .replace(/`([^`]*)`?/g, '$1')
    .replace(/^\s*>\s?/gm, '')
    .replace(/^\s*[-*+]\s+/gm, '')
    .replace(/^\s*\d+\.\s+/gm, '')
    .replace(/^\s*[-:|\s]+$/gm, '')
    .replace(/\|/g, ' ')
    .replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')

  // 5) 清理截断残留的孤立标记（如末尾 "**"、"*"）并压缩空白
  text = text
    .replace(/\*{2,}/g, '')
    .replace(/_{1,2}(?=\s|$)/g, '')
    .replace(/[ \t]{2,}/g, ' ')

  return text.trim()
}

// 渲染用户提问消息气泡中的公式与特殊字符 (保持无顶部空行的同时支持 LaTeX)
const renderUserMessage = (text: string): string => {
  if (!text) return ''
  let safe = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
  let normalized = safe.replace(/(?<![a-zA-Z0-9_\$\\])sqrt\(([a-zA-Z0-9_]+)\)/g, '$\\sqrt{$1}$')
  normalized = normalized.replace(/(?<![\$\\])\\sqrt\{([^}]+)\}(?!\$)/g, '$\\sqrt{$1}$')
  return normalized.replace(/\$([^\$\n]+?)\$/g, (_, math) => {
    try {
      return katex.renderToString(math.trim(), {
        displayMode: false,
        throwOnError: false
      })
    } catch {
      return math
    }
  })
}

const allPrompts = ref<string[]>([])
const displayedPrompts = ref<string[]>([...defaultPrompts])
const isRefreshingPrompts = ref(false)

// 动态拉取推荐问题 (根据全站搜索热度与热门博文聚合生成)
const fetchDynamicPrompts = async (isManualRefresh = false) => {
  if (isRefreshingPrompts.value) return
  isRefreshingPrompts.value = true
  try {
    const questions = await getRecommendedQuestionsApi(8, isManualRefresh)
    if (Array.isArray(questions) && questions.length > 0) {
      allPrompts.value = questions
      displayedPrompts.value = questions.slice(0, 4)
    }
  } catch (err) {
    console.warn('获取热度推荐问题失败，使用默认推荐池:', err)
  } finally {
    setTimeout(() => {
      isRefreshingPrompts.value = false
    }, 350)
  }
}

// 换一批：优先在已加载候选池中轮转，若候选用尽则向后端发起重新采样
const refreshRecommendations = () => {
  if (allPrompts.value.length > 4) {
    const current = displayedPrompts.value
    const remaining = allPrompts.value.filter(p => !current.includes(p))
    if (remaining.length >= 2) {
      isRefreshingPrompts.value = true
      setTimeout(() => {
        displayedPrompts.value = remaining.slice(0, 4)
        isRefreshingPrompts.value = false
      }, 200)
      return
    }
  }
  fetchDynamicPrompts(true)
}

const isLoadingHistory = ref(false)

// 自动拉取当前登录账号最近的 10 次对话历史 (服务端为唯一事实源)
const loadChatHistory = async () => {
  if (!userStore.token || isLoadingHistory.value) return
  isLoadingHistory.value = true
  try {
    const history = await getChatHistoryApi(10)
    // 拉取期间用户已发起新提问则丢弃快照，避免覆盖正在进行的流式回复
    if (isStreaming.value) return
    if (Array.isArray(history) && history.length > 0) {
      messages.value = history.map(h => ({
        role: h.role,
        content: h.content,
        citations: h.citations || []
      }))
      // 双时机校准：渲染后立即滚底，抽屉展开动画结束后再次对齐
      scrollToBottom()
      scrollToBottom(400)
    }
  } catch (err) {
    console.warn('拉取 AI 历史对话失败:', err)
  } finally {
    isLoadingHistory.value = false
  }
}

onMounted(() => {
  fetchDynamicPrompts()
  if (userStore.token) {
    loadChatHistory()
  }
})

// 当用户点开抽屉时，每次都重新拉取最近 10 次对话并自动对齐最新消息
watch(() => aiChatStore.isChatOpen, (isOpen) => {
  if (isOpen) {
    if (allPrompts.value.length === 0 || displayedPrompts.value.length === 0) {
      fetchDynamicPrompts()
    }
    if (userStore.token && !isStreaming.value) {
      loadChatHistory()
    }
    // 等待抽屉展开动画完成后对齐最新消息
    scrollToBottom(380)
  }
})

// 监听账号切换或重新登录
watch(() => userStore.token, (newToken) => {
  if (newToken) {
    messages.value = []
    loadChatHistory()
  } else {
    messages.value = []
  }
})

// 监听外界传入的问题触发自动提问
watch(() => aiChatStore.pendingQuestion, (newQ) => {
  if (newQ) {
    inputText.value = newQ
    aiChatStore.pendingQuestion = ''
    handleSend()
  }
})

const openDrawer = () => {
  aiChatStore.openChat()
}

const scrollToBottom = (delay = 0) => {
  nextTick(() => {
    setTimeout(() => {
      const el = messagesContainer.value
      if (!el) return
      // Element Plus 抽屉实际滚动容器是 .el-drawer__body（.chat-messages 自身不产生溢出滚动），
      // 必须定位到真实可滚动祖先节点，否则 scrollTop 赋值为空操作，打开抽屉无法对齐最新消息
      const scroller = (el.closest('.el-drawer__body') as HTMLElement | null) ?? el
      scroller.scrollTop = scroller.scrollHeight
    }, delay)
  })
}

// 清空当前会话：前端清空，若已登录则同步删除后端数据库存储记录
const clearHistory = async () => {
  if (userStore.token) {
    try {
      await clearChatHistoryApi()
    } catch (err) {
      console.warn('清空后端对话历史失败:', err)
    }
  }
  messages.value = []
}

const sendQuickQuestion = (q: string) => {
  inputText.value = q
  handleSend()
}

const handleEnter = (e: KeyboardEvent) => {
  if (!e.shiftKey) {
    handleSend()
  }
}

const jumpToArticle = (slug: string) => {
  aiChatStore.closeChat()
  router.push(`/article/${slug}`)
}

const handleSend = async () => {
  const query = inputText.value.trim()
  if (!query || isStreaming.value) return

  // 追加用户消息 (无顶部空行，紧凑原生对齐)
  messages.value.push({ role: 'user', content: query })
  inputText.value = ''
  scrollToBottom()

  // 准备 Assistant 占位消息 (触发“思考中”动效)
  const assistantMsgIndex = messages.value.length
  messages.value.push({ role: 'assistant', content: '', citations: [] })
  isStreaming.value = true
  scrollToBottom()

  const historyPayload = messages.value
    .slice(0, -2)
    .map(m => ({ role: m.role, content: m.content }))

  await streamRagChat(
    query,
    historyPayload,
    (token) => {
      messages.value[assistantMsgIndex].content += token
      scrollToBottom()
    },
    (citations) => {
      messages.value[assistantMsgIndex].citations = citations
      scrollToBottom()
    },
    () => {
      isStreaming.value = false
      scrollToBottom()
    },
    (err) => {
      console.error(err)
      messages.value[assistantMsgIndex].content += '\n\n*(网络连接或大模型服务响应异常，请重试)*'
      isStreaming.value = false
      scrollToBottom()
    }
  )
}
</script>

<style scoped>
.floating-ai-trigger {
  position: fixed;
  bottom: 32px;
  right: 32px;
  z-index: 999;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 10px;
}

.ai-button-glow {
  position: absolute;
  width: 58px;
  height: 58px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(16, 185, 129, 0.35) 0%, rgba(16, 185, 129, 0) 70%);
  animation: glow-pulse 2s infinite;
}

@keyframes glow-pulse {
  0% { transform: scale(0.9); opacity: 0.8; }
  50% { transform: scale(1.3); opacity: 0.3; }
  100% { transform: scale(0.9); opacity: 0.8; }
}

.ai-button-inner {
  position: relative;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  background: #18181b;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 8px 20px rgba(24, 24, 27, 0.35);
  transition: transform 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.floating-ai-trigger:hover .ai-button-inner {
  transform: scale(1.1) rotate(4deg);
}

.trigger-bot-icon {
  width: 28px;
  height: 28px;
  display: block;
}

.ai-badge-label {
  background: #ffffff;
  padding: 6px 14px;
  border-radius: 20px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.1);
  font-size: 0.85rem;
  font-weight: 600;
  color: #18181b;
  border: 1px solid #e4e4e7;
  display: flex;
  align-items: center;
  gap: 6px;
}

.emerald-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background-color: #10b981;
  box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
}

/* 抽屉样式 */
.drawer-header {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.header-avatar-box {
  position: relative;
}

.online-indicator {
  position: absolute;
  bottom: 0;
  right: 0;
  width: 10px;
  height: 10px;
  background: #10b981;
  border: 2px solid #ffffff;
  border-radius: 50%;
}

.header-info {
  flex: 1;
}

.header-title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 700;
  color: #18181b;
}

.header-subtitle {
  margin: 2px 0 0 0;
  font-size: 0.75rem;
  color: #71717a;
}

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 1rem 0;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.welcome-card {
  background: #f4f4f5;
  border: 1px solid #e4e4e7;
  border-radius: 12px;
  padding: 1.2rem;
  margin-bottom: 0.5rem;
}

.welcome-badge {
  display: inline-block;
  font-size: 0.75rem;
  font-weight: 700;
  background: #18181b;
  color: #ffffff;
  padding: 2px 8px;
  border-radius: 6px;
  margin-bottom: 8px;
}

.welcome-text {
  font-size: 0.88rem;
  color: #3f3f46;
  line-height: 1.6;
  margin: 0 0 8px 0;
}

.recommend-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.recommend-header .welcome-hint {
  font-size: 0.8rem;
  color: #71717a;
  margin: 0;
}

.refresh-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 0.72rem;
  font-weight: 500;
  color: #71717a;
  cursor: pointer;
  transition: all 0.2s;
  user-select: none;
}

.refresh-btn:hover {
  color: #059669;
  border-color: #10b981;
  background: #ecfdf5;
}

.refresh-icon {
  font-size: 0.8rem;
  transition: transform 0.4s ease;
}

.refresh-icon.is-rotating {
  transform: rotate(360deg);
}

.quick-questions {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.quick-tag {
  display: flex;
  align-items: center;
  gap: 6px;
  text-align: left;
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 0.82rem;
  color: #18181b;
  cursor: pointer;
  transition: all 0.2s;
}

.hot-badge {
  color: #10b981;
  font-size: 0.75rem;
  flex-shrink: 0;
}

.quick-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.quick-tag:hover {
  background: #18181b;
  color: #ffffff;
  border-color: #18181b;
  transform: translateX(4px);
}

.quick-tag:hover .hot-badge {
  color: #34d399;
}

.message-row {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}

.row-user {
  flex-direction: row-reverse;
}

.message-bubble-wrapper {
  max-width: 82%;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* 用户气泡：消除顶部/底部空行与内边距错位 */
.row-user .message-bubble {
  background: #18181b;
  color: #ffffff;
  border-radius: 16px 4px 16px 16px;
  padding: 10px 14px;
  box-shadow: 0 2px 8px rgba(24, 24, 27, 0.25);
  overflow: hidden;
}

.user-text-content {
  margin: 0;
  padding: 0;
  color: #ffffff;
  font-size: 0.92rem;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-word;
}

.user-text-content :deep(.katex) {
  font-size: 1.05em;
  color: #ffffff;
}

.quick-tag :deep(.katex) {
  font-size: 0.95em;
  color: inherit;
}

/* 助手回复气泡 */
.row-assistant .message-bubble {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 4px 16px 16px 16px;
  padding: 12px 16px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.04);
}

/* AI 思考中动效状态展示 */
.ai-thinking-state {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 4px 0;
}

.thinking-header-row {
  display: flex;
  align-items: center;
  gap: 6px;
}

.thinking-sparkle {
  color: #10b981;
  font-size: 1rem;
  animation: rotate-sparkle 2.5s linear infinite;
}

@keyframes rotate-sparkle {
  0% { transform: rotate(0deg) scale(0.9); }
  50% { transform: rotate(180deg) scale(1.15); }
  100% { transform: rotate(360deg) scale(0.9); }
}

.thinking-label {
  font-size: 0.88rem;
  font-weight: 700;
  color: #18181b;
  letter-spacing: 0.5px;
}

.thinking-pulse-dots {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-left: 2px;
}

.thinking-pulse-dots .dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background-color: #10b981;
  display: inline-block;
  animation: pulse-dot 1.4s ease-in-out infinite both;
}

.thinking-pulse-dots .dot-1 {
  animation-delay: -0.32s;
}

.thinking-pulse-dots .dot-2 {
  animation-delay: -0.16s;
}

@keyframes pulse-dot {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1.2); opacity: 1; }
}

.thinking-desc {
  font-size: 0.78rem;
  color: #71717a;
  line-height: 1.4;
}

.cursor-blink {
  display: inline-block;
  font-weight: bold;
  animation: blink 0.8s infinite;
  color: #10b981;
  margin-left: 2px;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0; }
}

/* 引用溯源卡片 */
.citations-container {
  background: #fafafa;
  border: 1px dashed #e4e4e7;
  border-radius: 10px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.citation-header {
  font-size: 0.78rem;
  font-weight: 700;
  color: #52525b;
}

.citation-card {
  background: #ffffff;
  border: 1px solid #e4e4e7;
  border-radius: 8px;
  padding: 8px 10px;
  cursor: pointer;
  transition: all 0.2s;
}

.citation-card:hover {
  border-color: #10b981;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  transform: translateY(-1px);
}

.citation-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 0.82rem;
  font-weight: 600;
  color: #18181b;
  margin-bottom: 4px;
}

.citation-num {
  color: #059669;
  font-weight: 800;
}

.similarity-badge {
  margin-left: auto;
  font-size: 0.7rem;
  background: #ecfdf5;
  color: #059669;
  padding: 1px 6px;
  border-radius: 4px;
  border: 1px solid #a7f3d0;
}

.citation-snippet {
  font-size: 0.75rem;
  color: #64748b;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.chat-input-wrapper {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 8px;
}

.input-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.model-tag {
  font-size: 0.75rem;
  color: #9ca3af;
}
</style>
