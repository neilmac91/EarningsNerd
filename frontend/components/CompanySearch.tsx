'use client'

import { useState, useEffect } from 'react'
import { Search, Loader2 } from 'lucide-react'
import { useQuery } from '@tanstack/react-query'
import { searchCompanies, Company, getApiUrl } from '@/lib/api'
import { useRouter } from 'next/navigation'
import { fmtCurrency, fmtPercent } from '@/lib/format'

export default function CompanySearch() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const router = useRouter()

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedQuery(query)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const { data: companies, isLoading, error, isError } = useQuery({
    queryKey: ['companies', debouncedQuery],
    queryFn: () => searchCompanies(debouncedQuery),
    enabled: debouncedQuery.length > 0,
    retry: 1,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 10 * 60 * 1000, // 10 minutes (formerly cacheTime)
  })

  const handleCompanyClick = (company: Company) => {
    router.push(`/company/${company.ticker}`)
  }

  return (
    <div className="relative">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5" />
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search for a company (e.g., AAPL, Apple, Microsoft)..."
          className="w-full pl-12 pr-4 py-4 text-lg text-gray-900 placeholder:text-gray-500 border-2 border-gray-300 rounded-lg focus:outline-none focus:border-primary-500 bg-white"
        />
        {isLoading && (
          <Loader2 className="absolute right-4 top-1/2 transform -translate-y-1/2 text-gray-400 h-5 w-5 animate-spin" />
        )}
      </div>

      {/* Error Message */}
      {isError && debouncedQuery.length > 0 && (
        <div className="absolute z-10 w-full mt-2 bg-red-50 border border-red-200 rounded-lg shadow-lg p-4">
          <div className="text-red-800 font-semibold mb-1">Error searching companies</div>
          <div className="text-sm text-red-600">
            {error instanceof Error 
              ? error.message.includes('Network Error') || error.message.includes('ECONNREFUSED')
                ? `Unable to connect to the server. Please ensure the backend API is running on ${getApiUrl()}`
                : error.message
              : 'An unexpected error occurred. Please try again.'}
          </div>
        </div>
      )}

      {/* No Results Message */}
      {!isLoading && !isError && companies && companies.length === 0 && debouncedQuery.length > 0 && (
        <div className="absolute z-10 w-full mt-2 bg-gray-50 border border-gray-200 rounded-lg shadow-lg p-4">
          <div className="text-gray-600 text-center">No companies found matching "{debouncedQuery}"</div>
        </div>
      )}

      {/* Search Results */}
      {companies && companies.length > 0 && (
        <div className="absolute z-10 w-full mt-2 bg-white border border-gray-200 rounded-lg shadow-lg max-h-96 overflow-y-auto">
          {companies.map((company) => (
            <button
              key={company.id}
              onClick={() => handleCompanyClick(company)}
              className="w-full text-left px-4 py-3 hover:bg-gray-50 border-b border-gray-100 last:border-b-0"
            >
              <div className="font-semibold text-gray-900">{company.name}</div>
              <div className="flex flex-col space-y-1 text-sm">
                <div className="flex items-center space-x-2">
                  <span className="text-gray-500">{company.ticker}</span>
                  {company.stock_quote?.price ? (
                    <>
                      <span className="text-gray-300">•</span>
                      <span className="font-semibold text-gray-900">
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
                      <span className="text-gray-300">•</span>
                      <span className="text-gray-400">Loading price...</span>
                    </>
                  )}
                </div>
                {/* Pre-market / After-hours */}
                {(company.stock_quote?.pre_market_price || company.stock_quote?.post_market_price) && (
                  <div className="flex items-center space-x-3 text-xs pl-1">
                    {company.stock_quote.pre_market_price && (
                      <div className="flex items-center space-x-1">
                        <span className="text-gray-400">Pre:</span>
                        <span className="font-semibold text-gray-700">
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
                        <span className="text-gray-400">After:</span>
                        <span className="font-semibold text-gray-700">
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

