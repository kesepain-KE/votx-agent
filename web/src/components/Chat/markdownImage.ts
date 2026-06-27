import { buildViewUrl, inferDirFromPath } from './artifacts/resultArtifacts'

const EXTERNAL_URL_RE = /^(https?:|mailto:|\/\/)/i
const WINDOWS_PATH_RE = /^[a-zA-Z]:[\\/]/i
const UNC_PATH_RE = /^\\\\/

function stripQueryAndHash(value: string) {
  return value.replace(/[?#].*$/, '')
}

export function safeMarkdownUrlTransform(url: string) {
  const value = url.trim()
  if (!value) return ''
  if (WINDOWS_PATH_RE.test(value) || UNC_PATH_RE.test(value)) return value
  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(value)
  if (!hasScheme) return value
  if (EXTERNAL_URL_RE.test(value)) return value
  return ''
}

export function buildMarkdownImageCandidates(src?: string) {
  const value = (src || '').trim()
  if (!value) return []
  if (EXTERNAL_URL_RE.test(value) || value.startsWith('/api/')) return [value]

  const normalized = stripQueryAndHash(value).replace(/\\/g, '/')
  const parts = normalized.split('/').filter(Boolean)
  const name = parts.length ? parts[parts.length - 1] : ''
  if (!name) return [value]

  const dir = inferDirFromPath(normalized)
  const fallback = buildViewUrl(name, dir)
  return fallback === value ? [value] : [value, fallback]
}
