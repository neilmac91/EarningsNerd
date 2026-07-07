'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCurrentUserSafe, logout } from '@/features/auth/api/auth-api'
import { getUsage, getSubscriptionStatus, createPortalSession } from '@/features/subscriptions/api/subscriptions-api'
import { getSavedSummaries, deleteSavedSummary, SavedSummary } from '@/features/summaries/api/summaries-api'
import { getWatchlistInsights } from '@/features/watchlist/api/watchlist-api'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { CheckCircleIcon, CircleNotchIcon, SparkleIcon, TrashIcon, WarningCircleIcon } from '@/lib/icons'
import Link from 'next/link'
import { format } from 'date-fns'
import { toast } from 'sonner'
import SecondaryHeader from '@/components/SecondaryHeader'
import TrialBanner from '@/features/subscriptions/components/TrialBanner'
import CompanySearch from '@/features/companies/components/CompanySearch'
import FilingFeed from '@/features/dashboard/components/FilingFeed'
import EarningsCalendar from '@/features/dashboard/components/EarningsCalendar'
import YourCompanies from '@/features/dashboard/components/YourCompanies'
import { ENABLE_CALENDAR } from '@/lib/featureFlags'
import analytics from '@/lib/analytics'
import { Badge, Button, buttonVariants, Card, GuidanceCard } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'

export default function DashboardPage() {
  const router = useRouter()

  const { data: user, isLoading: userLoading, isError: userError, error: userErrorData, refetch: refetchUser, isFetching: userFetching } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })

  const { data: usage, isLoading: usageLoading, isError: usageError, refetch: refetchUsage, isFetching: usageFetching } = useQuery({
    queryKey: queryKeys.usage(),
    queryFn: getUsage,
    retry: false,
    enabled: !!user,
  })

  const { data: subscription, isLoading: subscriptionLoading, isError: subscriptionError, refetch: refetchSubscription, isFetching: subscriptionFetching } = useQuery({
    queryKey: queryKeys.subscription(),
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!user,
  })

  const { data: savedSummaries, isError: savedError } = useQuery({
    queryKey: queryKeys.savedSummaries(),
    queryFn: getSavedSummaries,
    retry: false,
    enabled: !!user,
  })

  const { data: watchlistInsights, isLoading: insightsLoading, isError: insightsError, refetch: refetchInsights, isFetching: insightsFetching } = useQuery({
    queryKey: queryKeys.watchlistInsights(),
    queryFn: getWatchlistInsights,
    retry: false,
    enabled: !!user,
  })

  const queryClient = useQueryClient()

  const deleteSummaryMutation = useMutation({
    mutationFn: deleteSavedSummary,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.savedSummaries() })
      toast.success('Saved summary removed')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Couldn't delete that summary. Please try again.")
    },
  })

  const portalMutation = useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url
      } else {
        // 200 with no URL means the billing portal couldn't be created — don't leave a dead click.
        toast.error('Could not open the billing portal. Please try again.')
      }
    },
    onError: (error) => {
      // Surfaces the backend detail (e.g. "No subscription found") instead of failing silently.
      toast.error(error instanceof Error ? error.message : 'Could not open the billing portal. Please try again.')
    },
  })

  const logoutMutation = useMutation({
    mutationFn: logout,
    onSuccess: () => {
      analytics.logout()
      router.push('/login')
      router.refresh()
    },
  })

  useEffect(() => {
    // Redirect to login if not authenticated
    if (!userLoading && !user && !userError) {
      router.push('/login')
    }
  }, [user, userLoading, userError, router])

  useEffect(() => {
    if (user?.id) {
      // Identify on the internal id only — no email/PII into PostHog person properties.
      analytics.identify(String(user.id), {
        plan: user.is_pro ? 'pro' : 'free',
      })
    }
  }, [user])

  if (userLoading || usageLoading || subscriptionLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-panel-light dark:bg-background-dark">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  if (userError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-panel-light dark:bg-background-dark px-4">
        <div className="max-w-md w-full">
          <GuidanceCard
            variant="error"
            title="Unable to load your dashboard"
            description={userErrorData instanceof Error ? userErrorData.message : 'Please try again in a moment.'}
            action={
              <>
                <Button variant="secondary" onClick={() => refetchUser()} loading={userFetching} loadingText="Retrying…">
                  Retry
                </Button>
                <Link href="/login" className={buttonVariants({ variant: 'primary' })}>
                  Go to login
                </Link>
              </>
            }
          />
        </div>
      </div>
    )
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
  const showUsageWarning = usagePercentage >= 80 && !usage?.is_pro && !usageError
  const hasSavedSummaries = Boolean(savedSummaries && savedSummaries.length > 0)
  const watchlistCount = watchlistInsights?.length

  return (
    <div className="min-h-screen bg-panel-light dark:bg-background-dark">
      <SecondaryHeader
        title="Dashboard"
        subtitle={`Welcome back, ${user.full_name || user.email}`}
        backHref="/"
        backLabel="Back to home"
        actions={
          <button
            onClick={() => logoutMutation.mutate()}
            className="text-sm font-medium text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
          >
            Logout
          </button>
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {/* Reverse-trial countdown (renders only while a Pro trial is active) */}
        <TrialBanner status={subscription?.status} trialEnd={subscription?.trial_end} className="mb-6" />

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
                    ? 'Upgrade to Pro for unlimited summaries'
                    : 'Upgrade to Pro to continue generating summaries'}
                </p>
              </div>
            </div>
            <Link href="/pricing" className={buttonVariants({ variant: 'primary', className: 'sm:flex-shrink-0' })}>
              Upgrade to Pro
            </Link>
          </div>
        )}

        <div className="grid gap-8 lg:grid-cols-3">
          {/* Main column: search, the "what changed" feed, and the watchlist status section. */}
          <div className="space-y-8 lg:col-span-2">
            <Card className="p-5">
              <p className="mb-2 text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark">Jump to any company</p>
              <CompanySearch />
            </Card>

            <FilingFeed enabled={!!user} watchlistCount={watchlistCount} />

            <YourCompanies
              insights={watchlistInsights}
              isLoading={insightsLoading}
              isError={insightsError}
              refetch={refetchInsights}
              isFetching={insightsFetching}
            />
          </div>

          {/* Side column: what's next, saved work, and a compact plan/usage strip. */}
          <div className="space-y-8">
            {ENABLE_CALENDAR && <EarningsCalendar enabled={!!user} />}

            {/* Saved summaries render only when the user has any (the empty block is gone). */}
            {hasSavedSummaries ? (
              <section>
                <h2 className="mb-4 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Saved summaries</h2>
                <div className="space-y-3">
                  {savedSummaries!.map((item: SavedSummary) => (
                    <Card key={item.id} className="p-4">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0 flex-1">
                          <Link
                            href={`/filing/${item.summary.filing_id}`}
                            className="font-semibold text-text-primary-light hover:text-brand-strong transition-colors dark:text-text-primary-dark dark:hover:text-brand-strong-dark"
                          >
                            {item.company.name} - {item.filing.filing_type}
                          </Link>
                          <p className="text-sm text-text-secondary-light mt-1 dark:text-text-secondary-dark">
                            {item.filing.filing_date && format(new Date(item.filing.filing_date), 'MMM dd, yyyy')}
                          </p>
                          {item.notes && (
                            <p className="text-sm text-text-secondary-light mt-2 bg-panel-light p-2 rounded dark:bg-background-dark dark:text-text-secondary-dark border border-border-light dark:border-border-dark">
                              {item.notes}
                            </p>
                          )}
                        </div>
                        <button
                          onClick={() => deleteSummaryMutation.mutate(item.id)}
                          className="text-error-light hover:bg-error-light/10 p-2 rounded-lg focus-visible:outline-none focus-visible:shadow-ring-error dark:text-error-dark dark:hover:bg-error-dark/15"
                          title="Delete"
                          aria-label={`Delete summary for ${item.company.name}`}
                        >
                          <TrashIcon className="h-5 w-5" />
                        </button>
                      </div>
                    </Card>
                  ))}
                </div>
              </section>
            ) : savedError ? (
              <section>
                <h2 className="mb-4 text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Saved summaries</h2>
                <GuidanceCard
                  variant="error"
                  title="Unable to load saved summaries"
                  description="Please retry in a moment."
                />
              </section>
            ) : null}

            {/* Plan and usage — a single compact strip. The ≥80% warning is surfaced at the top. */}
            <Card className="p-5">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">Plan and usage</h2>
                {subscription?.is_pro ? (
                  <Badge variant="brand" icon={<SparkleIcon className="h-4 w-4" />}>Pro</Badge>
                ) : (
                  <Badge variant="free">Free</Badge>
                )}
              </div>

              {subscriptionError || usageError ? (
                <div role="alert" className="mt-3 space-y-2">
                  <p className="flex items-center gap-2 text-sm font-medium text-error-light dark:text-error-dark">
                    <WarningCircleIcon className="h-4 w-4 flex-shrink-0" />
                    Unable to load plan details
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() => {
                      refetchUsage()
                      refetchSubscription()
                    }}
                    loading={usageFetching || subscriptionFetching}
                    loadingText="Retrying…"
                  >
                    Retry
                  </Button>
                </div>
              ) : subscription?.is_pro ? (
                <div className="mt-3 space-y-3">
                  <p className="flex items-center gap-2 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                    <CheckCircleIcon className="h-4 w-4 flex-shrink-0 text-success-light dark:text-success-dark" />
                    Unlimited summaries
                  </p>
                  <Button
                    variant="secondary"
                    className="w-full"
                    onClick={() => portalMutation.mutate()}
                    loading={portalMutation.isPending}
                    loadingText="Loading..."
                  >
                    Manage subscription
                  </Button>
                </div>
              ) : (
                <div className="mt-3 space-y-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-text-secondary-light dark:text-text-secondary-dark">
                      {usage?.summaries_used || 0} / {usage?.summaries_limit || 5} summaries
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
                  <Link href="/pricing" className={buttonVariants({ variant: 'primary', className: 'w-full' })}>
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
