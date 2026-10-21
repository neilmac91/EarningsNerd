'use client'

import Link from 'next/link'

import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui'
import { diffDays, todayEasternIso } from '@/features/calendar/lib/dates'
import type { NotableFiling } from '@/lib/serverApi'

/**
 * When the filing was filed, in whole New York calendar days: "today", "yesterday" or "N days ago". `filed_date` is a
 * plain YYYY-MM-DD EDGAR day with no time, so the label claims no more than a day. It counts from the New York day of
 * the response's timestamp, the day the backend's window counts its week from (`today_eastern()`), so a card never
 * disagrees with the week the row promises: the window's oldest filing reads "7 days ago". A filing dated after that
 * day (bad data) or a timestamp that does not parse gets no label, never a future or a sub-day value.
 *
 * Measured against the response's own timestamp, NEVER the live clock. This is a client component server-rendered
 * into an ISR page: `/` is cached for up to an hour, so HTML generated before midnight and hydrated after it would
 * render one day on the server and the next in the browser, a hydration mismatch and a visible text swap. Anchoring
 * both passes to `asOf` makes the label a property of the data, which is what an ISR snapshot actually shows.
 */
function filedDay(isoDate: string, asOf: string): string | null {
  const asOfDate = new Date(asOf)
  if (Number.isNaN(asOfDate.getTime()) || !/^\d{4}-\d{2}-\d{2}$/.test(isoDate)) return null
  const days = diffDays(isoDate, todayEasternIso(asOfDate))
  if (!Number.isFinite(days) || days < 0) return null
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  return `${days} days ago`
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
  const filed = filedDay(filing.filed_date, asOf)

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
              <span className="sr-only">,</span> Filed {filed}
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
