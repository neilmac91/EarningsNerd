'use client'

import { useMemo } from 'react'
import { Badge, Button, Card, DataTable, type Column } from '@/components/ui'
import { FileXlsIcon } from '@/lib/icons'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionText } from '@/lib/financialTone'
import { formatGrowth, windowGrowth } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'

const currencyFromUnit = (unit: string | undefined): string => {
  const code = (unit || 'USD').split('/')[0].trim().toUpperCase()
  return /^[A-Z]{3}$/.test(code) ? code : 'USD'
}

export const formatSeriesValue = (value: number, series: AnalysisSeries): string => {
  if (series.percent) return fmtPercent(value, { digits: 1 })
  if (series.unit === 'pure')
    return `${value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}×`
  if (series.unit.endsWith('/shares'))
    return fmtCurrency(value, { currency: currencyFromUnit(series.unit), digits: 2, compact: false })
  return fmtCurrency(value, { currency: currencyFromUnit(series.unit), compact: true })
}

// DataTable's generic requires an index signature (Record<string, unknown>).
type Row = { series: AnalysisSeries } & Record<string, unknown>

/**
 * Metrics × periods grid: every value in the data face, the period-over-period delta beneath it
 * (gain/loss text tones), a "computed" dagger on derived Q4 columns. Renders straight from the
 * deterministic dataset — no client math beyond display formatting.
 */
export default function MetricsTable({
  dataset,
  onExportXlsx,
  exporting = false,
}: {
  dataset: AnalysisDataset
  /** Branded Excel workbook of the whole dataset (built server-side) — the page passes this on
   *  the Pro results surface only. */
  onExportXlsx?: () => void
  /** True while the workbook request is in flight — unlike the old client-side CSV, this is a
   *  network call, so the button shows a loading state. */
  exporting?: boolean
}) {
  const columns = useMemo<Column<Row>[]>(() => {
    const periodColumns: Column<Row>[] = dataset.periods.map((period) => ({
      key: period.key,
      header: period.key,
      align: 'right' as const,
      numeric: true,
      render: (row: Row) => {
        const point = row.series.points.find((p) => p.period === period.key)
        if (!point || point.value === null || point.value === undefined) {
          return <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
        }
        const growth = dataset.mode === 'quarterly' ? point.qoq ?? point.yoy : point.yoy
        const growthLabel = dataset.mode === 'quarterly' && point.qoq !== undefined ? 'QoQ' : 'YoY'
        const { text: growthText, direction } = formatGrowth(growth, row.series.percent)
        const tone = applySeriesTone(row.series.tone, direction)
        return (
          <div className="flex flex-col items-end gap-0.5">
            <span className="flex items-center gap-1">
              {formatSeriesValue(point.value, row.series)}
              {point.derived && (
                <span
                  className="cursor-help text-warning-light dark:text-warning-dark"
                  title="Computed fourth quarter: derived from the annual report (full year minus the reported year-to-date quarters; EPS re-derived from Q4 net income and weighted shares)."
                  aria-label="Derived value"
                >
                  †
                </span>
              )}
            </span>
            {growthText && (
              <span className={`text-xs ${directionText[tone]}`}>
                {growthLabel} {growthText}
              </span>
            )}
          </div>
        )
      },
    }))
    const metricColumn: Column<Row> = {
      key: 'metric',
      header: 'Metric',
      render: (row: Row) => (
        <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
          {row.series.label}
        </span>
      ),
    }
    // The engine computes CAGR annual-only (a "compound ANNUAL growth rate" over 12 quarters
    // isn't well-defined) — the column would render "—" for every row in quarterly mode, so it's
    // hidden there entirely rather than shipping as permanently dead UI.
    if (dataset.mode !== 'annual') {
      return [metricColumn, ...periodColumns]
    }
    const cagrColumn: Column<Row> = {
      key: 'cagr',
      header: 'CAGR',
      align: 'right' as const,
      numeric: true,
      render: (row: Row) => {
        // Shared window-growth rule (growth.ts): CAGR for monetary/per-share rows, the window's
        // pp change for percent-unit rows (margins) — the same resolution the KPI strip uses,
        // so a margin row shows its window figure here instead of a permanently dead "—".
        const win = windowGrowth(row.series)
        const { text, direction } = formatGrowth(win.value, win.isPercent)
        const tone = applySeriesTone(row.series.tone, direction)
        // cursor-help only when the tooltip actually exists — same condition for both.
        const windowTooltip =
          win.isPercent && row.series.window_pp_range
            ? `Percentage-point change over ${row.series.window_pp_range}. CAGR doesn't apply to a percent-unit series.`
            : undefined
        return text ? (
          <span
            className={windowTooltip ? `cursor-help ${directionText[tone]}` : directionText[tone]}
            title={windowTooltip}
          >
            {text}
          </span>
        ) : (
          <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
        )
      },
    }
    return [metricColumn, ...periodColumns, cagrColumn]
  }, [dataset])

  const rows = useMemo<Row[]>(() => dataset.series.map((series) => ({ series })), [dataset])
  const hasDerived = dataset.series.some((s) => s.points.some((p) => p.derived))

  return (
    <Card as="section" className="p-6">
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Metrics by period
          </h2>
          {hasDerived && (
            <Badge
              variant="warning"
              title="† values are computed fourth quarters, derived from the annual report, since companies disclose Q4 only inside the full-year figures. Flows: full year minus the reported year-to-date quarters; EPS: Q4 net income ÷ Q4 weighted shares."
            >
              † computed Q4
            </Badge>
          )}
        </div>
        {onExportXlsx && (
          <Button
            size="sm"
            variant="secondary"
            onClick={onExportXlsx}
            loading={exporting}
            leftIcon={<FileXlsIcon className="h-3.5 w-3.5" aria-hidden="true" />}
          >
            Export Excel
          </Button>
        )}
      </div>
      <DataTable<Row>
        columns={columns}
        rows={rows}
        rowKey={(row) => row.series.concept}
        density="compact"
        stickyFirstColumn
        empty="No metrics available for the selected periods."
      />
    </Card>
  )
}
