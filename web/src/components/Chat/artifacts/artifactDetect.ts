export type ArtifactVariant = 'json' | 'yaml' | 'diff' | 'terminal' | 'code'

export interface ArtifactInfo {
  variant: ArtifactVariant
  label: string
  content: string
  language?: string
}

export interface RawArtifactOptions {
  streaming?: boolean
}

const CODE_LABELS: Record<string, string> = {
  ts: 'TypeScript',
  typescript: 'TypeScript',
  tsx: 'TSX',
  js: 'JavaScript',
  javascript: 'JavaScript',
  jsx: 'JSX',
  py: 'Python',
  python: 'Python',
  go: 'Go',
  rs: 'Rust',
  java: 'Java',
  c: 'C',
  cpp: 'C++',
  cc: 'C++',
  cs: 'C#',
  sql: 'SQL',
  html: 'HTML',
  css: 'CSS',
  xml: 'XML',
  bash: 'Terminal',
  shell: 'Terminal',
  powershell: 'PowerShell',
  mermaid: 'Mermaid',
  txt: 'Text',
  text: 'Text',
}

export function normalizeContent(content: string) {
  return content.replace(/\r\n/g, '\n')
}

export function looksLikeMarkdown(content: string) {
  return /(^#{1,6}\s)|(^\s*[-*+]\s)|(^\s*\d+\.\s)|(^\s*>\s)|(^\s*```)|(^\s*~~~)|(\[[^\]]+\]\([^)]+\))|(!\[[^\]]*\]\([^)]+\))|(\|.*\|)/m.test(content)
}

export function prettyJson(content: string) {
  const trimmed = content.trim()
  if (!trimmed || !/^[{\[]/.test(trimmed)) return content
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return content
  }
}

export function parseJsonPreview(content: string) {
  const normalized = normalizeContent(content)
  const trimmed = normalized.trim()
  if (!trimmed || !/^[{\[]/.test(trimmed)) return null
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return null
  }
}

export function looksLikeDiff(content: string) {
  const lines = content.split('\n')
  let score = 0
  let hasStrongMarker = false
  for (const line of lines) {
    if (/^(diff --git|index |@@ |--- |\+\+\+ )/.test(line)) {
      score += 2
      hasStrongMarker = true
    }
    else if (/^[+-]/.test(line)) score += 1
  }
  return hasStrongMarker && score >= 3
}

export function looksLikeTerminal(content: string) {
  const lines = content.split('\n').map((line) => line.trim())
  let score = 0
  for (const line of lines) {
    if (!line) continue
    if (/^(PS\s[^>]+>|[A-Za-z]:\\|[~/].*[#>$]|root@|.*[@:~].*[#$>])/.test(line)) score += 2
    else if (/^(\$|>|#)\s+/.test(line)) score += 1
    else if (/^(cmd>|python>|git |npm |pnpm |yarn |pip |uv |docker |kubectl |opkg |apt |brew )/.test(line)) score += 1
  }
  return score >= 3
}

export function looksLikeYaml(content: string) {
  const lines = content.split('\n').map((line) => line.trim())
  const useful = lines.filter(Boolean)
  if (useful.length < 3) return false
  if (looksLikeMarkdown(content)) return false
  let score = 0
  for (const line of useful) {
    if (/^[A-Za-z0-9_.-]+\s*:\s+/.test(line)) score += 1
    else if (/^-\s+/.test(line)) score += 1
    else if (/^[A-Za-z0-9_.-]+\s*=\s+/.test(line)) score += 1
  }
  return score >= Math.max(2, Math.ceil(useful.length / 2))
}

export function looksLikeCode(content: string) {
  const lines = content.split('\n').map((line) => line.trimEnd())
  const useful = lines.filter((line) => line.trim().length > 0)
  if (useful.length < 3) return false
  if (looksLikeMarkdown(content)) return false

  let score = 0
  for (const line of useful) {
    const trimmed = line.trim()
    if (/^(import |from |export |const |let |var |function |class |def |async |await |if |for |while |try |catch |return |switch |case |public |private |protected |interface |type |enum |package |using |#include )/.test(trimmed)) score += 2
    else if (/[{}()[\];,]$/.test(trimmed) || /[{}()[\];,]/.test(trimmed)) score += 1
    else if (/^\s{2,}|\t/.test(line)) score += 1
    else if (/^[A-Za-z0-9_.$-]+\s*[:=]/.test(trimmed)) score += 1
  }

  return score >= Math.max(3, Math.ceil(useful.length / 2))
}

function classifyCodeLabel(language: string) {
  const normalized = language.trim().toLowerCase()
  return CODE_LABELS[normalized] || (normalized ? normalized.toUpperCase() : 'Code')
}

export function classifyFencedArtifact(language: string, content: string): ArtifactInfo {
  const normalizedContent = normalizeContent(content)
  const normalizedLanguage = language.trim()
  const lang = normalizedLanguage.toLowerCase()

  if (lang === 'json') return { variant: 'json', label: 'JSON', content: prettyJson(normalizedContent), language: normalizedLanguage || 'json' }
  if (lang === 'yaml' || lang === 'yml') return { variant: 'yaml', label: 'YAML', content: normalizedContent, language: normalizedLanguage || 'yaml' }
  if (lang === 'diff' || lang === 'patch') return { variant: 'diff', label: 'Diff', content: normalizedContent, language: normalizedLanguage || 'diff' }
  if (lang === 'bash' || lang === 'sh' || lang === 'shell' || lang === 'zsh'
    || lang === 'powershell' || lang === 'pwsh' || lang === 'ps1'
    || lang === 'cmd' || lang === 'console' || lang === 'terminal') {
    return { variant: 'terminal', label: classifyCodeLabel(lang), content: normalizedContent, language: normalizedLanguage || lang }
  }

  return {
    variant: 'code',
    label: classifyCodeLabel(lang),
    content: normalizedContent,
    language: normalizedLanguage || undefined,
  }
}

export function detectRawArtifact(content: string, options: RawArtifactOptions = {}): ArtifactInfo | null {
  const normalized = normalizeContent(content)
  const jsonPreview = parseJsonPreview(normalized)
  if (jsonPreview) return { variant: 'json', label: 'JSON', content: jsonPreview }
  if (looksLikeDiff(normalized)) return { variant: 'diff', label: 'Diff', content: normalized }
  if (looksLikeTerminal(normalized)) return { variant: 'terminal', label: 'Terminal', content: normalized }
  if (looksLikeYaml(normalized)) return { variant: 'yaml', label: 'YAML', content: normalized }
  if (!options.streaming && looksLikeCode(normalized)) return { variant: 'code', label: 'Code', content: normalized }
  return null
}
