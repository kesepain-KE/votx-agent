import { useState } from 'react'
import type { ResultArtifact } from './resultArtifacts'
import { formatImageMeta } from './resultArtifacts'

interface ImageArtifactCardProps {
  artifact: ResultArtifact
}

export function ImageArtifactCard({ artifact }: ImageArtifactCardProps) {
  const [previewFailed, setPreviewFailed] = useState(false)

  const handleCopyPath = async () => {
    if (!artifact.path) return
    try {
      await navigator.clipboard.writeText(artifact.path)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }

  const previewNode = previewFailed || !artifact.previewUrl ? (
    <div className="result-image-placeholder">预览不可用</div>
  ) : (
    <img
      src={artifact.previewUrl}
      alt={artifact.name}
      loading="lazy"
      className="result-image-preview"
      onError={() => setPreviewFailed(true)}
    />
  )

  return (
    <div className="result-card result-card-image">
      <div className="result-card-head">
        <div>
          <div className="result-card-title">🖼 {artifact.name}</div>
          <div className="result-card-meta">{formatImageMeta(artifact)}</div>
        </div>
      </div>

      {artifact.previewUrl ? (
        <a
          href={artifact.previewUrl}
          target="_blank"
          rel="noreferrer"
          className="result-image-link"
        >
          {previewNode}
        </a>
      ) : (
        <div className="result-image-link">
          {previewNode}
        </div>
      )}

      <div className="result-card-actions">
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
