import type { ResultArtifact } from './artifacts'

export const INLINE_ASSISTANT_IMAGE_TOOLS = new Set(['image_generate', 'image_edit'])

export function isInlineAssistantImageTool(name?: string) {
  return typeof name === 'string' && INLINE_ASSISTANT_IMAGE_TOOLS.has(name)
}

export function imageArtifactsOnly(artifacts: ResultArtifact[]) {
  return artifacts.filter((artifact) => artifact.kind === 'image')
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

export function mergeUniqueImageArtifacts(existing: ResultArtifact[], incoming: ResultArtifact[]) {
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
