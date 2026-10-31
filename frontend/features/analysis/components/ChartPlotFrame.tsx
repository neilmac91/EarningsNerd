'use client'
/**
 * A chart's plot under the spec renderer, for any card that draws one (E195 (D)): the plan laid out at the width
 * TrendChartPlot measures (the server and the first render plan at the desktop card's, spec §3.12), the plot, or for a
 * chart that does not apply its sentence at the card's height (§3.4), and the line a labelled panel without a label tier
 * prints (A4). The caller places those pieces, so TrendChartCard keeps its subgrid's rows (E193), and marks its card
 * aria-busy while the plot waits for its font (G4): the plot's bones are TrendChartPlot's own.
 */
import { useCallback, useId, useMemo, useRef, useState, type ReactNode, type RefObject } from 'react'
import { CARD_HEIGHT, layoutChart, VALUES_DONT_FIT, type ChartLayout } from '@/features/analysis/lib/charts/layout'
import type { ChartModel, ChartView } from '@/features/analysis/lib/charts/model'
import type { PeriodReadout } from '@/features/analysis/lib/charts/readout'
import type { ChartTokens } from '@/features/analysis/lib/charts/theme'
import TrendChartPlot from './TrendChartPlot'

/** The server and the first render plan at the desktop card's width (§3.12) until the plot is measured. */
const DEFAULT_WIDTH = 502

export interface ChartFrame {
  /** The plan, or null for a chart that does not apply. */
  layout: ChartLayout | null
  /** The plot, or the sentence saying why there is none at the card's height. */
  plot: ReactNode
  /** VALUES_DONT_FIT, where a labelled panel found no label tier (A4); null otherwise. */
  fit: ReactNode
  /** The plot waits for its font (G4): its card is aria-busy. */
  busy: boolean
}

export default function ChartPlotFrame({ model, readouts, tokens, fontReady, view, plotRef, children }: {
  model: ChartModel
  readouts: PeriodReadout[]
  tokens: ChartTokens
  /** Spec G4: the plot paints once its font has loaded (useChartFont); until then it holds its box. */
  fontReady: boolean
  view: ChartView
  /** The node the PNG export serialises, for a card that offers one. */
  plotRef?: RefObject<HTMLDivElement>
  children: (frame: ChartFrame) => ReactNode
}) {
  const [width, setWidth] = useState(DEFAULT_WIDTH)
  const ownRef = useRef<HTMLDivElement>(null)
  const onWidth = useCallback((measured: number) => setWidth(measured), [])
  const uid = `chart${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
  const layout = useMemo(() => (model.unavailable ? null : layoutChart(model, width, view)), [model, width, view])
  const plot = layout ? (
    <TrendChartPlot model={model} layout={layout} readouts={readouts} tokens={tokens} fontReady={fontReady} uid={uid} view={view}
      plotRef={plotRef ?? ownRef} onWidth={onWidth} />
  ) : (
    <div className="flex items-center justify-center px-4 text-center text-sm" style={{ height: CARD_HEIGHT, color: tokens.note }} data-chart-text="unavailable">
      {model.unavailable}
    </div>
  )
  const fit = layout?.valuesDontFit ? <p className="mt-2 text-xs" style={{ color: tokens.note }} data-chart-text="fit">{VALUES_DONT_FIT}</p> : null
  return children({ layout, plot, fit, busy: layout != null && !fontReady })
}
