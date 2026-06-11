'use client'

import { useState, useEffect, useRef } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { searchCompanies, Company } from '@/features/companies/api/companies-api'
import { ApiError } from '@/lib/api/client'
import { useRouter } from 'next/navigation'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import analytics from '@/lib/analytics'

export default function CompanySearch({ autoFocusDesktop = false }: { autoFocusDesktop?: boolean }) {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
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

  const handleCompanyClick = (company: Company) => {
    router.push(`/company/${company.ticker}`)
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
        <Search className="absolute left-4 top-1/2 h-5 w-5 -translate-y-1/2 text-slate-500" />
        <input
          ref={inputRef}
          id="company-search"
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search any company (e.g., AAPL, Apple, Microsoft)..."
          aria-label="Search for a company"
          aria-describedby={isError ? "company-search-error" : undefined}
          className="hero-search-glow w-full rounded-xl border border-white/10 bg-slate-900/80 py-4 pl-12 pr-4 text-lg text-white placeholder:text-slate-500 backdrop-blur-sm focus:border-mint-500/40 focus:outline-none"
        />
        {isLoading && (
          <Loader2 className="absolute right-4 top-1/2 h-5 w-5 -translate-y-1/2 animate-spin text-mint-400" />
        )}
      </div>

      {/* Error Message */}
      {isError && debouncedQuery.length > 0 && (
        <div
          id="company-search-error"
          role="alert"
          aria-live="polite"
          className="absolute z-10 mt-2 w-full rounded-xl border border-red-500/30 bg-red-950/80 p-4 shadow-lg backdrop-blur-sm"
        >
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="mb-1 font-semibold text-red-200">Error searching companies</div>
              <div className="text-sm text-red-300">
                {error instanceof ApiError
                  ? error.detail
                  : error instanceof Error
                    ? error.message
                    : 'An unexpected error occurred. Please try again.'}
              </div>
            </div>
            <button
              onClick={() => refetch()}
              className="ml-4 rounded-md border border-red-500/30 bg-red-500/10 px-3 py-1.5 text-sm font-medium text-red-200 transition-colors hover:bg-red-500/20"
              aria-label="Retry search"
            >
              Try Again
            </button>
          </div>
        </div>
      )}

      {/* No Results Message */}
      {!isLoading && !isError && companies && companies.length === 0 && debouncedQuery.length > 0 && (
        <div className="absolute z-10 mt-2 w-full rounded-xl border border-white/10 bg-slate-900/95 p-4 shadow-lg backdrop-blur-sm">
          <div className="text-center text-slate-400">No companies found matching &quot;{debouncedQuery}&quot;</div>
        </div>
      )}

      {/* Search Results */}
      {companies && companies.length > 0 && (
        <div className="absolute z-10 mt-2 max-h-96 w-full overflow-y-auto rounded-xl border border-white/10 bg-slate-900/95 shadow-lg backdrop-blur-sm">
          {companies.map((company) => (
            <button
              key={company.id}
              onClick={() => handleCompanyClick(company)}
              className="w-full border-b border-white/[0.06] px-4 py-3 text-left transition-colors last:border-b-0 hover:bg-white/5"
            >
              <div className="font-semibold text-white">{company.name}</div>
              <div className="flex flex-col space-y-1 text-sm">
                <div className="flex items-center space-x-2">
                  <span className="text-slate-400">{company.ticker}</span>
                  {company.stock_quote?.price ? (
                    <>
                      <span className="text-slate-600">•</span>
                      <span className="font-semibold text-white">
                        {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                      </span>
                      {company.stock_quote.change !== undefined && company.stock_quote.change_percent !== undefined && (
                        <span
                          className={`font-medium ${
                            company.stock_quote.change >= 0
                              ? 'text-green-600'
                              : 'text-red-600'
                          }`}
                        >
                          {fmtCurrency(company.stock_quote.change, { digits: 2, compact: false })}{' '}
                          ({fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })})
                        </span>
                      )}
                    </>
                  ) : (
                    <>
                      <span className="text-slate-600">•</span>
                      <span className="text-slate-500">Loading price...</span>
                    </>
                  )}
                </div>
                {/* Pre-market / After-hours */}
                {(company.stock_quote?.pre_market_price || company.stock_quote?.post_market_price) && (
                  <div className="flex items-center space-x-3 text-xs pl-1">
                    {company.stock_quote.pre_market_price && (
                      <div className="flex items-center space-x-1">
                        <span className="text-slate-500">Pre:</span>
                        <span className="font-semibold text-slate-200">
                          {fmtCurrency(company.stock_quote.pre_market_price, { digits: 2, compact: false })}
                        </span>
                        {company.stock_quote.pre_market_change !== undefined && company.stock_quote.pre_market_change_percent !== undefined && (
                          <span
                            className={`font-medium ${
                              company.stock_quote.pre_market_change >= 0
                                ? 'text-green-600'
                                : 'text-red-600'
                            }`}
                          >
                            {fmtCurrency(company.stock_quote.pre_market_change, { digits: 2, compact: false })}{' '}
                            ({fmtPercent(company.stock_quote.pre_market_change_percent, { digits: 2, signed: true })})
                          </span>
                        )}
                      </div>
                    )}
                    {company.stock_quote.post_market_price && (
                      <div className="flex items-center space-x-1">
                        <span className="text-slate-500">After:</span>
                        <span className="font-semibold text-slate-200">
                          {fmtCurrency(company.stock_quote.post_market_price, { digits: 2, compact: false })}
                        </span>
                        {company.stock_quote.post_market_change !== undefined && company.stock_quote.post_market_change_percent !== undefined && (
                          <span
                            className={`font-medium ${
                              company.stock_quote.post_market_change >= 0
                                ? 'text-green-600'
                                : 'text-red-600'
                            }`}
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

