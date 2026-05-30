/** web/src/components/Sidebar/Sidebar.tsx 模块。 */
import { useState } from 'react'
import { useAppStore } from '@/store/useAppStore'
import type { Conversation, ThemeId } from '@/types'
import type { MouseEvent as ReactMouseEvent } from 'react'
import { Brand } from './Brand'
import { UserSelect } from './UserSelect'
import { StatusBar } from './StatusBar'
import { ConvItem } from './ConvItem'
import { ConversationManager } from './ConversationManager'
import { ThemePicker } from './ThemePicker'

/** 描述 Props 数据结构。 */
interface Props {
  profileInitial: string
  selectUser: () => Promise<void>
  loadConversation: (c: Conversation | { id: '__current__' }) => Promise<void>
  renameConv: (c: Conversation) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  openConvMenu: (e: ReactMouseEvent, c: Conversation) => void
  loadFromManager: (c: Conversation) => Promise<void>
  refreshConversations: () => Promise<void>
  deleteAllConvs: () => Promise<void>
  refreshOverview: () => Promise<void>
  toggleThemeMenu: (e: ReactMouseEvent<HTMLButtonElement>) => void
  chooseTheme: (id: ThemeId) => void
}

/** 渲染 Sidebar 组件。 */
export function Sidebar(props: Props) {
  const showConvManager = useAppStore((s) => s.showConvManager)
  const conversations = useAppStore((s) => s.conversations)
  const activeConv = useAppStore((s) => s.activeConv)
  const profileName = useAppStore((s) => s.profileName)
  const profileInfo = useAppStore((s) => s.profileInfo)
  const avatarUrl = useAppStore((s) => s.avatarUrl)
  const refreshing = useAppStore((s) => s.refreshing)
  const set = useAppStore.setState
  const [avatarFailed, setAvatarFailed] = useState(false)

  return (
    <aside className="sidebar glass" style={{ position: 'relative', overflow: 'hidden' }}>
      {!showConvManager && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 14, height: '100%' }}>
          <Brand />
          <UserSelect selectUser={props.selectUser} />
          <StatusBar />

          <div className="section-row">
            <div className="section-title">对话历史</div>
            <div className="mini-actions">
              <button className="tiny-btn" onClick={props.refreshConversations}>刷新</button>
              <button className="tiny-btn danger" onClick={props.deleteAllConvs}>全部删除</button>
            </div>
          </div>
          <div className="conv-list">
            {!conversations.length && <div style={{ color: 'var(--text-secondary)', fontSize: 11, padding: 4 }}>选择用户后加载...</div>}
            {conversations.slice(0, 3).map((c) => (
              <ConvItem key={c.id} c={c} active={activeConv === c.id} loadConversation={props.loadConversation} renameConv={props.renameConv} deleteConversation={props.deleteConversation} openConvMenu={props.openConvMenu} />
            ))}
          </div>
          {conversations.length > 3 && (
            <button className="more-btn" onClick={() => set({ showConvManager: true })}>
              更多 ({conversations.length - 3})...
            </button>
          )}

          <div className="section-row" style={{ marginBottom: 8 }}>
            <div className="section-title">状态刷新</div>
            <button className={`refresh-btn ${refreshing ? 'spinning' : ''}`} title="刷新右侧栏所有数据" onClick={props.refreshOverview}>↻</button>
          </div>

          <div className="profile card profile-with-theme">
            <div className="avatar">
              {avatarUrl && !avatarFailed ? (
                <img src={avatarUrl} alt="" onError={() => setAvatarFailed(true)}
                  style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }} />
              ) : (
                props.profileInitial
              )}
            </div>
            <div>
              <b>{profileName}</b>
              <br />
              <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{profileInfo}</span>
            </div>
            <ThemePicker toggleThemeMenu={props.toggleThemeMenu} chooseTheme={props.chooseTheme} />
          </div>
        </div>
      )}

      {showConvManager && (
        <ConversationManager loadFromManager={props.loadFromManager} deleteConversation={props.deleteConversation} renameConv={props.renameConv} />
      )}
    </aside>
  )
}
