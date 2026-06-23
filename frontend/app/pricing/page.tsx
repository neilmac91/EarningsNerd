'use client'

import { useState, Suspense, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { createCheckoutSession, getSubscriptionStatus, getUsage } from '@/features/subscriptions/api/subscriptions-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { CheckIcon, CircleNotchIcon } from '@/lib/icons'
import { useRouter, useSearchParams } from 'next/navigation'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'
import analytics from '@/lib/analytics'
import { useFeatureFlagVariantKey } from 'posthog-js/react'
import posthog from 'posthog-js'

function PricingContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // Default to annual — it's the better value (2 months free) and the plan's preferred cycle.
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('yearly')
  const [isLoadingCheckout, setIsLoadingCheckout] = useState<string | null>(null)
  const pricingVariant = useFeatureFlagVariantKey('pricing-experiment')
  const hasTrackedPricingView = useRef(false)
  const hasTrackedVariantExposure = useRef(false)

  // The pricing page is publicly reachable; only fetch account-scoped data for
  // signed-in users so guests see the plain guest/free-tier view, not a 401 error card.
  const { data: currentUser } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isAuthenticated = Boolean(currentUser)

  const { data: subscription, isError: subscriptionError, error: subscriptionErrorData, refetch: refetchSubscription, isFetching: subscriptionFetching } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: isAuthenticated,
  })

  const { data: usage, isError: usageError, error: usageErrorData, refetch: refetchUsage, isFetching: usageFetching } = useQuery({
    queryKey: ['usage'],
    queryFn: getUsage,
    retry: false,
    enabled: isAuthenticated,
  })

  useEffect(() => {
    // Handle success/cancel from Stripe
    if (searchParams.get('success') === 'true') {
      // Refresh subscription status
      router.refresh()
    }
    if (searchParams.get('canceled') === 'true') {
      // Handle cancellation
    }
  }, [searchParams, router])

  useEffect(() => {
    if (!hasTrackedPricingView.current) {
      analytics.pricingViewed(billingCycle)
      hasTrackedPricingView.current = true
    }
  }, [billingCycle])

  useEffect(() => {
    if (pricingVariant && !hasTrackedVariantExposure.current) {
      posthog.capture('pricing_experiment_exposed', {
        variant: pricingVariant,
      })
      hasTrackedVariantExposure.current = true
    }
  }, [pricingVariant])

  const checkoutMutation = useMutation({
    mutationFn: createCheckoutSession,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url
      }
    },
    onError: (error: unknown) => {
      const errorMessage = isApiError(error)
        ? getErrorMessage(error)
        : 'Failed to create checkout session'
      alert(errorMessage)
      setIsLoadingCheckout(null)
    },
  })

  const handleUpgrade = async (priceId: string) => {
    // Guests can't create a checkout session (401) — send them to sign up instead.
    if (!isAuthenticated) {
      router.push('/register')
      return
    }
    setIsLoadingCheckout(priceId)
    try {
      const priceValue = billingCycle === 'monthly' ? priceConfig.monthly : priceConfig.yearly
      analytics.checkoutStarted('pro', priceValue, billingCycle)
      await checkoutMutation.mutateAsync(priceId)
    } catch {
      // Error handled in mutation
    }
  }

  // Confirmed pricing: $14/mo · $140/yr (annual = 2 months free). The legacy $19/$29 A/B is retired;
  // `pricingVariant` is still read below purely for exposure analytics continuity.
  const priceConfig = { monthly: 14, yearly: 140, monthlyDisplay: '$14', yearlyDisplay: '$140' }

  // A reverse-trial user is `is_pro` but hasn't paid yet, so they must still be able to pick a
  // billing cycle and convert. Only a *paid* (active, non-trial) subscriber has nothing to buy —
  // treating every `is_pro` user as "Current Plan" dead-ends trial users on the upgrade button.
  const isTrialing = subscription?.status === 'trialing'
  const isPaidPro = Boolean(subscription?.is_pro) && !isTrialing

  const plans = [
    {
      name: 'Free',
      price: '$0',
      period: 'forever',
      description: 'Perfect for trying out EarningsNerd',
      features: [
        '5 summaries per month',
        'Access to all filings',
        'Basic AI summaries',
        'Company search',
        'Historical filing access',
      ],
      // Only the genuinely-free user is "on" the Free plan. A Pro user (paid or trialing) would
      // otherwise see "Current Plan" on BOTH cards, which reads as a contradiction.
      cta: isAuthenticated && !subscription?.is_pro ? 'Current Plan' : 'Get Started Free',
      disabled: isAuthenticated,
      priceId: null,
    },
    {
      name: 'Pro',
      price: billingCycle === 'monthly' ? priceConfig.monthlyDisplay : priceConfig.yearlyDisplay,
      period: billingCycle === 'monthly' ? 'per month' : 'per year',
      description: 'For professionals who need unlimited access',
      features: [
        'Unlimited summaries',
        'Real-time filing alerts',
        '8-K coverage',
        'Multi-year comparisons',
        'PDF & CSV exports',
        'Premium AI model & deeper analysis',
        'Priority support',
      ],
      cta: isPaidPro ? 'Current Plan' : isTrialing ? 'Subscribe to Pro' : 'Upgrade to Pro',
      disabled: isPaidPro,
      priceId: billingCycle === 'monthly' ? 'price_pro_monthly' : 'price_pro_yearly',
      popular: true,
    },
  ]

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader
        title="Pricing"
        subtitle="Choose the plan that fits your workflow"
        backHref="/"
        backLabel="Back to home"
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <h2 className="text-4xl font-bold text-text-heading-light dark:text-text-heading-dark mb-4">Pricing</h2>
          <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark max-w-2xl mx-auto">
            Choose the plan that works for you. Upgrade or downgrade at any time.
          </p>

          {(subscriptionError || usageError) && (
            <div className="mt-6 mx-auto max-w-2xl text-left">
              <StateCard
                variant="error"
                title="We couldn't load all pricing details"
                message={
                  subscriptionErrorData instanceof Error
                    ? subscriptionErrorData.message
                    : usageErrorData instanceof Error
                    ? usageErrorData.message
                    : 'Please retry.'
                }
                action={
                  <div className="flex flex-wrap items-center gap-2">
                    <button
                      type="button"
                      onClick={() => refetchSubscription()}
                      disabled={subscriptionFetching}
                      className="inline-flex items-center rounded-md border border-error-light/40 bg-panel-light px-3 py-1 text-xs font-medium text-error-light transition hover:bg-error-light/10 dark:border-error-dark/40 dark:bg-panel-dark dark:text-error-dark dark:hover:bg-error-dark/15 disabled:opacity-60"
                    >
                      {subscriptionFetching ? 'Retrying…' : 'Retry subscription'}
                    </button>
                    <button
                      type="button"
                      onClick={() => refetchUsage()}
                      disabled={usageFetching}
                      className="inline-flex items-center rounded-md border border-error-light/40 bg-panel-light px-3 py-1 text-xs font-medium text-error-light transition hover:bg-error-light/10 dark:border-error-dark/40 dark:bg-panel-dark dark:text-error-dark dark:hover:bg-error-dark/15 disabled:opacity-60"
                    >
                      {usageFetching ? 'Retrying…' : 'Retry usage'}
                    </button>
                  </div>
                }
              />
            </div>
          )}

          {/* Billing Toggle — shown to free and trialing users (both can still choose a cycle). */}
          {!isPaidPro && (
            <div className="mt-8 flex items-center justify-center space-x-4">
              <span className={`text-sm font-medium ${billingCycle === 'monthly' ? 'text-text-primary-light dark:text-text-primary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>
                Monthly
              </span>
              <button
                type="button"
                role="switch"
                aria-checked={billingCycle === 'yearly'}
                aria-label="Billing cycle"
                onClick={() => {
                  const nextCycle = billingCycle === 'monthly' ? 'yearly' : 'monthly'
                  analytics.billingCycleToggled(billingCycle, nextCycle)
                  setBillingCycle(nextCycle)
                }}
                className="relative inline-flex h-6 w-11 items-center rounded-full bg-brand-strong dark:bg-brand-dark transition-colors focus:outline-none focus:ring-2 focus:ring-brand-light focus:ring-offset-2"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    billingCycle === 'yearly' ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <span className={`text-sm font-medium ${billingCycle === 'yearly' ? 'text-text-primary-light dark:text-text-primary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>
                Yearly <span className="text-success-light dark:text-success-dark">(2 months free)</span>
              </span>
            </div>
          )}
        </div>

        {/* Usage Stats */}
        {usage && !usageError && (
          <div className="mb-8 bg-info-light/10 border border-info-light/40 rounded-lg p-4 max-w-2xl mx-auto dark:bg-info-dark/15 dark:border-info-dark/40">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-info-light dark:text-info-dark">Current Usage</p>
                <p className="text-sm text-info-light dark:text-info-dark">
                  {usage.summaries_used} / {usage.summaries_limit || '∞'} summaries used this month
                </p>
              </div>
              {!usage.is_pro && usage.summaries_limit && (
                <div
                  className="w-32 bg-info-light/20 rounded-full h-2 dark:bg-info-dark/20"
                  role="progressbar"
                  aria-label={`${usage.summaries_used} of ${usage.summaries_limit} summaries used this month`}
                  aria-valuenow={usage.summaries_used}
                  aria-valuemin={0}
                  aria-valuemax={usage.summaries_limit}
                >
                  <div
                    className="bg-info-light dark:bg-info-dark h-2 rounded-full transition-all"
                    style={{ width: `${(usage.summaries_used / usage.summaries_limit) * 100}%` }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {plans.map((plan) => (
            <div
              key={plan.name}
              className={`relative rounded-2xl border-2 p-8 ${
                plan.popular
                  ? 'border-brand-strong dark:border-brand-dark bg-panel-light dark:bg-panel-dark shadow-e3 dark:shadow-none'
                  : 'border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e2 dark:shadow-none'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-brand-strong text-white dark:bg-brand-dark dark:text-background-dark px-4 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-text-heading-light dark:text-text-heading-dark mb-2">{plan.name}</h3>
                <div className="flex items-baseline justify-center">
                  <span className="text-5xl font-bold text-text-primary-light dark:text-text-primary-dark">{plan.price}</span>
                  {plan.period !== 'forever' && (
                    <span className="text-text-secondary-light dark:text-text-secondary-dark ml-2">/{plan.period}</span>
                  )}
                </div>
                <p className="text-text-secondary-light dark:text-text-secondary-dark mt-2">{plan.description}</p>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, index) => (
                  <li key={index} className="flex items-start">
                    <CheckIcon className="h-5 w-5 text-success-light dark:text-success-dark mr-3 flex-shrink-0 mt-0.5" />
                    <span className="text-text-secondary-light dark:text-text-secondary-dark">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => (plan.priceId ? handleUpgrade(plan.priceId) : router.push('/register'))}
                disabled={plan.disabled || (isAuthenticated && !plan.priceId) || (plan.priceId !== null && isLoadingCheckout === plan.priceId)}
                className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                  plan.disabled
                    ? 'bg-border-light text-text-secondary-light dark:bg-white/10 dark:text-text-secondary-dark cursor-not-allowed'
                    : plan.popular
                    ? 'bg-brand-strong text-white hover:bg-brand-light dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark focus-visible:outline-brand-light'
                    : 'bg-text-primary-light text-background-light dark:bg-white/10 dark:text-text-primary-dark hover:opacity-90'
                }`}
              >
                {plan.priceId && isLoadingCheckout === plan.priceId ? (
                  <span className="flex items-center justify-center">
                    <CircleNotchIcon className="h-5 w-5 animate-spin mr-2" />
                    Processing...
                  </span>
                ) : (
                  plan.cta
                )}
              </button>
            </div>
          ))}
        </div>

        {/* FAQ */}
        <div className="mt-16 max-w-3xl mx-auto">
          <h2 className="text-2xl font-bold text-text-heading-light dark:text-text-heading-dark mb-8 text-center">Frequently Asked Questions</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">
                Can I change plans later?
              </h3>
              <p className="text-text-secondary-light dark:text-text-secondary-dark">
                Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">
                What happens if I exceed my free limit?
              </h3>
              <p className="text-text-secondary-light dark:text-text-secondary-dark">
                You&apos;ll need to upgrade to Pro to generate more summaries. Your existing summaries remain accessible.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">
                Do you offer refunds?
              </h3>
              <p className="text-text-secondary-light dark:text-text-secondary-dark">
                We offer a 30-day money-back guarantee for Pro subscriptions. Contact us if you&apos;re not satisfied.
              </p>
            </div>
          </div>
        </div>
      </main>
    </div>
  )
}

export default function PricingPage() {
  return (
    <Suspense fallback={
      <div className="min-h-screen bg-background-light dark:bg-background-dark flex items-center justify-center">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-dark" />
      </div>
    }>
      <PricingContent />
    </Suspense>
  )
}

