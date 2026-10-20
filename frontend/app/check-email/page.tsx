'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { resendVerification } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { CircleNotchIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import AuthShell from '@/features/auth/components/AuthShell'
import { loginHrefWithRedirect } from '@/lib/postAuthRedirect'
import { Notice } from '@/components/ui'

const RESEND_COOLDOWN_SECONDS = 30

function CheckEmailContent() {
  const searchParams = useSearchParams()
  const email = searchParams.get('email') ?? ''
  // Forwarded from /register?redirect=… — passed on to login, which validates it before navigating.
  const redirect = searchParams.get('redirect') ?? ''
  const [resendLoading, setResendLoading] = useState(false)
  const [resendStatus, setResendStatus] = useState<'idle' | 'sent' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')
  const [cooldown, setCooldown] = useState(0)

  useEffect(() => {
    if (cooldown <= 0) return
    const timer = setInterval(() => setCooldown((c) => c - 1), 1000)
    return () => clearInterval(timer)
  }, [cooldown])

  const handleResend = async () => {
    if (!email || resendLoading || cooldown > 0) return
    setResendLoading(true)
    setResendStatus('idle')
    try {
      await resendVerification(email)
      setResendStatus('sent')
      setCooldown(RESEND_COOLDOWN_SECONDS)
    } catch (err: unknown) {
      setErrorMessage(isApiError(err) ? getErrorMessage(err) : 'Failed to resend. Please try again.')
      setResendStatus('error')
    } finally {
      setResendLoading(false)
    }
  }

  return (
    <AuthShell>
      <div className="flex justify-center">
        <div className="rounded-full bg-brand-strong/10 p-4 dark:bg-brand-dark/15">
          <EnvelopeSimpleIcon className="h-8 w-8 text-brand-strong dark:text-brand-strong-dark" />
        </div>
      </div>

      <h1 className="mt-6 text-center text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
        Check your inbox
      </h1>
      {/* Register lands here after sending a link; the account menu's "Verify your email" lands here
          without one. So the page never says a link was just sent: it names where links go, and Resend
          is what sends one. */}
      {email ? (
        <>
          <p className="mt-2 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
            We send verification links to
          </p>
          {/* An address has no break opportunity, so at 200% text a long one overflows the column;
              break-words lets it break at the edge (the column is a block of definite width). */}
          <p className="mt-1 break-words text-center text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
            {email}
          </p>
          <p className="mt-4 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Open the newest one to verify your email address. Each link expires 24 hours after we send it.
          </p>
        </>
      ) : (
        // Reached without an address (verify-email's "Get a new link"): nothing to
        // resend to, so the page says where a new link comes from instead of offering Resend.
        <>
          <p className="mt-2 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Open the newest verification link we sent you.
          </p>
          <p className="mt-2 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Need a new one? Log in, open the account menu and choose Verify your email.
          </p>
        </>
      )}

      {resendStatus === 'sent' && (
        <div className="mt-6">
          <Notice variant="success" title="Email resent" description="Check your inbox again." />
        </div>
      )}
      {resendStatus === 'error' && (
        <div className="mt-6">
          <Notice variant="error" title="Resend failed" description={errorMessage} />
        </div>
      )}

      {email && (
      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Didn&apos;t receive it?{' '}
        {/* In flight and cooling down: aria-disabled (handleResend returns early), not native
            `disabled`. Chromium blurs a focused button that turns disabled, and both states
            follow this button's own activation. Without an email the line is not rendered at
            all, so nothing here is natively disabled. In flight, the aria-disabled look fades the
            label's ink, not the element, so the focus indicator keeps its strength. */}
        <button
          onClick={handleResend}
          aria-disabled={resendLoading || cooldown > 0 || undefined}
          aria-busy={resendLoading || undefined}
          className="group rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark inline-flex items-center gap-1 font-medium disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed"
        >
          {resendLoading && <CircleNotchIcon className="h-3 w-3 animate-spin text-brand-strong/50 motion-reduce:animate-none dark:text-brand-strong-dark/50" />}
          {/* The label sets the ink and draws the underline, so the underline is always the label's
              colour (a button's own underline is drawn in the button's inherited secondary ink). The
              countdown carries a number, so it rests in the secondary ink at full strength while the
              control waits, legible and never sage (D-030); the sage label, its underline under the
              pointer and its in-flight fade come back with "Resend email". */}
          {cooldown > 0 ? (
            <span className="tabular-nums text-text-secondary-light dark:text-text-secondary-dark">Resend in {cooldown}s</span>
          ) : (
            <span className="text-brand-strong group-hover:underline group-disabled:no-underline group-aria-disabled:no-underline group-aria-disabled:text-brand-strong/50 dark:text-brand-strong-dark dark:group-aria-disabled:text-brand-strong-dark/50">Resend email</span>
          )}
        </button>
      </p>
      )}

      <p className="mt-4 text-center text-sm">
        <Link
          href={loginHrefWithRedirect(redirect)}
          className="rounded-lg focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark text-text-secondary-light hover:underline dark:text-text-secondary-dark"
        >
          Back to login
        </Link>
      </p>
    </AuthShell>
  )
}

export default function CheckEmailPage() {
  return (
    <Suspense>
      <CheckEmailContent />
    </Suspense>
  )
}
