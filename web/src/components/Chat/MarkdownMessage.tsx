import { Children, isValidElement, type ReactElement, type ReactNode } from 'react'
import ReactMarkdown, { type Components, type UrlTransform } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema, type Options as SanitizeOptions } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import remarkBreaks from 'remark-breaks'
import 'katex/dist/katex.min.css'

type CodeVariant = 'code' | 'json' | 'yaml' | 'diff' | 'terminal'

interface CodeArtifactInfo {
  variant: CodeVariant
  label: string
  content: string
}

const markdownSchema: SanitizeOptions = {
  ...defaultSchema,
  attributes: {
    ...defaultSchema.attributes,
    code: [
      ...(defaultSchema.attributes?.code || []),
      ['className', 'language-math', 'math-inline', 'math-display'],
    ],
  },
}

const safeUrlTransform: UrlTransform = (url) => {
  const value = url.trim()
  if (!value) return ''
  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(value)
  if (!hasScheme) return value
  if (/^(https?:|mailto:)/i.test(value)) return value
  return ''
}

function flattenText(node: ReactNode): string {
  if (node == null || typeof node === 'boolean') return ''
  if (typeof node === 'string' || typeof node === 'number') return String(node)
  if (Array.isArray(node)) return node.map((item) => flattenText(item)).join('')
  if (isValidElement(node)) {
    const child = node as ReactElement<{ children?: ReactNode }>
    return flattenText(child.props.children)
  }
  return ''
}

function prettyJson(content: string) {
  const trimmed = content.trim()
  if (!trimmed || !/^[{\[]/.test(trimmed)) return content
  try {
    return JSON.stringify(JSON.parse(trimmed), null, 2)
  } catch {
    return content
  }
}

function classifyCodeBlock(language: string, content: string): CodeArtifactInfo {
  const normalized = language.trim().toLowerCase()
  if (normalized === 'json') return { variant: 'json', label: 'JSON', content: prettyJson(content) }
  if (normalized === 'yaml' || normalized === 'yml') return { variant: 'yaml', label: 'YAML', content }
  if (normalized === 'diff' || normalized === 'patch') return { variant: 'diff', label: 'Diff', content }
  if (normalized === 'bash' || normalized === 'sh' || normalized === 'shell' || normalized === 'zsh'
    || normalized === 'powershell' || normalized === 'pwsh' || normalized === 'ps1'
    || normalized === 'cmd' || normalized === 'console' || normalized === 'terminal') {
    return { variant: 'terminal', label: 'Terminal', content }
  }

  const labelMap: Record<string, string> = {
    ts: 'TypeScript',
    typescript: 'TypeScript',
    tsx: 'TSX',
    js: 'JavaScript',
    javascript: 'JavaScript',
    jsx: 'JSX',
    py: 'Python',
    python: 'Python',
    go: 'Go',
    rs: 'Rust',
    java: 'Java',
    c: 'C',
    cpp: 'C++',
    cc: 'C++',
    cs: 'C#',
    sql: 'SQL',
    html: 'HTML',
    css: 'CSS',
    xml: 'XML',
    bash: 'Terminal',
    shell: 'Terminal',
    powershell: 'PowerShell',
    mermaid: 'Mermaid',
    txt: 'Text',
    text: 'Text',
  }

  return {
    variant: 'code',
    label: labelMap[normalized] || (normalized ? normalized.toUpperCase() : 'Code'),
    content,
  }
}

function CopyAction({ text, label }: { text: string; label: string }) {
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(text)
    } catch {
      // Ignore clipboard errors in non-secure contexts.
    }
  }

  return (
    <button
      type="button"
      className="artifact-copy-btn"
      title={label}
      aria-label={label}
      onClick={handleCopy}
    >
      ⧉
    </button>
  )
}

function CodeArtifact({ language, children }: { language: string; children: ReactNode }) {
  const rawContent = flattenText(children).replace(/\n$/, '')
  const info = classifyCodeBlock(language, rawContent)
  return (
    <div className={`bubble artifact artifact-${info.variant}`}>
      <div className="artifact-head">
        <span className="artifact-label">{info.label}</span>
        <span className="artifact-actions">
          <CopyAction text={info.content} label={`复制${info.label}`} />
        </span>
      </div>
      <pre>{info.content}</pre>
    </div>
  )
}

const markdownComponents: Components = {
  a({ node: _node, href, children, ...props }) {
    if (!href) return <span className="unsafe-link">{children}</span>
    const external = /^(https?:|mailto:|\/\/)/i.test(href)
    return (
      <a
        {...props}
        href={href}
        target={external ? '_blank' : undefined}
        rel={external ? 'noopener noreferrer' : undefined}
      >
        {children}
      </a>
    )
  },
  table({ node: _node, children, ...props }) {
    return (
      <div className="md-table-wrap">
        <table {...props}>{children}</table>
      </div>
    )
  },
  pre({ children }) {
    const childArray = Children.toArray(children)
    if (childArray.length !== 1 || !isValidElement(childArray[0])) {
      return <pre>{children}</pre>
    }

    const codeNode = childArray[0] as ReactElement<{ className?: string; children?: ReactNode }>
    const languageMatch = /language-([^\s]+)/.exec(codeNode.props.className || '')
    const language = languageMatch?.[1] || ''
    return <CodeArtifact language={language}>{codeNode.props.children}</CodeArtifact>
  },
  code({ node: _node, className, children, ...props }) {
    return (
      <code className={className} {...props}>
        {children}
      </code>
    )
  },
  img({ node: _node, alt, ...props }) {
    return <img alt={alt || ''} loading="lazy" {...props} />
  },
  input({ node: _node, type, checked, ...props }) {
    if (type === 'checkbox') {
      return <input {...props} type="checkbox" checked={Boolean(checked)} disabled readOnly />
    }
    return <input {...props} type={type} />
  },
}

interface Props {
  content: string
  streaming?: boolean
}

export function MarkdownMessage({ content, streaming = false }: Props) {
  const remarkPlugins = streaming ? [remarkGfm, remarkMath, remarkBreaks] : [remarkGfm, remarkMath]
  return (
    <div className={`bubble markdown${streaming ? ' markdown-streaming' : ''}`}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={[[rehypeSanitize, markdownSchema], rehypeKatex]}
        components={markdownComponents}
        urlTransform={safeUrlTransform}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
