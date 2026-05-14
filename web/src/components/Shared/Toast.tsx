/** 渲染 Toast 组件。 */
import { useAppStore } from '@/store/useAppStore'

/** 渲染 Toast 组件。 */
export function Toast() {
  const toastText = useAppStore((s) => s.toastText)
  const toastVisible = useAppStore((s) => s.toastVisible)
  return <div className={`toast ${toastVisible ? 'show' : ''}`}>{toastText}</div>
}
