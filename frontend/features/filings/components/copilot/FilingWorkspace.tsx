'use client'

import { useCallback, useEffect, useState, type CSSProperties, type ReactNode } from 'react'
import PaneResizer from './PaneResizer'

const DEFAULT_WIDTH = 420
const MIN_WIDTH = 360
const MAX_WIDTH = 640
const STORAGE_KEY = 'copilot:paneWidth'

function clampWidth(w: number): number {
  return Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, w))
}

function readStoredWidth(): number {
  if (typeof window === 'undefined') return DEFAULT_WIDTH
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const n = raw ? Number(raw) : NaN
    return Number.isFinite(n) ? clampWidth(n) : DEFAULT_WIDTH
  } catch {
    // localStorage can throw (private mode, blocked third-party storage, SecurityError in an iframe).
    return DEFAULT_WIDTH
  }
}

interface FilingWorkspaceProps {
  /** Whether the Copilot pane is open (drives the two-column desktop layout). */
  open: boolean
  /** The Copilot rail element — renders its own launcher when closed, panel when open. */
  rail: ReactNode
  /** The filing summary content (the left pane). */
  children: ReactNode
}

/**
 * Desktop "research desk" layout for the filing page (audit 1.1): the summary and the Copilot sit
 * side by side as reflowing CSS-grid panes that a draggable divider resizes — instead of the Copilot
 * floating over right-padded content. Below `lg` the grid collapses to a single column and the rail
 * falls back to its bottom-sheet / launcher overlay (its own classes handle that).
 *
 * The rail keeps a stable position in the tree across open/close (the right cell is always rendered),
 * so toggling the layout never remounts it — a live SSE stream is never aborted by a resize/toggle.
 */
export default function FilingWorkspace({ open, rail, children }: FilingWorkspaceProps) {
  const [width, setWidth] = useState<number>(DEFAULT_WIDTH)

  // Hydrate the persisted width after mount (keeps SSR markup deterministic, avoids hydration drift).
  useEffect(() => {
    setWidth(readStoredWidth())
  }, [])

  const handleResize = useCallback((next: number) => {
    const w = clampWidth(next)
    setWidth(w)
    if (typeof window === 'undefined') return
    try {
      window.localStorage.setItem(STORAGE_KEY, String(w))
    } catch {
      // Ignore storage write failures (quota/SecurityError) — the width still applies for the session.
    }
  }, [])

  // When closed, collapse the second track to 0 so the summary spans the full width.
  const style = { '--copilot-w': open ? `${width}px` : '0px' } as CSSProperties

  return (
    <div className="lg:grid lg:grid-cols-[minmax(0,1fr)_var(--copilot-w)]" style={style}>
      <div className="min-w-0">{children}</div>
      <div className="relative min-w-0 lg:sticky lg:top-16 lg:h-[calc(100vh-4rem)]">
        {open && (
          <PaneResizer
            width={width}
            min={MIN_WIDTH}
            max={MAX_WIDTH}
            onResize={handleResize}
            className="absolute -left-1 top-0 hidden h-full w-2 lg:block"
          />
        )}
        {rail}
      </div>
    </div>
  )
}
