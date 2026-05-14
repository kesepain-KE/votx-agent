/** 渲染 StatusBar 组件。 */
import { useAppStore } from '@/store/useAppStore'

/** 渲染 StatusBar 组件。 */
export function StatusBar() {
  const stats = useAppStore((s) => s.stats)
  return (
    <div>
      <div className="section-title">状态</div>
      <div className="stat"><span>历史消息</span><b>{stats.messages}</b></div>
      <div className="stat"><span>工具调用</span><b>{stats.tools}</b></div>
      <div className="stat"><span>会话大小</span><b>{stats.size}</b></div>
    </div>
  )
}
