import { describe, expect, it } from 'vitest'
import {
  buildDownloadUrl,
  buildViewUrl,
  formatBytes,
  formatFileMeta,
  formatImageMeta,
  inferDirFromPath,
  parseResultArtifacts,
} from './resultArtifacts'

describe('resultArtifacts', () => {
  it('formats bytes compactly', () => {
    expect(formatBytes(12480)).toBe('12 KB')
    expect(formatBytes(839421)).toBe('820 KB')
    expect(formatBytes(1258291)).toBe('1.2 MB')
  })

  it('builds file urls with dir', () => {
    expect(buildViewUrl('report.md', 'download')).toBe('/api/files/view/report.md?dir=download')
    expect(buildDownloadUrl('report.md', 'download')).toBe('/api/files/download/report.md?dir=download')
  })

  it('infers dir from path', () => {
    expect(inferDirFromPath('users/kesepain/download/logo.png')).toBe('download')
    expect(inferDirFromPath('users/kesepain/knowledge/note.md')).toBe('knowledge')
    expect(inferDirFromPath('knowledge/global.md')).toBe('global-knowledge')
  })

  it('parses file and image artifacts and builds missing urls', () => {
    const result = JSON.stringify({
      artifacts: [
        {
          kind: 'file',
          name: 'report.md',
          path: 'users/kesepain/download/report.md',
          dir: 'download',
          mimeType: 'text/markdown',
          size: 12480,
        },
        {
          kind: 'image',
          name: 'logo.png',
          path: 'users/kesepain/download/logo.png',
          dir: 'download',
          mimeType: 'image/png',
          size: 839421,
          width: 1024,
          height: 1024,
        },
      ],
    })

    const artifacts = parseResultArtifacts(result)

    expect(artifacts).toHaveLength(2)
    expect(artifacts[0]).toMatchObject({
      kind: 'file',
      name: 'report.md',
      dir: 'download',
      previewUrl: '/api/files/view/report.md?dir=download',
      downloadUrl: '/api/files/download/report.md?dir=download',
    })
    expect(formatFileMeta(artifacts[0])).toBe('Markdown 路 12 KB')
    expect(artifacts[1]).toMatchObject({
      kind: 'image',
      name: 'logo.png',
      dir: 'download',
      previewUrl: '/api/files/view/logo.png?dir=download',
      downloadUrl: '/api/files/download/logo.png?dir=download',
      width: 1024,
      height: 1024,
    })
    expect(formatImageMeta(artifacts[1])).toBe('PNG 图片 路 1024×1024 路 820 KB')
  })

  it('parses files fallback and infers image kind from mime type', () => {
    const result = JSON.stringify({
      files: [
        {
          name: 'logo.png',
          path: 'users/kesepain/download/logo.png',
          mimeType: 'image/png',
          size: 521334,
        },
      ],
    })

    const artifacts = parseResultArtifacts(result)
    expect(artifacts).toHaveLength(1)
    expect(artifacts[0]).toMatchObject({
      kind: 'image',
      name: 'logo.png',
      dir: 'download',
      previewUrl: '/api/files/view/logo.png?dir=download',
      downloadUrl: '/api/files/download/logo.png?dir=download',
    })
  })

  it('returns empty array for invalid JSON', () => {
    expect(parseResultArtifacts('not json')).toEqual([])
  })
})
