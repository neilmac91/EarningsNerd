'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { getTrendingCompanies, Company } from '@/features/companies/api/companies-api'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { TrendingUp } from 'lucide-react'

export default function TrendingCompanies() {
  const { data: trendingCompanies, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['trendingCompanies'],
    queryFn: () => getTrendingCompanies(6),
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="rounded-2xl bg-white/50 dark:bg-white/5 p-8 text-center border border-gray-200/60 dark:border-white/10">
        <p className="text-gray-500 dark:text-slate-400 text-sm">Loading trending companies...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-2xl border border-red-200/60 bg-red-50/60 p-6 text-center text-sm text-red-700 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200">
        <p className="font-semibold">Unable to load trending companies.</p>
        <p className="mt-1 text-xs text-red-600/80 dark:text-red-200/80">
          {error instanceof Error ? error.message : 'Please try again in a moment.'}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="mt-3 inline-flex items-center rounded-md border border-red-200 bg-white/60 px-3 py-1 text-xs font-medium text-red-700 transition hover:bg-white dark:border-red-400/40 dark:bg-white/10 dark:text-red-100 dark:hover:bg-white/20 disabled:opacity-60"
        >
          {isFetching ? 'Retrying…' : 'Retry'}
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center space-x-3 mb-6">
        <div className="rounded-xl bg-gradient-to-br from-sky-500 to-indigo-500 p-2.5 shadow-lg shadow-sky-500/30">
          <TrendingUp className="h-5 w-5 text-white" />
        </div>
        <h3 className="text-2xl font-bold text-gray-900 dark:text-white tracking-tight">Trending Companies</h3>
      </div>
      {trendingCompanies && trendingCompanies.length > 0 ? (
        <div className="space-y-3">
          {trendingCompanies.map((company: Company) => (
            <Link
              key={company.id}
              href={`/company/${company.ticker}`}
              className="group block p-5 rounded-2xl bg-white dark:bg-white/5 hover:bg-gradient-to-br hover:from-white hover:to-gray-50/50 dark:hover:from-white/10 dark:hover:to-white/5 transition-all duration-300 border border-gray-200/60 dark:border-white/10 hover:border-gray-300 dark:hover:border-white/20 hover:shadow-lg hover:shadow-gray-900/5 dark:hover:shadow-black/20"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-gray-900 dark:text-white group-hover:text-sky-600 dark:group-hover:text-sky-400 transition-colors">
                    {company.name}
                  </div>
                  <div className="text-sm text-gray-500 dark:text-slate-400 font-medium mt-1">
                    {company.ticker}
                  </div>
                </div>
                {company.stock_quote?.price !== undefined && company.stock_quote?.price !== null && (
                  <div className="text-right">
                    <div className="text-gray-900 dark:text-white font-bold text-lg">
                      {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                    </div>
                    {company.stock_quote.change_percent !== undefined && company.stock_quote.change_percent !== null && (
                      <div className={`text-sm font-semibold mt-1 ${
                        company.stock_quote.change_percent >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                      }`}>
                        {fmtPercent(company.stock_quote.change_percent, { digits: 2, signed: true })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </Link>
          ))}
        </div>
      ) : (
        <div className="rounded-2xl bg-white/50 dark:bg-white/5 p-8 text-center border border-gray-200/60 dark:border-white/10">
          <p className="text-gray-500 dark:text-slate-400 text-sm">Trending companies will load once the API responds.</p>
        </div>
      )}
    </div>
  )
}
