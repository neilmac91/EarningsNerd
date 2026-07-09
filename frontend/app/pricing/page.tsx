'use client'

import { useState, Suspense, useRef, useEffect } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { createCheckoutSession, getSubscriptionStatus, getUsage } from '@/features/subscriptions/api/subscriptions-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { CheckIcon, CircleNotchIcon } from '@/lib/icons'
import { useRouter, useSearchParams } from 'next/navigation'
import SecondaryHeader from '@/components/SecondaryHeader'
import { Badge, Button, Card, Notice, Switch } from '@/components/ui'
import analytics from '@/lib/analytics'
import { useFeatureFlagVariantKey } from 'posthog-js/react'
import posthog from 'posthog-js'
import { queryKeys } from '@/lib/queryKeys'

interface CurrentUser {
  id: number
  email: string
  is_pro?: boolean
  is_beta?: boolean
  email_verified?: boolean
}

// Pricing anchor: $39/mo · $390/yr (annual = 2 months free) — the prosumer-band anchor the council
// set (kill $14, which reads as "toy" for an accountability product). Beta members still pay $0 via
// the 100%-off forever promo; this only changes the displayed/anchored price + the analytics value.
//
// Fake-door $39-vs-$29 A/B (roadmap 2.3): the `pricing-experiment` PostHog flag picks the arm.
// Display-only — both arms route to the same checkout, so the charge path is unchanged. Only the
// explicit `price_29` arm lowers the anchor; an unset/missing flag (or PostHog being down) falls
// through to the $39 control, so there's no regression if the experiment isn't configured. Module-
// scoped (it's static) so it isn't re-allocated on every render.
const PRICE_VARIANTS = {
  control: { monthly: 39, yearly: 390, monthlyDisplay: '$39', yearlyDisplay: '$390' },
  price_29: { monthly: 29, yearly: 290, monthlyDisplay: '$29', yearlyDisplay: '$290' },
} as const

function PricingContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  // Default to annual — it's the better value (2 months free) and the plan's preferred cycle.
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('yearly')
  const [isLoadingCheckout, setIsLoadingCheckout] = useState<string | null>(null)
  const pricingVariant = useFeatureFlagVariantKey('pricing-experiment')
  // Declared up here (before handleUpgrade, which reads it) so there's no forward reference.
  const priceConfig = pricingVariant === 'price_29' ? PRICE_VARIANTS.price_29 : PRICE_VARIANTS.control
  const hasTrackedPricingView = useRef(false)
  const hasTrackedVariantExposure = useRef(false)

  // The pricing page is publicly reachable; only fetch account-scoped data for
  // signed-in users so guests see the plain guest/free-tier view, not a 401 error card.
  const { data: currentUser } = useQuery<CurrentUser | null>({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const isAuthenticated = Boolean(currentUser)

  const { data: subscription, isError: subscriptionError, error: subscriptionErrorData, refetch: refetchSubscription, isFetching: subscriptionFetching } = useQuery({
    queryKey: queryKeys.subscription(),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: isAuthenticated,
  })

  const { data: usage, isError: usageError, error: usageErrorData, refetch: refetchUsage, isFetching: usageFetching } = useQuery({
    queryKey: queryKeys.usage(),
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
      // Tag the checkout with the A/B arm ('control' when the flag is unset) so the funnel splits cleanly.
      const variant = typeof pricingVariant === 'string' ? pricingVariant : 'control'
      analytics.checkoutStarted('pro', priceValue, billingCycle, variant)
      await checkoutMutation.mutateAsync(priceId)
    } catch {
      // Error handled in mutation
    }
  }

  // A reverse-trial user is `is_pro` but hasn't paid yet, so they must still be able to pick a
  // billing cycle and convert. Only a *paid* (active, non-trial) subscriber has nothing to buy —
  // treating every `is_pro` user as "Current Plan" dead-ends trial users on the upgrade button.
  const isTrialing = subscription?.status === 'trialing'
  const isPaidPro = Boolean(subscription?.is_pro) && !isTrialing

  // Beta members get Pro free via the 100%-off forever promo (applied server-side at checkout).
  // Reframe the Pro card so they don't bounce off the $390 sticker — they pay $0 with no card.
  const showBetaOffer = Boolean(currentUser?.is_beta) && !isPaidPro

  // Claude-style pricing: always surface the effective MONTHLY cost, with a "Billed monthly/annually"
  // sub-note. The actual charge (priceConfig.monthly/.yearly + the priceId) is unchanged — this only
  // reframes the DISPLAY so users compare one per-month number across cycles.
  const fmtUsd = (n: number) => (Number.isInteger(n) ? `$${n}` : `$${n.toFixed(2)}`)
  const proMonthlyEquivalent = billingCycle === 'monthly' ? priceConfig.monthly : priceConfig.yearly / 12
  const proPriceDisplay = fmtUsd(proMonthlyEquivalent)
  const billingNote = billingCycle === 'monthly' ? 'Billed monthly' : 'Billed annually'

  const plans = [
    {
      name: 'Free',
      price: '$0',
      period: 'forever',
      description: 'For trying out EarningsNerd',
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
      betaOriginal: null,
      billingNote: null,
    },
    {
      name: 'Pro',
      price: showBetaOffer ? '$0' : proPriceDisplay,
      period: 'per month',
      betaOriginal: showBetaOffer ? proPriceDisplay : null,
      billingNote: showBetaOffer ? null : billingNote,
      description: 'For professionals who need unlimited access',
      features: [
        'Unlimited summaries',
        'Unlimited Multi-Period Analysis: 10-year trends, quarterly deltas & AI narrative',
        'Ask this Filing: Get answers on any filing',
        'Hourly filing alerts',
        '8-K filing alerts',
        'PDF, CSV & Excel exports',
        'Priority support',
      ],
      cta: isPaidPro ? 'Current Plan' : showBetaOffer ? 'Claim Pro' : isTrialing ? 'Subscribe to Pro' : 'Upgrade to Pro',
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
          <h2 className="text-4xl font-semibold text-text-heading-light dark:text-text-heading-dark mb-4">Pricing</h2>
          <p className="text-lg text-text-secondary-light dark:text-text-secondary-dark max-w-2xl mx-auto">
            Choose the plan that works for you. Upgrade or downgrade at any time.
          </p>

          {(subscriptionError || usageError) && (
            <div className="mt-6 mx-auto max-w-2xl text-left">
              <Notice
                variant="error"
                title="We couldn't load all pricing details"
                description={
                  subscriptionErrorData instanceof Error
                    ? subscriptionErrorData.message
                    : usageErrorData instanceof Error
                    ? usageErrorData.message
                    : 'Please retry.'
                }
                action={
                  <>
                    <Button variant="secondary" size="sm" onClick={() => refetchSubscription()} loading={subscriptionFetching} loadingText="Retrying…">
                      Retry subscription
                    </Button>
                    <Button variant="secondary" size="sm" onClick={() => refetchUsage()} loading={usageFetching} loadingText="Retrying…">
                      Retry usage
                    </Button>
                  </>
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
              <Switch
                checked={billingCycle === 'yearly'}
                aria-label="Billing cycle"
                onCheckedChange={(next) => {
                  const nextCycle = next ? 'yearly' : 'monthly'
                  analytics.billingCycleToggled(billingCycle, nextCycle)
                  setBillingCycle(nextCycle)
                }}
              />
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
                    className="bg-info-light dark:bg-info-dark h-2 rounded-full transition-[width] duration-base"
                    style={{ width: `${(usage.summaries_used / usage.summaries_limit) * 100}%` }}
                  />
                </div>
              )}
            </div>
          </div>
        )}

        {/* Beta member: Pro is free via the 100%-off forever promo. Make that unmistakable so a
            beta user doesn't bounce off the $390 sticker and settle for Free. */}
        {showBetaOffer && (
          <div className="mb-8 mx-auto max-w-2xl rounded-2xl border border-brand-strong/40 bg-brand-strong/10 p-5 text-center dark:border-brand-strong-dark/40 dark:bg-brand-strong-dark/15">
            <p className="text-base font-semibold text-text-heading-light dark:text-text-heading-dark">
              You&apos;re a beta member. Pro is on us.
            </p>
            <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Click <span className="font-semibold text-brand-strong dark:text-brand-strong-dark">Claim Pro</span> below.
              The beta discount applies automatically, so your total is{' '}
              <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">$0</span> and{' '}
              <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">no credit card</span> is required.
            </p>
          </div>
        )}

        {/* Pricing Cards */}
        <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              elevation={plan.popular ? 'e3' : 'e2'}
              className={`relative p-8 ${
                plan.popular ? 'ring-1 ring-inset ring-brand-strong dark:ring-brand-dark' : ''
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <Badge variant="solid">Most Popular</Badge>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">{plan.name}</h3>
                <div className="flex items-baseline justify-center gap-2">
                  <span className="tabular text-5xl font-semibold text-text-primary-light dark:text-text-primary-dark">{plan.price}</span>
                  {plan.betaOriginal ? (
                    <span className="tabular text-2xl font-medium text-text-secondary-light line-through dark:text-text-secondary-dark">{plan.betaOriginal}/mo</span>
                  ) : (
                    plan.period !== 'forever' && (
                      <span className="text-text-secondary-light dark:text-text-secondary-dark">/month</span>
                    )
                  )}
                </div>
                {plan.billingNote && (
                  <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">{plan.billingNote}</p>
                )}
                {plan.betaOriginal && (
                  <p className="mt-1 text-sm font-semibold text-brand-strong dark:text-brand-strong-dark">Free for beta members · no card required</p>
                )}
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

              <Button
                variant={plan.popular ? 'primary' : 'secondary'}
                size="lg"
                className="w-full"
                onClick={() => (plan.priceId ? handleUpgrade(plan.priceId) : router.push('/register'))}
                disabled={plan.disabled || (isAuthenticated && !plan.priceId)}
                loading={plan.priceId !== null && isLoadingCheckout === plan.priceId}
                loadingText="Processing..."
              >
                {plan.cta}
              </Button>
            </Card>
          ))}
        </div>

        {/* FAQ */}
        <div className="mt-16 max-w-3xl mx-auto">
          <h2 className="text-2xl font-semibold text-text-heading-light dark:text-text-heading-dark mb-8 text-center">Frequently Asked Questions</h2>
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
                You can cancel anytime and keep Pro until the end of the period you&apos;ve paid for,
                with no further charges. Except where required by law, fees already paid are
                non-refundable (see our Terms). If something isn&apos;t working right, contact us and
                we&apos;ll make it right.
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
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    }>
      <PricingContent />
    </Suspense>
  )
}

