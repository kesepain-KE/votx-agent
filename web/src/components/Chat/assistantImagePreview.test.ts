import { describe, expect, it } from 'vitest'
import type { ResultArtifact } from './artifacts'
import {
  imageArtifactsOnly,
  isInlineAssistantImageTool,
  mergeUniqueImageArtifacts,
} from './assistantImagePreview'

describe('assistantImagePreview', () => {
  it('matches only image tools for inline assistant previews', () => {
    expect(isInlineAssistantImageTool('image_generate')).toBe(true)
    expect(isInlineAssistantImageTool('image_edit')).toBe(true)
    expect(isInlineAssistantImageTool('pdf_split')).toBe(false)
    expect(isInlineAssistantImageTool('shell')).toBe(false)
  })

  it('keeps only image artifacts', () => {
    const artifacts = imageArtifactsOnly([
      { kind: 'image', name: 'logo.png' } as ResultArtifact,
      { kind: 'file', name: 'report.md' } as ResultArtifact,
    ])

    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({ kind: 'image', name: 'logo.png' })
  })

  it('deduplicates image artifacts by content identity', () => {
    const a = { kind: 'image', name: 'logo.png', path: 'users/a/download/logo.png' } as ResultArtifact
    const b = { kind: 'image', name: 'logo.png', path: 'users/a/download/logo.png' } as ResultArtifact
    const c = { kind: 'image', name: 'banner.png', path: 'users/a/download/banner.png' } as ResultArtifact

    expect(mergeUniqueImageArtifacts([a], [b, c])).toHaveLength(2)
  })
})
