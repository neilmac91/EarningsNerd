'use client'

import { useMutation, useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { CircleNotchIcon, CreditCardIcon, SparkleIcon } from '@/lib/icons'
import {
  getSubscriptionStatus,
  getUsage,
  createPortalSession,
} from '@/features/subscriptions/api/subscriptions-api'
import { formatLocalDate } from '@/lib/format'
import { Button, buttonVariants } from '@/components/ui/Button'

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
      <div className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-sm border border-border-light dark:border-border-dark p-6 mb-6">
        <div className="flex items-center gap-3 mb-4">
          <CreditCardIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
          <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Billing</h2>
        </div>
        <p className="text-sm text-error-light dark:text-error-dark">
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
    <div className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-sm border border-border-light dark:border-border-dark p-6 mb-6">
      <div className="flex items-center gap-3 mb-4">
        <CreditCardIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Billing</h2>
      </div>

      {isLoading ? (
        <div className="flex items-center text-text-tertiary-light dark:text-text-secondary-dark">
          <CircleNotchIcon className="h-4 w-4 mr-2 animate-spin" /> Loading…
        </div>
      ) : (
        <div className="space-y-3">
          {/* Plan, usage & renewal — divided rows keep each label tied to its value */}
          <div className="divide-y divide-border-light dark:divide-border-dark">
            {/* Plan + status */}
            <div className="flex items-center justify-between gap-4 py-2.5">
              <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Plan</span>
              <span
                className={`inline-flex items-center gap-1 rounded-full px-3 py-1 text-sm font-medium ${
                  isPro
                    ? 'bg-brand-strong text-white dark:bg-brand-dark dark:text-background-dark'
                    : 'bg-brand-weak text-text-secondary-light dark:bg-white/5 dark:text-text-secondary-dark'
                }`}
              >
                {isPro && <SparkleIcon className="h-3.5 w-3.5" />}
                {planLabel}
              </span>
            </div>

            {/* Usage */}
            <div className="flex items-center justify-between gap-4 py-2.5">
              <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">Summaries this month</span>
              <span className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">
                {usage
                  ? usage.summaries_limit == null
                    ? `${usage.summaries_used} · Unlimited`
                    : `${usage.summaries_used} / ${usage.summaries_limit}`
                  : '—'}
              </span>
            </div>

            {/* Renewal / cancellation */}
            {isPro && !isTrialing && sub?.current_period_end && (
              <div className="flex items-center justify-between gap-4 py-2.5">
                <span className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  {sub.cancel_at_period_end ? 'Access until' : 'Renews on'}
                </span>
                <span className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">
                  {formatLocalDate(sub.current_period_end, 'MMM d, yyyy')}
                </span>
              </div>
            )}
          </div>

          {/* Trial countdown */}
          {isTrialing && trialDays !== null && (
            <div className="rounded-lg border border-brand-border bg-brand-weak dark:bg-white/5 px-4 py-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              <strong>{trialDays} {trialDays === 1 ? 'day' : 'days'} left</strong> in your Pro trial
              {sub?.trial_end ? ` · ends ${formatLocalDate(sub.trial_end, 'MMM d, yyyy')}` : ''}.
            </div>
          )}

          {sub?.cancel_at_period_end && (
            <p className="text-sm text-warning-light dark:text-warning-dark">
              Your subscription is set to cancel at the end of the current period.
            </p>
          )}

          {/* Action — the Stripe Customer Portal only works for users with a real Stripe customer.
              A no-card reverse-trial user is `is_pro` but has no `stripe_customer_id`, so gating on
              `isPro` here used to render a "Manage billing" button that always 400s. Gate strictly on
              the customer id, and send everyone else to /pricing to subscribe. */}
          <div className="border-t border-border-light dark:border-border-dark pt-3">
            {sub?.stripe_customer_id ? (
              <Button
                variant="secondary"
                onClick={() => portal.mutate()}
                disabled={portal.isPending}
              >
                {portal.isPending ? <CircleNotchIcon className="h-4 w-4 animate-spin" /> : null}
                Manage billing
              </Button>
            ) : (
              <Link
                href="/pricing"
                className={buttonVariants({ variant: 'primary' })}
              >
                {isTrialing ? 'Subscribe to Pro' : 'Upgrade to Pro'}
              </Link>
            )}
            {portal.isError && (
              <p className="mt-2 text-sm text-error-light dark:text-error-dark">
                Could not open the billing portal. Please try again.
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
