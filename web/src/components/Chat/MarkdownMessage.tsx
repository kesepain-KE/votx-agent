import ReactMarkdown, { type Components, type UrlTransform } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema, type Options as SanitizeOptions } from 'rehype-sanitize'
import remarkBreaks from 'remark-breaks'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import { safeMarkdownUrlTransform } from './markdownImage'
import { ArtifactBlock } from './artifacts/ArtifactBlock'
import { classifyCodeLabel, classifyFencedArtifact } from './artifacts/artifactDetect'
import { CodePanel } from './CodePanel'
import 'katex/dist/katex.min.css'

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

const safeUrlTransform: UrlTransform = (url) => safeMarkdownUrlTransform(url)

function extractText(node: unknown): string {
  if (typeof node === 'string') return node
  if (!node || typeof node !== 'object') return ''
  if (Array.isArray(node)) return node.map(extractText).join('')
  const value = (node as { value?: unknown }).value
  if (typeof value === 'string') return value
  const children = (node as { children?: unknown }).children
  if (children) return extractText(children)
  return ''
}

function extractCodeLanguage(node: unknown): string {
  if (!node || typeof node !== 'object') return ''
  const children = (node as { children?: unknown }).children
  if (!Array.isArray(children)) return ''

  for (const child of children) {
    if (!child || typeof child !== 'object') continue
    if ((child as { tagName?: unknown }).tagName !== 'code') continue

    const properties = (child as { properties?: { className?: unknown } }).properties
    const className = properties?.className
    const classes = Array.isArray(className)
      ? className
      : typeof className === 'string'
        ? className.split(/\s+/)
        : []

    const languageClass = classes.find((item): item is string => item.startsWith('language-'))
    if (languageClass) return languageClass.slice('language-'.length)
  }

  return ''
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
  pre({ node }) {
    const content = extractText(node)
    const language = extractCodeLanguage(node)
    const info = classifyFencedArtifact(language, content)

    if (info.variant === 'code') {
      return (
        <CodePanel
          label={language ? classifyCodeLabel(language) : '\u4ee3\u7801'}
          content={info.content}
          className="markdown-code-panel"
          copyable
        />
      )
    }

    return (
      <ArtifactBlock
        variant={info.variant}
        label={info.label}
        content={info.content}
        className="markdown-code-panel"
        copyable
      />
    )
  },
  code({ children }) {
    return <code>{children}</code>
  },
  img() {
    return null
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
  bubble?: boolean
  className?: string
}

export function MarkdownMessage({ content, streaming = false, bubble = true, className = '' }: Props) {
  const remarkPlugins = streaming ? [remarkGfm, remarkMath, remarkBreaks] : [remarkGfm, remarkMath]
  const markdownRenderComponents: Components = {
    ...markdownComponents,
  }

  return (
    <div className={`${bubble ? 'bubble ' : ''}markdown-body${streaming ? ' markdown-streaming' : ''}${bubble ? '' : ' markdown-embedded'}${className ? ` ${className}` : ''}`}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={[[rehypeSanitize, markdownSchema], rehypeKatex]}
        components={markdownRenderComponents}
        urlTransform={safeUrlTransform}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
