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
import('./TrendChartsV2').catch(() => {})

export default function TrendCharts({ dataset, exportEnabled = false }: { dataset: AnalysisDataset; exportEnabled?: boolean }) {
  return (
    <ChartErrorBoundary noun="charts">
      <TrendChartsV2 dataset={dataset} exportEnabled={exportEnabled} />
    </ChartErrorBoundary>
  )
}
