import type { ResultArtifact } from './artifacts'

export const INLINE_ASSISTANT_MEDIA_TOOLS = new Set([
  'speech_generate',
  'speech_to_speech',
  'video_download',
  'video_generate',
])

export function isInlineAssistantMediaTool(name?: string) {
  return typeof name === 'string' && INLINE_ASSISTANT_MEDIA_TOOLS.has(name)
}

export function mediaArtifactsOnly(artifacts: ResultArtifact[]) {
  return artifacts.filter(
    (artifact) =>
      artifact.mimeType?.startsWith('audio/') ||
      artifact.mimeType?.startsWith('video/'),
  )
}

function artifactKey(artifact: ResultArtifact) {
  return [
    artifact.kind,
    artifact.path || '',
    artifact.name,
    artifact.previewUrl || '',
    artifact.downloadUrl || '',
  ].join(':')
}

export function mergeUniqueMediaArtifacts(existing: ResultArtifact[], incoming: ResultArtifact[]) {
  const seen = new Set(existing.map(artifactKey))
  const merged = [...existing]
  for (const artifact of incoming) {
    const key = artifactKey(artifact)
    if (seen.has(key)) continue
    seen.add(key)
    merged.push(artifact)
  }
  return merged
}
