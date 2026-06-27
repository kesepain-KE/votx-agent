interface CodePanelProps {
  label: string
  content: string
  density?: 'normal' | 'compact'
  className?: string
  copyable?: boolean
}

export function CodePanel({
  label,
  content,
  density = 'normal',
  className = '',
  copyable = true,
}: CodePanelProps) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }

  return (
    <div className={`code-panel code-panel-${density}${className ? ` ${className}` : ''}`}>
      <div className="code-panel-head">
        <div className="code-panel-head-main">
          <span className="code-panel-label">{label}</span>
          <span className="code-panel-hint">代码片段</span>
        </div>
        {copyable && (
          <button
            type="button"
            className="code-panel-copy"
            onClick={handleCopy}
            aria-label={`复制 ${label}`}
            title={`复制 ${label}`}
          >
            ⧉
          </button>
        )}
      </div>
      <div className="code-panel-body">{content}</div>
    </div>
  )
}
