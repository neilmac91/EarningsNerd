'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCurrentUserSafe, logout } from '@/features/auth/api/auth-api'
import { logoutAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { isConfirmedGuest } from '@/features/auth/lib/confirmedGuest'
import AccountLoadFailure from '@/features/auth/components/AccountLoadFailure'
import { getUsage, getSubscriptionStatus, createPortalSession } from '@/features/subscriptions/api/subscriptions-api'
import { getSavedSummaries, deleteSavedSummary, SavedSummary } from '@/features/summaries/api/summaries-api'
import { getWatchlistInsights } from '@/features/watchlist/api/watchlist-api'
import { useRouter } from 'next/navigation'
import { useEffect, useMemo, useRef, useState } from 'react'
import { CheckCircleIcon, LightningIcon, TrashIcon, WarningCircleIcon } from '@/lib/icons'
import Link from 'next/link'
import { formatLocalDate } from '@/lib/format'
import { toast } from 'sonner'
import SecondaryHeader from '@/components/SecondaryHeader'
import TrialBanner from '@/features/subscriptions/components/TrialBanner'
import { takeCarriedReturnNotice, useCarryReturnNotice } from '@/features/subscriptions/lib/returnNotice'
import CompanySearch from '@/features/companies/components/CompanySearch'
import FilingFeed from '@/features/dashboard/components/FilingFeed'
import EarningsCalendar from '@/features/dashboard/components/EarningsCalendar'
import YourCompanies from '@/features/dashboard/components/YourCompanies'
import { ENABLE_CALENDAR } from '@/lib/featureFlags'
import analytics from '@/lib/analytics'
import { Badge, Button, buttonVariants, Card, GuidanceCard, Notice, SkeletonStat, SkeletonText } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'
import { FREE_SUMMARY_LIMIT } from '@/lib/planLimits'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { untilPageReturns } from '@/lib/untilPageReturns'

export default function DashboardPage() {
  const router = useRouter()

  const userQuery = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  // isPending, not isLoading: a first load paused offline is still loading the page, not a blank one.
  const { data: user, isPending: userPending } = userQuery

  const usageQuery = useQuery({
    queryKey: queryKeys.usage.byUser(user?.id),
    queryFn: getUsage,
    retry: false,
    enabled: !!user,
  })
  const { data: usage, isLoading: usageLoading } = usageQuery

  const subscriptionQuery = useQuery({
    queryKey: queryKeys.subscription.byUser(user?.id),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!user,
  })
  const { data: subscription, isLoading: subscriptionLoading } = subscriptionQuery

  // A failure keeps the error card or plan strip (and a focused Retry in it) mounted through any refetch
  // until data replaces it. Read raw, the errored query, which has no data, goes back to pending, isLoading
  // turns true, and the page-wide skeleton replaces the button.
  const userFailure = useRetainedFailure(userQuery, queryKeys.currentUser())
  const usageFailure = useRetainedFailure(usageQuery, queryKeys.usage.byUser(user?.id))
  const subscriptionFailure = useRetainedFailure(subscriptionQuery, queryKeys.subscription.byUser(user?.id))
  const planFailed = usageFailure.failed || subscriptionFailure.failed

  const savedQuery = useQuery({
    queryKey: queryKeys.savedSummaries(),
    queryFn: getSavedSummaries,
    retry: false,
    enabled: !!user,
  })
  const { data: savedSummaries } = savedQuery
  const savedFailure = useRetainedFailure(savedQuery, queryKeys.savedSummaries())

  const insightsQuery = useQuery({
    queryKey: queryKeys.watchlistInsights(),
    queryFn: getWatchlistInsights,
    retry: false,
    enabled: !!user,
  })
  const { data: watchlistInsights, isLoading: insightsLoading } = insightsQuery
  // Your companies' Retry, as the two above: its skeleton branch would otherwise replace the error card.
  const insightsFailure = useRetainedFailure(insightsQuery, queryKeys.watchlistInsights())

  const queryClient = useQueryClient()

  // Focus targets for controls that unmount while they hold focus: a Retry (RetryButton hands off) and
  // a deleted row's Delete (the effect below, only when focus fell to <body>).
  const titleRef = useRef<HTMLHeadingElement>(null)
  const savedHeadingRef = useRef<HTMLHeadingElement>(null)
  const planHeadingRef = useRef<HTMLHeadingElement>(null)
  // A successful empty result removes the saved section. Resolve after the commit, as Delete does,
  // so a keyboard Retry lands on the remaining saved heading or the next stable section.
  const savedRetryTarget = useMemo(() => ({
    get current() { return savedHeadingRef.current ?? planHeadingRef.current },
  }), [])
  const deletedId = useRef<number | null>(null)

  const deleteSummaryMutation = useMutation({
    mutationFn: deleteSavedSummary,
    onSuccess: (_data, id) => {
      deletedId.current = id
      toast.success('Saved summary removed')
      // Drop the row from the cache now, so it and its focused Delete go with the DELETE itself.
      // Waiting for the refetch instead is not enough: a refetch that fails resolves the
      // invalidation anyway and leaves the deleted row's Delete live, where a second Enter would
      // DELETE it again. The refetch then only confirms the list.
      queryClient.setQueryData<SavedSummary[]>(queryKeys.savedSummaries(), (items) => items?.filter((item) => item.id !== id))
      void queryClient.invalidateQueries({ queryKey: queryKeys.savedSummaries() })
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Couldn't delete that summary. Please try again.")
    },
  })
  const pendingDeleteId = deleteSummaryMutation.isPending ? deleteSummaryMutation.variables : null

  const portalMutation = useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      if (!data.url) {
        // 200 with no URL means the billing portal couldn't be created — don't leave a dead click.
        toast.error('Could not open the billing portal. Please try again.')
        return
      }
      window.location.href = data.url
      // Pending while the page leaves for Stripe, as BillingPanel's Manage billing: the button keeps
      // focus, and released any sooner a second Enter would open a second portal session.
      return untilPageReturns()
    },
    onError: (error) => {
      // Surfaces the backend detail (e.g. "No subscription found") instead of failing silently.
      toast.error(error instanceof Error ? error.message : 'Could not open the billing portal. Please try again.')
    },
  })

  const logoutMutation = useMutation({
    mutationFn: () => logoutAndResetAccount(queryClient, logout, (succeeded) => {
      if (!succeeded) return
      analytics.logout()
      router.push('/login')
      router.refresh()
    }),
    // Offline, a press still sends the logout and reports how it went, rather than waiting paused for the connection.
    networkMode: 'always',
  })

  // Only a confirmed guest leaves for /login: an unresolved user (a fetch paused offline, a failure) is not logged out,
  // and neither is a null still being read (isConfirmedGuest).
  const guest = isConfirmedGuest(userQuery)
  useEffect(() => {
    if (guest) router.push('/login')
  }, [guest, router])

  // A successful delete drops its row once saved summaries refetch. Land on the section heading, or
  // on the next section's when the last summary went and the section with it.
  useEffect(() => {
    const id = deletedId.current
    if (id === null || savedSummaries?.some((item) => item.id === id)) return
    deletedId.current = null
    if (document.activeElement !== document.body) return
    ;(savedHeadingRef.current ?? planHeadingRef.current)?.focus({ preventScroll: true })
  }, [savedSummaries])

  useEffect(() => {
    if (user?.id) {
      // Identify on the internal id only — no email/PII into PostHog person properties.
      analytics.identify(String(user.id), {
        plan: user.is_pro ? 'pro' : 'free',
      })
    }
  }, [user])

  // Stripe's success_url (backend routers/subscriptions.py) lands here with ?success=true. Read after
  // hydration from window.location, not useSearchParams(): that hook outside a Suspense boundary bails
  // the page out of the server HTML. The notice only reads the subscription query the page already
  // holds; the webhook can land after the redirect, so a plan still Free is not called Pro. The flag is
  // read once, then dropped from the address (other params kept), so a reload, a history entry or a
  // bookmark of the return URL does not announce a checkout again. A remount in the same commit (any
  // parent that swaps its element type) keeps the notice (features/subscriptions/lib/returnNotice.ts).
  const [checkoutReturned, setCheckoutReturned] = useState(false)
  useCarryReturnNotice('dashboard-checkout-success', checkoutReturned)
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    // One-shot post-hydration read of the return flag, as the filing page reads its URL flags; reading
    // window.location during render would mismatch the server HTML. Without the flag, the notice a remount
    // in this same commit carried, which exists only after the commit that unmounted the page showing it.
    if (params.get('success') !== 'true') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- the post-hydration reads above: the flag, or the carried notice
      if (takeCarriedReturnNotice('dashboard-checkout-success')) setCheckoutReturned(true)
      return
    }
    setCheckoutReturned(true)
    params.delete('success')
    const query = params.toString()
    router.replace(`${window.location.pathname}${query ? `?${query}` : ''}${window.location.hash}`, { scroll: false })
  }, [router])

  // One header for the skeleton and the loaded page. Usage and subscription only start once the user
  // resolves, so by the time the grid replaces the bones the header already carries the real name and
  // the Log out action, and the grid lands without a shift. The name arriving on a cold load moves
  // nothing either: SecondaryHeader's subtitle never sizes the header row.
  const header = (
    <SecondaryHeader
      titleRef={titleRef}
      title="Dashboard"
      subtitle={user ? `Welcome back, ${user.full_name || user.email}` : 'Welcome back'}
      backHref="/"
      backLabel="Back to home"
      actions={
        <button
          type="button"
          onClick={() => logoutMutation.mutate()}
          className="rounded-lg text-sm font-medium text-text-secondary-light hover:text-text-primary-light focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-secondary-dark dark:hover:text-text-primary-dark dark:focus-visible:shadow-ring-brand-dark"
        >
          Log out
        </button>
      }
    />
  )

  if (
    (userPending && !userFailure.failed) ||
    (usageLoading && !usageFailure.failed) ||
    (subscriptionLoading && !subscriptionFailure.failed)
  ) {
    return (
      <div className="min-h-screen bg-background-light dark:bg-background-dark">
        {/* The loaded page's own header, so the bones below sit where the grid lands. */}
        {header}
        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          {/* Layout-preserving bones on the loaded grid's own tracks (grid-cols-1 = minmax(0, 1fr)), so they
              hand off without a reflow. SkeletonText/Stat own role="status" — no wrapper role. */}
          <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
            <div className="space-y-8 lg:col-span-2">
              <Card className="p-cap-5"><SkeletonText lines={2} /></Card>
              <Card className="p-cap-5"><SkeletonText lines={4} /></Card>
              <Card className="p-cap-5"><SkeletonText lines={4} /></Card>
            </div>
            <div className="space-y-8">
              <Card className="p-cap-5"><SkeletonStat /></Card>
              <Card className="p-cap-5"><SkeletonText lines={3} /></Card>
            </div>
          </div>
        </main>
      </div>
    )
  }

  // The account could not be read and there is no user to show. A refetch that fails with the user in hand keeps the
  // page, as the watchlist and the admin section do.
  if (userFailure.failed && !user) {
    return <AccountLoadFailure failure={userFailure} focusTarget={titleRef} title="Unable to load your dashboard" />
  }

  if (!user) {
    return null
  }

  const usagePercentage = usage?.summaries_limit
    ? (usage.summaries_used / usage.summaries_limit) * 100
    : 0
  // Key the warning off the usage query (which also drives usagePercentage), NOT subscription, so a
  // transient subscription-API error can't flip it: a Pro user reads usage.is_pro (never warned) and
  // a free user near the cap still gets warned even if the subscription call flaked.
  const showUsageWarning = usagePercentage >= 80 && !usage?.is_pro && !usageFailure.failed
  // The warning states the account's own numbers (usage drives it, as above), never a plan pitch.
  const summariesLimit = usage?.summaries_limit ?? FREE_SUMMARY_LIMIT
  const summariesLeft = Math.max(0, summariesLimit - (usage?.summaries_used || 0))
  const hasSavedSummaries = Boolean(savedSummaries && savedSummaries.length > 0)
  const watchlistCount = watchlistInsights?.length

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      {header}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {checkoutReturned && subscription && (
          subscription.is_pro ? (
            <Notice variant="success" title="Pro is active" className="mb-6" />
          ) : (
            <Notice
              variant="info"
              title="Checkout finished"
              description="Your plan updates in a moment. Reload this page if it still shows Free."
              className="mb-6"
            />
          )
        )}

        {/* The trial's end date (renders only while the resolved plan is a live Pro trial) */}
        <TrialBanner isPro={subscription?.is_pro} status={subscription?.status} trialEnd={subscription?.trial_end} className="mb-6" />

        {/* Usage-warning banner surfaced at the top where it will actually be seen (the plan/usage
            strip lives in the side column). */}
        {showUsageWarning && (
          <div
            role="status"
            className="mb-6 flex flex-col gap-3 rounded-xl border border-warning-light/30 bg-warning-light/10 p-4 sm:flex-row sm:items-center sm:justify-between dark:border-warning-dark/30 dark:bg-warning-dark/10"
          >
            <div className="flex items-start gap-3">
              <WarningCircleIcon className="h-5 w-5 flex-shrink-0 text-warning-light dark:text-warning-dark" />
              <div>
                <p className="text-sm font-semibold text-warning-light dark:text-warning-dark">
                  {usagePercentage >= 100 ? 'Limit reached' : 'Almost at your limit'}
                </p>
                <p className="mt-0.5 text-sm text-warning-light dark:text-warning-dark">
                  {usagePercentage >= 100
                    ? `You've used all ${summariesLimit} summaries this month.`
                    : `You have ${summariesLeft} ${summariesLeft === 1 ? 'summary' : 'summaries'} left this month.`}
                </p>
              </div>
            </div>
            <Link href="/pricing" className={buttonVariants({ variant: 'primary', className: 'sm:flex-shrink-0' })}>
              Upgrade to Pro
            </Link>
          </div>
        )}

        {/* grid-cols-1 is minmax(0, 1fr): an implicit phone track would size to its widest row's
            min-content (a long company name beside its status badge) and scroll the page sideways. */}
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-3">
          {/* Main column: search, the "what changed" feed, and the watchlist status section. */}
          <div className="space-y-8 lg:col-span-2">
            <Card className="p-cap-5">
              <p className="mb-2 text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark">Find a company by name or ticker</p>
              <CompanySearch />
            </Card>

            <FilingFeed enabled={!!user} watchlistCount={watchlistCount} />

            <YourCompanies
              insights={watchlistInsights}
              isLoading={insightsLoading && !insightsFailure.failed}
              failure={insightsFailure}
            />
          </div>

          {/* Side column: what's next, saved work, and a compact plan/usage strip. */}
          <div className="space-y-8">
            {ENABLE_CALENDAR && <EarningsCalendar enabled={!!user} />}

            {/* Saved summaries render only when the user has any (the empty block is gone). */}
            {hasSavedSummaries || savedFailure.failed ? (
              <section>
                <h2
                  ref={savedHeadingRef}
                  tabIndex={-1}
                  className="mb-4 text-xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
                >
                  Saved summaries
                </h2>
                {savedFailure.failed && (
                  <GuidanceCard
                    variant="error"
                    title="Unable to load saved summaries"
                    description="Try again in a moment."
                    action={<RetryButton failures={[savedFailure]} focusTarget={savedRetryTarget} />}
                    className={hasSavedSummaries ? 'mb-3' : undefined}
                  />
                )}
                {hasSavedSummaries && <div className="space-y-3">
                  {savedSummaries!.map((item: SavedSummary) => (
                    <Card key={item.id} className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <Link
                            href={`/filing/${item.summary.filing_id}`}
                            className="rounded font-semibold text-text-primary-light hover:text-brand-strong transition-colors focus-visible:outline-none focus-visible:shadow-ring-brand dark:text-text-primary-dark dark:hover:text-brand-strong-dark dark:focus-visible:shadow-ring-brand-dark"
                          >
                            {formatCompanyName(item.company.name)} - {item.filing.filing_type}
                          </Link>
                          <p className="text-sm text-text-secondary-light mt-1 dark:text-text-secondary-dark">
                            {formatLocalDate(item.filing.filing_date, 'MMM dd, yyyy')}
                          </p>
                          {item.notes && (
                            <p className="text-sm text-text-secondary-light mt-2 bg-background-light p-2 rounded dark:bg-background-dark dark:text-text-secondary-dark border border-border-light dark:border-border-dark">
                              {item.notes}
                            </p>
                          )}
                        </div>
                        {/* aria-disabled + aria-busy + an early return while a delete is in flight, not
                            native `disabled`: Chromium blurs a focused button that turns disabled. Busy fades
                            the glyph's ink, not the element: an element opacity would fade the focus ring too
                            (DESIGN_SYSTEM §4). */}
                        <button
                          onClick={() => {
                            if (deleteSummaryMutation.isPending) return
                            deleteSummaryMutation.mutate(item.id)
                          }}
                          aria-disabled={deleteSummaryMutation.isPending || undefined}
                          aria-busy={pendingDeleteId === item.id || undefined}
                          className="text-error-light hover:bg-error-light/10 inline-flex min-h-11 min-w-11 items-center justify-center p-2.5 rounded-lg focus-visible:outline-none focus-visible:shadow-ring-error dark:focus-visible:shadow-ring-error-dark aria-disabled:text-error-light/50 dark:text-error-dark dark:hover:bg-error-dark/15 dark:aria-disabled:text-error-dark/50"
                          title="Delete"
                          aria-label={`Delete summary for ${formatCompanyName(item.company.name)}`}
                        >
                          <TrashIcon className="h-5 w-5" />
                        </button>
                      </div>
                    </Card>
                  ))}
                </div>}
              </section>
            ) : null}

            {/* Plan and usage — a single compact strip. The ≥80% warning is surfaced at the top. */}
            <Card className="p-cap-5">
              <div className="flex items-center justify-between">
                <h2
                  ref={planHeadingRef}
                  tabIndex={-1}
                  className="text-sm font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
                >
                  Plan and usage
                </h2>
                {subscriptionFailure.failed || !subscription ? (
                  <Badge variant="neutral">{subscriptionFailure.failed ? 'Unavailable' : 'Loading'}</Badge>
                ) : subscription.is_pro ? (
                  <Badge variant="brand" icon={<LightningIcon className="h-4 w-4" />}>Pro</Badge>
                ) : (
                  <Badge variant="free">Free</Badge>
                )}
              </div>

              {planFailed ? (
                <div role="alert" className="mt-3 space-y-2">
                  <p className="flex items-center gap-2 text-sm font-medium text-error-light dark:text-error-dark">
                    <WarningCircleIcon className="h-4 w-4 flex-shrink-0" />
                    Unable to load plan details
                  </p>
                  <RetryButton size="sm" failures={[usageFailure, subscriptionFailure]} focusTarget={planHeadingRef} />
                </div>
              ) : !subscription ? (
                <p role="status" className="mt-3 text-sm text-text-secondary-light dark:text-text-secondary-dark">Checking your plan…</p>
              ) : subscription.is_pro ? (
                <div className="mt-3 space-y-3">
                  <p className="flex items-center gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    <CheckCircleIcon className="h-4 w-4 flex-shrink-0 text-success-light dark:text-success-dark" />
                    Unlimited summaries
                  </p>
                  <Button
                    variant="secondary"
                    wrap
                    className="w-full"
                    onClick={() => portalMutation.mutate()}
                    loading={portalMutation.isPending}
                    loadingText="Opening billing…"
                  >
                    Manage billing
                  </Button>
                </div>
              ) : (
                <div className="mt-3 space-y-3">
                  {/* The two counts share a line while they fit and stack when they do not (200% text on
                      a phone), with a gap between them either way. */}
                  <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 text-sm">
                    <span className="text-text-secondary-light dark:text-text-secondary-dark">
                      {usage?.summaries_used || 0} / {usage?.summaries_limit ?? FREE_SUMMARY_LIMIT} summaries
                    </span>
                    <span className="text-text-secondary-light dark:text-text-secondary-dark">
                      {usage?.summaries_limit
                        ? Math.max(0, usage.summaries_limit - (usage.summaries_used || 0))
                        : 0}{' '}
                      remaining
                    </span>
                  </div>
                  <div className="w-full bg-panel-light rounded-full h-3 border border-border-light dark:bg-background-dark dark:border-border-dark">
                    <div
                      className={`h-full rounded-full transition-[width] duration-base ${
                        usagePercentage >= 100
                          ? 'bg-error-light dark:bg-error-dark'
                          : usagePercentage >= 80
                          ? 'bg-warning-light dark:bg-warning-dark'
                          : 'bg-brand-strong dark:bg-brand-dark'
                      }`}
                      style={{ width: `${Math.min(100, usagePercentage)}%` }}
                    />
                  </div>
                  <Link href="/pricing" className={buttonVariants({ variant: 'primary', wrap: true, className: 'w-full text-center' })}>
                    Upgrade to Pro
                  </Link>
                </div>
              )}
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}
