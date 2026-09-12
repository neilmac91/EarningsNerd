import { formatCompanyName } from '@/lib/formatCompanyName'
import Link from 'next/link'
import CompanyLogo from '@/components/CompanyLogo'
import SectionImpression from '@/features/marketing/components/SectionImpression'
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
 * Curated large-caps reporting earnings this week. Renders nothing at all when
 * there's nothing to show (weekend, holiday, sparse week, upstream failure) — the
 * hero's "Popular companies" row already covers company discovery on every load,
 * so an empty section here would just be redundant clutter, never a gap.
 */
export default function ReportingThisWeek({
  data,
}: {
  data: ReportingThisWeekResponse | null
}) {
  const companies = data?.companies ?? []
  if (companies.length === 0) return null

  return (
    <section
      id="reporting"
      aria-labelledby="reporting-h"
      className="border-t border-border-light py-20 dark:border-white/10 sm:py-24"
    >
      <div className="mx-auto max-w-5xl px-4 sm:px-6 lg:px-8">
        {/* Impression baseline for per-section CTR (homepage-sections review §3). */}
        <SectionImpression section="reporting_this_week">
          <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
            <h2 id="reporting-h" className="text-2xl">
              Reporting this week
            </h2>
            {ENABLE_CALENDAR && (
              <Link
                href="/calendar"
                className="inline-flex items-center gap-1.5 rounded-sm text-sm font-medium text-brand-strong transition-colors duration-fast hover:text-brand-emphasis dark:text-brand-strong-dark dark:hover:text-brand-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
              >
                View full calendar
                <ArrowRightIcon aria-hidden="true" className="h-4 w-4" />
              </Link>
            )}
          </div>
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
            {companies.map((company) => (
              <Link
                key={company.ticker}
                href={`/company/${company.ticker}`}
                className="flex flex-col items-center gap-2 rounded-xl border border-border-light bg-panel-light p-4 text-center shadow-e1 transition-colors duration-fast hover:border-brand-border hover:bg-white dark:border-white/10 dark:bg-panel-dark dark:shadow-none dark:hover:border-brand-border-dark dark:hover:bg-white/10 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
                data-testid={`reporting-this-week-${company.ticker}`}
              >
                <CompanyLogo ticker={company.ticker} name={formatCompanyName(company.name)} size={40} />
                <div className="font-data font-semibold text-text-primary-light dark:text-text-primary-dark">
                  {company.ticker}
                </div>
                <div className="w-full truncate text-xs text-text-secondary-light dark:text-text-secondary-dark">
                  {formatCompanyName(company.name)}
                </div>
                <div className="mt-1 inline-flex items-center rounded-full border border-border-light px-2 py-0.5 text-xs font-medium text-text-secondary-light dark:border-white/10 dark:text-text-secondary-dark">
                  {whenLabel(company.earnings_date, company.time)}
                </div>
              </Link>
            ))}
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}
