'use client'

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCurrentUser, getUsage, getSubscriptionStatus, createPortalSession, getSavedSummaries, getWatchlist, deleteSavedSummary, removeFromWatchlist, SavedSummary, WatchlistItem, logout } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import { CheckCircle2, AlertCircle, Sparkles, BarChart3, FileText, Settings, Loader2, Star, Trash2, X } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import { ThemeToggle } from '@/components/ThemeToggle'
import SecondaryHeader from '@/components/SecondaryHeader'

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
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

  if (userLoading || usageLoading || subscriptionLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (userError) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 dark:bg-slate-950 px-4">
        <div className="max-w-md w-full rounded-2xl border border-red-200/60 bg-white p-6 text-center shadow-sm dark:border-red-500/40 dark:bg-slate-900">
          <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400 mx-auto mb-3" />
          <h1 className="text-lg font-semibold text-gray-900 dark:text-white">Unable to load your dashboard</h1>
          <p className="mt-2 text-sm text-gray-600 dark:text-slate-300">
            {userErrorData instanceof Error ? userErrorData.message : 'Please try again in a moment.'}
          </p>
          <div className="mt-4 flex items-center justify-center gap-3">
            <button
              type="button"
              onClick={() => refetchUser()}
              disabled={userFetching}
              className="inline-flex items-center rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 dark:border-gray-700 dark:text-slate-200 dark:hover:bg-slate-800 disabled:opacity-60"
            >
              {userFetching ? 'Retrying…' : 'Retry'}
            </button>
            <Link
              href="/login"
              className="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-primary-700"
            >
              Go to login
            </Link>
          </div>
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
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
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
              className="text-sm font-medium text-gray-600 hover:text-gray-900 dark:text-gray-300 dark:hover:text-white"
            >
              Logout
            </button>
          </>
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        {/* Subscription Status */}
        <div className="grid md:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900">Subscription</h2>
              {subscription?.is_pro ? (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-primary-100 text-primary-800">
                  <Sparkles className="h-4 w-4 mr-1" />
                  Pro
                </span>
              ) : (
                <span className="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-gray-100 text-gray-800">
                  Free
                </span>
              )}
            </div>
            {subscriptionError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <p className="font-medium">Unable to load subscription status.</p>
                <p className="text-xs text-red-600 mt-1">
                  {subscriptionErrorData instanceof Error ? subscriptionErrorData.message : 'Please retry.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetchSubscription()}
                  disabled={subscriptionFetching}
                  className="mt-2 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
                >
                  {subscriptionFetching ? 'Retrying…' : 'Retry'}
                </button>
              </div>
            ) : subscription?.is_pro ? (
              <div className="space-y-3">
                <p className="text-sm text-gray-600">
                  You're on the Pro plan with unlimited access.
                </p>
                <button
                  onClick={() => portalMutation.mutate()}
                  disabled={portalMutation.isPending}
                  className="w-full px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium"
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
                <p className="text-sm text-gray-600">
                  Upgrade to Pro for unlimited summaries and advanced features.
                </p>
                <Link
                  href="/pricing"
                  className="block w-full text-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
                >
                  Upgrade to Pro
                </Link>
              </div>
            )}
          </div>

          {/* Usage Stats */}
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Usage This Month</h2>
            {usageError ? (
              <div className="rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-700">
                <p className="font-medium">Unable to load usage data.</p>
                <p className="text-xs text-red-600 mt-1">
                  {usageErrorData instanceof Error ? usageErrorData.message : 'Please retry.'}
                </p>
                <button
                  type="button"
                  onClick={() => refetchUsage()}
                  disabled={usageFetching}
                  className="mt-2 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
                >
                  {usageFetching ? 'Retrying…' : 'Retry'}
                </button>
              </div>
            ) : usage?.is_pro ? (
              <div className="flex items-center space-x-2">
                <CheckCircle2 className="h-5 w-5 text-green-500" />
                <span className="text-gray-700">Unlimited summaries</span>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-600">
                    {usage?.summaries_used || 0} / {usage?.summaries_limit || 5} summaries
                  </span>
                  <span className="text-gray-600">
                    {usage?.summaries_limit
                      ? Math.max(0, usage.summaries_limit - (usage.summaries_used || 0))
                      : 0}{' '}
                    remaining
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-3">
                  <div
                    className={`h-3 rounded-full transition-all ${
                      usagePercentage >= 100
                        ? 'bg-red-500'
                        : usagePercentage >= 80
                        ? 'bg-yellow-500'
                        : 'bg-green-500'
                    }`}
                    style={{ width: `${Math.min(100, usagePercentage)}%` }}
                  />
                </div>
                {usagePercentage >= 80 && !subscription?.is_pro && (
                  <div className="flex items-start space-x-2 p-3 bg-amber-50 border border-amber-200 rounded-lg">
                    <AlertCircle className="h-5 w-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="text-sm font-medium text-amber-900">
                        {usagePercentage >= 100 ? 'Limit Reached' : 'Almost at Limit'}
                      </p>
                      <p className="text-sm text-amber-800 mt-1">
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
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 bg-blue-100 rounded-lg">
                <FileText className="h-6 w-6 text-blue-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Search Companies</h3>
            </div>
            <p className="text-sm text-gray-600">
              Find and analyze SEC filings for any public company
            </p>
          </Link>

          <Link
            href="/pricing"
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 bg-purple-100 rounded-lg">
                <Sparkles className="h-6 w-6 text-purple-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">View Plans</h3>
            </div>
            <p className="text-sm text-gray-600">
              Compare features and upgrade your plan
            </p>
          </Link>

          <Link
            href="/dashboard/watchlist"
            className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 hover:shadow-md transition-shadow"
          >
            <div className="flex items-center space-x-3 mb-3">
              <div className="p-2 bg-green-100 rounded-lg">
                <BarChart3 className="h-6 w-6 text-green-600" />
              </div>
              <h3 className="text-lg font-semibold text-gray-900">Watchlist Insights</h3>
            </div>
            <p className="text-sm text-gray-600">
              Monitor summary readiness across your tracked companies
            </p>
          </Link>
        </div>

        {/* Saved Summaries */}
        <div className="mt-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Saved Summaries</h2>
          {savedLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : savedError ? (
            <div className="bg-white rounded-lg shadow-sm border border-red-200 p-6 text-center text-sm text-red-700">
              <p className="font-medium">Unable to load saved summaries.</p>
              <p className="text-xs text-red-600 mt-1">
                {savedErrorData instanceof Error ? savedErrorData.message : 'Please retry.'}
              </p>
              <button
                type="button"
                onClick={() => refetchSavedSummaries()}
                disabled={savedFetching}
                className="mt-3 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
              >
                {savedFetching ? 'Retrying…' : 'Retry'}
              </button>
            </div>
          ) : savedSummaries && savedSummaries.length > 0 ? (
            <div className="grid md:grid-cols-2 gap-4">
              {savedSummaries.map((item: SavedSummary) => (
                <div key={item.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <Link
                        href={`/filing/${item.summary.filing_id}`}
                        className="text-lg font-semibold text-gray-900 hover:text-primary-600 transition-colors"
                      >
                        {item.company.name} - {item.filing.filing_type}
                      </Link>
                      <p className="text-sm text-gray-600 mt-1">
                        {item.filing.filing_date && format(new Date(item.filing.filing_date), 'MMM dd, yyyy')}
                      </p>
                      {item.notes && (
                        <p className="text-sm text-gray-700 mt-2 bg-gray-50 p-2 rounded">
                          {item.notes}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => deleteSummaryMutation.mutate(item.id)}
                      className="text-red-600 hover:text-red-700 p-2"
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
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">No saved summaries yet</p>
              <p className="text-sm text-gray-500 mt-2">Save summaries from filing pages to access them here</p>
            </div>
          )}
        </div>

        {/* Watchlist */}
        <div className="mt-8">
          <h2 className="text-2xl font-semibold text-gray-900 mb-4">Watchlist</h2>
          {watchlistLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : watchlistError ? (
            <div className="bg-white rounded-lg shadow-sm border border-red-200 p-6 text-center text-sm text-red-700">
              <p className="font-medium">Unable to load watchlist.</p>
              <p className="text-xs text-red-600 mt-1">
                {watchlistErrorData instanceof Error ? watchlistErrorData.message : 'Please retry.'}
              </p>
              <button
                type="button"
                onClick={() => refetchWatchlist()}
                disabled={watchlistFetching}
                className="mt-3 inline-flex items-center rounded-md border border-red-200 bg-white px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-red-50 disabled:opacity-60"
              >
                {watchlistFetching ? 'Retrying…' : 'Retry'}
              </button>
            </div>
          ) : watchlist && watchlist.length > 0 ? (
            <div className="grid md:grid-cols-3 gap-4">
              {watchlist.map((item: WatchlistItem) => (
                <div key={item.id} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                  <div className="flex items-center justify-between">
                    <Link
                      href={`/company/${item.company.ticker}`}
                      className="flex-1"
                    >
                      <div className="font-semibold text-gray-900 hover:text-primary-600 transition-colors">
                        {item.company.name}
                      </div>
                      <div className="text-sm text-gray-600">{item.company.ticker}</div>
                    </Link>
                    <button
                      onClick={() => removeWatchlistMutation.mutate(item.company.ticker)}
                      className="text-red-600 hover:text-red-700 p-2"
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
            <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-8 text-center">
              <Star className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600">Your watchlist is empty</p>
              <p className="text-sm text-gray-500 mt-2">Add companies to your watchlist from company pages</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

