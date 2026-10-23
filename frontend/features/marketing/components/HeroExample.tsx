import { format, parseISO } from 'date-fns'
import ExampleCtaLink from '@/features/marketing/components/ExampleCtaLink'
import CompanyLogo from '@/components/CompanyLogo'
import { Badge } from '@/components/ui/Badge'
import { EnRef, MarkedCopy, cx, markedBlockInsetClass, markedRowInsetClass } from '@/components/ui'
import { ArrowRightIcon, ArrowSquareOutIcon, CheckCircleIcon, QuotesIcon } from '@/lib/icons'
import { exampleFilingHref } from '@/lib/featureFlags'
import { directionOf, directionText } from '@/lib/financialTone'
import { Sep } from '@/features/filings/components/FilingIdentity'
import { sourceTraceChipClass } from '@/features/filings/lib/sourceTraceChip'
import { PASSAGE_FOUND } from '@/features/filings/lib/evidenceLabels'
import { excerptHeadings } from '@/features/summaries/lib/riskTitle'
import { AAPL_FY25_EDGAR_URL } from '@/features/marketing/lib/landing-samples'
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
 * back to a verified static snapshot of Apple's FY 2025 10-K (filed 2025-10-31; figures checked
 * against the filing's XBRL on 2026-10-11, docs/brand/00-audit.md §4), which has no evidence row:
 * its excerpt is not located here.
 *
 * The evidence row is the brand device at work (DESIGN.md › Graphic device): the filing's words in
 * the filing's face inside a marked block, with a bracketed marker whose twin sits in the margin.
 */

// Static fallback — every value verified against Apple's FY 2025 10-K XBRL.
const FALLBACK: ExampleData = {
  filingId: 0,
  ticker: 'AAPL',
  companyName: 'Apple Inc.',
  filingType: '10-K',
  filingDate: '2025-10-31',
  secUrl: AAPL_FY25_EDGAR_URL,
  excerpt:
    'Total net sales rose 6.4% to $416.2B with net income of $112.0B and diluted EPS of $7.46, while operating cash flow declined to $111.5B from $118.3B.',
  qualityTier: null,
  metrics: [
    { label: 'Revenue', value: '$416.2B', deltaPercent: 6.4 },
    { label: 'Net income', value: '$112.0B', deltaPercent: 19.5 },
    { label: 'Diluted EPS', value: '$7.46', deltaPercent: 22.7 },
  ],
}

// XBRL concepts behind the fallback metrics: the receipt is text inside each term, visually hidden
// so every reader reaches it (the hover repeats it for a mouse). Only the fallback carries them: its
// values were checked against the XBRL by hand, while a live figure is the summary's own financial
// highlight, which the hero cannot vouch for as an XBRL match.
const FALLBACK_CONCEPTS: Record<string, string> = {
  Revenue: 'us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax',
  'Net income': 'us-gaap:NetIncomeLoss',
  'Diluted EPS': 'us-gaap:EarningsPerShareDiluted',
}

const formatDelta = (delta?: number | null): string | null => {
  if (delta === null || delta === undefined || !Number.isFinite(delta)) return null
  return `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%`
}

const INK = 'text-text-primary-light dark:text-text-primary-dark'
const MUTED = 'text-text-secondary-light dark:text-text-secondary-dark'
const HAIRLINE = 'border-border-light dark:border-white/10'
/** A fact of the identity line and the middot after it, one item of the wrapping line, spaced as the line is. */
const FACT = 'flex items-center gap-x-2'
const GLYPH = { up: '▲', down: '▼', flat: '' } as const
/** The evidence row's excerpt, cut on a word with an ellipsis: the chip links to the whole passage. */
const MAX_EXCERPT = 180

function clip(text: string): string {
  if (text.length <= MAX_EXCERPT) return text
  const cut = text.slice(0, MAX_EXCERPT)
  return `${cut.slice(0, cut.lastIndexOf(' ')).replace(/[\s.,;:]+$/, '')} …`
}

/**
 * One figure in the hairline strip: label, value, and its change, direction in a glyph, never colour alone. A figure
 * takes its own content as its width (flex-auto) in a row that wraps, so where the three do not fit side by side
 * (a phone under 200% text) a figure moves under the one before it rather than running into it, as the receipt
 * card's steps read down (lessons/frontend-check-brand-layouts-at-200-percent-text.md); in equal thirds, at 390px under 200% text
 * each value ran across its 81px cell into the next. A value wider than the whole strip breaks inside rather than
 * being cut. Its left and top edges are the strip's hairlines, which the strip clips where a figure starts a row or
 * sits on the first one, so a hairline only ever stands between two figures.
 */
function Figure({ metric, isFallback }: { metric: ExampleMetric; isFallback: boolean }) {
  const delta = formatDelta(metric.deltaPercent)
  const direction = directionOf(metric.deltaPercent)
  const concept = isFallback ? FALLBACK_CONCEPTS[metric.label] : undefined
  return (
    <div className={cx('min-w-0 flex-auto border-l border-t py-3 pl-3', HAIRLINE)} title={concept}>
      {/* relative: the receipt's sr-only span is absolutely positioned, and an overflow clip holds such a box
          only when the box's containing block is inside it. Without it the span sits at its static place past
          the truncated label, outside the clip, and at 390px and 200% text the third term's receipt widened
          the page by 5px (tests/e2e/reflow-200.spec.ts). */}
      <dt className={cx('relative truncate text-xs', MUTED)}>
        {metric.label}
        {concept && <span className="sr-only">, filed tag {concept}</span>}
      </dt>
      <dd className={cx('mt-1 break-words font-data text-sm font-semibold tabular-nums sm:text-base', INK)}>{metric.value}</dd>
      {delta && (
        <dd className={cx('mt-0.5 break-words font-data text-xs font-medium tabular-nums', directionText[direction])}>
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
  const filed = Number.isNaN(parsedDate.getTime())
    ? null
    : { day: format(parsedDate, 'MMM d,'), year: format(parsedDate, 'yyyy') }
  const evidence = data.evidence ?? null

  return (
    <section
      aria-label="Example summary"
      className="min-w-0 max-w-full rounded-xl border border-border-light bg-panel-light shadow-e2 dark:border-white/10 dark:bg-panel-dark dark:shadow-none"
    >
      <div className="flex flex-col gap-4 p-cap-5 sm:p-cap-6">
        <div className="flex items-center justify-between gap-3">
          <p className={cx('text-xs font-medium', MUTED)}>Example summary</p>
          {data.qualityTier === 'full' && (
            <Badge variant="brand" icon={<CheckCircleIcon className="h-3 w-3" aria-hidden="true" />}>
              Full summary
            </Badge>
          )}
          {data.qualityTier === 'partial' && <Badge variant="warning">Partial</Badge>}
        </div>

        {/* The filing's identity, as the filing page states it: company, then one data-face line. The line wraps
            between its facts, each middot held to the fact before it (FACT) so no line starts or stands with one;
            the form is one run; and the date moves under "filed" whole before it breaks, and then only after its
            day ("Oct 31," over "2025"). As one nowrap run, "filed Oct 31, 2025" took the page to 329px at 320px
            under 200% text (tests/e2e/reflow-200.spec.ts). */}
        <div className="flex min-w-0 flex-wrap items-center gap-x-2.5 gap-y-1">
          <CompanyLogo decorative ticker={data.ticker} name={data.companyName} size={24} priority />
          <span className={cx('min-w-0 break-words text-sm font-semibold', INK)}>{data.companyName}</span>
          <span className={cx('flex flex-wrap items-center gap-x-2 font-data text-xs tabular-nums', MUTED)}>
            <span className={FACT}>
              {data.ticker}
              <Sep />
            </span>
            <span className={FACT}>
              {/* The form is text in the data face, never a Badge (2026-10 critique P-04). */}
              <span className={cx('whitespace-nowrap font-semibold', INK)}>{data.filingType}</span>
              {filed && <Sep />}
            </span>
            {filed && (
              <span>
                filed{' '}
                <span className="inline-block">
                  <span className="whitespace-nowrap">{filed.day}</span> {filed.year}
                </span>
              </span>
            )}
          </span>
        </div>

        <p className={cx('text-sm leading-relaxed', MUTED)}>{data.excerpt}</p>

        {/* The filing's figures: one hairline strip, no boxes. The figures wrap inside it (Figure), and the strip clips
            what a figure draws where it starts a row (its left hairline and the 0.75rem after it, which the list's
            negative margin puts outside) and on the first row (its top hairline, under the strip's own). */}
        {data.metrics.length > 0 && (
          <div className={cx('overflow-hidden border-y', HAIRLINE)}>
            <dl className="-ml-[calc(0.75rem_+_1px)] -mt-px flex flex-wrap">
              {data.metrics.map((metric) => (
                <Figure key={metric.label} metric={metric} isFallback={isFallback} />
              ))}
            </dl>
          </div>
        )}

        {/* One evidence row, the filing page's own (P-03): the filing's words, located in its text, as
            a marked block in the filing's face with its margin twin (the brand device). */}
        {evidence && (
          <MarkedCopy>
            <div className={cx('flex flex-col gap-2', markedRowInsetClass)}>
              <p className={cx('text-sm font-semibold', INK)}>
                {excerptHeadings([evidence.excerpt])[0]}
                <EnRef label="[1]" />
              </p>
              {/* The filing's words, so they wear quotation marks; the closing one follows the ellipsis. */}
              <blockquote className={cx('en-marked py-2.5 font-editorial text-base leading-relaxed', markedBlockInsetClass, INK)}>
                “{clip(evidence.excerpt)}”
              </blockquote>
              {evidence.url && (
                <div>
                  <a href={evidence.url} target="_blank" rel="noopener noreferrer" className={sourceTraceChipClass()}>
                    <QuotesIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
                    {PASSAGE_FOUND}
                    <span className="sr-only"> (opens in a new tab)</span>
                  </a>
                </div>
              )}
            </div>
          </MarkedCopy>
        )}

        <a
          href={data.secUrl}
          target="_blank"
          rel="noopener noreferrer"
          className={cx(
            'inline-flex items-center gap-1 self-start rounded-sm font-data text-xs underline-offset-2 transition-colors duration-fast',
            'hover:text-brand-strong hover:underline dark:hover:text-brand-strong-dark',
            'focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark',
            MUTED,
          )}
        >
          <ArrowSquareOutIcon className="h-3 w-3 shrink-0" aria-hidden="true" />
          {/* Only the checked fallback says its figures came from the company's filed data; live figures are the
              summary's, so the link sends the reader to the filing to check them. A no-break space holds the
              middot to the word before it, so the line breaks only after it: at 1440px under 200% text the
              receipt's second line began with "·" (tests/e2e/reflow-200.spec.ts). */}
          {data.metrics.length === 0
            ? 'Source filing\u00a0· read on SEC.gov'
            : isFallback
              ? "Figures from the company's filed data\u00a0· check them on SEC.gov"
              : 'Source filing\u00a0· check the figures on SEC.gov'}
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
