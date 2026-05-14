import { useAppStore } from '@/store/useAppStore'

export function Toast() {
  const toastText = useAppStore((s) => s.toastText)
  const toastVisible = useAppStore((s) => s.toastVisible)
  return <div className={`toast ${toastVisible ? 'show' : ''}`}>{toastText}</div>
}
