'use client'

import Link from 'next/link'
import { formatDistanceToNowStrict } from 'date-fns'

import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui'
import type { NotableFiling } from '@/lib/serverApi'

function filedAgo(isoDate: string): string | null {
  // filed_date is a plain YYYY-MM-DD EDGAR calendar day — anchor at UTC noon so the relative
  // label can't slip a day in extreme viewer timezones.
  try {
    return formatDistanceToNowStrict(new Date(`${isoDate}T12:00:00Z`), { addSuffix: true })
  } catch {
    return null
  }
}

/**
 * One notable filing, linking to the COMPANY page (not /filing/{id}): market-wide candidates
 * aren't ingested yet, so a filing deep-link would hit cold ingestion — the company page lists
 * the filing and offers the summary CTA on warmed ground.
 */
export default function NotableFilingCard({ filing }: { filing: NotableFiling }) {
  const ago = filedAgo(filing.filed_date)

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
