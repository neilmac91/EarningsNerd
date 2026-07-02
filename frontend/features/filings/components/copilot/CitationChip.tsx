'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowSquareOutIcon, CheckCircleIcon } from '@/lib/icons'
import { isXbrlCitation, type CopilotCitation } from '@/features/filings/api/copilot-api'
import { useFilingViewer } from './FilingViewerContext'

// Only render a citation as an active link when it's an http(s) URL. Defense-in-depth against a
// malicious/unexpected scheme (e.g. javascript:) reaching the href — the backend builds these from
// SEC URLs, but the excerpt portion is model-influenced, so we validate before linking. Defined in
// this leaf component (and re-imported by CopilotMessage/FilingViewer) to avoid a circular import.
export const isHttpUrl = (url: string | null): url is string =>
  !!url && (url.startsWith('https://') || url.startsWith('http://'))

interface CitationChipProps {
  citation: CopilotCitation
}

interface PopoverPos {
  left: number
  top?: number
  bottom?: number
}

const POPOVER_WIDTH = 256 // w-64
const CLOSE_DELAY_MS = 120

/**
 * An interactive inline citation marker (`[n]`) injected into a completed Copilot answer.
 *
 * Clicking highlights the passage in the in-app filing viewer when one is mounted (see
 * FilingViewerContext); otherwise it degrades to a SEC-jump anchor (`#:~:text=` deep link). The
 * hover/focus popover (verbatim excerpt + verified/cited + "open original") is rendered through a
 * **portal** with fixed positioning so it can't be clipped by the rail's scroll container — and so
 * its links are genuinely clickable. A short close delay bridges the gap from chip to popover.
 */
export default function CitationChip({ citation }: CitationChipProps) {
  const { n, excerpt, section_ref, verified, fragment_url } = citation
  const viewer = useFilingViewer()
  const header = section_ref || `Excerpt ${n}`
  const ariaLabel = `Citation ${n}: ${header}`
  const marker = `[${n}]`

  const triggerRef = useRef<HTMLElement | null>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [pos, setPos] = useState<PopoverPos | null>(null)

  const clearCloseTimer = () => {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current)
      closeTimer.current = null
    }
  }

  const openPopover = useCallback(() => {
    clearCloseTimer()
    const el = triggerRef.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const gap = 8
    const left = Math.min(
      Math.max(r.left + r.width / 2, POPOVER_WIDTH / 2 + 8),
      window.innerWidth - POPOVER_WIDTH / 2 - 8,
    )
    // Prefer above; flip below when there isn't room (so it never opens off the top of the viewport).
    setPos(
      r.top > 220
        ? { left, bottom: window.innerHeight - r.top + gap }
        : { left, top: r.bottom + gap },
    )
  }, [])

  const scheduleClose = useCallback(() => {
    clearCloseTimer()
    closeTimer.current = setTimeout(() => setPos(null), CLOSE_DELAY_MS)
  }, [])

  // Clean up a pending close timer on unmount.
  useEffect(() => () => clearCloseTimer(), [])

  // A fixed popover would detach from its chip on scroll/resize → just close it. Scroll doesn't
  // bubble, so capture to catch scrolling in any ancestor (e.g. the rail's scroll container).
  useEffect(() => {
    if (!pos) return
    const dismiss = () => setPos(null)
    window.addEventListener('scroll', dismiss, { capture: true, passive: true })
    window.addEventListener('resize', dismiss, { passive: true })
    return () => {
      window.removeEventListener('scroll', dismiss, { capture: true })
      window.removeEventListener('resize', dismiss)
    }
  }, [pos])

  // XBRL figure chips ([F1]) read as hard data, distinct from filing-text excerpt chips ([1]): a
  // ringed, monospace tabular-figure treatment vs. the plain filled chip. Same mint hue (on-brand).
  const isFact = isXbrlCitation(citation)
  const chipBase =
    'inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded px-1 text-[11px] font-semibold leading-none align-baseline transition-colors focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
  const chipClass = isFact
    ? `${chipBase} bg-brand-strong/10 font-mono tabular-nums text-brand-strong ring-1 ring-inset ring-brand-border hover:bg-brand-strong/20 dark:bg-brand-dark/15 dark:text-brand-strong-dark dark:ring-brand-dark/40 dark:hover:bg-brand-dark/25`
    : `${chipBase} bg-brand-strong/10 text-brand-strong hover:bg-brand-strong/20 dark:bg-brand-dark/15 dark:text-brand-strong-dark dark:hover:bg-brand-dark/25`

  const triggerHandlers = {
    ref: (el: HTMLElement | null) => {
      triggerRef.current = el
    },
    'aria-label': ariaLabel,
    'data-citation-kind': isFact ? 'xbrl' : 'text',
    className: chipClass,
    onMouseEnter: openPopover,
    onMouseLeave: scheduleClose,
    onFocus: openPopover,
    onBlur: scheduleClose,
  }

  let trigger: React.ReactNode
  if (viewer) {
    // In-app highlight is the primary action when the filing viewer is mounted.
    trigger = (
      <button type="button" {...triggerHandlers} onClick={() => viewer.requestHighlight(citation)}>
        {marker}
      </button>
    )
  } else if (isHttpUrl(fragment_url)) {
    trigger = (
      <a {...triggerHandlers} href={fragment_url} target="_blank" rel="noopener noreferrer">
        {marker}
      </a>
    )
  } else {
    // No viewer and no usable URL: a non-navigating button — the popover is still reachable.
    trigger = (
      <button type="button" {...triggerHandlers}>
        {marker}
      </button>
    )
  }

  const popover =
    pos && typeof document !== 'undefined'
      ? createPortal(
          <span
            // A labelled group, not role="tooltip": the popover contains an interactive "Open
            // original" link, and a tooltip must not hold focusable/interactive content (ARIA).
            role="group"
            aria-label={ariaLabel}
            onMouseEnter={clearCloseTimer}
            onMouseLeave={scheduleClose}
            onFocus={clearCloseTimer}
            onBlur={scheduleClose}
            style={{ position: 'fixed', left: pos.left, top: pos.top, bottom: pos.bottom, transform: 'translateX(-50%)' }}
            className="z-[60] block w-64 rounded-lg border border-border-light bg-panel-light p-3 text-left shadow-xl dark:border-white/10 dark:bg-slate-900"
          >
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark break-words">
              {header}
            </span>
            <span className="mt-1.5 block max-h-40 overflow-y-auto border-l-2 border-brand-strong/50 dark:border-brand-dark/50 pl-2 text-xs italic text-text-secondary-light dark:text-text-secondary-dark break-words">
              {excerpt}
            </span>
            {verified ? (
              <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-brand-strong dark:text-brand-strong-dark">
                <CheckCircleIcon className="h-3 w-3 shrink-0" />
                Verified in filing
              </span>
            ) : (
              <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-text-secondary-light dark:text-text-secondary-dark">
                <ArrowSquareOutIcon className="h-3 w-3 shrink-0" />
                Cited
              </span>
            )}
            {viewer && isHttpUrl(fragment_url) && (
              <a
                href={fragment_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex items-center gap-1 text-[11px] font-medium text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:text-brand-strong dark:hover:text-brand-strong-dark"
              >
                <ArrowSquareOutIcon className="h-3 w-3 shrink-0" />
                Open original
              </a>
            )}
          </span>,
          document.body,
        )
      : null

  return (
    <span className="inline-block align-baseline">
      {trigger}
      {popover}
    </span>
  )
}
