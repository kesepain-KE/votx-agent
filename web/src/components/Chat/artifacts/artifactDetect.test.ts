import { describe, expect, it } from 'vitest'
import {
  classifyFencedArtifact,
  detectRawArtifact,
  normalizeContent,
  parseJsonPreview,
  prettyJson,
} from './artifactDetect'

describe('artifactDetect', () => {
  it('normalizes CRLF to LF', () => {
    expect(normalizeContent('a\r\nb\r\n')).toBe('a\nb\n')
  })

  it('pretty prints valid JSON', () => {
    expect(prettyJson('{"ok":true,"name":"votx-agent"}')).toBe('{\n  "ok": true,\n  "name": "votx-agent"\n}')
  })

  it('keeps invalid JSON unchanged', () => {
    const input = '{"ok":true'
    expect(prettyJson(input)).toBe(input)
  })

  it('returns a JSON preview for raw JSON', () => {
    expect(parseJsonPreview('{"ok":true}')).toBe('{\n  "ok": true\n}')
  })

  it('detects raw JSON artifact', () => {
    expect(detectRawArtifact('{"ok":true,"name":"votx-agent"}')).toMatchObject({
      variant: 'json',
      label: 'JSON',
      content: '{\n  "ok": true,\n  "name": "votx-agent"\n}',
    })
  })

  it('detects already pretty raw JSON artifact', () => {
    const pretty = '{\n  "ok": true\n}'

    expect(detectRawArtifact(pretty)).toMatchObject({
      variant: 'json',
      label: 'JSON',
      content: pretty,
    })
  })

  it('detects raw diff artifact', () => {
    const artifact = detectRawArtifact([
      'diff --git a/a.ts b/a.ts',
      'index 111..222 100644',
      '--- a/a.ts',
      '+++ b/a.ts',
      '@@ -1,2 +1,2 @@',
      '-const oldValue = 1',
      '+const newValue = 2',
    ].join('\n'))

    expect(artifact).toMatchObject({
      variant: 'diff',
      label: 'Diff',
    })
  })

  it('does not misclassify markdown content with a fenced diff block as raw diff', () => {
    const artifact = detectRawArtifact([
      '## 正文层测试',
      '',
      '这里是普通正文。',
      '',
      '```diff',
      '--- a/start.py',
      '+++ b/start.py',
      '@@ -1,1 +1,1 @@',
      '-print("old")',
      '+print("new")',
      '```',
      '',
      '后面还有普通正文。',
    ].join('\n'))

    expect(artifact).toBeNull()
  })

  it('detects raw terminal artifact', () => {
    const artifact = detectRawArtifact([
      '$ npm run build',
      '$ tsc --noEmit',
      '$ vite build',
    ].join('\n'))

    expect(artifact).toMatchObject({
      variant: 'terminal',
      label: 'Terminal',
    })
  })

  it('detects raw YAML artifact', () => {
    const artifact = detectRawArtifact([
      'name: votx-agent',
      'type: skill',
      'enabled: true',
    ].join('\n'))

    expect(artifact).toMatchObject({
      variant: 'yaml',
      label: 'YAML',
    })
  })

  it('does not misclassify a markdown list as YAML', () => {
    const artifact = detectRawArtifact([
      '- item one',
      '- item two',
      '- item three',
    ].join('\n'))

    expect(artifact).toBeNull()
  })

  it('does not misclassify nested blockquote markdown as terminal', () => {
    const artifact = detectRawArtifact([
      '> 引用一',
      '> > 嵌套引用',
      '> 引用二',
      '',
      '仍然是普通 markdown 内容',
    ].join('\n'))

    expect(artifact).toBeNull()
  })

  it('detects raw code only when not streaming', () => {
    const code = [
      'import { test } from "vitest"',
      'const name = "votx-agent"',
      'function run() { return name }',
    ].join('\n')

    expect(detectRawArtifact(code, { streaming: false })).toMatchObject({
      variant: 'code',
      label: '代码',
    })
    expect(detectRawArtifact(code, { streaming: true })).toBeNull()
  })

  it('classifies fenced JSON as JSON artifact', () => {
    expect(classifyFencedArtifact('json', '{"ok":true}')).toEqual({
      variant: 'json',
      label: 'JSON',
      content: '{\n  "ok": true\n}',
      language: 'json',
    })
  })

  it('classifies fenced YAML as YAML artifact', () => {
    expect(classifyFencedArtifact('yaml', 'name: votx-agent')).toEqual({
      variant: 'yaml',
      label: 'YAML',
      content: 'name: votx-agent',
      language: 'yaml',
    })
  })

  it('classifies fenced diff as Diff artifact', () => {
    expect(classifyFencedArtifact('diff', '- old\n+ new')).toMatchObject({
      variant: 'diff',
      label: 'Diff',
      language: 'diff',
    })
  })

  it('classifies fenced bash as Terminal artifact', () => {
    expect(classifyFencedArtifact('bash', 'npm run build')).toMatchObject({
      variant: 'terminal',
      label: 'Terminal',
      language: 'bash',
    })
  })

  it('classifies fenced TypeScript as Code artifact', () => {
    expect(classifyFencedArtifact('ts', 'const name: string = "votx-agent"')).toMatchObject({
      variant: 'code',
      label: '代码',
      language: 'ts',
    })
  })

  it('classifies unknown fenced language as generic code artifact', () => {
    expect(classifyFencedArtifact('abc', 'some content')).toMatchObject({
      variant: 'code',
      label: '代码',
      language: 'abc',
    })
  })
})
