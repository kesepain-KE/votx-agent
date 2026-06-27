export type ResultArtifactKind = 'file' | 'image'

export type ResultArtifactDir = 'file' | 'download' | 'knowledge' | 'global-knowledge'

export interface ResultArtifact {
  kind: ResultArtifactKind
  name: string
  path?: string
  dir?: ResultArtifactDir
  mimeType?: string
  size?: number
  width?: number
  height?: number
  previewUrl?: string
  downloadUrl?: string
}

const VALID_KINDS = new Set<ResultArtifactKind>(['file', 'image'])
const VALID_DIRS = new Set<ResultArtifactDir>(['file', 'download', 'knowledge', 'global-knowledge'])

const IMAGE_MIME_LABELS: Record<string, string> = {
  'image/png': 'PNG',
  'image/jpeg': 'JPEG',
  'image/jpg': 'JPG',
  'image/webp': 'WEBP',
  'image/gif': 'GIF',
  'image/bmp': 'BMP',
  'image/x-icon': 'ICO',
}

const FILE_MIME_LABELS: Record<string, string> = {
  'text/markdown': 'Markdown',
  'text/plain': '文本',
  'text/html': 'HTML',
  'application/json': 'JSON',
  'application/pdf': 'PDF',
  'application/zip': 'ZIP',
  'application/x-7z-compressed': '7Z',
  'application/x-tar': 'TAR',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'DOCX',
  'application/msword': 'DOC',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'XLSX',
  'application/vnd.ms-excel': 'XLS',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'PPTX',
  'application/vnd.ms-powerpoint': 'PPT',
  'audio/mpeg': 'MP3',
  'audio/wav': 'WAV',
  'audio/x-wav': 'WAV',
  'video/mp4': 'MP4',
  'video/quicktime': 'MOV',
  'video/x-msvideo': 'AVI',
}

const FILE_EXT_LABELS: Record<string, string> = {
  md: 'Markdown',
  markdown: 'Markdown',
  txt: '文本',
  text: '文本',
  json: 'JSON',
  yaml: 'YAML',
  yml: 'YAML',
  pdf: 'PDF',
  doc: 'DOC',
  docx: 'DOCX',
  xls: 'XLS',
  xlsx: 'XLSX',
  ppt: 'PPT',
  pptx: 'PPTX',
  zip: 'ZIP',
  tar: 'TAR',
  gz: 'GZ',
  py: 'Python',
  js: 'JavaScript',
  ts: 'TypeScript',
  html: 'HTML',
  css: 'CSS',
  sh: 'Shell',
  mp3: 'MP3',
  wav: 'WAV',
  mp4: 'MP4',
  avi: 'AVI',
  mov: 'MOV',
  xml: 'XML',
}

const IMAGE_EXT_LABELS: Record<string, string> = {
  png: 'PNG',
  jpg: 'JPG',
  jpeg: 'JPEG',
  webp: 'WEBP',
  gif: 'GIF',
  bmp: 'BMP',
  ico: 'ICO',
}

function normalizeText(value: unknown) {
  return typeof value === 'string' ? value.trim() : ''
}

function basename(value: string) {
  const cleaned = value.replace(/[?#].*$/, '').replace(/\\/g, '/')
  const parts = cleaned.split('/').filter(Boolean)
  return parts.length ? parts[parts.length - 1] : ''
}

function extensionFromName(value?: string) {
  if (!value) return ''
  const fileName = basename(value)
  const idx = fileName.lastIndexOf('.')
  if (idx < 0) return ''
  return fileName.slice(idx + 1).toLowerCase()
}

export function normalizeDir(value: unknown): ResultArtifactDir | undefined {
  const dir = normalizeText(value)
  return VALID_DIRS.has(dir as ResultArtifactDir) ? (dir as ResultArtifactDir) : undefined
}

export function inferDirFromPath(path?: string): ResultArtifactDir | undefined {
  if (!path) return undefined
  const normalized = path.replace(/\\/g, '/')
  if (normalized.startsWith('knowledge/')) return 'global-knowledge'
  if (normalized.includes('/download/')) return 'download'
  if (normalized.includes('/knowledge/')) return 'knowledge'
  if (normalized.includes('/history/file/')) return 'file'
  return undefined
}

function inferKindFromMime(mimeType?: unknown, name?: string, path?: string): ResultArtifactKind | undefined {
  const mime = normalizeText(mimeType).toLowerCase()
  if (mime) {
    if (mime.startsWith('image/')) return 'image'
    return 'file'
  }

  const ext = extensionFromName(name || path)
  if (ext && IMAGE_EXT_LABELS[ext]) return 'image'
  if (name || path) return 'file'
  return undefined
}

export function buildViewUrl(name: string, dir?: ResultArtifactDir) {
  const q = dir ? `?dir=${encodeURIComponent(dir)}` : ''
  return `/api/files/view/${encodeURIComponent(name)}${q}`
}

export function buildDownloadUrl(name: string, dir?: ResultArtifactDir) {
  const q = dir ? `?dir=${encodeURIComponent(dir)}` : ''
  return `/api/files/download/${encodeURIComponent(name)}${q}`
}

export function formatBytes(bytes?: number) {
  if (typeof bytes !== 'number' || !Number.isFinite(bytes) || bytes < 0) return ''
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < units.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  if (unitIndex === 0) return `${Math.round(value)} ${units[unitIndex]}`
  const decimals = value < 10 ? 1 : 0
  return `${decimals ? value.toFixed(decimals) : Math.round(value)} ${units[unitIndex]}`
}

function inferTypeLabelFromMime(mimeType?: string, name?: string) {
  const mime = mimeType?.trim().toLowerCase() || ''
  if (mime) {
    if (mime.startsWith('image/')) return IMAGE_MIME_LABELS[mime] || '图片'
    if (FILE_MIME_LABELS[mime]) return FILE_MIME_LABELS[mime]
    const subtype = mime.split('/')[1] || ''
    if (subtype.includes('markdown')) return 'Markdown'
    if (subtype.includes('json')) return 'JSON'
    if (subtype.includes('xml')) return 'XML'
    if (subtype.includes('plain')) return '文本'
    if (subtype.includes('pdf')) return 'PDF'
    if (subtype.includes('zip')) return 'ZIP'
    return subtype ? subtype.toUpperCase() : '文件'
  }

  const ext = extensionFromName(name)
  if (IMAGE_EXT_LABELS[ext]) return IMAGE_EXT_LABELS[ext]
  if (FILE_EXT_LABELS[ext]) return FILE_EXT_LABELS[ext]
  return '文件'
}

export function formatFileMeta(artifact: ResultArtifact) {
  return [inferTypeLabelFromMime(artifact.mimeType, artifact.name), formatBytes(artifact.size)].filter(Boolean).join(' · ')
}

export function formatImageMeta(artifact: ResultArtifact) {
  const sizeText = formatBytes(artifact.size)
  const dims = artifact.width && artifact.height ? `${artifact.width}×${artifact.height}` : ''
  const typeLabel = inferTypeLabelFromMime(artifact.mimeType, artifact.name)
  const imageTypeLabel = typeLabel === '文件' ? '图片' : `${typeLabel} 图片`
  return [imageTypeLabel, dims, sizeText].filter(Boolean).join(' · ')
}

export function normalizeResultArtifact(raw: unknown): ResultArtifact | null {
  if (!raw || typeof raw !== 'object') return null

  const item = raw as Record<string, unknown>
  const name = normalizeText(item.name) || basename(normalizeText(item.path))
  if (!name) return null

  const path = normalizeText(item.path) || undefined
  const dir = normalizeDir(item.dir) || inferDirFromPath(path)
  const rawKind = normalizeText(item.kind).toLowerCase() as ResultArtifactKind | ''
  const inferredKind = inferKindFromMime(item.mimeType, name, path)
  const kind = rawKind && VALID_KINDS.has(rawKind) ? rawKind : inferredKind || null
  if (!kind) return null

  const previewUrl = normalizeText(item.previewUrl) || buildViewUrl(name, dir)
  const downloadUrl = normalizeText(item.downloadUrl) || buildDownloadUrl(name, dir)

  return {
    kind,
    name,
    path,
    dir,
    mimeType: normalizeText(item.mimeType) || undefined,
    size: typeof item.size === 'number' ? item.size : undefined,
    width: typeof item.width === 'number' ? item.width : undefined,
    height: typeof item.height === 'number' ? item.height : undefined,
    previewUrl,
    downloadUrl,
  }
}

export function parseResultArtifacts(result: string): ResultArtifact[] {
  try {
    const data = JSON.parse(result)
    const rawArtifacts: unknown[] = Array.isArray(data?.artifacts)
      ? data.artifacts
      : Array.isArray(data?.files)
        ? data.files
        : []

    return rawArtifacts
      .map(normalizeResultArtifact)
      .filter((item): item is ResultArtifact => Boolean(item))
  } catch {
    return []
  }
}
