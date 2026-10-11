'use client'

import { useMemo, useState } from 'react'
import { Button, Card, DataTable, SegmentedControl, type Column } from '@/components/ui'
import { FileXlsIcon } from '@/lib/icons'
import { directionText } from '@/lib/financialTone'
import { formatGrowth, windowGrowth } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import { formatTableGrowth, formatTableValue, tableCurrencyLabel, tableTokenBudget } from '@/features/analysis/lib/tableFormat'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import DataNoteMark from './DataNoteMark'
import { useDataNotes } from './DataNotesContext'
import SourceValue from './SourceValue'

// DataTable's generic requires an index signature (Record<string, unknown>).
type Row = { series: AnalysisSeries } & Record<string, unknown>
type TableWindow = 'all' | 'newest' | 'earliest'

/**
 * Metrics × periods grid: every value in the data face, the period-over-period delta beneath it
 * (gain/loss text tones), a "computed" dagger on derived Q4 columns. Renders straight from the
 * deterministic dataset — no client math beyond display formatting.
 */
export default function MetricsTable({
  dataset,
  onExportXlsx,
  exporting = false,
  headingLevel: Heading = 'h2',
}: {
  dataset: AnalysisDataset
  /** Heading element for "Metrics by period"; the landing page nests the table under an h3. */
  headingLevel?: 'h2' | 'h3' | 'h4'
  /** Branded Excel workbook of the whole dataset (built server-side) — the page passes this on
   *  the Pro results surface only. */
  onExportXlsx?: () => void
  /** True while the workbook request is in flight — unlike the old client-side CSV, this is a
   *  network call, so the button shows a loading state. */
  exporting?: boolean
}) {
  const notes = useDataNotes(dataset)
  const datasetKey = `${dataset.ticker}:${dataset.mode}:${dataset.period_key}`
  const [selection, setSelection] = useState<{ datasetKey: string; window: TableWindow }>({ datasetKey, window: 'all' })
  if (selection.datasetKey !== datasetKey) setSelection({ datasetKey, window: 'all' })
  const window = selection.datasetKey === datasetKey ? selection.window : 'all'
  const periods = useMemo(() => window === 'newest' ? dataset.periods.slice(-6)
    : window === 'earliest' ? dataset.periods.slice(0, 6) : dataset.periods, [dataset.periods, window])
  const periodUnit = dataset.mode === 'quarterly' ? 'quarters' : 'years'
  const basis = dataset.mode === 'quarterly' ? 'prior quarter' : 'prior year'
  const columns = useMemo<Column<Row>[]>(() => {
    const periodColumns: Column<Row>[] = periods.map((period) => ({
      key: period.key,
      header: dataset.mode === 'quarterly' ? (
        <span className="font-data tracking-normal">
          {period.fiscal_period}
          <span className="block font-normal">’{String(period.fiscal_year).slice(-2)}{period.fiscal_period === 'Q4' && dataset.series.some((series) => series.points.some((point) => point.period === period.key && point.value != null && point.derived && point.provenance?.method !== 'reported')) ? <span title="Includes calculated fourth-quarter figures"> †</span> : null}</span>
        </span>
      ) : period.key,
      align: 'right' as const,
      numeric: true,
      render: (row: Row) => {
        const point = row.series.points.find((p) => p.period === period.key) ?? { period: period.key, value: null }
        const currencyLabel = tableCurrencyLabel(row.series)
        const sourceLabel = `${row.series.label}${currencyLabel ? ` (${currencyLabel})` : ''}`
        if (point.value == null) return <SourceValue compactMarks point={point} label={sourceLabel} concept={row.series.concept} note={notes.noteFor(point)}>—</SourceValue>
        const growth = dataset.mode === 'quarterly' ? point.qoq ?? point.yoy : point.yoy
        const growthReconciled = dataset.mode === 'quarterly' && point.qoq != null
          ? point.qoq_reconciled : point.yoy_reconciled
        const growthLabel = dataset.mode === 'quarterly' && point.qoq != null ? 'QoQ' : 'YoY'
        const growthProvenance = dataset.mode === 'quarterly' && point.qoq != null ? point.qoq_provenance : point.yoy_provenance
        const { text: growthText, direction } = formatGrowth(growth, row.series.percent)
        const tone = applySeriesTone(row.series.tone, direction)
        const note = notes.noteFor(point)
        const calculated = point.provenance?.method === 'calculated' || (!point.provenance && point.derived)
        const growthNote = notes.noteForComparison(point, growthLabel === 'QoQ' ? 'qoq' : 'yoy')
        const compactGrowth = formatTableGrowth(growth, row.series.percent, tableTokenBudget(false, growthNote?.letter))
        return (
          <div className="relative flex flex-col items-end gap-0.5">
            <span className="max-w-full">
              <SourceValue compactMarks point={{ ...point, unit: point.unit ?? row.series.unit }} label={sourceLabel} concept={row.series.concept} note={note} comparison={growthText ? { label: growthLabel, display: growthText, provenance: growthProvenance, reconciled: growthReconciled, note: growthNote } : undefined}><span className="inline-block">{formatTableValue(point.value, row.series, tableTokenBudget(calculated, note?.letter))}</span></SourceValue>
            </span>
            {growthText && (
              <span className={`flex flex-col items-end text-xs ${directionText[tone]}`}>
                {dataset.mode === 'quarterly' && growthLabel === 'YoY' && <span>YoY </span>}
                <span className="inline-flex items-baseline">
                  <span className="sr-only">Change vs {dataset.mode === 'quarterly' && growthLabel === 'YoY' ? 'same quarter last year' : basis} </span>
                  {compactGrowth}<DataNoteMark compact note={growthNote} announce />
                </span>
              </span>
            )}
          </div>
        )
      },
    }))
    const metricColumn: Column<Row> = {
      key: 'metric',
      header: <><span>Metric</span><span className="block font-normal normal-case tracking-normal text-data-xs">value · Δ vs {basis}</span></>,
      rowHeader: true,
      render: (row: Row) => (
        <span className="font-medium text-text-primary-light dark:text-text-primary-dark">
          {row.series.label}{tableCurrencyLabel(row.series) ? ' ' : ''}
          {tableCurrencyLabel(row.series) && <span className="block text-data-xs font-normal text-text-secondary-light dark:text-text-secondary-dark">{tableCurrencyLabel(row.series)}</span>}
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
        const note = notes.noteForWindow(row.series)
        const provenance = win.isPercent ? row.series.window_pp_provenance : row.series.cagr_provenance
        const reconciled = win.isPercent ? row.series.window_pp_reconciled : row.series.cagr_reconciled
        const compactText = formatTableGrowth(win.value, win.isPercent, tableTokenBudget(provenance?.method === 'calculated', note?.letter))
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
            <SourceValue compactMarks
              point={{ value: win.value, period: (win.isPercent ? row.series.window_pp_range : row.series.cagr_window) ?? dataset.period_key, unit: win.isPercent ? 'percentage points' : 'growth fraction', provenance, reconciled: reconciled ?? undefined }}
              label={`${row.series.label} ${win.label}`} note={note}
              comparison={{ label: win.isPercent ? 'Window change' : 'CAGR', display: text, provenance, reconciled }}
            ><span className="inline-block">{compactText}</span></SourceValue>
          </span>
        ) : (
          <span className="text-text-tertiary-light dark:text-text-secondary-dark">—</span>
        )
      },
    }
    return [metricColumn, ...periodColumns, cagrColumn]
  }, [dataset, notes, periods, basis])

  const rows = useMemo<Row[]>(() => dataset.series.map((series) => ({ series })), [dataset])
  const hasDerived = dataset.series.some((s) => s.points.some((p) => p.provenance?.method === 'calculated' || (!p.provenance && p.derived)) || s.cagr_provenance?.method === 'calculated' || s.window_pp_provenance?.method === 'calculated')

  return (
    <Card as="section" className="min-w-0 p-4 sm:p-6" data-analysis-metrics>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Heading className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Metrics by period
          </Heading>
          {hasDerived && (
            <span
              className="text-xs text-text-secondary-light dark:text-text-secondary-dark"
              title="Calculated from source figures. Select a value to inspect its inputs and method."
            >
              † calculated
            </span>
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
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs text-text-secondary-light dark:text-text-secondary-dark">Showing {periods.length} of {dataset.periods.length} {periodUnit}</p>
        {dataset.periods.length > 6 && <SegmentedControl<TableWindow>
          label="Table window"
          size="md"
          fullWidth
          value={window}
          onChange={(value) => setSelection({ datasetKey, window: value })}
          options={[{ value: 'all', label: `All ${dataset.periods.length}` }, { value: 'newest', label: 'Newest 6' }, { value: 'earliest', label: 'Earliest 6' }]}
        />}
      </div>
      <p className="mb-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">Figures are rounded for display. Select a value for full precision.</p>
      <DataTable<Row>
        key={datasetKey}
        columns={columns}
        rows={rows}
        rowKey={(row) => row.series.concept}
        density="compact"
        cellPadding="compact"
        layout="fixed"
        colWidths={columns.map((column) => column.key === 'metric' ? 'var(--metric-col)' : 'var(--period-col)')}
        className="[--metric-col:6.5rem] [--period-col:4.25rem] md:[--metric-col:8.25rem] md:[--period-col:4.75rem]"
        snapColumns
        scrollRegion={{
          label: `Metrics by period, scrollable table of ${periods.length} ${periodUnit}`,
          hint: `Scroll for earlier or later ${periodUnit}, or use the arrow keys. Snaps to whole columns.`,
          startAtEndOnMobile: true,
        }}
        caption={`Metrics by period, ${periods.length} of ${dataset.periods.length} ${periodUnit}: value and change versus ${basis}. ${dataset.mode === 'quarterly' ? 'YoY labels identify comparisons versus the prior year when a quarterly comparison is unavailable.' : 'The final column shows the full selected window CAGR, or percentage-point change for margins.'}`}
        stickyFirstColumn
        empty="No metrics available for the selected periods."
      />
    </Card>
  )
}
