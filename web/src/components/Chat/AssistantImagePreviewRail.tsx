import { useEffect, useMemo, useRef, useState } from 'react'
import type { Message, ToolCard } from '@/types'
import { AssistantImageBubble } from './AssistantImageBubble'
import { imageArtifactsOnly, isInlineAssistantImageTool, mergeUniqueImageArtifacts } from './assistantImagePreview'
import { parseResultArtifacts, type ResultArtifact } from './artifacts'

interface AssistantImagePreviewRailProps {
  message: Message
  loadToolResult: (logId: string) => Promise<string>
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

function getInlineAssistantImageToolCalls(tools: ToolCard[] | undefined) {
  return (tools || []).filter((tool) => isInlineAssistantImageTool(tool.name) && Boolean(tool.log_id))
}

export function AssistantImagePreviewRail({ message, loadToolResult }: AssistantImagePreviewRailProps) {
  const toolCalls = useMemo(() => getInlineAssistantImageToolCalls(message.tools), [message.tools])
  const cacheRef = useRef<Map<string, ResultArtifact[]>>(new Map())
  const [artifacts, setArtifacts] = useState<ResultArtifact[]>([])
  const cacheKey = toolCalls.map((tool) => tool.log_id).join('|')

  useEffect(() => {
    let cancelled = false

    if (!toolCalls.length) {
      setArtifacts([])
      return () => {
        cancelled = true
      }
    }

    const cachedArtifacts: ResultArtifact[] = []
    const missingLogIds: string[] = []
    for (const tool of toolCalls) {
      const logId = tool.log_id
      if (!logId) continue
      const cached = cacheRef.current.get(logId)
      if (cached) {
        cachedArtifacts.push(...cached)
      } else {
        missingLogIds.push(logId)
      }
    }

    const mergedCached = mergeUniqueImageArtifacts([], cachedArtifacts)
    setArtifacts(mergedCached)

    if (!missingLogIds.length) {
      return () => {
        cancelled = true
      }
    }

    void (async () => {
      const resolved = await Promise.all(
        missingLogIds.map(async (logId) => {
          try {
            const result = await loadToolResult(logId)
            const imageArtifacts = imageArtifactsOnly(parseResultArtifacts(result))
            cacheRef.current.set(logId, imageArtifacts)
            return imageArtifacts
          } catch {
            cacheRef.current.set(logId, [])
            return []
          }
        }),
      )

      if (cancelled) return
      const resolvedArtifacts = resolved.reduce<ResultArtifact[]>(
        (all, items) => all.concat(items),
        [],
      )
      setArtifacts(mergeUniqueImageArtifacts(mergedCached, resolvedArtifacts))
    })()

    return () => {
      cancelled = true
    }
  }, [cacheKey, loadToolResult, toolCalls])

  if (!artifacts.length) return null

  return (
    <div className="assistant-image-rail">
      {artifacts.map((artifact) => (
        <AssistantImageBubble key={getArtifactKey(artifact)} artifact={artifact} />
      ))}
    </div>
  )
}
