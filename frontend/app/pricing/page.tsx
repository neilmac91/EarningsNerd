'use client'

import { useState, Suspense } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { createCheckoutSession, getSubscriptionStatus, getUsage } from '@/lib/api'
import { Check, Sparkles, Loader2, ArrowRight, ShieldCheck, Lock, CreditCard } from 'lucide-react'
import Link from 'next/link'
import { useRouter, useSearchParams } from 'next/navigation'
import { useEffect } from 'react'
import Navbar from '@/components/Navbar'

function PricingContent() {
  const router = useRouter()
  const searchParams = useSearchParams()
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'yearly'>('monthly')
  const [isLoadingCheckout, setIsLoadingCheckout] = useState<string | null>(null)

  const { data: subscription } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
  })

  const { data: usage } = useQuery({
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
    onError: (error: any) => {
      alert(error.response?.data?.detail || 'Failed to create checkout session')
      setIsLoadingCheckout(null)
    },
  })

  const handleUpgrade = async (priceId: string) => {
    setIsLoadingCheckout(priceId)
    try {
      await checkoutMutation.mutateAsync(priceId)
    } catch (error) {
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
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <Navbar />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 animate-fadeIn">
        <div className="text-center mb-12">
          <h1 className="text-4xl font-bold text-gray-900 mb-4">Pricing</h1>
          <p className="text-lg text-gray-600 max-w-2xl mx-auto">
            Choose the plan that works for you. Upgrade or downgrade at any time.
          </p>

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
        {usage && (
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
              className={`relative rounded-3xl border p-8 backdrop-blur-xl transition-all ${
                plan.popular
                  ? 'border-primary-500/60 bg-gradient-to-br from-white via-white to-primary-50 shadow-2xl shadow-primary-500/20 dark:border-primary-400/60 dark:from-slate-900/80 dark:via-slate-900/60 dark:to-slate-950 dark:shadow-primary-500/20'
                  : 'border-gray-200/70 bg-white/80 shadow-xl shadow-gray-900/5 dark:border-white/10 dark:bg-slate-900/70 dark:shadow-black/30'
              }`}
            >
              {plan.popular && (
                <div className="absolute -top-4 left-1/2 -translate-x-1/2">
                  <span className="bg-primary-600 text-white px-4 py-1 rounded-full text-sm font-medium shadow-lg shadow-primary-500/30">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="text-center mb-6">
                <h3 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">{plan.name}</h3>
                <div className="flex items-baseline justify-center">
                  <span className="text-5xl font-bold text-gray-900 dark:text-white">{plan.price}</span>
                  {plan.period !== 'forever' && (
                    <span className="text-gray-600 dark:text-slate-300 ml-2">/{plan.period}</span>
                  )}
                </div>
                <p className="text-gray-600 dark:text-slate-300 mt-2">{plan.description}</p>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, index) => (
                  <li key={index} className="flex items-start">
                    <Check className="h-5 w-5 text-green-500 mr-3 flex-shrink-0 mt-0.5" />
                    <span className="text-gray-700 dark:text-slate-200">{feature}</span>
                  </li>
                ))}
              </ul>

              <button
                onClick={() => plan.priceId && handleUpgrade(plan.priceId)}
                disabled={plan.disabled || !plan.priceId || isLoadingCheckout === plan.priceId}
                className={`w-full py-3 px-4 rounded-full font-semibold transition-colors ${
                  plan.disabled
                    ? 'bg-gray-100 text-gray-400 cursor-not-allowed dark:bg-slate-800/60 dark:text-slate-500'
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

        {/* Trust Signals */}
        <div className="mt-8 flex flex-wrap items-center justify-center gap-3 text-xs text-gray-600 dark:text-slate-300">
          <span className="inline-flex items-center gap-2 rounded-full border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-4 py-2">
            <ShieldCheck className="h-4 w-4 text-green-600" />
            Secured by Stripe
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-4 py-2">
            <Lock className="h-4 w-4 text-blue-600" />
            SSL encrypted checkout
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-4 py-2">
            <CreditCard className="h-4 w-4 text-purple-600" />
            Visa, Mastercard, AmEx
          </span>
          <span className="inline-flex items-center gap-2 rounded-full border border-gray-200 dark:border-white/10 bg-white dark:bg-slate-900 px-4 py-2">
            <Sparkles className="h-4 w-4 text-amber-500" />
            30-day money-back guarantee
          </span>
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
                You'll need to upgrade to Pro to generate more summaries. Your existing summaries remain accessible.
              </p>
            </div>
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-2">
                Do you offer refunds?
              </h3>
              <p className="text-gray-600">
                We offer a 30-day money-back guarantee for Pro subscriptions. Contact us if you're not satisfied.
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
      <div className="min-h-screen bg-slate-50 flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    }>
      <PricingContent />
    </Suspense>
  )
}

