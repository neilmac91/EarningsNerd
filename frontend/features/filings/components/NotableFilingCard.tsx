'use client'

import Link from 'next/link'
import { formatDistanceStrict } from 'date-fns'

import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui'
import type { NotableFiling } from '@/lib/serverApi'

function filedAgo(isoDate: string, asOf: string): string | null {
  // filed_date is a plain YYYY-MM-DD EDGAR calendar day — anchor at UTC noon so the relative
  // label can't slip a day in extreme viewer timezones.
  //
  // Measure against the response's own timestamp, NEVER the live clock. This is a client
  // component server-rendered into an ISR page: `/` is cached for up to an hour, so HTML
  // generated at 23:50Z and hydrated at 00:10Z would render "3 days ago" on the server and
  // recompute "4 days ago" in the browser — a hydration mismatch and a visible text swap for
  // every request that straddles the rounding boundary. Anchoring both passes to `asOf` makes
  // the label a property of the data, which is what an ISR snapshot actually shows.
  try {
    const asOfDate = new Date(asOf)
    if (Number.isNaN(asOfDate.getTime())) return null
    return formatDistanceStrict(new Date(`${isoDate}T12:00:00Z`), asOfDate, { addSuffix: true })
  } catch {
    return null
  }
}

/**
 * One notable filing, linking to the COMPANY page (not /filing/{id}): market-wide candidates
 * aren't ingested yet, so a filing deep-link would hit cold ingestion — the company page lists
 * the filing and offers the summary CTA on warmed ground.
 */
export default function NotableFilingCard({
  filing,
  asOf,
}: {
  filing: NotableFiling
  asOf: string
}) {
  const ago = filedAgo(filing.filed_date, asOf)

  return (
    <Link
      href={`/company/${filing.ticker}`}
      onClick={() =>
        analytics.notableFilingClicked({
          ticker: filing.ticker,
          form: filing.form,
          reason: filing.reason,
        })
      }
      className="group flex items-center gap-3 rounded-xl border border-border-light bg-panel-light p-4 shadow-e1 transition duration-base hover:-translate-y-1 motion-reduce:hover:translate-y-0 hover:border-brand-strong hover:shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none dark:hover:border-brand-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      data-testid={`notable-filing-${filing.ticker}`}
    >
      <CompanyLogo ticker={filing.ticker} name={filing.company_name} size={40} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-text-primary-light dark:text-text-primary-dark">
            {filing.ticker}
          </span>
          <span className="truncate text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {filing.company_name}
          </span>
        </div>
        <div className="mt-1 text-xs uppercase tracking-wide text-text-secondary-light dark:text-text-secondary-dark">
          {filing.form}
          {ago ? ` • Filed ${ago}` : ''}
        </div>
      </div>
      <Badge variant="neutral">{filing.reason_label}</Badge>
    </Link>
  )
}
