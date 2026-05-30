/** 渲染 Brand 组件。 */
import { useAppStore } from '@/store/useAppStore'

export function Brand() {
  const version = useAppStore((s) => s.frameworkVersion)
  return (
    <div className="brand">
      <img className="logo" src="/votx-agent.png" alt="votx-agent" />
      <div>
        <h1>votx-agent</h1>
        <p>Agent 控制台{version !== '-' ? ` · ${version}` : ''}</p>
      </div>
    </div>
  )
}
