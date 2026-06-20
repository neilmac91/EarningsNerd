'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCompany, Company } from '@/features/companies/api/companies-api'
import { getCompanyFilings, Filing } from '@/features/filings/api/filings-api'
import { addToWatchlist, removeFromWatchlist, getWatchlist, WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { FileText, ExternalLink, Loader2, ChevronDown, Filter, Star, Sparkles, ArrowRight } from 'lucide-react'
import { toast } from 'sonner'
import Link from 'next/link'
import { format } from 'date-fns'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import analytics from '@/lib/analytics'
import { ENABLE_RECOMMENDED_FILING, ENABLE_FINANCIAL_CHARTS } from '@/lib/featureFlags'
import FundamentalsTrendChart from '@/features/fundamentals/components/FundamentalsTrendChart'
import PeerComparisonPanel from '@/features/peers/components/PeerComparisonPanel'

export default function CompanyPageClient() {
  const params = useParams()
  const ticker = (params?.ticker as string | undefined) ?? ''
  const normalizedTicker = ticker.toUpperCase()

  // All hooks must be called before any conditional returns
  const currentYear = new Date().getFullYear().toString()
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set([currentYear]))
  const [filterType, setFilterType] = useState<'10-K' | '10-Q' | null>(null)
  const hasTrackedCompanyView = useRef(false)

  const { data: company, isLoading: companyLoading, error: companyError } = useQuery<Company>({
    queryKey: ['company', normalizedTicker],
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
    enabled: !!normalizedTicker,
  })

  const { data: filings, isLoading: filingsLoading, isError: filingsError, error: filingsErrorData, refetch: refetchFilings, isFetching: filingsRefetching } = useQuery<Filing[]>({
    queryKey: ['filings', normalizedTicker],
    queryFn: () => getCompanyFilings(normalizedTicker),
    enabled: !!company && !!normalizedTicker,
    retry: 1,
  })

  const { data: currentUser } = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUserSafe,
    retry: false,
  })

  const { data: watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    retry: false,
    enabled: !!currentUser,
  })

  const queryClient = useQueryClient()

  // The desired action (`shouldAdd`) is decided at click time from the rendered state, not
  // re-derived inside the mutation — onMutate flips the cache optimistically, so reading it
  // back in mutationFn would invert the decision.
  const watchlistMutation = useMutation({
    mutationFn: async ({ ticker: tickerToToggle, shouldAdd }: { ticker: string; shouldAdd: boolean }) => {
      if (shouldAdd) {
        await addToWatchlist(tickerToToggle)
        return { action: 'added' as const, ticker: tickerToToggle }
      }
      await removeFromWatchlist(tickerToToggle)
      return { action: 'removed' as const, ticker: tickerToToggle }
    },
    // Optimistic toggle: flip the star instantly, then reconcile with the server.
    onMutate: async ({ ticker: tickerToToggle, shouldAdd }) => {
      await queryClient.cancelQueries({ queryKey: ['watchlist'] })
      const previous = queryClient.getQueryData<WatchlistItem[]>(['watchlist'])
      queryClient.setQueryData<WatchlistItem[]>(['watchlist'], (old) => {
        const list = old ?? []
        if (shouldAdd) {
          if (!company || list.some((w) => w.company.ticker === tickerToToggle)) return list
          return [
            ...list,
            {
              id: -Date.now(), // temporary id; replaced by the real row on refetch (onSettled)
              company_id: company.id,
              created_at: new Date().toISOString(),
              company: { id: company.id, ticker: company.ticker, name: company.name },
            },
          ]
        }
        return list.filter((w) => w.company.ticker !== tickerToToggle)
      })
      return { previous }
    },
    onError: (_error, _variables, context) => {
      // Roll back to the pre-click snapshot and explain why the star didn't stick.
      if (context?.previous !== undefined) {
        queryClient.setQueryData(['watchlist'], context.previous)
      }
      toast.error("Couldn't update your watchlist. Please try again.")
    },
    onSuccess: (result) => {
      if (result.action === 'added') {
        analytics.watchlistAdded(result.ticker)
        toast.success(`${company?.ticker ?? result.ticker} added to your watchlist`)
      } else {
        analytics.watchlistRemoved(result.ticker)
        toast.success(`${company?.ticker ?? result.ticker} removed from your watchlist`)
      }
    },
    // Always refetch so the temporary optimistic row is replaced by the canonical server row.
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    },
  })

  const isInWatchlist = watchlist?.some((w: WatchlistItem) => w.company.ticker === normalizedTicker)

  useEffect(() => {
    if (!hasTrackedCompanyView.current && company) {
      analytics.companyViewed(company.ticker, company.name)
      hasTrackedCompanyView.current = true
    }
  }, [company])

  // Memoize filtered and grouped filings to avoid recalculating on every render.
  // Declared before the early returns below so hook order stays stable across renders.
  const { groupedFilings, sortedYears, recommendedFiling } = useMemo(() => {
    const filtered = filterType
      ? filings?.filter((f) => f.filing_type === filterType)
      : filings

    // Group filings by year
    const grouped = filtered?.reduce((acc, filing) => {
      const year = new Date(filing.filing_date).getFullYear().toString()
      if (!acc[year]) {
        acc[year] = []
      }
      acc[year].push(filing)
      return acc
    }, {} as Record<string, Filing[]>) || {}

    // Sort years in descending order (newest first)
    const years = Object.keys(grouped).sort((a, b) => parseInt(b) - parseInt(a))

    // Recommended filing: latest 10-K (the canonical annual report) if available,
    // otherwise the most recent filing of any type. Computed from the FULL list (not the
    // active type filter) so the recommendation is stable as the user filters.
    const byDateDesc = (a: Filing, b: Filing) =>
      new Date(b.filing_date).getTime() - new Date(a.filing_date).getTime()
    const tenKs = (filings ?? []).filter((f) => f.filing_type === '10-K')
    const recommendedFiling =
      [...tenKs].sort(byDateDesc)[0] ?? [...(filings ?? [])].sort(byDateDesc)[0] ?? null

    return { groupedFilings: grouped, sortedYears: years, recommendedFiling }
  }, [filings, filterType])

  // Handle case where ticker might not be available
  if (!ticker) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Invalid ticker</h1>
          <Link href="/" className="text-primary-600 hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    )
  }

  if (companyLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
      </div>
    )
  }

  if (!company) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Company not found</h1>
          <p className="text-gray-600 mb-4">
            {companyError ? `Error: ${companyError instanceof Error ? companyError.message : 'Failed to load company'}` : `Could not find company with ticker "${normalizedTicker}"`}
          </p>
          <Link href="/" className="text-primary-600 hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    )
  }

  // TypeScript type guard: company is definitely defined at this point (checked above)
  // Use non-null assertion since we've already verified company exists
  const companyData = company!

  const toggleYear = (year: string) => {
    const newExpanded = new Set(expandedYears)
    if (newExpanded.has(year)) {
      newExpanded.delete(year)
    } else {
      newExpanded.add(year)
    }
    setExpandedYears(newExpanded)
  }

  // Get styling for filing type
  const getFilingTypeStyles = (filingType: string) => {
    switch (filingType) {
      case '10-K':
        return {
          borderColor: 'border-l-blue-600 dark:border-l-blue-500',
          bgColor: 'bg-blue-50/50 dark:bg-blue-900/20',
          hoverBg: 'hover:bg-blue-50 dark:hover:bg-blue-900/30',
          iconColor: 'text-blue-600 dark:text-blue-400',
          badgeBg: 'bg-blue-100 dark:bg-blue-900/40',
          badgeText: 'text-blue-800 dark:text-blue-300',
        }
      case '10-Q':
        return {
          borderColor: 'border-l-teal-600 dark:border-l-teal-500',
          bgColor: 'bg-teal-50/50 dark:bg-teal-900/20',
          hoverBg: 'hover:bg-teal-50 dark:hover:bg-teal-900/30',
          iconColor: 'text-teal-600 dark:text-teal-400',
          badgeBg: 'bg-teal-100 dark:bg-teal-900/40',
          badgeText: 'text-teal-800 dark:text-teal-300',
        }
      default:
        return {
          borderColor: 'border-l-gray-400 dark:border-l-gray-500',
          bgColor: 'bg-gray-50/50 dark:bg-gray-800/50',
          hoverBg: 'hover:bg-gray-50 dark:hover:bg-gray-800',
          iconColor: 'text-gray-400 dark:text-gray-500',
          badgeBg: 'bg-gray-100 dark:bg-gray-700',
          badgeText: 'text-gray-800 dark:text-gray-300',
        }
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      {/* Header */}
      <header className="bg-white dark:bg-slate-900 border-b border-gray-200 dark:border-gray-800 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:space-x-4">
              <Link href="/" className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 font-medium transition-colors">
                ← Back
              </Link>
              <div className="border-l-0 sm:border-l border-gray-200 dark:border-gray-700 sm:pl-4 flex-1">
                <div className="flex items-center space-x-3">
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{companyData.name}</h1>
                  {currentUser && (
                    <button
                      onClick={() => watchlistMutation.mutate({ ticker: normalizedTicker, shouldAdd: !isInWatchlist })}
                      disabled={watchlistMutation.isPending}
                      aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                      aria-pressed={Boolean(isInWatchlist)}
                      className={`p-2 rounded-lg transition-colors ${
                        isInWatchlist
                          ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 dark:text-yellow-400 hover:bg-yellow-200 dark:hover:bg-yellow-900/50'
                          : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                      }`}
                      title={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                    >
                      {isInWatchlist ? (
                        <Star className="h-5 w-5 fill-current" />
                      ) : (
                        <Star className="h-5 w-5" />
                      )}
                    </button>
                  )}
                </div>
                <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500 dark:text-gray-400">
                  <span className="font-medium">{companyData.ticker}</span>
                  {companyData.exchange && <span>{companyData.exchange}</span>}
                  {companyData.stock_quote?.price !== undefined && companyData.stock_quote?.price !== null && (
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-gray-900 dark:text-white">
                        {fmtCurrency(companyData.stock_quote.price, { digits: 2, compact: false })}
                      </span>
                      {companyData.stock_quote.change_percent !== undefined && companyData.stock_quote.change_percent !== null && (
                        <span
                          className={`font-medium ${
                            companyData.stock_quote.change_percent >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                          }`}
                        >
                          {fmtPercent(companyData.stock_quote.change_percent, { digits: 2, signed: true })}
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Multi-year fundamentals trend (self-fetches; renders nothing until facts exist) */}
        {ENABLE_FINANCIAL_CHARTS && <FundamentalsTrendChart ticker={normalizedTicker} />}
        {ENABLE_FINANCIAL_CHARTS && <PeerComparisonPanel ticker={normalizedTicker} />}

        {/* Filings Section */}
        <section className="bg-white dark:bg-slate-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">SEC Filings</h2>
            {filings && filings.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Filter className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => setFilterType(null)}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-md transition-colors ${
                      filterType === null
                        ? 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`}
                  >
                    All Types
                  </button>
                  <button
                    onClick={() => setFilterType('10-K')}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-md transition-colors ${
                      filterType === '10-K'
                        ? 'bg-blue-600 dark:bg-blue-500 text-white'
                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                    }`}
                  >
                    10-K
                  </button>
                  <button
                    onClick={() => setFilterType('10-Q')}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-md transition-colors ${
                      filterType === '10-Q'
                        ? 'bg-teal-600 dark:bg-teal-500 text-white'
                        : 'bg-teal-100 dark:bg-teal-900/30 text-teal-800 dark:text-teal-300 hover:bg-teal-200 dark:hover:bg-teal-900/50'
                    }`}
                  >
                    10-Q
                  </button>
                </div>
              </div>
            )}
          </div>

          {ENABLE_RECOMMENDED_FILING && !filingsLoading && !filingsError && recommendedFiling && (
            <div className="mb-6 rounded-xl border border-primary-200 dark:border-primary-500/40 bg-gradient-to-r from-primary-50 to-white dark:from-primary-900/20 dark:to-slate-900 p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <Sparkles className="mt-0.5 h-5 w-5 flex-shrink-0 text-primary-600 dark:text-primary-400" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center rounded-full bg-primary-600 px-2 py-0.5 text-xs font-semibold text-white">
                        Recommended
                      </span>
                      <span className="text-sm font-semibold text-gray-900 dark:text-white">
                        {recommendedFiling.filing_type} · {format(new Date(recommendedFiling.filing_date), 'MMM d, yyyy')}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-gray-600 dark:text-gray-400">
                      Not sure where to start? This is {companyData.name}&apos;s most recent{' '}
                      {recommendedFiling.filing_type === '10-K' ? 'annual report' : 'filing'} — get an instant AI summary.
                    </p>
                  </div>
                </div>
                <Link
                  href={`/filing/${recommendedFiling.id}`}
                  className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md bg-primary-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-primary-700"
                >
                  Summarize this filing
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          )}

          {filingsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : filingsError ? (
            <div className="rounded-lg border border-red-200/60 bg-red-50/80 p-6 text-center text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
              <p className="font-semibold">Unable to load filings right now.</p>
              <p className="mt-1 text-xs text-red-600/80 dark:text-red-200/80">
                {filingsErrorData instanceof Error ? filingsErrorData.message : 'Please try again shortly.'}
              </p>
              <button
                type="button"
                onClick={() => refetchFilings()}
                disabled={filingsRefetching}
                className="mt-3 inline-flex items-center rounded-md border border-red-200 bg-white/80 px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-white dark:border-red-400/40 dark:bg-white/10 dark:text-red-100 dark:hover:bg-white/20 disabled:opacity-60"
              >
                {filingsRefetching ? 'Retrying…' : 'Retry'}
              </button>
            </div>
          ) : sortedYears.length > 0 ? (
            <div className="space-y-4">
              {sortedYears.map((year) => {
                const yearFilings = groupedFilings[year]
                const isExpanded = expandedYears.has(year)
                const filingCount = yearFilings?.length || 0

                return (
                  <div key={year} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                    {/* Year Header */}
                    <button
                      onClick={() => toggleYear(year)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-gray-50 dark:bg-gray-800 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors text-left"
                    >
                      <div className="flex items-center space-x-3">
                        {isExpanded ? (
                          <ChevronDown className="h-5 w-5 text-gray-500 dark:text-gray-400" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-gray-500 dark:text-gray-400 -rotate-90" />
                        )}
                        <span className="font-semibold text-gray-900 dark:text-white text-lg">{year}</span>
                        <span className="text-sm text-gray-500 dark:text-gray-400">({filingCount} {filingCount === 1 ? 'filing' : 'filings'})</span>
                      </div>
                    </button>

                    {/* Year Filings */}
                    {isExpanded && yearFilings && (
                      <div className="p-4 space-y-3 bg-white dark:bg-slate-900">
                        {yearFilings.map((filing) => {
                          const styles = getFilingTypeStyles(filing.filing_type)
                          return (
                            <div
                              key={filing.id}
                              className={`border-l-4 ${styles.borderColor} border-r border-t border-b border-gray-200 dark:border-gray-700 rounded-lg p-4 ${styles.bgColor} ${styles.hoverBg} transition-colors`}
                            >
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center space-x-3">
                                    <FileText className={`h-5 w-5 ${styles.iconColor}`} />
                                    <div>
                                      <div className="flex items-center space-x-2">
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${styles.badgeBg} ${styles.badgeText}`}>
                                          {filing.filing_type}
                                        </span>
                                        {ENABLE_RECOMMENDED_FILING && recommendedFiling?.id === filing.id && (
                                          <span className="inline-flex items-center gap-1 rounded-full bg-primary-600 px-2 py-0.5 text-xs font-semibold text-white">
                                            <Sparkles className="h-3 w-3" />
                                            Recommended
                                          </span>
                                        )}
                                        <span className="text-sm text-gray-500 dark:text-gray-400">
                                          {format(new Date(filing.filing_date), 'MMM d, yyyy')}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:gap-2 sm:ml-4">
                                  {filing.sec_url && (
                                    <a
                                      href={filing.sec_url}
                                      target="_blank"
                                      rel="noopener noreferrer"
                                      className="inline-flex items-center gap-2 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 text-sm font-medium rounded-md hover:bg-gray-50 dark:hover:bg-gray-800 hover:border-gray-400 dark:hover:border-gray-500 transition-colors"
                                      title="Open original filing on SEC EDGAR"
                                    >
                                      <ExternalLink className="h-4 w-4" />
                                      <span>View on SEC EDGAR</span>
                                    </a>
                                  )}
                                  <Link
                                    href={`/filing/${filing.id}`}
                                    className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 transition-colors"
                                  >
                                    Generate Filing Summary
                                  </Link>
                                </div>
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
              <p className="text-gray-500 dark:text-gray-400">No filings found for this company.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

