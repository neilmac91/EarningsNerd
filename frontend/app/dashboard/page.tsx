'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCurrentUser, logout } from '@/features/auth/api/auth-api'
import { getUsage, getSubscriptionStatus, createPortalSession } from '@/features/subscriptions/api/subscriptions-api'
import { getSavedSummaries, deleteSavedSummary, SavedSummary } from '@/features/summaries/api/summaries-api'
import { getWatchlist, removeFromWatchlist, WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { ChartBarIcon, CheckCircleIcon, CircleNotchIcon, FileTextIcon, SparkleIcon, TrashIcon, WarningCircleIcon, XIcon } from '@/lib/icons'
import Link from 'next/link'
import { format } from 'date-fns'
import { toast } from 'sonner'
import SecondaryHeader from '@/components/SecondaryHeader'
import TrialBanner from '@/components/TrialBanner'
import CompanySearch from '@/components/CompanySearch'
import FilingFeed from '@/components/dashboard/FilingFeed'
import EarningsCalendar from '@/components/dashboard/EarningsCalendar'
import { ENABLE_CALENDAR } from '@/lib/featureFlags'
import analytics from '@/lib/analytics'
import { Badge, Button, buttonVariants, Card, GuidanceCard, Skeleton } from '@/components/ui'

export default function DashboardPage() {
  const router = useRouter()

  const { data: user, isLoading: userLoading, isError: userError, error: userErrorData, refetch: refetchUser, isFetching: userFetching } = useQuery({
    queryKey: ['user'],
    queryFn: getCurrentUser,
    retry: false,
  })

  const { data: usage, isLoading: usageLoading, isError: usageError, error: usageErrorData, refetch: refetchUsage, isFetching: usageFetching } = useQuery({
    queryKey: ['usage'],
    queryFn: getUsage,
    retry: false,
    enabled: !!user,
  })

  const { data: subscription, isLoading: subscriptionLoading, isError: subscriptionError, error: subscriptionErrorData, refetch: refetchSubscription, isFetching: subscriptionFetching } = useQuery({
    queryKey: ['subscription'],
    queryFn: getSubscriptionStatus,
    retry: false,
    enabled: !!user,
  })

  const { data: savedSummaries, isLoading: savedLoading, isError: savedError, error: savedErrorData, refetch: refetchSavedSummaries, isFetching: savedFetching } = useQuery({
    queryKey: ['saved-summaries'],
    queryFn: getSavedSummaries,
    retry: false,
    enabled: !!user,
  })

  const { data: watchlist, isLoading: watchlistLoading, isError: watchlistError, error: watchlistErrorData, refetch: refetchWatchlist, isFetching: watchlistFetching } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    retry: false,
    enabled: !!user,
  })

  const queryClient = useQueryClient()

  const deleteSummaryMutation = useMutation({
    mutationFn: deleteSavedSummary,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['saved-summaries'] })
      toast.success('Saved summary removed')
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Couldn't delete that summary. Please try again.")
    },
  })

  const removeWatchlistMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: (_data, ticker) => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      analytics.watchlistRemoved(ticker)
      toast.success(`${ticker} removed from your watchlist`)
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Couldn't update your watchlist. Please try again.")
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

  return (
    <div className="min-h-screen bg-panel-light dark:bg-background-dark">
      <SecondaryHeader
        title="Dashboard"
        subtitle={`Welcome back, ${user.full_name || user.email}`}
        backHref="/"
        backLabel="Back to home"
        actions={
          <>
            <button
              onClick={() => logoutMutation.mutate()}
              className="text-sm font-medium text-text-secondary-light hover:text-text-primary-light dark:text-text-secondary-dark dark:hover:text-text-primary-dark"
            >
              Logout
            </button>
          </>
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {/* Reverse-trial countdown (renders only while a Pro trial is active) */}
        <TrialBanner status={subscription?.status} trialEnd={subscription?.trial_end} className="mb-8" />

        {/* Phase 3 hero: quick search + personalised "what changed" feed + (optional) calendar.
            The plan/usage cards below become a compact secondary strip. */}
        <div className="mb-10 space-y-6">
          <Card className="p-5">
            <p className="mb-2 text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark">Jump to any company</p>
            <CompanySearch />
          </Card>
          <FilingFeed enabled={!!user} />
          {ENABLE_CALENDAR && <EarningsCalendar enabled={!!user} />}
        </div>

        {/* Subscription Status */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <Card className="p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Subscription</h2>
              {subscription?.is_pro ? (
                <Badge variant="brand" icon={<SparkleIcon className="h-4 w-4" />}>Pro</Badge>
              ) : (
                <Badge variant="free">Free</Badge>
              )}
            </div>
            {subscriptionError ? (
              // Inline error (not GuidanceCard) — this state lives INSIDE the section
              // card, and nesting a guidance panel in a panel stacks borders/shadows.
              <div role="alert" className="space-y-2">
                <p className="flex items-center gap-2 text-sm font-medium text-error-light dark:text-error-dark">
                  <WarningCircleIcon className="h-4 w-4 flex-shrink-0" />
                  Unable to load subscription
                </p>
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  {subscriptionErrorData instanceof Error ? subscriptionErrorData.message : 'Please retry.'}
                </p>
                <Button variant="secondary" size="sm" onClick={() => refetchSubscription()} loading={subscriptionFetching} loadingText="Retrying…">
                  Retry
                </Button>
              </div>
            ) : subscription?.is_pro ? (
              <div className="space-y-3">
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  You&apos;re on the Pro plan with unlimited access.
                </p>
                <Button
                  variant="secondary"
                  className="w-full"
                  onClick={() => portalMutation.mutate()}
                  loading={portalMutation.isPending}
                  loadingText="Loading..."
                >
                  Manage Subscription
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Upgrade to Pro for unlimited summaries and advanced features.
                </p>
                <Link href="/pricing" className={buttonVariants({ variant: 'primary', className: 'w-full' })}>
                  Upgrade to Pro
                </Link>
              </div>
            )}
          </Card>

          {/* Usage Stats */}
          <Card className="p-6">
            <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">Usage This Month</h2>
            {usageError ? (
              // Inline error — same in-card composition rule as the subscription error.
              <div role="alert" className="space-y-2">
                <p className="flex items-center gap-2 text-sm font-medium text-error-light dark:text-error-dark">
                  <WarningCircleIcon className="h-4 w-4 flex-shrink-0" />
                  Unable to load usage data
                </p>
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  {usageErrorData instanceof Error ? usageErrorData.message : 'Please retry.'}
                </p>
                <Button variant="secondary" size="sm" onClick={() => refetchUsage()} loading={usageFetching} loadingText="Retrying…">
                  Retry
                </Button>
              </div>
            ) : usage?.is_pro ? (
              <div className="flex items-center space-x-2">
                <CheckCircleIcon className="h-5 w-5 text-success-light dark:text-success-dark" />
                <span className="text-text-secondary-light dark:text-text-secondary-dark">Unlimited summaries</span>
              </div>
            ) : (
              <div className="space-y-3">
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
                {usagePercentage >= 80 && !subscription?.is_pro && (
                  <div className="flex items-start space-x-2 p-3 bg-warning-light/10 border border-warning-light/30 rounded-lg dark:bg-warning-dark/10 dark:border-warning-dark/30">
                    <WarningCircleIcon className="h-5 w-5 text-warning-light dark:text-warning-dark flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-warning-light dark:text-warning-dark">
                        {usagePercentage >= 100 ? 'Limit Reached' : 'Almost at Limit'}
                      </p>
                      <p className="text-sm text-warning-light mt-1 dark:text-warning-dark">
                        {usagePercentage >= 100
                          ? 'Upgrade to Pro for unlimited summaries'
                          : 'Upgrade to Pro to continue generating summaries'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </Card>
        </div>

        {/* Quick Actions — interactive Cards wrapped in Links for semantics;
            the focus ring rides on the Link (the actual focusable element). */}
        <div className="grid md:grid-cols-3 gap-6">
          {(
            [
              {
                href: '/',
                icon: <FileTextIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" />,
                title: 'Search Companies',
                description: 'Find and analyze SEC filings for any public company',
              },
              {
                href: '/pricing',
                icon: <SparkleIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" />,
                title: 'View Plans',
                description: 'Compare features and upgrade your plan',
              },
              {
                href: '/dashboard/watchlist',
                icon: <ChartBarIcon className="h-6 w-6 text-brand-strong dark:text-brand-strong-dark" />,
                title: 'Watchlist Insights',
                description: 'Monitor summary readiness across your tracked companies',
              },
            ] as const
          ).map((action) => (
            <Link
              key={action.href}
              href={action.href}
              className="block rounded-xl focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
            >
              <Card interactive className="h-full p-6">
                <div className="flex items-center space-x-3 mb-3">
                  <div className="p-2 bg-brand-weak rounded-lg dark:bg-white/5">{action.icon}</div>
                  <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">{action.title}</h3>
                </div>
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{action.description}</p>
              </Card>
            </Link>
          ))}
        </div>

        {/* Saved Summaries */}
        <div className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">Saved Summaries</h2>
          {savedLoading ? (
            <div role="status" aria-label="Loading saved summaries" className="grid md:grid-cols-2 gap-4">
              <Skeleton className="h-28 rounded-xl" />
              <Skeleton className="h-28 rounded-xl" />
              <span className="sr-only">Loading saved summaries…</span>
            </div>
          ) : savedError ? (
            <GuidanceCard
              variant="error"
              title="Unable to load saved summaries"
              description={savedErrorData instanceof Error ? savedErrorData.message : 'Please retry.'}
              action={
                <Button variant="secondary" onClick={() => refetchSavedSummaries()} loading={savedFetching} loadingText="Retrying…">
                  Retry
                </Button>
              }
            />
          ) : savedSummaries && savedSummaries.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {savedSummaries.map((item: SavedSummary) => (
                <Card key={item.id} className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <Link
                        href={`/filing/${item.summary.filing_id}`}
                        className="text-lg font-semibold text-text-primary-light hover:text-brand-strong transition-colors dark:text-text-primary-dark dark:hover:text-brand-strong-dark"
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
                      className="text-error-light hover:bg-error-light/10 p-2 rounded-lg dark:text-error-dark dark:hover:bg-error-dark/15"
                      title="Delete"
                      aria-label={`Delete summary for ${item.company.name}`}
                    >
                      <TrashIcon className="h-5 w-5" />
                    </button>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <GuidanceCard
              variant="empty"
              title="No saved summaries yet"
              description="Save summaries from filing pages to access them here."
            />
          )}
        </div>

        {/* Watchlist */}
        <div className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">Watchlist</h2>
          {watchlistLoading ? (
            <div role="status" aria-label="Loading watchlist" className="grid md:grid-cols-3 gap-4">
              <Skeleton className="h-20 rounded-xl" />
              <Skeleton className="h-20 rounded-xl" />
              <Skeleton className="h-20 rounded-xl" />
              <span className="sr-only">Loading watchlist…</span>
            </div>
          ) : watchlistError ? (
            <GuidanceCard
              variant="error"
              title="Unable to load watchlist"
              description={watchlistErrorData instanceof Error ? watchlistErrorData.message : 'Please retry.'}
              action={
                <Button variant="secondary" onClick={() => refetchWatchlist()} loading={watchlistFetching} loadingText="Retrying…">
                  Retry
                </Button>
              }
            />
          ) : watchlist && watchlist.length > 0 ? (
            <div className="grid md:grid-cols-3 gap-4">
              {watchlist.map((item: WatchlistItem) => (
                <Card key={item.id} className="p-4">
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/company/${item.company.ticker}`}
                      className="flex-1"
                    >
                      <div className="font-semibold text-text-primary-light hover:text-brand-strong transition-colors dark:text-text-primary-dark dark:hover:text-brand-strong-dark">
                        {item.company.name}
                      </div>
                      <div className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{item.company.ticker}</div>
                    </Link>
                    <button
                      onClick={() => removeWatchlistMutation.mutate(item.company.ticker)}
                      className="text-error-light hover:bg-error-light/10 p-2 rounded-lg dark:text-error-dark dark:hover:bg-error-dark/15"
                      title="Remove from watchlist"
                      aria-label={`Remove ${item.company.name} from watchlist`}
                    >
                      <XIcon className="h-5 w-5" />
                    </button>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <GuidanceCard
              variant="empty"
              title="Your watchlist is empty"
              description="Add companies to your watchlist from company pages."
            />
          )}
        </div>
      </main>
    </div>
  )
}
