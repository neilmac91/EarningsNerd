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

  useEffect(() => {
    // Log the error to Sentry
    Sentry.captureException(error)
    console.error('Dashboard error:', error)

    // Check if this is an authentication error
    const isAuthError =
      error.message.includes('401') ||
      error.message.includes('Unauthorized') ||
      error.message.includes('authentication') ||
      error.message.toLowerCase().includes('auth')

    if (isAuthError) {
      // Redirect to login for authentication errors
      console.log('Authentication error detected, redirecting to login')
      router.push('/login')
    }
  }, [error, router])

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background-light px-4 dark:bg-background-dark">
      <div className="mx-auto max-w-md text-center">
        <div className="mb-8">
          <div className="mx-auto mb-4 flex h-20 w-20 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/20">
            <svg
              className="h-10 w-10 text-red-600 dark:text-red-400"
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
          className="rounded-lg bg-mint-600 px-6 py-3 font-medium text-white transition-colors hover:bg-mint-700 dark:bg-mint-500 dark:hover:bg-mint-600"
        >
          Go to Login
        </button>
      </div>
    </div>
  )
}
