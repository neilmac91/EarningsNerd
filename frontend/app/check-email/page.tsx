'use client'

import { useState, useEffect, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { resendVerification } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { CircleNotchIcon, EnvelopeSimpleIcon } from '@/lib/icons'
import AuthShell from '@/components/auth/AuthShell'
import { Notice } from '@/components/ui'

const RESEND_COOLDOWN_SECONDS = 30

function CheckEmailContent() {
  const searchParams = useSearchParams()
  const email = searchParams.get('email') ?? ''
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
      <p className="mt-2 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        We sent a verification link to
      </p>
      {email && (
        <p className="mt-1 text-center text-sm font-medium text-text-primary-light dark:text-text-primary-dark">
          {email}
        </p>
      )}
      <p className="mt-4 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Click the link to activate your account. It expires in 24 hours.
      </p>

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

      <p className="mt-8 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Didn&apos;t receive it?{' '}
        <button
          onClick={handleResend}
          disabled={resendLoading || cooldown > 0 || !email}
          className="inline-flex items-center gap-1 font-medium text-brand-strong hover:underline disabled:cursor-not-allowed disabled:opacity-50 disabled:no-underline dark:text-brand-strong-dark"
        >
          {resendLoading && <CircleNotchIcon className="h-3 w-3 animate-spin" />}
          {cooldown > 0 ? `Resend in ${cooldown}s` : 'Resend email'}
        </button>
      </p>

      <p className="mt-4 text-center text-sm">
        <Link href="/login" className="text-text-secondary-light hover:underline dark:text-text-secondary-dark">
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
