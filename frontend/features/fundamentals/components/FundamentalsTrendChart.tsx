'use client'
/**
 * Financial trends on the filing page: one metric's annual figures as reported in this filing, drawn through the trend
 * charts' engine as /analysis draws its charts (E195 (D), D-067): `buildBarChart` models the active series, the frame
 * lays it out at the card's measured width and the spec renderer paints it, so the plot is 320 px with 11 px ticks, every
 * metric is chart-1, every value is printed on its bar (A4), a withheld year prints "—" in its slot, and one values stop
 * reads a year at a time beside the column-wash tooltip, which marks a derived figure "· Calculated"
 * (docs/design/analysis-trend-charts-spec-2026-10.md §0.5; DESIGN_SYSTEM.md §10). The card's own chrome stays: the
 * heading and its source-check badge, the subtitle, the metric picker, the footnote and Sources & checks.
 */
import { useContext, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'
import {
  getFilingFundamentals,
  type FundamentalPoint,
  type FundamentalsResponse,
} from '@/features/fundamentals/api/fundamentals-api'
import { ApiError } from '@/lib/api/client'
import { ThemeContext } from '@/components/ThemeProvider'
import { Card, Skeleton, inputClasses } from '@/components/ui'
import ChartPlotFrame from '@/features/analysis/components/ChartPlotFrame'
import SourceChecks from '@/features/analysis/components/SourceChecks'
import { useChartFont } from '@/features/analysis/components/useChartFont'
import { buildBarChart, unitCurrency, type BarAxis, type BarCategory } from '@/features/analysis/lib/charts/barChart'
import { CARD_HEIGHT } from '@/features/analysis/lib/charts/layout'
import { periodHeader, readouts } from '@/features/analysis/lib/charts/readout'
import { chartTokens } from '@/features/analysis/lib/charts/theme'
import { needsSourceCheck } from '@/features/analysis/lib/provenance'
import SourceCheckBadge from '@/features/fundamentals/components/SourceCheckBadge'

type FmtKind = 'usd' | 'eps' | 'pct' | 'ratio'

// Curated, ordered set of concepts to offer (only those present in the response are shown).
// `concept` keys match the backend's standardized vocabulary (facts_service._CONCEPT_UNITS). Each label is stored in
// sentence case, as the picker, the tooltip, the values stop, the footnote and the source checks show it (E34).
const FEATURED: { key: string; label: string; fmt: FmtKind }[] = [
  { key: 'revenue', label: 'Revenue', fmt: 'usd' },
  // Financial-institution revenue lines (only present for banks/insurers/BDCs — a bank shows these
  // instead of a single Revenue; insurers add these alongside their reported total revenue).
  { key: 'net_interest_income', label: 'Net interest income', fmt: 'usd' },
  { key: 'noninterest_income', label: 'Non-interest income', fmt: 'usd' },
  { key: 'premiums_earned', label: 'Premiums earned', fmt: 'usd' },
  { key: 'net_investment_income', label: 'Net investment income', fmt: 'usd' },
  { key: 'net_income', label: 'Net income', fmt: 'usd' },
  { key: 'gross_profit', label: 'Gross profit', fmt: 'usd' },
  { key: 'operating_income', label: 'Operating income', fmt: 'usd' },
  { key: 'operating_cash_flow', label: 'Operating cash flow', fmt: 'usd' },
  { key: 'investing_cash_flow', label: 'Investing cash flow', fmt: 'usd' },
  { key: 'financing_cash_flow', label: 'Financing cash flow', fmt: 'usd' },
  { key: 'free_cash_flow', label: 'Free cash flow', fmt: 'usd' },
  { key: 'eps_diluted', label: 'Diluted EPS', fmt: 'eps' },
  { key: 'earnings_per_share', label: 'EPS', fmt: 'eps' },
  { key: 'gross_margin', label: 'Gross margin', fmt: 'pct' },
  { key: 'operating_margin', label: 'Operating margin', fmt: 'pct' },
  { key: 'net_margin', label: 'Net margin', fmt: 'pct' },
  { key: 'total_assets', label: 'Total assets', fmt: 'usd' },
  { key: 'current_assets', label: 'Current assets', fmt: 'usd' },
  { key: 'current_liabilities', label: 'Current liabilities', fmt: 'usd' },
  { key: 'working_capital', label: 'Working capital', fmt: 'usd' },
  { key: 'current_ratio', label: 'Current ratio', fmt: 'ratio' },
  { key: 'shareholders_equity', label: "Shareholders' equity", fmt: 'usd' },
]

/** What the plot says, at the card's height, for a metric whose every year is withheld (§3.4: a chart that does not apply
 *  keeps its card and says why). */
const NO_FIGURES = 'No multi-year data available for this metric.'
/** Where A4 finds no label tier even at the widest slot (an amount in thousands of trillions of won, on a phone), the bars
 *  print no values and the card says so. Not the analysis card's VALUES_DONT_FIT: no metrics table on the filing page
 *  lists this series' years, so the line stops at what is true. */
const VALUES_DONT_FIT_HERE = 'Values don’t fit at this width.'

/** The value axis a metric takes: an amount in its series' XBRL unit, whose currency the engine prints (CNY, never "$";
 *  "USD/shares" is a per-share amount, in cents), a margin in percentage points, or a multiple. */
const axisOf = (fmt: FmtKind, unit: string): BarAxis =>
  fmt === 'pct' ? { kind: 'percent' } : fmt === 'ratio' ? { kind: 'ratio' } : { kind: 'money', unit }

/** Each point's slot: its fiscal year names it ("FY2025", ticked "2025"), and a point the backend names no year for
 *  takes its period end's year, as the axis has always ticked it. The engine places a bar and reads a year by its key,
 *  so a key is never given twice (buildBarChart refuses it): a name two points share keys each by its place. */
function slotsOf(points: FundamentalPoint[]): BarCategory[] {
  const names = points.map((point) => (point.fiscal_year != null ? `FY${point.fiscal_year}` : point.period_end?.slice(0, 4) ?? ''))
  return points.map((point, i) => {
    const name = names[i]
    const own = name !== '' && names.indexOf(name) === names.lastIndexOf(name)
    return {
      key: own ? name : `${name || 'period'}#${i}`,
      tick: point.fiscal_year != null ? String(point.fiscal_year) : name,
      long: name || 'Period unavailable',
    }
  })
}

export default function FundamentalsTrendChart({
  filingId,
  subtitle,
}: {
  // Filing-scoped (roadmap B): the multi-year figures *as reported in this specific filing* — an
  // immutable snapshot faithful to the document, not the company's accumulated latest series.
  filingId: number
  // Optional context line under the heading (the filing page passes one to frame the source).
  subtitle?: string
}) {
  // The chart's inks are SVG attributes, not classes: the theme comes off the context (not useTheme), with a light
  // fallback, so a render without a provider (tests) never throws.
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const tokens = chartTokens(dark)
  const fontReady = useChartFont()

  const { data, isLoading, isError } = useQuery<FundamentalsResponse>({
    queryKey: queryKeys.filingFundamentals(filingId),
    queryFn: () => getFilingFundamentals(filingId),
    retry: (failureCount, err) =>
      err instanceof ApiError && err.isRetryable ? failureCount < 2 : false,
    staleTime: 60 * 60 * 1000, // facts change only with new filings (filing-scoped is immutable)
    gcTime: 2 * 60 * 60 * 1000,
  })

  // The concepts actually available for this company, in our curated order.
  const available = useMemo(() => {
    const present = new Set((data?.concepts ?? []).map((c) => c.concept))
    return FEATURED.filter((f) => present.has(f.key))
  }, [data])

  const [selected, setSelected] = useState<string | null>(null)
  const activeKey = selected && available.some((a) => a.key === selected)
    ? selected
    : available[0]?.key ?? null
  const active = FEATURED.find((f) => f.key === activeKey)
  const series = data?.concepts.find((c) => c.concept === activeKey)

  // The active series as the engine's bar chart: a slot per year the filing reports, withheld years included.
  const chart = useMemo(() => {
    if (!active || !series) return null
    const slots = slotsOf(series.points)
    const model = buildBarChart({
      id: 'financial-trends',
      // The plot announces "{title} chart", and its values stop "{title} chart values".
      title: active.label,
      categories: slots,
      series: { key: active.key, label: active.label, values: series.points.map((point) => point.value) },
      axis: axisOf(active.fmt, series.unit),
      unavailable: series.points.some((point) => point.value != null) ? null : NO_FIGURES,
    })
    const pointAt = new Map(slots.map((slot, i) => [slot.key, series.points[i]]))
    // Each year as the tooltip prints it and the values stop says it ("FY2025 · year ended Sep 27, 2025"), and a figure
    // the backend derived (a margin, working capital, the current ratio) read as calculated from its own provenance.
    const reads = readouts(model, {
      header: (period) => periodHeader(period.long, 'year', pointAt.get(period.key)?.period_end),
      calculated: (_mark, key) => pointAt.get(key)?.provenance?.method === 'calculated',
    })
    return { model, reads }
  }, [active, series])
  // Reporting currency of an amount (CNY for an FPI like Alibaba), named in the footnote; a margin or a multiple has none.
  const currency = active && series && (active.fmt === 'usd' || active.fmt === 'eps') ? unitCurrency(series.unit).currency : null

  // Any flagged value in the active series → show the honesty badge.
  const hasUnverified = !!series?.points.some(needsSourceCheck)

  // Supplementary section: stay quiet on error, and disappear when there are no facts
  // (e.g. before the backfill runs) rather than showing an empty card. Keep the card (with
  // bones the plot's height) mounted *while loading* so the common "has data" case doesn't
  // shift content when the query resolves — only collapse once we know there are no facts.
  if (isError || (!isLoading && available.length === 0)) return null

  return (
    <Card as="section" className="mb-8 p-cap-6">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-0.5">
          {/* The row wraps, so where the heading and the badge do not fit side by side (a phone under 200% text) the
              badge goes beneath the heading rather than past the card and the screen; on a line of its own the
              one-line badge is 287px under 200% text, wider than the card's content box at 320 to 390px, so below a
              24rem viewport its label may wrap too (SourceCheckBadge). */}
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">Financial trends</h2>
            {hasUnverified && (
              <SourceCheckBadge reconciled={false} />
            )}
          </div>
          {subtitle && (
            <p className="text-xs text-text-tertiary-light dark:text-text-tertiary-dark">{subtitle}</p>
          )}
        </div>
        {available.length > 0 && (
          // Up to 23 metrics: a compact select sized to its content beside its label, never a segmented row.
          <label className="flex min-w-0 flex-wrap items-center gap-2 text-sm font-medium">
            Metric
            <select
              className={inputClasses({ select: true, density: 'compact', autoWidth: true })}
              value={activeKey ?? ''}
              onChange={(event) => setSelected(event.target.value)}
            >
              {available.map((f) => (
                <option key={f.key} value={f.key}>{f.label}</option>
              ))}
            </select>
          </label>
        )}
      </div>

      {!chart || !active ? (
        // Loading: the bones hold the plot's height, and nothing below the plot shows until there is a metric to name.
        <div role="status" aria-label="Loading financial trends">
          <Skeleton className="w-full rounded-lg" style={{ height: CARD_HEIGHT }} />
          <span className="sr-only">Loading…</span>
        </div>
      ) : (
        <>
          <ChartPlotFrame model={chart.model} readouts={chart.reads} tokens={tokens} fontReady={fontReady} view="card">
            {({ layout, plot, busy }) => (
              // Busy while the plot waits for its font (G4): the plot holds bones of its own plan until then.
              <div data-testid="fundamentals-chart" aria-busy={busy || undefined}>
                {plot}
                {layout?.valuesDontFit && (
                  <p className="mt-2 text-xs" style={{ color: tokens.note }} data-chart-text="fit">{VALUES_DONT_FIT_HERE}</p>
                )}
              </div>
            )}
          </ChartPlotFrame>
          {/* The engine's own footnotes: a margin bar the axis clips is broken, and this line says its printed value is
              the true one. */}
          {chart.model.footnotes.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs" style={{ color: tokens.note }}>
              {chart.model.footnotes.map((footnote) => (
                <li key={`${footnote.mark}${footnote.text}`} data-chart-text="footnote">
                  {footnote.mark && <span className="mr-2 font-data">{footnote.mark}</span>}
                  {footnote.text}
                </li>
              ))}
            </ul>
          )}
          <p className="mt-3 text-xs text-text-tertiary-light dark:text-text-tertiary-dark">
            Annual figures from SEC filings (XBRL){currency && currency !== 'USD' ? `, reported in ${currency}` : ''}.{' '}
            {active.label} by fiscal year.
          </p>
          <SourceChecks values={(series?.points ?? []).map((point) => ({ ...point, label: `${active.label}, ${point.fiscal_year ?? point.period_end ?? 'period unavailable'}` }))} />
        </>
      )}
    </Card>
  )
}
