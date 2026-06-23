'use client'

import { useCallback, useEffect, useRef } from 'react'

interface PaneResizerProps {
  /** Current width of the (right-docked) Copilot pane, in px. */
  width: number
  min: number
  max: number
  onResize: (width: number) => void
  /** Positioning classes from the parent (the divider sits on the pane's left edge). */
  className?: string
}

const KEY_STEP = 24

/**
 * A draggable / keyboard-operable divider between the summary and the Copilot pane (audit 1.1).
 * It's a `role="separator"` window-splitter: pointer-drag resizes, Arrow keys nudge, Home/End jump
 * to the extremes. The Copilot pane is docked on the right, so its width is the distance from the
 * pointer to the viewport's right edge; dragging the divider left widens the pane (ArrowLeft).
 */
export default function PaneResizer({ width, min, max, onResize, className = '' }: PaneResizerProps) {
  const clamp = useCallback((w: number) => Math.min(max, Math.max(min, w)), [min, max])
  const dragging = useRef(false)

  // The drag listeners must stay referentially stable for the whole drag: `onResize` re-renders the
  // parent (it sets width state), so if the handlers depended on it they'd be recreated mid-drag and
  // the `useEffect(() => stop, [stop])` cleanup would tear the drag down after the first move. Read
  // the latest callback/clamp from refs instead so the handlers can have empty deps.
  const onResizeRef = useRef(onResize)
  const clampRef = useRef(clamp)
  useEffect(() => {
    onResizeRef.current = onResize
    clampRef.current = clamp
  }, [onResize, clamp])

  const onPointerMove = useCallback((e: PointerEvent) => {
    if (!dragging.current) return
    // Pane is docked on the right: its width is the distance from the pointer to the right edge.
    onResizeRef.current(clampRef.current(window.innerWidth - e.clientX))
  }, [])

  const stop = useCallback(() => {
    if (!dragging.current) return
    dragging.current = false
    document.body.style.userSelect = ''
    window.removeEventListener('pointermove', onPointerMove)
    window.removeEventListener('pointerup', stop)
  }, [onPointerMove])

  const onPointerDown = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault()
      dragging.current = true
      // Suppress text selection while dragging across the page.
      document.body.style.userSelect = 'none'
      window.addEventListener('pointermove', onPointerMove)
      window.addEventListener('pointerup', stop)
    },
    [onPointerMove, stop],
  )

  // Belt-and-braces: drop any active drag listeners if we unmount mid-drag (e.g. panel closes).
  useEffect(() => stop, [stop])

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      e.preventDefault()
      onResize(clamp(width + KEY_STEP)) // divider left → pane wider
    } else if (e.key === 'ArrowRight') {
      e.preventDefault()
      onResize(clamp(width - KEY_STEP))
    } else if (e.key === 'Home') {
      e.preventDefault()
      onResize(max)
    } else if (e.key === 'End') {
      e.preventDefault()
      onResize(min)
    }
  }

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label="Resize Copilot panel"
      aria-valuemin={min}
      aria-valuemax={max}
      aria-valuenow={Math.round(width)}
      tabIndex={0}
      onPointerDown={onPointerDown}
      onKeyDown={onKeyDown}
      className={`group z-10 cursor-col-resize touch-none ${className}`}
    >
      <div className="mx-auto h-full w-px bg-white/10 transition-colors group-hover:bg-brand-strong/60 dark:group-hover:bg-brand-strong-dark/60 group-focus-visible:bg-brand-strong dark:group-focus-visible:bg-brand-strong-dark" />
    </div>
  )
}
