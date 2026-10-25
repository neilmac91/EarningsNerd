'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChatCircleDotsIcon, PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalHeader, SegmentedControl, inputClasses, type SegmentedOption } from '@/components/ui'
import { submitFeedback, type FeedbackType } from '@/features/feedback/api/feedback-api'
import { getCurrentUserSafe, type CurrentUser } from '@/features/auth/api/auth-api'
import { getSessionGeneration, isSessionGenerationCurrent } from '@/lib/api/session'
import { queryKeys } from '@/lib/queryKeys'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { ENABLE_FEEDBACK_WIDGET } from '@/lib/featureFlags'
import { BOTTOM_CHROME_OFFSET } from '@/lib/consentLayer'

// The report's kind: one choice among options that all show, so the SegmentedControl (E35), at its `md` size and
// stretched across the form below 40rem (1280px under 200% text), wrapping whole segments onto another row where the
// dialog is narrower than the row (a phone at 200% text, E169); from 40rem up it is one content-width row, as
// `fullWidth` documents (E183).
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
 * (observing the shared current-user query), opening a small bug/idea/general report panel that
 * posts to /api/feedback. Mounted once in Providers so it's available across the authenticated app.
 *
 * v3 (DS-04): the report panel is a ui/Modal dialog (focus trap, Escape, focus return to the
 * launcher, overlay + z-modal tokens) instead of an anchored popover with no keyboard handling.
 */
export default function FeedbackWidget() {
  const { data: user } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    enabled: ENABLE_FEEDBACK_WIDGET,
    staleTime: 60_000,
  })

  // Undefined is an unresolved identity, not a guest. Retained identity survives a failed
  // background read; confirmed logout or a different reader unmounts the private draft.
  if (!ENABLE_FEEDBACK_WIDGET || !user) return null
  return <AccountFeedback key={user.id} readerId={user.id} />
}

function AccountFeedback({ readerId }: { readerId: number }) {
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [type, setType] = useState<FeedbackType>('general')
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const inFlight = useRef(false)
  const mounted = useRef(false)
  const messageRef = useRef<HTMLTextAreaElement>(null)
  const close = () => setOpen(false)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // Send uses `loading` (aria-disabled + click guard, not native disabled) so it keeps focus while
    // the request is in flight; a submit that bypasses its click must not send a second report.
    if (inFlight.current) return
    if (message.trim().length < 5) return
    // Read ownership at activation as well as completion: a cache transition may have happened
    // before React renders the new reader. The generation also catches A → logout → A.
    const generation = getSessionGeneration()
    const ownsFeedback = () => mounted.current
      && isSessionGenerationCurrent(generation)
      && queryClient.getQueryData<CurrentUser | null>(queryKeys.currentUser())?.id === readerId
    if (!ownsFeedback()) return
    inFlight.current = true
    setSubmitting(true)
    try {
      await submitFeedback({
        type,
        message: message.trim(),
        pageUrl: typeof window !== 'undefined' ? window.location.pathname : undefined,
      })
      if (!ownsFeedback()) return
      toast.success('Thanks for the feedback', { description: 'We read every note. It really helps.' })
      setMessage('')
      setType('general')
      setOpen(false)
    } catch (err: unknown) {
      if (!ownsFeedback()) return
      toast.error(isApiError(err) ? getErrorMessage(err) : 'Could not send feedback. Please try again.')
    } finally {
      inFlight.current = false
      // A failed logout can retain the same reader after moving the generation. Release this
      // form's busy state without publishing its old result or discarding the retained draft.
      if (mounted.current) setSubmitting(false)
    }
  }

  return (
    <>
      <Modal open={open} onClose={close} labelledBy="feedback-dialog-title" size="sm" initialFocusRef={messageRef} className="ph-no-capture">
        <ModalHeader id="feedback-dialog-title" onClose={close}>
          Send feedback
        </ModalHeader>
        <ModalBody>
          <form onSubmit={handleSubmit} className="space-y-3">
            <SegmentedControl label="Feedback type" options={TYPES} value={type} onChange={setType} size="md" fullWidth />

            <textarea
              ref={messageRef}
              aria-label="Feedback message"
              aria-describedby="feedback-message-help"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              rows={4}
              maxLength={4000}
              placeholder="What's working, what's broken, or what you'd love to see…"
              // The field recipe (E154): its fill, border, padding, focus ring and 44px floor; it stays a fixed four rows.
              className={inputClasses({ className: 'resize-none' })}
            />
            <p id="feedback-message-help" className="text-xs text-text-secondary-light dark:text-text-secondary-dark">
              Describe what happened. You can paste a web link here too.
            </p>

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
