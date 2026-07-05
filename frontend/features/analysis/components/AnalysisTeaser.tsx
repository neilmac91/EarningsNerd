'use client'

import PeekLocked from '@/components/PeekLocked'
import KpiStrip from './KpiStrip'
import MetricsTable from './MetricsTable'
import NarrativePane from './NarrativePane'
import TrendCharts from './TrendCharts'
import demo from '../demo/demo-analysis.json'
import type { AnalysisCompletion, AnalysisDataset } from '@/features/analysis/api/analysis-api'

const demoDataset = demo.dataset as unknown as AnalysisDataset
const demoCompletion = demo.completion as unknown as AnalysisCompletion

/**
 * The free-user teaser (D6): the REAL results experience — KPI strip, charts, metrics grid,
 * narrative with verified citations — rendered from a checked-in sample payload behind
 * PeekLocked. Zero backend/AI cost for free users; the blur shows exactly what Pro unlocks.
 */
export default function AnalysisTeaser({ forTicker }: { forTicker?: string }) {
  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Sample: Apple Inc. (AAPL), FY2019–FY2024
        {forTicker ? ` — upgrade to run it for ${forTicker.toUpperCase()}` : ''}.
      </p>
      <PeekLocked feature="Multi-Period Analysis">
        <div className="flex flex-col gap-4">
          <KpiStrip dataset={demoDataset} />
          <TrendCharts dataset={demoDataset} />
          <NarrativePane
            state={{ status: 'done', text: demoCompletion.narrative, completion: demoCompletion }}
          />
          <MetricsTable dataset={demoDataset} />
        </div>
      </PeekLocked>
    </div>
  )
}
