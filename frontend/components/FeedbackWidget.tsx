'use client'

import { useEffect, useState } from 'react'
import { toast } from 'sonner'
import { ChatCircleDotsIcon, XIcon, CircleNotchIcon, PaperPlaneTiltIcon } from '@/lib/icons'
import { Button } from '@/components/ui/Button'
import { submitFeedback, type FeedbackType } from '@/features/feedback/api/feedback-api'
import { hasActiveSession } from '@/lib/api/session'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { ENABLE_FEEDBACK_WIDGET } from '@/lib/featureFlags'

const TYPES: { value: FeedbackType; label: string }[] = [
  { value: 'bug', label: '🐞 Bug' },
  { value: 'feature', label: '✨ Idea' },
  { value: 'general', label: '💬 General' },
]

// Secondary launcher: pinned bottom-LEFT (Ask is the bottom-right hero) and clear of the iOS home
// indicator / Android nav bar. max() keeps a 1.25rem base gap on flat phones and adds the inset on
// notched ones (needs viewport-fit=cover, set in app/layout.tsx).
const LAUNCHER_OFFSET: React.CSSProperties = {
  bottom: 'max(1.25rem, env(safe-area-inset-bottom))',
  left: 'max(1.25rem, env(safe-area-inset-left))',
}
// The popup sits just above the launcher.
const PANEL_OFFSET: React.CSSProperties = {
  bottom: 'calc(max(1.25rem, env(safe-area-inset-bottom)) + 3.75rem)',
  left: 'max(1.25rem, env(safe-area-inset-left))',
}

/**
 * Always-available beta feedback launcher. Renders a floating button for logged-in users only
 * (gated on the client-readable session marker), opening a small bug/idea/general report panel that
 * posts to /api/feedback. Mounted once in Providers so it's available across the authenticated app.
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

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time hydration latch: session marker lives in localStorage, so we resolve client-only state after mount
    setMounted(true)
    setAuthed(hasActiveSession())
  }, [])

  if (!ENABLE_FEEDBACK_WIDGET || !mounted || !authed) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (message.trim().length < 5) return
    setSubmitting(true)
    try {
      await submitFeedback({
        type,
        message: message.trim(),
        pageUrl: typeof window !== 'undefined' ? window.location.pathname : undefined,
      })
      toast.success('Thanks for the feedback!', { description: "We read every note — it really helps." })
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
      {open && (
        <div
          role="dialog"
          aria-label="Send feedback"
          style={PANEL_OFFSET}
          className="fixed z-30 w-[min(92vw,22rem)] rounded-2xl bg-panel-light p-4 shadow-e2 ring-1 ring-black/5 dark:bg-panel-dark dark:shadow-none dark:ring-white/10"
        >
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
              Send feedback
            </h2>
            <button
              type="button"
              aria-label="Close feedback"
              onClick={() => setOpen(false)}
              className="rounded-md p-1 text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
            >
              <XIcon className="h-4 w-4" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="mt-3 space-y-3">
            <div className="flex gap-2">
              {TYPES.map((t) => (
                <button
                  key={t.value}
                  type="button"
                  onClick={() => setType(t.value)}
                  aria-pressed={type === t.value}
                  className={
                    'flex-1 rounded-lg border px-2 py-1.5 text-xs font-medium transition-colors ' +
                    (type === t.value
                      ? 'border-brand-strong/40 bg-brand-strong/10 text-brand-strong dark:border-brand-strong-dark/40 dark:bg-brand-strong-dark/15 dark:text-brand-strong-dark'
                      : 'border-black/10 text-text-secondary-light hover:bg-black/[0.03] dark:border-white/15 dark:text-text-secondary-dark dark:hover:bg-white/[0.04]')
                  }
                >
                  {t.label}
                </button>
              ))}
            </div>

            <textarea
              aria-label="Feedback message"
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              required
              autoFocus
              rows={4}
              maxLength={4000}
              placeholder="What's working, what's broken, or what you'd love to see…"
              className="w-full resize-none rounded-lg border border-black/10 bg-white/70 px-3 py-2 text-sm text-text-primary-light placeholder:text-text-tertiary-light focus:border-brand-strong focus:outline-none focus:ring-2 focus:ring-brand-strong/30 dark:border-white/15 dark:bg-white/5 dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
            />

            <Button
              type="submit"
              disabled={submitting || message.trim().length < 5}
              className="w-full py-2 font-semibold active:scale-[0.99]"
            >
              {submitting ? (
                <span className="flex items-center justify-center gap-2">
                  <CircleNotchIcon className="h-4 w-4 animate-spin" />
                  Sending…
                </span>
              ) : (
                <span className="flex items-center justify-center gap-2">
                  <PaperPlaneTiltIcon className="h-4 w-4" />
                  Send feedback
                </span>
              )}
            </Button>
          </form>
        </div>
      )}

      <button
        type="button"
        aria-label={open ? 'Close feedback' : 'Send feedback'}
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        style={LAUNCHER_OFFSET}
        className="fixed z-30 inline-flex min-h-[2.75rem] min-w-[2.75rem] items-center justify-center gap-2 rounded-full border border-border-light bg-panel-light px-3 py-2.5 text-xs font-medium text-text-secondary-light shadow-e2 transition-colors hover:bg-background-light hover:text-text-primary-light focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-light dark:border-white/10 dark:bg-panel-dark dark:text-text-secondary-dark dark:shadow-none dark:hover:bg-white/5 dark:hover:text-text-primary-dark"
      >
        <ChatCircleDotsIcon className="h-5 w-5" />
        <span className="hidden sm:inline">Feedback</span>
      </button>
    </>
  )
}
