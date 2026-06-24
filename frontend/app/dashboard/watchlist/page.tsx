'use client'

import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { format, formatDistanceToNowStrict } from 'date-fns'
import { ArrowsCounterClockwiseIcon, CalendarDotsIcon, CircleNotchIcon, ClockIcon, SparkleIcon, WarningCircleIcon } from '@/lib/icons'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getWatchlistInsights, WatchlistInsight } from '@/features/watchlist/api/watchlist-api'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'
import WatchlistAddSearch from '@/components/watchlist/WatchlistAddSearch'
import { ENABLE_COMPARE } from '@/lib/featureFlags'

function useAuthGate() {
  const router = useRouter()
  const { data: user, isLoading } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
  })

  useEffect(() => {
    if (!isLoading && !user) {
      router.push('/login')
    }
  }, [router, isLoading, user])

  return { isReady: !isLoading, hasUser: Boolean(user) }
}

function getStatusBadge(status: string, needsRegeneration: boolean) {
  const [base, detail] = status.split(':')
  switch (base) {
    case 'ready':
      return { label: 'Ready', className: 'bg-gain-soft text-success-light dark:bg-gain-soft-dark dark:text-success-dark' }
    case 'generating':
      return {
        label: detail ? `Generating (${detail})` : 'Generating',
        className: 'bg-brand-weak text-brand-strong dark:bg-white/5 dark:text-brand-strong-dark',
      }
    case 'placeholder':
      return { label: 'Fallback', className: 'bg-warning-light/10 text-warning-light dark:bg-warning-dark/10 dark:text-warning-dark' }
    case 'error':
      return { label: 'Error', className: 'bg-loss-soft text-error-light dark:bg-loss-soft-dark dark:text-error-dark' }
    default:
      return {
        label: needsRegeneration ? 'Needs Attention' : 'Pending',
        className: needsRegeneration ? 'bg-loss-soft text-error-light dark:bg-loss-soft-dark dark:text-error-dark' : 'bg-brand-weak text-text-secondary-light dark:bg-white/5 dark:text-text-secondary-dark',
      }
  }
}

function formatRelative(dateLike?: string | null) {
  if (!dateLike) return 'Unknown'
  const date = new Date(dateLike)
  if (Number.isNaN(date.getTime())) return 'Unknown'
  return `${formatDistanceToNowStrict(date, { addSuffix: true })}`
}

function formatDate(dateLike?: string | null) {
  if (!dateLike) return '—'
  const date = new Date(dateLike)
  if (Number.isNaN(date.getTime())) return '—'
  return format(date, 'MMM dd, yyyy')
}

export default function WatchlistDashboardPage() {
  const { isReady, hasUser } = useAuthGate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['watchlist-insights'],
    queryFn: getWatchlistInsights,
    retry: false,
    enabled: hasUser,
  })

  const insights = useMemo(() => data ?? [], [data])

  if (!isReady || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background-light dark:bg-background-dark">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  if (!hasUser) {
    return null
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <SecondaryHeader
        title="Watchlist insights"
        subtitle="Monitor filings and summary freshness for tracked companies."
        backHref="/dashboard"
        backLabel="Back to dashboard"
        actions={
          ENABLE_COMPARE ? (
            <Link
              href="/compare"
              className="inline-flex items-center rounded-lg bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-4 py-2 text-sm font-semibold transition-colors"
            >
              <SparkleIcon className="h-4 w-4 mr-2" />
              Compare filings
            </Link>
          ) : undefined
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        {/* Add-from-search: track a company without visiting its page first. */}
        <WatchlistAddSearch />

        {isError && (
          <StateCard
            variant="error"
            title="Unable to load watchlist insights"
            message="Please retry in a moment, or confirm you are signed in with an active session."
          />
        )}

        {insights.length === 0 ? (
          <StateCard
            title="No watchlist companies yet"
            message="Use the search above to track your first company — you'll get an alert here (and by email) whenever it files with the SEC."
          />
        ) : (
          <div className="grid gap-6">
            {insights.map((insight: WatchlistInsight) => {
              const latest = insight.latest_filing
              const badge = latest
                ? getStatusBadge(latest.summary_status, latest.needs_regeneration)
                : null
              const progressStage = latest?.progress?.stage
              const elapsedSeconds = latest?.progress?.elapsedSeconds ?? latest?.progress?.elapsed

              return (
                <div
                  key={insight.company.id}
                  className="bg-panel-light dark:bg-panel-dark border border-border-light dark:border-border-dark rounded-xl shadow-sm p-6 transition hover:border-brand-light/30"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div>
                      <div className="flex items-center space-x-3">
                        <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                          {insight.company.name}
                        </h2>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-brand-weak text-text-secondary-light dark:bg-white/5 dark:text-text-secondary-dark">
                          {insight.company.ticker}
                        </span>
                        {badge && (
                          <span
                            className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-semibold ${badge.className}`}
                          >
                            {badge.label}
                          </span>
                        )}
                      </div>
                      <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                        {insight.total_filings} filing{insight.total_filings === 1 ? '' : 's'} on
                        record
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      {latest && (
                        <Link
                          href={`/filing/${latest.id}`}
                          className="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg border border-border-light dark:border-border-dark text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/5 transition-colors"
                        >
                          <CalendarDotsIcon className="h-4 w-4 mr-2" />
                          View filing
                        </Link>
                      )}
                      <Link
                        href={`/company/${insight.company.ticker}`}
                        className="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark transition-colors"
                      >
                        <ArrowsCounterClockwiseIcon className="h-4 w-4 mr-2" />
                        Manage coverage
                      </Link>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 md:grid-cols-3">
                    <div className="bg-background-light dark:bg-background-dark rounded-lg p-4 border border-border-light dark:border-border-dark">
                      <div className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">Latest filing</div>
                      {latest ? (
                        <>
                          <div className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                            {latest.filing_type}
                          </div>
                          <div className="flex items-center space-x-2 text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                            <CalendarDotsIcon className="h-4 w-4" />
                            <span>{formatDate(latest.filing_date)}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                            <ClockIcon className="h-4 w-4" />
                            <span>Period end: {formatDate(latest.period_end_date)}</span>
                          </div>
                        </>
                      ) : (
                        <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
                          No filings synced yet for this company.
                        </p>
                      )}
                    </div>

                    <div className="bg-background-light dark:bg-background-dark rounded-lg p-4 border border-border-light dark:border-border-dark">
                      <div className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">Summary freshness</div>
                      {latest && latest.summary_id ? (
                        <>
                          <div className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">
                            Updated {formatRelative(latest.summary_updated_at || latest.summary_created_at)}
                          </div>
                          <div className="text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                            Summary ID #{latest.summary_id}
                          </div>
                        </>
                      ) : latest && progressStage ? (
                        <>
                          <div className="text-lg font-semibold text-brand-strong dark:text-brand-strong-dark capitalize">
                            {progressStage} in progress
                          </div>
                          {typeof elapsedSeconds === 'number' && (
                            <div className="text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                              Elapsed {Math.max(0, Math.round(elapsedSeconds))}s
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="flex items-center space-x-2 text-sm text-warning-light dark:text-warning-dark">
                          <WarningCircleIcon className="h-4 w-4" />
                          <span>No AI summary generated yet</span>
                        </div>
                      )}
                    </div>

                    <div className="bg-background-light dark:bg-background-dark rounded-lg p-4 border border-border-light dark:border-border-dark">
                      <div className="text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-1">Next steps</div>
                      {latest ? (
                        latest.needs_regeneration ? (
                          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                            Flag this filing for regeneration before distributing to clients.
                          </p>
                        ) : (
                          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                            Summary is current. Consider exporting a briefing pack for your next
                            meeting.
                          </p>
                        )
                      ) : (
                        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                          Ingest filings for this company to begin tracking.
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}

