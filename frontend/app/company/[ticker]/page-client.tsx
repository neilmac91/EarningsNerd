'use client'

import { useState } from 'react'
import { useParams } from 'next/navigation'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getCompany, getCompanyFilings, Company, Filing, addToWatchlist, removeFromWatchlist, getWatchlist } from '@/lib/api'
import { FileText, Calendar, ExternalLink, Loader2, ChevronDown, ChevronUp, Filter, Star, X } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import { fmtCurrency, fmtPercent } from '@/lib/format'

export default function CompanyPageClient() {
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

  const [expandedSections, setExpandedSections] = useState<Set<string>>(new Set())
  const [filterType, setFilterType] = useState<string | null>(null)

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(section)) {
      newExpanded.delete(section)
    } else {
      newExpanded.add(section)
    }
    setExpandedSections(newExpanded)
  }

  const filteredFilings = filterType
    ? filings?.filter((f) => f.filing_type === filterType)
    : filings

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
                <div className="mt-1 flex items-center space-x-4 text-sm text-gray-500">
                  <span className="font-medium">{company.ticker}</span>
                  {company.exchange && <span>{company.exchange}</span>}
                  {company.stock_quote?.price !== undefined && company.stock_quote?.price !== null && (
                    <div className="flex items-center space-x-2">
                      <span className="font-semibold text-gray-900">
                        {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                      </span>
                      {company.stock_quote.change_percent !== undefined && company.stock_quote.change_percent !== null && (
                        <span
                          className={`font-medium ${
                            company.stock_quote.change_percent >= 0 ? 'text-green-600' : 'text-red-600'
                          }`}
                        >
                          {fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })}
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
        {/* Filings Section */}
        <section className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900">SEC Filings</h2>
            {filings && filings.length > 0 && (
              <div className="flex items-center space-x-2">
                <Filter className="h-4 w-4 text-gray-400" />
                <select
                  value={filterType || ''}
                  onChange={(e) => setFilterType(e.target.value || null)}
                  className="text-sm border border-gray-300 rounded-md px-3 py-1 focus:outline-none focus:ring-2 focus:ring-primary-500"
                >
                  <option value="">All Types</option>
                  <option value="10-K">10-K</option>
                  <option value="10-Q">10-Q</option>
                  <option value="8-K">8-K</option>
                </select>
              </div>
            )}
          </div>

          {filingsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-8 w-8 animate-spin text-primary-600" />
            </div>
          ) : filteredFilings && filteredFilings.length > 0 ? (
            <div className="space-y-3">
              {filteredFilings.map((filing) => (
                <div
                  key={filing.id}
                  className="border border-gray-200 rounded-lg p-4 hover:bg-gray-50 transition-colors"
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3">
                        <FileText className="h-5 w-5 text-gray-400" />
                        <div>
                          <div className="flex items-center space-x-2">
                            <span className="font-semibold text-gray-900">{filing.filing_type}</span>
                            <span className="text-sm text-gray-500">
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
                          className="p-2 text-gray-400 hover:text-gray-600 transition-colors"
                          title="View on SEC EDGAR"
                        >
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      )}
                      <Link
                        href={`/filing/${filing.id}`}
                        className="inline-flex items-center px-4 py-2 bg-primary-600 text-white text-sm font-medium rounded-md hover:bg-primary-700 transition-colors"
                      >
                        View Summary
                      </Link>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-12">
              <FileText className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500">No filings found for this company.</p>
            </div>
          )}
        </section>
      </main>
    </div>
  )
}

