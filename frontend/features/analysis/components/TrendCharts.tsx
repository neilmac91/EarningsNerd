'use client'

import { useContext, useMemo, useRef, useState } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  LabelList,
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
  CHART_FONT,
  ChartTooltip,
  barCursorProps,
  chartTheme,
  cx,
  gridProps,
  lineProps,
  seriesColor,
  xAxisProps,
  yAxisProps,
} from '@/components/ui'
import {
  ArrowsInSimpleIcon,
  ArrowsOutSimpleIcon,
  ImageSquareIcon,
  TagSimpleIcon,
} from '@/lib/icons'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { exportFilename, exportPanelPng } from '@/features/analysis/lib/chartExport'
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

// Data labels auto-thin on crowded axes: annual 10 / quarterly 12 periods overlap at full
// density, so past this count only every other point is labelled.
const LABEL_THINNING_THRESHOLD = 8

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

/** Recharts LabelList `content` renderer: panel-formatted value above the point/bar, chart-label
 *  ink, data face, thinned to every `step`-th point on crowded axes. */
const makeValueLabel = (format: (v: number) => string, fill: string, step: number) =>
  function ChartValueLabel(props: unknown) {
    const { x, y, width, value, index } = props as {
      x?: number | string
      y?: number | string
      width?: number | string
      value?: number | string | null
      index?: number
    }
    if (value === null || value === undefined || typeof index !== 'number') return null
    if (index % step !== 0) return null
    const num = Number(value)
    if (!Number.isFinite(num)) return null
    const anchorX = Number(x) + (width !== undefined ? Number(width) / 2 : 0)
    return (
      <text
        x={anchorX}
        y={Number(y) - 6}
        textAnchor="middle"
        fill={fill}
        fontSize={10}
        fontFamily={CHART_FONT}
      >
        {format(num)}
      </text>
    )
  }

/** Icon-only panel-header control (the CopilotComposer icon-button recipe, ghost + square). */
function PanelControl({
  label,
  pressed,
  expanded,
  onClick,
  children,
}: {
  label: string
  /** Toggle semantics (aria-pressed) — the data-labels control. */
  pressed?: boolean
  /** Disclosure semantics (aria-expanded) — the expand control. */
  expanded?: boolean
  onClick: () => void
  children: React.ReactNode
}) {
  return (
    <Button
      variant="ghost"
      size="sm"
      aria-label={label}
      title={label}
      aria-pressed={pressed}
      aria-expanded={expanded}
      onClick={onClick}
      className={cx('h-7 w-7 shrink-0 px-0', pressed && 'bg-brand-weak dark:bg-brand-weak-dark')}
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
  const [showLabels, setShowLabels] = useState(false)
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

  // ChartTooltip formats by value only (no series name). In the composed panel the two scales
  // are unambiguous — growth is ±100 (%) while monetary values are ≥ millions — so route small
  // magnitudes to the percent formatter.
  const formatTooltip = (v: number | string | undefined) => {
    const num = Number(v)
    if (!Number.isFinite(num)) return String(v ?? '')
    if (barSeries && panel.growthLine && Math.abs(num) < 1000) return pct(num)
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

  const labelStep = dataset.periods.length > LABEL_THINNING_THRESHOLD ? 2 : 1
  const valueLabel = showLabels
    ? makeValueLabel(panel.format, chartTheme(dark).label, labelStep)
    : null

  const exportPng = async () => {
    if (!plotRef.current) return
    await exportPanelPng(plotRef.current, exportFilename(dataset, panel.title, 'png'))
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
        <div className="flex shrink-0 items-center gap-1">
          <PanelControl
            label={showLabels ? 'Hide data labels' : 'Show data labels'}
            pressed={showLabels}
            onClick={() => setShowLabels((v) => !v)}
          >
            <TagSimpleIcon className="h-3.5 w-3.5" aria-hidden="true" />
          </PanelControl>
          {exportEnabled && (
            <PanelControl label="Download chart as PNG" onClick={() => void exportPng()}>
              <ImageSquareIcon className="h-3.5 w-3.5" aria-hidden="true" />
            </PanelControl>
          )}
          <PanelControl
            label={expanded ? 'Collapse chart' : 'Expand chart'}
            expanded={expanded}
            onClick={() => setExpanded((v) => !v)}
          >
            {expanded ? (
              <ArrowsInSimpleIcon className="h-3.5 w-3.5" aria-hidden="true" />
            ) : (
              <ArrowsOutSimpleIcon className="h-3.5 w-3.5" aria-hidden="true" />
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
            <ComposedChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis dataKey="period" {...xAxisProps(dark)} />
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
              >
                {valueLabel && (
                  <LabelList dataKey={barSeries.concept} position="top" content={valueLabel} />
                )}
              </Bar>
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
            <LineChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
              <CartesianGrid {...gridProps(dark)} />
              <XAxis dataKey="period" {...xAxisProps(dark)} />
              <YAxis yAxisId="left" {...yAxisProps(dark)} width={64} tickFormatter={panel.format} />
              {dualAxis && (
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  {...yAxisProps(dark)}
                  width={64}
                  tickFormatter={panel.format}
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
                >
                  {valueLabel && (
                    <LabelList dataKey={concept} position="top" content={valueLabel} />
                  )}
                </Line>
              ))}
            </LineChart>
          )}
        </ResponsiveContainer>
      </div>
    </Card>
  )
}

/**
 * The four trend panels (revenue+growth, margins, cash, balance sheet), all straight from the
 * deterministic dataset via the design-system chart factories. Panels whose concepts are absent
 * (gross margin for a bank) collapse silently. Per-panel controls: data-label toggle, PNG
 * download (Pro), expand to full grid width.
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
      title: 'Cash generation',
      lines: [
        ['operating_cash_flow', 'Operating CF'],
        ['free_cash_flow', 'Free cash flow'],
        ['net_income', 'Net income'],
      ],
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