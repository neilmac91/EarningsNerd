import type { Metadata } from 'next'
import AnalysisPageClient from '@/features/analysis/components/AnalysisPageClient'

export const metadata: Metadata = {
  title: 'Multi-Period Analysis | EarningsNerd',
  description:
    'Compare up to 10 fiscal years or 12 quarters of any US-listed company. Growth, margins, cash, and balance-sheet trends, with an AI analysis grounded in SEC XBRL.',
}

export default function AnalysisPage() {
  return <AnalysisPageClient />
}
