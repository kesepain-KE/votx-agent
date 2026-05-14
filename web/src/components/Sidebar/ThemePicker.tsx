/** 描述 Props 数据结构。 */
import { THEMES, useAppStore } from '@/store/useAppStore'
import type { ThemeId } from '@/types'
import { createPortal } from 'react-dom'
import type { MouseEvent as ReactMouseEvent } from 'react'

/** 描述 Props 数据结构。 */
interface Props {
  toggleThemeMenu: (e: ReactMouseEvent<HTMLButtonElement>) => void
  chooseTheme: (id: ThemeId) => void
}

/** 渲染 ThemePicker 组件。 */
export function ThemePicker({ toggleThemeMenu, chooseTheme }: Props) {
  const theme = useAppStore((s) => s.theme)
  const themeMenu = useAppStore((s) => s.themeMenu)
  const themeMenuPos = useAppStore((s) => s.themeMenuPos)
  const label = THEMES.find((x) => x.id === theme)?.label || '高级黑'

  return (
    <div className="theme-picker" title="选择主题" onClick={(e) => e.stopPropagation()}>
      <button className={`theme-trigger ${themeMenu ? 'active' : ''}`} onClick={toggleThemeMenu} type="button" aria-label="选择主题">
        {label}
      </button>
      {themeMenu &&
        createPortal(
          <div className="theme-menu" style={{ left: themeMenuPos.x, top: themeMenuPos.y }} onClick={(e) => e.stopPropagation()}>
            {THEMES.map((t) => (
              <button key={t.id} className={`theme-choice ${theme === t.id ? 'active' : ''}`} onClick={() => chooseTheme(t.id)} type="button">
                <span className="theme-dot" style={{ background: `linear-gradient(135deg, ${t.c1}, ${t.c2})` }} />
                <span>{t.label}</span>
                {theme === t.id && <span className="theme-choice-mark">✓</span>}
              </button>
            ))}
          </div>,
          document.body,
        )}
    </div>
  )
}
