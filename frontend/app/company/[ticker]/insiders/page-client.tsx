'use client'

import Link from 'next/link'
import { useParams } from 'next/navigation'
import { useEffect, useRef } from 'react'
import { useQuery } from '@tanstack/react-query'

import CompanyLogo from '@/components/CompanyLogo'
import { Card, GuidanceCard, Skeleton, buttonVariants, cx } from '@/components/ui'
import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import { getCompany, type Company } from '@/features/companies/api/companies-api'
import { getCompanyFilings, type Filing } from '@/features/filings/api/filings-api'
import { IDENTITY_CRUMB, TickerPill } from '@/features/filings/components/FilingIdentity'
import { isFpiFiler } from '@/features/filings/lib/fpi'
import InsiderActivityPanel from '@/features/insiders/components/InsiderActivityPanel'
import { RetryButton, useRetainedFailure } from '@/hooks/useRetainedFailure'
import { ApiError } from '@/lib/api/client'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { queryKeys } from '@/lib/queryKeys'

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'

interface InsidersPageClientProps {
  /** Seeds for a test that mounts the bare client. The route passes none: it reads the company and its filings in
   *  the browser, from the company page's cache where the reader came from there. */
  initialCompany?: Company
  initialFilings?: Filing[]
}

/**
 * A company's insider (Form 4) activity on its own page (ADR 0009). The company page keeps its filings in the lead
 * and shows insider activity as a card in its side column; that card links here, where the read is shown in full:
 * the window control, the net signal and every trade the answer carries (InsiderActivityPanel).
 *
 * The lead is the company in the identity vocabulary of the company page (its mark, its name as the h1, its ticker),
 * under a breadcrumb that leads back to its filings. It stands from the first paint, named by the ticker until the
 * company's name is read, over the card's bones: the page has no full-page spinner (DESIGN_SYSTEM.md §11, Loading).
 * Insider activity is read by beta accounts only, so any other reader gets a card that says so and the way back,
 * never an empty page; the company's queries are the company page's own (the same keys), so arriving from there
 * renders from cache.
 */
export default function InsidersPageClient({ initialCompany, initialFilings }: InsidersPageClientProps = {}) {
  const params = useParams()
  const ticker = ((params?.ticker as string | undefined) ?? '').toUpperCase()
  const companyCardHeadingRef = useRef<HTMLHeadingElement>(null)

  const companyKey = queryKeys.company(ticker)
  const companyQuery = useQuery<Company>({
    queryKey: companyKey,
    queryFn: () => getCompany(ticker),
    retry: 1,
    enabled: !!ticker,
    initialData: initialCompany,
    initialDataUpdatedAt: 0,
  })
  const { data: company } = companyQuery
  const companyFailure = useRetainedFailure(companyQuery, companyKey)
  const companyNotFound = companyFailure.error instanceof ApiError && companyFailure.error.status === 404

  // The company's listed filings say whether it is a foreign private issuer, which files no Form 4s. The company
  // page's own default query, so its answer is shared.
  const filingsKey = queryKeys.companyFilings(ticker, undefined)
  const filingsQuery = useQuery<Filing[]>({
    queryKey: filingsKey,
    queryFn: () => getCompanyFilings(ticker, undefined, undefined),
    enabled: !!company && !!ticker,
    retry: 1,
    initialData: initialFilings,
    initialDataUpdatedAt: 0,
  })
  // Unknown while the filings load. A failed read is treated as "not known to be one": the endpoint is asked, and
  // a foreign issuer's stored scan simply holds no trades.
  const isFpi = filingsQuery.data ? isFpiFiler(filingsQuery.data) : filingsQuery.isError ? false : undefined

  // The reader: a user, null (signed out), or no answer. A check that failed outright has settled too, as a reader
  // who is not known to be a beta account, so the page never waits on it for good.
  const userQuery = useQuery({
    queryKey: queryKeys.currentUser(),
    queryFn: getCurrentUserSafe,
    retry: false,
  })
  const currentUser = userQuery.data
  const userSettled = currentUser !== undefined || userQuery.isError

  // The server names no company (the shell is one per ticker and fetches nothing), so the tab's title takes the
  // company's name here, in the form the company page's title has.
  const companyName = company ? formatCompanyName(company.name) || company.ticker : null
  useEffect(() => {
    if (companyName) document.title = `${companyName} (${ticker}) insider activity | EarningsNerd`
  }, [companyName, ticker])

  if (!company && companyFailure.failed) {
    // A load failure says so and offers Try again; only a 404 reads as "not found", and it is an answer, not an error.
    const loadFailed = !companyNotFound
    return (
      <main className="flex min-h-screen items-center justify-center px-4">
        <div className="w-full max-w-md">
          <GuidanceCard
            variant={loadFailed ? 'error' : 'empty'}
            headingLevel="h1"
            headingRef={companyCardHeadingRef}
            title={loadFailed ? 'Couldn’t load this company' : 'Company not found'}
            description={
              loadFailed ? 'Try again in a moment.' : `No company with a ticker on SEC EDGAR matches "${ticker}".`
            }
            action={
              loadFailed ? (
                <RetryButton failures={[companyFailure]} focusTarget={companyCardHeadingRef} />
              ) : (
                <Link href="/" className={buttonVariants({ variant: 'secondary' })}>
                  Go back home
                </Link>
              )
            }
          />
        </div>
      </main>
    )
  }

  // Until the company is read the lead is named by its ticker, which the address already gives.
  const name = companyName ?? ticker
  const companyHref = `/company/${encodeURIComponent(ticker)}`
  // An issuer that files no financial reports with the SEC files no Form 4s either: the foreign issuer's note.
  const foreign = company?.coverage_status === 'unsupported_foreign' ? true : isFpi

  return (
    <div className="min-h-screen bg-background-light dark:bg-background-dark">
      <header className="border-b border-border-light dark:border-border-dark">
        <div className="mx-auto flex max-w-7xl flex-col gap-5 px-4 pb-6 pt-5 sm:px-6 lg:flex-row lg:items-end lg:justify-between lg:gap-8 lg:px-8">
          <div className="flex min-w-0 flex-col gap-2">
            <nav aria-label="Breadcrumb" className="mb-3">
              <ol className="flex flex-wrap items-center gap-2 text-sm">
                <li>
                  <Link href="/" className={IDENTITY_CRUMB}>
                    Home
                  </Link>
                </li>
                <li aria-hidden="true" className={MUTED}>
                  /
                </li>
                <li>
                  <Link href={companyHref} className={IDENTITY_CRUMB}>
                    {name}
                  </Link>
                </li>
                <li aria-hidden="true" className={MUTED}>
                  /
                </li>
                <li aria-current="page" className={MUTED}>
                  Insider activity
                </li>
              </ol>
            </nav>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
              <CompanyLogo decorative ticker={ticker} name={name} size={36} priority />
              <h1 className={cx('min-w-0 break-words text-2xl font-semibold sm:text-3xl', INK)}>
                {name} <span className="sr-only">insider activity</span>
              </h1>
              <TickerPill ticker={ticker} />
            </div>
            <p className={cx('max-w-2xl text-sm', MUTED)}>
              Open-market trades by the company’s officers, directors and largest shareholders, as they report them
              to the SEC on Form&nbsp;4.
            </p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center lg:shrink-0">
            <Link href={companyHref} className={buttonVariants({ variant: 'secondary' })}>
              View filings
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        {!userSettled || !company ? (
          // The account check or the company is still out: the card's place, so the page does not jump when they
          // settle.
          <Card as="section" className="p-cap-6">
            <div role="status" aria-label="Loading insider activity">
              <Skeleton className="h-48 w-full rounded-lg" />
              <span className="sr-only">Loading…</span>
            </div>
          </Card>
        ) : currentUser?.is_beta ? (
          <InsiderActivityPanel key={ticker} ticker={ticker} isFpi={foreign} />
        ) : (
          // Insider activity is read by beta accounts only (the endpoint answers no one else): say so, with the way
          // back to the filings and, signed out, the way in.
          <div className="mx-auto max-w-md">
            <GuidanceCard
              variant="empty"
              headingLevel="h2"
              title="Insider activity is in beta"
              description={
                currentUser
                  ? 'It is open to beta testers for now. The company’s filings and summaries are a click away.'
                  : 'It is open to beta testers for now. Log in with a beta account to see it.'
              }
              action={
                <>
                  {!currentUser && (
                    <Link
                      href={`/login?redirect=${encodeURIComponent(`${companyHref}/insiders`)}`}
                      className={buttonVariants({ variant: 'primary' })}
                    >
                      Log in
                    </Link>
                  )}
                  <Link href={companyHref} className={buttonVariants({ variant: 'secondary' })}>
                    View filings
                  </Link>
                </>
              }
            />
          </div>
        )}
      </main>
    </div>
  )
}
