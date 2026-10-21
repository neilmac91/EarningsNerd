'use client'

import Link from 'next/link'

import analytics from '@/lib/analytics'
import CompanyLogo from '@/components/CompanyLogo'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { formatLocalDate } from '@/lib/format'
import type { NotableFiling } from '@/lib/serverApi'

/**
 * One notable filing as one hairline line, in Reporting this week's anatomy (ReportingThisWeek.tsx): the two rows sit
 * one above the other, both list companies and both open the company page, so they read as one system and their
 * titles and lines tell them apart. The mark at 32; the ticker in the data face, with the form and its filed date where
 * Reporting this week has its day, sharing the line while both fit and dropping beneath the ticker when they do not;
 * the company's name beneath, truncating. The list's hairlines are the row's (NotableFilings.tsx), and every class here
 * is Reporting this week's, held to it by tests/unit/NotableFilings.spec.tsx's parity case.
 *
 * It links to the COMPANY page (not /filing/{id}): market-wide candidates aren't ingested yet, so a filing deep-link
 * would hit cold ingestion; the company page lists the filing and offers the summary CTA on warmed ground.
 */
export default function NotableFilingLine({ filing }: { filing: NotableFiling }) {
  // EDGAR's display name often arrives in capitals ("SAMPLE INDUSTRIES A INC"), so the line and the mark print it as
  // Reporting this week, the Filing identity line and the company page do, through formatCompanyName. The analytics
  // event carries no name.
  const name = formatCompanyName(filing.company_name)
  // The filed date as the Filing identity line states it ("filed Oct 20, 2026"), through the same helper: filed_date is
  // an EDGAR day with no time, so the line states that day and claims nothing finer, the same in every time zone, and
  // reads no clock, so the server render and hydration agree. The day and the year come apart only so that "Oct 20,"
  // stays one run.
  const day = formatLocalDate(filing.filed_date, 'MMM d,')
  const year = formatLocalDate(filing.filed_date, 'yyyy')

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
      className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-3 transition-colors duration-fast hover:bg-white dark:hover:bg-white/5 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      data-testid={`notable-filing-${filing.ticker}`}
    >
      <CompanyLogo decorative ticker={filing.ticker} name={name} size={32} />
      <span className="min-w-0 flex-1">
        <span className="flex flex-wrap items-baseline justify-between gap-x-3">
          {/* A ticker is data: the data face, as Reporting this week's and the hero's tickers are (DESIGN.md, Typography). */}
          <span className="font-data text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            {filing.ticker}
          </span>
          {/* A form code is text in the data face, never an eyebrow chip (DESIGN.md › Chips), and one unbroken run, so
              it never breaks at its hyphen on the landing (tests/unit/NotableFilings.spec.tsx holds it: reflow-200 reads
              only the rows that paint, and CI's run, with no backend, paints none of these lines). The middot is the
              search rows' separator (FullTextSearch's Sep; DESIGN_SYSTEM.md, Filing identity): a no-break
              space keeps it to the code, so the dot stays on the code's line and no line starts with it, and assistive
              tech hears a comma in its place. The date is one inline block after "filed", as the hero's identity line
              holds its date (HeroExample.tsx): it moves under the code whole before it breaks, and then only after its
              day, so "Oct 20," is one run and no line reads "filed Oct" over "20, 2026". */}
          <span className="text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">
            <span className="whitespace-nowrap font-data text-text-primary-light dark:text-text-primary-dark">{filing.form}</span>
            {day && year && (
              <>
                {'\u00a0'}
                <span aria-hidden="true">·</span>
                <span className="sr-only">,</span> filed{' '}
                <span className="inline-block">
                  <span className="whitespace-nowrap">{day}</span> {year}
                </span>
              </>
            )}
          </span>
        </span>
        <span className="block truncate text-xs text-text-secondary-light dark:text-text-secondary-dark">{name}</span>
      </span>
    </Link>
  )
}
