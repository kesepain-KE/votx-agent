import { MarkdownMessage } from './MarkdownMessage'

type ArtifactVariant = 'json' | 'yaml' | 'diff' | 'terminal' | 'code'

interface Props {
  content: string
  streaming?: boolean
}

const ARTIFACT_LABELS: Record<ArtifactVariant, string> = {
  json: 'JSON',
  yaml: 'YAML',
  diff: 'Diff',
  terminal: 'Terminal',
  code: 'Code',
}

function normalizeContent(content: string) {
  return content.replace(/\r\n/g, '\n')
}

function looksLikeMarkdown(content: string) {
  return /(^#{1,6}\s)|(^\s*[-*+]\s)|(^\s*\d+\.\s)|(^\s*>\s)|(^\s*```)|(^\s*~~~)|(\[[^\]]+\]\([^)]+\))|(!\[[^\]]*\]\([^)]+\))|(\|.*\|)/m.test(content)
}

function parseJsonPreview(content: string) {
  const trimmed = content.trim()
  if (!trimmed || !/^[{\[]/.test(trimmed)) return null
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return null
  }
}

function looksLikeCode(content: string) {
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

function looksLikeDiff(content: string) {
  const lines = content.split('\n')
  let score = 0
  for (const line of lines) {
    if (/^(diff --git|index |@@ |--- |\+\+\+ )/.test(line)) score += 2
    else if (/^[+-]/.test(line)) score += 1
  }
  return score >= 3
}

function looksLikeTerminal(content: string) {
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

function looksLikeYaml(content: string) {
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

function ArtifactBlock({ variant, content }: { variant: ArtifactVariant; content: string }) {
  return (
    <div className={`bubble artifact artifact-${variant}`}>
      <div className="artifact-head">
        <span className="artifact-label">{ARTIFACT_LABELS[variant]}</span>
        <span className="artifact-actions">
          <button
            type="button"
            className="artifact-copy-btn"
            title={`复制${ARTIFACT_LABELS[variant]}`}
            aria-label={`复制${ARTIFACT_LABELS[variant]}`}
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(content)
              } catch {
                // Ignore clipboard errors in non-secure contexts.
              }
            }}
          >
            ⧉
          </button>
        </span>
      </div>
      <pre>{content}</pre>
    </div>
  )
}

export function AssistantMessageContent({ content, streaming = false }: Props) {
  const normalized = normalizeContent(content)
  const jsonPreview = parseJsonPreview(normalized)
  if (jsonPreview) return <ArtifactBlock variant="json" content={jsonPreview} />
  if (looksLikeDiff(normalized)) return <ArtifactBlock variant="diff" content={normalized} />
  if (looksLikeTerminal(normalized)) return <ArtifactBlock variant="terminal" content={normalized} />
  if (looksLikeYaml(normalized)) return <ArtifactBlock variant="yaml" content={normalized} />
  if (!streaming && looksLikeCode(normalized)) return <ArtifactBlock variant="code" content={normalized} />
  return <MarkdownMessage content={normalized} streaming={streaming} />
}
