'use client'

import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { format } from 'date-fns'
import { getCompany, type Company } from '@/features/companies/api/companies-api'
import { getCompanyFilings, type Filing } from '@/features/filings/api/filings-api'
import { CircleNotchIcon } from '@/lib/icons'
import { Badge, Skeleton } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'

/**
 * Filing route with a ticker in the URL (e.g. /filing/AAPL) rather than a numeric id:
 * shows the company's recent filings as a picker. Extracted from page-client.tsx (F2).
 */
export function TickerFilingsView({ ticker }: { ticker: string }) {
  const normalizedTicker = ticker.toUpperCase()

  const { data: company, isLoading: companyLoading, error: companyError } = useQuery<Company>({
    queryKey: queryKeys.tickerCompany(normalizedTicker),
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
  })

  const { data: filings, isLoading: filingsLoading, error: filingsError } = useQuery<Filing[]>({
    queryKey: queryKeys.tickerFilings(normalizedTicker),
    queryFn: () => getCompanyFilings(normalizedTicker),
    enabled: !!company,
    retry: 1,
  })

  if (companyLoading) {
    return (
      <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
        <div className="flex h-full min-h-screen items-center justify-center">
          <CircleNotchIcon className="h-8 w-8 animate-spin text-brand-strong dark:text-brand-strong-dark" />
        </div>
      </div>
    )
  }

  if (!company || companyError) {
    return (
      <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
        <div className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center">
          <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">Filings unavailable</h1>
          <p className="mt-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            We couldn&apos;t load filings for <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{normalizedTicker}</span> right now. Please try again later.
          </p>
          {companyError instanceof Error && (
            <p className="mt-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">{companyError.message}</p>
          )}
          <Link
            href="/"
            className="mt-6 inline-flex items-center rounded-full bg-brand px-5 py-2 text-sm font-semibold text-white transition hover:bg-brand-strong active:bg-brand-emphasis dark:bg-brand-dark dark:text-background-dark dark:hover:bg-brand-strong-dark"
          >
            Back to home
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold text-text-primary-light dark:text-text-primary-dark">{company.name}</h1>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {company.ticker} • Latest SEC filings
            </p>
          </div>
          <Link
            href={`/company/${company.ticker}`}
            className="inline-flex items-center rounded-full border border-border-light dark:border-white/20 bg-panel-light dark:bg-white/5 px-4 py-2 text-sm font-medium text-text-primary-light dark:text-text-primary-dark transition hover:border-brand-border hover:bg-brand-weak dark:hover:border-white/40 dark:hover:bg-white/10"
          >
            View company dashboard
          </Link>
        </div>

        <div className="rounded-3xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 p-6 shadow-e3 dark:shadow-[0_20px_50px_rgba(15,23,42,0.45)]">
          <h2 className="text-lg font-semibold text-text-primary-light dark:text-text-primary-dark">Recent filings</h2>
          <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            Select a filing below to open it and generate an AI summary.
          </p>

          <div className="mt-6 space-y-3">
            {filingsLoading && (
              <div className="space-y-3" role="status" aria-label="Loading filings">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-20 rounded-2xl" />
                ))}
                <span className="sr-only">Loading filings…</span>
              </div>
            )}

            {filingsError instanceof Error && (
              <div className="rounded-xl border border-error-light/30 dark:border-error-dark/40 bg-error-light/10 dark:bg-error-dark/10 p-4 text-sm text-error-light dark:text-error-dark">
                Unable to load filings right now. {filingsError.message}
              </div>
            )}

            {!filingsLoading && !filingsError && filings && filings.length === 0 && (
              <div className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/10 p-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
                No filings available yet for {company.ticker}. Check back soon.
              </div>
            )}

            {filings && filings.length > 0 && (
              <div className="grid gap-3">
                {filings.map((filing) => (
                  <Link
                    key={filing.id}
                    href={`/filing/${filing.id}`}
                    className="group flex flex-col gap-3 rounded-xl border border-border-light dark:border-white/10 bg-panel-light hover:bg-white dark:bg-panel-dark dark:hover:bg-white/[0.06] shadow-e2 dark:shadow-none p-5 transition-colors duration-fast hover:border-brand-border dark:hover:border-brand-border-dark"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">{filing.filing_type}</p>
                        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                          {filing.filing_date ? format(new Date(filing.filing_date), 'MMM dd, yyyy') : 'Date TBD'}
                        </p>
                      </div>
                      <Badge variant="brand">Generate AI summary</Badge>
                    </div>
                    <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Accession: {filing.accession_number}</div>
                  </Link>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
