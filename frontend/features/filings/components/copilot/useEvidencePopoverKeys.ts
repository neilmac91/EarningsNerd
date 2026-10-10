'use client'

import { useCallback, useEffect, type KeyboardEvent, type RefObject } from 'react'
import { getFocusable } from './useSheetFocusTrap'

/**
 * The keyboard contract of the evidence popovers (SourceTrace's "Source detail" and CitationChip's
 * citation card). Both open on hover or focus and render through a portal at the end of <body>, so
 * the page's own tab order never reached their link: Tab from the chip went to the next chip and the
 * popover closed on blur (EN-01). This hands the keys over explicitly, the way DESIGN_SYSTEM §4's
 * Popover resumes the page's order at its trigger:
 *
 *  - Tab on the open chip moves focus to the popover's action (the EDGAR / "Open original" link);
 *  - Tab on that action closes the popover and focuses the element the page visits after the chip;
 *  - Shift+Tab on the action returns to the chip, popover kept;
 *  - Escape while the popover is open closes it alone and refocuses the chip when focus was inside
 *    it (`ownsEscape`), unless the chip already owns Escape and returns focus itself (SourceTrace).
 *    The key is taken in window capture, ahead of the copilot sheet's document-level trap and the
 *    rail's window listener, so the pane beneath stays open: one layer per press, whether focus is on
 *    the chip or on its action. lessons/frontend-top-dialog-owns-the-keyboard.md
 *
 * Focus moves between the chip and the action synchronously, so the blur that would schedule a close
 * is cancelled by the popover's own onFocus (`holdOpen` covers the ordering either way). Pointer
 * users see no change: hover still opens, leaving still closes after the short delay. The refs are
 * read only inside the handlers, never during render.
 */
interface EvidencePopoverKeysOptions {
  /** The popover is rendered. */
  open: boolean
  /** The chip. */
  triggerRef: RefObject<HTMLElement | null>
  /** The popover's root, so the scan past the chip skips the portal's own content. */
  popoverRef: RefObject<HTMLElement | null>
  /** The popover's action link, when rendered. */
  actionRef: RefObject<HTMLElement | null>
  close: () => void
  /** Cancel a pending blur close. */
  holdOpen: () => void
  ownsEscape?: boolean
}

export interface EvidencePopoverKeys {
  onTriggerKeyDown: (e: KeyboardEvent<HTMLElement>) => void
  onPopoverKeyDown: (e: KeyboardEvent<HTMLElement>) => void
}

/**
 * Focus the element the page's sequential order visits after `from`, skipping everything inside
 * `skip` (the portaled popover, which sits at the end of <body>). Document order over the trap's
 * focusable selector, rendered elements only; with nothing after `from`, focus leaves to <body> as a
 * final Tab would.
 */
export function focusNextAfter(from: HTMLElement, skip: HTMLElement | null): void {
  const order = getFocusable(document.body).filter((el) => !skip?.contains(el))
  const index = order.indexOf(from)
  const next = index >= 0 ? order[index + 1] : undefined
  if (next) next.focus()
  else from.blur()
}

export function useEvidencePopoverKeys({
  open,
  triggerRef,
  popoverRef,
  actionRef,
  close,
  holdOpen,
  ownsEscape = false,
}: EvidencePopoverKeysOptions): EvidencePopoverKeys {
  const onTriggerKeyDown = useCallback(
    (e: KeyboardEvent<HTMLElement>) => {
      if (e.key !== 'Tab' || e.shiftKey || !open) return
      const action = actionRef.current
      if (!action) return
      e.preventDefault()
      holdOpen()
      action.focus()
    },
    [open, actionRef, holdOpen],
  )
  const onPopoverKeyDown = useCallback(
    (e: KeyboardEvent<HTMLElement>) => {
      const trigger = triggerRef.current
      if (e.key === 'Tab') {
        e.preventDefault()
        if (e.shiftKey) {
          holdOpen()
          trigger?.focus()
          return
        }
        close()
        if (trigger) focusNextAfter(trigger, popoverRef.current)
      }
    },
    [triggerRef, popoverRef, close, holdOpen],
  )

  useEffect(() => {
    if (!open || !ownsEscape) return
    const onKey = (e: globalThis.KeyboardEvent) => {
      // An Escape that cancels an IME composition (a hover card over the composer) is the IME's.
      if (e.key !== 'Escape' || e.isComposing) return
      // A ui/Modal raised above the popover (UpgradeModal from the rail) shares this capture phase
      // and owns its own keys; stopping them here would close the popover under it instead.
      if (e.target instanceof Element && e.target.closest('[data-ui-modal="true"]')) return
      e.preventDefault()
      e.stopPropagation()
      // Focus first, then close: the chip's own onFocus re-opens the popover, and in one batch the
      // later close wins, so the user gets the chip back without the popover they just dismissed.
      // Focus elsewhere (a hover-opened popover over the composer) stays where it is.
      if (popoverRef.current?.contains(document.activeElement)) triggerRef.current?.focus()
      close()
    }
    window.addEventListener('keydown', onKey, true)
    return () => window.removeEventListener('keydown', onKey, true)
  }, [open, ownsEscape, triggerRef, popoverRef, close])

  return { onTriggerKeyDown, onPopoverKeyDown }
}
