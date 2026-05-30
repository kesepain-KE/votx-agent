/** 渲染 Brand 组件。 */
import { useAppStore } from '@/store/useAppStore'

export function Brand() {
  const version = useAppStore((s) => s.frameworkVersion)
  return (
    <div className="brand">
      <div className="logo">V</div>
      <div>
        <h1>votx-agent</h1>
        <p>本地多用户 Agent 控制台{version !== '-' ? ` · ${version}` : ''}</p>
      </div>
    </div>
  )
}
