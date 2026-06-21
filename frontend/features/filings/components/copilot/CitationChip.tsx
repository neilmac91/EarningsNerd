'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CheckCircle2, ExternalLink } from 'lucide-react'
import type { CopilotCitation } from '@/features/filings/api/copilot-api'
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

  const chipClass =
    'inline-flex min-h-[18px] min-w-[18px] items-center justify-center rounded bg-mint-500/15 px-1 text-[11px] font-semibold leading-none text-mint-300 align-baseline transition-colors hover:bg-mint-500/25 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-mint-400'

  const triggerHandlers = {
    ref: (el: HTMLElement | null) => {
      triggerRef.current = el
    },
    'aria-label': ariaLabel,
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
            role="tooltip"
            onMouseEnter={clearCloseTimer}
            onMouseLeave={scheduleClose}
            style={{ position: 'fixed', left: pos.left, top: pos.top, bottom: pos.bottom, transform: 'translateX(-50%)' }}
            className="z-[60] block w-64 rounded-lg border border-white/10 bg-slate-900 p-3 text-left shadow-xl"
          >
            <span className="block text-[11px] font-semibold uppercase tracking-wide text-slate-400 break-words">
              {header}
            </span>
            <span className="mt-1.5 block max-h-40 overflow-y-auto border-l-2 border-mint-500/50 pl-2 text-xs italic text-slate-200 break-words">
              {excerpt}
            </span>
            {verified ? (
              <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-mint-300">
                <CheckCircle2 className="h-3 w-3 shrink-0" />
                Verified in filing
              </span>
            ) : (
              <span className="mt-2 flex items-center gap-1 text-[11px] font-medium text-slate-400">
                <ExternalLink className="h-3 w-3 shrink-0" />
                Cited
              </span>
            )}
            {viewer && isHttpUrl(fragment_url) && (
              <a
                href={fragment_url}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 flex items-center gap-1 text-[11px] font-medium text-slate-400 transition-colors hover:text-mint-300"
              >
                <ExternalLink className="h-3 w-3 shrink-0" />
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
