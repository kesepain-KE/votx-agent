/** 描述 Props 数据结构。 */
import { useAppStore } from '@/store/useAppStore'
import type { Conversation } from '@/types'
import type { MouseEvent } from 'react'

/** 描述 Props 数据结构。 */
interface Props {
  loadConversation: (c: Conversation | { id: '__current__' }) => Promise<void>
  renameConv: (c: Conversation) => Promise<void>
  deleteConversation: (id: string) => Promise<void>
  openConvMenu: (e: MouseEvent, c: Conversation) => void
}

/** 渲染 ConvItem 组件。 */
export function ConvItem({ c, active, loadConversation, openConvMenu, renameConv, deleteConversation }: Props & { c: Conversation; active: boolean }) {
  return (
    <div
      className={`conv ${active ? 'active' : ''}`}
      onClick={() => loadConversation(c)}
      onContextMenu={(e) => openConvMenu(e, c)}
    >
      <div>
        <b>{c.id === '__current__' ? `● ${c.summary || '新对话'}` : c.label}</b>
        <p>{c.meta}</p>
        {c.raw_label && <p className="ci-summary">{c.raw_label}</p>}
      </div>
      <div className="conv-actions">
        <button className="icon-btn" onClick={(e) => (e.stopPropagation(), renameConv(c))} title="重命名">✎</button>
        <button className="icon-btn danger" onClick={(e) => (e.stopPropagation(), deleteConversation(c.id))} title="删除">×</button>
      </div>
    </div>
  )
}
