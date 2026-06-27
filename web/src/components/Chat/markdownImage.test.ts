import { describe, expect, it } from 'vitest'
import { buildMarkdownImageCandidates, safeMarkdownUrlTransform } from './markdownImage'

describe('markdownImage', () => {
  it('keeps relative paths first and adds api fallback', () => {
    expect(buildMarkdownImageCandidates('users/kesepain/download/logo.png')).toEqual([
      'users/kesepain/download/logo.png',
      '/api/files/view/logo.png?dir=download',
    ])
  })

  it('keeps windows paths first and adds api fallback', () => {
    expect(
      buildMarkdownImageCandidates('E:\\code\\votx-agent\\users\\kesepain\\history\\file\\【哲风壁纸】代码-多边形.png'),
    ).toEqual([
      'E:\\code\\votx-agent\\users\\kesepain\\history\\file\\【哲风壁纸】代码-多边形.png',
      '/api/files/view/%E3%80%90%E5%93%B2%E9%A3%8E%E5%A3%81%E7%BA%B8%E3%80%91%E4%BB%A3%E7%A0%81-%E5%A4%9A%E8%BE%B9%E5%BD%A2.png?dir=file',
    ])
  })

  it('keeps external urls as-is', () => {
    expect(buildMarkdownImageCandidates('https://example.com/logo.png')).toEqual(['https://example.com/logo.png'])
  })

  it('allows local paths and blocks unsafe schemes', () => {
    expect(safeMarkdownUrlTransform('E:\\code\\votx-agent\\users\\kesepain\\history\\file\\logo.png')).toBe(
      'E:\\code\\votx-agent\\users\\kesepain\\history\\file\\logo.png',
    )
    expect(safeMarkdownUrlTransform('javascript:alert(1)')).toBe('')
  })
})
