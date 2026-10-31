'use client'

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react'
import { PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Textarea, cx, inputClasses, primaryUnavailableClass } from '@/components/ui'

interface CopilotComposerProps {
  onSubmit: (question: string) => void
  /** Send refuses while true (a stream is in flight, or no questions are left). It is aria-disabled
   *  and stays focusable, and the field stays editable. Not named `disabled`: nothing turns natively
   *  disabled. */
  locked: boolean
}

export interface CopilotComposerHandle {
  /** Focus the field without moving the page, and bring the shell around it into view inside the box that scrolls
   *  it (revealInScrollBox). */
  focus: () => void
  /** Replace the input with `text`, focus as `focus` does, grow to fit, and put the caret at the end. */
  prefill: (text: string) => void
  /** When focus is in the composer (its field or Send), bring the shell that draws the focus ring around both to the
   *  nearest edge of the box that scrolls it, never the page. Nothing moves when focus is elsewhere or the shell is
   *  already in view. */
  revealFocus: () => void
}

const SCROLLS = /^(auto|scroll|hidden)$/

/** The box that scrolls `el` (the rail's column): its nearest scrolling ancestor, never the page. */
function scrollBoxOf(el: HTMLElement): HTMLElement | null {
  let box = el.parentElement
  while (box && box !== document.body && !SCROLLS.test(getComputedStyle(box).overflowY)) box = box.parentElement
  return box === document.body ? null : box
}

/** How far `box` scrolls to bring `el`, its scroll margin included, to its nearest edge, the least distance: 0 when `el`
 *  is in view. */
function distanceToReveal(el: HTMLElement, box: HTMLElement) {
  const boxStyle = getComputedStyle(box)
  const elStyle = getComputedStyle(el)
  const b = box.getBoundingClientRect()
  const r = el.getBoundingClientRect()
  const top = b.top + box.clientTop + (parseFloat(boxStyle.scrollPaddingTop) || 0)
  const bottom = b.top + box.clientTop + box.clientHeight - (parseFloat(boxStyle.scrollPaddingBottom) || 0)
  const elTop = r.top - (parseFloat(elStyle.scrollMarginTop) || 0)
  const elBottom = r.bottom + (parseFloat(elStyle.scrollMarginBottom) || 0)
  if (elBottom > bottom) return Math.min(elBottom - bottom, elTop - top)
  if (elTop < top) return elTop - top
  return 0
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
 * Bottom-pinned input for the Copilot rail. Enter submits, Shift+Enter inserts a newline.
 * Send is unavailable (aria-disabled, still focusable) while a stream is in flight or the input is
 * empty. Exposes `focus()` / `prefill()` handles so the rail can focus it on open (⌘K) or pre-fill
 * it from a "Ask about this" text selection; neither moves the page (revealInScrollBox), and a
 * focused composer that stood in view stays in view as its column settles.
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

  useImperativeHandle(ref, () => {
    const reveal = () => {
      if (!shellRef.current) return
      const box = revealInScrollBox(shellRef.current)
      if (box) placedRef.current = box.scrollTop
      followRef.current = true
    }
    // preventScroll, then the shell (the ring's box, as revealFocus brings) into view inside its column: the page stays.
    const focusField = (el: HTMLTextAreaElement) => {
      el.focus({ preventScroll: true })
      reveal()
    }
    return {
      focus: () => {
        if (textareaRef.current) focusField(textareaRef.current)
      },
      prefill: (text: string) => {
        setValue(text)
        const el = textareaRef.current
        if (!el) return
        // Set the DOM value synchronously so the caret position is accurate immediately (React
        // state catches up on the next render; height comes from the controlled path — Textarea's
        // layout effect re-grows on the value change).
        el.value = text
        focusField(el)
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

  // The box and the shell can still change size under a focused composer: the desktop pane's height follows its top a
  // frame late, the text size or the consent bar can shrink it later, and a pre-fill grows the field after it takes
  // focus. While the shell follows, each change brings it back to the box's nearest edge if focus is in the composer.
  // A reveal starts the follow, and so do the reader's scroll and focus moving in, once the shell is in view; the
  // reader's scroll that takes it out of view stops it, and a resize never starts it again: the reader's place is theirs.
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
          Textarea inside stays chrome-free. scroll-mb-1 keeps the 3px ring in view when the
          reveal (on focus, a pre-fill or revealFocus) brings the shell to the bottom edge, where
          the rail's reveal lands (its column has just returned to the top); a top scroll margin
          here would read as a site-header offset, which is what this codebase's top scroll
          margins are. */}
      <div ref={shellRef} className={inputClasses({ shell: true, className: 'flex items-end gap-2 scroll-mb-1' })}>
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
