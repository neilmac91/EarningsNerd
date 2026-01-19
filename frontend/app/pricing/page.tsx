'use client'

import { useState, Suspense } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { createCheckoutSession, getSubscriptionStatus, getUsage } from '@/lib/api'
import { Check, Loader2 } from 'lucide-react'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect } from 'react'
import { ThemeToggle } from '@/components/ThemeToggle'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'

function PricingContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const [isLoadingCheckout, setIsLoadingCheckout] = useState<string | null>(null)

  const { data: subscription, isError: subscriptionError, error: subscriptionErrorData, refetch: refetchSubscription, isFetching: subscriptionFetching } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
  })

  const { data: usage, isError: usageError, error: usageErrorData, refetch: refetchUsage, isFetching: usageFetching } = useQuery({
    queryKey: ['usage'],
    queryFn: getUsage,
    retry: false,
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

  const checkoutMutation = useMutation({
    mutationFn: createCheckoutSession,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url
      }
    },
    onError: (error: unknown) => {
      const axiosErr = error as { response?: { data?: { detail?: string } } }
      alert(axiosErr.response?.data?.detail || 'Failed to create checkout session')
      setIsLoadingCheckout(null)
    },
  })

  const handleUpgrade = async (priceId: string) => {
    setIsLoadingCheckout(priceId)
    try {
      await checkoutMutation.mutateAsync(priceId)
    } catch {
      // Error handled in mutation
    }
  }

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
      cta: 'Current Plan',
      disabled: true,
      priceId: null,
    },
    {
      name: 'Pro',
      price: billingCycle === 'monthly' ? '$19' : '$190',
      period: billingCycle === 'monthly' ? 'per month' : 'per year',
      description: 'For professionals who need unlimited access',
      features: [
        'Unlimited summaries',
        'Multi-year comparisons',
        'PDF & CSV exports',
        'Shareable links',
        'Priority support',
        'Advanced analytics',
      ],
      cta: subscription?.is_pro ? 'Current Plan' : 'Upgrade to Pro',
      disabled: subscription?.is_pro || false,
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
        actions={<ThemeToggle />}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 dark:text-white mb-4">Pricing</h1>
          <p className="text-lg text-gray-600 dark:text-slate-300 max-w-2xl mx-auto">
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
                      className="inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
                    >
                      {subscriptionFetching ? 'Retrying…' : 'Retry subscription'}
                    </button>
                    <button
                      type="button"
                      onClick={() => refetchUsage()}
                      disabled={usageFetching}
                      className="inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
                    >
                      {usageFetching ? 'Retrying…' : 'Retry usage'}
                    </button>
                  </div>
                }
              />
            </div>
          )}

          {/* Billing Toggle */}
          {!subscription?.is_pro && (
            <div className="mt-8 flex items-center justify-center space-x-4">
              <span className={`text-sm font-medium ${billingCycle === 'monthly' ? 'text-gray-900' : 'text-gray-500'}`}>
                Monthly
              </span>
              <button
                onClick={() => setBillingCycle(billingCycle === 'monthly' ? 'yearly' : 'monthly')}
                className="relative inline-flex h-6 w-11 items-center rounded-full bg-primary-600 transition-colors focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                    billingCycle === 'yearly' ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <span className={`text-sm font-medium ${billingCycle === 'yearly' ? 'text-gray-900' : 'text-gray-500'}`}>
                Yearly <span className="text-green-600">(Save 17%)</span>
              </span>
            </div>
          )}
        </div>

        {/* Usage Stats */}
        {usage && !usageError && (
          <div className="mb-8 bg-blue-50 border border-blue-200 rounded-lg p-4 max-w-2xl mx-auto">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-blue-900">Current Usage</p>
                <p className="text-sm text-blue-700">
                  {usage.summaries_used} / {usage.summaries_limit || '∞'} summaries used this month
                </p>
              </div>
              {!usage.is_pro && usage.summaries_limit && (
                <div className="w-32 bg-blue-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
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
                  ? 'border-primary-500 bg-white shadow-lg'
                  : 'border-gray-200 bg-white'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-primary-600 text-white px-4 py-1 rounded-full text-sm font-medium">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-gray-900 mb-2">{plan.name}</h3>
                <div className="flex items-baseline justify-center">
                  <span className="text-5xl font-bold text-gray-900">{plan.price}</span>
                  {plan.period !== 'forever' && (
                    <span className="text-gray-600 ml-2">/{plan.period}</span>
                  )}
                </div>
                <p className="text-gray-600 mt-2">{plan.description}</p>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, index) => (
                  <li key={index} className="flex items-start">
                    <Check className="h-5 w-5 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => plan.priceId && handleUpgrade(plan.priceId)}
                disabled={plan.disabled || !plan.priceId || isLoadingCheckout === plan.priceId}
                className={`w-full py-3 px-4 rounded-lg font-semibold transition-colors ${
                  plan.disabled
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                    : plan.popular
                    ? 'bg-primary-600 text-white hover:bg-primary-700'
                    : 'bg-gray-900 text-white hover:bg-gray-800'
                }`}
              >
                {isLoadingCheckout === plan.priceId ? (
                  <span className="flex items-center justify-center">
                    <Loader2 className="h-5 w-5 animate-spin mr-2" />
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
          <h2 className="text-2xl font-bold text-gray-900 mb-8 text-center">Frequently Asked Questions</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Can I change plans later?
              </h3>
              <p className="text-gray-600">
                Yes, you can upgrade or downgrade your plan at any time. Changes take effect immediately.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                What happens if I exceed my free limit?
              </h3>
              <p className="text-gray-600">
                You&apos;ll need to upgrade to Pro to generate more summaries. Your existing summaries remain accessible.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Do you offer refunds?
              </h3>
              <p className="text-gray-600">
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
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    }>
      <PricingContent />
    </Suspense>
  )
}

