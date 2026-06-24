'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { getTrendingCompanies, Company } from '@/features/companies/api/companies-api'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText, directionOf } from '@/lib/financialTone'
import { TrendUpIcon } from '@/lib/icons'

export default function TrendingCompanies() {
  const { data: trendingCompanies, isLoading, isError, error, refetch, isFetching } = useQuery({
    queryKey: ['trendingCompanies'],
    queryFn: () => getTrendingCompanies(6),
    retry: 1,
  })

  if (isLoading) {
    return (
      <div className="rounded-2xl bg-panel-light dark:bg-white/5 shadow-e1 dark:shadow-none p-8 text-center border border-border-light dark:border-white/10">
        <p className="text-text-secondary-light dark:text-text-secondary-dark text-sm">Loading trending companies...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="rounded-2xl border border-error-light/30 bg-error-light/10 p-6 text-center text-sm text-error-light dark:border-error-dark/40 dark:bg-error-dark/10 dark:text-error-dark">
        <p className="font-semibold">Unable to load trending companies.</p>
        <p className="mt-1 text-xs text-error-light/80 dark:text-error-dark/80">
          {error instanceof Error ? error.message : 'Please try again in a moment.'}
        </p>
        <button
          type="button"
          onClick={() => refetch()}
          disabled={isFetching}
          className="mt-3 inline-flex items-center rounded-md border border-error-light/30 bg-error-light/10 px-3 py-1 text-xs font-medium text-error-light transition hover:bg-error-light/15 dark:border-error-dark/40 dark:bg-error-dark/10 dark:text-error-dark dark:hover:bg-error-dark/20 disabled:opacity-60"
        >
          {isFetching ? 'Retrying…' : 'Retry'}
        </button>
      </div>
    )
  }

  return (
    <div>
      <div className="flex items-center space-x-3 mb-6">
        <div className="rounded-xl bg-brand-strong/10 p-2.5 dark:bg-brand-dark/15">
          <TrendUpIcon className="h-5 w-5 text-brand-strong dark:text-brand-strong-dark" />
        </div>
        <h3 className="text-2xl font-bold text-text-primary-light dark:text-text-primary-dark tracking-tight">Trending Companies</h3>
      </div>
      {trendingCompanies && trendingCompanies.length > 0 ? (
        <div className="space-y-3">
          {trendingCompanies.map((company: Company) => (
            <Link
              key={company.id}
              href={`/company/${company.ticker}`}
              className="group block p-5 rounded-2xl bg-panel-light dark:bg-white/5 shadow-e1 dark:shadow-none hover:bg-gradient-to-br hover:from-panel-light hover:to-background-light dark:hover:from-white/10 dark:hover:to-white/5 transition-all duration-300 border border-border-light dark:border-white/10 hover:border-border-light dark:hover:border-white/20 hover:shadow-lg hover:shadow-gray-900/5 dark:hover:shadow-black/20"
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="font-semibold text-text-primary-light dark:text-text-primary-dark group-hover:text-brand-strong dark:group-hover:text-brand-strong-dark transition-colors">
                    {company.name}
                  </div>
                  <div className="text-sm text-text-secondary-light dark:text-text-secondary-dark font-medium mt-1">
                    {company.ticker}
                  </div>
                </div>
                {company.stock_quote?.price !== undefined && company.stock_quote?.price !== null && (
                  <div className="text-right">
                    <div className="text-text-primary-light dark:text-text-primary-dark font-bold text-lg">
                      {fmtCurrency(company.stock_quote.price, { digits: 2, compact: false })}
                    </div>
                    {company.stock_quote.change_percent !== undefined && company.stock_quote.change_percent !== null && (
                      <div className={`text-sm font-semibold mt-1 ${directionText[directionOf(company.stock_quote.change_percent)]}`}>
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
        <div className="rounded-2xl bg-panel-light dark:bg-white/5 shadow-e1 dark:shadow-none p-8 text-center border border-border-light dark:border-white/10">
          <p className="text-text-secondary-light dark:text-text-secondary-dark text-sm">Trending companies will load once the API responds.</p>
        </div>
      )}
    </div>
  )
}
