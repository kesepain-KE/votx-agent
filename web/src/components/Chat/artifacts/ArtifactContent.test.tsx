import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import { ArtifactContent } from './ArtifactContent'

describe('ArtifactContent', () => {
  it('renders raw code as an embedded code panel without artifact chrome', () => {
    const html = renderToStaticMarkup(
      <ArtifactContent
        content={[
          'def hello():',
          '    print("votx-agent")',
          '',
          'hello()',
        ].join('\n')}
        streaming={false}
        density="normal"
      />,
    )

    expect(html).toContain('code-panel code-panel-normal')
    expect(html).toContain('<div class="code-panel-body">')
    expect(html).toContain('def hello():')
    expect(html).not.toContain('<pre class="code-panel-body"><code>')
    expect(html).not.toContain('artifact-head')
    expect(html).not.toContain('artifact-shell')
    expect(html).not.toContain('artifact-label')
  })
})
