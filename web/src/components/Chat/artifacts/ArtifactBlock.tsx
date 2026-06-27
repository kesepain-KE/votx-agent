import type { ArtifactVariant } from './artifactDetect'

interface ArtifactBlockProps {
  variant: ArtifactVariant
  label: string
  content: string
  density?: 'normal' | 'compact'
  className?: string
  copyable?: boolean
}

const variantHints: Record<ArtifactVariant, string> = {
  json: '结构化数据',
  yaml: '配置 / 清单',
  diff: '变更片段',
  terminal: '终端输出',
  code: '代码片段',
}

export function ArtifactBlock({
  variant,
  label,
  content,
  density = 'normal',
  className = '',
  copyable = true,
}: ArtifactBlockProps) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }

  return (
    <div className={`artifact artifact-${variant} artifact-${density}${className ? ` ${className}` : ''}`}>
      <div className="artifact-head">
        <div className="artifact-head-main">
          <span className="artifact-label">{label}</span>
          <span className="artifact-hint">{variantHints[variant]}</span>
        </div>
        {copyable && (
          <button
            type="button"
            className="artifact-copy-btn"
            onClick={handleCopy}
            aria-label={`复制 ${label}`}
            title={`复制 ${label}`}
          >
            ⧉
          </button>
        )}
      </div>
      <div className="artifact-shell">
        <pre className="artifact-body">
          <code>{content}</code>
        </pre>
      </div>
    </div>
  )
}
