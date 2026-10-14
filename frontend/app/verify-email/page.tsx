'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { useQueryClient } from '@tanstack/react-query'
import { verifyEmail } from '@/features/auth/api/auth-api'
import { verifyEmailFailureMessage } from '@/features/auth/lib/verifyEmailFailure'
import Link from 'next/link'
import { CheckCircleIcon, CircleNotchIcon, XCircleIcon } from '@/lib/icons'
import AuthShell from '@/features/auth/components/AuthShell'
import { queryKeys } from '@/lib/queryKeys'

function VerifyEmailContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const queryClient = useQueryClient()
  const token = searchParams.get('token') ?? ''
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    if (!token) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time guard that sets error state before kicking off async email verification
      setStatus('error')
      setErrorMessage('No verification token found. Please use the link from your email.')
      return
    }

    verifyEmail(token)
      .then(() => {
        setStatus('success')
        // Refresh cached identity so the banner/avatar dot clear immediately
        queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
        queryClient.invalidateQueries({ queryKey: queryKeys.currentUser() })
        setTimeout(() => router.push('/'), 3000)
      })
      .catch((err: unknown) => {
        setStatus('error')
        setErrorMessage(verifyEmailFailureMessage(err))
      })
  }, [token, router, queryClient])

  return (
    <AuthShell>
      <div className="text-center">
        {status === 'loading' && (
          <>
            <CircleNotchIcon className="mx-auto mb-4 h-10 w-10 animate-spin motion-reduce:animate-none text-brand-strong dark:text-brand-strong-dark" />
            <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Verifying your email…
            </h1>
          </>
        )}

        {status === 'success' && (
          <>
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
          </>
        )}

        {status === 'error' && (
          <>
            <div className="mb-4 flex justify-center">
              <XCircleIcon className="h-12 w-12 text-error-light dark:text-error-dark" />
            </div>
            <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
              Verification failed
            </h1>
            <p className="mt-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {errorMessage}
            </p>
            <div className="mt-6 space-y-2 text-sm">
              <p>
                <Link href="/check-email" className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark font-medium text-brand-strong hover:underline dark:text-brand-strong-dark">
                  Resend verification email
                </Link>
              </p>
              <p className="text-text-tertiary-light dark:text-text-secondary-dark">
                or{' '}
                <Link href="/login" className="rounded-sm focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark text-brand-strong hover:underline dark:text-brand-strong-dark">
                  back to login
                </Link>
              </p>
            </div>
          </>
        )}
      </div>
    </AuthShell>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  )
}
