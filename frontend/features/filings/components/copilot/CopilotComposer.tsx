'use client'

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Textarea, cx, inputClasses, primaryUnavailableClass } from '@/components/ui'
import { prefersReducedMotion } from '@/hooks/usePrefersReducedMotion'

interface CopilotComposerProps {
  onSubmit: (question: string) => void
  /** Send refuses while true (a stream is in flight, or no questions are left). It is aria-disabled
   *  and stays focusable, and the field stays editable. Not named `disabled`: nothing turns natively
   *  disabled. */
  locked: boolean
}

/** What a press asks of a focus handle. */
export interface ComposerFocusOptions {
  /** The press opened the pane or pre-filled it (Source, ⌘K, "/", "Ask about this"): once the pane has settled, when
   *  the shell is still not wholly in view below the site header, the page moves by the least distance that brings it
   *  there, once (E252). */
  revealOnPage?: boolean
}

export interface CopilotComposerHandle {
  /** Focus the field without moving the page, and bring the shell around it into view inside the box that scrolls it
   *  (revealInScrollBox). */
  focus: (options?: ComposerFocusOptions) => void
  /** Replace the input with `text`, focus as `focus` does, grow to fit, and put the caret at the end. */
  prefill: (text: string, options?: ComposerFocusOptions) => void
  /** When focus is in the composer (its field or Send), bring the shell that draws the focus ring around both to the
   *  nearest edge of the box that scrolls it, never the page. Nothing moves when focus is elsewhere or the shell is
   *  already in view. */
  revealFocus: () => void
}

const SCROLLS = /^(auto|scroll|hidden)$/
const px = (value: string) => parseFloat(value) || 0
/** The reader's own moves, any of which drops a page reveal still waiting for the pane to settle. */
const READER_MOVES = ['wheel', 'touchstart', 'pointerdown'] as const
/** Frames the shell and its column hold still before the pane counts as settled, and the most frames waited for it. */
const SETTLED_FRAMES = 2
const MAX_SETTLE_FRAMES = 12

/** The box that scrolls `el` (the rail's column): its nearest scrolling ancestor, never the page. */
function scrollBoxOf(el: HTMLElement): HTMLElement | null {
  let box = el.parentElement
  while (box && box !== document.body && !SCROLLS.test(getComputedStyle(box).overflowY)) box = box.parentElement
  return box === document.body ? null : box
}

/** Whether `el` sits in a fixed layer (the phone's sheet, the standalone rail), which no page scroll moves. */
function inFixedLayer(el: HTMLElement) {
  for (let node: HTMLElement | null = el; node; node = node.parentElement) {
    if (getComputedStyle(node).position === 'fixed') return true
  }
  return false
}

/** The part of the window a reveal lands in: below the bars the page's scroll padding reserves (the site header) and
 *  above the consent bar it reserves (globals.css), or the whole window in a fixed layer, which sits over both. */
function bandOf(el: HTMLElement) {
  if (inFixedLayer(el)) return { top: 0, bottom: window.innerHeight, fixed: true }
  const page = getComputedStyle(document.documentElement)
  return { top: px(page.scrollPaddingTop), bottom: window.innerHeight - px(page.scrollPaddingBottom), fixed: false }
}

/** How far to scroll so [top, bottom] holds [from, to] at its nearest edge, the least distance, or holds its top when it
 *  is the taller: 0 when it already holds it. */
function toNearestEdge(from: number, to: number, top: number, bottom: number) {
  if (to > bottom) return Math.min(to - bottom, from - top)
  if (from < top) return from - top
  return 0
}

/** `el`'s extent in the window, its scroll margins included. */
function marginBox(el: HTMLElement) {
  const style = getComputedStyle(el)
  const r = el.getBoundingClientRect()
  return { from: r.top - px(style.scrollMarginTop), to: r.bottom + px(style.scrollMarginBottom) }
}

/** How far `box` scrolls to bring `el`, its scroll margins included, to the nearest edge of the part of `box` on screen
 *  (below the site header, above the fold and the consent bar), the least distance: 0 when `el` is in view there. When
 *  `el` does not fit there (nothing of `box` is on screen, or too little), the nearest edge of `box` itself, and the
 *  page's reveal after a press brings it on screen. Chief design on #1845: "The column's reveal aims at its visible
 *  part: its box clipped to the window, below the site header, not its whole box." */
function distanceToReveal(el: HTMLElement, box: HTMLElement) {
  const style = getComputedStyle(box)
  const b = box.getBoundingClientRect()
  const top = b.top + box.clientTop + px(style.scrollPaddingTop)
  const bottom = b.top + box.clientTop + box.clientHeight - px(style.scrollPaddingBottom)
  const { from, to } = marginBox(el)
  const band = bandOf(box)
  const shownTop = Math.max(top, band.top)
  const shownBottom = Math.min(bottom, band.bottom)
  return shownBottom - shownTop >= to - from
    ? toNearestEdge(from, to, shownTop, shownBottom)
    : toNearestEdge(from, to, top, bottom)
}

/**
 * Brings `el` to the nearest edge of the box that scrolls it, the least distance, and scrolls nothing else: not the
 * boxes around that box, and never the page. A focus's own scroll and scrollIntoView move every scrolling ancestor. The
 * desktop pane's height follows its top a frame late, so after the page above it moves its lower part can sit below the
 * fold, and focusing the composer then moved the page under the reader (E248; chief design on #1813: "A press on Source
 * should never move the page under the reader"). Instant, as that scroll was.
 */
function revealInScrollBox(el: HTMLElement, box = scrollBoxOf(el)) {
  const by = box ? distanceToReveal(el, box) : 0
  if (box && by) box.scrollTop += by
  return box
}

/**
 * The one page move a press makes (E252), once its pane has settled and the column has had its own reveal: when `el`,
 * its scroll margins included, is still not wholly in view below the site header, the page moves by the least distance
 * that brings it there. At the foot of a long page under 200% text the pane's sticky cell has scrolled up with the
 * workspace's end, and in a short window at the page's top the pane opens below the fold: either way focus would land in
 * a composer the reader cannot see. Not in a fixed layer, which no page scroll moves. Smooth, or one jump under
 * prefers-reduced-motion, as a citation jump's scroll is. Chief design on #1845: "Move it once per press or ⌘K. Never
 * move it from a resize or the follow."
 */
function revealOnPage(el: HTMLElement, box: HTMLElement) {
  const band = bandOf(box)
  if (band.fixed) return
  const { from, to } = marginBox(el)
  const by = toNearestEdge(from, to, band.top, band.bottom)
  if (by) window.scrollBy({ top: by, behavior: prefersReducedMotion() ? 'auto' : 'smooth' })
}

/**
 * Bottom-pinned input for the Copilot rail. Enter submits, Shift+Enter inserts a newline.
 * Send is unavailable (aria-disabled, still focusable) while a stream is in flight or the input is
 * empty. Exposes `focus()` / `prefill()` handles so the rail can focus it on open (⌘K) or pre-fill
 * it from a "Ask about this" text selection; neither moves the page while the pane settles
 * (revealInScrollBox), a focused composer that stood in view stays in view as its column settles,
 * and a press that opened the pane may move the page once it has settled (revealOnPage).
 */
const CopilotComposer = forwardRef<CopilotComposerHandle, CopilotComposerProps>(
  function CopilotComposer({ onSubmit, locked }, ref) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const shellRef = useRef<HTMLDivElement>(null)
  // Whether the shell follows its box as the box or the shell changes size (the effect below), and the scrollTop the
  // composer's own reveal last left the box at.
  const followRef = useRef(true)
  const placedRef = useRef<number | null>(null)
  // A press's page reveal, waiting for the pane to settle; calling it drops the wait.
  const settlingRef = useRef<(() => void) | null>(null)

  useImperativeHandle(ref, () => {
    const reveal = () => {
      if (!shellRef.current) return null
      const box = revealInScrollBox(shellRef.current)
      if (box) placedRef.current = box.scrollTop
      followRef.current = true
      return box
    }
    // Once the shell and its column hold still for SETTLED_FRAMES frames (the pane's height catches up with its top a
    // frame late, a pre-fill grows the field, the column follows), or after MAX_SETTLE_FRAMES: the column's reveal
    // again, then the page's. A newer press, the reader's own move or focus leaving the composer drops it.
    const revealOnPageOnceSettled = () => {
      settlingRef.current?.()
      const shell = shellRef.current
      const box = shell && scrollBoxOf(shell)
      if (!shell || !box) return
      let raf = 0
      let frames = 0
      let still = 0
      let last = ''
      const drop = () => {
        cancelAnimationFrame(raf)
        for (const type of READER_MOVES) window.removeEventListener(type, drop, true)
        if (settlingRef.current === drop) settlingRef.current = null
      }
      const tick = () => {
        const s = shell.getBoundingClientRect()
        const b = box.getBoundingClientRect()
        const now = `${s.top} ${s.bottom} ${b.top} ${b.bottom}`
        still = now === last ? still + 1 : 0
        last = now
        if (still < SETTLED_FRAMES && ++frames < MAX_SETTLE_FRAMES) {
          raf = requestAnimationFrame(tick)
          return
        }
        drop()
        if (!shell.contains(document.activeElement)) return
        reveal()
        revealOnPage(shell, box)
      }
      for (const type of READER_MOVES) window.addEventListener(type, drop, { capture: true, passive: true })
      raf = requestAnimationFrame(tick)
      settlingRef.current = drop
    }
    // preventScroll, then the shell (the ring's box, as revealFocus brings) into view inside its column: the page stays
    // while the pane settles.
    const focusField = (el: HTMLTextAreaElement, options?: ComposerFocusOptions) => {
      el.focus({ preventScroll: true })
      reveal()
      if (options?.revealOnPage) revealOnPageOnceSettled()
    }
    return {
      focus: (options) => {
        if (textareaRef.current) focusField(textareaRef.current, options)
      },
      prefill: (text, options) => {
        setValue(text)
        const el = textareaRef.current
        if (!el) return
        // Set the DOM value synchronously so the caret position is accurate immediately (React
        // state catches up on the next render; height comes from the controlled path — Textarea's
        // layout effect re-grows on the value change).
        el.value = text
        focusField(el, options)
        el.setSelectionRange(text.length, text.length)
        // The caret at the end, in view inside the field's own scroll (its 120px cap): a focus without the browser's
        // scroll leaves a long excerpt showing its start.
        el.scrollTop = el.scrollHeight
      },
      revealFocus: () => {
        if (shellRef.current?.contains(document.activeElement)) reveal()
      },
    }
  }, [])

  // A page reveal still waiting when the composer leaves goes with it.
  useEffect(() => () => settlingRef.current?.(), [])

  // The box and the shell can still change size under a focused composer: the desktop pane's height follows its top a
  // frame late, the text size or the consent bar can shrink it later, and a pre-fill grows the field after it takes
  // focus. While the shell follows, each change brings it back to the box's nearest edge if focus is in the composer.
  // A reveal starts the follow, and so do the reader's scroll and focus moving in, once the shell is in view; the
  // reader's scroll that takes it out of view stops it, and a resize never starts it again: the reader's place is theirs.
  // The follow scrolls the column only, never the page.
  useEffect(() => {
    const shell = shellRef.current
    const box = shell && scrollBoxOf(shell)
    if (!shell || !box || typeof ResizeObserver === 'undefined') return
    const inView = () => Math.abs(distanceToReveal(shell, box)) < 1
    // A reveal's own scroll is reported a frame late, and a pre-fill can grow the field before it is: a scroll to where
    // the composer left the box is that reveal's, and keeps the follow.
    const onScroll = () => {
      const placed = placedRef.current
      followRef.current = (placed !== null && Math.abs(box.scrollTop - placed) < 1) || inView()
    }
    const onFocusIn = () => {
      if (inView()) followRef.current = true
    }
    const observer = new ResizeObserver(() => {
      if (!followRef.current || !shell.contains(document.activeElement)) return
      revealInScrollBox(shell, box)
      placedRef.current = box.scrollTop
    })
    observer.observe(box)
    observer.observe(shell)
    box.addEventListener('scroll', onScroll, { passive: true })
    shell.addEventListener('focusin', onFocusIn)
    return () => {
      observer.disconnect()
      box.removeEventListener('scroll', onScroll)
      shell.removeEventListener('focusin', onFocusIn)
    }
  }, [])

  const trimmed = value.trim()
  const canSend = !locked && trimmed.length > 0

  const submit = () => {
    if (!canSend) return
    onSubmit(trimmed)
    setValue('')
  }

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Don't submit while an IME is composing (CJK input): Enter confirms the candidate, not send.
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      submit()
    }
  }

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault()
        submit()
      }}
      // px-4: the rail's own 16px inset (its header, messages and notes), so on a phone the sheet's
      // composer and privacy note keep the page's 16px gutter instead of 12px plus the sheet's border.
      className="border-t border-border-light bg-panel-light dark:border-white/10 dark:bg-panel-dark px-4 py-3"
    >
      {/* DS "Chat composer" pattern: the shell carries the field recipe, its focus
          border and ring keyed to focus-within (`shell: true`); the composer-variant
          Textarea inside stays chrome-free. scroll-my-1 keeps the 3px ring in view at the edge
          a reveal brings the shell to: the column's foot, where the rail's reveal lands (its
          column has just returned to the top), or, when a press moves the page (revealOnPage),
          the top of the window below the site header. The ring's room only: the page's scroll
          padding holds the header's height, which no scroll margin here adds again. */}
      <div ref={shellRef} className={inputClasses({ shell: true, className: 'flex items-end gap-2 scroll-my-1' })}>
        <Textarea
          variant="composer"
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about this filing…"
          aria-label="Ask about this filing"
          // className styles the shell wrapper (a flex item), not the <textarea>;
          // the height cap must ride `style`, which spreads onto the element.
          className="min-w-0 flex-1"
          style={{ maxHeight: 120, overflowY: 'auto' }}
        />
        {/* Icon-only primary Button — the first-class icon size (a zero-padding className
            override on `sm` loses the stylesheet-order conflict and crushes the glyph).
            aria-disabled, never native `disabled`: pressing Send itself starts the stream and clears
            the input, and Chromium blurs a focused button that turns disabled (focus → <body>).
            submit()'s `canSend` early return is the guard for both click and Enter. */}
        <Button
          type="submit"
          size="icon-sm"
          aria-disabled={!canSend || undefined}
          aria-label="Send"
          className={cx('shrink-0', primaryUnavailableClass)}
        >
          <PaperPlaneTiltIcon className="h-4 w-4" />
        </Button>
      </div>
      <p className="mt-2 px-1 text-xs leading-snug text-text-secondary-light dark:text-text-secondary-dark">
        Avoid entering personal or confidential information. Your question is sent to our AI
        provider to generate an answer.
      </p>
    </form>
  )
})

export default CopilotComposer
