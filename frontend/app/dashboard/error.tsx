'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import * as Sentry from '@sentry/nextjs'

export default function DashboardError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  const router = useRouter()

  // Check if this is an authentication error
  const isAuthError =
    error.message.includes('401') ||
    error.message.includes('Unauthorized') ||
    error.message.includes('authentication') ||
    error.message.toLowerCase().includes('auth')

  useEffect(() => {
    // Log the error to Sentry
    Sentry.captureException(error)
    console.error('Dashboard error:', error)

    if (isAuthError) {
      // Redirect to login for authentication errors
      console.log('Authentication error detected, redirecting to login')
      router.push('/login')
    }
  }, [error, router, isAuthError])

  if (isAuthError) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center bg-background-light px-4 dark:bg-background-dark">
        <div className="mx-auto max-w-md text-center">
          <div className="mb-8">
            <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-loss-soft dark:bg-loss-soft-dark">
              <svg
                className="h-10 w-10 text-error-light dark:text-error-dark"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"
                />
              </svg>
            </div>
            <h1 className="mb-2 text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
              Authentication Required
            </h1>
            <p className="text-text-secondary-light dark:text-text-secondary-dark">
              Please log in to access your dashboard.
            </p>
          </div>

          <button
            onClick={() => router.push('/login')}
            className="rounded-lg bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-6 py-3 font-medium transition-colors"
          >
            Go to Login
          </button>
        </div>
      </div>
    )
  }

  // Generic Error UI
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background-light px-4 dark:bg-background-dark">
      <div className="mx-auto max-w-md text-center">
        <div className="mb-8">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-loss-soft dark:bg-loss-soft-dark">
            <svg
              className="h-10 w-10 text-error-light dark:text-error-dark"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="mb-2 text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            Something went wrong
          </h1>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We encountered an unexpected error. Please try again.
          </p>
        </div>

        <div className="flex justify-center gap-4">
          <button
            onClick={reset}
            className="rounded-lg bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-6 py-3 font-medium transition-colors"
          >
            Try Again
          </button>
          <button
            onClick={() => router.push('/')}
            className="rounded-lg border border-border-light px-6 py-3 font-medium text-text-primary-light transition-colors hover:bg-brand-weak dark:border-border-dark dark:text-text-primary-dark dark:hover:bg-white/5"
          >
            Go Home
          </button>
        </div>
      </div>
    </div>
  )
}
