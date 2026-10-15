'use client'

import { formatCompanyName } from '@/lib/formatCompanyName'
import { useRef } from 'react'
import { useQuery } from '@tanstack/react-query'
import Link from 'next/link'
import { formatLocalDate } from '@/lib/format'
import { ApiError } from '@/lib/api/client'
import { getCompany, type Company } from '@/features/companies/api/companies-api'
import { getCompanyFilings, type Filing } from '@/features/filings/api/filings-api'
import { CircleNotchIcon } from '@/lib/icons'
import { Notice, Skeleton, buttonVariants, cx } from '@/components/ui'
import { queryKeys } from '@/lib/queryKeys'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { IDENTITY_LINK } from './FilingIdentity'
import SupersededFilingNotice from './SupersededFilingNotice'

/**
 * Filing route with a ticker in the URL (e.g. /filing/AAPL) rather than a numeric id:
 * shows the company's recent filings as a picker. Extracted from page-client.tsx (F2).
 *
 * Its failures read as the company page's do (#1292): a load failure says so in a sentence and offers
 * a Retry held through its refetch (useRetainedFailure), a 404 is an answer (no such ticker) and reads
 * as not found, a first load paused offline is still loading, and none prints the raw error.
 */
export function TickerFilingsView({ ticker }: { ticker: string }) {
  const normalizedTicker = ticker.toUpperCase()
  // The page's h1 in whichever branch shows: where a Retry's focus goes when its card leaves (the loaded
  // page's company name, or the not-found title when the retry finds no such ticker).
  const pageHeadingRef = useRef<HTMLHeadingElement>(null)
  // The filings section's heading: where the filings Retry's focus goes when the list loads.
  const filingsHeadingRef = useRef<HTMLHeadingElement>(null)

  const companyKey = queryKeys.tickerCompany(normalizedTicker)
  const companyQuery = useQuery<Company>({
    queryKey: companyKey,
    queryFn: () => getCompany(normalizedTicker),
    retry: 1,
  })
  const { data: company } = companyQuery
  // A failed load keeps its card, and a focused Retry in it, through the Retry's refetch: the query has
  // no data, so the refetch goes back to pending, and the spinner would otherwise replace the card.
  const companyFailure = useRetainedFailure(companyQuery, companyKey)
  // A first load paused offline (fetchStatus 'paused': the default networkMode 'online' holds the fetch, or
  // the retry after a failed one, until the network returns) is neither loading nor failed to TanStack, yet
  // nothing has answered, so it reads as loading, never as "Company not found". As the company page does.
  const companyPaused = companyQuery.isPending && companyQuery.fetchStatus === 'paused'
  const companyLoading = (companyQuery.isLoading || companyPaused) && !companyFailure.failed
  // A 404 is an answer, not a failure: read from the held error, so a refetch that clears the query's own
  // error while it runs does not turn the not-found page into the load-failure page.
  const companyNotFound = companyFailure.error instanceof ApiError && companyFailure.error.status === 404

  const filingsKey = queryKeys.tickerFilings(normalizedTicker)
  const filingsQuery = useQuery<Filing[]>({
    queryKey: filingsKey,
    queryFn: () => getCompanyFilings(normalizedTicker),
    enabled: !!company,
    retry: 1,
  })
  const { data: filings } = filingsQuery
  const filingsFailure = useRetainedFailure(filingsQuery, filingsKey)
  const filingsLoading = filingsQuery.isLoading && !filingsFailure.failed

  if (companyLoading) {
    return (
      <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
        <div className="flex h-full min-h-screen items-center justify-center">
          <CircleNotchIcon className="h-8 w-8 animate-spin motion-reduce:animate-none text-brand-strong dark:text-brand-strong-dark" />
        </div>
      </div>
    )
  }

  if (!company) {
    // A load failure says so and offers a Retry; only a 404 reads as not found (a request still waiting on
    // the network is the loading state above).
    const loadFailed = companyFailure.failed && !companyNotFound
    return (
      <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
        <div
          role={loadFailed ? 'alert' : undefined}
          className="mx-auto flex min-h-screen max-w-lg flex-col items-center justify-center px-6 text-center"
        >
          <h1
            ref={pageHeadingRef}
            tabIndex={-1}
            className="text-3xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
          >
            {loadFailed ? 'Filings unavailable' : 'Company not found'}
          </h1>
          <p className="mt-4 text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {loadFailed ? (
              <>
                We couldn’t load filings for{' '}
                <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{normalizedTicker}</span>. Try
                again in a moment.
              </>
            ) : (
              <>
                No company with a ticker on SEC EDGAR matches{' '}
                <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">{normalizedTicker}</span>.
              </>
            )}
          </p>
          {loadFailed ? (
            <RetryButton failures={[companyFailure]} focusTarget={pageHeadingRef} className="mt-6">
              Retry
            </RetryButton>
          ) : (
            <Link href="/" className={buttonVariants({ className: 'mt-6' })}>
              Go to the homepage
            </Link>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-background-light text-text-primary-light dark:bg-background-dark dark:text-text-primary-dark">
      <div className="mx-auto max-w-5xl px-4 py-12">
        <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1
              ref={pageHeadingRef}
              tabIndex={-1}
              className="text-3xl font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
            >
              {formatCompanyName(company.name)}
            </h1>
            <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
              {company.ticker} · Latest SEC filings
            </p>
          </div>
          <Link href={`/company/${company.ticker}`} className={buttonVariants({ variant: 'secondary' })}>
            View company page
          </Link>
        </div>

        <div className="rounded-3xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/5 p-6 shadow-e3 dark:shadow-[0_20px_50px_rgba(15,23,42,0.45)]">
          <h2
            ref={filingsHeadingRef}
            tabIndex={-1}
            className="text-lg font-semibold text-text-primary-light outline-none dark:text-text-primary-dark"
          >
            Recent filings
          </h2>
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

            {/* Inside the "Recent filings" card, so the inline Notice: a GuidanceCard is a standalone panel,
                never nested in a card (DESIGN_SYSTEM.md, GuidanceCard). */}
            {filingsFailure.failed && (
              <Notice
                variant="error"
                title="Couldn’t load the filings"
                description="Try again in a moment."
                action={
                  <RetryButton failures={[filingsFailure]} focusTarget={filingsHeadingRef} size="sm">
                    Retry
                  </RetryButton>
                }
              />
            )}

            {!filingsLoading && !filingsFailure.failed && filings && filings.length === 0 && (
              <div className="rounded-xl border border-border-light dark:border-white/10 bg-panel-light dark:bg-white/10 p-6 text-center text-sm text-text-secondary-light dark:text-text-secondary-dark">
                No filings available yet for {company.ticker}. Check back soon.
              </div>
            )}

            {filings && filings.length > 0 && (
              <div className="grid gap-3">
                {filings.map((filing) => (
                  <div
                    key={filing.id}
                    className="group flex flex-col gap-3 rounded-xl border border-border-light dark:border-white/10 bg-panel-light hover:bg-white dark:bg-panel-dark dark:hover:bg-white/[0.06] shadow-e2 dark:shadow-none p-5 transition-colors duration-fast hover:border-brand-border dark:hover:border-brand-border-dark"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-4">
                      <div>
                        <p className="text-base font-semibold text-text-primary-light dark:text-text-primary-dark">{filing.filing_type}</p>
                        <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
                          {formatLocalDate(filing.filing_date, 'MMM dd, yyyy', 'Date TBD')}
                        </p>
                      </div>
                      {/* A plain text link: the row's one action opens the filing (its summary is generated
                          there), and a Badge is a label, never a control. The ring is IDENTITY_LINK's, restated
                          so the focus-ring scan, which reads the file, sees it. The accessible name starts with
                          the visible "Open filing" (label in name, WCAG 2.5.3) and a hidden tail names the row's
                          filing (lessons/frontend-hidden-name-tails-bring-their-own-space.md). */}
                      <Link
                        href={`/filing/${filing.id}`}
                        className={cx(
                          IDENTITY_LINK,
                          'text-sm font-medium focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
                        )}
                      >
                        Open filing{' '}
                        <span className="sr-only">
                          ({filing.filing_type}, accession {filing.accession_number})
                        </span>
                      </Link>
                    </div>
                    <SupersededFilingNotice filing={filing} filings={filings} />
                    <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Accession: {filing.accession_number}</div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
