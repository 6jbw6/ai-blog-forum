<template>
  <div class="markdown-container">
    <!-- 如果包含思考过程 (<think>...</think>)，展示现代折叠思考面板 -->
    <div v-if="thinkingContent" class="thinking-box">
      <div class="thinking-header" @click="isThinkingOpen = !isThinkingOpen">
        <div class="thinking-title">
          <span class="thinking-icon">💡</span>
          <span class="thinking-text">{{ isThinkingStreaming ? '正在思考中...' : '已完成思考' }}</span>
        </div>
        <span class="thinking-arrow">{{ isThinkingOpen ? '收起 ▲' : '展开 ▼' }}</span>
      </div>
      <div v-show="isThinkingOpen" class="thinking-content">
        {{ thinkingContent }}
      </div>
    </div>

    <!-- 正文渲染 -->
    <div
      class="markdown-body"
      :class="{ 'chat-mode': chatMode }"
      v-html="renderedHtml"
    ></div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { marked } from 'marked'
import hljs from 'highlight.js'
import 'highlight.js/styles/atom-one-dark.css'
import katex from 'katex'
import 'katex/dist/katex.min.css'

const props = withDefaults(defineProps<{
  content: string
  chatMode?: boolean
}>(), {
  chatMode: false
})

const isThinkingOpen = ref(false)
const isThinkingStreaming = ref(false)

// 配置 marked 与 highlight.js 代码高亮
marked.setOptions({
  gfm: true,
  breaks: true,
  // @ts-ignore
  highlight: function (code: string, lang: string) {
    const language = hljs.getLanguage(lang) ? lang : 'plaintext'
    return hljs.highlight(code, { language }).value
  }
})

// 解析思考内容与正文内容
const parsedContent = computed(() => {
  const raw = props.content || ''
  
  // 检测 <think> 标签 (DeepSeek R1 / 推理模型思考过程)
  const thinkMatch = raw.match(/<think>([\s\S]*?)(?:<\/think>|$)/i)
  if (thinkMatch) {
    const thinking = thinkMatch[1].trim()
    const answer = raw.replace(/<think>[\s\S]*?(?:<\/think>|$)/i, '').trim()
    const isStillThinking = !raw.includes('</think>')
    return {
      thinking,
      answer,
      isThinking: isStillThinking
    }
  }

  return {
    thinking: '',
    answer: raw,
    isThinking: false
  }
})

const thinkingContent = computed(() => parsedContent.value.thinking)

watch(() => parsedContent.value.isThinking, (val) => {
  isThinkingStreaming.value = val
  if (val) {
    isThinkingOpen.value = true
  }
}, { immediate: true })

// 结合 KaTeX 与 Marked 解析 Markdown
const renderedHtml = computed(() => {
  const contentToRender = parsedContent.value.answer
  if (!contentToRender) return ''

  const blockMaths: string[] = []
  const inlineMaths: string[] = []
  const codeBlocks: string[] = []

  // 0. 保护围栏代码块，避免公式定界符归一化误伤代码内容
  let text = contentToRender.replace(/```[\s\S]*?```/g, (code) => {
    const id = codeBlocks.length
    codeBlocks.push(code)
    return `%%%CODE_BLOCK_${id}%%%`
  })

  // 0.5 标准 LaTeX 定界符归一化：\[...\] 显示公式 -> $$...$$，\(...\) 行内公式 -> $...$
  text = text.replace(/\\\[([\s\S]+?)\\\]/g, (_, math) => `\n\n$$${math.trim()}$$\n\n`)
  text = text.replace(/\\\(([\s\S]+?)\\\)/g, (_, math) => `$${math.trim()}$`)

  // 1. 保护块级数学公式 $$...$$ (支持多行与行内连续块)
  text = text.replace(/\$\$([\s\S]+?)\$\$/g, (_, math) => {
    const id = blockMaths.length
    blockMaths.push(math.trim())
    return `%%%KATEX_BLOCK_${id}%%%`
  })

  // 1.5 智能兼容归一化：将文本中未包裹 $ 的 LaTeX 开根号或伪代码 (如 \sqrt{d_k} 或 sqrt(d_k)) 自动转为 KaTeX 行内公式
  text = text.replace(/(?<![\$\\])\\sqrt\{([^}]+)\}(?!\$)/g, (_, math) => {
    const id = inlineMaths.length
    inlineMaths.push(`\\sqrt{${math.trim()}}`)
    return `%%%KATEX_INLINE_${id}%%%`
  })
  text = text.replace(/(?<![a-zA-Z0-9_\$\\])sqrt\(([a-zA-Z0-9_]+)\)(?!\$)/g, (_, math) => {
    const id = inlineMaths.length
    inlineMaths.push(`\\sqrt{${math.trim()}}`)
    return `%%%KATEX_INLINE_${id}%%%`
  })

  // 2. 保护行内数学公式 $...$
  text = text.replace(/(?<!\$)\$([^\$\n]+?)\$(?!\$)/g, (_, math) => {
    const id = inlineMaths.length
    inlineMaths.push(math.trim())
    return `%%%KATEX_INLINE_${id}%%%`
  })

  // 2.5 还原围栏代码块后再进入 Markdown 解析
  text = text.replace(/%%%CODE_BLOCK_(\d+)%%%/g, (_, idStr) => codeBlocks[Number(idStr)] || '')

  // 3. 解析标准 Markdown 为 HTML
  let html = marked.parse(text) as string

  // 4. 还原块级公式为 KaTeX 渲染结果
  html = html.replace(/%%%KATEX_BLOCK_(\d+)%%%/g, (_, idStr) => {
    const math = blockMaths[Number(idStr)] || ''
    try {
      return katex.renderToString(math, {
        displayMode: true,
        throwOnError: false
      })
    } catch {
      return `<div class="katex-error">$$${math}$$</div>`
    }
  })

  // 5. 还原行内公式为 KaTeX 渲染结果
  html = html.replace(/%%%KATEX_INLINE_(\d+)%%%/g, (_, idStr) => {
    const math = inlineMaths[Number(idStr)] || ''
    try {
      return katex.renderToString(math, {
        displayMode: false,
        throwOnError: false
      })
    } catch {
      return `<span class="katex-error">$${math}$</span>`
    }
  })

  return html
})
</script>

<style scoped>
.markdown-container {
  width: 100%;
}

/* 思考过程折叠框 */
.thinking-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  margin-bottom: 0.75rem;
  overflow: hidden;
}

.thinking-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: #f1f5f9;
  cursor: pointer;
  user-select: none;
  font-size: 0.8rem;
  color: #64748b;
  transition: background 0.2s;
}

.thinking-header:hover {
  background: #e2e8f0;
}

.thinking-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
}

.thinking-arrow {
  font-size: 0.75rem;
}

.thinking-content {
  padding: 10px 12px;
  font-size: 0.82rem;
  line-height: 1.6;
  color: #64748b;
  border-top: 1px solid #e2e8f0;
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}
</style>

<style>
/* 全局 Markdown 基础排版 */
.markdown-body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 16px;
  line-height: 1.8;
  color: #2c3e50;
  word-break: break-word;
}

.markdown-body h1,
.markdown-body h2,
.markdown-body h3,
.markdown-body h4 {
  color: #1a1a1a;
  margin-top: 1.6em;
  margin-bottom: 0.8em;
  font-weight: 700;
  border-bottom: 1px solid #ebeef5;
  padding-bottom: 0.3em;
}

.markdown-body h1 { font-size: 2rem; border-bottom: 2px solid #18181b; }
.markdown-body h2 { font-size: 1.5rem; }
.markdown-body h3 { font-size: 1.25rem; border-bottom: none; }

.markdown-body p {
  margin-top: 0;
  margin-bottom: 1.2em;
}

.markdown-body blockquote {
  margin: 1.2em 0;
  padding: 0.8em 1.2em;
  color: #52525b;
  background-color: #f4f4f5;
  border-left: 4px solid #10b981;
  border-radius: 4px;
}

.markdown-body pre {
  background-color: #282c34;
  border-radius: 8px;
  padding: 1rem;
  overflow-x: auto;
  margin: 1.2em 0;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.markdown-body pre code {
  background: transparent;
  padding: 0;
  color: #abb2bf;
  font-family: "Fira Code", Consolas, Monaco, "Courier New", Courier, monospace;
  font-size: 0.92rem;
}

.markdown-body :not(pre) > code {
  background-color: #f2f4f7;
  color: #059669;
  padding: 0.2em 0.4em;
  border-radius: 4px;
  font-size: 0.9em;
  font-family: monospace;
}

.markdown-body table {
  width: 100%;
  border-collapse: collapse;
  margin: 1.5em 0;
}

.markdown-body th,
.markdown-body td {
  border: 1px solid #dcdfe6;
  padding: 10px 14px;
  text-align: left;
}

.markdown-body th {
  background-color: #f5f7fa;
  font-weight: 600;
}

.markdown-body ul,
.markdown-body ol {
  padding-left: 24px;
  margin-bottom: 1.2em;
}

.markdown-body li {
  margin-bottom: 0.4em;
}

/* KaTeX 公式在 Markdown 中的全局渲染规范 */
.markdown-body .katex-display {
  margin: 1em 0;
  overflow-x: auto;
  overflow-y: hidden;
  padding: 6px 0;
}

.markdown-body .katex {
  font-size: 1.06em;
  text-rendering: auto;
}

/* Chat 紧凑模式专用排版 (对话抽屉专属优化) */
.markdown-body.chat-mode {
  font-size: 0.92rem;
  line-height: 1.65;
  color: #18181b;
}

.markdown-body.chat-mode h1 {
  font-size: 1.25rem;
  margin: 0.7em 0 0.35em;
  padding-bottom: 0.2em;
  border-bottom: 1px solid #e4e4e7;
}

.markdown-body.chat-mode h2 {
  font-size: 1.12rem;
  margin: 0.65em 0 0.3em;
  padding-bottom: 0.2em;
  border-bottom: 1px solid #f4f4f5;
}

.markdown-body.chat-mode h3 {
  font-size: 1.02rem;
  margin: 0.55em 0 0.25em;
  border-bottom: none;
}

.markdown-body.chat-mode h4 {
  font-size: 0.95rem;
  margin: 0.5em 0 0.2em;
  border-bottom: none;
}

.markdown-body.chat-mode p {
  margin: 0 0 0.6em 0;
}

.markdown-body.chat-mode p:last-child {
  margin-bottom: 0;
}

.markdown-body.chat-mode pre {
  margin: 0.6em 0;
  padding: 0.75rem;
  font-size: 0.82rem;
  border-radius: 6px;
}

.markdown-body.chat-mode blockquote {
  margin: 0.6em 0;
  padding: 0.5em 0.8em;
  font-size: 0.88rem;
}

.markdown-body.chat-mode ul,
.markdown-body.chat-mode ol {
  padding-left: 20px;
  margin: 0 0 0.6em 0;
}

.markdown-body.chat-mode hr {
  margin: 0.7em 0;
  border: none;
  border-top: 1px solid #e4e4e7;
}

.markdown-body.chat-mode .katex-display {
  margin: 0.6em 0;
  font-size: 0.96em;
}
</style>
