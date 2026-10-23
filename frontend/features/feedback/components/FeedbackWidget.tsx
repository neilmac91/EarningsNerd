'use client'

import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import { ChatCircleDotsIcon, PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalHeader, SegmentedControl, inputClasses, type SegmentedOption } from '@/components/ui'
import { submitFeedback, type FeedbackType } from '@/features/feedback/api/feedback-api'
import { hasActiveSession } from '@/lib/api/session'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { ENABLE_FEEDBACK_WIDGET } from '@/lib/featureFlags'
import { BOTTOM_CHROME_OFFSET } from '@/lib/consentLayer'

// The report's kind: one choice among options that all show, so the SegmentedControl (E35), at its `md` size and
// stretched across the form below sm, wrapping whole segments onto another row where the dialog is narrower than the
// row (a phone at 200% text, E169); from sm up it is one content-width row, as `fullWidth` documents.
const TYPES: readonly SegmentedOption<FeedbackType>[] = [
  { value: 'bug', label: 'Bug' },
  { value: 'feature', label: 'Idea' },
  { value: 'general', label: 'General' },
]

// Secondary launcher: pinned bottom-LEFT (Ask is the bottom-right hero) and clear of the iOS home
// indicator / Android nav bar and of the cookie-consent bar: BOTTOM_CHROME_OFFSET keeps a 1.25rem
// base gap on flat phones, adds the inset on notched ones (needs viewport-fit=cover, set in
// app/layout.tsx) and the bar's height while it is mounted, so this z-30 button never rises over
// the bar's "Customize" (lib/consentLayer).
const LAUNCHER_OFFSET: React.CSSProperties = {
  bottom: BOTTOM_CHROME_OFFSET,
  left: 'max(1.25rem, env(safe-area-inset-left))',
}

/**
 * Always-available beta feedback launcher. Renders a floating button for logged-in users only
 * (gated on the client-readable session marker), opening a small bug/idea/general report panel that
 * posts to /api/feedback. Mounted once in Providers so it's available across the authenticated app.
 *
 * v3 (DS-04): the report panel is a ui/Modal dialog (focus trap, Escape, focus return to the
 * launcher, overlay + z-modal tokens) instead of an anchored popover with no keyboard handling.
 */
export default function FeedbackWidget() {
  // Avoid a hydration mismatch: the session marker lives in localStorage (client-only), so we render
  // nothing on the server / first paint and decide after mount.
  const [mounted, setMounted] = useState(false)
  const [authed, setAuthed] = useState(false)
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<FeedbackType>('general')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const messageRef = useRef<HTMLTextAreaElement>(null)
  const close = () => setOpen(false)

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time hydration latch: session marker lives in localStorage, so we resolve client-only state after mount
    setMounted(true)
    setAuthed(hasActiveSession())
  }, [])

  if (!ENABLE_FEEDBACK_WIDGET || !mounted || !authed) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // Send uses `loading` (aria-disabled + click guard, not native disabled) so it keeps focus while
    // the request is in flight; a submit that bypasses its click must not send a second report.
    if (submitting) return
    if (message.trim().length < 5) return
    setSubmitting(true)
    try {
      await submitFeedback({
        type,
        message: message.trim(),
        pageUrl: typeof window !== 'undefined' ? window.location.pathname : undefined,
      })
      toast.success('Thanks for the feedback', { description: 'We read every note. It really helps.' })
      setMessage('')
      setType('general')
      setOpen(false)
    } catch (err: unknown) {
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not send feedback. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Modal open={open} onClose={close} labelledBy="feedback-dialog-title" size="sm" initialFocusRef={messageRef}>
        <ModalHeader id="feedback-dialog-title" onClose={close}>
          Send feedback
        </ModalHeader>
        <ModalBody>
          <form onSubmit={handleSubmit} className="space-y-3">
            <SegmentedControl label="Feedback type" options={TYPES} value={type} onChange={setType} size="md" fullWidth />

            <textarea
              ref={messageRef}
              aria-label="Feedback message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              rows={4}
              maxLength={4000}
              placeholder="What's working, what's broken, or what you'd love to see…"
              // The field recipe (E154): its fill, border, padding, focus ring and 44px floor; it stays a fixed four rows.
              className={inputClasses({ className: 'resize-none' })}
            />

            {/* `loading`, never native `disabled`, while sending: Chromium blurs a focused button
                that turns disabled (focus → <body>). Native `disabled` stays only for the too-short
                message — the textarea sets it, and the success reset that clears the message also
                closes this panel in the same render, so it never flips under focus. */}
            <Button
              type="submit"
              loading={submitting}
              loadingText="Sending…"
              disabled={message.trim().length < 5}
              className="w-full py-2 font-semibold active:scale-[0.99]"
            >
              <span className="flex items-center justify-center gap-2">
                <PaperPlaneTiltIcon className="h-4 w-4" />
                Send feedback
              </span>
            </Button>
          </form>
        </ModalBody>
      </Modal>

      <button
        type="button"
        aria-label={open ? 'Close feedback' : 'Send feedback'}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        style={LAUNCHER_OFFSET}
        className="fixed z-30 inline-flex min-h-[2.75rem] min-w-[2.75rem] items-center justify-center gap-2 rounded-full border border-border-light bg-panel-light px-3 py-2.5 text-xs font-medium text-text-secondary-light shadow-e2 transition-colors hover:bg-white hover:text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:shadow-none dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
      >
        <ChatCircleDotsIcon className="h-5 w-5" />
        <span className="hidden sm:inline">Feedback</span>
      </button>
    </>
  )
}
