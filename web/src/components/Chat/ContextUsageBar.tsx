import { useAppStore } from '@/store/useAppStore'

function formatTokens(v: number) {
  if (v >= 1000) return `${(v / 1000).toFixed(1)}K`
  return String(v)
}

export function ContextUsageBar() {
  const cw = useAppStore((s) => s.contextWindow)

  if (!cw || !cw.max) return null

  const raw = cw.max > 0 ? (cw.used / cw.max) * 100 : 0
  const pct = Math.min(100, Math.max(0, raw))
  const warn = cw.used > cw.max

  return (
    <div
      className="context-usage-bar"
      title={`上下文使用量：${cw.used} / ${cw.max}`}
    >
      <span className="context-usage-text">
        <span>{formatTokens(cw.used)}</span>
        <span className="context-usage-separator"> / </span>
        <span>{formatTokens(cw.max)}</span>
      </span>
      <div className="context-usage-track">
        <div
          className="context-usage-fill"
          style={{
            width: pct > 0 ? `max(${pct}%, 6px)` : '0%',
            opacity: warn ? 1 : undefined,
            background: warn ? 'linear-gradient(180deg, var(--danger) 0%, #e04040 100%)' : undefined,
          }}
        />
      </div>
      <span className="context-usage-percent">{Math.round(pct)}%</span>
    </div>
  )
}
