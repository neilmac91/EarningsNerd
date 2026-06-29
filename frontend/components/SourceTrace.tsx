'use client'

import { useCallback, useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowSquareOutIcon, CheckCircleIcon, XIcon } from '@/lib/icons'
import { useFilingViewer } from '@/features/filings/components/copilot/FilingViewerContext'

/**
 * Shared "Trace to Source" provenance affordance — the ambient, on-brand way every metric and risk
 * claim links back to the SEC filing, matching the Copilot's CitationChip treatment so provenance
 * reads as one consistent texture across the app (Plan D2).
 *
 * A compact verified/cited chip that, on a fine pointer, reveals a hover/focus popover, and on a
 * coarse pointer (touch) opens a tap bottom-sheet — so the provenance detail (section, an optional
 * verbatim excerpt, the verified/cited explanation, and an "Open in SEC EDGAR" deep link) is
 * first-class on mobile, not an afterthought that dumps the user straight onto EDGAR.
 */

const isHttpUrl = (u: string | null | undefined): u is string =>
  !!u && (u.startsWith('https://') || u.startsWith('http://'))

interface SourceTraceProps {
  url?: string | null
  verified?: boolean | null
  /** e.g. "Item 1A · Risk Factors" — shown as the panel header. */
  sectionRef?: string | null
  /** Chip text. Defaults to the honest verified/cited vocabulary. */
  label?: string
  /** One-line explanation in the panel (e.g. a metric's XBRL match note). */
  note?: string | null
  /**
   * Verbatim filing text to scroll-highlight in the IN-APP viewer (item 1.4). When a
   * `FilingViewerProvider` is mounted, the chip becomes an in-app "jump to source" instead of an
   * external EDGAR link; the EDGAR link stays available as the popover fallback. A verified risk
   * excerpt anchors precisely; metrics (no verbatim excerpt) fall back to the section heading.
   */
  excerpt?: string | null
}

interface PopoverPos {
  left: number
  top?: number
  bottom?: number
}

const POPOVER_WIDTH = 288 // w-72
const CLOSE_DELAY_MS = 120

export function SourceTrace({ url, verified, sectionRef, label, note, excerpt }: SourceTraceProps) {
  const isVerified = verified === true
  const header = sectionRef?.trim() || null
  const chipLabel = label ?? (isVerified ? 'Verified in filing' : 'Cited')
  const linkable = isHttpUrl(url)
  const panelId = useId()

  // Nothing to trace → render nothing (keeps the affordance honest + backward-compatible).
  if (!header && !note && !linkable) return null

  return (
    <SourceTraceInner
      url={linkable ? url! : null}
      isVerified={isVerified}
      header={header}
      note={note?.trim() || null}
      chipLabel={chipLabel}
      panelId={panelId}
      excerpt={excerpt?.trim() || null}
    />
  )
}

function SourceTraceInner({
  url,
  isVerified,
  header,
  note,
  chipLabel,
  panelId,
  excerpt,
}: {
  url: string | null
  isVerified: boolean
  header: string | null
  note: string | null
  chipLabel: string
  panelId: string
  excerpt: string | null
}) {
  const viewer = useFilingViewer()
  // In-app source highlight (item 1.4): prefer a verbatim excerpt (a verified risk-evidence span
  // anchors the exact line); else fall back to the section heading (metrics have no verbatim
  // excerpt — a best-effort section jump that degrades to "couldn't pinpoint, showing the full
  // filing" when the heading isn't found, never a wrong line).
  // Prefer the verbatim excerpt (anchors the exact line); if it's too short to anchor reliably,
  // fall back to the section heading rather than disabling the in-app jump entirely.
  const highlightTarget =
    excerpt && excerpt.length >= 4 ? excerpt : header && header.length >= 4 ? header : ''
  const canHighlight = !!viewer && !!highlightTarget
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [open, setOpen] = useState(false)
  const [pos, setPos] = useState<PopoverPos | null>(null)
  // Coarse pointer (touch) → tap opens a bottom sheet; fine pointer → hover/focus popover.
  const [isCoarse, setIsCoarse] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mq = window.matchMedia('(pointer: coarse)')
    const update = () => setIsCoarse(mq.matches)
    update()
    mq.addEventListener?.('change', update)
    return () => mq.removeEventListener?.('change', update)
  }, [])

  const clearCloseTimer = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
  }

  const computePos = useCallback(() => {
    const el = triggerRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const gap = 8
    const left = Math.min(
      Math.max(r.left + r.width / 2, POPOVER_WIDTH / 2 + 8),
      window.innerWidth - POPOVER_WIDTH / 2 - 8,
    )
    setPos(
      r.top > 240
        ? { left, bottom: window.innerHeight - r.top + gap }
        : { left, top: r.bottom + gap },
    )
  }, [])

  const openPanel = useCallback(() => {
    clearCloseTimer()
    if (!isCoarse) computePos()
    setOpen(true)
  }, [isCoarse, computePos])

  const closePanel = useCallback(() => setOpen(false), [])

  const scheduleClose = useCallback(() => {
    clearCloseTimer()
    closeTimer.current = setTimeout(() => setOpen(false), CLOSE_DELAY_MS)
  }, [])

  useEffect(() => () => clearCloseTimer(), [])

  // Desktop popover detaches from its anchor on scroll/resize → close it. Capture to catch any
  // scrolling ancestor. The mobile sheet is fixed to the viewport, so it's exempt.
  useEffect(() => {
    if (!open || isCoarse) return
    const dismiss = () => setOpen(false)
    window.addEventListener('scroll', dismiss, { capture: true, passive: true })
    window.addEventListener('resize', dismiss, { passive: true })
    return () => {
      window.removeEventListener('scroll', dismiss, { capture: true })
      window.removeEventListener('resize', dismiss)
    }
  }, [open, isCoarse])

  // ESC closes either presentation.
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open])

  const Icon = isVerified ? CheckCircleIcon : ArrowSquareOutIcon
  const chipClass = isVerified
    ? 'text-brand-strong dark:text-brand-strong-dark hover:bg-brand-weak dark:hover:bg-white/5'
    : 'text-text-tertiary-light dark:text-text-secondary-dark hover:bg-border-light/40 dark:hover:bg-white/5'

  const handleTrigger = () => {
    // Toggle the panel on click. On fine pointers WITH a URL the trigger is an <a> (no onClick), so a
    // click opens EDGAR; this handler only runs on the <button> (no-URL desktop, or any touch).
    if (open) closePanel()
    else openPanel()
  }

  const statusLine = isVerified ? (
    <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-brand-strong dark:text-brand-strong-dark">
      <CheckCircleIcon className="h-3 w-3 shrink-0" />
      {note || 'Verified against the original SEC filing'}
    </span>
  ) : (
    <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-text-tertiary-light dark:text-text-secondary-dark">
      <ArrowSquareOutIcon className="h-3 w-3 shrink-0" />
      {note || 'Cited — open the section to confirm'}
    </span>
  )

  const panelBody = (
    <>
      {header && (
        <span className="block text-[11px] font-semibold uppercase tracking-wide text-text-tertiary-light dark:text-text-secondary-dark break-words">
          {header}
        </span>
      )}
      {statusLine}
      {url && (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center gap-1 text-[11px] font-medium text-text-tertiary-light transition-colors hover:text-brand-strong dark:text-text-secondary-dark dark:hover:text-brand-strong-dark"
        >
          <ArrowSquareOutIcon className="h-3 w-3 shrink-0" />
          Open in SEC EDGAR
        </a>
      )}
    </>
  )

  // The chip is an anchor when linkable (so fine-pointer click + middle-click open EDGAR, and it's
  // keyboard-reachable) — except on coarse pointers, where tapping must open the sheet, so we use a
  // button there and surface the EDGAR link inside the sheet.
  const triggerCommon = {
    ref: triggerRef as React.RefObject<HTMLButtonElement> & React.RefObject<HTMLAnchorElement>,
    'aria-label': `Source: ${chipLabel}`,
    className: `inline-flex items-center gap-1 rounded px-1 py-0.5 text-[11px] font-medium leading-none align-baseline transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-brand-light ${chipClass}`,
    onMouseEnter: isCoarse ? undefined : openPanel,
    onMouseLeave: isCoarse ? undefined : scheduleClose,
    onFocus: isCoarse ? undefined : openPanel,
    onBlur: isCoarse ? undefined : scheduleClose,
  }

  const chipInner = (
    <>
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {chipLabel}
    </>
  )

  const doHighlight = () => {
    // Dismiss the hover/focus popover so it doesn't linger over the freshly-highlighted passage.
    closePanel()
    viewer?.requestHighlight({
      n: 0,
      excerpt: highlightTarget,
      section_ref: header,
      verified: isVerified,
      fragment_url: url,
    })
  }

  const trigger = canHighlight ? (
    // In-app: clicking jumps to + highlights the source in the embedded filing viewer; the
    // hover/focus panel still offers "Open in SEC EDGAR" as the fallback.
    <button
      type="button"
      {...triggerCommon}
      onClick={doHighlight}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
    >
      {chipInner}
    </button>
  ) : url && !isCoarse ? (
    <a {...triggerCommon} href={url} target="_blank" rel="noopener noreferrer">
      {chipInner}
    </a>
  ) : (
    <button
      type="button"
      {...triggerCommon}
      onClick={handleTrigger}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
    >
      {chipInner}
    </button>
  )

  let overlay: React.ReactNode = null
  if (open && typeof document !== 'undefined') {
    if (isCoarse) {
      overlay = createPortal(
        <div className="fixed inset-0 z-[70]" role="dialog" aria-modal="true" aria-label="Source detail">
          <button
            type="button"
            aria-label="Close"
            className="absolute inset-0 bg-black/40"
            onClick={closePanel}
          />
          <div
            id={panelId}
            className="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-2xl border-t border-border-light bg-background-light p-4 pb-6 shadow-2xl dark:border-border-dark dark:bg-panel-dark"
          >
            <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-border-light dark:bg-border-dark" />
            <button
              type="button"
              onClick={closePanel}
              aria-label="Close source detail"
              className="absolute right-3 top-3 rounded p-1 text-text-tertiary-light hover:bg-border-light/40 dark:text-text-secondary-dark dark:hover:bg-white/5"
            >
              <XIcon className="h-4 w-4" />
            </button>
            {panelBody}
          </div>
        </div>,
        document.body,
      )
    } else if (pos) {
      overlay = createPortal(
        <span
          id={panelId}
          role="group"
          aria-label="Source detail"
          onMouseEnter={clearCloseTimer}
          onMouseLeave={scheduleClose}
          style={{ position: 'fixed', left: pos.left, top: pos.top, bottom: pos.bottom, transform: 'translateX(-50%)' }}
          className="z-[60] block w-72 rounded-lg border border-border-light bg-background-light p-3 text-left shadow-xl dark:border-border-dark dark:bg-panel-dark"
        >
          {panelBody}
        </span>,
        document.body,
      )
    }
  }

  return (
    <span className="inline-flex align-baseline">
      {trigger}
      {overlay}
    </span>
  )
}
