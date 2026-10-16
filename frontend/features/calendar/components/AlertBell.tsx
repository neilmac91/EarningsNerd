'use client'

/* =============================================================================
   AlertBell + BellPopover (features/calendar/components/AlertBell.tsx)
   -----------------------------------------------------------------------------
   The per-company earnings-alert toggle. Everyone sees the bell:
     - signed-out  → popover prompting sign-in; its second action follows the
                     access mode (ACCESS_COPY: an invite while registration is
                     invite-only, the free account when it is public)
     - free at cap → upsell popover (deliberate conversion surface, §3.7)
     - pro at cap  → the API's terse 403 message, verbatim, no upsell
   aria-pressed carries the on/off state.

   BellPopover is a NON-MODAL popover, not a dialog (DESIGN_SYSTEM §4 Stacking:
   z-overlay). It explains one control, anchored to it, and dismisses lightly:
   nothing behind it is made inert, Tab is not trapped and the page does not
   lock. Modal semantics (a dialog role plus a trap, or ui/Modal's centred scrim)
   would claim an interruption it does not make, and ui/Modal portals to <body>,
   where a bell inside DayDetailDialog's native top layer could not reach it.
   So it carries no dialog role: a group named by its title and described by
   its message (the async error kind is also announced as an alert), with
   the popover keyboard contract —
     - focus moves to the first action on open, unless the user already moved
       it elsewhere while a request was pending; the effect arms ONCE per popover
       (onClose read through a ref — the page hands a new one every render);
     - Escape closes (window capture + preventDefault, so a native <dialog>
       beneath does not close on the same key);
     - Tab past the last action or Shift+Tab before the first closes it and
       resumes the page's order at the bell, as a native popover's would;
     - a scroll that moves the bell, or a resize, closes it (fixed at the bell's
       rect, it would detach), as CitationChip's popover does;
     - every close returns focus to the bell unless the user moved it on.
   It is placed where it fits, from its measured height (placeBellPopover):
   18.75rem wide within the visible viewport, below the bell when it fits there
   whole, above it when only that side holds it (capped at its own height), else
   on the roomier side with its height capped there, scrolling inside. When
   neither side offers 6rem of the reader's text (a landscape phone at large
   text, or with the keyboard up), it spans the visible height over the bell and
   scrolls inside: a side that short would show the panel's padding and a line.
   Never past what the reader can see, the bell in view or not. Capped, the
   panel scrolls its focused action into view, never the page. A guessed height
   ran a tall popover (200% text) off the bottom of the screen.
   The transparent click-catcher stays: an outside press closes only the
   popover, so it cannot also close the day dialog through its backdrop or
   re-toggle the bell that raised it.
   While a native <dialog> is open it portals into that dialog, sharing its top
   layer instead of rendering inert beneath it.
============================================================================= */

import { useEffect, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import Link from 'next/link'
import { BellIcon, LockSimpleIcon, WarningCircleIcon } from '@/lib/icons'
import { Button, buttonVariants } from '@/components/ui'
import { cx } from '@/components/ui/cx'
import type { BlockedState, EarningsAlertsApi } from '../hooks/useCalendar'
import { FREE_EARNINGS_ALERT_LIMIT } from '@/lib/planLimits'
import { ACCESS_COPY, DEFAULT_ACCESS_MODE, type AccessMode } from '@/features/marketing/lib/access'

export function AlertBell({
  ticker,
  alerts,
  signedIn,
  size = 'sm',
  className,
}: {
  ticker: string
  alerts: EarningsAlertsApi
  signedIn: boolean
  /** sm = 28px (dense desktop cells) · lg = 44px (mobile / dialog rows). */
  size?: 'sm' | 'lg'
  className?: string
}) {
  const on = alerts.isOn(ticker)
  const pending = alerts.isPending(ticker)
  const checking = alerts.identityPending
  const label = checking
    ? `Checking your account before managing alerts for ${ticker}`
    : !signedIn
    ? `Sign in to get earnings alerts for ${ticker}`
    : on
      ? `Turn off earnings alerts for ${ticker}`
      : `Get an email the morning ${ticker} reports`
  return (
    <button
      type="button"
      aria-pressed={on}
      aria-label={label}
      title={label}
      // While its own toggle is in flight the bell is aria-disabled, not natively disabled: a focused
      // button that turns `disabled` is blurred to <body> (Chromium), so every keyboard toggle sent the
      // user back to the top of the page. `checking` stays native — it only holds before identity
      // resolves, when the bell cannot have focus yet.
      disabled={checking}
      aria-disabled={pending || undefined}
      onClick={(e) => {
        e.preventDefault()
        e.stopPropagation()
        if (pending) return
        alerts.toggle(ticker, e.currentTarget)
      }}
      className={cx(
        'inline-flex flex-none items-center justify-center rounded-lg transition-colors duration-fast',
        'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
        size === 'sm' ? 'h-7 w-7' : 'h-11 w-11',
        // Its own toggle in flight (aria-disabled) fades the glyph's ink, not the element: an element
        // opacity would fade the focus ring the focusable bell still shows (DESIGN_SYSTEM §4).
        on
          ? 'bg-brand-weak text-brand-strong aria-disabled:text-brand-strong/60 dark:bg-brand-weak-dark dark:text-brand-strong-dark dark:aria-disabled:text-brand-strong-dark/60'
          : 'text-text-tertiary-light hover:bg-brand-weak hover:text-brand-strong aria-disabled:text-text-tertiary-light/60 dark:text-text-secondary-dark dark:hover:bg-brand-weak-dark dark:hover:text-brand-strong-dark dark:aria-disabled:text-text-secondary-dark/60',
        // `checking` is natively disabled, so the bell cannot hold focus then and keeps the element fade.
        'disabled:cursor-progress disabled:opacity-60 aria-disabled:cursor-progress',
        className,
      )}
    >
      <BellIcon weight={on ? 'fill' : 'regular'} className={size === 'sm' ? 'h-4 w-4' : 'h-[18px] w-[18px]'} />
    </button>
  )
}

/** The popover's inset from the viewport's edges and its gap from the bell, in px. */
export const POPOVER_MARGIN = 12
const POPOVER_GAP = 8
/** The least height a side must offer before the popover takes it, in rem of the reader's text (96px at the default
    size, 192px at 200%). The panel's padding is 2rem and a line of its text about 1.4rem, so a shorter side shows
    little more than its title: when neither side offers it, the popover spans the visible height, over the bell,
    and scrolls inside, the most of its message a short visible area can show. */
export const POPOVER_MIN_SIDE_REM = 6

type PopoverBox = { left: number; top: number; maxHeight: number }
/** The visible part of the viewport, in the coordinates a fixed box and getBoundingClientRect share. */
export type VisibleArea = { left: number; top: number; width: number; height: number }

/**
 * Where the popover goes, from its measured size and the visible area's: centred on the bell and kept
 * inside the margins; below the bell when it fits there whole, above it when only that side holds it,
 * otherwise on the roomier side with its height capped to that side (the panel scrolls inside). When
 * neither side offers `minSide` (POPOVER_MIN_SIDE_REM of the reader's text, in px), it spans the area's
 * height, over the bell. Never past the visible area.
 */
export function placeBellPopover(
  anchor: Pick<DOMRect, 'left' | 'top' | 'bottom' | 'width'>,
  size: { width: number; height: number },
  area: VisibleArea,
  minSide = POPOVER_MIN_SIDE_REM * 16,
): PopoverBox {
  const left = Math.max(
    area.left + POPOVER_MARGIN,
    Math.min(anchor.left + anchor.width / 2 - size.width / 2, area.left + area.width - size.width - POPOVER_MARGIN),
  )
  const top = area.top + POPOVER_MARGIN
  const bottom = area.top + area.height - POPOVER_MARGIN
  // The bell's edges, held inside the area: a bell out of view (an error that lands after a scroll, or
  // a page wider than the phone) still leaves the popover where the reader can see it.
  const belowStart = Math.min(Math.max(anchor.bottom + POPOVER_GAP, top), bottom)
  const aboveEnd = Math.max(Math.min(anchor.top - POPOVER_GAP, bottom), top)
  const below = bottom - belowStart
  const above = aboveEnd - top
  if (size.height <= below) return { left, top: belowStart, maxHeight: below }
  // Above, the cap is its own height: should its text grow, it scrolls rather than reach over the bell.
  if (size.height <= above) return { left, top: aboveEnd - size.height, maxHeight: size.height }
  if (Math.max(below, above) < minSide) return { left, top, maxHeight: bottom - top }
  return below >= above ? { left, top: belowStart, maxHeight: below } : { left, top, maxHeight: above }
}

/** What the reader can see. Not window.inner*: on a phone whose page is wider than the screen, Chromium
    widens the layout viewport (and window.innerWidth/innerHeight) to the page and shows only part of it,
    so a box placed in the layout viewport's bounds can sit off screen. */
function visibleArea(): VisibleArea {
  const vv = window.visualViewport
  if (vv && vv.width > 0 && vv.height > 0) return { left: vv.offsetLeft, top: vv.offsetTop, width: vv.width, height: vv.height }
  const root = document.documentElement
  return { left: 0, top: 0, width: root.clientWidth || window.innerWidth, height: root.clientHeight || window.innerHeight }
}

/** The reader's rem in px: the root's font size, which the browser's own text size sets. */
function rootRem() {
  return parseFloat(getComputedStyle(document.documentElement).fontSize) || 16
}

/** 18.75rem (300px at the default text size): it grows with the text, within the visible area's margins. */
function popoverWidth(area: VisibleArea) {
  return Math.min(18.75 * rootRem(), area.width - 2 * POPOVER_MARGIN)
}

/** Scrolls the capped panel, and only it, the least distance that shows its focused action whole inside the
    panel's scroll padding, so the action and its ring are in view. The page never scrolls: a fixed popover
    would stay where it is while its bell moved, and a scroll that moves the bell closes the popover. */
function revealFocusIn(panel: HTMLElement) {
  const active = document.activeElement
  if (!(active instanceof HTMLElement) || active === panel || !panel.contains(active)) return
  const style = getComputedStyle(panel)
  const box = panel.getBoundingClientRect()
  const r = active.getBoundingClientRect()
  const top = box.top + panel.clientTop + (parseFloat(style.scrollPaddingTop) || 0)
  const bottom = box.top + panel.clientTop + panel.clientHeight - (parseFloat(style.scrollPaddingBottom) || 0)
  if (r.bottom > bottom) panel.scrollTop += Math.min(r.bottom - bottom, r.top - top)
  else if (r.top < top) panel.scrollTop -= top - r.top
}

/** One popover per page, anchored to the bell that raised `blocked`. */
export function BellPopover({
  blocked,
  accessMode = DEFAULT_ACCESS_MODE,
  onClose,
}: {
  blocked: BlockedState
  /** The registration mode (resolveAccessMode): the signed-out prompt's account action. Fails closed to the invite. */
  accessMode?: AccessMode
  onClose: () => void
}) {
  const ref = useRef<HTMLDivElement>(null)
  const titleId = useId()
  const bodyId = useId()
  const onCloseRef = useRef(onClose)
  useEffect(() => {
    onCloseRef.current = onClose
  }, [onClose])
  // Resolved ONCE per popover: while a native <dialog> is open the popover renders inside it — the
  // top layer would otherwise paint over a <body> portal and make it inert — including a failed
  // toggle whose error arrives after the user opened a day, from a bell outside the dialog. Picking
  // the host on every render would re-mount the portal (stale refs, focus lost) if the dialog went.
  const host = useMemo(
    () => blocked.trigger?.closest('dialog[open]') ?? document.querySelector('dialog[open]') ?? document.body,
    [blocked],
  )

  useEffect(() => {
    const popover = ref.current
    const trigger = blocked.trigger
    // Focus is "free" when nobody else claimed it: an async result must not yank a user who moved on
    // (the error kind's alert announces it instead). Body focus is also free if the trigger lost focus.
    const free = (el: Element | null) => !el || el === document.body || el === trigger || !!popover?.contains(el)
    const actions = () => Array.from(popover?.querySelectorAll<HTMLElement>('a[href], button') ?? [])
    if (free(document.activeElement)) actions()[0]?.focus({ preventScroll: true })
    if (popover) revealFocusIn(popover)

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        // An async bell error can mount behind an already-open ui/Modal without taking focus.
        // Both listen on window capture; yield to that upper panel so one Escape closes one layer.
        if (e.target instanceof Element && e.target.closest('[data-ui-modal="true"]')) return
        e.preventDefault()
        e.stopPropagation()
        onCloseRef.current()
        return
      }
      if (e.key !== 'Tab' || !trigger) return
      const items = actions()
      const active = document.activeElement
      // The panel itself takes focus when its text is clicked; Shift+Tab from there leaves too.
      const leaving = e.shiftKey ? active === items[0] || active === popover : active === items[items.length - 1]
      if (!leaving) return
      // Leaving the popover: Shift+Tab lands on the bell; Tab focuses the bell and lets the
      // browser's own Tab move past it, so the page's order resumes where the user was.
      e.stopPropagation()
      if (e.shiftKey) e.preventDefault()
      trigger.focus()
      onCloseRef.current()
    }
    // Fixed at the bell's rect, the popover would detach from it once a scroll moves the bell (a
    // wheel goes straight through the catcher), so it closes then, as CitationChip's does. Scroll
    // does not bubble: capture catches any scroller, the day dialog's list included. A scroll that
    // leaves the bell in place keeps it open — the page behind the fixed day dialog, or a smooth
    // scroll from before the popover opened whose events arrive a frame late.
    const origin = trigger?.getBoundingClientRect()
    const onScroll = (e: Event) => {
      if (e.target instanceof Node && popover?.contains(e.target)) return
      const now = trigger?.getBoundingClientRect()
      if (origin && now && Math.abs(now.top - origin.top) < 1 && Math.abs(now.left - origin.left) < 1) return
      onCloseRef.current()
    }
    const dismiss = () => onCloseRef.current()
    // A popover living in a day dialog goes with it: a close request that is not a key (the Android
    // back gesture fires `cancel` on the dialog) would otherwise leave it in a detached host,
    // invisible, still holding Escape.
    const hostDialog = host.localName === 'dialog' ? host : null
    window.addEventListener('keydown', onKey, true)
    window.addEventListener('scroll', onScroll, { capture: true, passive: true })
    window.addEventListener('resize', dismiss, { passive: true })
    hostDialog?.addEventListener('cancel', dismiss)
    hostDialog?.addEventListener('close', dismiss)
    return () => {
      window.removeEventListener('keydown', onKey, true)
      window.removeEventListener('scroll', onScroll, { capture: true })
      window.removeEventListener('resize', dismiss)
      hostDialog?.removeEventListener('cancel', dismiss)
      hostDialog?.removeEventListener('close', dismiss)
      // Escape, Not now / Dismiss, the outside click and a scroll all land here with focus gone from
      // the (unmounted) popover; send it back to the bell without scrolling the page to it. A Tab
      // out already moved it on, and a user who moved on keeps their place.
      if (trigger?.isConnected && free(document.activeElement)) {
        trigger.focus({ preventScroll: true })
        // A page bell is inert under the day dialog (an error that landed after a day was opened):
        // keep focus inside the dialog, on its first control, rather than dropping it on <body>.
        if (document.activeElement !== trigger) hostDialog?.querySelector<HTMLElement>('a[href], button')?.focus({ preventScroll: true })
      }
    }
  }, [blocked, host])

  // Placed from the panel's own height, measured before paint: the first pass renders it below the bell,
  // and this moves it where it fits. Its rendered height, rounded up, or its content's full height
  // (scrollHeight and the borders) when a cap already on the panel shortens the box.
  const [box, setBox] = useState<(PopoverBox & { width: number }) | null>(null)
  useLayoutEffect(() => {
    const panel = ref.current
    if (!panel) return
    const area = visibleArea()
    const width = popoverWidth(area)
    const height = Math.max(Math.ceil(panel.getBoundingClientRect().height), panel.scrollHeight + panel.offsetHeight - panel.clientHeight)
    setBox({ width, ...placeBellPopover(blocked.anchor, { width, height }, area, POPOVER_MIN_SIDE_REM * rootRem()) })
  }, [blocked])
  // The open effect focuses the first action with preventScroll, and runs before this cap lands (React flushes
  // it ahead of the re-render the placement's setBox starts). Capped, the panel scrolls inside, and that action
  // can sit below its scrollport (the Free cap's upsell at 200% text, above its bell): once placed, the panel's
  // own scroller brings the focused action into view, ring and all.
  useLayoutEffect(() => {
    if (box && ref.current) revealFocusIn(ref.current)
  }, [box])
  const area = visibleArea()
  const width = box?.width ?? popoverWidth(area)
  const placed = box ?? placeBellPopover(blocked.anchor, { width, height: 0 }, area)

  const isError = blocked.kind === 'error'
  const title = isError
    ? 'Alert not enabled'
    : blocked.kind === 'signin'
      ? 'Sign in to set earnings alerts'
      : `Free includes ${FREE_EARNINGS_ALERT_LIMIT} earnings alerts`
  const body = isError
    ? blocked.message // the API's message, verbatim — never rewritten client-side
    : blocked.kind === 'signin'
      ? `Sign in to get an email the morning a company reports. Free includes ${FREE_EARNINGS_ALERT_LIMIT} companies.`
      : blocked.message

  return createPortal(
    <div className="fixed inset-0 z-overlay" onClick={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={ref}
        role="group"
        aria-labelledby={titleId}
        aria-describedby={bodyId}
        tabIndex={-1}
        style={{ left: placed.left, top: placed.top, width, maxHeight: box?.maxHeight }}
        className="fixed overflow-y-auto scroll-py-4 rounded-lg outline-none border border-border-light bg-panel-light p-4 shadow-e4 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
      >
        <div className="flex items-start gap-3">
          <span
            aria-hidden="true"
            className={cx(
              'flex h-8 w-8 flex-none items-center justify-center rounded-full border',
              isError
                ? 'border-error-light/25 bg-error-light/10 text-error-light dark:border-error-dark/25 dark:bg-error-dark/10 dark:text-error-dark'
                : 'border-brand-border bg-brand-weak text-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:text-brand-strong-dark',
            )}
          >
            {isError ? (
              <WarningCircleIcon className="h-4 w-4" />
            ) : blocked.kind === 'signin' ? (
              <LockSimpleIcon className="h-4 w-4" />
            ) : (
              <BellIcon className="h-4 w-4" />
            )}
          </span>
          <div className="min-w-0 flex-1">
            {/* A failed toggle lands asynchronously, so it is also announced as an alert: focus may
                not move in (the user moved on), and when it does, the focus speech can cut the alert
                off — the group's description keeps the message reachable either way. */}
            <div role={isError ? 'alert' : undefined}>
              <p id={titleId} className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                {title}{isError && <> <span className="sr-only">for {blocked.ticker}</span></>}
              </p>
              <p id={bodyId} className="mt-0.5 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
                {body}
              </p>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2">
              {blocked.kind === 'upsell' && (
                <>
                  <Link href="/pricing" className={buttonVariants({ variant: 'primary', size: 'sm' })}>
                    Upgrade to Pro
                  </Link>
                  <Button variant="ghost" size="sm" onClick={onClose}>
                    Not now
                  </Button>
                </>
              )}
              {blocked.kind === 'signin' && (
                <>
                  <Link href="/login" className={buttonVariants({ variant: 'primary', size: 'sm' })}>
                    Sign in
                  </Link>
                  <Link href={ACCESS_COPY[accessMode].href} className={buttonVariants({ variant: 'ghost', size: 'sm' })}>
                    {ACCESS_COPY[accessMode].cta}
                  </Link>
                </>
              )}
              {isError && (
                <Button variant="secondary" size="sm" onClick={onClose}>
                  Dismiss
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>,
    host,
  )
}
