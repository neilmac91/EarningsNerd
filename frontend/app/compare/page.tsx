'use client'

import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { useRouter } from 'next/navigation'
import { getCompanyFilings, Filing, compareFilings } from '@/lib/api'
import { Loader2 } from 'lucide-react'
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
    <div className="min-h-screen bg-panel-light dark:bg-background-dark">
      <SecondaryHeader
        title="Compare Filings"
        subtitle="Select 2-5 filings to compare side-by-side"
        backHref="/"
        backLabel="Back to home"
        actions={<ThemeToggle />}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

        <SubscriptionGate requirePro={true}>
          <div className="bg-background-light rounded-lg shadow-sm border border-border-light p-6 mb-6 dark:bg-panel-dark dark:border-border-dark">
            <div className="mb-4">
              <label className="block text-sm font-medium text-text-secondary-light dark:text-text-secondary-dark mb-2">
                Search Company
              </label>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <input
                  type="text"
                  value={selectedTicker}
                  onChange={(e) => setSelectedTicker(e.target.value)}
                  onKeyPress={(e) => e.key === 'Enter' && handleSearch()}
                  placeholder="Enter ticker (e.g., AAPL)"
                  className="flex-1 px-4 py-2 border border-border-light rounded-lg bg-background-light text-text-primary-light placeholder:text-text-tertiary-light focus:outline-none focus:ring-2 focus:ring-mint-500/50 focus:border-mint-500 dark:border-border-dark dark:bg-background-dark dark:text-text-primary-dark dark:placeholder:text-text-tertiary-dark"
                />
                <button
                  onClick={handleSearch}
                  disabled={isSearching}
                  className="px-6 py-2 bg-mint-500 text-white rounded-lg hover:bg-mint-600 transition-colors disabled:opacity-60 font-semibold"
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
                <div className="mt-3">
                  <StateCard
                    variant="error"
                    title="Search Failed"
                    message={searchError}
                  />
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
                <h3 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark mb-4">
                  Select Filings ({selectedFilings.length}/5 selected)
                </h3>
                <div className="space-y-2 max-h-96 overflow-y-auto pr-2 custom-scrollbar">
                  {companyFilings.map((filing) => (
                    <div
                      key={filing.id}
                      onClick={() => toggleFiling(filing.id!)}
                      className={`p-4 border-2 rounded-lg cursor-pointer transition-colors ${
                        selectedFilings.includes(filing.id!)
                          ? 'border-mint-500 bg-mint-50 dark:bg-mint-900/20'
                          : 'border-border-light hover:border-mint-200 dark:border-border-dark dark:hover:border-mint-800 bg-background-light dark:bg-background-dark'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="font-medium text-text-primary-light dark:text-text-primary-dark">
                            {filing.filing_type} - {filing.filing_date && format(new Date(filing.filing_date), 'MMM dd, yyyy')}
                          </div>
                          {filing.report_date && (
                            <div className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                              Period: {format(new Date(filing.report_date), 'MMM dd, yyyy')}
                            </div>
                          )}
                        </div>
                        {selectedFilings.includes(filing.id!) && (
                          <div className="w-6 h-6 bg-mint-500 rounded-full flex items-center justify-center">
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
                    className="mt-6 w-full px-6 py-3 bg-mint-500 text-white rounded-lg hover:bg-mint-600 transition-colors font-semibold disabled:opacity-50"
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
                      className="inline-flex items-center rounded-lg bg-mint-500 px-4 py-2 text-sm font-semibold text-white hover:bg-mint-600 transition"
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
