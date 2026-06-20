import ReactMarkdown, { type Components, type UrlTransform } from 'react-markdown'
import rehypeKatex from 'rehype-katex'
import rehypeSanitize, { defaultSchema, type Options as SanitizeOptions } from 'rehype-sanitize'
import remarkGfm from 'remark-gfm'
import remarkMath from 'remark-math'
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
}

export function MarkdownMessage({ content }: Props) {
  return (
    <div className="bubble markdown">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[[rehypeSanitize, markdownSchema], rehypeKatex]}
        components={markdownComponents}
        urlTransform={safeUrlTransform}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}
