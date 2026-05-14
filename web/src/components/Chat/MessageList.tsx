/** 描述 Props 数据结构。 */
import type { Message, ToolCard } from '@/types'
import { formatContent } from '@/utils/format'
import { useAppStore } from '@/store/useAppStore'

/** 描述 Props 数据结构。 */
interface Props {
  message: Message
  patchMessage: (id: number, patch: Partial<Message> | ((m: Message) => Message)) => void
  copyMsg: (m: Message) => void
}

/** 渲染 ThinkBlock 组件。 */
function ThinkBlock({ message, patchMessage }: { message: Message; patchMessage: Props['patchMessage'] }) {
  const showThinking = useAppStore((s) => s.showThinking)
  if (!message.think || !showThinking) return null
  return (
    <div className={`think-block ${message.thinkOpen ? 'open' : ''}`}>
      <div className="think-header" onClick={() => patchMessage(message.id, { thinkOpen: !message.thinkOpen })}>
        💭 思考过程
      </div>
      <div className="think-body">{message.think}</div>
    </div>
  )
}

/** 渲染 ToolCallCard 组件。 */
function ToolCallCard({ tc, message, patchMessage }: { tc: ToolCard; message: Message; patchMessage: Props['patchMessage'] }) {
  const showToolCalls = useAppStore((s) => s.showToolCalls)
  return (
    <div key={tc._key} className={`tool-call ${tc.open ? 'open' : ''}`} style={{ display: showToolCalls ? undefined : 'none' }}>
      <div
        className="tc-header"
        onClick={() => patchMessage(message.id, (msg) => { msg.tools = (msg.tools || []).map((t) => (t._key === tc._key ? { ...t, open: !t.open } : t)); return msg })}
      >
        <span>{tc.icon}</span>
        <span className="tc-name">{tc.name}</span>
        <span className="tc-param">{tc.param}</span>
        <span className="tc-time">{tc.time}</span>
        <span className={`tc-status ${tc.success ? 'ok' : 'fail'}`}>{tc.success ? 'OK' : 'FAIL'}</span>
      </div>
      <div className="tc-detail"><pre>{tc.detail}</pre></div>
    </div>
  )
}

/** 渲染 UserMessage 组件。 */
function UserMessage({ message, copyMsg }: { message: Message; copyMsg: Props['copyMsg'] }) {
  return (
    <div className="bubble-wrap">
      {(message.images || []).map((img) => (
        <img key={img.name} src={`/api/files/view/${encodeURIComponent(img.name)}${img.dir && img.dir !== 'file' ? `?dir=${img.dir}` : ''}`} alt={img.name} style={{ maxWidth: '100%', maxHeight: 260, borderRadius: 12, marginBottom: 6, display: 'block' }} loading="lazy" />
      ))}
      <div className="bubble">{message.content}</div>
      {message.content && (
        <button className={`copy-msg ${message.copied ? 'copied' : ''}`} onClick={() => copyMsg(message)}>
          {message.copied ? '✓ 已复制' : '复制'}
        </button>
      )}
    </div>
  )
}

/** 渲染 AssistantMessage 组件。 */
function AssistantMessage({ message, patchMessage, copyMsg }: Props) {
  return (
    <div className="bubble-wrap">
      <ThinkBlock message={message} patchMessage={patchMessage} />
      {(message.tools || []).map((tc) => (
        <ToolCallCard key={tc._key} tc={tc} message={message} patchMessage={patchMessage} />
      ))}
      {message.streaming
        ? <div className="bubble">{message._raw}</div>
        : <div className="bubble" dangerouslySetInnerHTML={{ __html: formatContent(message.content) }} />
      }
      {message.usage ? (
        <div className="msg-footer">
          <div className="live-stats">
            <span className="ls-item"><span className="ls-label">输入</span><span className="ls-val">{message.usage.input}</span></span>
            <span className="ls-item"><span className="ls-label">输出</span><span className="ls-val">{message.usage.output}</span></span>
            <span className="ls-item"><span className="ls-label">缓存命中</span><span className="ls-val">{message.usage.hit}</span></span>
            <span className="ls-item"><span className="ls-label">命中率</span><span className="ls-val">{message.usage.hit_rate}</span></span>
            <span className="ls-item"><span className="ls-label">耗时</span><span className="ls-val">{message.usage.time}</span></span>
          </div>
          <button className={`copy-msg ${message.copied ? 'copied' : ''}`} onClick={() => copyMsg(message)}>
            {message.copied ? '✓ 已复制' : '复制'}
          </button>
        </div>
      ) : (
        message.content && (
          <button className={`copy-msg ${message.copied ? 'copied' : ''}`} onClick={() => copyMsg(message)}>
            {message.copied ? '✓ 已复制' : '复制'}
          </button>
        )
      )}
    </div>
  )
}

/** 描述 MessageListProps 数据结构。 */
interface MessageListProps {
  patchMessage: (id: number, patch: Partial<Message> | ((m: Message) => Message)) => void
  copyMsg: (m: Message) => void
  continueAfterMaxRounds: () => void
  chatRef: React.RefObject<HTMLDivElement>
  onChatScroll: () => void
}

/** 渲染 MessageList 组件。 */
export function MessageList({ patchMessage, copyMsg, continueAfterMaxRounds, chatRef, onChatScroll }: MessageListProps) {
  const messages = useAppStore((s) => s.messages)

  return (
    <div className="chat" ref={chatRef} onScroll={onChatScroll}>
      {messages.map((m) => {
        if (m.type === 'sys') return <div key={m.id} className="sys-msg">{m.content}</div>
        if (m.type === 'error') return <div key={m.id} className="sys-error">⚠ {m.content}</div>
        if (m.type === 'warn') {
          return (
            <div key={m.id} className="sys-warn">
              {m.maxRounds ? (
                <span>⚠ {m.content} <button className="btn btn-ghost small" onClick={continueAfterMaxRounds}>继续</button></span>
              ) : (
                <span>⚠ {m.content}</span>
              )}
            </div>
          )
        }
        return (
          <div key={m.id} className={`msg ${m.role === 'user' ? 'me' : ''}`}>
            <div className="msg-avatar">{m.role === 'user' ? '你' : '🤖'}</div>
            {m.role === 'user'
              ? <UserMessage message={m} copyMsg={copyMsg} />
              : <AssistantMessage message={m} patchMessage={patchMessage} copyMsg={copyMsg} />
            }
          </div>
        )
      })}
    </div>
  )
}
