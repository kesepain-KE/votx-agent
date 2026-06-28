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

  const mime = artifact.mimeType?.toLowerCase() || ''
  const previewUrl = artifact.previewUrl
  const downloadUrl = artifact.downloadUrl

  const actions = (
    <div className="result-card-actions" style={{ flexWrap: 'nowrap', gap: 8, flexShrink: 0, marginTop: 0 }}>
      {downloadUrl && (
        <a href={downloadUrl} download>
          下载
        </a>
      )}
      {artifact.path && (
        <button type="button" onClick={handleCopyPath}>
          复制路径
        </button>
      )}
    </div>
  )

  // 音频内联预览
  if (mime.startsWith('audio/') && previewUrl) {
    return (
      <div className="result-card result-card-file result-card-audio" style={{ flexDirection: 'column' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          alignSelf: 'stretch',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span
              className="result-card-title"
              title={artifact.name}
              style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '20ch', lineHeight: 1 }}
            >
              🎵 {artifact.name}
            </span>
            <span className="result-card-meta" style={{ whiteSpace: 'nowrap', flexShrink: 0, lineHeight: 1 }}>
              {formatFileMeta(artifact)}
            </span>
          </div>
          {actions}
        </div>
        <audio controls src={previewUrl} style={{ width: '100%', display: 'block', marginTop: 8 }}>
          您的浏览器不支持音频播放。
        </audio>
      </div>
    )
  }

  // 视频内联预览
  if (mime.startsWith('video/') && previewUrl) {
    return (
      <div className="result-card result-card-file result-card-video" style={{ flexDirection: 'column' }}>
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          alignSelf: 'stretch',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, minWidth: 0 }}>
            <span
              className="result-card-title"
              title={artifact.name}
              style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '20ch', lineHeight: 1 }}
            >
              🎬 {artifact.name}
            </span>
            <span className="result-card-meta" style={{ whiteSpace: 'nowrap', flexShrink: 0, lineHeight: 1 }}>
              {formatFileMeta(artifact)}
            </span>
          </div>
          {actions}
        </div>
        <video
          controls
          src={previewUrl}
          style={{ maxWidth: '100%', maxHeight: 400, display: 'block', marginTop: 8 }}
        >
          您的浏览器不支持视频播放。
        </video>
      </div>
    )
  }

  // 默认文件卡片
  return (
    <div className="result-card result-card-file">
      <div className="result-card-icon" aria-hidden="true">📄</div>
      <div className="result-card-main">
        <div className="result-card-title" title={artifact.name} style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{artifact.name}</div>
        <div className="result-card-meta">{formatFileMeta(artifact)}</div>
        <div className="result-card-actions" style={{ flexWrap: 'nowrap', gap: 8 }}>
          {downloadUrl && (
            <a href={downloadUrl} download>
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
