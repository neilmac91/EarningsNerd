'use client'

import { forwardRef, useImperativeHandle, useRef, useState } from 'react'
import { Send } from 'lucide-react'

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
        // Set the DOM value synchronously so scrollHeight + caret are accurate immediately (React
        // state catches up on the next render) — avoids an rAF race / layout flicker.
        el.value = text
        el.style.height = 'auto'
        el.style.height = `${Math.min(el.scrollHeight, 120)}px`
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
    // Reset the auto-grown height after sending.
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
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
      className="border-t border-white/10 bg-slate-900 p-3"
    >
      <div className="flex items-end gap-2 rounded-xl border border-white/10 bg-slate-950/60 p-2 focus-within:border-mint-500/50">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            // Auto-grow up to a few lines.
            const el = e.target
            el.style.height = 'auto'
            el.style.height = `${Math.min(el.scrollHeight, 120)}px`
          }}
          onKeyDown={onKeyDown}
          rows={1}
          placeholder="Ask about this filing…"
          aria-label="Ask about this filing"
          className="max-h-[120px] flex-1 resize-none bg-transparent px-1 py-1 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
        />
        <button
          type="submit"
          disabled={!canSend}
          aria-label="Send"
          className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-mint-500 text-slate-950 transition-colors hover:bg-mint-400 disabled:cursor-not-allowed disabled:bg-white/10 disabled:text-slate-500"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </form>
  )
})

export default CopilotComposer
