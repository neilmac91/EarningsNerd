'use client'

import { useState, useEffect, useRef, useMemo } from 'react'
import { CircleNotchIcon, MagnifyingGlassIcon } from '@/lib/icons'
import { useQuery } from '@tanstack/react-query'
import { searchCompanies, Company } from '@/features/companies/api/companies-api'
import CompanyLogo from '@/components/CompanyLogo'
import { ApiError } from '@/lib/api/client'
import { useRouter } from 'next/navigation'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText, directionOf } from '@/lib/financialTone'
import analytics from '@/lib/analytics'

const isTypingTarget = (el: EventTarget | null): boolean => {
  if (!(el instanceof HTMLElement)) return false
  return (
    el.tagName === 'INPUT' ||
    el.tagName === 'TEXTAREA' ||
    el.tagName === 'SELECT' ||
    el.isContentEditable
  )
}

export default function CompanySearch({ autoFocusDesktop = false }: { autoFocusDesktop?: boolean }) {
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
    if (!autoFocusDesktop) return
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
  }, [autoFocusDesktop])

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const { data: companies, isLoading, error, isError, refetch } = useQuery({
    queryKey: ['companies', debouncedQuery],
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

  // Navigate to a result and record the search→click so search→company conversion is causal.
  const goToResult = (ticker: string, position: number) => {
    analytics.companySearchResultClicked(debouncedQuery || query, ticker, position)
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
      } else {
        // No results yet (query in flight): if the input is ticker-shaped,
        // navigate directly — power users shouldn't wait for autocomplete.
        // Name-like queries ("apple inc") are NOT navigated; they'd produce
        // junk /company/ URLs.
        const typed = query.trim().toUpperCase()
        if (/^[A-Z]{1,5}(-[A-Z])?$/.test(typed)) {
          router.push(`/company/${typed}`)
        }
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

  return (
    <div className="relative">
      <div className="relative">
        <MagnifyingGlassIcon className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-text-tertiary-light dark:text-text-secondary-dark" />
        <input
          ref={inputRef}
          id="company-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleInputKeyDown}
          placeholder="Search any company (e.g., AAPL, Apple, Microsoft)..."
          role="combobox"
          aria-expanded={navigableTickers.length > 0}
          aria-controls="company-search-results"
          aria-activedescendant={
            highlightIndex >= 0 ? `company-search-option-${highlightIndex}` : undefined
          }
          aria-label="Search for a company"
          aria-describedby={isError ? "company-search-error" : undefined}
          aria-autocomplete="list"
          className="hero-search-glow w-full rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900/80 py-4 pl-12 pr-4 text-lg text-text-primary-light dark:text-text-primary-dark placeholder:text-text-tertiary-light dark:placeholder:text-text-secondary-dark backdrop-blur-sm focus:border-brand-strong/40 dark:focus:border-brand-dark/40 focus:outline-none"
        />
        {isLoading && (
          <CircleNotchIcon className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        )}
        {!isLoading && !query && (
          <kbd
            className="absolute right-4 top-1/2 hidden -translate-y-1/2 rounded border border-border-light dark:border-white/15 bg-brand-weak dark:bg-white/5 px-2 py-0.5 font-mono text-xs text-text-tertiary-light dark:text-text-secondary-dark sm:block"
            aria-hidden="true"
          >
            /
          </kbd>
        )}
      </div>

      {/* Error Message */}
      {isError && debouncedQuery.length > 0 && (
        <div
          id="company-search-error"
          role="alert"
          aria-live="polite"
          className="absolute z-10 mt-2 w-full rounded-xl border border-error-light/30 dark:border-error-dark/30 bg-panel-light dark:bg-error-dark/10 p-4 shadow-lg backdrop-blur-sm"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="mb-1 font-semibold text-error-light dark:text-error-dark">Error searching companies</div>
              <div className="text-sm text-error-light dark:text-error-dark">
                {error instanceof ApiError
                  ? error.detail
                  : error instanceof Error
                    ? error.message
                    : 'An unexpected error occurred. Please try again.'}
              </div>
            </div>
            <button
              onClick={() => refetch()}
              className="ml-4 rounded-lg border border-error-light/30 dark:border-error-dark/30 bg-error-light/10 dark:bg-error-dark/10 px-3 py-1.5 text-sm font-medium text-error-light dark:text-error-dark transition-colors hover:bg-error-light/15 dark:hover:bg-error-dark/20"
              aria-label="Retry search"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* No Results Message */}
      {!isLoading && !isError && companies && companies.length === 0 && debouncedQuery.length > 0 && (
        <div className="absolute z-10 mt-2 w-full rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900/95 p-4 shadow-lg backdrop-blur-sm">
          <div className="text-center text-text-secondary-light dark:text-text-secondary-dark">No companies found matching &quot;{debouncedQuery}&quot;</div>
        </div>
      )}

      {/* Search Results */}
      {companies && companies.length > 0 && (
        <div
          id="company-search-results"
          role="listbox"
          aria-label="Company results"
          className="absolute z-10 mt-2 max-h-96 w-full overflow-y-auto rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-slate-900/95 shadow-lg backdrop-blur-sm"
        >
          {companies.map((company, index) => (
            <button
              key={company.id}
              id={`company-search-option-${index}`}
              role="option"
              aria-selected={index === highlightIndex}
              onClick={() => handleCompanyClick(company, index)}
              className={`w-full border-b border-border-light dark:border-white/10 px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-brand-weak dark:hover:bg-white/5 ${
                index === highlightIndex ? 'bg-brand-weak dark:bg-white/10' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                <CompanyLogo ticker={company.ticker} name={company.name} size={24} />
                <div className="font-semibold text-text-primary-light dark:text-text-primary-dark">{company.name}</div>
              </div>
              <div className="flex flex-col space-y-1 text-sm">
                <div className="flex items-center space-x-2">
                  <span className="text-text-secondary-light dark:text-text-secondary-dark">{company.ticker}</span>
                  {company.stock_quote?.price ? (
                    <>
                      <span className="text-text-tertiary-light dark:text-text-secondary-dark">•</span>
                      <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                        {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                      </span>
                      {company.stock_quote.change !== undefined && company.stock_quote.change_percent !== undefined && (
                        <span
                          className={`font-medium ${directionText[directionOf(company.stock_quote.change)]}`}
                        >
                          {fmtCurrency(company.stock_quote.change, { digits: 2, compact: false })}{' '}
                          ({fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })})
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="text-text-tertiary-light dark:text-text-secondary-dark">•</span>
                      <span className="text-text-tertiary-light dark:text-text-secondary-dark">Loading price...</span>
                    </>
                  )}
                </div>
                {/* Pre-market / After-hours */}
                {(company.stock_quote?.pre_market_price || company.stock_quote?.post_market_price) && (
                  <div className="flex items-center space-x-3 text-xs pl-1">
                    {company.stock_quote.pre_market_price && (
                      <div className="flex items-center space-x-1">
                        <span className="text-text-tertiary-light dark:text-text-secondary-dark">Pre:</span>
                        <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                          {fmtCurrency(company.stock_quote.pre_market_price, { digits: 2, compact: false })}
                        </span>
                        {company.stock_quote.pre_market_change !== undefined && company.stock_quote.pre_market_change_percent !== undefined && (
                          <span
                            className={`font-medium ${directionText[directionOf(company.stock_quote.pre_market_change)]}`}
                          >
                            {fmtCurrency(company.stock_quote.pre_market_change, { digits: 2, compact: false })}{' '}
                            ({fmtPercent(company.stock_quote.pre_market_change_percent, { digits: 2, signed: true })})
                          </span>
                        )}
                      </div>
                    )}
                    {company.stock_quote.post_market_price && (
                      <div className="flex items-center space-x-1">
                        <span className="text-text-tertiary-light dark:text-text-secondary-dark">After:</span>
                        <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
                          {fmtCurrency(company.stock_quote.post_market_price, { digits: 2, compact: false })}
                        </span>
                        {company.stock_quote.post_market_change !== undefined && company.stock_quote.post_market_change_percent !== undefined && (
                          <span
                            className={`font-medium ${directionText[directionOf(company.stock_quote.post_market_change)]}`}
                          >
                            {fmtCurrency(company.stock_quote.post_market_change, { digits: 2, compact: false })}{' '}
                            ({fmtPercent(company.stock_quote.post_market_change_percent, { digits: 2, signed: true })})
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

