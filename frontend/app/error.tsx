'use client'

import { useEffect } from 'react'
import * as Sentry from '@sentry/nextjs'
import Link from 'next/link'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log the error to Sentry
    Sentry.captureException(error)
    console.error('Application error:', error)
  }, [error])

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
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h1 className="mb-2 text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">
            Something went wrong
          </h1>
          <p className="text-text-secondary-light dark:text-text-secondary-dark">
            We encountered an unexpected error. This has been logged and we&apos;ll look into it.
          </p>
          {error.digest && (
            <p className="mt-2 text-sm text-text-tertiary-light dark:text-text-tertiary-dark">
              Error ID: {error.digest}
            </p>
          )}
        </div>

        <div className="flex flex-col gap-3 sm:flex-row sm:justify-center">
          <button
            onClick={reset}
            className="rounded-lg bg-mint-600 px-6 py-3 font-medium text-white transition-colors hover:bg-mint-700 dark:bg-mint-500 dark:hover:bg-mint-600"
          >
            Try again
          </button>
          <Link
            href="/"
            className="rounded-lg border border-border-light bg-white px-6 py-3 font-medium text-text-primary-light transition-colors hover:bg-gray-50 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:hover:bg-gray-800"
          >
            Go home
          </Link>
        </div>

        {/* DEBUG: Enabled in production to troubleshoot crash */}
        <div className="mt-8 rounded-lg border border-border-light bg-gray-50 p-4 text-left dark:border-border-dark dark:bg-gray-900">
          <h2 className="mb-2 font-mono text-sm font-semibold text-red-600 dark:text-red-400">
            Error Details (Debug Mode):
          </h2>
          <pre className="overflow-x-auto text-xs text-text-secondary-light dark:text-text-secondary-dark">
            {error.message}
          </pre>
          {error.stack && (
            <pre className="mt-2 overflow-x-auto text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
              {error.stack}
            </pre>
          )}
        </div>
      </div>
    </div>
  )
}
