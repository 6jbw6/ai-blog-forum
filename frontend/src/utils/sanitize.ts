import DOMPurify from 'dompurify'

// 站内唯一的 HTML 白名单出口：所有 v-html 渲染的内容必须先经过 sanitizeHtml，
// 把 Markdown / 推荐词 / 富文本里的 <script>、onerror 等注入向量挡在渲染层之外。
// 默认白名单保留 HTML + SVG + MathML（KaTeX 公式输出依赖 MathML 与行内 style）。
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  // 外链一律新窗口打开并补 rel，防钓鱼跳转与 window.opener 泄露
  if (node.tagName === 'A' && (node.getAttribute('href') || '').startsWith('http')) {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

export function sanitizeHtml(html: string): string {
  return DOMPurify.sanitize(html)
}
