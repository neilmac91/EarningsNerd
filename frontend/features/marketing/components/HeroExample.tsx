import { format, parseISO } from 'date-fns'
import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui/Badge'
import { ArrowRightIcon, ArrowSquareOutIcon, CheckCircleIcon, SparkleIcon, TrendDownIcon, TrendUpIcon } from '@/lib/icons'
import { exampleFilingHref } from '@/lib/featureFlags'
import { directionText } from '@/lib/financialTone'
import { AAPL_FY22_EDGAR_URL } from '@/features/marketing/lib/landing-samples'
import type { ExampleData, ExampleMetric } from '@/lib/serverApi'

/**
 * Hero product visual. When the pre-generated example summary is reachable it
 * renders the REAL thing (excerpt, metrics, quality verdict — fetched
 * server-side with hourly ISR), so the preview can never drift from what a
 * click delivers. Falls back to a verified static snapshot of Apple's FY 2022
 * 10-K (filed 2022-10-28; figures checked against the filing's XBRL).
 */

// Static fallback — every value verified against Apple's FY 2022 10-K XBRL.
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

// Inside-card eyebrow register (11px uppercase tracked, tertiary on the white field surface).
const EYEBROW =
  'text-[11px] font-semibold uppercase tracking-[0.08em] text-text-tertiary-light dark:text-text-secondary-dark'

function MetricCell({ metric, isFallback }: { metric: ExampleMetric; isFallback: boolean }) {
  const delta = formatDelta(metric.deltaPercent)
  const up = (metric.deltaPercent ?? 0) >= 0
  const DeltaIcon = up ? TrendUpIcon : TrendDownIcon
  return (
    <div
      className="min-w-0 rounded-lg border border-border-light bg-white p-3 transition-colors duration-fast hover:border-brand-border dark:border-white/10 dark:bg-white/5 dark:hover:border-brand-border-dark"
      title={isFallback ? FALLBACK_CONCEPTS[metric.label] : 'Reported in the filing’s XBRL data'}
    >
      <div className={`truncate ${EYEBROW}`}>{metric.label}</div>
      <div className="tnum mt-1 whitespace-nowrap font-data text-sm font-semibold text-text-primary-light dark:text-text-primary-dark sm:text-base">
        {metric.value}
      </div>
      {delta && (
        <div className={`tnum mt-0.5 flex items-center gap-0.5 font-data text-xs font-medium ${directionText[up ? 'up' : 'down']}`}>
          <DeltaIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
          {delta}
        </div>
      )}
    </div>
  )
}

interface HeroExampleProps {
  example: ExampleData | null
  ctaHref?: string
  ctaPlacement?: string
  ctaLabel?: string
}

function HeroExample({
  example,
  ctaHref = exampleFilingHref('hero_visual_example'),
  ctaPlacement = 'hero_visual',
  ctaLabel = 'Read the full example summary',
}: HeroExampleProps) {
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
    <div className="relative min-w-0 max-w-full">
      {/* Browser frame: panel + hairline + e3 (DS §7); no title-bar dots, no ambient glow. */}
      <div className="mockup-frame relative shadow-e3 dark:shadow-none">
        {/* Title bar: the summary's address + the "AI summary" chip (sparkle lives ONLY here, DS §4). */}
        <div className="mockup-frame-titlebar flex flex-wrap items-center justify-between gap-x-2 gap-y-1.5 px-4 py-2.5">
          <span className="min-w-0 truncate font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
            {isFallback ? 'earningsnerd.io · example summary' : `earningsnerd.io/filing/${data.filingId}`}
          </span>
          <Badge variant="brand" icon={<SparkleIcon className="h-3 w-3" aria-hidden="true" />}>
            AI summary
          </Badge>
        </div>

        {/* Page content */}
        <div className="flex flex-col gap-3.5 p-4 sm:p-5">
          {/* Header area */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <CompanyLogo ticker={data.ticker} name={data.companyName} size={24} priority />
              <span className="min-w-0 break-words text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
                {data.companyName}
              </span>
              <span className="font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">{data.ticker}</span>
              <Badge variant="neutral">{data.filingType}</Badge>
              {data.qualityTier === 'full' && (
                <Badge variant="brand" icon={<CheckCircleIcon className="h-3 w-3" aria-hidden="true" />}>
                  Full summary
                </Badge>
              )}
              {data.qualityTier === 'partial' && <Badge variant="warning">Partial</Badge>}
            </div>
            {filedLabel && (
              <span className="tnum whitespace-nowrap font-data text-xs text-text-secondary-light dark:text-text-secondary-dark">
                filed {filedLabel}
              </span>
            )}
          </div>

          {/* Executive snapshot — real summary text */}
          <div className="rounded-lg border border-border-light bg-white p-4 dark:border-white/10 dark:bg-white/5">
            <div className={`mb-2 ${EYEBROW}`}>Executive snapshot</div>
            <p className="text-[13px] leading-relaxed text-text-secondary-light dark:text-text-secondary-dark">{data.excerpt}</p>
          </div>

          {/* Metrics — with the receipt: where the numbers come from */}
          {data.metrics.length > 0 && (
            <div className="grid grid-cols-3 gap-2.5">
              {data.metrics.map((metric) => (
                <MetricCell key={metric.label} metric={metric} isFallback={isFallback} />
              ))}
            </div>
          )}
          <a
            href={data.secUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 font-data text-[11px] text-text-secondary-light underline-offset-2 transition-colors duration-fast hover:text-brand-strong hover:underline dark:text-text-secondary-dark dark:hover:text-brand-strong-dark"
          >
            <ArrowSquareOutIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
            {data.metrics.length > 0
              ? "Figures from the company's XBRL filing · verify on SEC EDGAR"
              : 'Source filing · read on SEC EDGAR'}
          </a>

          {/* Footer CTA into the real example */}
          <ExampleCtaLink
            href={ctaHref}
            placement={ctaPlacement}
            className="group flex items-center justify-between gap-2 rounded-lg border border-brand-border bg-brand-weak px-4 py-3 transition-colors duration-fast hover:border-brand-strong dark:border-brand-border-dark dark:bg-brand-weak-dark dark:hover:border-brand-dark focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
          >
            <span className="text-[13px] font-semibold text-brand-strong dark:text-brand-strong-dark">{ctaLabel}</span>
            <ArrowRightIcon
              className="h-3.5 w-3.5 shrink-0 text-brand-strong transition-transform duration-fast group-hover:translate-x-0.5 motion-reduce:group-hover:translate-x-0 dark:text-brand-strong-dark"
              aria-hidden="true"
            />
          </ExampleCtaLink>
        </div>
      </div>
    </div>
  )
}

export default HeroExample
