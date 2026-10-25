'use client'

import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ChatCircleDotsIcon, PaperPlaneTiltIcon } from '@/lib/icons'
import { Button, Modal, ModalBody, ModalHeader, SegmentedControl, cx, inputClasses, type SegmentedOption } from '@/components/ui'
import { submitFeedback, type FeedbackType } from '@/features/feedback/api/feedback-api'
import { getCurrentUserSafe, type CurrentUser } from '@/features/auth/api/auth-api'
import { getSessionGeneration, isSessionGenerationCurrent } from '@/lib/api/session'
import { queryKeys } from '@/lib/queryKeys'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { ENABLE_FEEDBACK_WIDGET } from '@/lib/featureFlags'
import { BOTTOM_CHROME_OFFSET, CONSENT_LAYER_EVENT } from '@/lib/consentLayer'
import { overlapsKeepClear } from '@/lib/launcherKeepClear'

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

// The launcher's one fixed site (tests/unit/bottomChromeLadder.spec.ts pins it at z-30). Its colour and opacity changes
// take the fast motion token, and none runs under reduced motion (DESIGN_SYSTEM §11).
const LAUNCHER_CLASS =
  'fixed z-30 inline-flex min-h-[2.75rem] min-w-[2.75rem] items-center justify-center gap-2 rounded-full border border-border-light bg-panel-light px-3 py-2.5 text-xs font-medium text-text-secondary-light shadow-e2 transition-[color,background-color,opacity] duration-fast motion-reduce:transition-none hover:bg-white hover:text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:shadow-none dark:hover:bg-white/5 dark:hover:text-text-primary-dark'

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
  const launcherRef = useRef<HTMLButtonElement>(null)
  // N17: the launcher never rests over a headline figure. While a region the page marks keep-clear (the analysis KPI
  // strip) lies under its box (lib/launcherKeepClear), it steps aside without moving: it fades and lets the pointer
  // through to the figure, keyboard focus brings it back, and it never yields while its own dialog is open.
  const [yielding, setYielding] = useState(false)
  const close = () => setOpen(false)

  useEffect(() => {
    mounted.current = true
    return () => { mounted.current = false }
  }, [])

  // One check a frame at most, the requestAnimationFrame throttle DataTable's heading rail also uses, queued on a passive
  // scroll, a resize, the consent bar coming or going (the launcher rises with it) and a change of the page's size
  // (results mount after Run with no scroll). jsdom has no ResizeObserver of its own, hence the guard. This component mounts only for a reader the
  // current-user query confirms, so the measurement runs for as long as the launcher shows.
  useEffect(() => {
    let frame = 0
    const check = () => {
      frame = 0
      const box = launcherRef.current?.getBoundingClientRect()
      setYielding(!!box && overlapsKeepClear(box))
    }
    const queue = () => { if (!frame) frame = requestAnimationFrame(check) }
    queue()
    window.addEventListener('scroll', queue, { passive: true })
    window.addEventListener('resize', queue)
    window.addEventListener(CONSENT_LAYER_EVENT, queue)
    const observer = typeof ResizeObserver === 'undefined' ? undefined : new ResizeObserver(queue)
    observer?.observe(document.body)
    return () => {
      observer?.disconnect()
      window.removeEventListener('scroll', queue)
      window.removeEventListener('resize', queue)
      window.removeEventListener(CONSENT_LAYER_EVENT, queue)
      if (frame) cancelAnimationFrame(frame)
    }
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

      {/* Yielding, it keeps its place, its rung and its name in the accessibility tree. Keyboard focus brings it back
          (`focus-visible:`: a Tab, an Escape close, any key); a focus Modal returns after a pointer close (Send, the
          close button, a scrim tap) does not, so it never comes back opaque and tappable over the figures as the
          reader scrolls on. */}
      <button
        ref={launcherRef}
        type="button"
        aria-label={open ? 'Close feedback' : 'Send feedback'}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        style={LAUNCHER_OFFSET}
        className={cx(LAUNCHER_CLASS, yielding && !open && 'pointer-events-none opacity-0 focus-visible:pointer-events-auto focus-visible:opacity-100')}
      >
        <ChatCircleDotsIcon className="h-5 w-5" />
        <span className="hidden sm:inline">Feedback</span>
      </button>
    </>
  )
}
