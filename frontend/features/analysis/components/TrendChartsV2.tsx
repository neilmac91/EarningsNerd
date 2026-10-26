'use client'
/**
 * The four trend charts under the spec renderer (CHARTS_V2; E192). Every chart keeps its card, a chart that does not
 * apply saying why at full height (spec §3.4), where today's Recharts grid drops it. Each card spans three of the grid's
 * rows as a subgrid (TrendChartCard, E193), so a row's plots start at one height. TrendCharts loads this module only
 * while the flag is on, inside the grid's ChartErrorBoundary, which it holds outside this chunk.
 */
import { useEffect, useState } from 'react'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { CHART_IDS } from '@/features/analysis/lib/charts/model'
import { useDataNotes } from './DataNotesContext'
import TrendChartCard from './TrendChartCard'

/** G4's wait: the font the plan's widths assume (layout.ts ADVANCE), or this long, whichever comes first. */
const CHART_FACE = '11px "Geist Mono"'
/** The text the wait loads and checks the face for. The Font Loading API picks a family's faces by their
 *  unicode-range, and with no text it takes a space, so the latin face alone; no route preloads latin-ext (app/fonts.ts,
 *  spec §0.5). So the sample names the latin face ("0") and every glyph past it that the plot can print and Geist Mono
 *  draws, all in latin-ext: † (G2) and the ₹, ₪ and ₱ that moneyPrefix prints. Geist Mono has no ₩ or ₫, so
 *  moneyPrefix prints KRW's and VND's codes instead (E203). */
const CHART_TEXT = '0†₹₪₱'
const FONT_WAIT_MS = 1500

/** Spec G4: the plots paint once Geist Mono's latin and latin-ext faces have loaded, or after 1,500 ms, so no text
 *  paints at the planner's positions in a fallback face, and † never swaps after a plot's first paint (G3). Until then
 *  each card holds its plot's exact box, on the server and through hydration (D9). A browser without the Font Loading
 *  API paints at once. */
function useChartFont() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const fonts = typeof document === 'undefined' ? undefined : document.fonts
    if (!fonts?.load || fonts.check(CHART_FACE, CHART_TEXT)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time latch: the server and hydration hold the plot's box, the client paints after
      setReady(true)
      return
    }
    let live = true
    const done = () => { if (live) setReady(true) }
    const timer = window.setTimeout(done, FONT_WAIT_MS)
    fonts.load(CHART_FACE, CHART_TEXT).then(done, done)
    return () => {
      live = false
      window.clearTimeout(timer)
    }
  }, [])
  return ready
}

export default function TrendChartsV2({ dataset, exportEnabled = false }: { dataset: AnalysisDataset; exportEnabled?: boolean }) {
  const notes = useDataNotes(dataset)
  const fontReady = useChartFont()
  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      {CHART_IDS.map((chart) => (
        <TrendChartCard key={chart} chart={chart} dataset={dataset} notes={notes} exportEnabled={exportEnabled} fontReady={fontReady} />
      ))}
    </div>
  )
}
