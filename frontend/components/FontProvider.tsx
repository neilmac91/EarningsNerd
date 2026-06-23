'use client'

/* =============================================================================
   EarningsNerd — Font switcher (Client Component)
   -----------------------------------------------------------------------------
   - Lightweight React Context, no extra deps.
   - Persists the choice in localStorage ('en-font').
   - Writes the selection to <html data-font="…">, which globals.css maps to
     --font-active. NOTHING re-renders for the font swap — it's one attribute,
     so it's cheap and works for Server Components further down the tree too.
   - Pair with the inline pre-hydration script (see app/layout.tsx) so the right
     font is set BEFORE React hydrates → no flash-of-wrong-font, no hydration
     mismatch (the server renders the default; the script + provider agree on it).
============================================================================= */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'

export const FONT_OPTIONS = [
  { id: 'figtree',   label: 'Figtree',   hint: 'Body · default',   stack: 'var(--font-body)' },
  { id: 'grotesque', label: 'Helvetica', hint: 'Headings · Arial', stack: 'var(--font-grotesque)' },
  { id: 'data',      label: 'Mono',      hint: 'Technical',        stack: 'var(--font-data)' },
] as const

export type FontId = (typeof FONT_OPTIONS)[number]['id']
export const DEFAULT_FONT: FontId = 'figtree'
const STORAGE_KEY = 'en-font'

function isFontId(v: string | null): v is FontId {
  return !!v && FONT_OPTIONS.some((f) => f.id === v)
}

type FontContextValue = { font: FontId; setFont: (id: FontId) => void }
const FontContext = createContext<FontContextValue | null>(null)

export function FontProvider({ children }: { children: ReactNode }) {
  // SSR + first client render both use DEFAULT_FONT → markup matches → no hydration error.
  // The pre-hydration script has already set <html data-font>, so the pixels are correct;
  // here we only sync React state to whatever the script picked.
  const [font, setFontState] = useState<FontId>(DEFAULT_FONT)

  useEffect(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY)
      if (isFontId(stored)) setFontState(stored)
    } catch {
      /* private mode / storage disabled — keep the default font for this session */
    }
  }, [])

  const setFont = useCallback((id: FontId) => {
    setFontState(id)
    document.documentElement.setAttribute('data-font', id)
    try {
      localStorage.setItem(STORAGE_KEY, id)
    } catch {
      /* private mode / storage disabled — the attribute still applies for this session */
    }
  }, [])

  const value = useMemo(() => ({ font, setFont }), [font, setFont])
  return <FontContext.Provider value={value}>{children}</FontContext.Provider>
}

export function useFont(): FontContextValue {
  const ctx = useContext(FontContext)
  if (!ctx) throw new Error('useFont must be used within <FontProvider>')
  return ctx
}

/* -----------------------------------------------------------------------------
   FontSwitcher — drop into Settings, the footer, or a header menu.
   Styled with the design-system tokens (subdued brand accent, semantic borders).
----------------------------------------------------------------------------- */
export function FontSwitcher({ className = '' }: { className?: string }) {
  const { font, setFont } = useFont()

  return (
    <div
      role="radiogroup"
      aria-label="Interface font"
      className={`inline-flex items-center gap-1 rounded-lg border border-border-light dark:border-border-dark bg-panel-light dark:bg-panel-dark p-1 ${className}`}
    >
      {FONT_OPTIONS.map((opt) => {
        const active = font === opt.id
        return (
          <button
            key={opt.id}
            type="button"
            role="radio"
            aria-checked={active}
            title={opt.hint}
            onClick={() => setFont(opt.id)}
            style={{ fontFamily: opt.stack }}
            className={[
              'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
              'focus-visible:outline-none focus-visible:shadow-ring-brand',
              active
                ? 'bg-brand-strong text-white dark:bg-brand-dark dark:text-background-dark'
                : 'text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/5',
            ].join(' ')}
          >
            {opt.label}
          </button>
        )
      })}
    </div>
  )
}
