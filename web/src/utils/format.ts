/** web/src/utils/format.ts 模块。 */

/** 处理 fmtSize 相关逻辑。 */
export function fmtSize(n: number): string {
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(1)} MB`
}

/** 处理 formatNumber 相关逻辑。 */
export function formatNumber(n: number): string {
  if (!n && n !== 0) return ''
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

/** 处理 fmtTime 相关逻辑。 */
export function fmtTime(ts: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const diff = Date.now() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString('zh-CN')
}

/** 处理 fmtMs 相关逻辑。 */
export function fmtMs(ms: number): string {
  if (!ms && ms !== 0) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

/** 处理 isImageFile 相关逻辑。 */
export function isImageFile(name: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg|bmp|ico)$/i.test(name)
}
