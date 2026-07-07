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
import WatchlistAddSearch from '@/features/watchlist/components/WatchlistAddSearch'
import CompanyLogo from '@/components/CompanyLogo'
import { ENABLE_ANALYSIS } from '@/lib/featureFlags'
import { Badge, buttonVariants, Card, GuidanceCard, type BadgeVariant } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'

function useAuthGate() {
  const router = useRouter()
  const { data: user, isLoading } = useQuery({
    queryKey: queryKeys.currentUser(),
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

// Status chips ride the Badge tonal recipes (beat/miss/new are tone names, not
// semantics — icon={null} at the render site strips their auto glyphs).
function getStatusBadge(status: string, needsRegeneration: boolean): { label: string; variant: BadgeVariant } {
  const [base, detail] = status.split(':')
  switch (base) {
    case 'ready':
      return { label: 'Ready', variant: 'beat' }
    case 'generating':
      return { label: detail ? `Generating (${detail})` : 'Generating', variant: 'brand' }
    case 'placeholder':
      return { label: 'Fallback', variant: 'new' }
    case 'error':
      return { label: 'Error', variant: 'miss' }
    default:
      return needsRegeneration
        ? { label: 'Needs Attention', variant: 'miss' }
        : { label: 'Pending', variant: 'neutral' }
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
    queryKey: queryKeys.watchlistInsights(),
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
          ENABLE_ANALYSIS ? (
            <Link href="/analysis" className={buttonVariants({ variant: 'primary' })}>
              <SparkleIcon className="h-4 w-4" />
              Analyze trends
            </Link>
          ) : undefined
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        {/* Add-from-search: track a company without visiting its page first. */}
        <WatchlistAddSearch />

        {isError && (
          <GuidanceCard
            variant="error"
            title="Unable to load watchlist insights"
            description="Please retry in a moment, or confirm you are signed in with an active session."
          />
        )}

        {insights.length === 0 ? (
          <GuidanceCard
            variant="empty"
            title="No watchlist companies yet"
            description="Use the search above to track your first company. You'll get an alert here and by email whenever it files with the SEC."
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
                // Non-interactive card (nothing on it is clickable as a whole) —
                // no hover affordance; the buttons inside carry the actions.
                <Card key={insight.company.id} className="p-6">
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div>
                      <div className="flex items-center space-x-3">
                        <CompanyLogo ticker={insight.company.ticker} name={insight.company.name} size={36} />
                        <h2 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">
                          {insight.company.name}
                        </h2>
                        <Badge variant="neutral">{insight.company.ticker}</Badge>
                        {badge && (
                          <Badge variant={badge.variant} icon={null}>
                            {badge.label}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-text-tertiary-light dark:text-text-secondary-dark mt-1">
                        {insight.total_filings} filing{insight.total_filings === 1 ? '' : 's'} on
                        record
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      {latest && (
                        <Link href={`/filing/${latest.id}`} className={buttonVariants({ variant: 'secondary' })}>
                          <CalendarDotsIcon className="h-4 w-4" />
                          View filing
                        </Link>
                      )}
                      <Link
                        href={`/company/${insight.company.ticker}`}
                        className={buttonVariants({ variant: 'primary' })}
                      >
                        <ArrowsCounterClockwiseIcon className="h-4 w-4" />
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
                            This summary needs regenerating. Open the filing and run it again.
                          </p>
                        ) : (
                          <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                            Summary is current. Nothing to do here.
                          </p>
                        )
                      ) : (
                        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                          Open the company page to load its filings from SEC EDGAR.
                        </p>
                      )}
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        )}
      </main>
    </div>
  )
}

