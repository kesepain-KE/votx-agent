import type { ResultArtifact } from './resultArtifacts'
import { FileArtifactCard } from './FileArtifactCard'
import { ImageArtifactCard } from './ImageArtifactCard'

interface ResultArtifactListProps {
  artifacts: ResultArtifact[]
}

function getArtifactKey(artifact: ResultArtifact) {
  return [
    artifact.kind,
    artifact.path || '',
    artifact.name,
    artifact.downloadUrl || '',
    artifact.previewUrl || '',
  ].join(':')
}

export function ResultArtifactList({ artifacts }: ResultArtifactListProps) {
  if (!artifacts.length) return null

  return (
    <div className="result-artifact-list">
      {artifacts.map((artifact) => {
        const key = getArtifactKey(artifact)
        if (artifact.kind === 'image') {
          return <ImageArtifactCard key={key} artifact={artifact} />
        }
        return <FileArtifactCard key={key} artifact={artifact} />
      })}
    </div>
  )
}
