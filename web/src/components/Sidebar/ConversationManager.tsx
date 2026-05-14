/** 描述 Props 数据结构。 */
import { useAppStore } from '@/store/useAppStore'
import type { Conversation } from '@/types'

/** 描述 Props 数据结构。 */
interface Props {
  loadFromManager: (c: Conversation) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  renameConv: (c: Conversation) => Promise<void>
}

/** 渲染 ConversationManager 组件。 */
export function ConversationManager({ loadFromManager, deleteConversation, renameConv }: Props) {
  const conversations = useAppStore((s) => s.conversations)
  const activeConv = useAppStore((s) => s.activeConv)
  const set = useAppStore.setState

  return (
    <div className="conv-mgr">
      <div className="conv-mgr-header">
        <button className="icon-btn" onClick={() => set({ showConvManager: false })} title="返回">←</button>
        <h3>对话管理</h3>
      </div>
      <div className="conv-mgr-list">
        {!conversations.length && <div style={{ color: 'var(--text-secondary)', fontSize: 12, textAlign: 'center', padding: 20 }}>暂无对话</div>}
        {conversations.map((c) => (
          <div key={c.id} className={`conv-mgr-item ${activeConv === c.id ? 'active' : ''}`} onClick={() => loadFromManager(c)}>
            <div className="conv-mgr-item-info">
              <b>{c.id === '__current__' ? `● ${c.summary || '新对话'}` : c.label}</b>
              <p>{c.meta}</p>
            </div>
            <div className="conv-mgr-item-actions">
              <button className="icon-btn" onClick={(e) => (e.stopPropagation(), renameConv(c))} title="重命名">✎</button>
              <button className="icon-btn danger" onClick={(e) => (e.stopPropagation(), deleteConversation(c.id))} title="删除">×</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
