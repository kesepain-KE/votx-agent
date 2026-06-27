import { useState } from 'react'
import type { ResultArtifact } from './artifacts'
import { formatImageMeta } from './artifacts'

interface AssistantImageBubbleProps {
  artifact: ResultArtifact
}

export function AssistantImageBubble({ artifact }: AssistantImageBubbleProps) {
  const [previewFailed, setPreviewFailed] = useState(false)

  const handleCopyPath = async () => {
    if (!artifact.path) return
    try {
      await navigator.clipboard.writeText(artifact.path)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }

  const canPreview = Boolean(artifact.previewUrl) && !previewFailed
  const previewNode = canPreview ? (
    <img
      src={artifact.previewUrl}
      alt={artifact.name}
      loading="lazy"
      className="assistant-image-preview"
      onError={() => setPreviewFailed(true)}
    />
  ) : (
    <div className="assistant-image-placeholder">预览不可用</div>
  )

  return (
    <div className="assistant-image-bubble">
      <div className="assistant-image-head">
        <div>
          <div className="assistant-image-title">🖼 {artifact.name}</div>
          <div className="assistant-image-meta">{formatImageMeta(artifact)}</div>
        </div>
      </div>

      {canPreview ? (
        <a href={artifact.previewUrl} target="_blank" rel="noreferrer" className="assistant-image-link">
          {previewNode}
        </a>
      ) : (
        <div className="assistant-image-link">{previewNode}</div>
      )}

      <div className="assistant-image-actions">
        {artifact.previewUrl && (
          <a href={artifact.previewUrl} target="_blank" rel="noreferrer">
            预览
          </a>
        )}
        {artifact.downloadUrl && (
          <a href={artifact.downloadUrl} download>
            下载
          </a>
        )}
        {artifact.path && (
          <button type="button" onClick={handleCopyPath}>
            复制路径
          </button>
        )}
      </div>
    </div>
  )
}
