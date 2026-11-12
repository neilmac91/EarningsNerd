'use client'

import { useEffect, useRef, useState } from 'react'
import { useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { verifyEmail } from '@/features/auth/api/auth-api'
import {
  readVerifyEmailFailure,
  VERIFY_FIRST_TRY_HINT,
  VERIFY_UNANSWERED_DESCRIPTION,
  VERIFY_UNANSWERED_TITLE,
} from '@/features/auth/lib/verifyEmailFailure'
import Link from 'next/link'
import { CheckCircleIcon, XCircleIcon } from '@/lib/icons'
import AuthShell from '@/features/auth/components/AuthShell'
import { Button, cx, Notice, primaryUnavailableClass } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'

const NO_TOKEN = 'No verification token found. Please use the link from your email.'
/** The answer that replaces the button takes focus from it, so it can show the ring a keyboard user expects. */
const ANSWER = 'rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark'

/** The token in a location's query (`?token=…`, the form the email's link uses) or fragment (`#token=…`), or null. */
function verificationTokenFrom(search: string, hash: string): string | null {
  for (const part of [search, hash]) {
    const token = new URLSearchParams(part.replace(/^[?#]/, '')).get('token')?.trim()
    if (token) return token
  }
  return null
}

/**
 * The page a verification email's link opens: {FRONTEND_URL}/verify-email?token=<token> (a `#token=` fragment works
 * too). It is safe for a link scanner: loading it sends nothing. A mail scanner that runs the page's script would
 * otherwise spend the single-use token before its reader clicks, who would then see "Verification failed". The token
 * is read after mount and taken out of the address bar at once; only a press of Verify email posts it
 * (POST /api/auth/verify-email), once per press. No login: the token is the email's own. A refused link (a 400) ends
 * on the failure state, since its token is spent or bad. A press that got no answer about the link (no connection, a
 * timeout, a server error, a rate limit) leaves the token unspent in this page's state, so the page stays as it is,
 * says so in an error notice above the button, and the next press posts the same token again. If that next press is
 * refused, the first may have verified the address before its answer was lost, so the refusal adds that the reader
 * can log in to check. The success state's move to the home page is cancelled when the reader leaves first.
 */
export default function VerifyEmailPage() {
  const router = useRouter()
  const queryClient = useQueryClient()
  // The email's token: undefined until the address is read after mount (the server renders none), null when the
  // address held none.
  const [token, setToken] = useState<string | null | undefined>(undefined)
  const [verifying, setVerifying] = useState(false)
  // What the server answered about the link: null until it answers, then success or the refusal's sentence.
  const [outcome, setOutcome] = useState<{ verified: true } | { verified: false; message: string } | null>(null)
  // The last press got no answer about the link: the button stays, under the notice that says so.
  const [unanswered, setUnanswered] = useState(false)
  // One post per press: a second press, or a double click before the busy render lands, sends nothing while a post is
  // out, and nothing after an answer about the link. A press that got no such answer frees it for the next press.
  const sent = useRef(false)
  // A press in this visit got no answer: it may still have verified the address, which a later refusal cannot tell.
  const unansweredBefore = useRef(false)
  const answerRef = useRef<HTMLDivElement>(null)
  // The success state's move to the home page, cancelled if the reader leaves the page before it runs.
  const goHome = useRef<ReturnType<typeof setTimeout> | null>(null)
  useEffect(() => () => {
    if (goHome.current) clearTimeout(goHome.current)
  }, [])

  useEffect(() => {
    const found = verificationTokenFrom(window.location.search, window.location.hash)
    // Out of the address bar and this history entry: from here the token lives in this page's state alone, so no
    // bookmark, copied address or later visit carries it. Next's own history state is kept.
    if (window.location.search || window.location.hash) {
      window.history.replaceState(window.history.state, '', window.location.pathname)
    }
    // Development's StrictMode runs this twice, and the second run finds the address cleared: it keeps the first read.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- the address is the browser's alone, read once after mount
    setToken((read) => read ?? found)
  }, [])

  // The answer takes the button away, so focus goes to the answer rather than falling to the page. A press with no
  // answer about the link keeps the button, and focus stays on it.
  const answered = outcome !== null
  useEffect(() => {
    if (answered) answerRef.current?.focus({ preventScroll: true })
  }, [answered])

  const verify = async () => {
    if (!token || sent.current) return
    sent.current = true
    setVerifying(true)
    setUnanswered(false)
    try {
      await verifyEmail(token)
      setOutcome({ verified: true })
      // Refresh cached identity so the banner and the avatar dot clear at once.
      void queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
      goHome.current = setTimeout(() => router.push('/'), 3000)
    } catch (err: unknown) {
      const read = readVerifyEmailFailure(err)
      if (read.retryable) {
        sent.current = false
        unansweredBefore.current = true
        setUnanswered(true)
      } else {
        setOutcome({
          verified: false,
          message: unansweredBefore.current ? `${read.message} ${VERIFY_FIRST_TRY_HINT}` : read.message,
        })
      }
    } finally {
      setVerifying(false)
    }
  }

  const failure = token === null ? NO_TOKEN : outcome && !outcome.verified ? outcome.message : null
  const unavailable = !token
  return (
    <AuthShell>
      <div className="text-center">
        {outcome?.verified ? (
          <div ref={answerRef} tabIndex={-1} className={ANSWER}>
            <div className="mb-4 flex justify-center">
              <CheckCircleIcon className="animate-check-pop h-12 w-12 text-brand-strong dark:text-brand-strong-dark" />
            </div>
            <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Email verified
            </h1>
            <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Your email address is confirmed. Taking you to the home page…
            </p>
            <Link href="/" className="mt-6 inline-block rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark text-sm font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
              Continue to EarningsNerd
            </Link>
          </div>
        ) : failure !== null ? (
          <div ref={answerRef} tabIndex={-1} className={ANSWER}>
            <div className="mb-4 flex justify-center">
              <XCircleIcon className="h-12 w-12 text-error-light dark:text-error-dark" />
            </div>
            <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Verification failed
            </h1>
            <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {failure}
            </p>
            <div className="mt-6 space-y-2 text-sm">
              <p>
                {/* /check-email without an address offers no Resend: it says where a new link comes from. */}
                <Link href="/check-email" className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
                  Get a new link
                </Link>
              </p>
              <p className="text-text-tertiary-light dark:text-text-tertiary-dark">
                or{' '}
                <Link href="/login" className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark text-brand-strong hover:underline dark:text-brand-strong-dark">
                  back to login
                </Link>
              </p>
            </div>
          </div>
        ) : (
          <>
            <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Verify your email address
            </h1>
            <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Press Verify email to confirm this address is yours.
            </p>
            {unanswered && (
              <div className="mt-4">
                <Notice variant="error" title={VERIFY_UNANSWERED_TITLE} description={VERIFY_UNANSWERED_DESCRIPTION} />
              </div>
            )}
            <div className="mt-6">
              {/* Unavailable only until the address is read after mount: aria-disabled and an early return. */}
              <Button
                onClick={verify}
                loading={verifying}
                loadingText="Verifying…"
                // Busy keeps Button's own aria-disabled: a value here replaces it, so it names `verifying` too.
                aria-disabled={unavailable || verifying || undefined}
                className={cx('w-full', unavailable && !verifying && primaryUnavailableClass)}
              >
                Verify email
              </Button>
            </div>
          </>
        )}
      </div>
    </AuthShell>
  )
}
