'use client'

import { useEffect } from 'react'
import * as Sentry from '@sentry/nextjs'
import Link from 'next/link'
import { Button, buttonVariants, GuidanceCard } from '@/components/ui'

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
      <div className="w-full max-w-md space-y-4">
        <GuidanceCard
          variant="error"
          title="Something went wrong"
          description={
            <>
              The error has been logged and we&apos;ll look into it.
              {error.digest && (
                <span className="mt-2 block text-text-tertiary-light dark:text-text-secondary-dark">
                  Error ID: {error.digest}
                </span>
              )}
            </>
          }
          action={
            <>
              <Button onClick={reset}>Try again</Button>
              <Link href="/" className={buttonVariants({ variant: 'secondary' })}>
                Go home
              </Link>
            </>
          }
        />

        {process.env.NODE_ENV === 'development' && (
          <div className="rounded-lg border border-border-light bg-background-light p-4 text-left dark:border-border-dark dark:bg-white/5">
            <h2 className="mb-2 font-mono text-sm font-semibold text-error-light dark:text-error-dark">
              Development Error Details:
            </h2>
            <pre className="overflow-x-auto text-xs text-text-secondary-light dark:text-text-secondary-dark">
              {error.message}
            </pre>
            {error.stack && (
              <pre className="mt-2 overflow-x-auto text-xs text-text-tertiary-light dark:text-text-secondary-dark">
                {error.stack}
              </pre>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
