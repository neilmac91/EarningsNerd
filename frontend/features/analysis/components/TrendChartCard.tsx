'use client'
/**
 * One trend chart's card under the spec renderer (CHARTS_V2; steps 4 and 5 of the migration, E192, E193): today's Card
 * shell and controls around the chart engine's model and plan. The plan is laid out at the card's measured width, and
 * the expanded view at its own width, never a CSS scale (spec §3.10). A chart that does not apply keeps the card's
 * height and says why (§3.4). The card's HTML text takes the theme's chart inks (§3.8), which reach Tailwind with the
 * step-6 switch (E194). TrendChartPlot holds the plot and the ways to read it. The card spans three rows of the grid's
 * subgrid, its header, plot and notes, so a grid row's plots start at one height whatever its legends wrap to (chief
 * design's review of #1609). Escape in an expanded card collapses it and returns focus to its toggle (§3.10, D13).
 */
import { useCallback, useContext, useId, useMemo, useRef, useState } from 'react'
import { toast } from 'sonner'
import { ThemeContext } from '@/components/ThemeProvider'
import { Card, cx } from '@/components/ui'
import analytics from '@/lib/analytics'
import { formatCompanyName } from '@/lib/formatCompanyName'
import { ArrowsInSimpleIcon, ArrowsOutSimpleIcon, ImageSquareIcon } from '@/lib/icons'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { chartDataNotes, exportFilename, exportPanelPng, exportSourceText } from '@/features/analysis/lib/chartExport'
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
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const onWidth = useCallback((measured: number) => setWidth(measured), [])
  const plotRef = useRef<HTMLDivElement>(null)
  const toggleRef = useRef<HTMLButtonElement>(null)
  const uid = `chart${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const model = useMemo(() => buildChartModel(chart, dataset, notes), [chart, dataset, notes])
  const readouts = useMemo(() => chartReadouts(model, dataset, notes), [model, dataset, notes])
  const view = expanded ? 'expanded' : 'card'
  const layout = useMemo(() => (model.unavailable ? null : layoutChart(model, width, view)), [model, width, view])

  // The series this chart plots, for its data-notes link (the growth mark's key is its top line's, plus ":yoy").
  const plotted = useMemo(() => {
    const concepts = new Set(model.panels.flatMap((panel) => panel.marks.map((mark) => mark.seriesKey.split(':')[0])))
    return dataset.series.filter((series) => concepts.has(series.concept))
  }, [model, dataset])
  const { panelNotes } = useMemo(() => chartDataNotes(dataset, plotted, notes, chart === 'topline'), [dataset, plotted, notes, chart])

  const exportPng = async () => {
    if (!plotRef.current) return
    const downloaded = await exportPanelPng(
      plotRef.current,
      exportFilename(dataset, model.title, 'png'),
      {
        dark,
        header: {
          company: formatCompanyName(dataset.company_name),
          ticker: dataset.ticker,
          title: model.title,
          // The card's legend and footnotes, so the picture and the screen say the same (§3.11, E2).
          legend: model.legend.flatMap((item) => (item.color == null ? [] : [{ label: item.label, color: tokens.series[item.color] }])),
          ...exportSourceText(dataset),
          notes: [
            ...model.footnotes.map((footnote) => (footnote.mark ? `${footnote.mark}  ${footnote.text}` : footnote.text)),
            ...(plotted.some((series) => series.concept === 'free_cash_flow') ? [FCF_DEFINITION] : []),
          ],
        },
      }
    ).catch(() => false)
    if (downloaded) {
      analytics.exportGenerated({ surface: 'analysis', format: 'png', ticker: dataset.ticker, mode: dataset.mode, periodKey: dataset.period_key, panel: model.title })
    } else {
      toast.error('Could not create the chart image. Try again.')
    }
  }

  return (
    <Card as="section" className={cx('row-span-3 grid min-w-0 grid-cols-1 grid-rows-subgrid gap-y-0 p-cap-5', expanded && 'md:col-span-2')}
      onKeyDown={(event) => {
        // A portalled dialog's Escape is not the card's: its DOM sits outside the section.
        if (event.key !== 'Escape' || !expanded || event.defaultPrevented || !event.currentTarget.contains(event.target as Node)) return
        event.preventDefault()
        setExpanded(false)
        toggleRef.current?.focus()
      }}>
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-text-primary-light dark:text-text-primary-dark">{model.title}</h2>
          <p className="mt-0.5 text-xs" style={{ color: tokens.note }}>{model.subtitle}</p>
          {(model.legend.length > 0 || panelNotes.length > 0) && (
            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1">
              {model.legend.length > 0 && (
                <ul className="flex flex-wrap gap-x-3 gap-y-1" aria-label="Series">
                  {model.legend.map((item) => (
                    <li key={item.label} className="inline-flex items-center gap-1.5 text-xs">
                      <LegendSwatch item={item} tokens={tokens} />
                      <span style={{ color: tokens.name }}>{item.label}</span>
                      {item.value && <span className="font-data" style={{ color: tokens.figure }}>{item.value}</span>}
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
            <ChartControl label="Download chart as PNG" disabled={!fontReady} onClick={() => void exportPng()}>
              <ImageSquareIcon className="h-5 w-5" aria-hidden="true" />
            </ChartControl>
          )}
          <ChartControl label={expanded ? 'Collapse chart' : 'Expand chart'} expanded={expanded} buttonRef={toggleRef} onClick={() => setExpanded((value) => !value)}>
            {expanded ? <ArrowsInSimpleIcon className="h-5 w-5" aria-hidden="true" /> : <ArrowsOutSimpleIcon className="h-5 w-5" aria-hidden="true" />}
          </ChartControl>
        </div>
      </div>
      {layout ? (
        <TrendChartPlot model={model} layout={layout} readouts={readouts} tokens={tokens} fontReady={fontReady} uid={uid} view={view}
          plotRef={plotRef} onWidth={onWidth} />
      ) : (
        <div className="flex items-center justify-center px-4 text-center text-sm" style={{ height: CARD_HEIGHT, color: tokens.note }}>
          {model.unavailable}
        </div>
      )}
      {/* Always rendered: the subgrid's third row. */}
      <div>
        {layout?.valuesDontFit && <p className="mt-2 text-xs" style={{ color: tokens.note }}>{VALUES_DONT_FIT}</p>}
        {model.footnotes.length > 0 && (
          <ul className="mt-2 space-y-0.5 text-xs" style={{ color: tokens.note }}>
            {model.footnotes.map((footnote) => (
              <li key={`${footnote.mark}${footnote.text}`}>
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
