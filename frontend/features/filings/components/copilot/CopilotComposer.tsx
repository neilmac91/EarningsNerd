'use client'

import { forwardRef, useImperativeHandle, useRef, useState, type RefObject } from 'react'
import { PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Textarea, cx, inputClasses, primaryUnavailableClass } from '@/components/ui'

interface CopilotComposerProps {
  onSubmit: (question: string) => void
  /** Send refuses while true (a stream is in flight, or no questions are left). It is aria-disabled
   *  and stays focusable, and the field stays editable. Not named `disabled`: nothing turns natively
   *  disabled. */
  locked: boolean
  /** The box that scrolls the composer: the rail's column. The composer's focus and its reveal move this box alone,
   *  never the page; without it they move nothing. */
  scrollerRef?: RefObject<HTMLElement | null>
}

export interface CopilotComposerHandle {
  /** Focus the field without scrolling the page, then reveal it as `revealFocus` does. */
  focus: () => void
  /** Replace the input with `text`, focus as `focus` does, grow to fit, and put the caret at the end. */
  prefill: (text: string) => void
  /** When focus is in the composer (its field or Send), scroll the shell that draws the focus ring around both to
   *  the nearest edge of the box that scrolls it (`scrollerRef`), and nothing else. Nothing moves when focus is
   *  elsewhere or the shell is already in view. */
  revealFocus: () => void
}

/**
 * Bring `el` to the nearest edge of `box`, which scrolls it, keeping `el`'s scroll margins, and move `box` alone. A
 * press on Source should never move the page under the reader (chief design on #1813). focus() and scrollIntoView
 * scroll every box around their element, the page included, so a frame in which the opening pane's composer lay
 * below the window scrolled the page down to it (E248). The nearest edge is the one scrollIntoView's
 * `block: 'nearest'` picks, except that the top wins where `el` is taller than `box`.
 */
function revealInside(box: HTMLElement, el: HTMLElement): void {
  const top = box.getBoundingClientRect().top + box.clientTop
  const rect = el.getBoundingClientRect()
  const style = getComputedStyle(el)
  const above = top - (rect.top - (parseFloat(style.scrollMarginTop) || 0))
  const below = rect.bottom + (parseFloat(style.scrollMarginBottom) || 0) - (top + box.clientHeight)
  if (above > 0) box.scrollTop -= above
  else if (below > 0) box.scrollTop += Math.min(below, -above)
}

/**
 * Bottom-pinned input for the Copilot rail. Enter submits, Shift+Enter inserts a newline.
 * Send is unavailable (aria-disabled, still focusable) while a stream is in flight or the input is
 * empty. Exposes `focus()` / `prefill()` handles so the rail can focus it on open (⌘K) or pre-fill
 * it from a "Ask about this" text selection. Neither scrolls the page: each moves only the rail's
 * column, where the composer would otherwise be focused out of view.
 */
const CopilotComposer = forwardRef<CopilotComposerHandle, CopilotComposerProps>(
  function CopilotComposer({ onSubmit, locked, scrollerRef }, ref) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const shellRef = useRef<HTMLDivElement>(null)

  useImperativeHandle(
    ref,
    () => {
      const revealFocus = () => {
        const shell = shellRef.current
        const box = scrollerRef?.current
        if (shell && box && shell.contains(document.activeElement)) revealInside(box, shell)
      }
      return {
        focus: () => {
          textareaRef.current?.focus({ preventScroll: true })
          revealFocus()
        },
        prefill: (text: string) => {
          setValue(text)
          const el = textareaRef.current
          if (!el) return
          // Set the DOM value synchronously so the caret position is accurate immediately (React
          // state catches up on the next render; height comes from the controlled path — Textarea's
          // layout effect re-grows on the value change).
          el.value = text
          el.focus({ preventScroll: true })
          el.setSelectionRange(text.length, text.length)
          revealFocus()
        },
        revealFocus,
      }
    },
    [scrollerRef],
  )

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
          Textarea inside stays chrome-free. scroll-mb-1 keeps the 3px ring in view when
          revealFocus brings the shell to the bottom edge, where the rail's reveal lands (its
          column has just returned to the top); a top scroll margin here would read as a
          site-header offset, which is what this codebase's top scroll margins are. */}
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
