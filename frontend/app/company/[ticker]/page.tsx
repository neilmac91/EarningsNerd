'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCompany, getCompanyFilings, Company, Filing, addToWatchlist, removeFromWatchlist, getWatchlist } from '@/lib/api'
import { FileText, Calendar, ExternalLink, Loader2, ChevronDown, ChevronUp, Filter, Star, X } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import { fmtCurrency, fmtPercent } from '@/lib/format'


export default function CompanyPage() {
  const params = useParams()
  const ticker = params.ticker as string

  const { data: company, isLoading: companyLoading } = useQuery<Company>({
    queryKey: ['company', ticker],
    queryFn: () => getCompany(ticker),
  })

  const { data: filings, isLoading: filingsLoading } = useQuery<Filing[]>({
    queryKey: ['filings', ticker],
    queryFn: () => getCompanyFilings(ticker),
    enabled: !!company,
  })

  const { data: watchlist } = useQuery({
    queryKey: ['watchlist'],
    queryFn: getWatchlist,
    retry: false,
    enabled: !!localStorage.getItem('token'), // Only fetch if user is logged in
  })

  const queryClient = useQueryClient()

  const watchlistMutation = useMutation({
    mutationFn: async (ticker: string) => {
      const isInWatchlist = watchlist?.some((w: any) => w.company.ticker === ticker)
      if (isInWatchlist) {
        await removeFromWatchlist(ticker)
      } else {
        await addToWatchlist(ticker)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['watchlist'] })
    },
  })

  const isInWatchlist = watchlist?.some((w: any) => w.company.ticker === ticker)

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
          <Link href="/" className="text-primary-600 hover:underline">
            Go back home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/" className="text-slate-600 hover:text-slate-900 font-medium transition-colors">
                ← Back
              </Link>
              <div className="border-l border-gray-200 pl-4 flex-1">
                <div className="flex items-center space-x-3">
                  <h1 className="text-2xl font-bold text-gray-900">{company.name}</h1>
                  {typeof window !== 'undefined' && localStorage.getItem('token') && (
                    <button
                      onClick={() => watchlistMutation.mutate(ticker)}
                      disabled={watchlistMutation.isPending}
                      className={`p-2 rounded-lg transition-colors ${
                        isInWatchlist
                          ? 'bg-yellow-100 text-yellow-600 hover:bg-yellow-200'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
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
                <div className="flex flex-col space-y-1 mt-1">
                  <div className="flex items-center space-x-3">
                    <span className="text-sm text-gray-500">{company.ticker}</span>
                    {company.stock_quote?.price ? (
                      <div className="flex items-center space-x-2">
                        <span className="text-sm font-semibold text-gray-900">
                          {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                        </span>
                        {company.stock_quote.change !== undefined && company.stock_quote.change_percent !== undefined && (
                          <span
                            className={`text-sm font-medium ${
                              company.stock_quote.change >= 0
                                ? 'text-green-600'
                                : 'text-red-600'
                            }`}
                          >
                            {fmtCurrency(company.stock_quote.change, { digits: 2, compact: false })}{' '}
                            ({fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })})
                          </span>
                        )}
                      </div>
                    ) : (
                      <span className="text-sm text-gray-400">Loading price...</span>
                    )}
                  </div>
                  {/* Pre-market / After-hours */}
                  {(company.stock_quote?.pre_market_price || company.stock_quote?.post_market_price) && (
                    <div className="flex items-center space-x-4 text-xs">
                      {company.stock_quote.pre_market_price && (
                        <div className="flex items-center space-x-1">
                          <span className="text-gray-500">Pre:</span>
                          <span className="font-semibold text-gray-900">
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
                          <span className="text-gray-500">After:</span>
                          <span className="font-semibold text-gray-900">
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
              </div>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="mb-8">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-2xl font-semibold text-gray-900">All Filings</h2>
            {filings && filings.length > 0 && (
              <span className="text-sm text-gray-500">
                {filings.length} {filings.length === 1 ? 'filing' : 'filings'} found
              </span>
            )}
          </div>
          
          {filingsLoading ? (
            <div className="flex justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : filings && filings.length > 0 ? (
            <FilingsGroupedByYear filings={filings} />
          ) : (
            <div className="bg-white rounded-lg p-8 text-center shadow-sm">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-600 text-lg">No filings found for this company.</p>
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function FilingsGroupedByYear({ filings }: { filings: Filing[] }) {
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set())
  const [filterType, setFilterType] = useState<'all' | '10-K' | '10-Q' | '8-K'>('all')

  // Group filings by year
  const filingsByYear = filings.reduce((acc, filing) => {
    const year = new Date(filing.filing_date).getFullYear().toString()
    if (!acc[year]) {
      acc[year] = []
    }
    acc[year].push(filing)
    return acc
  }, {} as Record<string, Filing[]>)

  // Filter by type if needed
  const filteredFilingsByYear = Object.entries(filingsByYear).reduce((acc, [year, yearFilings]) => {
    const filtered = filterType === 'all' 
      ? yearFilings 
      : yearFilings.filter(f => f.filing_type === filterType)
    
    if (filtered.length > 0) {
      acc[year] = filtered.sort((a, b) => 
        new Date(b.filing_date).getTime() - new Date(a.filing_date).getTime()
      )
    }
    return acc
  }, {} as Record<string, Filing[]>)

  // Auto-expand current year and last year
  const currentYear = new Date().getFullYear().toString()
  const lastYear = (new Date().getFullYear() - 1).toString()
  const defaultExpanded = new Set([currentYear, lastYear])
  
  const toggleYear = (year: string) => {
    const newExpanded = new Set(expandedYears)
    if (newExpanded.has(year)) {
      newExpanded.delete(year)
    } else {
      newExpanded.add(year)
    }
    setExpandedYears(newExpanded)
  }

  const years = Object.keys(filteredFilingsByYear).sort((a, b) => parseInt(b) - parseInt(a))
  const isExpanded = (year: string) => expandedYears.has(year) || defaultExpanded.has(year)

  // Count filings by type
  const typeCounts = filings.reduce((acc, filing) => {
    acc[filing.filing_type] = (acc[filing.filing_type] || 0) + 1
    return acc
  }, {} as Record<string, number>)

  return (
    <div className="space-y-6">
      {/* Filter Controls */}
      <div className="bg-white rounded-lg shadow-sm p-4 border border-gray-200">
        <div className="flex items-center space-x-4">
          <Filter className="h-5 w-5 text-gray-400" />
          <span className="text-sm font-medium text-gray-700">Filter by type:</span>
          <div className="flex items-center space-x-2">
            <button
              onClick={() => setFilterType('all')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterType === 'all'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              All ({filings.length})
            </button>
            <button
              onClick={() => setFilterType('10-K')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterType === '10-K'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              10-K ({typeCounts['10-K'] || 0})
            </button>
            <button
              onClick={() => setFilterType('10-Q')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterType === '10-Q'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              10-Q ({typeCounts['10-Q'] || 0})
            </button>
            <button
              onClick={() => setFilterType('8-K')}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                filterType === '8-K'
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              8-K ({typeCounts['8-K'] || 0})
            </button>
          </div>
        </div>
      </div>

      {/* Filings grouped by year */}
      {years.length === 0 ? (
        <div className="bg-white rounded-lg p-8 text-center shadow-sm">
          <p className="text-gray-600">No filings match the selected filter.</p>
        </div>
      ) : (
        years.map((year) => {
          const yearFilings = filteredFilingsByYear[year]
          const expanded = isExpanded(year)
          
          return (
            <div key={year} className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
              {/* Year Header */}
              <button
                onClick={() => toggleYear(year)}
                className="w-full flex items-center justify-between px-6 py-4 bg-gray-50 hover:bg-gray-100 transition-colors text-left"
              >
                <div className="flex items-center space-x-3">
                  <ChevronDown 
                    className={`h-5 w-5 text-gray-500 transition-transform ${
                      expanded ? 'rotate-0' : '-rotate-90'
                    }`}
                  />
                  <h3 className="text-lg font-semibold text-gray-900">{year}</h3>
                  <span className="text-sm text-gray-500">
                    {yearFilings.length} {yearFilings.length === 1 ? 'filing' : 'filings'}
                  </span>
                </div>
                       <div className="flex items-center space-x-4 text-sm text-gray-500">
                         <span className="inline-flex items-center space-x-1.5">
                           <span className="w-2 h-2 rounded-full bg-blue-500"></span>
                           <span>{yearFilings.filter(f => f.filing_type === '10-K').length} 10-K</span>
                         </span>
                         <span className="inline-flex items-center space-x-1.5">
                           <span className="w-2 h-2 rounded-full bg-purple-500"></span>
                           <span>{yearFilings.filter(f => f.filing_type === '10-Q').length} 10-Q</span>
                         </span>
                         {yearFilings.filter(f => f.filing_type === '8-K').length > 0 && (
                           <span className="inline-flex items-center space-x-1.5">
                             <span className="w-2 h-2 rounded-full bg-orange-500"></span>
                             <span>{yearFilings.filter(f => f.filing_type === '8-K').length} 8-K</span>
                           </span>
                         )}
                       </div>
              </button>

              {/* Year Filings */}
              {expanded && (
                <div className="divide-y divide-gray-100">
                  {yearFilings.map((filing) => (
                    <FilingCard key={filing.id} filing={filing} />
                  ))}
                </div>
              )}
            </div>
          )
        })
      )}
    </div>
  )
}

function FilingCard({ filing }: { filing: Filing }) {
  return (
    <div className="px-6 py-4 hover:bg-gray-50 transition-colors">
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-4 flex-1">
          <div className={`mt-1 px-2 py-1 rounded text-xs font-semibold ${
            filing.filing_type === '10-K' 
              ? 'bg-blue-100 text-blue-700' 
              : filing.filing_type === '10-Q'
              ? 'bg-purple-100 text-purple-700'
              : 'bg-orange-100 text-orange-700'
          }`}>
            {filing.filing_type}
          </div>
          <div className="flex-1">
            <div className="flex items-center space-x-4 text-sm text-gray-600">
              <div className="flex items-center space-x-1.5">
                <Calendar className="h-4 w-4 text-gray-400" />
                <span className="font-medium">Filed: {format(new Date(filing.filing_date), 'MMM dd, yyyy')}</span>
              </div>
              {filing.report_date && (
                <>
                  <span className="text-gray-300">•</span>
                  <span>Period: {format(new Date(filing.report_date), 'MMM dd, yyyy')}</span>
                </>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center space-x-2 ml-4">
          <Link
            href={`/filing/${filing.id}`}
            className="bg-primary-600 text-white px-4 py-2 rounded-lg hover:bg-primary-700 transition-colors text-sm font-medium whitespace-nowrap"
            title="View AI-generated summary of this filing"
          >
            View AI Summary
          </Link>
          <a
            href={filing.sec_url}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center space-x-1.5 px-3 py-2 rounded-lg border border-gray-300 text-gray-700 hover:bg-gray-50 hover:border-gray-400 transition-colors text-sm ml-2"
            title="View original filing on SEC EDGAR"
          >
            <ExternalLink className="h-4 w-4" />
            <span className="text-xs font-medium">View on SEC</span>
          </a>
        </div>
      </div>
    </div>
  )
}

