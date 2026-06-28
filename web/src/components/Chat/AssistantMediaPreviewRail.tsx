import { useEffect, useMemo, useRef, useState } from 'react'
import type { Message, ToolCard } from '@/types'
import { FileArtifactCard } from './artifacts/FileArtifactCard'
import { parseResultArtifacts, type ResultArtifact } from './artifacts'
import {
  isInlineAssistantMediaTool,
  mediaArtifactsOnly,
  mergeUniqueMediaArtifacts,
} from './assistantMediaPreview'

interface AssistantMediaPreviewRailProps {
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

function getInlineAssistantMediaToolCalls(tools: ToolCard[] | undefined) {
  return (tools || []).filter((tool) => isInlineAssistantMediaTool(tool.name) && Boolean(tool.log_id))
}

export function AssistantMediaPreviewRail({ message, loadToolResult }: AssistantMediaPreviewRailProps) {
  const toolCalls = useMemo(() => getInlineAssistantMediaToolCalls(message.tools), [message.tools])
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

    const mergedCached = mergeUniqueMediaArtifacts([], cachedArtifacts)
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
            const mediaArtifacts = mediaArtifactsOnly(parseResultArtifacts(result))
            cacheRef.current.set(logId, mediaArtifacts)
            return mediaArtifacts
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
      setArtifacts(mergeUniqueMediaArtifacts(mergedCached, resolvedArtifacts))
    })()

    return () => {
      cancelled = true
    }
  }, [cacheKey, loadToolResult, toolCalls])

  if (!artifacts.length) return null

  return (
    <div className="assistant-media-rail">
      {artifacts.map((artifact) => (
        <FileArtifactCard key={getArtifactKey(artifact)} artifact={artifact} />
      ))}
    </div>
  )
}
