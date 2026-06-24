'use client'

import { useCallback, useEffect, useState } from 'react'
import { createPortal } from 'react-dom'
import { SparkleIcon } from '@/lib/icons'

const MIN_SELECTION_LEN = 8
const MAX_SELECTION_LEN = 4000

/** A selection worth offering "Ask about this" on — long enough to be meaningful, not a whole page. */
export function shouldOfferAsk(text: string): boolean {
  const t = text.trim()
  return t.length >= MIN_SELECTION_LEN && t.length <= MAX_SELECTION_LEN
}

interface AskAboutSelectionProps {
  /** The region whose text selections should offer the action (e.g. the summary container). */
  containerRef: React.RefObject<HTMLElement | null>
  /** Only active for entitled users (the Copilot is Pro-only). */
  enabled: boolean
  /** Called with the selected text when the user taps the action. */
  onAsk: (text: string) => void
}

interface Floating {
  text: string
  top: number
  left: number
}

/**
 * Renders a floating "Ask about this" action when the user selects text inside `containerRef`
 * (P8e). Tapping it hands the selection to `onAsk` (which opens the Copilot rail + pre-fills the
 * composer). Dismisses on scroll/resize/Escape or when the selection collapses.
 */
export default function AskAboutSelection({ containerRef, enabled, onAsk }: AskAboutSelectionProps) {
  const [floating, setFloating] = useState<Floating | null>(null)

  const evaluateSelection = useCallback(() => {
    const sel = typeof window !== 'undefined' ? window.getSelection() : null
    if (!sel || sel.isCollapsed || sel.rangeCount === 0) {
      setFloating(null)
      return
    }
    const text = sel.toString()
    if (!shouldOfferAsk(text)) {
      setFloating(null)
      return
    }
    const range = sel.getRangeAt(0)
    const container = containerRef.current
    if (!container || !container.contains(range.commonAncestorContainer)) {
      setFloating(null)
      return
    }
    const rect = range.getBoundingClientRect()
    setFloating({
      text: text.trim(),
      top: Math.max(rect.top - 8, 8),
      left: Math.min(Math.max(rect.left + rect.width / 2, 80), window.innerWidth - 80),
    })
  }, [containerRef])

  // Offer the action after a selection gesture settles.
  useEffect(() => {
    if (!enabled) {
      setFloating(null)
      return
    }
    let timer: ReturnType<typeof setTimeout> | null = null
    const onMouseUp = () => {
      if (timer) clearTimeout(timer)
      timer = setTimeout(evaluateSelection, 0)
    }
    document.addEventListener('mouseup', onMouseUp)
    return () => {
      if (timer) clearTimeout(timer)
      document.removeEventListener('mouseup', onMouseUp)
    }
  }, [enabled, evaluateSelection])

  // Dismiss when the anchor would go stale or the user signals dismissal.
  useEffect(() => {
    if (!floating) return
    const dismiss = () => setFloating(null)
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setFloating(null)
    }
    window.addEventListener('scroll', dismiss, { capture: true, passive: true })
    window.addEventListener('resize', dismiss, { passive: true })
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('scroll', dismiss, { capture: true })
      window.removeEventListener('resize', dismiss)
      window.removeEventListener('keydown', onKey)
    }
  }, [floating])

  if (!floating || typeof document === 'undefined') return null

  return createPortal(
    <button
      type="button"
      // Keep the text selection alive through the click (mousedown would otherwise clear it).
      onMouseDown={(e) => e.preventDefault()}
      onClick={() => {
        onAsk(floating.text)
        window.getSelection()?.removeAllRanges()
        setFloating(null)
      }}
      style={{ position: 'fixed', top: floating.top, left: floating.left, transform: 'translate(-50%, -100%)' }}
      className="z-[60] inline-flex items-center gap-1.5 rounded-full bg-brand-dark text-background-dark hover:bg-brand-strong-dark px-3 py-1.5 text-xs font-semibold shadow-lg transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light"
    >
      <SparkleIcon className="h-3.5 w-3.5" />
      Ask about this
    </button>,
    document.body,
  )
}
