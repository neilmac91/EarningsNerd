'use client'

import Link from 'next/link'
import { Sparkles } from 'lucide-react'

interface TrialBannerProps {
  /** Subscription status from GET /api/subscriptions/subscription. */
  status: string | null | undefined
  /** ISO timestamp of trial end (trial_end). */
  trialEnd: string | null | undefined
  /** Optional extra classes for the outer container (e.g. spacing). */
  className?: string
}

function daysRemaining(trialEnd: string): number | null {
  const end = new Date(trialEnd).getTime()
  if (Number.isNaN(end)) return null
  return Math.max(0, Math.ceil((end - Date.now()) / (1000 * 60 * 60 * 24)))
}

/**
 * Shows "N days left in your Pro trial" while a reverse trial is active. Renders nothing for
 * non-trialing users (or expired/unknown trials), so it's safe to drop into any authed surface.
 */
export default function TrialBanner({ status, trialEnd, className = '' }: TrialBannerProps) {
  if (status !== 'trialing' || !trialEnd) return null
  const days = daysRemaining(trialEnd)
  if (days === null || days <= 0) return null

  return (
    <div className={`flex flex-wrap items-center justify-between gap-3 rounded-xl border border-mint-500/30 bg-mint-500/10 px-4 py-3 ${className}`}>
      <div className="flex items-center gap-2 text-sm text-text-primary-light dark:text-text-primary-dark">
        <Sparkles className="h-4 w-4 text-mint-600 dark:text-mint-400" />
        <span>
          <strong>{days} {days === 1 ? 'day' : 'days'} left</strong> in your Pro trial.
        </span>
      </div>
      <Link
        href="/pricing"
        className="rounded-lg bg-mint-500 px-3 py-1.5 text-xs font-semibold text-slate-950 transition-all hover:bg-mint-400"
      >
        Keep Pro
      </Link>
    </div>
  )
}
