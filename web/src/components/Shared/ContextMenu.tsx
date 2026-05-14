/** 描述 Props 数据结构。 */
import { useAppStore } from '@/store/useAppStore'

/** 描述 Props 数据结构。 */
interface Props {
  renameConvFromMenu: () => void
  deleteConvFromMenu: () => void
}

/** 渲染 ContextMenu 组件。 */
export function ContextMenu({ renameConvFromMenu, deleteConvFromMenu }: Props) {
  const menu = useAppStore((s) => s.menu)
  return (
    <div className="ctx-menu" style={{ display: menu.show ? 'block' : 'none', left: menu.x, top: menu.y }}>
      <button onClick={renameConvFromMenu}>重命名对话</button>
      <button className="danger" onClick={deleteConvFromMenu}>删除对话</button>
    </div>
  )
}
