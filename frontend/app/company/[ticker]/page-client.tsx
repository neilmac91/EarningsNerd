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
import { directionText, directionOf } from '@/lib/financialTone'
import analytics from '@/lib/analytics'
import { getEntryPoint } from '@/lib/entryPoint'
import { ENABLE_RECOMMENDED_FILING, ENABLE_FINANCIAL_CHARTS, ENABLE_INSIDER_ACTIVITY } from '@/lib/featureFlags'
import FundamentalsTrendChart from '@/features/fundamentals/components/FundamentalsTrendChart'
import PeerComparisonPanel from '@/features/peers/components/PeerComparisonPanel'
import InsiderActivityPanel from '@/features/insiders/components/InsiderActivityPanel'

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
      analytics.companyViewed(company.ticker, company.name, getEntryPoint())
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
          <Link href="/" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    )
  }

  if (companyLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
      </div>
    )
  }

  if (!company) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-4">Company not found</h1>
          <p className="text-text-secondary-light dark:text-text-secondary-dark mb-4">
            {companyError ? `Error: ${companyError instanceof Error ? companyError.message : 'Failed to load company'}` : `Could not find company with ticker "${normalizedTicker}"`}
          </p>
          <Link href="/" className="text-brand-strong dark:text-brand-strong-dark hover:underline">
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
          borderColor: 'border-l-brand-strong dark:border-l-brand-strong-dark',
          bgColor: 'bg-brand-weak dark:bg-white/5',
          hoverBg: 'hover:bg-brand-weak dark:hover:bg-white/10',
          iconColor: 'text-brand-strong dark:text-brand-strong-dark',
          badgeBg: 'bg-brand-weak dark:bg-white/10',
          badgeText: 'text-brand-strong dark:text-brand-strong-dark',
        }
      case '10-Q':
        return {
          borderColor: 'border-l-info-light dark:border-l-info-dark',
          bgColor: 'bg-info-light/10 dark:bg-info-dark/10',
          hoverBg: 'hover:bg-info-light/15 dark:hover:bg-info-dark/15',
          iconColor: 'text-info-light dark:text-info-dark',
          badgeBg: 'bg-info-light/10 dark:bg-info-dark/15',
          badgeText: 'text-info-light dark:text-info-dark',
        }
      default:
        return {
          borderColor: 'border-l-border-light dark:border-l-border-dark',
          bgColor: 'bg-background-light dark:bg-background-dark',
          hoverBg: 'hover:bg-background-light dark:hover:bg-background-dark',
          iconColor: 'text-text-tertiary-light dark:text-text-secondary-dark',
          badgeBg: 'bg-background-light dark:bg-white/5',
          badgeText: 'text-text-secondary-light dark:text-text-secondary-dark',
        }
    }
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      {/* Header */}
      <header className="bg-panel-light dark:bg-panel-dark border-b border-border-light dark:border-border-dark shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:space-x-4">
              <Link href="/" className="text-text-secondary-light dark:text-text-secondary-dark hover:text-text-primary-light dark:hover:text-text-primary-dark font-medium transition-colors">
                ← Back
              </Link>
              <div className="border-l-0 sm:border-l border-border-light dark:border-border-dark sm:pl-4 flex-1">
                <div className="flex items-center space-x-3">
                  <h1 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark">{companyData.name}</h1>
                  {currentUser && (
                    <button
                      onClick={() => watchlistMutation.mutate({ ticker: normalizedTicker, shouldAdd: !isInWatchlist })}
                      disabled={watchlistMutation.isPending}
                      aria-label={isInWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
                      aria-pressed={Boolean(isInWatchlist)}
                      className={`p-2 rounded-lg transition-colors ${
                        isInWatchlist
                          ? 'bg-warning-light/10 dark:bg-warning-dark/10 text-warning-light dark:text-warning-dark hover:bg-warning-light/20 dark:hover:bg-warning-dark/20'
                          : 'border border-border-light dark:border-white/10 bg-background-light dark:bg-white/5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/10'
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
                <div className="mt-1 flex items-center space-x-4 text-sm text-text-tertiary-light dark:text-text-secondary-dark">
                  <span className="font-medium">{companyData.ticker}</span>
                  {companyData.exchange && <span>{companyData.exchange}</span>}
                  {companyData.stock_quote?.price !== undefined && companyData.stock_quote?.price !== null && (
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                        {fmtCurrency(companyData.stock_quote.price, { digits: 2, compact: false })}
                      </span>
                      {companyData.stock_quote.change_percent !== undefined && companyData.stock_quote.change_percent !== null && (
                        <span
                          className={`font-medium ${directionText[directionOf(companyData.stock_quote.change_percent)]}`}
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
        {/* Insider (Form 4) activity — self-fetches; live SEC read, off by default */}
        {ENABLE_INSIDER_ACTIVITY && <InsiderActivityPanel ticker={normalizedTicker} />}

        {/* Filings Section */}
        <section className="bg-panel-light dark:bg-panel-dark rounded-lg shadow-sm border border-border-light dark:border-border-dark p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-6">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">SEC Filings</h2>
            {filings && filings.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Filter className="h-4 w-4 text-text-tertiary-light dark:text-text-secondary-dark" />
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => setFilterType(null)}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-md transition-colors ${
                      filterType === null
                        ? 'bg-text-primary-light dark:bg-text-primary-dark text-panel-light dark:text-background-dark'
                        : 'bg-background-light dark:bg-white/5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/10'
                    }`}
                  >
                    All Types
                  </button>
                  <button
                    onClick={() => setFilterType('10-K')}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-md transition-colors ${
                      filterType === '10-K'
                        ? 'bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                        : 'bg-brand-weak dark:bg-white/5 text-brand-strong dark:text-brand-strong-dark hover:bg-brand-weak/70 dark:hover:bg-white/10'
                    }`}
                  >
                    10-K
                  </button>
                  <button
                    onClick={() => setFilterType('10-Q')}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-md transition-colors ${
                      filterType === '10-Q'
                        ? 'bg-brand-strong dark:bg-brand-dark text-white'
                        : 'bg-brand-weak dark:bg-white/5 text-brand-strong dark:text-brand-strong-dark hover:bg-brand-weak/70 dark:hover:bg-white/10'
                    }`}
                  >
                    10-Q
                  </button>
                </div>
              </div>
            )}
          </div>

          {ENABLE_RECOMMENDED_FILING && !filingsLoading && !filingsError && recommendedFiling && (
            <div className="mb-6 rounded-xl border border-brand-light/30 dark:border-brand-light/30 bg-gradient-to-r from-brand-weak to-panel-light dark:from-white/5 dark:to-panel-dark p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <Sparkles className="mt-0.5 h-5 w-5 flex-shrink-0 text-brand-strong dark:text-brand-strong-dark" />
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center rounded-full bg-brand-strong dark:bg-brand-dark px-2 py-0.5 text-xs font-semibold text-white dark:text-background-dark">
                        Recommended
                      </span>
                      <span className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                        {recommendedFiling.filing_type} · {format(new Date(recommendedFiling.filing_date), 'MMM d, yyyy')}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                      Not sure where to start? This is {companyData.name}&apos;s most recent{' '}
                      {recommendedFiling.filing_type === '10-K' ? 'annual report' : 'filing'} — get an instant AI summary.
                    </p>
                  </div>
                </div>
                <Link
                  href={`/filing/${recommendedFiling.id}`}
                  className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark px-4 py-2 text-sm font-semibold transition-colors"
                >
                  Summarize this filing
                  <ArrowRight className="h-4 w-4" />
                </Link>
              </div>
            </div>
          )}

          {filingsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
            </div>
          ) : filingsError ? (
            <div className="rounded-lg border border-error-light/30 bg-error-light/10 p-6 text-center text-sm text-error-light dark:border-error-dark/40 dark:bg-error-dark/10 dark:text-error-dark">
              <p className="font-semibold">Unable to load filings right now.</p>
              <p className="mt-1 text-xs text-error-light/80 dark:text-error-dark/80">
                {filingsErrorData instanceof Error ? filingsErrorData.message : 'Please try again shortly.'}
              </p>
              <button
                type="button"
                onClick={() => refetchFilings()}
                disabled={filingsRefetching}
                className="mt-3 inline-flex items-center rounded-md border border-error-light/30 bg-panel-light/80 px-3 py-1 text-xs font-medium text-error-light transition hover:bg-panel-light dark:border-error-dark/40 dark:bg-white/10 dark:text-error-dark dark:hover:bg-white/20 disabled:opacity-60"
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
                  <div key={year} className="border border-border-light dark:border-border-dark rounded-lg overflow-hidden">
                    {/* Year Header */}
                    <button
                      onClick={() => toggleYear(year)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-background-light dark:bg-white/5 hover:bg-brand-weak dark:hover:bg-white/10 transition-colors text-left"
                    >
                      <div className="flex items-center space-x-3">
                        {isExpanded ? (
                          <ChevronDown className="h-5 w-5 text-text-tertiary-light dark:text-text-secondary-dark" />
                        ) : (
                          <ChevronDown className="h-5 w-5 text-text-tertiary-light dark:text-text-secondary-dark -rotate-90" />
                        )}
                        <span className="font-semibold text-text-primary-light dark:text-text-primary-dark text-lg">{year}</span>
                        <span className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">({filingCount} {filingCount === 1 ? 'filing' : 'filings'})</span>
                      </div>
                    </button>

                    {/* Year Filings */}
                    {isExpanded && yearFilings && (
                      <div className="p-4 space-y-3 bg-panel-light dark:bg-panel-dark">
                        {yearFilings.map((filing) => {
                          const styles = getFilingTypeStyles(filing.filing_type)
                          return (
                            <div
                              key={filing.id}
                              className={`border-l-4 ${styles.borderColor} border-r border-t border-b border-border-light dark:border-border-dark rounded-lg p-4 ${styles.bgColor} ${styles.hoverBg} transition-colors`}
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
                                          <span className="inline-flex items-center gap-1 rounded-full bg-brand-strong dark:bg-brand-dark px-2 py-0.5 text-xs font-semibold text-white dark:text-background-dark">
                                            <Sparkles className="h-3 w-3" />
                                            Recommended
                                          </span>
                                        )}
                                        <span className="text-sm text-text-tertiary-light dark:text-text-secondary-dark">
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
                                      className="inline-flex items-center gap-2 px-4 py-2 border border-border-light dark:border-border-dark text-text-secondary-light dark:text-text-secondary-dark text-sm font-medium rounded-md hover:bg-background-light dark:hover:bg-white/5 hover:border-text-tertiary-light dark:hover:border-text-tertiary-dark transition-colors"
                                      title="Open original filing on SEC EDGAR"
                                    >
                                      <ExternalLink className="h-4 w-4" />
                                      <span>View on SEC EDGAR</span>
                                    </a>
                                  )}
                                  <Link
                                    href={`/filing/${filing.id}`}
                                    className="inline-flex items-center px-4 py-2 bg-brand-strong hover:bg-brand-light text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark text-sm font-medium rounded-md transition-colors"
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
              <FileText className="h-12 w-12 text-text-tertiary-light dark:text-text-secondary-dark mx-auto mb-4" />
              <p className="text-text-tertiary-light dark:text-text-secondary-dark">No filings found for this company.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

