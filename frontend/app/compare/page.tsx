'use client'

import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { getCompanyFilings, Filing, compareFilings } from '@/lib/api'
import { Loader2, X, TrendingUp, TrendingDown, AlertCircle, BarChart3 } from 'lucide-react'
import Link from 'next/link'
import { format } from 'date-fns'
import SubscriptionGate from '@/components/SubscriptionGate'
import { ThemeToggle } from '@/components/ThemeToggle'
import SecondaryHeader from '@/components/SecondaryHeader'
import StateCard from '@/components/StateCard'

export default function ComparePage() {
  const router = useRouter()
  const [selectedTicker, setSelectedTicker] = useState<string>('')
  const [selectedFilings, setSelectedFilings] = useState<number[]>([])
  const [companyFilings, setCompanyFilings] = useState<Filing[]>([])
  const [searchError, setSearchError] = useState<string | null>(null)
  const [isSearching, setIsSearching] = useState(false)

  const compareMutation = useMutation({
    mutationFn: compareFilings,
    onSuccess: (data) => {
      // Store comparison data and navigate to comparison view
      sessionStorage.setItem('comparisonData', JSON.stringify(data))
      router.push('/compare/result')
    },
  })

  const handleSearch = async () => {
    if (!selectedTicker) return
    setSearchError(null)
    setIsSearching(true)
    try {
      const filings = await getCompanyFilings(selectedTicker.toUpperCase())
      setCompanyFilings(filings)
      if (!filings.length) {
        setSearchError('No filings found for that ticker yet.')
      }
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unable to fetch filings right now.'
      setSearchError(message)
    } finally {
      setIsSearching(false)
    }
  }

  const toggleFiling = (filingId: number) => {
    setSelectedFilings(prev => {
      if (prev.includes(filingId)) {
        return prev.filter(id => id !== filingId)
      } else if (prev.length < 5) {
        return [...prev, filingId]
      }
      return prev
    })
  }

  const handleCompare = () => {
    if (selectedFilings.length >= 2) {
      compareMutation.mutate(selectedFilings)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-950">
      <SecondaryHeader
        title="Compare Filings"
        subtitle="Select 2-5 filings to compare side-by-side"
        backHref="/"
        backLabel="Back to home"
        actions={<ThemeToggle />}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        <SubscriptionGate requirePro={true}>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-6">
            <div className="mb-4">
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Search Company
              </label>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  type="text"
                  value={selectedTicker}
                  onChange={(e) => setSelectedTicker(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Enter ticker (e.g., AAPL)"
                  className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                />
                <button
                  onClick={handleSearch}
                  disabled={isSearching}
                  className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors disabled:opacity-60"
                >
                  {isSearching ? (
                    <span className="flex items-center justify-center">
                      <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      Searching...
                    </span>
                  ) : (
                    'Search'
                  )}
                </button>
              </div>
              {searchError && (
                <div className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {searchError}
                </div>
              )}
            </div>

            {compareMutation.isError && (
              <div className="mb-6">
                <StateCard
                  variant="error"
                  title="Comparison failed"
                  message={
                    compareMutation.error instanceof Error
                      ? compareMutation.error.message
                      : 'Please try again in a moment.'
                  }
                />
              </div>
            )}

            {companyFilings.length > 0 && (
              <div className="mt-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Select Filings ({selectedFilings.length}/5 selected)
                </h3>
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {companyFilings.map((filing) => (
                    <div
                      key={filing.id}
                      onClick={() => toggleFiling(filing.id!)}
                      className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                        selectedFilings.includes(filing.id!)
                          ? 'border-primary-500 bg-primary-50'
                          : 'border-gray-200 hover:border-gray-300'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-gray-900">
                            {filing.filing_type} - {filing.filing_date && format(new Date(filing.filing_date), 'MMM dd, yyyy')}
                          </div>
                          {filing.report_date && (
                            <div className="text-sm text-gray-600">
                              Period: {format(new Date(filing.report_date), 'MMM dd, yyyy')}
                            </div>
                          )}
                        </div>
                        {selectedFilings.includes(filing.id!) && (
                          <div className="w-6 h-6 bg-primary-600 rounded-full flex items-center justify-center">
                            <span className="text-white text-sm font-bold">✓</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                {selectedFilings.length >= 2 && (
                  <button
                    onClick={handleCompare}
                    disabled={compareMutation.isPending}
                    className="mt-6 w-full px-6 py-3 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition-colors font-semibold disabled:opacity-50"
                  >
                    {compareMutation.isPending ? (
                      <span className="flex items-center justify-center">
                        <Loader2 className="h-5 w-5 animate-spin mr-2" />
                        Comparing...
                      </span>
                    ) : (
                      'Compare Filings'
                    )}
                  </button>
                )}
              </div>
            )}

            {!companyFilings.length && !searchError && !isSearching && (
              <div className="mt-6">
                <StateCard
                  title="Start a comparison"
                  message="Search for a ticker to begin building a comparison set."
                  action={
                    <Link
                      href="/company/AAPL"
                      className="inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white hover:bg-primary-700 transition"
                    >
                      Explore companies
                    </Link>
                  }
                />
              </div>
            )}
          </div>
        </SubscriptionGate>
      </main>
    </div>
  )
}

