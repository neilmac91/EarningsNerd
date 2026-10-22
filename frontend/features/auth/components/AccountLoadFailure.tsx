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
  /** What could not load, named for the route that shows the card. */
  title: string
}

/**
 * What a signed-in route shows when its current-user read fails before it has a user (offline, a 5xx): there is no
 * page to show and no guest to send to /login (isConfirmedGuest), so the reader can read /me again or go to the login
 * page. The dashboard, the watchlist and the admin section render this one card, so they say the same thing, each
 * naming what it could not load. It replaces the whole page, so its title is the page's h1 (UA-50, DESIGN_SYSTEM §5).
 */
export default function AccountLoadFailure({ failure, focusTarget, title }: AccountLoadFailureProps) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-background-light dark:bg-background-dark px-4">
      <div className="max-w-md w-full">
        <GuidanceCard
          variant="error"
          headingLevel="h1"
          title={title}
          description={failure.error instanceof Error ? failure.error.message : 'Try again in a moment.'}
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
