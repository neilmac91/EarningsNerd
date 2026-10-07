'use client'

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { ArrowSquareOutIcon, CheckCircleIcon } from '@/lib/icons'
import { isXbrlCitation, type CopilotCitation } from '@/features/filings/api/copilot-api'
import { useFilingViewer } from './FilingViewerContext'
import { citationVerificationLabel, SOURCE_MATCH_SCOPE } from './citationVerification'
import { useEvidencePopoverKeys } from './useEvidencePopoverKeys'

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
  top: number
}

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
  const popoverRef = useRef<HTMLSpanElement | null>(null)
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null)
  const [pos, setPos] = useState<PopoverPos | null>(null)
  const linkRef = useRef<HTMLAnchorElement | null>(null)

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
    // The layout effect measures and places the card before paint. Its initial coordinates
    // only mount the portal; they do not assume a fixed height for variable source content.
    setPos({ left: r.left + r.width / 2, top: r.bottom + 8 })
  }, [])

  useLayoutEffect(() => {
    const card = popoverRef.current
    const trigger = triggerRef.current
    if (!pos || !card || !trigger) return
    const margin = 8
    const gap = 8
    const anchor = trigger.getBoundingClientRect()
    const bounds = card.getBoundingClientRect()
    const aboveSpace = Math.max(0, anchor.top - gap - margin)
    const belowSpace = Math.max(0, window.innerHeight - margin - anchor.bottom - gap)
    // Keep the trigger reachable: viewport clamping alone can put a tall portal over it.
    // Prefer a full card above, then below; otherwise scroll within the larger side.
    const placeAbove = bounds.height <= aboveSpace ||
      (bounds.height > belowSpace && aboveSpace >= belowSpace)
    card.style.maxHeight = `${placeAbove ? aboveSpace : belowSpace}px`
    const fittedHeight = card.getBoundingClientRect().height
    const top = placeAbove ? anchor.top - gap - fittedHeight : anchor.bottom + gap
    const left = Math.max(margin + bounds.width / 2,
      Math.min(anchor.left + anchor.width / 2, window.innerWidth - margin - bounds.width / 2))
    // DOM placement avoids a second React render and stays paired with this measured card.
    card.style.top = `${top}px`
    card.style.left = `${left}px`
  }, [pos, excerpt, header, verified, viewer])

  const scheduleClose = useCallback(() => {
    clearCloseTimer()
    closeTimer.current = setTimeout(() => setPos(null), CLOSE_DELAY_MS)
  }, [])

  // Clean up a pending close timer on unmount.
  useEffect(() => () => clearCloseTimer(), [])

  // A fixed popover would detach from its chip on scroll/resize. A hover popover just closes; one
  // the keyboard owns (the chip focused, or focus inside the popover) re-anchors instead: focusing
  // a chip the rail has to scroll into view used to close the popover the focus had just opened, so
  // Tab could never reach "Open original" (EN-01). Scroll doesn't bubble, so capture to catch
  // scrolling in any ancestor (e.g. the rail's scroll container). Scrolling the portal itself or its
  // excerpt must keep its content/actions reachable.
  useEffect(() => {
    if (!pos) return
    const onMove = (event: Event) => {
      if (event.type === 'scroll' && event.target instanceof Node && popoverRef.current?.contains(event.target)) return
      const active = document.activeElement
      const keyboardOwned = active === triggerRef.current || !!popoverRef.current?.contains(active)
      if (keyboardOwned) openPopover()
      else setPos(null)
    }
    window.addEventListener('scroll', onMove, { capture: true, passive: true })
    window.addEventListener('resize', onMove, { passive: true })
    return () => {
      window.removeEventListener('scroll', onMove, { capture: true })
      window.removeEventListener('resize', onMove)
    }
  }, [pos, openPopover])

  // Keyboard contract shared with SourceTrace (EN-01): Tab from the chip reaches "Open original", Tab
  // past it resumes the page after the chip, Shift+Tab returns to the chip, Escape closes + refocuses.
  const closePopover = useCallback(() => setPos(null), [])
  const keys = useEvidencePopoverKeys({
    open: pos !== null,
    triggerRef,
    popoverRef,
    actionRef: linkRef,
    close: closePopover,
    holdOpen: clearCloseTimer,
    ownsEscape: true,
  })

  // XBRL figure chips ([F1]) read as hard data, distinct from filing-text excerpt chips ([1]):
  // the same bordered brand-tint chip (the v2.2 marker treatment), with the mono/tabular register
  // marking figures. Inline markers fall under the WCAG 2.5.8 inline-target exception (18px).
  const isFact = isXbrlCitation(citation)
  const chipBase =
    'inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded border px-1 font-data text-data-xs font-semibold leading-none align-baseline transition-colors ' +
    'border-brand-border bg-brand-weak text-brand-strong hover:bg-brand-border/60 ' +
    'dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark dark:hover:bg-brand-border-dark ' +
    'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'
  // chipBase is already mono (font-data); .tnum adds only the tabular flag —
  // the DS spelling for data surfaces that already carry the data face.
  const chipClass = isFact ? `${chipBase} tnum` : chipBase

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
    onKeyDown: keys.onTriggerKeyDown,
  }

  let trigger: React.ReactNode
  if (viewer) {
    // In-app highlight is the primary action when the filing viewer is mounted; the chip is the
    // opener the pane returns focus to on close.
    trigger = (
      <button type="button" {...triggerHandlers} onClick={(e) => viewer.requestHighlight(citation, e.currentTarget)}>
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
            ref={popoverRef}
            role="group"
            aria-label={ariaLabel}
            onMouseEnter={clearCloseTimer}
            onMouseLeave={scheduleClose}
            onFocus={clearCloseTimer}
            onBlur={scheduleClose}
            onKeyDown={keys.onPopoverKeyDown}
            style={{ position: 'fixed', left: pos.left, top: pos.top, transform: 'translateX(-50%)',
              maxWidth: Math.max(0, window.innerWidth - 16), maxHeight: Math.max(0, window.innerHeight - 16),
              overflowY: 'auto' }}
            className="z-overlay block w-64 rounded-lg border border-border-light bg-panel-light p-3 text-left shadow-e5 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
          >
            <span className="block text-data-xs font-semibold uppercase tracking-eyebrow text-text-secondary-light dark:text-text-secondary-dark break-words">
              {header}
            </span>
            <span className="mt-1.5 block max-h-40 overflow-y-auto border-l-2 border-brand-border dark:border-brand-border-dark pl-2 font-data text-xs text-text-secondary-light dark:text-text-secondary-dark break-words">
              {excerpt}
            </span>
            {verified ? (
              <span className="mt-2 flex items-center gap-1 text-data-xs font-medium text-brand-strong dark:text-brand-strong-dark">
                <CheckCircleIcon className="h-3 w-3 shrink-0" />
                {citationVerificationLabel(citation)}
              </span>
            ) : (
              <span className="mt-2 flex items-center gap-1 text-data-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">
                <ArrowSquareOutIcon className="h-3 w-3 shrink-0" />
                Cited
              </span>
            )}
            {verified && (
              <span className="mt-1.5 block text-xs text-text-secondary-light dark:text-text-secondary-dark">
                {SOURCE_MATCH_SCOPE}
              </span>
            )}
            {viewer && isHttpUrl(fragment_url) && (
              <a
                ref={linkRef}
                href={fragment_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex items-center gap-1 text-data-xs font-medium text-text-secondary-light dark:text-text-secondary-dark transition-colors hover:text-brand-strong dark:hover:text-brand-strong-dark"
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
