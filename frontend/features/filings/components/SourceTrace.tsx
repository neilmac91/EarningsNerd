'use client'

import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode, type Ref, type RefObject } from 'react'
import { createPortal } from 'react-dom'
import { ArrowSquareOutIcon, CheckCircleIcon, FileTextIcon, XIcon } from '@/lib/icons'
import { Button } from '@/components/ui'
import { useFilingViewer } from '@/features/filings/components/copilot/FilingViewerContext'
import { useSheetFocusTrap } from '@/features/filings/components/copilot/useSheetFocusTrap'
import { useEvidencePopoverKeys } from '@/features/filings/components/copilot/useEvidencePopoverKeys'

/**
 * Shared "Trace to Source" provenance affordance — the ambient, on-brand way every metric and risk
 * claim links back to the SEC filing, matching the Copilot's CitationChip treatment so provenance
 * reads as one consistent texture across the app (Plan D2).
 *
 * A compact verified/cited chip. On a fine pointer it reveals a hover/focus popover (section, the
 * verified/cited explanation, an "Open in SEC EDGAR" deep link). With a `FilingViewerProvider`
 * mounted (the filing page), activating the chip opens the research pane on the Filing tab and
 * highlights the passage when the filing text is available and matched, or shows the pane's truthful
 * empty state with its original-document action; activation never does nothing (EN-01). On a coarse
 * pointer (touch) a tap opens the bottom sheet, which carries the same detail plus "Show in filing",
 * the in-app jump, so provenance is first-class on mobile rather than a straight drop onto EDGAR.
 * Keyboard: Tab from a focused chip reaches the popover's EDGAR link and Tab again resumes the page
 * after the chip; Escape closes the popover or sheet and returns focus to the chip; the sheet traps
 * focus while open. Nothing here reads plan or auth state: the route to the source is the same for
 * anonymous, free and Pro visitors.
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
   * `FilingViewerProvider` is mounted, activating the chip jumps to the source in-app (opening the
   * pane); the EDGAR link stays available in the popover and the sheet. A verified risk excerpt
   * anchors precisely; metrics (no verbatim excerpt) fall back to the section heading.
   */
  excerpt?: string | null
  /**
   * Pairs this chip with its copy in a component's other responsive layout (FinancialMetricsTable
   * renders every chip in its phone cards and again in its md+ table, and CSS shows one copy). When
   * a breakpoint hides the chip while its sheet or popover is open, the surface closes and focus that
   * was on the chip or in the surface moves to the copy now shown.
   */
  layoutTwin?: string
}

/** The rendered copy of a chip paired by `layoutTwin`, other than `chip` itself. */
function shownTwin(chip: HTMLElement, layoutTwin: string): HTMLElement | null {
  const copies = Array.from(document.querySelectorAll<HTMLElement>('[data-layout-twin]'))
  return copies.find((el) => el !== chip && el.dataset.layoutTwin === layoutTwin && el.getClientRects().length > 0) ?? null
}

interface PopoverPos {
  left: number
  top?: number
  bottom?: number
}

const POPOVER_WIDTH = 288 // w-72
const CLOSE_DELAY_MS = 120

/**
 * The chip's full trigger className: the base recipe plus the verified/cited colourway. Exported so
 * the landing page's Trace-to-Source demo renders a chip identical to the product's.
 */
export const sourceTraceChipClass = (isVerified: boolean): string => {
  const tone = isVerified
    ? 'text-brand-strong dark:text-brand-strong-dark hover:bg-brand-weak dark:hover:bg-white/5'
    : 'text-text-tertiary-light dark:text-text-secondary-dark hover:bg-border-light/40 dark:hover:bg-white/5'
  return `inline-flex items-center gap-1 rounded px-1 py-0.5 text-data-xs font-medium leading-none align-baseline transition-colors focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark ${tone}`
}

/**
 * Presentational body of the provenance panel: section header, verified/cited status line, an
 * optional in-app action and the "Open in SEC EDGAR" link. Shared by the desktop popover, the touch
 * bottom-sheet and the landing page's Trace-to-Source demo.
 */
export function SourceTracePanelBody({
  header,
  isVerified,
  note,
  url,
  excerpt,
  action,
  linkRef,
}: {
  header: string | null
  isVerified: boolean
  note: string | null
  url: string | null
  /** Optional verbatim passage, slotted between the header and the status line. */
  excerpt?: ReactNode
  /** Optional in-app action (the sheet's "Show in filing"), slotted before the EDGAR link. */
  action?: ReactNode
  /** The EDGAR link's ref, for the popover's keyboard hand-off. */
  linkRef?: Ref<HTMLAnchorElement>
}) {
  const statusLine = isVerified ? (
    <span className="mt-2 flex items-center gap-1 text-data-xs font-medium text-brand-strong dark:text-brand-strong-dark">
      <CheckCircleIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {note || 'Verified against the original SEC filing'}
    </span>
  ) : (
    <span className="mt-2 flex items-center gap-1 text-data-xs font-medium text-text-tertiary-light dark:text-text-secondary-dark">
      <ArrowSquareOutIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {note || 'Cited. Open the section to confirm.'}
    </span>
  )

  return (
    <>
      {header && (
        <span className="block text-data-xs font-semibold uppercase tracking-eyebrow text-text-tertiary-light dark:text-text-secondary-dark break-words">
          {header}
        </span>
      )}
      {excerpt}
      {statusLine}
      {action}
      {url && (
        <a
          ref={linkRef}
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center gap-1 text-data-xs font-medium text-text-tertiary-light transition-colors hover:text-brand-strong dark:text-text-secondary-dark dark:hover:text-brand-strong-dark"
        >
          <ArrowSquareOutIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
          Open in SEC EDGAR
        </a>
      )}
    </>
  )
}

export function SourceTrace({ url, verified, sectionRef, label, note, excerpt, layoutTwin }: SourceTraceProps) {
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
      layoutTwin={layoutTwin}
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
  layoutTwin,
}: {
  url: string | null
  isVerified: boolean
  header: string | null
  note: string | null
  chipLabel: string
  panelId: string
  excerpt: string | null
  layoutTwin?: string
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
  const sheetRef = useRef<HTMLDivElement | null>(null)
  const popoverRef = useRef<HTMLSpanElement | null>(null)
  const edgarRef = useRef<HTMLAnchorElement | null>(null)
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

  // Desktop popover detaches from its anchor on scroll/resize. A hover popover closes; one the
  // keyboard owns (the chip focused, or focus inside the popover) re-anchors instead, because
  // focusing a chip below the fold scrolls it into view, and that scroll used to close the popover
  // the focus had just opened, so Tab could never reach its link (EN-01). Capture catches any
  // scrolling ancestor. The mobile sheet is fixed to the viewport, so it's exempt.
  useEffect(() => {
    if (!open || isCoarse) return
    const onMove = () => {
      const active = document.activeElement
      const keyboardOwned = active === triggerRef.current || !!popoverRef.current?.contains(active)
      if (keyboardOwned) computePos()
      else setOpen(false)
    }
    window.addEventListener('scroll', onMove, { capture: true, passive: true })
    window.addEventListener('resize', onMove, { passive: true })
    return () => {
      window.removeEventListener('scroll', onMove, { capture: true })
      window.removeEventListener('resize', onMove)
    }
  }, [open, isCoarse, computePos])

  // A chip hidden by a breakpoint takes its surface with it. FinancialMetricsTable renders each chip
  // twice (phone cards below md, the table at md+) and CSS shows one copy: rotating a phone across
  // 768px with this sheet open left it over the other layout, and closing it then returned focus to a
  // display:none chip. Whatever the pointer, an open surface whose chip is no longer rendered closes;
  // focus that was on the chip or in the surface goes to the chip's twin now shown (the sheet's trap
  // through `returnTarget`, the trap-less popover here).
  useEffect(() => {
    if (!open) return
    const onResize = () => {
      const chip = triggerRef.current
      if (!chip || chip.getClientRects().length > 0) return
      const active = document.activeElement
      const held = active === chip || !!popoverRef.current?.contains(active)
      setOpen(false)
      if (held && !isCoarse && layoutTwin) shownTwin(chip, layoutTwin)?.focus()
    }
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [open, isCoarse, layoutTwin])

  // ESC closes either presentation when this panel owns the key (on a phone, the source sheet can
  // sit over the copilot sheet), so it owns the key: window capture runs ahead of the sheet's
  // document-level trap and the rail's own Escape listener, and stopping it there closes one layer
  // per press. lessons/frontend-top-dialog-owns-the-keyboard.md
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape') return
      // ui/Modal can open above this panel and traps focus inside its marked panel. Its capture
      // listener shares window with ours, so stopPropagation alone cannot shield it. Do not use
      // aria-modal here: a lower copilot sheet can also retain focus beneath the source sheet.
      if (e.target instanceof Element && e.target.closest('[data-ui-modal="true"]')) return
      e.stopPropagation()
      // A keyboard user who tabbed into the popover's EDGAR link gets the chip back, not <body>.
      // (The sheet's trap restores focus to the chip itself on close.)
      if (!isCoarse && popoverRef.current?.contains(document.activeElement)) triggerRef.current?.focus()
      setOpen(false)
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, isCoarse])

  // The touch sheet is a modal layer: trap focus inside it while open and return it to the chip on
  // close (the chip stays mounted beneath the scrim: lessons/frontend-dialog-opener-outlives-the-dialog.md).
  // Read at close: the chip, or its twin when a breakpoint hid the chip (see the resize effect above).
  const returnTarget = useMemo<RefObject<HTMLElement | null>>(
    () => ({
      get current() {
        const chip = triggerRef.current
        if (chip && layoutTwin && chip.getClientRects().length === 0) return shownTwin(chip, layoutTwin) ?? chip
        return chip
      },
    }),
    [layoutTwin],
  )
  useSheetFocusTrap({ active: open && isCoarse, containerRef: sheetRef, onClose: closePanel, restoreFocusRef: returnTarget })

  // Fine pointer: Tab reaches the popover's EDGAR link and resumes the page after the chip; Escape
  // is handled above. See useEvidencePopoverKeys for the shared contract with CitationChip. With no
  // viewer the chip is itself the EDGAR anchor, so the hand-off would only add a second stop for the
  // same link: it stays off there.
  const triggerIsLink = !isCoarse && !canHighlight && !!url
  const keys = useEvidencePopoverKeys({
    open: open && !isCoarse && !triggerIsLink,
    triggerRef,
    popoverRef,
    actionRef: edgarRef,
    close: closePanel,
    holdOpen: clearCloseTimer,
  })

  const Icon = isVerified ? CheckCircleIcon : ArrowSquareOutIcon

  // The browser blurs a focused chip that a breakpoint hides (no relatedTarget, no client rects left)
  // in a task of its own, which can run before the resize effect above sees the change. That focus
  // goes to the twin now shown as well, so whichever comes first, keyboard focus never falls to
  // <body>. Any other blur is the ordinary hover/focus close.
  const handleTriggerBlur = (e: React.FocusEvent<HTMLElement>) => {
    const chip = e.currentTarget
    const twin =
      layoutTwin && e.relatedTarget === null && chip.getClientRects().length === 0 ? shownTwin(chip, layoutTwin) : null
    if (twin) {
      clearCloseTimer()
      setOpen(false)
      twin.focus()
      return
    }
    if (!isCoarse) scheduleClose()
  }

  const handleTrigger = () => {
    // Toggle the panel on click: the sheet on a coarse pointer, the popover on a fine pointer with no
    // URL and no in-app jump. On fine pointers WITH a URL and no viewer the trigger is an <a>.
    if (open) closePanel()
    else openPanel()
  }

  // The chip is an anchor when linkable and no viewer is mounted (so fine-pointer click + middle-click
  // open EDGAR, and it's keyboard-reachable); with a viewer it is the in-app jump; on coarse pointers
  // it is always the sheet's trigger, with the jump and the EDGAR link inside the sheet.
  const triggerCommon = {
    ref: triggerRef as React.RefObject<HTMLButtonElement> & React.RefObject<HTMLAnchorElement>,
    'aria-label': `Source: ${chipLabel}`,
    'data-layout-twin': layoutTwin,
    className: sourceTraceChipClass(isVerified),
    onMouseEnter: isCoarse ? undefined : openPanel,
    onMouseLeave: isCoarse ? undefined : scheduleClose,
    onFocus: isCoarse ? undefined : openPanel,
    onBlur: handleTriggerBlur,
    onKeyDown: isCoarse ? undefined : keys.onTriggerKeyDown,
  }

  const chipInner = (
    <>
      <Icon className="h-3 w-3 shrink-0" aria-hidden="true" />
      {chipLabel}
    </>
  )

  // The in-app jump: record the passage, switch the pane to the Filing tab and open it (the provider
  // calls the page's onRequestOpen). The chip is the opener the pane returns focus to on close.
  const jumpToSource = () => {
    // Dismiss the popover or sheet so it doesn't linger over the freshly-highlighted passage.
    closePanel()
    viewer?.requestHighlight(
      {
        n: 0,
        excerpt: highlightTarget,
        section_ref: header,
        verified: isVerified,
        fragment_url: url,
      },
      triggerRef.current,
    )
  }

  const trigger = isCoarse ? (
    // Touch: the documented bottom sheet, which holds the in-app jump (when a viewer is mounted) and
    // the EDGAR link. Even with a viewer the tap opens the sheet, never a silent jump.
    <button
      type="button"
      {...triggerCommon}
      onClick={handleTrigger}
      aria-haspopup="dialog"
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
    >
      {chipInner}
    </button>
  ) : canHighlight ? (
    // In-app: activating jumps to + highlights the source in the embedded filing viewer, opening the
    // pane; the hover/focus panel still offers "Open in SEC EDGAR" as the fallback.
    <button
      type="button"
      {...triggerCommon}
      onClick={jumpToSource}
      aria-expanded={open}
      aria-controls={open ? panelId : undefined}
    >
      {chipInner}
    </button>
  ) : url ? (
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

  let overlay: ReactNode = null
  if (open && typeof document !== 'undefined') {
    if (isCoarse) {
      const showInFiling = canHighlight ? (
        <Button
          variant="secondary"
          size="sm"
          className="mt-3"
          leftIcon={<FileTextIcon className="h-3.5 w-3.5" aria-hidden="true" />}
          onClick={jumpToSource}
        >
          Show in filing
        </Button>
      ) : null
      overlay = createPortal(
        <div className="fixed inset-0 z-modal" role="dialog" aria-modal="true" aria-label="Source detail">
          {/* The scrim closes on tap but is no tab stop: the trap's first stop is the close button. */}
          <button
            type="button"
            aria-hidden="true"
            tabIndex={-1}
            className="absolute inset-0 bg-overlay"
            onClick={closePanel}
          />
          <div
            ref={sheetRef}
            id={panelId}
            className="absolute inset-x-0 bottom-0 max-h-[80vh] overflow-y-auto rounded-t-2xl border-t border-border-light bg-background-light p-4 pb-6 shadow-e5 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
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
            <SourceTracePanelBody header={header} isVerified={isVerified} note={note} url={url} action={showInFiling} />
          </div>
        </div>,
        document.body,
      )
    } else if (pos) {
      overlay = createPortal(
        <span
          ref={popoverRef}
          id={panelId}
          role="group"
          aria-label="Source detail"
          onMouseEnter={clearCloseTimer}
          onMouseLeave={scheduleClose}
          onFocus={clearCloseTimer}
          onBlur={scheduleClose}
          onKeyDown={keys.onPopoverKeyDown}
          style={{ position: 'fixed', left: pos.left, top: pos.top, bottom: pos.bottom, transform: 'translateX(-50%)' }}
          className="z-overlay block w-72 rounded-lg border border-border-light bg-background-light p-3 text-left shadow-e4 dark:shadow-none dark:border-border-dark dark:bg-panel-dark"
        >
          <SourceTracePanelBody header={header} isVerified={isVerified} note={note} url={url} linkRef={edgarRef} />
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
