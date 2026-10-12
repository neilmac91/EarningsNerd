import type { Metadata } from 'next'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'

export const metadata: Metadata = {
  title: 'Multi-Period Analysis | EarningsNerd',
  description:
    'Compare up to 10 fiscal years or 12 quarters with source-linked figures, transparent calculations and AI-assisted commentary.',
}

export default function AnalysisPage() {
  return <AnalysisPageClient />
}
