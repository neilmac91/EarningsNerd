'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCompany, Company } from '@/features/companies/api/companies-api'
import { getCompanyFilings, Filing } from '@/features/filings/api/filings-api'
import { getSummary } from '@/features/summaries/api/summaries-api'
import { addToWatchlist, removeFromWatchlist, getWatchlist, WatchlistItem } from '@/features/watchlist/api/watchlist-api'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { CircleNotchIcon, FileTextIcon, StarIcon } from '@/lib/icons'
import { Button, buttonVariants, GuidanceCard } from '@/components/ui'
import { toast } from 'sonner'
import Link from 'next/link'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText, directionOf } from '@/lib/financialTone'
import analytics from '@/lib/analytics'
import { getEntryPoint } from '@/lib/entryPoint'
import { ENABLE_RECOMMENDED_FILING, ENABLE_FINANCIAL_CHARTS, ENABLE_INSIDER_ACTIVITY } from '@/lib/featureFlags'
import PeerComparisonPanel from '@/features/peers/components/PeerComparisonPanel'
import CompanyLogo from '@/components/CompanyLogo'
import InsiderActivityPanel from '@/features/insiders/components/InsiderActivityPanel'
import { queryKeys } from '@/lib/queryKeys'
import { selectRecommendedFiling } from '@/features/filings/lib/recommendedFiling'
import { groupByFiscalYear } from '@/features/filings/lib/fiscalYear'
// The filings list: one surface, hairline rows, one link per filing (design review 2026-10-08).
// It owns the form/year filters and renders dates through formatLocalDate (filing dates are
// UTC-midnight instants; local-TZ rendering would shift the day west of UTC and mismatch hydration).
import { FilingIndex } from '@/features/filings/components/FilingIndex'
import { useRetainedFailure } from '@/hooks/useRetainedFailure'

// How many filings to request once the visitor asks for the full backfilled history (vs the
// backend's default recent cap). P1-6: deep 10-K/10-Q history since 2001 is well under this.
const FULL_HISTORY_LIMIT = 300

// Foreign private issuer forms — a company that files any of these is an FPI, which we use to show
// the honest "insider reporting not required for FPIs" state instead of an empty insider panel.
const FPI_FILING_TYPES = ['20-F', '40-F', '6-K']

interface CompanyPageClientProps {
  /** Server-fetched seeds (SEO/ISR): make the first server render carry the real page content
   * so crawlers get HTML, not a spinner. Absent (backend unreachable during the server render,
   * or a test mounting the bare client) the page behaves exactly as before: client-side fetch. */
  initialCompany?: Company
  initialFilings?: Filing[]
}

export default function CompanyPageClient({ initialCompany, initialFilings }: CompanyPageClientProps = {}) {
  const params = useParams()
  const ticker = (params?.ticker as string | undefined) ?? ''
  const normalizedTicker = ticker.toUpperCase()

  // All hooks must be called before any conditional returns
  const currentYear = new Date().getFullYear().toString()
  // Seeded renders expand the top ~3 filing years immediately (same rule as the A4 effect below)
  // so the server-rendered HTML contains the filing links crawlers should discover.
  const [expandedYears, setExpandedYears] = useState<Set<string>>(() => {
    if (initialFilings?.length) {
      const years = Object.keys(groupByFiscalYear(initialFilings)).sort((a, b) => parseInt(b) - parseInt(a))
      return new Set(years.slice(0, 3))
    }
    return new Set([currentYear])
  })
  const [showFullHistory, setShowFullHistory] = useState(false)
  const hasTrackedCompanyView = useRef(false)
  const filingsHeadingRef = useRef<HTMLHeadingElement>(null)

  // initialDataUpdatedAt: 0 marks the ISR-cached seed as already stale, so the client refetches
  // on mount and live fields (stock quote) catch up — the seed only guarantees the first paint.
  const { data: company, isLoading: companyLoading, error: companyError } = useQuery<Company>({
    queryKey: queryKeys.company(normalizedTicker),
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
    enabled: !!normalizedTicker,
    initialData: initialCompany,
    initialDataUpdatedAt: 0,
  })

  // Default view serves the backend's recent cap; "Show full history" refetches with a high limit
  // so the deep-backfilled 10-K/10-Q history (P1-6) surfaces. The limit is part of the query key so
  // the two views cache independently.
  const historyLimit = showFullHistory ? FULL_HISTORY_LIMIT : undefined
  const filingsKey = queryKeys.companyFilings(normalizedTicker, historyLimit)
  const filingsQuery = useQuery<Filing[]>({
    queryKey: filingsKey,
    queryFn: () => getCompanyFilings(normalizedTicker, undefined, historyLimit),
    enabled: !!company && !!normalizedTicker,
    retry: 1,
    // The seed matches only the default (no-limit) query key — never the full-history one.
    initialData: historyLimit === undefined ? initialFilings : undefined,
    initialDataUpdatedAt: 0,
  })
  const { data: filings, isFetching: filingsRefetching } = filingsQuery
  // A failure keeps the error Notice, and a focused Retry in it, through any refetch until data
  // replaces it: an errored list has no data, so its refetch goes back to pending, and the skeleton
  // would otherwise replace the Notice (RetryButton + useRetainedFailure, DESIGN_SYSTEM §4).
  const filingsFailure = useRetainedFailure(filingsQuery, filingsKey)
  const filingsLoading = filingsQuery.isLoading && !filingsFailure.failed

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

  // Derived from the FULL list (the filters live in FilingIndex), declared before the early returns
  // below so hook order stays stable across renders.
  const { sortedYears, recommendedFiling, isFpi } = useMemo(() => {
    // Report years present, newest first (calendar year of report end, filing-date fallback).
    const years = Object.keys(groupByFiscalYear(filings ?? [])).sort((a, b) => parseInt(b) - parseInt(a))
    return {
      sortedYears: years,
      // Recommended ("Latest") filing: the company's single MOST RECENT non-superseded filing of any
      // type, from the FULL list so it stays stable as the user filters.
      recommendedFiling: selectRecommendedFiling(filings),
      isFpi: (filings ?? []).some((f) => FPI_FILING_TYPES.includes(f.filing_type)),
    }
  }, [filings])

  // A4: default the filing list to the most recent ~3 years that actually have filings (older years
  // stay collapsed behind their headers) — instead of only the current calendar year, which is empty
  // for a company whose latest filing is last year. Runs once on load; the user controls it after.
  // A server-seeded mount already applied this rule in the expandedYears initializer, so it starts
  // marked-done for this ticker.
  const autoExpandedForRef = useRef<string | null>(initialFilings?.length ? normalizedTicker : null)
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
            title={formatCompanyName(company.name) || normalizedTicker}
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
  // Display casing only: analytics/cache payloads above keep the raw EDGAR name as the data value.
  const companyDisplayName = formatCompanyName(companyData.name)

  const toggleYear = (year: string) => {
    const newExpanded = new Set(expandedYears)
    if (newExpanded.has(year)) {
      newExpanded.delete(year)
    } else {
      newExpanded.add(year)
    }
    setExpandedYears(newExpanded)
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
                  <CompanyLogo decorative ticker={companyData.ticker} name={companyDisplayName} size={40} priority />
                  <h1 className="text-2xl font-semibold text-text-primary-light dark:text-text-primary-dark">{companyDisplayName}</h1>
                  {currentUser && (
                    // aria-disabled + aria-busy + an early return while the toggle is in flight, not
                    // native `disabled`: Chromium blurs a focused button that turns disabled, so a
                    // keyboard toggle would drop the user to <body>.
                    <button
                      onClick={() => {
                        if (watchlistMutation.isPending) return
                        watchlistMutation.mutate({ ticker: normalizedTicker, shouldAdd: !isInWatchlist })
                      }}
                      aria-disabled={watchlistMutation.isPending || undefined}
                      aria-busy={watchlistMutation.isPending || undefined}
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
          <InsiderActivityPanel ticker={normalizedTicker} isFpi={filingsLoading ? undefined : isFpi} />
        )}

        {/* SEC filings. Keyed on the ticker so its filters reset on a soft navigation to another company. */}
        <FilingIndex
          key={normalizedTicker}
          companyName={companyDisplayName}
          filings={filings}
          status={filingsLoading ? 'loading' : filingsFailure.failed ? 'error' : 'ready'}
          failure={filingsFailure}
          headingRef={filingsHeadingRef}
          latest={ENABLE_RECOMMENDED_FILING ? recommendedFiling : null}
          expandedYears={expandedYears}
          onToggleYear={toggleYear}
          cik={company?.cik}
          footerAction={
            showFullHistory ? undefined : (
              // P1-6: the default view serves the recent cap; load the full backfilled 10-K/10-Q
              // history (since 2001) on demand. `loading`, not `disabled`: a background refetch
              // (reconnect, invalidation) can start while this button holds focus, and a focused
              // button that turns disabled is blurred to <body> in Chromium. Activating it unmounts
              // it (the unseeded full-history key swaps the list for the skeleton), so focus moves
              // to the section heading first, not to <body>.
              <Button
                variant="secondary"
                className="w-full sm:w-auto"
                onClick={(e) => {
                  // Only a keyboard (or AT) user holding this button loses focus when it unmounts.
                  if (document.activeElement === e.currentTarget) filingsHeadingRef.current?.focus({ preventScroll: true })
                  setShowFullHistory(true)
                }}
                loading={filingsRefetching}
                loadingText="Loading full history…"
              >
                Show full history
              </Button>
            )
          }
        />
      </main>
    </div>
  )
}
