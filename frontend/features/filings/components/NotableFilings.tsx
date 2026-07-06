import NotableFilingCard from '@/features/filings/components/NotableFilingCard'
import SectionImpression from '@/features/marketing/components/SectionImpression'
import type { NotableFilingsResponse } from '@/lib/serverApi'

/**
 * Market-wide notable SEC filings from the past week (EDGAR-native; replaces the retired
 * "Trending Filings" section — tasks/homepage-sections-review-findings.md). Renders nothing at
 * all when there's nothing honest to show: the backend already enforces the contract (flag off,
 * fewer than 3 distinct companies in the 7-day window, or upstream failure → empty list), and a
 * sparse section on a sales surface is worse than absence (ReportingThisWeek precedent).
 */
export default function NotableFilings({
  data,
}: {
  data: NotableFilingsResponse | null
}) {
  const filings = data?.filings ?? []
  if (filings.length === 0) return null

  return (
    <section id="notable-filings" className="py-20 sm:py-24">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <SectionImpression section="notable_filings">
          <div className="mb-8">
            <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-text-primary-light dark:text-text-primary-dark">
              <span aria-hidden="true">📄</span> Notable filings
            </h2>
            <p className="mt-1 text-sm text-text-secondary-light dark:text-text-secondary-dark">
              High-signal SEC filings from the past week, across the whole market — sourced from
              EDGAR.
            </p>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {filings.map((filing) => (
              <NotableFilingCard key={`${filing.ticker}-${filing.filed_date}`} filing={filing} />
            ))}
          </div>
        </SectionImpression>
      </div>
    </section>
  )
}
