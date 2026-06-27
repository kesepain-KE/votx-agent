import { Children, isValidElement, type ReactElement, type ReactNode } from 'react'
import ReactMarkdown, { type Components, type UrlTransform } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema, type Options as SanitizeOptions } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
import remarkBreaks from 'remark-breaks'
import { ArtifactBlock } from './artifacts/ArtifactBlock'
import { classifyFencedArtifact } from './artifacts/artifactDetect'
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

const safeUrlTransform: UrlTransform = (url) => {
  const value = url.trim()
  if (!value) return ''
  const hasScheme = /^[a-z][a-z0-9+.-]*:/i.test(value)
  if (!hasScheme) return value
  if (/^(https?:|mailto:)/i.test(value)) return value
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
  bubble?: boolean
  className?: string
  copyable?: boolean
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

export function MarkdownMessage({ content, streaming = false, bubble = true, className = '', copyable = true }: Props) {
  const remarkPlugins = streaming ? [remarkGfm, remarkMath, remarkBreaks] : [remarkGfm, remarkMath]
  const markdownRenderComponents: Components = {
    ...markdownComponents,
    pre({ children }) {
      const childArray = Children.toArray(children)
      if (childArray.length !== 1 || !isValidElement(childArray[0])) {
        return <pre>{children}</pre>
      }

      const codeNode = childArray[0] as ReactElement<{ className?: string; children?: ReactNode }>
      const languageMatch = /language-([^\s]+)/.exec(codeNode.props.className || '')
      const language = languageMatch?.[1] || ''
      const rawContent = flattenText(codeNode.props.children).replace(/\n$/, '')
      const info = classifyFencedArtifact(language, rawContent)
      return <ArtifactBlock variant={info.variant} label={info.label} content={info.content} copyable={copyable} />
    },
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
