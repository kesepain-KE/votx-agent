import { useState, useEffect, useCallback } from 'react'

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
  const [copied, setCopied] = useState(false)

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }, [content])

  useEffect(() => {
    if (!copied) return
    const timer = setTimeout(() => setCopied(false), 2000)
    return () => clearTimeout(timer)
  }, [copied])

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
            className={`code-panel-copy${copied ? ' copied' : ''}`}
            onClick={handleCopy}
            disabled={copied}
            aria-label={copied ? '已复制' : `复制 ${label}`}
            title={copied ? '已复制' : `复制 ${label}`}
          >
            {copied ? '✓' : '⧉'}
          </button>
        )}
      </div>
      <div className="code-panel-body">{content}</div>
    </div>
  )
}
