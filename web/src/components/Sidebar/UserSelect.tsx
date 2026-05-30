/** web/src/components/Sidebar/UserSelect.tsx 模块。 */
import { useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { useAppStore } from '@/store/useAppStore'

interface Props {
  selectUser: () => Promise<void>
}

const FRIENDLY_PROVIDER: Record<string, string> = {
  openai: 'OpenAI', anthropic: 'Anthropic', deepseek: 'DeepSeek',
  azure_openai: 'Azure', google_gemini: 'Gemini',
}

export function UserSelect({ selectUser }: Props) {
  const users = useAppStore((s) => s.users)
  const selectedUser = useAppStore((s) => s.selectedUser)
  const selectErr = useAppStore((s) => s.selectErr)
  const set = useAppStore.setState

  const [expanded, setExpanded] = useState(false)
  const [failedAvatars, setFailedAvatars] = useState<Record<string, boolean>>({})
  const wrapRef = useRef<HTMLDivElement>(null)
  const [popoverStyle, setPopoverStyle] = useState<React.CSSProperties>({})

  useEffect(() => {
    if (expanded && wrapRef.current) {
      const rect = wrapRef.current.getBoundingClientRect()
      setPopoverStyle({
        position: 'fixed',
        top: rect.bottom + 8,
        left: rect.left,
        width: rect.width,
        zIndex: 9999,
      })
    }
  }, [expanded])

  const close = () => setExpanded(false)

  return (
    <div className="user-select-card">
      <div className="user-select-eyebrow">● 用户选择</div>

      <div className="user-select-wrap" ref={wrapRef}>
        <button
          className="user-select-btn"
          onClick={() => setExpanded(!expanded)}
          type="button"
        >
          <span>{selectedUser || '选择用户'}</span>
          <span className={`expand-arrow${expanded ? ' open' : ''}`}>▼</span>
        </button>

        {expanded && createPortal(
          <>
            <div className="user-select-backdrop" onClick={close} />
            <div className="user-select-popover" style={popoverStyle}>
              <div className="user-select-arcs" aria-hidden="true" />
              <div className="user-cards" role="list">
                {users.map((u) => {
                  const isSelected = selectedUser === u.name
                  const providerLabel = FRIENDLY_PROVIDER[u.provider_type] || u.provider_type
                  return (
                    <button
                      key={u.name}
                      className={`user-card${isSelected ? ' pressed' : ''}`}
                      onClick={() => { set({ selectedUser: u.name }); close() }}
                      type="button"
                    >
                      <span className="avatar">
                        {!failedAvatars[u.name] ? (
                          <img
                            src={`/api/avatar/${encodeURIComponent(u.name)}?t=${Date.now()}`}
                            alt=""
                            onError={() => setFailedAvatars((f) => ({ ...f, [u.name]: true }))}
                          />
                        ) : (
                          u.name.slice(0, 1).toUpperCase()
                        )}
                      </span>
                      <span className="user-card-info">
                        <b>{u.name}</b>
                        <span className="meta">
                          {providerLabel && <span className="pill">{providerLabel}</span>}
                          {u.model && <span className="pill">{u.model}</span>}
                        </span>
                      </span>
                      <span className="check">✓</span>
                    </button>
                  )
                })}
              </div>
            </div>
          </>,
          document.body
        )}
      </div>

      <button className="user-select-enter" onClick={selectUser} type="button">进入</button>
      {selectErr && <div className="select-err" style={{ marginTop: 8 }}>{selectErr}</div>}
    </div>
  )
}
