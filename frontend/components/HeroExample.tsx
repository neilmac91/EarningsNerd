import { format, parseISO } from 'date-fns'
import ExampleCtaLink from '@/components/ExampleCtaLink'
import CompanyLogo from '@/components/CompanyLogo'
import { exampleFilingHref } from '@/lib/featureFlags'
import { directionText } from '@/lib/financialTone'
import type { ExampleData, ExampleMetric } from '@/lib/serverApi'

/**
 * Hero product visual. When the pre-generated example summary is reachable it
 * renders the REAL thing (excerpt, metrics, quality verdict — fetched
 * server-side with hourly ISR), so the preview can never drift from what a
 * click delivers. Falls back to a verified static snapshot of Apple's FY 2022
 * 10-K (filed 2022-10-28; figures checked against the filing's XBRL).
 */

// Static fallback — every value verified against Apple's FY 2022 10-K XBRL.
const AAPL_FY22_EDGAR_URL =
  'https://www.sec.gov/Archives/edgar/data/320193/000032019322000108/'

const FALLBACK: ExampleData = {
  filingId: 0,
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  filingType: '10-K',
  filingDate: '2022-10-28',
  secUrl: AAPL_FY22_EDGAR_URL,
  excerpt:
    'Net sales rose 8% to $394.3B, led by iPhone and Services growth. Gross margin expanded to 43.3%, and operating cash flow reached a record $122.2B.',
  qualityTier: null,
  metrics: [
    { label: 'Revenue', value: '$394.3B', deltaPercent: 7.8 },
    { label: 'Net Income', value: '$99.8B', deltaPercent: 5.4 },
    { label: 'Diluted EPS', value: '$6.11', deltaPercent: 8.9 },
  ],
}

// XBRL concepts behind the fallback metrics (shown as hover receipts).
const FALLBACK_CONCEPTS: Record<string, string> = {
  Revenue: 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
  'Net Income': 'us-gaap:NetIncomeLoss',
  'Diluted EPS': 'us-gaap:EarningsPerShareDiluted',
}

const formatDelta = (delta?: number | null): string | null => {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return null
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%`
}

function MetricCell({ metric, isFallback }: { metric: ExampleMetric; isFallback: boolean }) {
  const delta = formatDelta(metric.deltaPercent)
  return (
    <div
      className="rounded-lg border border-border-light dark:border-white/10 bg-white dark:bg-white/5 p-3"
      title={isFallback ? FALLBACK_CONCEPTS[metric.label] : 'Reported in the filing’s XBRL data'}
    >
      <div className="text-xs text-text-secondary-light dark:text-text-secondary-dark">{metric.label}</div>
      <div className="mt-1 text-sm font-semibold tabular-nums text-text-primary-light dark:text-text-primary-dark">{metric.value}</div>
      {delta && (
        <div
          className={`mt-0.5 text-xs font-medium tabular-nums ${
            directionText[(metric.deltaPercent ?? 0) >= 0 ? 'up' : 'down']
          }`}
        >
          {delta}
        </div>
      )}
    </div>
  )
}

function HeroExample({ example }: { example: ExampleData | null }) {
  const data = example ?? FALLBACK
  const isFallback = example === null
  // Parse the calendar date only — `new Date('2022-10-28')` is UTC midnight
  // and renders the previous day in negative-offset timezones. Guard against
  // a malformed upstream date: format() throws on invalid dates, which would
  // crash the homepage render; omit the label instead.
  const parsedDate = parseISO(data.filingDate.slice(0, 10))
  const filedLabel = Number.isNaN(parsedDate.getTime())
    ? null
    : format(parsedDate, 'MMM d, yyyy')

  return (
    <div className="relative">
      {/* Browser frame — no ambient glow: DS §7, the only glow is the hero search. */}
      <div className="mockup-frame relative shadow-e5 dark:shadow-none">
        {/* Title bar */}
        <div className="mockup-frame-titlebar flex items-center gap-2 px-4 py-3">
          <div className="flex gap-1.5" aria-hidden="true">
            <span className="h-3 w-3 rounded-full bg-red-500/70" />
            <span className="h-3 w-3 rounded-full bg-yellow-500/70" />
            <span className="h-3 w-3 rounded-full bg-green-500/70" />
          </div>
          <div className="mx-auto flex-1 max-w-xs">
            <div className="rounded border border-border-light dark:border-white/10 bg-white dark:bg-white/5 px-3 py-1 text-center font-mono text-xs text-text-secondary-light dark:text-text-secondary-dark">
              earningsnerd.io — example summary
            </div>
          </div>
        </div>

        {/* Page content */}
        <div className="space-y-4 p-5">
          {/* Header area */}
          <div className="flex items-center justify-between gap-2">
            <div className="flex min-w-0 items-center gap-2">
              <CompanyLogo ticker={data.ticker} name={data.companyName} size={24} priority />
              <span className="truncate text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{data.companyName}</span>
              <span className="flex-shrink-0 rounded-full border border-border-light dark:border-white/10 bg-white dark:bg-white/10 px-2 py-0.5 text-xs text-text-secondary-light dark:text-text-secondary-dark">
                {data.filingType}
              </span>
              {data.qualityTier === 'full' && (
                <span className="flex-shrink-0 rounded-full border border-brand-strong/25 dark:border-brand-dark/30 bg-brand-strong/10 dark:bg-brand-dark/15 px-2 py-0.5 text-xs font-medium text-brand-strong dark:text-brand-strong-dark">
                  Full summary
                </span>
              )}
              {data.qualityTier === 'partial' && (
                <span className="flex-shrink-0 rounded-full border border-warning-light/30 dark:border-warning-dark/30 bg-warning-light/10 dark:bg-warning-dark/10 px-2 py-0.5 text-xs font-medium text-warning-light dark:text-warning-dark">
                  Partial
                </span>
              )}
            </div>
            {filedLabel && (
              <span className="flex-shrink-0 font-mono text-xs tabular-nums text-text-secondary-light dark:text-text-secondary-dark">
                filed {filedLabel}
              </span>
            )}
          </div>

          {/* Executive snapshot — real summary text */}
          <div className="rounded-xl border border-border-light dark:border-white/10 bg-white dark:bg-white/5 p-4">
            <div className="mb-2 flex items-center gap-2">
              <div className="h-1.5 w-1.5 rounded-full bg-brand-strong dark:bg-brand-dark" aria-hidden="true" />
              <span className="text-xs font-semibold uppercase tracking-wider text-brand-strong dark:text-brand-strong-dark">
                Executive Snapshot
              </span>
            </div>
            <p className="text-xs leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">{data.excerpt}</p>
          </div>

          {/* Metrics — with the receipt: where the numbers come from */}
          {data.metrics.length > 0 && (
            <div>
              <div className="grid grid-cols-3 gap-3">
                {data.metrics.map((metric) => (
                  <MetricCell key={metric.label} metric={metric} isFallback={isFallback} />
                ))}
              </div>
              <a
                href={data.secUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="mt-2 inline-flex items-center gap-1 font-mono text-[11px] text-text-tertiary-light dark:text-text-secondary-dark underline-offset-2 transition-colors hover:text-brand-strong dark:hover:text-brand-strong-dark hover:underline"
              >
                Figures from the company&apos;s XBRL filing · verify on SEC EDGAR ↗
              </a>
            </div>
          )}

          {/* Footer CTA into the real example */}
          <ExampleCtaLink
            href={exampleFilingHref('hero_visual_example')}
            placement="hero_visual"
            className="group flex items-center justify-between rounded-xl border border-brand-strong/25 dark:border-brand-dark/30 bg-brand-strong/10 dark:bg-brand-dark/15 px-4 py-3 transition-colors hover:border-brand-strong/40 dark:hover:border-brand-dark/40 hover:bg-brand-strong/15 dark:hover:bg-brand-dark/20 focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          >
            <span className="text-xs font-medium text-brand-strong dark:text-brand-strong-dark">
              Read the full example summary
            </span>
            <span
              className="text-xs text-brand-strong dark:text-brand-strong-dark transition-transform group-hover:translate-x-0.5"
              aria-hidden="true"
            >
              →
            </span>
          </ExampleCtaLink>
        </div>
      </div>
    </div>
  )
}

export default HeroExample
