'use client'

import { useEffect } from 'react'
import { useRouter } from 'next/navigation'
import * as Sentry from '@sentry/nextjs'
import { LockSimpleIcon, WarningCircleIcon } from '@/lib/icons'
import { Button, GuidanceCard } from '@/components/ui'

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
        <div className="w-full max-w-md">
          <GuidanceCard
            variant="error"
            icon={<LockSimpleIcon className="h-5 w-5" />}
            title="Authentication Required"
            description="Please log in to access your dashboard."
            action={<Button onClick={() => router.push('/login')}>Go to Login</Button>}
          />
        </div>
      </div>
    )
  }

  // Generic Error UI
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background-light px-4 dark:bg-background-dark">
      <div className="w-full max-w-md">
        <GuidanceCard
          variant="error"
          icon={<WarningCircleIcon className="h-5 w-5" />}
          title="Something went wrong"
          description="We encountered an unexpected error. Please try again."
          action={
            <>
              <Button onClick={reset}>Try Again</Button>
              <Button variant="secondary" onClick={() => router.push('/')}>
                Go Home
              </Button>
            </>
          }
        />
      </div>
    </div>
  )
}
