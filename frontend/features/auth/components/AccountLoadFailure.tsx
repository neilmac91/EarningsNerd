'use client'

import Link from 'next/link'
import type { RefObject } from 'react'
import { buttonVariants, GuidanceCard } from '@/components/ui'
import { RetryButton, type RetainedFailure } from '@/hooks/useRetainedFailure'

interface AccountLoadFailureProps {
  /** The current-user read's failure, held through Try again's refetch until data replaces it (useRetainedFailure). */
  failure: RetainedFailure
  /** Where focus goes when Try again unmounts while it holds focus: an element the route renders once the read lands. */
  focusTarget: RefObject<HTMLElement | null>
}

/**
 * What a signed-in route shows when its current-user read fails before it has a user (offline, a 5xx): there is no
 * page to show and no guest to send to /login (isConfirmedGuest), so the reader can read /me again or go to the login
 * page. The dashboard, the watchlist and the admin section render this one card, so they say the same thing.
 */
export default function AccountLoadFailure({ failure, focusTarget }: AccountLoadFailureProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background-light dark:bg-background-dark px-4">
      <div className="max-w-md w-full">
        <GuidanceCard
          variant="error"
          title="Unable to load your dashboard"
          description={failure.error instanceof Error ? failure.error.message : 'Please try again in a moment.'}
          action={
            <>
              <RetryButton failures={[failure]} focusTarget={focusTarget} />
              <Link href="/login" className={buttonVariants({ variant: 'primary' })}>
                Go to login
              </Link>
            </>
          }
        />
      </div>
    </div>
  )
}
