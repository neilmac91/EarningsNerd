'use client'

import PeekLocked from '@/features/subscriptions/components/PeekLocked'
import KpiStrip from './KpiStrip'
import MetricsTable from './MetricsTable'
import NarrativePane from './NarrativePane'
import TrendCharts from './TrendCharts'
import DataNotes from './DataNotes'
import { DataNotesProvider } from './DataNotesContext'
import demo from '../demo/demo-analysis.json'
import type { AnalysisCompletion, AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { formatAnalysisWindow } from '@/features/analysis/lib/periodLabels'
import { formatCompanyName } from '@/lib/formatCompanyName'

const demoDataset = demo.dataset as unknown as AnalysisDataset
const demoCompletion = demo.completion as unknown as AnalysisCompletion
// The company the sample covers, in its display form, and the window, both read from the run itself (as the landing's
// AnalysisDemo reads them).
const SAMPLE_COMPANY = formatCompanyName(demoDataset.company_name)
const SAMPLE_RANGE = formatAnalysisWindow(demoDataset.periods[0]?.key ?? '', demoDataset.periods[demoDataset.periods.length - 1]?.key ?? '')

/**
 * The free-user teaser (D6): the REAL results experience — KPI strip, charts, metrics grid,
 * narrative with verified citations — rendered from a checked-in sample payload behind
 * PeekLocked: one saved run of the pipeline, its figures, data notes and narrative unedited (D-046).
 * Zero backend/AI cost for free users; the blur shows exactly what Pro unlocks. The preview shows about one
 * screen of the run, the KPI strip and the top of the results, with the upgrade action centred there (E139;
 * tests/e2e/analysis-teaser-window.spec.ts).
 */
export default function AnalysisTeaser({ forTicker }: { forTicker?: string }) {
  return (
    <div data-analysis-teaser className="flex flex-col gap-3">
      <p className="text-sm text-text-secondary-light dark:text-text-secondary-dark">
        Sample: {SAMPLE_COMPANY} ({demoDataset.ticker}), {SAMPLE_RANGE}
        {forTicker ? `. Upgrade to run it for ${forTicker.toUpperCase()}` : ''}.
      </p>
      <PeekLocked feature="Multi-Period Analysis" preview="screen">
        <DataNotesProvider dataset={demoDataset}>
          {/* The page's module gaps, 16px on a phone and 24px from sm. The caption above names the sample, so the
              preview takes no results header: it would repeat the caption, blurred, and a sample has no live date. */}
          <div className="flex flex-col gap-4 sm:gap-6">
            <KpiStrip dataset={demoDataset} />
            <TrendCharts dataset={demoDataset} />
            <NarrativePane
              state={{ status: 'done', text: demoCompletion.narrative, completion: demoCompletion }}
              sample
            />
            {/* The table's fine print sits 8px under it, as on the page. */}
            <div className="flex flex-col gap-2">
              <MetricsTable dataset={demoDataset} />
              <DataNotes dataset={demoDataset} sample />
            </div>
          </div>
        </DataNotesProvider>
      </PeekLocked>
    </div>
  )
}
