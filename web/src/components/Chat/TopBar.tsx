/** 描述 Props 数据结构。 */
import { useAppStore } from '@/store/useAppStore'

/** 描述 Props 数据结构。 */
interface Props {
  saveChat: () => Promise<void>
  newChat: () => Promise<void>
}

/** 渲染 TopBar 组件。 */
export function TopBar({ saveChat, newChat }: Props) {
  const chatTitle = useAppStore((s) => s.chatTitle)
  const mainSub = useAppStore((s) => s.mainSub)
  const userActive = useAppStore((s) => s.userActive)
  const running = useAppStore((s) => s.running)
  const modelName = useAppStore((s) => s.modelName)

  return (
    <header className="top">
      <div>
        <h2>{chatTitle}</h2>
        <p>{mainSub}</p>
      </div>
      <div className="top-actions">
        <div className="model-badge">
          {userActive && <span className={`pulse ${running ? 'active' : ''}`} />}
          <span>{modelName}</span>
          {running && <span className="running-tag">运行中...</span>}
        </div>
        <button className="btn btn-ghost mini" onClick={saveChat}>保存</button>
        <button className="btn btn-ghost mini" onClick={newChat}>新对话</button>
      </div>
    </header>
  )
}
