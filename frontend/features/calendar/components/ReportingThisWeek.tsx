import { formatCompanyName } from '@/lib/formatCompanyName'
import Link from 'next/link'
import CompanyLogo from '@/components/CompanyLogo'
import LandingRow from '@/features/marketing/components/LandingRow'
import { ArrowRightIcon } from '@/lib/icons'
import { ENABLE_CALENDAR } from '@/lib/featureFlags'
import type { ReportingThisWeekResponse } from '@/lib/serverApi'

const DAY_LABELS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'] as const

function dayLabel(isoDate: string): string {
  // earnings_date is a plain YYYY-MM-DD calendar date (already computed server-side
  // against America/New_York) — parse as UTC midnight purely to read the weekday,
  // no timezone-correct instant is needed.
  const idx = new Date(`${isoDate}T00:00:00Z`).getUTCDay()
  return DAY_LABELS[idx] ?? ''
}

function timeLabel(time: string | null): string | null {
  if (time === 'bmo') return 'Before open'
  if (time === 'amc') return 'After close'
  return null
}

/** "Tue · After close" / "Fri · Before open"; the day alone when the session is unknown. */
function whenLabel(isoDate: string, time: string | null): string {
  const day = dayLabel(isoDate)
  const session = timeLabel(time)
  return session ? `${day} · ${session}` : day
}

/**
 * Curated large-caps reporting earnings this week, a ruled row of the landing page (D-045): one hairline
 * line per company (its mark, ticker, name and when it reports), two across from 40rem at the reader's
 * text size, never the four-up grid of tiles the template skeleton had (T4). Renders nothing at all when
 * there's nothing to show (weekend, holiday, sparse week, upstream failure), so it takes no number among
 * the rows: the hero's "Popular companies" row already covers company discovery on every load, so an
 * empty section here would just be redundant clutter, never a gap.
 */
export default function ReportingThisWeek({
  data,
}: {
  data: ReportingThisWeekResponse | null
}) {
  const companies = data?.companies ?? []
  if (companies.length === 0) return null

  return (
    // Impression baseline for per-section CTR (homepage-sections review §3).
    <LandingRow id="reporting" title="Reporting this week" impression="reporting_this_week">
      <ul className="grid grid-cols-1 gap-x-10 border-t border-border-light dark:border-white/10 [@media(min-width:40rem)]:grid-cols-2">
        {companies.map((company) => (
          <li key={company.ticker} className="border-b border-border-light dark:border-white/10">
            {/* The ticker and its day share a line while both fit, and the day drops beneath the ticker when they
                do not (a phone under a 200% text setting); the name truncates on its own line. */}
            <Link
              href={`/company/${company.ticker}`}
              className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-3 transition-colors duration-fast hover:bg-white dark:hover:bg-white/5 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
              data-testid={`reporting-this-week-${company.ticker}`}
            >
              <CompanyLogo decorative ticker={company.ticker} name={formatCompanyName(company.name)} size={32} />
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-baseline justify-between gap-x-3">
                  <span className="font-data text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                    {company.ticker}
                  </span>
                  <span className="text-xs font-medium text-text-secondary-light dark:text-text-secondary-dark">
                    {whenLabel(company.earnings_date, company.time)}
                  </span>
                </span>
                <span className="block truncate text-xs text-text-secondary-light dark:text-text-secondary-dark">
                  {formatCompanyName(company.name)}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
      {ENABLE_CALENDAR && (
        <Link
          href="/calendar"
          className="mt-5 inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-brand-strong transition-colors duration-fast hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
        >
          View full calendar
          <ArrowRightIcon aria-hidden="true" className="h-4 w-4" />
        </Link>
      )}
    </LandingRow>
  )
}
