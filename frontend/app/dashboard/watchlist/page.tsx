'use client'

import { useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { format, formatDistanceToNowStrict } from 'date-fns'
import {
  AlertCircle,
  CalendarDays,
  Clock,
  Loader2,
  RefreshCcw,
  Sparkles,
} from 'lucide-react'
import { getCurrentUserSafe, getWatchlistInsights, WatchlistInsight } from '@/lib/api'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'

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
      return { label: 'Ready', className: 'bg-green-100 text-green-800' }
    case 'generating':
      return {
        label: detail ? `Generating (${detail})` : 'Generating',
        className: 'bg-blue-100 text-blue-800',
      }
    case 'placeholder':
      return { label: 'Fallback', className: 'bg-amber-100 text-amber-800' }
    case 'error':
      return { label: 'Error', className: 'bg-red-100 text-red-800' }
    default:
      return {
        label: needsRegeneration ? 'Needs Attention' : 'Pending',
        className: needsRegeneration ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700',
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
  const router = useRouter()
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
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!hasUser) {
    return null
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <SecondaryHeader
        title="Watchlist insights"
        subtitle="Monitor filings and summary freshness for tracked companies."
        backHref="/dashboard"
        backLabel="Back to dashboard"
        actions={
          <Link
            href="/compare"
            className="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition-colors"
          >
            <Sparkles className="h-4 w-4 mr-2" />
            Compare filings
          </Link>
        }
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
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
            message="Track a company from any company page to see its filing freshness and summary status here."
            action={
              <Link
                href="/company/AAPL"
                className="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition-colors"
              >
                Explore companies
              </Link>
            }
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
                  className="bg-white border border-gray-200 rounded-xl shadow-sm p-6 transition hover:border-primary-200"
                >
                  <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
                    <div>
                      <div className="flex items-center space-x-3">
                        <h2 className="text-2xl font-semibold text-gray-900">
                          {insight.company.name}
                        </h2>
                        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 text-slate-700">
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
                      <p className="text-sm text-slate-500 mt-1">
                        {insight.total_filings} filing{insight.total_filings === 1 ? '' : 's'} on
                        record
                      </p>
                    </div>
                    <div className="flex flex-wrap items-center gap-3">
                      {latest && (
                        <Link
                          href={`/filing/${latest.id}`}
                          className="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg border border-gray-200 text-gray-700 hover:bg-gray-50 transition-colors"
                        >
                          <CalendarDays className="h-4 w-4 mr-2" />
                          View filing
                        </Link>
                      )}
                      <Link
                        href={`/company/${insight.company.ticker}`}
                        className="inline-flex items-center px-3 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 transition-colors"
                      >
                        <RefreshCcw className="h-4 w-4 mr-2" />
                        Manage coverage
                      </Link>
                    </div>
                  </div>

                  <div className="mt-6 grid gap-4 md:grid-cols-3">
                    <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
                      <div className="text-sm font-medium text-slate-600 mb-1">Latest filing</div>
                      {latest ? (
                        <>
                          <div className="text-lg font-semibold text-slate-900">
                            {latest.filing_type}
                          </div>
                          <div className="flex items-center space-x-2 text-sm text-slate-500 mt-1">
                            <CalendarDays className="h-4 w-4" />
                            <span>{formatDate(latest.filing_date)}</span>
                          </div>
                          <div className="flex items-center space-x-2 text-sm text-slate-500 mt-1">
                            <Clock className="h-4 w-4" />
                            <span>Period end: {formatDate(latest.period_end_date)}</span>
                          </div>
                        </>
                      ) : (
                        <p className="text-sm text-slate-500">
                          No filings synced yet for this company.
                        </p>
                      )}
                    </div>

                    <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
                      <div className="text-sm font-medium text-slate-600 mb-1">Summary freshness</div>
                      {latest && latest.summary_id ? (
                        <>
                          <div className="text-lg font-semibold text-slate-900">
                            Updated {formatRelative(latest.summary_updated_at || latest.summary_created_at)}
                          </div>
                          <div className="text-sm text-slate-500 mt-1">
                            Summary ID #{latest.summary_id}
                          </div>
                        </>
                      ) : latest && progressStage ? (
                        <>
                          <div className="text-lg font-semibold text-blue-700 capitalize">
                            {progressStage} in progress
                          </div>
                          {typeof elapsedSeconds === 'number' && (
                            <div className="text-sm text-slate-500 mt-1">
                              Elapsed {Math.max(0, Math.round(elapsedSeconds))}s
                            </div>
                          )}
                        </>
                      ) : (
                        <div className="flex items-center space-x-2 text-sm text-amber-600">
                          <AlertCircle className="h-4 w-4" />
                          <span>No AI summary generated yet</span>
                        </div>
                      )}
                    </div>

                    <div className="bg-slate-50 rounded-lg p-4 border border-slate-100">
                      <div className="text-sm font-medium text-slate-600 mb-1">Next steps</div>
                      {latest ? (
                        latest.needs_regeneration ? (
                          <p className="text-sm text-slate-600">
                            Flag this filing for regeneration before distributing to clients.
                          </p>
                        ) : (
                          <p className="text-sm text-slate-600">
                            Summary is current. Consider exporting a briefing pack for your next
                            meeting.
                          </p>
                        )
                      ) : (
                        <p className="text-sm text-slate-600">
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

