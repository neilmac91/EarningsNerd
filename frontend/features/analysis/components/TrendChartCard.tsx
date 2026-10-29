'use client'
/**
 * One trend chart's card under the spec renderer (steps 4 to 7 of the migration, E192, E193, E195): the app's Card
 * shell and controls around the chart engine's model and plan. The plan is laid out at the card's measured width, and
 * the expanded view at its own width, never a CSS scale (spec §3.10). A chart that does not apply keeps the card's
 * height and says why (§3.4). The card's HTML text takes the theme's chart inks (§3.8) inline, from the same source as
 * the plot (theme.ts, which mirrors the renderer's Tailwind pairs, E194), and so does its PNG's header. TrendChartPlot holds the plot and the ways to read it. The card spans three rows of the grid's
 * subgrid, its header, plot and notes, so a grid row's plots start at one height whatever its legends wrap to (chief
 * design's review of #1609). Escape in an expanded card collapses it and returns focus to its toggle (§3.10, D13).
 * The card names its chart (data-trend-chart) and each piece of its text (data-chart-text) for the gallery's DOM checks
 * (D6, D9, M19; step 6, E194). It is busy (aria-busy) while its plot waits for its font, and its export control while a
 * PNG is drawn; expanding or collapsing grows or shrinks the plot's row to its new height (§3.9, §3.10; E200).
 */
import { useCallback, useContext, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { ThemeContext } from '@/components/ThemeProvider'
import { Card, cx } from '@/components/ui'
import { usePrefersReducedMotion } from '@/hooks/usePrefersReducedMotion'
import analytics from '@/lib/analytics'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { ArrowsInSimpleIcon, ArrowsOutSimpleIcon, ImageSquareIcon } from '@/lib/icons'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { exportFilename, exportPanelPng, exportSourceText } from '@/features/analysis/lib/chartExport'
import { CARD_HEIGHT, layoutChart, VALUES_DONT_FIT } from '@/features/analysis/lib/charts/layout'
import { buildChartModel, type ChartId } from '@/features/analysis/lib/charts/model'
import { chartReadouts } from '@/features/analysis/lib/charts/readout'
import { chartTokens } from '@/features/analysis/lib/charts/theme'
import type { DataNotesModel } from '@/features/analysis/lib/dataNotes'
import { FCF_DEFINITION } from '@/features/analysis/lib/provenance'
import ChartControl from './ChartControl'
import { LegendSwatch } from './chartMarks'
import DataNotesLink from './DataNotesLink'
import TrendChartPlot from './TrendChartPlot'

/** The server and the first render plan at the desktop card's width (§3.12) until the card is measured. */
const DEFAULT_WIDTH = 502

/** §3.10: the plot's row runs from the height it had before a toggle to the one it has now, over the row's own
 *  transition (duration-base, ease-standard), clipped while it runs; then the row is left to size itself again. Returns
 *  what ends it early. */
function growFrom(row: HTMLElement, from: number): (() => void) | undefined {
  const to = row.getBoundingClientRect().height
  if (Math.abs(to - from) < 1) return undefined
  const done = () => {
    row.removeEventListener('transitionend', end)
    row.removeEventListener('transitioncancel', done)
    row.style.height = ''
    row.style.overflow = ''
  }
  const end = (event: TransitionEvent) => {
    if (event.target === row && event.propertyName === 'height') done()
  }
  row.style.overflow = 'hidden'
  row.style.height = `${from}px`
  // Commit the start height, so the change to the end height is a transition rather than a jump.
  row.getBoundingClientRect()
  row.addEventListener('transitionend', end)
  row.addEventListener('transitioncancel', done)
  row.style.height = `${to}px`
  return done
}

export default function TrendChartCard({ chart, dataset, notes, exportEnabled, fontReady }: {
  chart: ChartId
  dataset: AnalysisDataset
  notes: DataNotesModel
  exportEnabled: boolean
  /** Spec G4: the plot paints once its font has loaded; until then the card holds the plot's box. */
  fontReady: boolean
}) {
  const dark = useContext(ThemeContext)?.theme === 'dark'
  const tokens = chartTokens(dark)
  const [expanded, setExpanded] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const onWidth = useCallback((measured: number) => setWidth(measured), [])
  const plotRef = useRef<HTMLDivElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const rowRef = useRef<HTMLDivElement>(null)
  // The plot row's height when a toggle was asked for, read before the view changes it.
  const fromHeight = useRef<number | null>(null)
  const reduced = usePrefersReducedMotion()
  const uid = `chart${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const model = useMemo(() => buildChartModel(chart, dataset, notes), [chart, dataset, notes])
  const readouts = useMemo(() => chartReadouts(model, dataset, notes), [model, dataset, notes])
  const view = expanded ? 'expanded' : 'card'
  const layout = useMemo(() => (model.unavailable ? null : layoutChart(model, width, view)), [model, width, view])

  // The Notes chip names the letters the band and the footnotes show, read from the model's footnotes, so the three
  // never disagree: an n/m comparison's note letters here too.
  const panelNotes = useMemo(() => {
    const lettered = new Set(model.footnotes.map((footnote) => footnote.mark))
    return notes.notes.filter((note) => lettered.has(note.letter))
  }, [model, notes])

  const toggle = (next: boolean) => {
    fromHeight.current = rowRef.current?.getBoundingClientRect().height ?? null
    setExpanded(next)
  }
  // The view has changed the row's height by now; it runs there from the old one, unless the reader asks for no motion.
  useLayoutEffect(() => {
    const row = rowRef.current
    const from = fromHeight.current
    fromHeight.current = null
    if (!row || from == null || reduced) return undefined
    return growFrom(row, from)
  }, [expanded, reduced])

  const exportPng = async () => {
    if (!plotRef.current || exporting) return
    setExporting(true)
    const downloaded = await exportPanelPng(
      plotRef.current,
      exportFilename(dataset, model.title, 'png'),
      {
        dark,
        // The card's own inks: legend names' for the subtitle, legend and notes, so dark text clears its floor (§3.8).
        ink: { primary: tokens.figure, secondary: tokens.name },
        header: {
          company: formatCompanyName(dataset.company_name),
          ticker: dataset.ticker,
          title: model.title,
          // The card's legend and footnotes, so the picture and the screen say the same (§3.11, E2).
          legend: model.legend.flatMap((item) => (item.color == null ? [] : [{ label: item.label, color: tokens.series[item.color] }])),
          ...exportSourceText(dataset),
          notes: [
            ...model.footnotes.map((footnote) => (footnote.mark ? `${footnote.mark}  ${footnote.text}` : footnote.text)),
            ...(model.panels.some((panel) => panel.marks.some((mark) => mark.seriesKey === 'free_cash_flow')) ? [FCF_DEFINITION] : []),
          ],
        },
      }
    ).catch(() => false)
    setExporting(false)
    if (downloaded) {
      analytics.exportGenerated({ surface: 'analysis', format: 'png', ticker: dataset.ticker, mode: dataset.mode, periodKey: dataset.period_key, panel: model.title })
    } else {
      toast.error('Could not create the chart image. Try again.')
    }
  }

  return (
    <Card as="section" className={cx('row-span-3 grid min-w-0 grid-cols-1 grid-rows-subgrid gap-y-0 p-cap-5', expanded && 'md:col-span-2')}
      data-trend-chart={chart} aria-busy={(layout != null && !fontReady) || undefined} onKeyDown={(event) => {
        // A portalled dialog's Escape is not the card's: its DOM sits outside the section.
        if (event.key !== 'Escape' || !expanded || event.defaultPrevented || !event.currentTarget.contains(event.target as Node)) return
        event.preventDefault()
        toggle(false)
        toggleRef.current?.focus()
      }}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{model.title}</h2>
          <p className="mt-0.5 text-xs" style={{ color: tokens.note }} data-chart-text="subtitle">{model.subtitle}</p>
          {(model.legend.length > 0 || panelNotes.length > 0) && (
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              {model.legend.length > 0 && (
                <ul className="flex flex-wrap gap-x-3 gap-y-1" aria-label="Series">
                  {model.legend.map((item) => (
                    <li key={item.label} className="inline-flex items-center gap-1.5 text-xs">
                      <LegendSwatch item={item} tokens={tokens} />
                      <span style={{ color: tokens.name }} data-chart-text="name">{item.label}</span>
                      {item.value && <span className="font-data" style={{ color: tokens.figure }} data-chart-text="figure">{item.value}</span>}
                    </li>
                  ))}
                </ul>
              )}
              <DataNotesLink notes={panelNotes} />
            </div>
          )}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          {exportEnabled && layout && (
            <ChartControl label="Download chart as PNG" disabled={!fontReady} loading={exporting} onClick={() => void exportPng()}>
              <ImageSquareIcon className="h-5 w-5" aria-hidden="true" />
            </ChartControl>
          )}
          <ChartControl label={expanded ? 'Collapse chart' : 'Expand chart'} expanded={expanded} buttonRef={toggleRef} onClick={() => toggle(!expanded)}>
            {expanded ? <ArrowsInSimpleIcon className="h-5 w-5" aria-hidden="true" /> : <ArrowsOutSimpleIcon className="h-5 w-5" aria-hidden="true" />}
          </ChartControl>
        </div>
      </div>
      {/* The subgrid's second row, whose height a toggle runs (§3.10). */}
      <div ref={rowRef} className="min-w-0 transition-[height] duration-base ease-standard motion-reduce:transition-none">
        {layout ? (
          <TrendChartPlot model={model} layout={layout} readouts={readouts} tokens={tokens} fontReady={fontReady} uid={uid} view={view}
            plotRef={plotRef} onWidth={onWidth} />
        ) : (
          <div className="flex items-center justify-center px-4 text-center text-sm" style={{ height: CARD_HEIGHT, color: tokens.note }} data-chart-text="unavailable">
            {model.unavailable}
          </div>
        )}
      </div>
      {/* Always rendered: the subgrid's third row. */}
      <div>
        {layout?.valuesDontFit && <p className="mt-2 text-xs" style={{ color: tokens.note }} data-chart-text="fit">{VALUES_DONT_FIT}</p>}
        {model.footnotes.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs" style={{ color: tokens.note }}>
            {model.footnotes.map((footnote) => (
              <li key={`${footnote.mark}${footnote.text}`} data-chart-text="footnote">
                {footnote.mark && <span className="mr-2 font-data">{footnote.mark}</span>}
                {footnote.text}
              </li>
            ))}
          </ul>
        )}
      </div>
    </Card>
  )
}
