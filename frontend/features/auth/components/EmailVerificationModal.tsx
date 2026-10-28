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
type ResendState = {
  phase: 'idle' | 'sending' | 'sent' | 'failed' | 'limited'
  /** The last failure, kept through the next send so the panel does not shrink under the pointer: the
      centred dialog would move "I've verified" (or the scrim) under a quick second tap on Resend. `n`
      keys its Notice, so each new failure re-mounts its role="alert" and is announced again. */
  failure: { message: string; n: number } | null
}

const IDLE: ResendState = { phase: 'idle', failure: null }
const RESEND_FAILED = 'Please try again in a moment.'
// A 429 may come from the per-address cap or the shared per-IP one, so the copy fits both.
const RESEND_LIMITED = "We can't send another link right now. Use the newest link in your inbox, or try again later."

/**
 * Global, graceful intercept of the backend's "verify your email" 403. The axios
 * interceptor dispatches EMAIL_VERIFICATION_REQUIRED_EVENT on that 403, which only checkout sends
 * (`backend/app/routers/subscriptions.py`; `tests/unit/authPagesCopy.spec.tsx` holds it to that
 * route); this modal turns it into a friendly resend prompt instead of a raw error toast. It names
 * subscribing alone, and it sends nothing on opening, so it says where links go, not that one was sent.
 *
 * v3 (DS-04): composed on ui/Modal — the focus trap, Escape, focus return, scroll lock
 * and the overlay / z-modal tokens come from the primitive; actions are <Button>s.
 */
export default function EmailVerificationModal() {
  const [open, setOpen] = useState(false)
  const [resend, setResend] = useState<ResendState>(IDLE)
  const router = useRouter()
  const queryClient = useQueryClient()
  const [checking, setChecking] = useState(false)
  const checkingRef = useRef(false)
  const [checkFailure, setCheckFailure] = useState<{ title: string; message: string; n: number } | null>(null)

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
      if (!openRef.current) {
        setResend((r) => (r.phase === 'sending' ? r : IDLE))
        if (!checkingRef.current) setCheckFailure(null)
      }
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
    setResend((r) => ({ phase: 'sending', failure: r.failure }))
    try {
      await resendVerification(user.email)
      setResend({ phase: 'sent', failure: null })
    } catch (err) {
      // A 429 is the server's cap (3/hr per address, 20/hr per IP). The route charges the per-IP
      // bucket before the per-address check rejects, so a live button would let each further press
      // spend the shared IP allowance for nothing: Resend turns unavailable for this prompt.
      const limited = getErrorStatus(err) === 429
      setResend((r) => ({
        phase: limited ? 'limited' : 'failed',
        failure: { message: limited ? RESEND_LIMITED : RESEND_FAILED, n: (r.failure?.n ?? 0) + 1 },
      }))
    }
  }

  const handleRefresh = async () => {
    if (checkingRef.current) return
    checkingRef.current = true
    setChecking(true)
    try {
      // One explicit identity read; join an existing read instead of cancelling and restarting it.
      const identity = await queryClient.fetchQuery({
        queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0,
      })
      if (!identity) {
        setCheckFailure((previous) => ({
          title: "Couldn't check verification",
          message: 'Log in again to check your email verification.',
          n: (previous?.n ?? 0) + 1,
        }))
      } else if (identity.email_verified === true) {
        setCheckFailure(null)
        router.refresh()
        setOpen(false)
      } else {
        setCheckFailure((previous) => ({
          title: 'Email still unverified',
          message: "Open the newest verification link in your inbox, then choose “I've verified” again.",
          n: (previous?.n ?? 0) + 1,
        }))
      }
    } catch {
      setCheckFailure((previous) => ({
        title: "Couldn't check verification", message: 'Please try again in a moment.', n: (previous?.n ?? 0) + 1,
      }))
    } finally {
      checkingRef.current = false
      setChecking(false)
    }
  }

  return (
    <Modal open={open} onClose={close} labelledBy="verify-modal-title" size="md">
      <ModalHeader id="verify-modal-title" onClose={close} icon={<WarningCircleIcon className="h-5 w-5" />} tone="warning">
        Verify your email to continue
      </ModalHeader>
      <ModalBody>
        <p className="text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
          Subscribing requires a verified email. We send verification links to{' '}
          {/* The address wraps inside the paragraph only where it is longer than the line (overflow-wrap), so under
              200% text it no longer runs past the paragraph and scrolls the dialog sideways, and at the default size
              it moves to its own line whole, where break-all would split it at a line's end. */}
          <span className="break-words font-medium text-text-primary-light dark:text-text-primary-dark">
            {user?.email ?? 'your email address'}
          </span>
          .
        </p>
        {/* A polite live region, mounted and empty from the moment the dialog opens: the sent line is
            announced when it appears, and nothing else in it ever changes. */}
        <div role="status">
          {resend.phase === 'sent' ? (
            <p className="mt-3 flex items-start gap-2 text-sm leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">
              <CheckCircleIcon aria-hidden="true" className="mt-0.5 h-4 w-4 flex-shrink-0 text-success-light dark:text-success-dark" />
              <span>
                New link sent. Only the newest link works. Not there in a minute or two? Check your spam folder.
              </span>
            </p>
          ) : null}
        </div>
        {resend.failure ? (
          <Notice
            key={resend.failure.n}
            variant="error"
            title="Couldn't send a new link"
            description={resend.failure.message}
            className="mt-4 px-cap-4"
          />
        ) : null}
        {checkFailure ? (
          <Notice key={`check-${checkFailure.n}`} variant="error" title={checkFailure.title} description={checkFailure.message} className="mt-4 px-cap-4" />
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
        <Button onClick={handleRefresh} loading={checking} loadingText="Checking…" className="w-full sm:w-auto">
          I&apos;ve verified
        </Button>
      </ModalFooter>
    </Modal>
  )
}
