'use client'

import { useEffect, useState, Suspense } from 'react'
import { useSearchParams, useRouter } from 'next/navigation'
import { verifyEmail } from '@/features/auth/api/auth-api'
import Link from 'next/link'
import { Loader2, CheckCircle, XCircle } from 'lucide-react'
import SecondaryHeader from '@/components/SecondaryHeader'

function VerifyEmailContent() {
  const searchParams = useSearchParams()
  const router = useRouter()
  const token = searchParams.get('token') ?? ''
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading')
  const [errorMessage, setErrorMessage] = useState('')

  useEffect(() => {
    if (!token) {
      setStatus('error')
      setErrorMessage('No verification token found. Please use the link from your email.')
      return
    }

    verifyEmail(token)
      .then(() => {
        setStatus('success')
        setTimeout(() => router.push('/'), 3000)
      })
      .catch((err: unknown) => {
        setStatus('error')
        const msg =
          err && typeof err === 'object' && 'response' in err
            ? (err as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? 'Verification failed.'
            : 'Verification failed.'
        setErrorMessage(msg)
      })
  }, [token, router])

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader backHref="/login" backLabel="Back to Login" />

      <div className="flex min-h-[calc(100vh-80px)] items-center justify-center px-4 py-10">
        <div className="w-full max-w-md rounded-2xl border border-border-light bg-panel-light p-8 shadow-lg dark:border-border-dark dark:bg-panel-dark text-center">
          {status === 'loading' && (
            <>
              <Loader2 className="h-10 w-10 animate-spin text-mint-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark mb-2">
                Verifying your email…
              </h1>
            </>
          )}

          {status === 'success' && (
            <>
              <CheckCircle className="h-10 w-10 text-mint-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark mb-2">
                Email verified!
              </h1>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-6">
                Your account is active. Redirecting you now…
              </p>
              <Link href="/" className="text-mint-600 hover:underline dark:text-mint-400 text-sm">
                Continue to EarningsNerd
              </Link>
            </>
          )}

          {status === 'error' && (
            <>
              <XCircle className="h-10 w-10 text-red-500 mx-auto mb-4" />
              <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark mb-2">
                Verification failed
              </h1>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark mb-6">
                {errorMessage}
              </p>
              <div className="space-y-2 text-sm">
                <p>
                  <Link href="/check-email" className="text-mint-600 hover:underline dark:text-mint-400">
                    Resend verification email
                  </Link>
                </p>
                <p className="text-text-tertiary-light dark:text-text-tertiary-dark">
                  or{' '}
                  <Link href="/login" className="text-mint-600 hover:underline dark:text-mint-400">
                    back to login
                  </Link>
                </p>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyEmailContent />
    </Suspense>
  )
}
