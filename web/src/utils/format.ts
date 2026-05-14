declare global {
  interface Window {
    katex?: {
      renderToString: (
        input: string,
        options?: { displayMode?: boolean; throwOnError?: boolean; strict?: boolean },
      ) => string
    }
  }
}

type StashedBlock =
  | { type: 'code'; content: string; lang?: string }
  | { type: 'inlineCode'; content: string }
  | { type: 'details'; content: string }
  | { type: 'mathBlock'; content: string }
  | { type: 'mathInline'; content: string }

export function escHtml(s: string): string {
  return String(s || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function fmtSize(n: number): string {
  if (!n) return ''
  if (n < 1024) return `${n} B`
  if (n < 1048576) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1048576).toFixed(1)} MB`
}

export function formatNumber(n: number): string {
  if (!n && n !== 0) return ''
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
  return String(n)
}

export function fmtTime(ts: number): string {
  if (!ts) return ''
  const d = new Date(ts * 1000)
  const diff = Date.now() - d.getTime()
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return d.toLocaleDateString('zh-CN')
}

export function fmtMs(ms: number): string {
  if (!ms && ms !== 0) return ''
  if (ms < 1000) return `${ms}ms`
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
  return `${(ms / 60000).toFixed(1)}min`
}

export function isImageFile(name: string): boolean {
  return /\.(png|jpe?g|gif|webp|svg|bmp|ico)$/i.test(name)
}

function renderMath(content: string, displayMode: boolean): string {
  try {
    if (!window.katex) throw new Error('KaTeX not loaded')
    return window.katex.renderToString(content, {
      displayMode,
      throwOnError: false,
      strict: false,
    })
  } catch {
    return displayMode
      ? `<pre class="katex-error">${escHtml(content)}</pre>`
      : `<code class="katex-error">${escHtml(content)}</code>`
  }
}

export function formatContent(input: string): string {
  let text = String(input || '')

  function parseNestedList(lines: string[], startIdx: number, baseIndent?: number): { html: string; endIdx: number } {
    if (baseIndent === undefined) {
      const firstM = lines[startIdx].match(/^(\s*)([-*]|\d+\.)\s/)
      baseIndent = firstM ? firstM[1].length : 0
    }
    let html = ''
    let currentTag: 'ul' | 'ol' | null = null
    let i = startIdx

    while (i < lines.length) {
      const m = lines[i].match(/^(\s*)([-*]|\d+\.)\s/)
      if (!m) break

      const indent = m[1].length
      if (indent < baseIndent) break
      if (indent > baseIndent) {
        i++
        continue
      }

      const marker = m[2]
      const rest = lines[i].slice(m[0].length)
      const type: 'ul' | 'ol' = marker === '-' || marker === '*' ? 'ul' : 'ol'
      const cb = rest.match(/^\[(\s|x|X)\]\s?(.*)$/)
      const itemText = cb ? cb[2] : rest
      const checked = cb ? cb[1] !== ' ' : null

      if (type !== currentTag) {
        if (currentTag) html += `</${currentTag}>`
        html += `<${type}>`
        currentTag = type
      }

      html += '<li>'
      if (checked !== null) html += `<input type="checkbox" disabled${checked ? ' checked' : ''}>`
      html += escHtml(itemText)
      i++

      if (i < lines.length) {
        const nextM = lines[i].match(/^(\s*)([-*]|\d+\.)\s/)
        if (nextM && nextM[1].length > indent) {
          const sub = parseNestedList(lines, i, nextM[1].length)
          html += sub.html
          i = sub.endIdx
        }
      }

      html += '</li>'
    }

    if (currentTag) html += `</${currentTag}>`
    return { html, endIdx: i }
  }

  const blocks: StashedBlock[] = []
  const stash = (block: StashedBlock): string => {
    const ph = `\x00${blocks.length}\x00`
    blocks.push(block)
    return ph
  }

  text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_all, lang: string, code: string) =>
    stash({ type: 'code', content: code, lang }),
  )

  text = text.replace(/`([^`]+)`/g, (_all, code: string) => stash({ type: 'inlineCode', content: code }))

  text = text.replace(/<details[^>]*>([\s\S]*?)<\/details>/g, (_all, inner: string) =>
    stash({ type: 'details', content: inner }),
  )

  text = text.replace(/(?<!\\)\$\$([\s\S]+?)(?<!\\)\$\$/g, (_all, math: string) =>
    stash({ type: 'mathBlock', content: math.trim() }),
  )
  text = text.replace(/(?:^|\n)(\s*\\begin\{[a-zA-Z*]+\}[\s\S]*?\\end\{[a-zA-Z*]+\})/g, (_all, math: string) =>
    stash({ type: 'mathBlock', content: math.trim() }),
  )

  text = text.replace(/(?<!\\)\$([^\s\d$](?:[^$]*[^\s$])?)(?<!\\)\$/g, (_all, math: string) =>
    stash({ type: 'mathInline', content: math }),
  )

  text = text.replace(/\\(.)/g, '$1')

  const lines = text.split('\n')
  const out: string[] = []
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]
    const t = line.trim()

    const hMatch = line.match(/^(#{1,6})\s+(.+)$/)
    if (hMatch) {
      const level = hMatch[1].length
      out.push(`<h${level}>${escHtml(hMatch[2])}</h${level}>`)
      continue
    }

    if (/^(-{3,}|\*{3,})$/.test(t)) {
      out.push('<hr>')
      continue
    }

    if (/^>+/.test(line)) {
      const q: string[] = []
      while (i < lines.length && /^>+/.test(lines[i])) {
        q.push(escHtml(lines[i].replace(/^>+\s?/, '')))
        i++
      }
      i--
      out.push(`<blockquote>${q.join('<br>')}</blockquote>`)
      continue
    }

    if (/\|/.test(line) && i + 1 < lines.length && /^\|?[\s\-:]+\|[\s\-:|]+\|?$/.test(lines[i + 1])) {
      const hCells = line
        .split('|')
        .filter((c) => c.trim())
        .map((c) => escHtml(c.trim()))
      const sCells = lines[i + 1].split('|').filter((c) => c.trim())
      const aligns = sCells.map((c) => {
        const s = c.trim()
        if (s.charAt(0) === ':' && s.charAt(s.length - 1) === ':') return 'center'
        if (s.charAt(s.length - 1) === ':') return 'right'
        return 'left'
      })
      let tbl = '<table><thead><tr>'
      for (let hi = 0; hi < hCells.length; hi++) {
        tbl += `<th style="text-align:${aligns[hi] || 'left'}">${hCells[hi]}</th>`
      }
      tbl += '</tr></thead><tbody>'
      i += 2
      while (i < lines.length && /\|/.test(lines[i]) && !/^\|?[\s\-:]+\|[\s\-:|]+\|?$/.test(lines[i])) {
        const dCells = lines[i]
          .split('|')
          .filter((c) => c.trim())
          .map((c) => escHtml(c.trim()))
        tbl += '<tr>'
        for (let di = 0; di < dCells.length; di++) {
          tbl += `<td style="text-align:${aligns[di] || 'left'}">${dCells[di]}</td>`
        }
        tbl += '</tr>'
        i++
      }
      i--
      tbl += '</tbody></table>'
      out.push(tbl)
      continue
    }

    if ((/^[\s]*[-*]\s/.test(line) && !/^[\s]*\*\*/.test(line)) || /^[\s]*\d+\.\s/.test(line)) {
      const listResult = parseNestedList(lines, i)
      out.push(listResult.html)
      i = listResult.endIdx - 1
      continue
    }

    if (line && i + 1 < lines.length && /^:\s/.test(lines[i + 1])) {
      let dl = `<dl><dt>${escHtml(t)}</dt>`
      i++
      while (i < lines.length && /^:\s/.test(lines[i])) {
        dl += `<dd>${escHtml(lines[i].replace(/^:\s/, ''))}</dd>`
        i++
      }
      i--
      dl += '</dl>'
      out.push(dl)
      continue
    }

    out.push(escHtml(line))
  }
  text = out.join('\n')

  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
  text = text.replace(/\*([^*]+)\*/g, '<em>$1</em>')
  text = text.replace(/~~([^~]+)~~/g, '<del>$1</del>')
  text = text.replace(/~([^~]+)~/g, '<sub>$1</sub>')
  text = text.replace(/\^([^^]+)\^/g, '<sup>$1</sup>')
  text = text.replace(/==([^=]+)==/g, '<mark>$1</mark>')
  text = text.replace(/\+\+([^+]+)\+\+/g, '<u>$1</u>')
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>')

  text = text.replace(/&lt;kbd&gt;/g, '<kbd>').replace(/&lt;\/kbd&gt;/g, '</kbd>')
  text = text.replace(/&lt;mark&gt;/g, '<mark>').replace(/&lt;\/mark&gt;/g, '</mark>')
  text = text.replace(/&lt;abbr\s+title=&quot;(.*?)&quot;&gt;/g, '<abbr title="$1">').replace(/&lt;\/abbr&gt;/g, '</abbr>')

  for (let j = 0; j < blocks.length; j++) {
    const b = blocks[j]
    const ph = `\x00${j}\x00`
    let html = ''

    if (b.type === 'code') html = `<pre><code>${escHtml(b.content)}</code></pre>`
    else if (b.type === 'details') html = `<details>${b.content}</details>`
    else if (b.type === 'inlineCode') html = `<code>${escHtml(b.content)}</code>`
    else if (b.type === 'mathBlock') html = renderMath(b.content, true)
    else if (b.type === 'mathInline') html = renderMath(b.content, false)

    text = text.split(ph).join(html)
  }

  return text
}

