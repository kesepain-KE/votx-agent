import type { ResultArtifact } from './resultArtifacts'
import { formatFileMeta } from './resultArtifacts'

interface FileArtifactCardProps {
  artifact: ResultArtifact
}

export function FileArtifactCard({ artifact }: FileArtifactCardProps) {
  const handleCopyPath = async () => {
    if (!artifact.path) return
    try {
      await navigator.clipboard.writeText(artifact.path)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }

  return (
    <div className="result-card result-card-file">
      <div className="result-card-icon" aria-hidden="true">📄</div>
      <div className="result-card-main">
        <div className="result-card-title">{artifact.name}</div>
        <div className="result-card-meta">{formatFileMeta(artifact)}</div>
        <div className="result-card-actions">
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
    </div>
  )
}
