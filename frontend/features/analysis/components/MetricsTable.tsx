'use client'

import { useMemo } from 'react'
import { Button, Card, DataTable, MissingValue, type Column } from '@/components/ui'
import { FileXlsIcon } from '@/lib/icons'
import { dataDirectionText } from '@/lib/financialTone'
import { formatGrowth, windowGrowth } from '@/features/analysis/lib/growth'
import { applySeriesTone } from '@/features/analysis/lib/tonePolicy'
import { formatTableGrowth, formatTableValue, tableCurrencyLabel, tableTokenBudget } from '@/features/analysis/lib/tableFormat'
import { formatAnalysisPeriod, formatAnalysisWindow } from '@/features/analysis/lib/periodLabels'
import { reportIdentity, tableComparisonBasis, tablePresentation } from '@/features/analysis/lib/reportPresentation'
import type { AnalysisDataset, AnalysisSeries } from '@/features/analysis/api/analysis-api'
import DataNoteMark from './DataNoteMark'
import { useDataNotes } from './DataNotesContext'
import DataNotesLink from './DataNotesLink'
import GrowthText from './GrowthText'
import SourceValue from './SourceValue'

// DataTable's generic requires an index signature (Record<string, unknown>).
type Row = { series: AnalysisSeries } & Record<string, unknown>

// A figure cell: value over change, each line the cell's full width and right-justified onto one figure edge (the mark
// gutter to its right, DataNoteMark compact: --mark-gutter is one 11px mark, 0.4125rem, and its 2px gap), in the figure
// face (Geist Mono with a drawn minus), whose fixed 600-unit advance gives tabular lining figures; no tracking, as the
// data annotation size has none. A period column holds its widest line inside its 1px phone inset: a seven-glyph figure,
// a dagger and a one-letter note, 7 × 7.2 + 2 + 6.6 + 2 + 6.6 = 67.6px, so 4.375rem (70px, 68px inside) on a phone and
// 4.75rem (68px inside its 4px inset) from md. metrics-table.spec.tsx derives both from tableTokenBudget. Those 2px a
// column cost a 375px phone its third whole period (a 309px card, 104 + 3 × 70 > 309), so on a card 19.25rem to
// 19.625rem wide the metric column gives up to 6px (0.375rem) and three periods sit beside it, as at 390px.
const FIGURE_CELL = 'relative flex flex-col gap-0.5 font-figure tabular-nums lining-nums tracking-normal'
const FIGURE_LINE = 'flex w-full items-baseline justify-end'

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
  // Every period of the run, in one horizontally scrolling table: from 1280px up all of them fit, and on a phone the
  // table opens on the newest (the 6-of-N window it replaced hid periods and saved nothing).
  const periods = dataset.periods
  const visibleNotes = useMemo(() => tablePresentation(dataset, notes).notes, [dataset, notes])
  // A count agrees with the run's length: "1 year", "10 years".
  const periodUnit = `${dataset.mode === 'quarterly' ? 'quarter' : 'year'}${dataset.periods.length === 1 ? '' : 's'}`
  const basis = dataset.mode === 'quarterly' ? 'prior quarter' : 'prior year'
  // The engine computes CAGR annual-only (a "compound ANNUAL growth rate" over 12 quarters
  // isn't well-defined) and over a window of two years or more: in quarterly mode or on a run of
  // one year the final column would show the missing-value mark in every row, so it is hidden
  // there entirely, with the legend's sentence and the caption's, rather than shipping as dead UI.
  const showsCagr = dataset.mode === 'annual' && dataset.periods.length > 1
  const columns = useMemo<Column<Row>[]>(() => {
    const periodColumns: Column<Row>[] = periods.map((period) => {
      const derivedQuarter = period.fiscal_period === 'Q4' && dataset.series.some(series => series.points.some(point => point.period === period.key && point.value != null && point.derived && point.provenance?.method !== 'reported'))
      return {
      key: period.key,
      header: dataset.mode === 'quarterly' ? (
        <span className="font-data tracking-normal">
          <span className="sr-only">{formatAnalysisPeriod(period.key)}{derivedQuarter ? ', includes calculated fourth-quarter flow figures' : ''}</span>
          <span aria-hidden="true" data-period-label>
            {period.fiscal_period}
            <span className="block font-normal">’{String(period.fiscal_year).slice(-2)}{derivedQuarter ? <span title="Includes calculated fourth-quarter flow figures"> †</span> : null}</span>
          </span>
        </span>
      ) : period.key,
      align: 'right' as const,
      numeric: true,
      render: (row: Row) => {
        const point = row.series.points.find((p) => p.period === period.key) ?? { period: period.key, value: null }
        const currencyLabel = tableCurrencyLabel(row.series)
        const sourceLabel = `${row.series.label}${currencyLabel ? ` (${currencyLabel})` : ''}`
        // A missing figure is MissingValue in its source control; the control's own name reads "unavailable" too. Its
        // dash stands on the figure edge in the note ink, its letter in the mark gutter.
        if (point.value == null) return <div className={FIGURE_CELL}><SourceValue compactMarks point={point} label={sourceLabel} concept={row.series.concept} note={notes.noteFor(point)}><MissingValue className="text-note-light dark:text-note-dark" /></SourceValue></div>
        const growthBasis = tableComparisonBasis(dataset.mode, point)
        const growth = point[growthBasis]
        const growthReconciled = point[`${growthBasis}_reconciled`]
        const growthLabel = growthBasis === 'qoq' ? 'QoQ' : 'YoY'
        const growthProvenance = point[`${growthBasis}_provenance`]
        const { text: growthText, direction } = formatGrowth(growth, row.series.percent)
        const tone = applySeriesTone(row.series.tone, direction)
        const note = notes.noteFor(point)
        const calculated = point.provenance?.method === 'calculated' || (!point.provenance && point.derived)
        const growthNote = notes.noteForComparison(point, growthBasis)
        const compactGrowth = formatTableGrowth(growth, row.series.percent, tableTokenBudget(false, growthNote?.letter))
        return (
          <div className={FIGURE_CELL}>
            <span className="block">
              <SourceValue compactMarks point={{ ...point, unit: point.unit ?? row.series.unit }} label={sourceLabel} concept={row.series.concept} note={note} comparison={growthText ? { label: growthLabel, display: growthText, provenance: growthProvenance, reconciled: growthReconciled, note: growthNote } : undefined}><span className="inline-block font-medium text-figure-light dark:text-figure-dark">{formatTableValue(point.value, row.series, tableTokenBudget(calculated, note?.letter))}</span></SourceValue>
            </span>
            {growthText && (
              <span className={`flex flex-col items-end text-xs tracking-normal ${dataDirectionText[tone]}`}>
                {dataset.mode === 'quarterly' && growthLabel === 'YoY' && <span>YoY </span>}
                <span className={FIGURE_LINE}>
                  <span className="sr-only">Change vs {dataset.mode === 'quarterly' && growthLabel === 'YoY' ? 'same quarter last year' : basis} </span>
                  <GrowthText text={compactGrowth} /><DataNoteMark compact note={growthNote} />
                </span>
              </span>
            )}
          </div>
        )
      },
      }
    })
    const metricColumn: Column<Row> = {
      key: 'metric',
      header: <><span>Metric</span><span className="block font-normal normal-case tracking-normal text-data-xs">value · Δ vs {basis}</span></>,
      rowHeader: true,
      // The metric column sits on the panel frame: the name in the figure ink (Lc 101.3 / -91.8 on panel), its currency
      // line in the panel's secondary ink (90.9 / -77.3).
      render: (row: Row) => (
        <span className="font-medium text-figure-light dark:text-figure-dark">
          {row.series.label}{tableCurrencyLabel(row.series) ? ' ' : ''}
          {tableCurrencyLabel(row.series) && <span className="block text-data-xs font-normal text-text-secondary-light dark:text-text-secondary-dark">{tableCurrencyLabel(row.series)}</span>}
        </span>
      ),
    }
    if (!showsCagr) {
      return [metricColumn, ...periodColumns]
    }
    // An en-dash already offers a line break after it, so the window wraps there in a narrow column.
    const cagrWindow = formatAnalysisWindow(dataset.periods[0]?.key ?? '', dataset.periods.at(-1)?.key ?? '')
    const cagrColumn: Column<Row> = {
      key: 'cagr',
      header: <><span className="sr-only">{cagrWindow} CAGR</span><span aria-hidden="true" className="block font-data normal-case tracking-normal">{cagrWindow}<span className="block">CAGR</span></span></>,
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
            ? `Percentage-point change over ${formatAnalysisPeriod(row.series.window_pp_range)}. CAGR doesn't apply to a percent-unit series.`
            : undefined
        return text ? (
          <span
            className={`${FIGURE_CELL} ${windowTooltip ? `cursor-help ${dataDirectionText[tone]}` : dataDirectionText[tone]}`}
            title={windowTooltip}
          >
            <SourceValue compactMarks
              point={{ value: win.value, period: (win.isPercent ? row.series.window_pp_range : row.series.cagr_window) ?? dataset.period_key, unit: win.isPercent ? 'percentage points' : 'growth fraction', provenance, reconciled: reconciled ?? undefined }}
              label={`${row.series.label} ${win.label}`} note={note}
              comparison={{ label: win.isPercent ? 'Window change' : 'CAGR', display: text, provenance, reconciled, note }}
            ><span className="inline-block">{compactText}</span></SourceValue>
          </span>
        ) : (
          // No window figure: the dash on the figure edge, the gutter kept beside it.
          <span className={FIGURE_CELL}><span className={FIGURE_LINE}><MissingValue className="text-note-light dark:text-note-dark" /><DataNoteMark compact /></span></span>
        )
      },
    }
    return [metricColumn, ...periodColumns, cagrColumn]
  }, [dataset, notes, periods, basis, showsCagr])

  const rows = useMemo<Row[]>(() => dataset.series.map((series) => ({ series })), [dataset])
  const hasDerived = dataset.series.some((s) => s.points.some((p) => p.provenance?.method === 'calculated' || (!p.provenance && p.derived)) || s.cagr_provenance?.method === 'calculated' || s.window_pp_provenance?.method === 'calculated')

  return (
    <Card as="section" className="[--mark-gutter:0.5375rem] [container-type:inline-size] min-w-0 p-4 sm:p-cap-6" data-analysis-metrics>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <Heading className="text-xl font-semibold text-text-primary-light dark:text-text-primary-dark">
            Metrics by period
          </Heading>
          <DataNotesLink notes={visibleNotes} />
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
      <p className="mb-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">Figures are rounded for display. Select a value for full precision.</p>
      <p className="mb-3 text-xs text-text-secondary-light dark:text-text-secondary-dark">n/m means not meaningful.{dataset.mode === 'quarterly'
        ? ' Fiscal quarters follow the company’s reporting calendar. A Q4 header † means some flow figures are calculated from annual totals less the first nine months; it does not mark the column’s balance-sheet figures as calculated.'
        : showsCagr ? ' The final column shows CAGR, or percentage-point change for percent-unit rows. Each value’s source detail states its calculation range.' : null}</p>
      <DataTable<Row>
        key={reportIdentity(dataset)}
        columns={columns}
        rows={rows}
        rowKey={(row) => row.series.concept}
        density="compact"
        cellPadding="compact"
        layout="fixed"
        colWidths={columns.map((column) => column.key === 'metric' ? 'var(--metric-col)' : 'var(--period-col)')}
        className="[--metric-col:min(6.5rem,100cqi)] [@container(19.25rem<=width<19.625rem)]:[--metric-col:calc(100cqi-3*var(--period-col))] [--period-col:4.375rem] md:[--metric-col:min(8.25rem,100cqi)] md:[--period-col:4.75rem]"
        snapColumns
        scrollRegion={{
          label: `Metrics by period, scrollable table of ${periods.length} ${periodUnit}`,
          // A phone opens the table at its end: with one period, the metric names are all that lies to its left.
          hint: periods.length === 1 ? '← Metric names' : `← Earlier ${periodUnit}`,
          startAtEndOnMobile: true,
        }}
        caption={`Metrics by period, ${periods.length} ${periodUnit}: value and change versus ${basis}.${dataset.mode === 'quarterly' ? ' Fiscal quarters follow the company’s reporting calendar. YoY labels identify comparisons versus the prior year when a quarterly comparison is unavailable.' : showsCagr ? ' The final column shows CAGR, or percentage-point change for percent-unit rows.' : ''}`}
        stickyFirstColumn
        surface="well"
        pageHeader
        empty="No metrics available for the selected periods."
      />
    </Card>
  )
}
