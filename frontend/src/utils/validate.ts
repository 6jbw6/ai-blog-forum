/**
 * 通用邮箱校验：只校验「本地部分@域名.顶级域」的格式，**不限制邮箱服务商**，
 * QQ / 163 / 126 / Gmail / Outlook / Hotmail / Foxmail / iCloud / Yahoo / Zoho /
 * Proton / Yandex / 阿里云 / 139 / 新浪 / Sohu / Naver / GMX / Web.de / 自建域名 等一律可用。
 */
export const EMAIL_MAX_LENGTH = 128

// 本地部分允许常见字符（含 + 别名），域名至少两段、顶级域 ≥ 2 个字母
const EMAIL_PATTERN = /^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$/

export const isValidEmail = (email: string): boolean => {
  const value = (email || '').trim()
  if (!value || value.length > EMAIL_MAX_LENGTH) return false
  if (value.includes('..') || value.startsWith('.') || value.includes('@.')) return false
  return EMAIL_PATTERN.test(value)
}

export const EMAIL_PLACEHOLDER = '例如：you@gmail.com / you@qq.com / you@outlook.com'
export const EMAIL_INVALID_MESSAGE = '邮箱格式不正确，支持 QQ、163、Gmail、Outlook 等所有主流邮箱'
