'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { CreditCard, Loader2, Sparkles } from 'lucide-react'
import {
  getSubscriptionStatus,
  getUsage,
  createPortalSession,
} from '@/features/subscriptions/api/subscriptions-api'
import { formatLocalDate } from '@/lib/format'

function daysUntil(value: string | null): number | null {
  if (!value) return null
  const end = new Date(value).getTime()
  if (Number.isNaN(end)) return null
  return Math.max(0, Math.ceil((end - Date.now()) / (1000 * 60 * 60 * 24)))
}

export default function BillingPanel() {
  const { data: sub, isLoading, isError } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
  })
  const { data: usage } = useQuery({ queryKey: ['usage'], queryFn: getUsage, retry: false })

  const portal = useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      if (data.url) window.location.href = data.url
    },
  })

  // Surface the failure rather than silently falling back to "Free" — that would mislead a Pro
  // subscriber on a transient network error.
  if (isError) {
    return (
      <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <CreditCard className="h-5 w-5 text-blue-600" />
          <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Billing</h2>
        </div>
        <p className="text-sm text-red-600 dark:text-red-400">
          Failed to load billing information. Please refresh the page or try again later.
        </p>
      </div>
    )
  }

  const isTrialing = sub?.status === 'trialing'
  const isPro = Boolean(sub?.is_pro)
  const trialDays = isTrialing ? daysUntil(sub?.trial_end ?? null) : null
  const planLabel = isTrialing ? 'Pro (trial)' : isPro ? 'Pro' : 'Free'

  return (
    <div className="bg-white dark:bg-slate-800 rounded-lg shadow-sm border border-slate-200 dark:border-slate-700 p-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <CreditCard className="h-5 w-5 text-blue-600" />
        <h2 className="text-xl font-semibold text-slate-900 dark:text-white">Billing</h2>
      </div>

      {isLoading ? (
        <div className="flex items-center text-slate-500 dark:text-slate-400">
          <Loader2 className="h-4 w-4 mr-2 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-4">
          {/* Plan + status */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-600 dark:text-slate-400">Plan</span>
            <span
              className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium ${
                isPro
                  ? 'bg-mint-100 text-mint-800 dark:bg-mint-900/30 dark:text-mint-300'
                  : 'bg-slate-100 text-slate-700 dark:bg-slate-700 dark:text-slate-300'
              }`}
            >
              {isPro && <Sparkles className="h-3.5 w-3.5" />}
              {planLabel}
            </span>
          </div>

          {/* Usage */}
          <div className="flex items-center justify-between">
            <span className="text-sm text-slate-600 dark:text-slate-400">Summaries this month</span>
            <span className="text-sm font-medium text-slate-900 dark:text-white">
              {usage
                ? usage.summaries_limit == null
                  ? `${usage.summaries_used} · Unlimited`
                  : `${usage.summaries_used} / ${usage.summaries_limit}`
                : '—'}
            </span>
          </div>

          {/* Trial countdown */}
          {isTrialing && trialDays !== null && (
            <div className="rounded-lg border border-mint-500/30 bg-mint-500/10 px-4 py-3 text-sm text-slate-800 dark:text-slate-200">
              <strong>{trialDays} {trialDays === 1 ? 'day' : 'days'} left</strong> in your Pro trial
              {sub?.trial_end ? ` · ends ${formatLocalDate(sub.trial_end, 'MMM d, yyyy')}` : ''}.
            </div>
          )}

          {/* Renewal / cancellation */}
          {isPro && !isTrialing && sub?.current_period_end && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-slate-600 dark:text-slate-400">
                {sub.cancel_at_period_end ? 'Access until' : 'Renews on'}
              </span>
              <span className="text-sm font-medium text-slate-900 dark:text-white">
                {formatLocalDate(sub.current_period_end, 'MMM d, yyyy')}
              </span>
            </div>
          )}
          {sub?.cancel_at_period_end && (
            <p className="text-sm text-amber-600 dark:text-amber-400">
              Your subscription is set to cancel at the end of the current period.
            </p>
          )}

          {/* Action — the Stripe Customer Portal only works for users with a real Stripe customer.
              A no-card reverse-trial user is `is_pro` but has no `stripe_customer_id`, so gating on
              `isPro` here used to render a "Manage billing" button that always 400s. Gate strictly on
              the customer id, and send everyone else to /pricing to subscribe. */}
          <div className="pt-1">
            {sub?.stripe_customer_id ? (
              <button
                type="button"
                onClick={() => portal.mutate()}
                disabled={portal.isPending}
                className="inline-flex items-center px-4 py-2 bg-slate-200 hover:bg-slate-300 dark:bg-slate-700 dark:hover:bg-slate-600 text-slate-900 dark:text-white rounded-lg transition-colors disabled:opacity-50"
              >
                {portal.isPending ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : null}
                Manage billing
              </button>
            ) : (
              <Link
                href="/pricing"
                className="inline-flex items-center px-4 py-2 bg-mint-500 hover:bg-mint-400 text-slate-950 rounded-lg font-medium transition-colors"
              >
                {isTrialing ? 'Subscribe to Pro' : 'Upgrade to Pro'}
              </Link>
            )}
            {portal.isError && (
              <p className="mt-2 text-sm text-red-600 dark:text-red-400">
                Could not open the billing portal. Please try again.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
