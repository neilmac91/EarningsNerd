'use client'

import Link from 'next/link'

import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui'
import { formatLocalDate } from '@/lib/format'
import type { NotableFiling } from '@/lib/serverApi'

/**
 * One notable filing, linking to the COMPANY page (not /filing/{id}): market-wide candidates
 * aren't ingested yet, so a filing deep-link would hit cold ingestion — the company page lists
 * the filing and offers the summary CTA on warmed ground.
 */
export default function NotableFilingCard({ filing }: { filing: NotableFiling }) {
  // The filed date as the Filing identity line states it ("filed Oct 20, 2026"), through the same helper. filed_date is
  // an EDGAR day with no time, so the card states that day and claims nothing finer. formatLocalDate reads it as a
  // calendar day in every time zone (parsed as a UTC instant it would show the day before to a reader west of UTC),
  // and it reads no clock, so the server render and hydration agree and the cached page never states a stale day.
  const filed = formatLocalDate(filing.filed_date, 'MMM d, yyyy')

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
      <CompanyLogo decorative ticker={filing.ticker} name={filing.company_name} size={40} />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {/* A ticker is data: the data face, as Reporting this week's and the hero's tickers are (DESIGN.md, Typography). */}
          <span className="font-data font-semibold text-text-primary-light dark:text-text-primary-dark">
            {filing.ticker}
          </span>
          <span className="truncate text-sm text-text-secondary-light dark:text-text-secondary-dark">
            {filing.company_name}
          </span>
        </div>
        <div className="mt-1 text-xs text-text-secondary-light dark:text-text-secondary-dark">
          {/* A form code is text in the data face, never an eyebrow chip (DESIGN.md › Chips), and one unbroken run, so
              it never breaks at its hyphen on the landing (tests/e2e/reflow-200.spec.ts reads every row's codes). The
              middot is the search rows' separator (FullTextSearch's Sep; DESIGN_SYSTEM.md, Filing identity): a no-break
              space keeps it to the code, so where the line wraps (a phone at 200% text) the dot stays on the code's
              line and no line starts with it, and assistive tech hears a comma in its place. */}
          <span className="whitespace-nowrap font-data text-text-primary-light dark:text-text-primary-dark">{filing.form}</span>
          {filed && (
            <>
              {'\u00a0'}
              <span aria-hidden="true">·</span>
              <span className="sr-only">,</span> filed {filed}
            </>
          )}
        </div>
        <div className="mt-2">
          {/* The label wraps where the card is narrow (a phone at 200% text), so the chip takes the 16px step, not
              Badge's full radius: a pill on one line, a rounded box once it wraps (DESIGN.md, Shapes). */}
          <Badge
            variant="neutral"
            className="max-w-full justify-center !whitespace-normal !rounded-xl text-center leading-tight"
          >
            {filing.reason_label}
          </Badge>
        </div>
      </div>
    </Link>
  )
}
