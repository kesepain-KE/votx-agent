import type { ArtifactVariant } from './artifactDetect'

interface ArtifactBlockProps {
  variant: ArtifactVariant
  label: string
  content: string
  density?: 'normal' | 'compact'
  className?: string
  copyable?: boolean
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
        <span className="artifact-label">{label}</span>
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
      <pre className="artifact-body">
        <code>{content}</code>
      </pre>
    </div>
  )
}
