import { format, parseISO } from 'date-fns'
import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui/Badge'
import { cx } from '@/components/ui'
import { ArrowRightIcon, ArrowSquareOutIcon, CheckCircleIcon, QuotesIcon } from '@/lib/icons'
import { exampleFilingHref } from '@/lib/featureFlags'
import { directionOf, directionText } from '@/lib/financialTone'
import { Sep } from '@/features/filings/components/FilingIdentity'
import { sourceTraceChipClass } from '@/features/filings/components/SourceTrace'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'
import { AAPL_FY22_EDGAR_URL } from '@/features/marketing/lib/landing-samples'
import type { ExampleData, ExampleMetric } from '@/lib/serverApi'

/**
 * Hero product visual (2026-10 critique, homepage 1d): the example IS the product, on one surface.
 * The filing's identity in the data face, the summary's opening, a hairline strip of the filing's
 * figures, and, when the live summary has one, one evidence row: a risk excerpt the server located
 * in the filing text, headed by its own opening clause, with its chip. No browser-frame mockup, no
 * card inside the card, no sparkle chip, no tinted call to action.
 *
 * When the pre-generated example summary is reachable it renders the REAL thing (fetched
 * server-side with hourly ISR), so the preview can never drift from what a click delivers. Falls
 * back to a verified static snapshot of Apple's FY 2022 10-K (filed 2022-10-28; figures checked
 * against the filing's XBRL), which has no evidence row: its excerpt is not verified here.
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

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'
const GLYPH = { up: '▲', down: '▼', flat: '' } as const
/** The evidence row's excerpt, cut on a word with an ellipsis: the chip links to the whole passage. */
const MAX_EXCERPT = 180

function clip(text: string): string {
  if (text.length <= MAX_EXCERPT) return text
  const cut = text.slice(0, MAX_EXCERPT)
  return `${cut.slice(0, cut.lastIndexOf(' ')).replace(/[\s.,;:]+$/, '')} …`
}

/** One figure in the hairline strip: label, value, and its change, direction in a glyph, never colour alone. */
function Figure({ metric, isFallback }: { metric: ExampleMetric; isFallback: boolean }) {
  const delta = formatDelta(metric.deltaPercent)
  const direction = directionOf(metric.deltaPercent)
  return (
    <div className="min-w-0 py-3 pl-3 first:pl-0" title={isFallback ? FALLBACK_CONCEPTS[metric.label] : 'Reported in the filing’s XBRL data'}>
      <dt className={cx('truncate text-xs', MUTED)}>{metric.label}</dt>
      <dd className={cx('mt-1 whitespace-nowrap font-data text-sm font-semibold tabular-nums sm:text-base', INK)}>{metric.value}</dd>
      {delta && (
        <dd className={cx('mt-0.5 whitespace-nowrap font-data text-xs font-medium tabular-nums', directionText[direction])}>
          {GLYPH[direction] && (
            <span aria-hidden="true" className="mr-1">
              {GLYPH[direction]}
            </span>
          )}
          {delta}
        </dd>
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
  const evidence = data.evidence ?? null

  return (
    <section
      aria-label="Example summary"
      className="min-w-0 max-w-full rounded-xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
    >
      <div className="flex flex-col gap-4 p-5 sm:p-6">
        <div className="flex items-center justify-between gap-3">
          <p className={cx('text-xs font-medium', MUTED)}>Example summary</p>
          {data.qualityTier === 'full' && (
            <Badge variant="brand" icon={<CheckCircleIcon className="h-3 w-3" aria-hidden="true" />}>
              Full summary
            </Badge>
          )}
          {data.qualityTier === 'partial' && <Badge variant="warning">Partial</Badge>}
        </div>

        {/* The filing's identity, as the filing page states it: company, then one data-face line. */}
        <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
          <CompanyLogo decorative ticker={data.ticker} name={data.companyName} size={24} priority />
          <span className={cx('min-w-0 break-words text-sm font-semibold', INK)}>{data.companyName}</span>
          <span className={cx('flex flex-wrap items-center gap-x-2 font-data text-xs tabular-nums', MUTED)}>
            <span>{data.ticker}</span>
            <Sep />
            {/* The form is text in the data face, never a Badge (2026-10 critique P-04). */}
            <span className={cx('font-semibold', INK)}>{data.filingType}</span>
            {filedLabel && (
              <>
                <Sep />
                <span className="whitespace-nowrap">filed {filedLabel}</span>
              </>
            )}
          </span>
        </div>

        <p className={cx('text-sm leading-relaxed', MUTED)}>{data.excerpt}</p>

        {/* The filing's figures: one hairline strip, no boxes. */}
        {data.metrics.length > 0 && (
          <dl className={cx('grid grid-cols-3 divide-x border-y', HAIRLINE, 'divide-border-light dark:divide-white/10')}>
            {data.metrics.map((metric) => (
              <Figure key={metric.label} metric={metric} isFallback={isFallback} />
            ))}
          </dl>
        )}

        {/* One evidence row, the filing page's own (P-03): the filing's words, located in its text. */}
        {evidence && (
          <div className="flex flex-col gap-2">
            <p className={cx('text-sm font-semibold', INK)}>{excerptHeadings([evidence.excerpt])[0]}</p>
            <blockquote className={cx('border-l-2 pl-3.5 text-sm leading-relaxed', HAIRLINE, MUTED)}>
              {clip(evidence.excerpt)}
            </blockquote>
            {evidence.url && (
              <div>
                <a href={evidence.url} target="_blank" rel="noopener noreferrer" className={sourceTraceChipClass()}>
                  <QuotesIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
                  Located in the filing
                  <span className="sr-only"> (opens in a new tab)</span>
                </a>
              </div>
            )}
          </div>
        )}

        <a
          href={data.secUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={cx(
            'inline-flex items-center gap-1 font-data text-xs underline-offset-2 transition-colors duration-fast',
            'hover:text-brand-strong hover:underline dark:hover:text-brand-strong-dark',
            MUTED,
          )}
        >
          <ArrowSquareOutIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
          {data.metrics.length > 0
            ? "Figures from the company's XBRL filing · verify on SEC EDGAR"
            : 'Source filing · read on SEC EDGAR'}
        </a>

        {/* Into the real example: a text link (the hero's primary action lives beside the headline). */}
        <ExampleCtaLink
          href={ctaHref}
          placement={ctaPlacement}
          className={cx(
            'group -ml-2 inline-flex h-9 items-center gap-1.5 self-start rounded-lg px-2 text-sm font-semibold',
            'text-brand-strong transition-colors duration-fast hover:bg-brand-weak',
            'focus-visible:outline-none focus-visible:shadow-ring-brand',
            'dark:text-brand-strong-dark dark:hover:bg-brand-weak-dark dark:focus-visible:shadow-ring-brand-dark',
          )}
        >
          {ctaLabel}
          <ArrowRightIcon
            className="h-3.5 w-3.5 shrink-0 transition-transform duration-fast group-hover:translate-x-0.5 motion-reduce:group-hover:translate-x-0"
            aria-hidden="true"
          />
        </ExampleCtaLink>
      </div>
    </section>
  )
}

export default HeroExample
