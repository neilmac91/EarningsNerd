'use client'

import { useContext, useMemo } from 'react'
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
  Card,
  ChartTooltip,
  barCursorProps,
  gridProps,
  lineProps,
  seriesColor,
  xAxisProps,
  yAxisProps,
} from '@/components/ui'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'

const bySeries = (dataset: AnalysisDataset): Record<string, AnalysisSeries> =>
  Object.fromEntries(dataset.series.map((s) => [s.concept, s]))

const compactUsd = (v: number) => fmtCurrency(v, { compact: true })
const pct = (v: number) => fmtPercent(v, { digits: 1 })

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
  /** Bar series (first panel: the top line as bars + growth as a line). */
  bar?: [string, string]
  /** Right-axis growth line derived from the bar concept's yoy. */
  growthLine?: boolean
  format: (v: number) => string
}

/**
 * The four trend panels (revenue+growth, margins, cash, balance sheet), all straight from the
 * deterministic dataset via the design-system chart factories. Panels whose concepts are absent
 * (gross margin for a bank) collapse silently.
 */
export default function TrendCharts({ dataset }: { dataset: AnalysisDataset }) {
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const reduced = usePrefersReducedMotion()
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
      title: 'Balance sheet',
      lines: [
        ['long_term_debt', 'Long-term debt'],
        ['shareholders_equity', 'Equity'],
        ['cash_and_equivalents', 'Cash'],
      ],
      format: compactUsd,
    },
  ]

  const renderPanel = (panel: PanelSpec) => {
    const presentLines = panel.lines.filter(([concept]) => series[concept])
    const barSeries = panel.bar && series[panel.bar[0]] ? series[panel.bar[0]] : null
    if (!barSeries && presentLines.length === 0) return null

    // One row per period; keys are concept names (+ `growth` for the yoy line).
    const data = dataset.periods.map((period) => {
      const row: Record<string, string | number | null> = { period: period.key }
      for (const [concept] of presentLines) {
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
          { label: barSeries.label, color: seriesColor(0) },
          ...(panel.growthLine ? [{ label: 'YoY growth', color: seriesColor(1) }] : []),
        ]
      : presentLines.map(([, label], index) => ({ label, color: seriesColor(index) }))

    return (
      <Card key={panel.title} as="section" className="p-5">
        <div className="mb-3">
          <h3 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">
            {panel.title}
          </h3>
          <PanelLegend items={legendItems} />
        </div>
        <div className="h-56 w-full">
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
                  fill={seriesColor(0)}
                  radius={[4, 4, 0, 0]}
                  maxBarSize={44}
                />
                {panel.growthLine && (
                  <Line
                    yAxisId="growth"
                    dataKey="growth"
                    name="YoY growth"
                    stroke={seriesColor(1)}
                    {...lineProps(reduced)}
                    connectNulls
                  />
                )}
              </ComposedChart>
            ) : (
              <LineChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 0 }}>
                <CartesianGrid {...gridProps(dark)} />
                <XAxis dataKey="period" {...xAxisProps(dark)} />
                <YAxis {...yAxisProps(dark)} width={64} tickFormatter={panel.format} />
                <Tooltip content={<ChartTooltip dark={dark} formatValue={formatTooltip} />} />
                {presentLines.map(([concept, label], index) => (
                  <Line
                    key={concept}
                    dataKey={concept}
                    name={label}
                    stroke={seriesColor(index)}
                    {...lineProps(reduced)}
                    connectNulls
                  />
                ))}
              </LineChart>
            )}
          </ResponsiveContainer>
        </div>
      </Card>
    )
  }

  const rendered = panels.map(renderPanel).filter(Boolean)
  if (rendered.length === 0) return null

  return (
    <ChartErrorBoundary>
      <div className="grid gap-4 md:grid-cols-2">{rendered}</div>
    </ChartErrorBoundary>
  )
}
