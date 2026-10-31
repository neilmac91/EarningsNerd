'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import { queryKeys } from '@/lib/queryKeys'
import { Fragment, useState, useEffect, useRef, useMemo } from 'react'
import { MagnifyingGlassIcon } from '@/lib/icons'
import { useQuery } from '@tanstack/react-query'
import { searchCompanies, Company, type LatestFilingRef } from '@/features/companies/api/companies-api'
import { Sep, periodPhrase } from '@/features/filings/components/FilingIdentity'
import { tickerShaped } from '@/features/companies/lib/tickerShape'
import CompanyLogo from '@/components/CompanyLogo'
import { FieldSpinner, Notice, inputClasses } from '@/components/ui'
import { ApiError } from '@/lib/api/client'
import { useRouter } from 'next/navigation'
import { fmtCurrency, fmtPercent, formatLocalDate } from '@/lib/format'
import { directionText, directionOf } from '@/lib/financialTone'
import analytics from '@/lib/analytics'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'

const isTypingTarget = (el: EventTarget | null): boolean => {
  if (!(el instanceof HTMLElement)) return false
  return (
    el.tagName === 'INPUT' ||
    el.tagName === 'TEXTAREA' ||
    el.tagName === 'SELECT' ||
    el.isContentEditable
  )
}

export default function CompanySearch({
  autoFocusDesktop = false,
  shortcuts = autoFocusDesktop,
  ariaLabel = 'Search for a company',
  onSelect,
  placeholder = 'Search company or ticker',
}: {
  autoFocusDesktop?: boolean
  /** "/" and Cmd/Ctrl+K focus the field from anywhere on the page. Defaults to autoFocusDesktop
   *  so existing call sites keep both; the landing hero wants the shortcut without the autofocus. */
  shortcuts?: boolean
  /** Accessible name. Pass null when a visible <label htmlFor="company-search"> names the field. */
  ariaLabel?: string | null
  /** Field placeholder. The default is the landing hero's copy: no example tickers, no ellipsis. */
  placeholder?: string
  /**
   * Override the pick behaviour (default navigates to /company/{ticker}). Used by surfaces that
   * consume the selection in place — e.g. the Multi-Period Analysis picker. An Enter pressed before
   * the results arrive picks through it too, as in the default mode: the result whose ticker is the
   * typed text once the search lands, or a ticker-shaped text as typed when the search failed.
   */
  onSelect?: (ticker: string) => void
}) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [highlightIndex, setHighlightIndex] = useState(-1)
  const router = useRouter()
  const lastTrackedQuery = useRef<string>('')
  const inputRef = useRef<HTMLInputElement>(null)

  // Desktop-only autofocus: search is the hero's primary action. Skipped on
  // small screens, where autofocus pops the keyboard and jumps the viewport.
  useEffect(() => {
    if (autoFocusDesktop && window.matchMedia('(min-width: 1024px)').matches) {
      inputRef.current?.focus({ preventScroll: true })
    }
  }, [autoFocusDesktop])

  // "/" or Cmd/Ctrl+K focuses search from anywhere on the page.
  useEffect(() => {
    if (!shortcuts) return
    const onKeyDown = (e: KeyboardEvent) => {
      const slash = e.key === '/' && !e.metaKey && !e.ctrlKey && !e.altKey
      const cmdK = e.key.toLowerCase() === 'k' && (e.metaKey || e.ctrlKey)
      if ((slash && !isTypingTarget(e.target)) || cmdK) {
        e.preventDefault()
        inputRef.current?.focus()
      }
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [shortcuts])

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const companiesQuery = useQuery({
    queryKey: queryKeys.companies(debouncedQuery),
    queryFn: () => searchCompanies(debouncedQuery),
    enabled: debouncedQuery.length > 0,
    // Retry logic: retry more for transient errors (503, 429, 5xx)
    retry: (failureCount, error) => {
      if (error instanceof ApiError && error.isRetryable) {
        return failureCount < 3 // Retry up to 3 times for transient errors
      }
      return failureCount < 1 // Only retry once for other errors
    },
    // Exponential backoff: 1s, 2s, 4s
    retryDelay: (attemptIndex) => Math.min(1000 * Math.pow(2, attemptIndex), 4000),
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  })
  const { data: companies, isLoading, isLoadingError } = companiesQuery
  // The alert keeps its failure through any refetch until data replaces it. An errored search has no
  // data, so its refetch goes back to pending, and the alert (and a focused "Try again" in it) would
  // vanish. A new term is another query, so typing one drops the old failure.
  const failure = useRetainedFailure(companiesQuery, queryKeys.companies(debouncedQuery))
  const isError = failure.failed
  const error = failure.error

  // Navigate to a result and record the search→click so search→company conversion is causal.
  const goToResult = (ticker: string, position: number) => {
    analytics.companySearchResultClicked(debouncedQuery || query, ticker, position)
    if (onSelect) {
      setQuery('')
      onSelect(ticker)
      return
    }
    router.push(`/company/${ticker}`)
  }

  const handleCompanyClick = (company: Company, index: number) => {
    goToResult(company.ticker, index)
  }

  // Keyboard navigation operates over the network search results.
  const navigableTickers = useMemo(
    () => companies?.map((c) => c.ticker) ?? [],
    [companies],
  )

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- reset keyboard selection when the query or network results change (external sync), not derivable from render
    setHighlightIndex(-1)
  }, [query, companies])

  // An Enter with no results to pick from waits here for the search of the text it was pressed on. It
  // acts once, when that search answers, and only while the field still holds that text: typing or
  // Escape drops it, and an unmounted search acts on nothing. It opens the result whose ticker is the
  // text, never the first partial hit, so a name ("nike") stays on the list its search brings, for the
  // user to pick from. After a failed search it still opens a ticker-shaped text as typed.
  const pendingEnter = useRef<string | null>(null)
  const settleEnter = () => {
    const term = pendingEnter.current
    if (term === null) return
    if (term !== query) {
      pendingEnter.current = null
      return
    }
    // Called from the Enter, this render's search may still be the previous text's: the flush
    // lands in the next render.
    if (term !== debouncedQuery) return
    if (companies) {
      pendingEnter.current = null
      const exact = companies.findIndex((c) => c.ticker.toUpperCase() === term.trim().toUpperCase())
      if (exact !== -1) goToResult(companies[exact].ticker, exact)
    } else if (isLoadingError) {
      // Failed for good: the retries above are spent (a "Try again" still running is not final).
      pendingEnter.current = null
      const typed = tickerShaped(term)
      if (!typed) return
      if (onSelect) {
        setQuery('')
        onSelect(typed)
      } else {
        router.push(`/company/${typed}`)
      }
    }
  }

  const handleInputKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Escape') {
      setQuery('')
      inputRef.current?.blur()
      return
    }
    if (e.key === 'ArrowDown') {
      if (navigableTickers.length === 0) return
      e.preventDefault()
      setHighlightIndex((i) => (i + 1) % navigableTickers.length)
    } else if (e.key === 'ArrowUp') {
      if (navigableTickers.length === 0) return
      e.preventDefault()
      setHighlightIndex((i) => (i <= 0 ? navigableTickers.length - 1 : i - 1))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      const position = highlightIndex === -1 ? 0 : highlightIndex
      const ticker = navigableTickers[position]
      if (ticker) {
        goToResult(ticker, position)
      } else if (query.trim()) {
        // No results to pick from yet: search this text now, not after the debounce, and act when
        // that search answers (settleEnter), at once if it already has. Opening a ticker-shaped text
        // straight away sent names such as "nike" to /company/NIKE, which the server binds by exact
        // ticker only: a 404.
        pendingEnter.current = query
        setDebouncedQuery(query)
        settleEnter()
      }
    }
  }

  useEffect(() => {
    if (
      debouncedQuery.length > 0 &&
      !isLoading &&
      !isError &&
      companies &&
      debouncedQuery !== lastTrackedQuery.current
    ) {
      analytics.companySearched(debouncedQuery, companies.length)
      lastTrackedQuery.current = debouncedQuery
    }
  }, [debouncedQuery, isLoading, isError, companies])

  // No dependency list: it runs after every render, and after the search is counted above, so the pick a
  // pending Enter makes is recorded after the search it came from.
  useEffect(settleEnter)

  return (
    <div className="relative">
      {/* Glow keys on :focus-within, so it lives on the wrapper (rounded-lg matches
          the field radius) — keeps its box-shadow off the input's focus ring. */}
      <div className="hero-search-glow relative rounded-lg">
        <MagnifyingGlassIcon
          aria-hidden="true"
          className="pointer-events-none absolute left-3.5 top-1/2 h-5 w-5 -translate-y-1/2 text-text-tertiary-light dark:text-text-tertiary-dark"
        />
        <input
          ref={inputRef}
          id="company-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder={placeholder}
          role="combobox"
          aria-expanded={navigableTickers.length > 0}
          aria-controls="company-search-results"
          aria-activedescendant={
            highlightIndex >= 0 ? `company-search-option-${highlightIndex}` : undefined
          }
          aria-label={ariaLabel ?? undefined}
          aria-describedby={isError ? "company-search-error" : undefined}
          aria-autocomplete="list"
          aria-busy={isLoading || undefined}
          className={inputClasses({ leadingIcon: true, trailingIcon: true })}
        />
        {/* The trailing inset is always reserved, never only while the spinner shows: growing the padding
            under a long query leaves its end and the caret behind the spinner (Chromium does not re-scroll
            the caret), and shrinking it jumps the line. The "/" hint sits at right-3, inside the same inset. */}
        {isLoading && <FieldSpinner />}
        {!isLoading && !query && (
          <kbd
            className="absolute right-3 top-1/2 hidden -translate-y-1/2 rounded border border-border-light dark:border-white/15 bg-brand-weak dark:bg-white/5 px-2 py-0.5 font-mono text-xs text-text-tertiary-light dark:text-text-tertiary-dark sm:block"
            aria-hidden="true"
          >
            /
          </kbd>
        )}
      </div>

      {/* Error Message: an error Notice (E196 (4)) on the dropdown's own opaque panel, since the dropdown floats over the
          page. Its description is keyed to the failure count, so a retry that fails again with the same message
          re-inserts it and the alert announces it again. The backend's own words can hold a long token, so it breaks
          inside the alert (Notice breaks its description). The Retry takes the Notice's action row under the message:
          it keeps the room of "Trying again…" at rest, and beside the message that room left the message too little
          width at 200% text on a phone and pushed the Retry past the screen (e2e reflow-200.spec.ts holds this). When
          the alert goes while "Try again" holds focus (the search lands), focus moves to the field, except after a
          tap, which would raise the touch keyboard. */}
      {isError && debouncedQuery.length > 0 && (
        <div
          id="company-search-error"
          className="absolute z-10 mt-2 w-full rounded-lg bg-panel-light shadow-e3 dark:bg-panel-dark dark:shadow-none"
        >
          <Notice
            variant="error"
            title="Error searching companies"
            description={
              <span key={companiesQuery.errorUpdateCount}>
                {error instanceof ApiError
                  ? error.detail
                  : error instanceof Error
                    ? error.message
                    : 'An unexpected error occurred. Please try again.'}
              </span>
            }
            action={<RetryButton size="sm" failures={[failure]} focusTarget={inputRef} textField />}
          />
        </div>
      )}

      {/* No Results Message */}
      {!isLoading && !isError && companies && companies.length === 0 && debouncedQuery.length > 0 && (
        <div className="absolute z-10 mt-2 w-full rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark p-4 shadow-e3 dark:shadow-none backdrop-blur-sm">
          <div className="text-center text-text-secondary-light dark:text-text-secondary-dark">No company with a ticker on SEC EDGAR matches &quot;{debouncedQuery}&quot;.</div>
        </div>
      )}

      {/* Search Results: one popup holding the listbox and a visual keyboard hint. Each option is
          the company (name, ticker · exchange, today's quote when the search has one) over the
          filing identity strip of the filing a pick lands on (2026-10 critique 1d, P-04). */}
      {companies && companies.length > 0 && (
        <div className="absolute z-10 mt-2 w-full overflow-hidden rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-panel-dark shadow-e3 dark:shadow-none backdrop-blur-sm">
          <div id="company-search-results" role="listbox" aria-label="Company results" className="max-h-96 overflow-y-auto">
            {companies.map((company, index) => (
              <button
                key={company.id}
                id={`company-search-option-${index}`}
                role="option"
                aria-selected={index === highlightIndex}
                onClick={() => handleCompanyClick(company, index)}
                className={`flex w-full items-start gap-3 border-b border-border-light dark:border-white/10 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-brand-weak focus-visible:outline-none focus-visible:shadow-ring-brand-inset dark:hover:bg-white/5 dark:focus-visible:shadow-ring-brand-inset-dark ${
                  index === highlightIndex ? 'bg-brand-weak dark:bg-white/10' : ''
                }`}
              >
                <CompanyLogo decorative ticker={company.ticker} name={formatCompanyName(company.name)} size={24} />
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                    <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{formatCompanyName(company.name)}</span>
                    <span className="font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
                      {company.ticker}
                      {company.exchange && (
                        <>
                          <span aria-hidden="true"> · </span>
                          <span className="sr-only">, </span>
                          {company.exchange}
                        </>
                      )}
                    </span>
                    {company.stock_quote?.price ? (
                      <span className="ml-auto whitespace-nowrap font-data text-xs tabular-nums">
                        <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                          {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                        </span>
                        {company.stock_quote.change !== undefined && company.stock_quote.change_percent !== undefined && (
                          <>
                            {' '}
                            <span className={`font-medium ${directionText[directionOf(company.stock_quote.change)]}`}>
                              {fmtCurrency(company.stock_quote.change, { digits: 2, compact: false })}{' '}
                              ({fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })})
                            </span>
                          </>
                        )}
                      </span>
                    ) : null}
                  </div>
                  {company.latest_filing && <LatestFilingLine filing={company.latest_filing} />}
                </div>
              </button>
            ))}
          </div>
          {/* Visual only: the listbox already announces its options; phones have no arrow keys. */}
          <div
            aria-hidden="true"
            className="flex items-center justify-between gap-3 border-t border-border-light px-4 py-2 font-data text-xs text-text-secondary-light dark:border-white/10 dark:text-text-secondary-dark"
          >
            <span>
              {companies.length} {companies.length === 1 ? 'company' : 'companies'}
            </span>
            <span className="hidden sm:inline">↑↓ to move · ↵ to open</span>
          </div>
        </div>
      )}
    </div>
  )
}

/** "Latest 10-K · fiscal year ended Sep 27, 2025 · filed Oct 31, 2025 · summary ready": the filing a
 *  pick lands on, in the filing identity strip's vocabulary. */
function LatestFilingLine({ filing }: { filing: LatestFilingRef }) {
  const period = periodPhrase({ filing_type: filing.filing_type, report_date: filing.report_date ?? undefined })
  const filed = formatLocalDate(filing.filing_date, 'MMM d, yyyy')
  const facts = [
    <span key="form">
      Latest <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{filing.filing_type}</span>
    </span>,
    period && <span key="period">{period}</span>,
    filed && <span key="filed">filed {filed}</span>,
    filing.summary_ready && <span key="ready">summary ready</span>,
  ].filter(Boolean)
  return (
    <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 font-data text-xs tabular-nums text-text-secondary-light dark:text-text-secondary-dark">
      {facts.map((fact, i) => (
        <Fragment key={i}>
          {i > 0 && <Sep />}
          {fact}
        </Fragment>
      ))}
    </p>
  )
}

