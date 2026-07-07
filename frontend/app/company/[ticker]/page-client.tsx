'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCompany, Company } from '@/features/companies/api/companies-api'
import { getCompanyFilings, Filing } from '@/features/filings/api/filings-api'
import { getSummary } from '@/features/summaries/api/summaries-api'
import { addToWatchlist, removeFromWatchlist, getWatchlist, WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { ArrowRightIcon, ArrowSquareOutIcon, CaretDownIcon, CircleNotchIcon, FileTextIcon, FunnelIcon, SparkleIcon, StarIcon, WarningCircleIcon } from '@/lib/icons'
import { Badge, Button, buttonVariants, Card, GuidanceCard, Skeleton } from '@/components/ui'
import { toast } from 'sonner'
import Link from 'next/link'
import { format } from 'date-fns'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText, directionOf } from '@/lib/financialTone'
import analytics from '@/lib/analytics'
import { getEntryPoint } from '@/lib/entryPoint'
import { ENABLE_RECOMMENDED_FILING, ENABLE_FINANCIAL_CHARTS, ENABLE_INSIDER_ACTIVITY } from '@/lib/featureFlags'
import PeerComparisonPanel from '@/features/peers/components/PeerComparisonPanel'
import CompanyLogo from '@/components/CompanyLogo'
import InsiderActivityPanel from '@/features/insiders/components/InsiderActivityPanel'
import { queryKeys } from '@/lib/queryKeys'
import { recommendedFilingNoun, selectRecommendedFiling } from '@/features/filings/lib/recommendedFiling'
import FilingsHistoryNote from '@/features/filings/components/FilingsHistoryNote'

// Display order for the filing-type filter chips; unknown types sort to the end alphabetically.
const FILING_TYPE_ORDER = ['10-K', '10-Q', '20-F', '6-K', '40-F']
// Foreign private issuer forms — a company that files any of these is an FPI, which we use to show
// the honest "insider reporting not required for FPIs" state instead of an empty insider panel.
const FPI_FILING_TYPES = ['20-F', '40-F', '6-K']

export default function CompanyPageClient() {
  const params = useParams()
  const ticker = (params?.ticker as string | undefined) ?? ''
  const normalizedTicker = ticker.toUpperCase()

  // All hooks must be called before any conditional returns
  const currentYear = new Date().getFullYear().toString()
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set([currentYear]))
  const [filterType, setFilterType] = useState<string | null>(null)
  const hasTrackedCompanyView = useRef(false)

  const { data: company, isLoading: companyLoading, error: companyError } = useQuery<Company>({
    queryKey: queryKeys.company(normalizedTicker),
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
    enabled: !!normalizedTicker,
  })

  const { data: filings, isLoading: filingsLoading, isError: filingsError, error: filingsErrorData, refetch: refetchFilings, isFetching: filingsRefetching } = useQuery<Filing[]>({
    queryKey: queryKeys.companyFilings(normalizedTicker),
    queryFn: () => getCompanyFilings(normalizedTicker),
    enabled: !!company && !!normalizedTicker,
    retry: 1,
  })

  const { data: currentUser } = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })

  const { data: watchlist } = useQuery({
    queryKey: queryKeys.watchlist(),
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
      await queryClient.cancelQueries({ queryKey: queryKeys.watchlist() })
      const previous = queryClient.getQueryData<WatchlistItem[]>(queryKeys.watchlist())
      queryClient.setQueryData<WatchlistItem[]>(queryKeys.watchlist(), (old) => {
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
        queryClient.setQueryData(queryKeys.watchlist(), context.previous)
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
    // Always refetch so the temporary optimistic row is replaced by the canonical server row. The
    // watchlist-derived insights, dashboard feed, and calendar go stale on a toggle too, so refresh
    // them here (invalidating an unmounted query is harmless).
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlist() })
      queryClient.invalidateQueries({ queryKey: queryKeys.watchlistInsights() })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardFeed() })
      queryClient.invalidateQueries({ queryKey: queryKeys.dashboardCalendar() })
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
  const { groupedFilings, sortedYears, recommendedFiling, availableFilingTypes, oldestFilingDate } = useMemo(() => {
    const filtered = filterType
      ? filings?.filter((f) => f.filing_type === filterType)
      : filings

    // Distinct filing types present, in canonical display order — drives the filter chips so the
    // UI adapts to whatever the company actually files (10-K/10-Q for domestic, 20-F/6-K for FPIs)
    // instead of hardcoding domestic forms.
    const availableFilingTypes = Array.from(
      new Set((filings ?? []).map((f) => f.filing_type)),
    ).sort((a, b) => {
      const ia = FILING_TYPE_ORDER.indexOf(a)
      const ib = FILING_TYPE_ORDER.indexOf(b)
      return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib) || a.localeCompare(b)
    })

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

    // Recommended filing: the company's single MOST RECENT filing of any type. Computed from the
    // FULL list (not the active type filter) so the recommendation is stable as the user filters.
    const recommendedFiling = selectRecommendedFiling(filings)

    // P0-5: earliest filing_date in the FULL list (not the active filter) — drives the
    // "Showing filings since …" honesty note under the list.
    const oldestFilingDate = (filings ?? []).reduce<string | null>(
      (oldest, f) =>
        !oldest || new Date(f.filing_date) < new Date(oldest) ? f.filing_date : oldest,
      null,
    )

    return { groupedFilings: grouped, sortedYears: years, recommendedFiling, availableFilingTypes, oldestFilingDate }
  }, [filings, filterType])

  // A4: default the filing list to the most recent ~3 years that actually have filings (older years
  // stay collapsed behind their headers) — instead of only the current calendar year, which is empty
  // for a company whose latest filing is last year. Runs once on load; the user controls it after.
  const autoExpandedForRef = useRef<string | null>(null)
  useEffect(() => {
    // Keyed on the ticker (not a one-shot bool) so it re-expands when this page is reused across a
    // soft navigation to a different company. `sortedYears` is [] while the new ticker's filings
    // load, so this no-ops until the correct data arrives.
    if (autoExpandedForRef.current === normalizedTicker || sortedYears.length === 0) return
    autoExpandedForRef.current = normalizedTicker
    setExpandedYears(new Set(sortedYears.slice(0, 3)))
  }, [sortedYears, normalizedTicker])

  // A4: prefetch the recommended filing's summary (the company's most recent filing) the moment the
  // company opens, so the most-likely next click renders the cached analysis instantly. Read-only
  // GET — never triggers generation. Dovetails with the A1 precompute that warms summaries server-side.
  const prefetchedFilingIdRef = useRef<number | null>(null)
  useEffect(() => {
    // Keyed on the filing id so a soft-nav to a different company prefetches that company's most
    // recent filing, and we never re-prefetch the same one.
    if (!recommendedFiling?.id || prefetchedFilingIdRef.current === recommendedFiling.id) return
    prefetchedFilingIdRef.current = recommendedFiling.id
    queryClient.prefetchQuery({
      queryKey: queryKeys.summary(recommendedFiling.id),
      queryFn: () => getSummary(recommendedFiling.id),
      staleTime: 60_000,
    })
  }, [recommendedFiling, queryClient])

  // Handle case where ticker might not be available
  if (!ticker) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <GuidanceCard
            variant="error"
            title="Invalid ticker"
            action={
              <Link href="/" className={buttonVariants({ variant: 'secondary' })}>
                Go back home
              </Link>
            }
          />
        </div>
      </div>
    )
  }

  if (companyLoading) {
    return (
      <div role="status" aria-label="Loading company" className="min-h-screen flex items-center justify-center">
        <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        <span className="sr-only">Loading company…</span>
      </div>
    )
  }

  if (!company) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4">
        <div className="w-full max-w-md">
          <GuidanceCard
            variant="error"
            title="Company not found"
            description={
              companyError
                ? `Error: ${companyError instanceof Error ? companyError.message : 'Failed to load company'}`
                : `Could not find company with ticker "${normalizedTicker}"`
            }
            action={
              <Link href="/" className={buttonVariants({ variant: 'secondary' })}>
                Go back home
              </Link>
            }
          />
        </div>
      </div>
    )
  }

  // Known unsupported foreign issuer (an unsponsored ADR that files no financial reports with the
  // SEC). The backend returns a 200 with coverage_status set so we can show an honest "coverage
  // unavailable" state — distinct from a bare "Company not found" — instead of a broken page.
  if (company.coverage_status === 'unsupported_foreign') {
    return (
      <div className="min-h-screen bg-background-light dark:bg-background-dark">
        <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center px-6">
          {/* Honest coverage-unavailable state — an empty, not an error. */}
          <GuidanceCard
            variant="empty"
            icon={<FileTextIcon className="h-5 w-5" />}
            title={company.name || normalizedTicker}
            description={
              company.coverage_reason ||
              'This issuer does not file financial reports with the SEC, so EarningsNerd has no filings to analyze.'
            }
            action={
              <Link href="/" className={buttonVariants({ variant: 'primary' })}>
                Back to home
              </Link>
            }
          />
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

  // Get styling for filing type. Annual reports (10-K + the foreign 20-F/40-F) share the brand
  // accent; interim reports (10-Q + the foreign 6-K) share the info accent — so an FPI page reads
  // consistently with a domestic one (annual = brand, interim = info).
  const getFilingTypeStyles = (filingType: string) => {
    switch (filingType) {
      case '10-K':
      case '20-F':
      case '40-F':
        return {
          borderColor: 'border-l-brand-strong dark:border-l-brand-strong-dark',
          bgColor: 'bg-brand-weak dark:bg-white/5',
          hoverBg: 'hover:bg-brand-weak dark:hover:bg-white/10',
          iconColor: 'text-brand-strong dark:text-brand-strong-dark',
          badgeVariant: 'brand',
        } as const
      case '10-Q':
      case '6-K':
        return {
          borderColor: 'border-l-info-light dark:border-l-info-dark',
          bgColor: 'bg-info-light/10 dark:bg-info-dark/10',
          hoverBg: 'hover:bg-info-light/15 dark:hover:bg-info-dark/15',
          iconColor: 'text-info-light dark:text-info-dark',
          badgeVariant: 'info',
        } as const
      default:
        return {
          borderColor: 'border-l-border-light dark:border-l-border-dark',
          bgColor: 'bg-background-light dark:bg-background-dark',
          hoverBg: 'hover:bg-background-light dark:hover:bg-background-dark',
          iconColor: 'text-text-tertiary-light dark:text-text-secondary-dark',
          badgeVariant: 'neutral',
        } as const
    }
  }

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      {/* Header */}
      <header className="bg-panel-light dark:bg-panel-dark border-b border-border-light dark:border-border-dark shadow-e1 dark:shadow-none">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:space-x-4">
              <Link href="/" className="text-text-secondary-light dark:text-text-secondary-dark hover:text-text-primary-light dark:hover:text-text-primary-dark font-medium transition-colors">
                ← Back
              </Link>
              <div className="border-l-0 sm:border-l border-border-light dark:border-border-dark sm:pl-4 flex-1">
                <div className="flex items-center space-x-3">
                  <CompanyLogo ticker={companyData.ticker} name={companyData.name} size={40} priority />
                  <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">{companyData.name}</h1>
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
                        <StarIcon className="h-5 w-5 fill-current" />
                      ) : (
                        <StarIcon className="h-5 w-5" />
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
        {ENABLE_FINANCIAL_CHARTS && <PeerComparisonPanel ticker={normalizedTicker} />}
        {/* Insider (Form 4) activity — self-fetches; live SEC read, off by default. FPIs are
            exempt from Form 4 reporting, so the panel shows an honest note (no live read). */}
        {ENABLE_INSIDER_ACTIVITY && (
          <InsiderActivityPanel
            ticker={normalizedTicker}
            isFpi={filingsLoading ? undefined : availableFilingTypes.some((t) => FPI_FILING_TYPES.includes(t))}
          />
        )}

        {/* Filings Section */}
        <Card as="section" className="p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between mb-6">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">SEC Filings</h2>
            {filings && filings.length > 0 && availableFilingTypes.length > 1 && (
              <div className="flex flex-wrap items-center gap-2">
                <FunnelIcon className="h-4 w-4 text-text-tertiary-light dark:text-text-secondary-dark" />
                <div className="flex flex-wrap items-center gap-2">
                  <button
                    onClick={() => setFilterType(null)}
                    className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-lg transition-colors ${
                      filterType === null
                        ? 'bg-text-primary-light dark:bg-text-primary-dark text-panel-light dark:text-background-dark'
                        : 'bg-background-light dark:bg-white/5 text-text-secondary-light dark:text-text-secondary-dark hover:bg-brand-weak dark:hover:bg-white/10'
                    }`}
                  >
                    All Types
                  </button>
                  {availableFilingTypes.map((ft) => (
                    <button
                      key={ft}
                      onClick={() => setFilterType(ft)}
                      className={`px-3 py-1.5 text-xs sm:px-4 sm:py-2 sm:text-sm font-medium rounded-lg transition-colors ${
                        filterType === ft
                          ? 'bg-brand hover:bg-brand-strong active:bg-brand-emphasis text-white dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark'
                          : 'bg-brand-weak dark:bg-white/5 text-brand-strong dark:text-brand-strong-dark hover:bg-brand-weak/70 dark:hover:bg-white/10'
                      }`}
                    >
                      {ft}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>

          {ENABLE_RECOMMENDED_FILING && !filingsLoading && !filingsError && recommendedFiling && (
            // Highlighted inset INSIDE the section card: a flat brand-weak TINT box
            // (like the billing trial box) — the old gradient is banned (DS §7).
            <div className="mb-6 rounded-xl border border-brand-border dark:border-brand-border-dark bg-brand-weak dark:bg-white/5 p-4 sm:p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-start gap-3">
                  <SparkleIcon className="mt-0.5 h-5 w-5 flex-shrink-0 text-brand-strong dark:text-brand-strong-dark" />
                  <div>
                    <div className="flex items-center gap-2">
                      {/* Solid emphasis chip (primary-button colorway) — the tint Badge would
                          vanish against this brand-weak banner. */}
                      <Badge variant="solid">Recommended</Badge>
                      <span className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                        {recommendedFiling.filing_type} · {format(new Date(recommendedFiling.filing_date), 'MMM d, yyyy')}
                      </span>
                    </div>
                    <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
                      Not sure where to start? This is {companyData.name}&apos;s most recent{' '}
                      {recommendedFilingNoun(recommendedFiling)}. Start with its AI summary.
                    </p>
                  </div>
                </div>
                <Link href={`/filing/${recommendedFiling.id}`} className={buttonVariants({ variant: 'primary' })}>
                  Summarize this filing
                  <ArrowRightIcon className="h-4 w-4" />
                </Link>
              </div>
            </div>
          )}

          {filingsLoading ? (
            <div role="status" aria-label="Loading filings" className="space-y-4">
              <Skeleton className="h-12 rounded-xl" />
              <Skeleton className="h-12 rounded-xl" />
              <Skeleton className="h-12 rounded-xl" />
              <span className="sr-only">Loading filings…</span>
            </div>
          ) : filingsError ? (
            // Inline error (not GuidanceCard) — this state lives INSIDE the section card.
            <div role="alert" className="space-y-2 py-4">
              <p className="flex items-center gap-2 text-sm font-medium text-error-light dark:text-error-dark">
                <WarningCircleIcon className="h-4 w-4 flex-shrink-0" />
                Unable to load filings right now.
              </p>
              <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                {filingsErrorData instanceof Error ? filingsErrorData.message : 'Please try again shortly.'}
              </p>
              <Button variant="secondary" size="sm" onClick={() => refetchFilings()} loading={filingsRefetching} loadingText="Retrying…">
                Retry
              </Button>
            </div>
          ) : sortedYears.length > 0 ? (
            <div className="space-y-4">
              {sortedYears.map((year) => {
                const yearFilings = groupedFilings[year]
                const isExpanded = expandedYears.has(year)
                const filingCount = yearFilings?.length || 0

                return (
                  <div key={year} className="border border-border-light dark:border-border-dark rounded-xl overflow-hidden">
                    {/* Year Header */}
                    <button
                      onClick={() => toggleYear(year)}
                      className="w-full flex items-center justify-between px-4 py-3 bg-background-light dark:bg-white/5 hover:bg-brand-weak dark:hover:bg-white/10 transition-colors text-left"
                    >
                      <div className="flex items-center space-x-3">
                        {isExpanded ? (
                          <CaretDownIcon className="h-5 w-5 text-text-tertiary-light dark:text-text-secondary-dark" />
                        ) : (
                          <CaretDownIcon className="h-5 w-5 text-text-tertiary-light dark:text-text-secondary-dark -rotate-90" />
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
                              className={`border-l-4 ${styles.borderColor} border-r border-t border-b border-border-light dark:border-border-dark rounded-xl p-4 ${styles.bgColor} ${styles.hoverBg} transition-colors`}
                            >
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center space-x-3">
                                    <FileTextIcon className={`h-5 w-5 ${styles.iconColor}`} />
                                    <div>
                                      <div className="flex items-center space-x-2">
                                        <Badge variant={styles.badgeVariant}>{filing.filing_type}</Badge>
                                        {ENABLE_RECOMMENDED_FILING && recommendedFiling?.id === filing.id && (
                                          /* Solid emphasis chip — sits on the row's brand-weak tint,
                                             where the tint Badge would vanish (see banner note). */
                                          <Badge variant="solid" icon={<SparkleIcon className="h-3 w-3" />}>
                                            Recommended
                                          </Badge>
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
                                      className={buttonVariants({ variant: 'secondary' })}
                                      title="Open original filing on SEC EDGAR"
                                    >
                                      <ArrowSquareOutIcon className="h-4 w-4" />
                                      <span>View on SEC EDGAR</span>
                                    </a>
                                  )}
                                  <Link href={`/filing/${filing.id}`} className={buttonVariants({ variant: 'primary' })}>
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
              <FilingsHistoryNote oldestFilingDate={oldestFilingDate} cik={company?.cik} />
            </div>
          ) : (
            // Inline empty — inside the section card, so no nested GuidanceCard panel.
            <div role="status" className="text-center py-12">
              <FileTextIcon className="h-12 w-12 text-text-tertiary-light dark:text-text-secondary-dark mx-auto mb-4" />
              <p className="text-text-tertiary-light dark:text-text-secondary-dark">No filings found for this company.</p>
            </div>
          )}
        </Card>
      </main>
    </div>
  )
}

