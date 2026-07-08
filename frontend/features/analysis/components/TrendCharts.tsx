'use client'

import { useContext, useMemo, useRef, useState } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

import { ThemeContext } from '@/components/ThemeProvider'
import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import {
  Button,
  Card,
  ChartTooltip,
  barCursorProps,
  cx,
  gridProps,
  lineProps,
  seriesColor,
  xAxisProps,
  yAxisProps,
} from '@/components/ui'
import { ArrowsInSimpleIcon, ArrowsOutSimpleIcon, ImageSquareIcon } from '@/lib/icons'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import analytics from '@/lib/analytics'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { exportFilename, exportPanelPng } from '@/features/analysis/lib/chartExport'
import {
  ANNUAL_AXIS_HEIGHT,
  PeriodAxisTick,
  QUARTERLY_AXIS_HEIGHT,
  periodAxisLabel,
} from '@/features/analysis/lib/periodAxis'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'

const bySeries = (dataset: AnalysisDataset): Record<string, AnalysisSeries> =>
  Object.fromEntries(dataset.series.map((s) => [s.concept, s]))

const compactUsd = (v: number) => fmtCurrency(v, { compact: true })
const pct = (v: number) => fmtPercent(v, { digits: 1 })

// The bar panel's series→(label, color) pairing — ONE definition referenced by both the legend
// and the plotted Bar/Line JSX, so the swatches can never drift from what's actually drawn.
const BAR_COLOR = seriesColor(0)
const GROWTH_LINE_COLOR = seriesColor(1)
const GROWTH_LINE_LABEL = 'YoY growth'

// Dual-axis sanity (P1-8): anchor BOTH value axes to zero so the two independent scales share a
// baseline — a right-axis series sitting near its own min can't read as "at the bottom" when it is
// really a large positive number, and a sign change stays visible. Recharts calls these with the
// series' own dataMin/dataMax, so each axis still auto-scales the far end.
const ZERO_ANCHORED_DOMAIN: [(min: number) => number, (max: number) => number] = [
  (dataMin) => Math.min(0, dataMin),
  (dataMax) => Math.max(0, dataMax),
]

/** A panel's series legend: swatch + label per line, mirroring ChartTooltip's own swatch recipe
 *  (8×8 square, 2px radius) so a multi-line panel's series are identifiable without hovering.
 *  A single-series panel needs no legend — the title already names the one line. */
function PanelLegend({ items }: { items: { label: string; color: string }[] }) {
  if (items.length < 2) return null
  return (
    <div className="mt-1 flex flex-wrap gap-x-3 gap-y-1">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-1.5 text-xs text-text-secondary-light dark:text-text-secondary-dark"
        >
          <span
            aria-hidden="true"
            className="inline-block h-2 w-2 shrink-0 rounded-sm"
            style={{ background: item.color }}
          />
          {item.label}
        </span>
      ))}
    </div>
  )
}

interface PanelSpec {
  title: string
  /** [concept, display label] pairs; only concepts present in the dataset render. */
  lines: [string, string][]
  /** Concepts (from `lines`) plotted on a RIGHT value axis — mixed-magnitude panels (equity
   *  dwarfs debt/cash on the balance sheet) get a second scale, called out in the legend. */
  rightAxis?: string[]
  /** Bar series (first panel: the top line as bars + growth as a line). */
  bar?: [string, string]
  /** Right-axis growth line derived from the bar concept's yoy. */
  growthLine?: boolean
  format: (v: number) => string
}

/** Icon-only panel-header control. `secondary` (hairline border + resting surface), 32px hit
 *  area, 20px glyphs — the TSLA field test proved the ghost 28px/14px version read as unshipped
 *  (owner decision D3: keep icon-only, make the affordance visible at rest), and the AAPL
 *  follow-up sized the glyphs up from 16px, which still read tiny in production. Native `title`
 *  tooltips + aria semantics carry the labels. */
function PanelControl({
  label,
  expanded,
  onClick,
  children,
}: {
  label: string
  /** Disclosure semantics (aria-expanded) — the expand control. */
  expanded?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Button
      variant="secondary"
      size="icon-sm"
      aria-label={label}
      title={label}
      aria-expanded={expanded}
      onClick={onClick}
      className="shrink-0"
    >
      {children}
    </Button>
  )
}

function PanelCard({
  panel,
  dataset,
  series,
  exportEnabled,
}: {
  panel: PanelSpec
  dataset: AnalysisDataset
  series: Record<string, AnalysisSeries>
  exportEnabled: boolean
}) {
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const reduced = usePrefersReducedMotion()
  const [expanded, setExpanded] = useState(false)
  const plotRef = useRef<HTMLDivElement>(null)

  // One series→(concept, label, color, axis) mapping drives the legend AND the plotted <Line>s —
  // built once so the two can't disagree on color/label pairing.
  const rightSet = new Set(panel.rightAxis ?? [])
  const lineEntries = panel.lines
    .filter(([concept]) => series[concept])
    .map(([concept, label], index) => ({
      concept,
      label,
      color: seriesColor(index),
      right: rightSet.has(concept),
    }))
  // A second scale only helps when both sides are populated — equity alone stays single-axis.
  const dualAxis = lineEntries.some((e) => e.right) && lineEntries.some((e) => !e.right)
  const barSeries = panel.bar && series[panel.bar[0]] ? series[panel.bar[0]] : null
  if (!barSeries && lineEntries.length === 0) return null

  // One row per period; keys are concept names (+ `growth` for the yoy line).
  const data = dataset.periods.map((period) => {
    const row: Record<string, string | number | null> = { period: period.key }
    for (const { concept } of lineEntries) {
      row[concept] = series[concept].points.find((p) => p.period === period.key)?.value ?? null
    }
    if (barSeries) {
      const point = barSeries.points.find((p) => p.period === period.key)
      row[barSeries.concept] = point?.value ?? null
      if (panel.growthLine) {
        // A sign-flip ("nm") isn't a plottable percentage — render it as a gap, same as a
        // missing value, rather than coercing the sentinel into NaN.
        row.growth = typeof point?.yoy === 'number' ? point.yoy * 100 : null
      }
    }
    return row
  })

  // Route by SERIES, not by value magnitude: the growth line always formats as a percent and
  // everything else with the panel's formatter — a micro-cap's $850 bar or a +1,400% growth
  // spike must never fall through a magnitude heuristic to the wrong formatter.
  const formatTooltip = (v: number | string | undefined, name?: string) => {
    const num = Number(v)
    if (!Number.isFinite(num)) return String(v ?? '')
    if (name === GROWTH_LINE_LABEL) return pct(num)
    return panel.format(num)
  }

  const legendItems = barSeries
    ? [
        { label: barSeries.label, color: BAR_COLOR },
        ...(panel.growthLine ? [{ label: GROWTH_LINE_LABEL, color: GROWTH_LINE_COLOR }] : []),
      ]
    : // " (right)" is a legend-only decoration — the color/label pairing itself stays shared.
      lineEntries.map(({ label, color, right }) => ({
        label: dualAxis && right ? `${label} (right)` : label,
        color,
      }))

  // P1-8: which line series stop before the dataset's final period (a trailing null Recharts can't
  // bridge with connectNulls). Derived from the plotted rows so it matches exactly what's drawn.
  const finalIdx = data.length - 1
  const notReported = lineEntries
    .map(({ concept, label }) => {
      let lastIdx = -1
      for (let i = 0; i < data.length; i++) if (data[i][concept] != null) lastIdx = i
      return lastIdx >= 0 && lastIdx < finalIdx ? { label, period: String(data[lastIdx].period) } : null
    })
    .filter((n): n is { label: string; period: string } => n !== null)

  const exportPng = async () => {
    if (!plotRef.current) return
    const downloaded = await exportPanelPng(
      plotRef.current,
      exportFilename(dataset, panel.title, 'png'),
      { dark }
    )
    if (downloaded) {
      analytics.exportGenerated({
        surface: 'analysis',
        format: 'png',
        ticker: dataset.ticker,
        mode: dataset.mode,
        periodKey: dataset.period_key,
        panel: panel.title,
      })
    }
  }

  return (
    <Card as="section" className={cx('p-5', expanded && 'md:col-span-2')}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            {panel.title}
          </h3>
          <PanelLegend items={legendItems} />
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {exportEnabled && (
            <PanelControl label="Download chart as PNG" onClick={() => void exportPng()}>
              <ImageSquareIcon className="h-5 w-5" aria-hidden="true" />
            </PanelControl>
          )}
          <PanelControl
            label={expanded ? 'Collapse chart' : 'Expand chart'}
            expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <ArrowsInSimpleIcon className="h-5 w-5" aria-hidden="true" />
            ) : (
              <ArrowsOutSimpleIcon className="h-5 w-5" aria-hidden="true" />
            )}
          </PanelControl>
        </div>
      </div>
      <div
        ref={plotRef}
        className={cx(
          'w-full transition-[height] duration-base ease-standard motion-reduce:transition-none',
          expanded ? 'h-96' : 'h-56'
        )}
      >
        <ResponsiveContainer width="100%" height="100%">
          {barSeries ? (
            <ComposedChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis
                dataKey="period"
                {...xAxisProps(dark)}
                // Every period gets a tick (owner decision D2) — Recharts' auto interval was
                // dropping half of a 10-year window. The compact PeriodAxisTick buys the room,
                // and the axis caption underneath names what the bare ticks mean.
                interval={0}
                height={dataset.mode === 'quarterly' ? QUARTERLY_AXIS_HEIGHT : ANNUAL_AXIS_HEIGHT}
                tick={<PeriodAxisTick mode={dataset.mode} dark={dark} />}
                label={periodAxisLabel(dataset.mode, dark)}
              />
              <YAxis yAxisId="value" {...yAxisProps(dark)} width={64} tickFormatter={panel.format} />
              <YAxis
                yAxisId="growth"
                orientation="right"
                {...yAxisProps(dark)}
                width={48}
                tickFormatter={(v: number) => pct(v)}
              />
              <Tooltip
                cursor={barCursorProps(dark)}
                content={<ChartTooltip dark={dark} formatValue={formatTooltip} />}
              />
              <Bar
                yAxisId="value"
                dataKey={barSeries.concept}
                name={barSeries.label}
                fill={BAR_COLOR}
                radius={[4, 4, 0, 0]}
                maxBarSize={44}
              />
              {panel.growthLine && (
                <Line
                  yAxisId="growth"
                  dataKey="growth"
                  name={GROWTH_LINE_LABEL}
                  stroke={GROWTH_LINE_COLOR}
                  {...lineProps(reduced)}
                  connectNulls
                />
              )}
            </ComposedChart>
          ) : (
            <LineChart data={data} margin={{ top: 8, right: 16, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis
                dataKey="period"
                {...xAxisProps(dark)}
                // Every period gets a tick (owner decision D2) — Recharts' auto interval was
                // dropping half of a 10-year window. The compact PeriodAxisTick buys the room,
                // and the axis caption underneath names what the bare ticks mean.
                interval={0}
                height={dataset.mode === 'quarterly' ? QUARTERLY_AXIS_HEIGHT : ANNUAL_AXIS_HEIGHT}
                tick={<PeriodAxisTick mode={dataset.mode} dark={dark} />}
                label={periodAxisLabel(dataset.mode, dark)}
              />
              <YAxis
                yAxisId="left"
                {...yAxisProps(dark)}
                width={64}
                tickFormatter={panel.format}
                {...(dualAxis ? { domain: ZERO_ANCHORED_DOMAIN } : {})}
              />
              {dualAxis && (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  {...yAxisProps(dark)}
                  width={64}
                  tickFormatter={panel.format}
                  domain={ZERO_ANCHORED_DOMAIN}
                />
              )}
              <Tooltip content={<ChartTooltip dark={dark} formatValue={formatTooltip} />} />
              {lineEntries.map(({ concept, label, color, right }) => (
                <Line
                  key={concept}
                  yAxisId={dualAxis && right ? 'right' : 'left'}
                  dataKey={concept}
                  name={label}
                  stroke={color}
                  {...lineProps(reduced)}
                  connectNulls
                />
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
      {notReported.length > 0 && (
        // P1-8: a line that stops before the final period (a trailing null connectNulls can't
        // bridge) reads as missing data — name the last period each series was reported.
        <p className="mt-2 text-xs text-text-tertiary-light dark:text-text-secondary-dark">
          {notReported.map((n) => `${n.label}: not reported after ${n.period}`).join(' · ')}
        </p>
      )}
    </Card>
  )
}

/**
 * The four trend panels (revenue+growth, margins, cash, balance sheet), all straight from the
 * deterministic dataset via the design-system chart factories. Panels whose concepts are absent
 * (gross margin for a bank) collapse silently. Per-panel controls: PNG download (Pro), expand
 * to full grid width. (Data labels were removed after the AAPL field test — on dense real-world
 * series they collide into unreadable stacks; values live in the tooltip and metrics grid.)
 */
export default function TrendCharts({
  dataset,
  exportEnabled = false,
}: {
  dataset: AnalysisDataset
  /** Shows the per-panel PNG download (the page passes this on the Pro results surface only). */
  exportEnabled?: boolean
}) {
  const series = useMemo(() => bySeries(dataset), [dataset])

  const topLine = series['revenue'] ? 'revenue' : 'net_interest_income'

  const panels: PanelSpec[] = [
    {
      title: series[topLine]?.label ? `${series[topLine].label} & growth` : 'Top line & growth',
      lines: [],
      bar: [topLine, series[topLine]?.label ?? 'Top line'],
      growthLine: true,
      format: compactUsd,
    },
    {
      title: 'Margins',
      lines: [
        ['gross_margin', 'Gross'],
        ['operating_margin', 'Operating'],
        ['net_margin', 'Net'],
      ],
      format: pct,
    },
    {
      // Net income and the cash flows can diverge by an order of magnitude (a bank's operating CF
      // swings on trading/deposit flows while net income stays comparatively small), so net income
      // gets its own right axis to stay readable — same rationale as equity on the balance sheet.
      title: 'Cash generation',
      lines: [
        ['operating_cash_flow', 'Operating CF'],
        ['free_cash_flow', 'Free cash flow'],
        ['net_income', 'Net income'],
      ],
      rightAxis: ['net_income'],
      format: compactUsd,
    },
    {
      // Equity routinely dwarfs debt/cash — a right axis keeps the smaller series readable
      // without breaking the "every pixel is a citable dollar value" promise an indexed view
      // would (audit D2).
      title: 'Balance sheet',
      lines: [
        ['long_term_debt', 'Long-term debt'],
        ['shareholders_equity', 'Equity'],
        ['cash_and_equivalents', 'Cash'],
      ],
      rightAxis: ['shareholders_equity'],
      format: compactUsd,
    },
  ]

  // Panels whose concepts are entirely absent collapse silently (a bank has no gross margin) —
  // filtered HERE so the grid (and the all-empty null return) is decided before any Card mounts.
  const visiblePanels = panels.filter((panel) => {
    const hasBar = panel.bar ? Boolean(series[panel.bar[0]]) : false
    const hasLine = panel.lines.some(([concept]) => series[concept])
    return hasBar || hasLine
  })
  if (visiblePanels.length === 0) return null

  return (
    <ChartErrorBoundary>
      <div className="grid gap-4 md:grid-cols-2">
        {visiblePanels.map((panel) => (
          <PanelCard
            key={panel.title}
            panel={panel}
            dataset={dataset}
            series={series}
            exportEnabled={exportEnabled}
          />
        ))}
      </div>
    </ChartErrorBoundary>
  )
}