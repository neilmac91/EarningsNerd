'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCompany, getCompanyFilings, Company, Filing, addToWatchlist, removeFromWatchlist, getWatchlist } from '@/lib/api'
import { FileText, Calendar, ExternalLink, Loader2, ChevronDown, ChevronUp, Filter, Star, X } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { ThemeToggle } from '@/components/ThemeToggle'

export default function CompanyPageClient() {
  const params = useParams()
  const ticker = params?.ticker as string | undefined

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

  const { data: company, isLoading: companyLoading, error: companyError } = useQuery<Company>({
    queryKey: ['company', ticker],
    queryFn: () => getCompany(ticker),
    retry: 1,
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
    enabled: typeof window !== 'undefined' && !!localStorage.getItem('token'), // Only fetch if user is logged in
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

  // All hooks must be called before any conditional returns
  const currentYear = new Date().getFullYear().toString()
  const [expandedYears, setExpandedYears] = useState<Set<string>>(new Set([currentYear]))
  const [filterType, setFilterType] = useState<string | null>(null)

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
          <p className="text-gray-600 mb-4">
            {companyError ? `Error: ${companyError instanceof Error ? companyError.message : 'Failed to load company'}` : `Could not find company with ticker "${ticker}"`}
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

  const filteredFilings = filterType
    ? filings?.filter((f) => f.filing_type === filterType)
    : filings

  // Group filings by year
  const groupedFilings = filteredFilings?.reduce((acc, filing) => {
    const year = new Date(filing.filing_date).getFullYear().toString()
    if (!acc[year]) {
      acc[year] = []
    }
    acc[year].push(filing)
    return acc
  }, {} as Record<string, Filing[]>) || {}

  // Sort years in descending order (newest first)
  const sortedYears = Object.keys(groupedFilings).sort((a, b) => parseInt(b) - parseInt(a))

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
      case '8-K':
        return {
          borderColor: 'border-l-purple-600 dark:border-l-purple-500',
          bgColor: 'bg-purple-50/50 dark:bg-purple-900/20',
          hoverBg: 'hover:bg-purple-50 dark:hover:bg-purple-900/30',
          iconColor: 'text-purple-600 dark:text-purple-400',
          badgeBg: 'bg-purple-100 dark:bg-purple-900/40',
          badgeText: 'text-purple-800 dark:text-purple-300',
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
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Link href="/" className="text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-100 font-medium transition-colors">
                ← Back
              </Link>
              <div className="border-l border-gray-200 dark:border-gray-700 pl-4 flex-1">
                <div className="flex items-center space-x-3">
                  <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{companyData.name}</h1>
                  {typeof window !== 'undefined' && localStorage.getItem('token') && (
                    <button
                      onClick={() => watchlistMutation.mutate(ticker)}
                      disabled={watchlistMutation.isPending}
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
            <div className="flex items-center space-x-2">
              <ThemeToggle />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Filings Section */}
        <section className="bg-white dark:bg-slate-900 rounded-lg shadow-sm border border-gray-200 dark:border-gray-800 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">SEC Filings</h2>
            {filings && filings.length > 0 && (
              <div className="flex items-center space-x-2">
                <Filter className="h-4 w-4 text-gray-400 dark:text-gray-500" />
                <div className="flex items-center space-x-2">
                  <button
                    onClick={() => setFilterType(null)}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      filterType === null
                        ? 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900'
                        : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
                    }`}
                  >
                    All Types
                  </button>
                  <button
                    onClick={() => setFilterType('10-K')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      filterType === '10-K'
                        ? 'bg-blue-600 dark:bg-blue-500 text-white'
                        : 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300 hover:bg-blue-200 dark:hover:bg-blue-900/50'
                    }`}
                  >
                    10-K
                  </button>
                  <button
                    onClick={() => setFilterType('10-Q')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      filterType === '10-Q'
                        ? 'bg-teal-600 dark:bg-teal-500 text-white'
                        : 'bg-teal-100 dark:bg-teal-900/30 text-teal-800 dark:text-teal-300 hover:bg-teal-200 dark:hover:bg-teal-900/50'
                    }`}
                  >
                    10-Q
                  </button>
                  <button
                    onClick={() => setFilterType('8-K')}
                    className={`px-4 py-2 text-sm font-medium rounded-md transition-colors ${
                      filterType === '8-K'
                        ? 'bg-purple-600 dark:bg-purple-500 text-white'
                        : 'bg-purple-100 dark:bg-purple-900/30 text-purple-800 dark:text-purple-300 hover:bg-purple-200 dark:hover:bg-purple-900/50'
                    }`}
                  >
                    8-K
                  </button>
                </div>
              </div>
            )}
          </div>

          {filingsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
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
                              <div className="flex items-start justify-between">
                                <div className="flex-1">
                                  <div className="flex items-center space-x-3">
                                    <FileText className={`h-5 w-5 ${styles.iconColor}`} />
                                    <div>
                                      <div className="flex items-center space-x-2">
                                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold ${styles.badgeBg} ${styles.badgeText}`}>
                                          {filing.filing_type}
                                        </span>
                                        <span className="text-sm text-gray-500 dark:text-gray-400">
                                          {format(new Date(filing.filing_date), 'MMM d, yyyy')}
                                        </span>
                                      </div>
                                    </div>
                                  </div>
                                </div>
                                <div className="flex items-center space-x-2 ml-4">
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

