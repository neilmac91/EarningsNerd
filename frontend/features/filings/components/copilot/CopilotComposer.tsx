'use client'

import { forwardRef, useImperativeHandle, useRef, useState } from 'react'
import { PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Textarea, cx, inputClasses } from '@/components/ui'

interface CopilotComposerProps {
  onSubmit: (question: string) => void
  disabled: boolean
}

export interface CopilotComposerHandle {
  focus: () => void
  /** Replace the input with `text`, focus, grow to fit, and put the caret at the end. */
  prefill: (text: string) => void
}

/**
 * Bottom-pinned input for the Copilot rail. Enter submits, Shift+Enter inserts a newline.
 * Send is disabled while a stream is in flight or the input is empty. Exposes `focus()` / `prefill()`
 * handles so the rail can focus it on open (⌘K) or pre-fill it from a "Ask about this" text selection.
 */
const CopilotComposer = forwardRef<CopilotComposerHandle, CopilotComposerProps>(
  function CopilotComposer({ onSubmit, disabled }, ref) {
  const [value, setValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useImperativeHandle(
    ref,
    () => ({
      focus: () => textareaRef.current?.focus(),
      prefill: (text: string) => {
        setValue(text)
        const el = textareaRef.current
        if (!el) return
        // Set the DOM value synchronously so the caret position is accurate immediately (React
        // state catches up on the next render; height comes from the controlled path — Textarea's
        // layout effect re-grows on the value change).
        el.value = text
        el.focus()
        el.setSelectionRange(text.length, text.length)
      },
    }),
    [],
  )

  const trimmed = value.trim()
  const canSend = !disabled && trimmed.length > 0

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
      className="border-t border-border-light bg-panel-light dark:border-white/10 dark:bg-panel-dark p-3"
    >
      {/* DS "Chat composer" pattern: the shell carries the field recipe + focus-within
          ring; the composer-variant Textarea inside stays chrome-free. */}
      <div
        className={cx(
          inputClasses({ className: 'flex items-end gap-2' }),
          'focus-within:border-brand focus-within:shadow-ring-brand',
          'dark:focus-within:border-brand-dark dark:focus-within:shadow-ring-brand-dark',
        )}
      >
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
        {/* Icon-only primary Button — sm height with the horizontal padding
            zeroed so it stays a square send affordance. */}
        <Button type="submit" size="sm" disabled={!canSend} aria-label="Send" className="w-8 shrink-0 px-0">
          <PaperPlaneTiltIcon className="h-4 w-4" />
        </Button>
      </div>
      <p className="mt-2 px-1 text-xs leading-snug text-text-secondary-light dark:text-text-secondary-dark">
        Avoid entering personal or confidential information — your question is sent to our AI
        provider to generate an answer.
      </p>
    </form>
  )
})

export default CopilotComposer
