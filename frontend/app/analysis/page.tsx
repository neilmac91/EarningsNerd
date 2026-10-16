import type { Metadata } from 'next'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'
import { ANALYSIS_MAX_ANNUAL_PERIODS, ANALYSIS_MAX_QUARTERLY_PERIODS } from '@/lib/planLimits'

export const metadata: Metadata = {
  title: 'Multi-Period Analysis | EarningsNerd',
  description:
    `Compare up to ${ANALYSIS_MAX_ANNUAL_PERIODS} fiscal years or ${ANALYSIS_MAX_QUARTERLY_PERIODS} quarters with source-linked figures, transparent calculations and AI-assisted commentary.`,
}

export default function AnalysisPage() {
  return (
    <div className="[container-type:inline-size]">
      <AnalysisPageClient />
    </div>
  )
}
