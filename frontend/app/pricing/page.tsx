'use client'

import { useState, Suspense, useRef, useEffect, useCallback, useId } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { createCheckoutSession, getSubscriptionStatus, getUsage } from '@/features/subscriptions/api/subscriptions-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getRegistrationConfig } from '@/features/marketing/api/access-api'
import { ACCESS_COPY, resolveAccessMode } from '@/features/marketing/lib/access'
import { isApiError, getErrorMessage } from '@/lib/api/types'
import { CheckIcon } from '@/lib/icons'
import { useRouter, useSearchParams } from 'next/navigation'
import SecondaryHeader from '@/components/SecondaryHeader'
import { Button, Card, Notice, Switch } from '@/components/ui'
import analytics from '@/lib/analytics'
import { ENABLE_PRO_TRIAL } from '@/lib/featureFlags'
import { queryKeys } from '@/lib/queryKeys'
import { ANALYSIS_LINES, FILING_FORMS_LINE, FREE_SUMMARY_LIMIT, TRIAL_DAYS, shipped } from '@/lib/planLimits'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { PRO_PRICING } from './prices'
import { billingCycleFromQuery, pricingHref, type BillingCycle } from '@/features/subscriptions/lib/pricingRoute'
import { takeCarriedReturnNotice, useCarryReturnNotice } from '@/features/subscriptions/lib/returnNotice'
import { registerHrefWithRedirect, stashPostAuthRedirect } from '@/lib/postAuthRedirect'

interface CurrentUser {
  id: number
  email: string
  is_pro?: boolean
  is_beta?: boolean
  email_verified?: boolean
}

// The approved offer lives in ./prices, shared with the homepage and Product JSON-LD.

// The ONLY consumer of useSearchParams() on this page, isolated so it is the only thing inside the
// Suspense boundary. useSearchParams() bails its nearest Suspense subtree out of the server HTML;
// while it lived in PricingContent the whole body (H1, plans, prices, FAQ) shipped as the spinner
// fallback and crawlers saw no content. Renders nothing — it resolves the incoming billing cycle
// and reacts to Stripe's return params without removing the plans from server HTML.
function PricingQueryEffects({ onBillingResolved, onCheckoutCanceled }: {
  onBillingResolved: (cycle: BillingCycle) => void
  onCheckoutCanceled: () => void
}) {
  const router = useRouter()
  const searchParams = useSearchParams()
  const requestedBilling = searchParams.get('billing')
  const checkoutCanceled = searchParams.get('canceled') === 'true'

  useEffect(() => {
    onBillingResolved(billingCycleFromQuery(requestedBilling))
  }, [requestedBilling, onBillingResolved])

  // Stripe's cancel_url (backend routers/subscriptions.py) returns here with ?canceled=true; the page
  // says so beside its intro. The flag is read once, then dropped from the address (other params kept),
  // so a reload, a history entry or a bookmark of the return URL does not say it again. Presentation
  // only: nothing about the plan or checkout changes.
  useEffect(() => {
    if (!checkoutCanceled) return
    onCheckoutCanceled()
    const rest = new URLSearchParams(searchParams.toString())
    rest.delete('canceled')
    const query = rest.toString()
    router.replace(query ? `/pricing?${query}` : '/pricing', { scroll: false })
  }, [checkoutCanceled, searchParams, router, onCheckoutCanceled])

  useEffect(() => {
    // Handle success from Stripe: refresh subscription status
    if (searchParams.get('success') === 'true') {
      router.refresh()
    }
  }, [searchParams, router])

  return null
}

function PricingContent({ billingCycle, setBillingCycle, billingResolved, checkoutCanceled }: {
  billingCycle: BillingCycle
  setBillingCycle: (cycle: BillingCycle) => void
  billingResolved: boolean
  checkoutCanceled: boolean
}) {
  const router = useRouter()
  const yearlyLabelId = useId()
  const [isLoadingCheckout, setIsLoadingCheckout] = useState<string | null>(null)
  const [checkoutError, setCheckoutError] = useState<string | null>(null)
  const checkoutErrorRef = useRef<HTMLDivElement>(null)
  const hasTrackedPricingView = useRef(false)

  // The pricing page is publicly reachable; only fetch account-scoped data for
  // signed-in users so guests see the plain guest/free-tier view, not a 401 error card.
  const identityQuery = useQuery<CurrentUser | null>({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const { data: currentUser, isError: identityError } = identityQuery
  // `undefined` is an unresolved identity (pending, or failed without data); only `null` is a
  // confirmed guest. Conflating the two labelled Free "Current plan" and armed checkout before
  // anything was known about the account.
  const identityResolved = currentUser !== undefined
  const isGuest = currentUser === null
  const isAuthenticated = Boolean(currentUser)

  const subscriptionQuery = useQuery({
    queryKey: queryKeys.subscription.byUser(currentUser?.id),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!currentUser,
  })
  const { data: subscription, isError: subscriptionError } = subscriptionQuery

  const usageQuery = useQuery({
    queryKey: queryKeys.usage.byUser(currentUser?.id),
    queryFn: getUsage,
    retry: false,
    enabled: !!currentUser,
  })
  const { data: usage, isError: usageError } = usageQuery

  // The Free plan's account CTA follows the page-wide access decision (invite-only or public), read
  // from the same payload the landing page reads on the server. Until it answers, and when it
  // cannot, the CTA fails closed to the invite copy, so the Free card never advertises a signup
  // /register would reject (audit T9). The Pro card's guest path is the upgrade flow's own: it
  // still routes a guest through /register, which applies the gate itself.
  const { data: registration } = useQuery({
    queryKey: queryKeys.registrationConfig(),
    queryFn: getRegistrationConfig,
    retry: false,
    staleTime: 60 * 60 * 1000,
  })
  const access = ACCESS_COPY[resolveAccessMode(registration ?? null)]

  // What the error Notices show. A failure keeps its Notice (and a focused Retry in it) through any
  // refetch until data replaces it.
  const identityFailure = useRetainedFailure(identityQuery, queryKeys.currentUser())
  const subscriptionFailure = useRetainedFailure(subscriptionQuery, queryKeys.subscription.byUser(currentUser?.id))
  const usageFailure = useRetainedFailure(usageQuery, queryKeys.usage.byUser(currentUser?.id))

  // Account readiness for plan labels and the buy action. A guest is fully resolved; a known
  // user needs a subscription snapshot. Retained same-account data counts: a failed refresh
  // alone does not un-know the plan (the server re-checks entitlement at checkout). A usage
  // failure never blocks a plan decision.
  const subscriptionResolved = subscription !== undefined
  const accountResolved = billingResolved && (isGuest || (isAuthenticated && subscriptionResolved))
  const accountFailed = !accountResolved && (identityError || (isAuthenticated && subscriptionError))
  const identityUnavailable = identityFailure.failed && !identityResolved
  const subscriptionStale = subscriptionError && subscriptionResolved

  // A Retry that unmounts while it holds focus (its Notice clears) hands focus to the intro line the
  // Notice sat under (RetryButton).
  const introRef = useRef<HTMLParagraphElement>(null)

  useEffect(() => {
    if (billingResolved && !hasTrackedPricingView.current) {
      analytics.pricingViewed(billingCycle)
      hasTrackedPricingView.current = true
    }
  }, [billingCycle, billingResolved])

  useEffect(() => {
    // The Notice renders above the plan grid, so on a phone the CTA that failed sits a screen below
    // it. Bring a new error into view (an instant jump, so reduced motion needs no special case).
    if (checkoutError) checkoutErrorRef.current?.scrollIntoView?.({ block: 'center' })
  }, [checkoutError])

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
      setCheckoutError(errorMessage)
      setIsLoadingCheckout(null)
    },
  })

  const handleUpgrade = async (priceId: string) => {
    // Decide from resolved data only, before any loading state, analytics event or request: an
    // unresolved identity or a missing subscription snapshot is not a purchase decision.
    if (!billingResolved || !identityResolved) return
    // Guests can't create a checkout session (401) — send them to sign up, then back here.
    if (isGuest) {
      const destination = pricingHref(billingCycle)
      stashPostAuthRedirect(destination)
      router.push(registerHrefWithRedirect(destination))
      return
    }
    if (!subscription || subscription.is_pro) return
    if (isLoadingCheckout) return
    setCheckoutError(null)
    setIsLoadingCheckout(priceId)
    try {
      const priceValue = billingCycle === 'monthly' ? PRO_PRICING.monthly : PRO_PRICING.yearly
      analytics.checkoutStarted('pro', priceValue, billingCycle)
      await checkoutMutation.mutateAsync(priceId)
    } catch {
      // Error handled in mutation
    }
  }

  // A trialing user on the CARD-REQUIRED Stripe trial already holds a live subscription that
  // auto-charges at trial end — so for the buy CTA they are a CURRENT-PLAN user, not a prospect.
  // (The old rule let trialing users click through to checkout; that was written for the retired
  // no-card reverse trial and would now create a SECOND live subscription — double-billing plus
  // a webhook hazard when the orphaned sub later cancels. Staff review, PR #619.)
  // isPaidPro stays distinct so copy can say "Current plan (trial)" vs "Current plan".
  // Expired trial rows can retain their Stripe status after the API resolves them to Free.
  const isTrialing = Boolean(subscription?.is_pro) && subscription?.status === 'trialing'
  const isPaidPro = Boolean(subscription?.is_pro) && !isTrialing

  // Beta members get Pro free via the 100%-off forever promo (applied server-side at checkout).
  // Reframe the Pro card around their $0 total with no card.
  // Waits for the subscription snapshot: "Claim Pro" must not appear before Pro is ruled out.
  const showBetaOffer = Boolean(currentUser?.is_beta) && subscriptionResolved && !isPaidPro

  // Client-side mirror of the checkout's trial rule (create_checkout_session): first-time
  // subscriber (no Subscription row → status null; guests count too) + MONTHLY cycle + not beta.
  // Display-only — the server decides authoritatively at checkout, so a stale read can't
  // over-promise a trial Stripe won't grant… it just words the button differently.
  // For a signed-in user, wait for the subscription query to RESOLVE (`subscription` set) before
  // claiming eligibility — while it loads, `!subscription?.status` would read trial-eligible and
  // flash the trial CTA at repeat subscribers (Gemini review, PR #619).
  // ENABLE_PRO_TRIAL keeps the copy dark until the backend's PRO_TRIAL_DAYS is live (lockstep).
  const trialEligible =
    ENABLE_PRO_TRIAL &&
    billingCycle === 'monthly' &&
    !showBetaOffer &&
    !isPaidPro &&
    !isTrialing &&
    (isGuest || Boolean(subscription && !subscription.status))

  // The headline is the per-month price; annual states its full charge and saving beneath it.
  const proPriceDisplay = billingCycle === 'monthly' ? PRO_PRICING.monthlyDisplay : PRO_PRICING.yearlyPerMonthDisplay
  const billingNote = billingCycle === 'monthly'
    ? 'Billed monthly'
    : `Billed annually at ${PRO_PRICING.yearlyDisplay}, saving ${PRO_PRICING.annualSavingsDisplay} a year.`

  // Shared label while account data is absent; neither card may claim a current plan or a
  // purchase decision until the account resolves (or the visitor is a confirmed guest).
  const unresolvedCta = accountFailed ? 'Plan unavailable' : 'Checking your plan…'

  const handleGetStartedFree = () => {
    // Same readiness as the buy action: an unresolved identity is not a guest.
    if (!identityResolved || isAuthenticated) return
    router.push(access.href)
  }

  const plans = [
    {
      name: 'Free',
      price: '$0',
      period: 'forever',
      description: 'For reading a few filings a month',
      // 20-F lists only while NEXT_PUBLIC_ENABLE_FPI_FILINGS mirrors the API's flag (tasks/todo.md F39):
      // lib/planLimits.ts FILING_FORMS_LINE, read through shipped().
      features: shipped([
        { text: `${FREE_SUMMARY_LIMIT} summaries per month` },
        FILING_FORMS_LINE,
        { text: 'The same summaries Pro reads' },
        { text: 'Company search' },
        { text: 'Historical filing access' },
      ]),
      // Only the genuinely-free user is "on" the Free plan. A Pro user (paid or trialing) would
      // otherwise see "Current plan" on BOTH cards, which reads as a contradiction. Nor is a Pro
      // account offered the guest's access CTA ("Request an invite" or "Create a free account") for
      // a plan it does not need: its disabled Free button names the plan, a fact and no call to action.
      cta: !accountResolved
        ? unresolvedCta
        : !isAuthenticated
        ? access.cta
        : subscription?.is_pro
        ? 'Free plan'
        : 'Current plan',
      disabled: !accountResolved || isAuthenticated,
      priceId: null,
      betaOriginal: null,
      billingNote: null,
      trialNote: null,
    },
    {
      name: 'Pro',
      price: showBetaOffer ? '$0' : proPriceDisplay,
      period: 'per month',
      betaOriginal: showBetaOffer ? proPriceDisplay : null,
      billingNote: showBetaOffer ? null : billingNote,
      description: 'For deeper filing research',
      // Multi-Period Analysis and its Excel workbook list only while the analysis route ships (it 404s
      // with the flag off): lib/planLimits.ts types those lines once and shipped() reads the flag.
      features: shipped([
        { text: 'Unlimited summaries' },
        ANALYSIS_LINES.pricingPro,
        { text: 'Ask this Filing, with cited passages you can check' },
        { text: 'Hourly filing alerts' },
        { text: '8-K filing alerts' },
        ANALYSIS_LINES.exports,
        { text: 'Priority support' },
      ]),
      cta: !accountResolved
        ? unresolvedCta
        : isPaidPro
        ? 'Current plan'
        : isTrialing
        ? 'Current plan (trial)'
        : showBetaOffer
        ? 'Claim Pro'
        : trialEligible
        ? `Start ${TRIAL_DAYS}-day free trial`
        : 'Upgrade to Pro',
      // Trialing counts as current-plan: their card-required trial IS a live subscription that
      // auto-charges at trial end; an enabled buy button here creates a duplicate (see comment
      // above isTrialing). Existing subscribers manage billing from their account settings.
      disabled: !accountResolved || isPaidPro || isTrialing,
      priceId: billingCycle === 'monthly' ? 'price_pro_monthly' : 'price_pro_yearly',
      popular: true,
      trialNote: trialEligible ? `First ${TRIAL_DAYS} days free · cancel anytime, no charge` : null,
    },
  ]

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader
        title="Pricing"
        subtitle="One summary per filing, generated once and shared"
        backHref="/"
        backLabel="Back to home"
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <div className="text-center mb-12">
          {/* SecondaryHeader already renders the page H1 ("Pricing"); no duplicate heading here. */}
          <p ref={introRef} tabIndex={-1} className="text-lg text-text-secondary-light dark:text-text-secondary-dark max-w-2xl mx-auto outline-none">
            Summaries are generated once per filing and shared. That is what makes unlimited reading
            possible at this price. Pro is billed monthly or annually, and you can upgrade or
            downgrade at any time.
          </p>

          {/* The return URL says only that the visitor came back from Stripe's checkout, not what was charged,
              so the notice claims no payment outcome. The plan, once the subscription query resolves, is the
              one fact it adds. */}
          {checkoutCanceled && (
            <div className="mt-6 mx-auto max-w-2xl text-left">
              <Notice
                variant="info"
                title="You returned from checkout"
                description={
                  !accountResolved ? undefined : subscription?.is_pro ? 'Your plan is Pro.' : 'You can choose a plan below.'
                }
              />
            </div>
          )}

          {identityUnavailable ? (
            // Identity failed with nothing retained: an account error, not a guest view. Each Notice is
            // keyed: unkeyed, React would reuse the account Notice's Retry as the details Notice's when one
            // Notice replaces the other, and a Retry must never outlive its Notice (RetryButton).
            <div key="identity" className="mt-6 mx-auto max-w-2xl text-left">
              <Notice
                variant="error"
                title="We couldn't check your account"
                description={identityFailure.error instanceof Error ? identityFailure.error.message : 'Please try again.'}
                action={<RetryButton size="sm" failures={[identityFailure]} focusTarget={introRef} />}
              />
            </div>
          ) : (subscriptionFailure.failed || usageFailure.failed) && (
            <div key="details" className="mt-6 mx-auto max-w-2xl text-left">
              <Notice
                variant="error"
                title={subscriptionStale ? "We couldn't refresh your plan details" : "We couldn't load all pricing details"}
                description={
                  subscriptionStale
                    ? 'Showing your last loaded plan. Try again to refresh it.'
                    : subscriptionFailure.error instanceof Error
                    ? subscriptionFailure.error.message
                    : usageFailure.error instanceof Error
                    ? usageFailure.error.message
                    : 'Please try again.'
                }
                // One Retry for both reads: a press retries only the failed ones (RetryButton), and two
                // buttons with the one label side by side could not say which read each retries.
                action={<RetryButton size="sm" failures={[subscriptionFailure, usageFailure]} focusTarget={introRef} />}
              />
            </div>
          )}

          {/* Billing Toggle — free users only. A card-trial user already holds a subscription
              (their buy CTA is disabled as current-plan), so the toggle would only move a
              button they can't press. */}
          {!isPaidPro && !isTrialing && (
            <div className="mt-8 flex items-center justify-center space-x-4">
              <span className={`text-sm font-medium ${billingCycle === 'monthly' ? 'text-text-primary-light dark:text-text-primary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>
                Monthly
              </span>
              {/* Named by the cycle it turns on, its visible "Yearly" label, so a screen reader hears
                  "Yearly (save N%), switch, on"; off is monthly. A category name ("Billing cycle")
                  left on and off meaning nothing. */}
              <Switch
                checked={billingCycle === 'yearly'}
                aria-labelledby={yearlyLabelId}
                onCheckedChange={(next) => {
                  const nextCycle = next ? 'yearly' : 'monthly'
                  analytics.billingCycleToggled(billingCycle, nextCycle)
                  setBillingCycle(nextCycle)
                }}
              />
              <span id={yearlyLabelId} className={`text-sm font-medium ${billingCycle === 'yearly' ? 'text-text-primary-light dark:text-text-primary-dark' : 'text-text-secondary-light dark:text-text-secondary-dark'}`}>
                Yearly <span className="font-semibold">(save {PRO_PRICING.annualSavingsPercent}%)</span>
              </span>
            </div>
          )}
        </div>

        {/* Usage Stats */}
        {usage && !usageError && (
          <div className="mb-8 bg-info-light/10 border border-info-light/40 rounded-lg p-4 max-w-2xl mx-auto dark:bg-info-dark/15 dark:border-info-dark/40">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-info-text dark:text-info-dark">Current usage</p>
                <p className="text-sm text-info-text dark:text-info-dark">
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

        {/* Beta member: Pro is free via the 100%-off forever promo. Make their $0 total clear. */}
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

        {checkoutError && (
          <div ref={checkoutErrorRef} className="mb-8 mx-auto max-w-2xl">
            <Notice variant="error" title="Checkout didn't start" description={checkoutError} />
          </div>
        )}

        {/* Pricing Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 max-w-4xl mx-auto">
          {plans.map((plan) => (
            <Card
              key={plan.name}
              elevation={plan.popular ? 'e3' : 'e2'}
              className={`relative p-6 sm:p-8 ${
                plan.popular ? 'ring-1 ring-inset ring-brand-strong dark:ring-brand-dark' : ''
              }`}
            >
              {/* No "Most popular" badge: the beta has no popularity figure behind one, and the brand ring
                  already carries the emphasis. */}
              <div className="text-center mb-6">
                {/* h2: each plan is a top-level section of the page, beside the FAQ (no h1 → h3 skip). */}
                <h2 className="text-2xl font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">{plan.name}</h2>
                <div className="flex items-baseline justify-center gap-2">
                  <span className="tabular text-5xl font-semibold text-text-primary-light dark:text-text-primary-dark">{plan.price}</span>
                  {plan.betaOriginal ? (
                    // The strike is visual only, so a screen reader is told which price this is.
                    <span className="tabular text-2xl font-medium text-text-secondary-light line-through dark:text-text-secondary-dark">
                      <span className="sr-only">Regular price</span>{' '}{plan.betaOriginal}/mo
                    </span>
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
                {plan.trialNote && (
                  <p className="mt-1 text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{plan.trialNote}</p>
                )}
                <p className="text-text-secondary-light dark:text-text-secondary-dark mt-2">{plan.description}</p>
              </div>

              <ul className="space-y-4 mb-8">
                {plan.features.map((feature, index) => (
                  <li key={index} className="flex items-start">
                    <CheckIcon aria-hidden="true" className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark mr-3 flex-shrink-0 mt-0.5" />
                    <span className="text-text-secondary-light dark:text-text-secondary-dark">{feature}</span>
                  </li>
                ))}
              </ul>

              <Button
                variant={plan.popular ? 'primary' : 'secondary'}
                size="lg"
                wrap
                className="w-full"
                onClick={() => (plan.priceId ? handleUpgrade(plan.priceId) : handleGetStartedFree())}
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
          <h2 className="text-2xl font-semibold text-text-heading-light dark:text-text-heading-dark mb-8 text-center">Frequently asked questions</h2>
          <div className="space-y-6">
            <div>
              <h3 className="text-lg font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">
                How do I manage my subscription?
              </h3>
              <p className="text-text-secondary-light dark:text-text-secondary-dark">
                Manage your subscription, payment details and cancellation from your billing settings.
                Contact us for questions about changing your billing cycle.
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
            {ENABLE_PRO_TRIAL && (
              <div>
                <h3 className="text-lg font-semibold text-text-heading-light dark:text-text-heading-dark mb-2">
                  How does the {TRIAL_DAYS}-day free trial work?
                </h3>
                <p className="text-text-secondary-light dark:text-text-secondary-dark">
                  Subscribing to Pro monthly for the first time starts with {TRIAL_DAYS} days free. A card is
                  required to start the trial, but you won&apos;t be charged until the trial ends.
                  Cancel anytime in those {TRIAL_DAYS} days from your billing settings and you pay nothing.
                  After {TRIAL_DAYS} days, your subscription starts automatically. One trial per account.
                </p>
              </div>
            )}
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
  // Keep the annual server-rendered default. Only the isolated query reader may override it;
  // until it resolves, do not record a view or offer a checkout for the wrong incoming cycle.
  const [billingCycle, setBillingCycle] = useState<BillingCycle>('yearly')
  const [billingResolved, setBillingResolved] = useState(false)
  const [checkoutCanceled, setCheckoutCanceled] = useState(false)
  const noteCheckoutCanceled = useCallback(() => setCheckoutCanceled(true), [])
  // The flag is gone from the address once read, so a remount in the same commit (any parent that swaps
  // its element type) keeps the notice (features/subscriptions/lib/returnNotice.ts).
  useCarryReturnNotice('pricing-checkout-canceled', checkoutCanceled)
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- takes the notice a remount in this same commit carried; it exists only after the commit that unmounted the page showing it
    if (takeCarriedReturnNotice('pricing-checkout-canceled')) setCheckoutCanceled(true)
  }, [])
  const resolveBilling = useCallback((cycle: BillingCycle) => {
    setBillingCycle(cycle)
    setBillingResolved(true)
  }, [])

  return (
    <>
      <Suspense fallback={null}>
        <PricingQueryEffects onBillingResolved={resolveBilling} onCheckoutCanceled={noteCheckoutCanceled} />
      </Suspense>
      <PricingContent
        billingCycle={billingCycle}
        setBillingCycle={setBillingCycle}
        billingResolved={billingResolved}
        checkoutCanceled={checkoutCanceled}
      />
    </>
  )
}
