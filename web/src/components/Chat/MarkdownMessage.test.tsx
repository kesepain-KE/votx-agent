import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { MarkdownMessage } from './MarkdownMessage'

describe('MarkdownMessage', () => {
  it('renders fenced code blocks as embedded panels without syntax highlight classes', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          'Before text',
          '',
          'Inline `code` stays with text.',
          '',
          '```python',
          'def greet(name):',
          '    return f"Hello, {name}!"',
          '',
          'print(greet("votx-agent"))',
          '```',
          '',
          'After text',
        ].join('\n')}
      />,
    )

    expect(html).toContain('<p>Before text</p>')
    expect(html).toContain('<p>Inline <code>code</code> stays with text.</p>')
    expect(html).toContain('code-panel code-panel-normal markdown-code-panel')
    expect(html).toContain('<span class="code-panel-label">Python</span>')
    expect(html).toContain('<div class="code-panel-body">')
    expect(html).toContain('def greet(name):')
    expect(html).not.toContain('<pre class="code-panel-body"><code>')
    expect(html).not.toContain('language-python')
    expect(html).not.toContain('artifact-shell')
    expect(html).toContain('After text')
  })

  it('keeps markdown images suppressed in assistant replies', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          'Plain text',
          '',
          '![example](users/kesepain/history/file/example.png)',
          '',
          '```ts',
          'const ok = true',
          '```',
        ].join('\n')}
      />,
    )

    expect(html).toContain('Plain text')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('example.png')
    expect(html).toContain('code-panel')
  })


  it('renders fenced JSON as artifact chrome', () => {
    const html = renderToStaticMarkup(
      <MarkdownMessage
        content={[
          '```json',
          '{"ok": true}',
          '```',
        ].join('\n')}
      />,
    )

    expect(html).toContain('artifact artifact-json artifact-normal')
    expect(html).toContain('artifact-shell')
    expect(html).toContain('<pre class="artifact-body">')
    expect(html).toContain('<span class="artifact-label">JSON</span>')
    expect(html).toContain('&quot;ok&quot;: true')
  })

})
