'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { CheckCircleIcon, WarningCircleIcon } from '@/lib/icons'
import {
  Button,
  Modal,
  ModalBody,
  ModalFooter,
  ModalHeader,
  Notice,
  cx,
  secondaryUnavailableClass,
} from '@/components/ui'
import { getCurrentUserSafe, resendVerification } from '@/features/auth/api/auth-api'
import { EMAIL_VERIFICATION_REQUIRED_EVENT } from '@/lib/api/client'
import { getErrorStatus } from '@/lib/api/types'
import { queryKeys } from '@/lib/queryKeys'

/** Resend's lifecycle within one prompt. `sent` and `limited` (a 429) leave Resend unavailable as a
    result of its own press, so it stays focusable: aria-disabled plus handleResend's early return,
    never native `disabled`. Chromium blurs a focused control that turns disabled, which dropped
    keyboard focus to <body> inside the open dialog. lessons/frontend-busy-controls-stay-focusable.md (e) */
type ResendState =
  | { phase: 'idle' | 'sending' | 'sent' }
  | { phase: 'failed' | 'limited'; message: string }

const IDLE: ResendState = { phase: 'idle' }
const RESEND_FAILED = 'Please try again in a moment.'
const RESEND_LIMITED = "We've sent several links recently. Use the newest one, or try again later."

/**
 * Global, graceful intercept of the backend's "verify your email" 403. The axios
 * interceptor dispatches EMAIL_VERIFICATION_REQUIRED_EVENT when an unverified user
 * hits a gated action (generate / checkout); this modal turns that into a friendly
 * resend prompt instead of a raw error toast.
 *
 * v3 (DS-04): composed on ui/Modal — the focus trap, Escape, focus return, scroll lock
 * and the overlay / z-modal tokens come from the primitive; actions are <Button>s.
 */
export default function EmailVerificationModal() {
  const [open, setOpen] = useState(false)
  const [resend, setResend] = useState<ResendState>(IDLE)
  const router = useRouter()
  const queryClient = useQueryClient()

  const { data: user } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
    staleTime: 60_000,
  })

  // Whether the dialog is showing, readable from the event handler without re-subscribing.
  const openRef = useRef(false)
  useEffect(() => {
    openRef.current = open
  }, [open])

  useEffect(() => {
    const handler = () => {
      // A new prompt starts fresh. Another gated 403 while this one is open is the same prompt: it
      // must not re-arm a just-sent Resend, whose next press would replace the fresh link. Nor does a
      // prompt reset a send still in flight, which would re-arm Resend under the live request.
      if (!openRef.current) setResend((r) => (r.phase === 'sending' ? r : IDLE))
      openRef.current = true
      setOpen(true)
    }
    window.addEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, handler)
    return () => window.removeEventListener(EMAIL_VERIFICATION_REQUIRED_EVENT, handler)
  }, [])

  const close = () => setOpen(false)

  const sending = resend.phase === 'sending'
  const unavailable = resend.phase === 'sent' || resend.phase === 'limited'

  const handleResend = async () => {
    if (!user?.email || sending || unavailable) return
    // Leaving `failed` unmounts the error Notice, so the next failure re-inserts its role="alert"
    // and is announced again even when the message is unchanged.
    setResend({ phase: 'sending' })
    try {
      await resendVerification(user.email)
      setResend({ phase: 'sent' })
    } catch (err) {
      // A 429 is the server's cap (3/hr per address, 20/hr per IP). The route charges the per-IP
      // bucket before the per-address check rejects, so a live button would let each further press
      // spend the shared IP allowance for nothing: Resend turns unavailable for this prompt.
      setResend(
        getErrorStatus(err) === 429
          ? { phase: 'limited', message: RESEND_LIMITED }
          : { phase: 'failed', message: RESEND_FAILED },
      )
    }
  }

  const handleRefresh = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
    router.refresh()
    setOpen(false)
  }

  return (
    <Modal open={open} onClose={close} labelledBy="verify-modal-title" size="md">
      <ModalHeader id="verify-modal-title" onClose={close} icon={<WarningCircleIcon className="h-5 w-5" />} tone="warning">
        Verify your email to continue
      </ModalHeader>
      <ModalBody>
        <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          Generating summaries and subscribing require a verified email. We sent a link to{' '}
          <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
            {user?.email ?? 'your email address'}
          </span>
          .
        </p>
        {/* A polite live region, mounted and empty from the moment the dialog opens: the sent line is
            announced when it appears, and nothing else in it ever changes. */}
        <div role="status">
          {resend.phase === 'sent' ? (
            <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
              <CheckCircleIcon className="mt-0.5 h-4 w-4 flex-shrink-0 text-success-light dark:text-success-dark" />
              <span>
                New link sent. Only the newest link works. Not there in a minute or two? Check your spam folder.
              </span>
            </p>
          ) : null}
        </div>
        {resend.phase === 'failed' || resend.phase === 'limited' ? (
          <Notice variant="error" title="Couldn't send a new link" description={resend.message} className="mt-4" />
        ) : null}
      </ModalBody>
      <ModalFooter>
        <Button
          variant="secondary"
          onClick={handleResend}
          loading={sending}
          loadingText="Sending…"
          aria-disabled={unavailable || sending || undefined}
          className={cx('w-full sm:w-auto', unavailable && secondaryUnavailableClass)}
        >
          {resend.phase === 'sent' ? 'Link sent' : 'Resend link'}
        </Button>
        <Button onClick={handleRefresh} className="w-full sm:w-auto">
          I&apos;ve verified
        </Button>
      </ModalFooter>
    </Modal>
  )
}
