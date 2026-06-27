import { MarkdownMessage } from '../MarkdownMessage'
import { ArtifactBlock } from './ArtifactBlock'
import { detectRawArtifact } from './artifactDetect'

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

  if (artifact) {
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
      streaming={streaming}
      bubble={surface === 'bubble'}
      copyable={copyable}
      className={className}
    />
  )
}
