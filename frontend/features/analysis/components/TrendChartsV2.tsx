'use client'
/**
 * The four trend charts under the spec renderer (E192; the analysis route's only renderer since E195). Every chart keeps
 * its card, a chart that does not apply saying why at full height (spec §3.4), where the Recharts grid before it dropped
 * the card. Each card spans three of the grid's rows as a subgrid (TrendChartCard, E193), so a row's plots start at one
 * height. TrendCharts loads this module as its own chunk, inside the grid's ChartErrorBoundary, which it holds outside
 * this chunk. The plots wait for their font together (useChartFont, G4).
 */
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { CHART_IDS } from '@/features/analysis/lib/charts/model'
import { useDataNotes } from './DataNotesContext'
import TrendChartCard from './TrendChartCard'
import { useChartFont } from './useChartFont'

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
