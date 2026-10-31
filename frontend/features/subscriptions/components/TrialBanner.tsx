'use client'

import Link from 'next/link'
import { LightningIcon } from '@/lib/icons'
import { formatInstant } from '@/lib/format'

interface TrialBannerProps {
  /** The resolved plan (GET /api/subscriptions/subscription `is_pro`). An expired trial row keeps its
   *  raw `trialing` status after the API resolves it to Free, so status alone never decides. */
  isPro: boolean | null | undefined
  /** Subscription status from GET /api/subscriptions/subscription. */
  status: string | null | undefined
  /** ISO timestamp of trial end (trial_end). */
  trialEnd: string | null | undefined
  /** Optional extra classes for the outer container (e.g. spacing). */
  className?: string
}

/**
 * States the date a live Pro trial ends. Renders nothing unless the plan resolves to Pro while the
 * status is trialing (lessons/frontend-trial-labels-use-entitlements.md), so an expired trial with a
 * stale trial_end never reads as current. The date, not a countdown: the voice is patient. The glyph
 * is Lightning, commerce's mark; the sparkle belongs to the AI summary chip alone.
 */
export default function TrialBanner({ isPro, status, trialEnd, className = '' }: TrialBannerProps) {
  if (!isPro || status !== 'trialing') return null
  // trial_end is a Stripe instant: the day it falls on where the reader is, as in BillingPanel.
  const endsOn = formatInstant(trialEnd, 'MMM d, yyyy')
  if (!endsOn) return null

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border border-brand-border dark:border-brand-dark/40 bg-brand-strong/10 dark:bg-brand-dark/15 px-4 py-3 ${className}`}>
      <div className="flex items-center gap-2 text-sm text-text-primary-light dark:text-text-primary-dark">
        <LightningIcon className="h-4 w-4 text-brand-strong dark:text-brand-strong-dark" />
        <span>Your Pro trial ends {endsOn}.</span>
      </div>
      <Link
        href="/pricing"
        className="rounded-lg bg-brand text-white hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark px-3 py-1.5 text-xs font-semibold transition"
      >
        Keep Pro
      </Link>
    </div>
  )
}
