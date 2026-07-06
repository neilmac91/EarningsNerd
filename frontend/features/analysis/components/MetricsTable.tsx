'use client'

import { useMemo } from 'react'
import { Badge, Card, DataTable, type Column } from '@/components/ui'
import { fmtCurrency, fmtPercent } from '@/lib/format'
import { directionOf, directionText } from '@/lib/financialTone'
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
export default function MetricsTable({ dataset }: { dataset: AnalysisDataset }) {
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
        return (
          <div className="flex flex-col items-end gap-0.5">
            <span className="flex items-center gap-1">
              {formatSeriesValue(point.value, row.series)}
              {point.derived && (
                <span
                  className="cursor-help text-warning-light dark:text-warning-dark"
                  title="Computed fourth quarter: full year minus the three reported quarters."
                  aria-label="Derived value"
                >
                  †
                </span>
              )}
            </span>
            {growth !== null && growth !== undefined && (
              <span className={`text-xs ${directionText[directionOf(growth)]}`}>
                {growthLabel} {fmtPercent(growth * 100, { digits: 1, signed: true })}
              </span>
            )}
          </div>
        )
      },
    }))
    return [
      {
        key: 'metric',
        header: 'Metric',
        render: (row: Row) => (
          <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
            {row.series.label}
          </span>
        ),
      },
      ...periodColumns,
      {
        key: 'cagr',
        header: 'CAGR',
        align: 'right' as const,
        numeric: true,
        render: (row: Row) =>
          row.series.cagr === null || row.series.cagr === undefined ? (
            <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
          ) : (
            <span className={directionText[directionOf(row.series.cagr)]}>
              {fmtPercent(row.series.cagr * 100, { digits: 1, signed: true })}
            </span>
          ),
      },
    ]
  }, [dataset])

  const rows = useMemo<Row[]>(() => dataset.series.map((series) => ({ series })), [dataset])
  const hasDerived = dataset.series.some((s) => s.points.some((p) => p.derived))

  return (
    <Card as="section" className="p-6">
      <div className="mb-4 flex items-center gap-2">
        <h2 className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
          Metrics by period
        </h2>
        {hasDerived && (
          <Badge
            variant="warning"
            title="† values are computed fourth quarters (full year minus the three reported quarters) — companies disclose Q4 only inside the annual report."
          >
            † computed Q4
          </Badge>
        )}
      </div>
      <div className="overflow-x-auto">
        <DataTable<Row>
          columns={columns}
          rows={rows}
          rowKey={(row) => row.series.concept}
          density="compact"
          empty="No metrics available for the selected periods."
        />
      </div>
    </Card>
  )
}
