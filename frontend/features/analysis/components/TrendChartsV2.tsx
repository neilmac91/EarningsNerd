'use client'
/**
 * The four trend charts under the spec renderer (CHARTS_V2; E192). Every chart keeps its card, a chart that does not
 * apply saying why at full height (spec §3.4), where today's Recharts grid drops it. TrendCharts loads this module only
 * while the flag is on, inside the grid's ChartErrorBoundary, which it holds outside this chunk.
 */
import { useEffect, useState } from 'react'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { CHART_IDS } from '@/features/analysis/lib/charts/model'
import { useDataNotes } from './DataNotesContext'
import TrendChartCard from './TrendChartCard'

/** G4's wait: the font the plan's widths assume (layout.ts ADVANCE), or this long, whichever comes first. */
const CHART_FACE = '11px "Geist Mono"'
const FONT_WAIT_MS = 1500

/** Spec G4: the plots paint once Geist Mono has loaded, or after 1,500 ms, so no text paints at the planner's
 *  positions in a fallback face of other widths. Until then each card holds its plot's exact box, on the server and
 *  through hydration (D9). A browser without the Font Loading API paints at once. */
function useChartFont() {
  const [ready, setReady] = useState(false)
  useEffect(() => {
    const fonts = typeof document === 'undefined' ? undefined : document.fonts
    if (!fonts?.load || fonts.check(CHART_FACE)) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- mount-time latch: the server and hydration hold the plot's box, the client paints after
      setReady(true)
      return
    }
    let live = true
    const done = () => { if (live) setReady(true) }
    const timer = window.setTimeout(done, FONT_WAIT_MS)
    fonts.load(CHART_FACE).then(done, done)
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
