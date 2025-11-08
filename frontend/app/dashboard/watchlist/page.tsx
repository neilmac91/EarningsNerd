'use client'

import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import Link from 'next/link'
import { format, formatDistanceToNowStrict } from 'date-fns'
import {
  AlertCircle,
  ArrowLeft,
  CalendarDays,
  Clock,
  Loader2,
  RefreshCcw,
  Sparkles,
} from 'lucide-react'
import { getWatchlistInsights, WatchlistInsight } from '@/lib/api'

function useAuthGate() {
  const router = useRouter()
  const [isReady, setIsReady] = useState(false)
  const [hasToken, setHasToken] = useState(false)

  useEffect(() => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null
    if (!token) {
      router.push('/login')
    } else {
      setHasToken(true)
    }
    setIsReady(true)
  }, [router])

  return { isReady, hasToken }
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
  const { isReady, hasToken } = useAuthGate()

  const { data, isLoading, isError } = useQuery({
    queryKey: ['watchlist-insights'],
    queryFn: getWatchlistInsights,
    retry: false,
    enabled: hasToken,
  })

  const insights = useMemo(() => data ?? [], [data])

  if (!isReady || isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!hasToken) {
    return null
  }

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex items-center justify-between">
            <button
              onClick={() => router.push('/dashboard')}
              className="inline-flex items-center text-slate-600 hover:text-slate-900 font-medium transition-colors"
            >
              <ArrowLeft className="h-4 w-4 mr-2" />
              Back to dashboard
            </button>
            <Link
              href="/compare"
              className="inline-flex items-center px-4 py-2 rounded-lg bg-primary-600 text-white text-sm font-semibold hover:bg-primary-700 transition-colors"
            >
              <Sparkles className="h-4 w-4 mr-2" />
              Compare filings
            </Link>
          </div>
          <div className="mt-6">
            <h1 className="text-3xl font-bold text-slate-900">Watchlist insights</h1>
            <p className="text-slate-500 max-w-2xl mt-2">
              Monitor the freshest filings for your tracked companies and spot summaries that need a
              refresh before morning briefing.
            </p>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10 space-y-8">
        {isError && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-600 mt-0.5" />
            <div>
              <p className="text-red-700 font-medium">Unable to load watchlist insights.</p>
              <p className="text-sm text-red-600">
                Please retry in a moment, or confirm you are signed in with an active session.
              </p>
            </div>
          </div>
        )}

        {insights.length === 0 ? (
          <div className="bg-white border border-dashed border-gray-300 rounded-xl p-10 text-center">
            <h2 className="text-xl font-semibold text-gray-900 mb-2">No watchlist companies yet</h2>
            <p className="text-gray-600 mb-4">
              Track a company from any company page to see its filing freshness and summary status
              here.
            </p>
            <Link
              href="/company/AAPL"
              className="inline-flex items-center px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-medium"
            >
              Explore companies
            </Link>
          </div>
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

