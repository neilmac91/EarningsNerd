'use client'

import { useState, Suspense } from 'react'
import { useSearchParams } from 'next/navigation'
import { resendVerification } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import Link from 'next/link'
import { Loader2, Mail } from 'lucide-react'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'

function CheckEmailContent() {
  const searchParams = useSearchParams()
  const email = searchParams.get('email') ?? ''
  const [resendLoading, setResendLoading] = useState(false)
  const [resendStatus, setResendStatus] = useState<'idle' | 'sent' | 'error'>('idle')
  const [errorMessage, setErrorMessage] = useState('')

  const handleResend = async () => {
    if (!email || resendLoading) return
    setResendLoading(true)
    setResendStatus('idle')
    try {
      await resendVerification(email)
      setResendStatus('sent')
    } catch (err: unknown) {
      setErrorMessage(isApiError(err) ? getErrorMessage(err) : 'Failed to resend. Please try again.')
      setResendStatus('error')
    } finally {
      setResendLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader backHref="/register" backLabel="Back to Register" />

      <div className="flex min-h-[calc(100vh-80px)] items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-8 shadow-lg dark:border-border-dark dark:bg-panel-dark text-center">
          <div className="flex justify-center mb-4">
            <div className="rounded-full bg-mint-500/10 p-4">
              <Mail className="h-8 w-8 text-mint-500" />
            </div>
          </div>

          <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark mb-3">
            Check your inbox
          </h1>
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-2">
            We sent a verification link to
          </p>
          {email && (
            <p className="text-sm font-medium text-text-primary-light dark:text-text-primary-dark mb-6">
              {email}
            </p>
          )}
          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-8">
            Click the link in the email to activate your account. The link expires in 24 hours.
          </p>

          {resendStatus === 'sent' && (
            <div className="mb-4">
              <StateCard variant="info" title="Email resent" message="Check your inbox again." />
            </div>
          )}
          {resendStatus === 'error' && (
            <div className="mb-4">
              <StateCard variant="error" title="Resend failed" message={errorMessage} />
            </div>
          )}

          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Didn&apos;t receive it?{' '}
            <button
              onClick={handleResend}
              disabled={resendLoading || !email}
              className="text-mint-600 hover:underline dark:text-mint-400 disabled:opacity-50 inline-flex items-center gap-1"
            >
              {resendLoading && <Loader2 className="h-3 w-3 animate-spin" />}
              Resend email
            </button>
          </p>

          <p className="mt-6 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            <Link href="/login" className="text-mint-600 hover:underline dark:text-mint-400">
              Back to login
            </Link>
          </p>
        </div>
      </div>
    </div>
  )
}

export default function CheckEmailPage() {
  return (
    <Suspense>
      <CheckEmailContent />
    </Suspense>
  )
}
