/**
 * 邮箱校验：格式校验 + **主流服务商准入**（不接受自有域名 / 自建邮局地址）。
 *
 * 域名清单与后端 `backend/app/core/email_policy.py` 保持一致：
 * 前端负责输入框即时提示，后端是最终校验。新增服务商时两边同时加。
 */
export const EMAIL_MAX_LENGTH = 128

export const MAINSTREAM_EMAIL_DOMAINS = new Set([
  // 国内主流免费邮
  'qq.com', 'vip.qq.com', 'foxmail.com',
  '163.com', '126.com', 'yeah.net', '188.com', '88.com', '163.net',
  'sina.com', 'sina.cn', 'vip.sina.com',
  'sohu.com', '21cn.com', 'tom.com', '263.net', 'aliyun.com',
  // 国内运营商邮
  '139.com', '189.cn', 'wo.cn',
  // 国际主流
  'gmail.com', 'googlemail.com',
  'outlook.com', 'hotmail.com', 'live.com', 'live.cn', 'msn.com',
  'icloud.com', 'me.com', 'mac.com',
  'yahoo.com', 'yahoo.co.jp', 'ymail.com', 'rocketmail.com',
  'zoho.com', 'zohomail.com',
  'proton.me', 'protonmail.com',
  'gmx.com', 'gmx.de', 'gmx.net', 'web.de', 'mail.com',
  'yandex.com', 'yandex.ru', 'ya.ru',
  'aol.com', 'fastmail.com', 'fastmail.fm',
  'tutanota.com', 'tuta.io', 'hushmail.com', 'hey.com',
  'naver.com', 'daum.net', 'hanmail.net', 'nate.com'
])

// 本地部分允许常见字符（含 + 别名），域名至少两段、顶级域 ≥ 2 个字母
const EMAIL_PATTERN = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/

export const isValidEmail = (email: string): boolean => {
  const value = (email || '').trim()
  if (!value || value.length > EMAIL_MAX_LENGTH) return false
  if (value.includes('..') || value.startsWith('.') || value.includes('@.')) return false
  return EMAIL_PATTERN.test(value)
}

export const emailDomainOf = (email: string): string =>
  (email || '').trim().toLowerCase().split('@').pop() || ''

/** 是否为主流邮箱服务商域名 */
export const isMainstreamEmail = (email: string): boolean =>
  MAINSTREAM_EMAIL_DOMAINS.has(emailDomainOf(email))

export const EMAIL_PLACEHOLDER = '请输入邮箱'
export const EMAIL_INVALID_MESSAGE = '邮箱格式不正确，请检查后重新输入'
export const EMAIL_DOMAIN_REJECT_MESSAGE = '暂不支持自有域名邮箱，请使用 QQ、163、Gmail、Outlook、iCloud 等主流邮箱'

/** 完整校验：先看格式，再看服务商；返回 null 表示通过，否则返回提示文案 */
export const validateEmail = (email: string): string | null => {
  if (!isValidEmail(email)) return EMAIL_INVALID_MESSAGE
  if (!isMainstreamEmail(email)) return EMAIL_DOMAIN_REJECT_MESSAGE
  return null
}

/** 密码强度校验（注册 / 改密）：至少 8 位且字母数字混合；null 表示通过 */
export const validatePassword = (password: string): string | null => {
  if (password.length < 8) return '密码至少需要 8 个字符'
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) return '密码需同时包含字母和数字'
  return null
}

export const PASSWORD_PLACEHOLDER = '至少 8 位，字母数字混合'
