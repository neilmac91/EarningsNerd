'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCurrentUser, getUsage, getSubscriptionStatus, createPortalSession, getSavedSummaries, getWatchlist, deleteSavedSummary, removeFromWatchlist, SavedSummary, WatchlistItem, logout } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { CheckCircle2, AlertCircle, Sparkles, BarChart3, FileText, Loader2, Trash2, X } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import { ThemeToggle } from '@/components/ThemeToggle'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'
import analytics from '@/lib/analytics'

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
    },
  })

  const removeWatchlistMutation = useMutation({
    mutationFn: removeFromWatchlist,
    onSuccess: (_data, ticker) => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
      analytics.watchlistRemoved(ticker)
    },
  })

  const portalMutation = useMutation({
    mutationFn: createPortalSession,
    onSuccess: (data) => {
      if (data.url) {
        window.location.href = data.url
      }
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
    if (user?.id && user?.email) {
      analytics.identify(String(user.id), {
        email: user.email,
        plan: user.is_pro ? 'pro' : 'free',
      })
    }
  }, [user])

  if (userLoading || usageLoading || subscriptionLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-panel-light dark:bg-background-dark">
        <Loader2 className="h-8 w-8 animate-spin text-mint-600" />
      </div>
    )
  }

  if (userError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-panel-light dark:bg-background-dark px-4">
        <div className="max-w-md w-full">
          <StateCard
            variant="error"
            title="Unable to load your dashboard"
            message={userErrorData instanceof Error ? userErrorData.message : 'Please try again in a moment.'}
            action={
              <div className="flex gap-3 mt-2">
                <button
                  type="button"
                  onClick={() => refetchUser()}
                  disabled={userFetching}
                  className="inline-flex items-center rounded-lg border border-border-light px-4 py-2 text-sm font-medium text-text-secondary-light transition hover:bg-panel-light dark:border-border-dark dark:text-text-secondary-dark dark:hover:bg-panel-dark disabled:opacity-60"
                >
                  {userFetching ? 'Retrying…' : 'Retry'}
                </button>
                <Link
                  href="/login"
                  className="inline-flex items-center rounded-lg bg-mint-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-mint-700"
                >
                  Go to login
                </Link>
              </div>
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
            <ThemeToggle />
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

        {/* Subscription Status */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <div className="bg-background-light rounded-lg shadow-sm border border-border-light p-6 dark:bg-panel-dark dark:border-border-dark">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Subscription</h2>
              {subscription?.is_pro ? (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-mint-100 text-mint-800 dark:bg-mint-900/30 dark:text-mint-400">
                  <Sparkles className="h-4 w-4 mr-1" />
                  Pro
                </span>
              ) : (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-panel-light text-text-secondary-light dark:bg-panel-dark dark:text-text-secondary-dark border border-border-light dark:border-border-dark">
                  Free
                </span>
              )}
            </div>
            {subscriptionError ? (
              <StateCard
                variant="error"
                title="Unable to load subscription"
                message={subscriptionErrorData instanceof Error ? subscriptionErrorData.message : 'Please retry.'}
                action={
                  <button
                    type="button"
                    onClick={() => refetchSubscription()}
                    disabled={subscriptionFetching}
                    className="mt-2 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
                  >
                    {subscriptionFetching ? 'Retrying…' : 'Retry'}
                  </button>
                }
              />
            ) : subscription?.is_pro ? (
              <div className="space-y-3">
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  You&apos;re on the Pro plan with unlimited access.
                </p>
                <button
                  onClick={() => portalMutation.mutate()}
                  disabled={portalMutation.isPending}
                  className="w-full px-4 py-2 bg-panel-light text-text-primary-light border border-border-light rounded-lg hover:bg-gray-100 transition-colors font-medium dark:bg-background-dark dark:text-text-primary-dark dark:border-border-dark dark:hover:bg-gray-800"
                >
                  {portalMutation.isPending ? (
                    <span className="flex items-center justify-center">
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Loading...
                    </span>
                  ) : (
                    'Manage Subscription'
                  )}
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                  Upgrade to Pro for unlimited summaries and advanced features.
                </p>
                <Link
                  href="/pricing"
                  className="block w-full text-center px-4 py-2 bg-mint-500 text-white rounded-lg hover:bg-mint-600 transition-colors font-medium"
                >
                  Upgrade to Pro
                </Link>
              </div>
            )}
          </div>

          {/* Usage Stats */}
          <div className="bg-background-light rounded-lg shadow-sm border border-border-light p-6 dark:bg-panel-dark dark:border-border-dark">
            <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">Usage This Month</h2>
            {usageError ? (
              <StateCard
                variant="error"
                title="Unable to load usage data"
                message={usageErrorData instanceof Error ? usageErrorData.message : 'Please retry.'}
                action={
                  <button
                    type="button"
                    onClick={() => refetchUsage()}
                    disabled={usageFetching}
                    className="mt-2 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
                  >
                    {usageFetching ? 'Retrying…' : 'Retry'}
                  </button>
                }
              />
            ) : usage?.is_pro ? (
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="h-5 w-5 text-mint-500" />
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
                    className={`h-full rounded-full transition-all ${
                      usagePercentage >= 100
                        ? 'bg-red-500'
                        : usagePercentage >= 80
                        ? 'bg-yellow-500'
                        : 'bg-mint-500'
                    }`}
                    style={{ width: `${Math.min(100, usagePercentage)}%` }}
                  />
                </div>
                {usagePercentage >= 80 && !subscription?.is_pro && (
                  <div className="flex items-start space-x-2 p-3 bg-amber-50 border border-amber-200 rounded-lg dark:bg-amber-900/20 dark:border-amber-800">
                    <AlertCircle className="h-5 w-5 text-amber-600 dark:text-amber-500 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
                        {usagePercentage >= 100 ? 'Limit Reached' : 'Almost at Limit'}
                      </p>
                      <p className="text-sm text-amber-800 mt-1 dark:text-amber-300">
                        {usagePercentage >= 100
                          ? 'Upgrade to Pro for unlimited summaries'
                          : 'Upgrade to Pro to continue generating summaries'}
                      </p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Quick Actions */}
        <div className="grid md:grid-cols-3 gap-6">
          <Link
            href="/"
            className="bg-background-light rounded-lg shadow-sm border border-border-light p-6 hover:shadow-md transition-shadow dark:bg-panel-dark dark:border-border-dark"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 bg-blue-100 rounded-lg dark:bg-blue-900/30">
                <FileText className="h-6 w-6 text-blue-600 dark:text-blue-400" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Search Companies</h3>
            </div>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Find and analyze SEC filings for any public company
            </p>
          </Link>

          <Link
            href="/pricing"
            className="bg-background-light rounded-lg shadow-sm border border-border-light p-6 hover:shadow-md transition-shadow dark:bg-panel-dark dark:border-border-dark"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 bg-purple-100 rounded-lg dark:bg-purple-900/30">
                <Sparkles className="h-6 w-6 text-purple-600 dark:text-purple-400" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">View Plans</h3>
            </div>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Compare features and upgrade your plan
            </p>
          </Link>

          <Link
            href="/dashboard/watchlist"
            className="bg-background-light rounded-lg shadow-sm border border-border-light p-6 hover:shadow-md transition-shadow dark:bg-panel-dark dark:border-border-dark"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 bg-mint-100 rounded-lg dark:bg-mint-900/30">
                <BarChart3 className="h-6 w-6 text-mint-600 dark:text-mint-400" />
              </div>
              <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Watchlist Insights</h3>
            </div>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              Monitor summary readiness across your tracked companies
            </p>
          </Link>
        </div>

        {/* Saved Summaries */}
        <div className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">Saved Summaries</h2>
          {savedLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-mint-600" />
            </div>
          ) : savedError ? (
            <StateCard
              variant="error"
              title="Unable to load saved summaries"
              message={savedErrorData instanceof Error ? savedErrorData.message : 'Please retry.'}
              action={
                <button
                  type="button"
                  onClick={() => refetchSavedSummaries()}
                  disabled={savedFetching}
                  className="mt-2 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
                >
                  {savedFetching ? 'Retrying…' : 'Retry'}
                </button>
              }
            />
          ) : savedSummaries && savedSummaries.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {savedSummaries.map((item: SavedSummary) => (
                <div key={item.id} className="bg-background-light rounded-lg shadow-sm border border-border-light p-4 dark:bg-panel-dark dark:border-border-dark">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <Link
                        href={`/filing/${item.summary.filing_id}`}
                        className="text-lg font-semibold text-text-primary-light hover:text-mint-600 transition-colors dark:text-text-primary-dark dark:hover:text-mint-400"
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
                      className="text-red-600 hover:text-red-700 p-2 dark:text-red-400 dark:hover:text-red-300"
                      title="Delete"
                      aria-label={`Delete summary for ${item.company.name}`}
                    >
                      <Trash2 className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <StateCard
              variant="info"
              title="No saved summaries yet"
              message="Save summaries from filing pages to access them here."
            />
          )}
        </div>

        {/* Watchlist */}
        <div className="mt-8">
          <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">Watchlist</h2>
          {watchlistLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-mint-600" />
            </div>
          ) : watchlistError ? (
            <StateCard
              variant="error"
              title="Unable to load watchlist"
              message={watchlistErrorData instanceof Error ? watchlistErrorData.message : 'Please retry.'}
              action={
                <button
                  type="button"
                  onClick={() => refetchWatchlist()}
                  disabled={watchlistFetching}
                  className="mt-2 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60 dark:bg-red-900/20 dark:border-red-800 dark:text-red-300 dark:hover:bg-red-900/30"
                >
                  {watchlistFetching ? 'Retrying…' : 'Retry'}
                </button>
              }
            />
          ) : watchlist && watchlist.length > 0 ? (
            <div className="grid md:grid-cols-3 gap-4">
              {watchlist.map((item: WatchlistItem) => (
                <div key={item.id} className="bg-background-light rounded-lg shadow-sm border border-border-light p-4 dark:bg-panel-dark dark:border-border-dark">
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/company/${item.company.ticker}`}
                      className="flex-1"
                    >
                      <div className="font-semibold text-text-primary-light hover:text-mint-600 transition-colors dark:text-text-primary-dark dark:hover:text-mint-400">
                        {item.company.name}
                      </div>
                      <div className="text-sm text-text-secondary-light dark:text-text-secondary-dark">{item.company.ticker}</div>
                    </Link>
                    <button
                      onClick={() => removeWatchlistMutation.mutate(item.company.ticker)}
                      className="text-red-600 hover:text-red-700 p-2 dark:text-red-400 dark:hover:text-red-300"
                      title="Remove from watchlist"
                      aria-label={`Remove ${item.company.name} from watchlist`}
                    >
                      <X className="h-5 w-5" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <StateCard
              variant="info"
              title="Your watchlist is empty"
              message="Add companies to your watchlist from company pages."
            />
          )}
        </div>
      </main>
    </div>
  )
}
