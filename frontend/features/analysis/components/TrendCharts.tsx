'use client'

import dynamic from 'next/dynamic'

import { ChartErrorBoundary } from '@/components/ChartErrorBoundary'
import type { AnalysisDataset } from '@/features/analysis/api/analysis-api'
import { TrendChartsSkeleton } from './TrendChartBones'

/** The four trend charts (the spec renderer, E192–E195), their own chunk. */
const TrendChartsV2 = dynamic(() => import('./TrendChartsV2'), {
  loading: ({ error }) => {
    if (error) throw error
    return <TrendChartsSkeleton />
  },
})
// The chunk starts loading with this module, before a run's results ask for it; a failure is reported where it
// counts, when the grid's own load throws it to the boundary. The module is named twice, not through one shared
// function, because on a server render Next preloads a dynamic() chunk only when its import() is written inside the
// call (its lazy-loading guide).
import('./TrendChartsV2').catch(() => {})

export default function TrendCharts({ dataset, exportEnabled = false }: { dataset: AnalysisDataset; exportEnabled?: boolean }) {
  return (
    <ChartErrorBoundary noun="charts">
      <TrendChartsV2 dataset={dataset} exportEnabled={exportEnabled} />
    </ChartErrorBoundary>
  )
}
