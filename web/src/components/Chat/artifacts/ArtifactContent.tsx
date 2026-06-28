import { MarkdownMessage } from '../MarkdownMessage'
import { CodePanel } from '../CodePanel'
import { ArtifactBlock } from './ArtifactBlock'
import { detectRawArtifact } from './artifactDetect'
import { parseResultArtifacts } from './resultArtifacts'
import { ResultArtifactList } from './ResultArtifactList'

interface ArtifactContentProps {
  content: string
  streaming?: boolean
  density?: 'normal' | 'compact'
  markdown?: boolean
  surface?: 'bubble' | 'plain'
  className?: string
  copyable?: boolean
}

export function ArtifactContent({
  content,
  streaming = false,
  density = 'normal',
  markdown = true,
  surface = 'bubble',
  className = '',
  copyable = surface === 'bubble',
}: ArtifactContentProps) {
  const artifact = detectRawArtifact(content, { streaming })
  const markdownStreaming = surface === 'plain' ? true : streaming

  if (artifact) {
    // 如果是 JSON artifact，尝试解析 artifacts 数组渲染文件/媒体卡片
    if (artifact.variant === 'json') {
      const parsed = parseResultArtifacts(content)
      if (parsed.length > 0) {
        return <ResultArtifactList artifacts={parsed} />
      }
    }

    if (artifact.variant === 'code') {
      return (
        <CodePanel
          label={artifact.label}
          content={artifact.content}
          density={density}
          className={className}
          copyable={copyable}
        />
      )
    }

    return (
      <ArtifactBlock
        variant={artifact.variant}
        label={artifact.label}
        content={artifact.content}
        density={density}
        className={className}
        copyable={copyable}
      />
    )
  }

  if (!markdown) {
    return (
      <pre className={`plain-result plain-result-${density}${className ? ` ${className}` : ''}`}>
        {content}
      </pre>
    )
  }

  return (
    <MarkdownMessage
      content={content}
      streaming={markdownStreaming}
      bubble={surface === 'bubble'}
      className={className}
    />
  )
}
