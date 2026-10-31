import type { Metadata } from 'next'
import FilingRedlines from '@/features/filing-redlines/components/FilingRedlines'

export const metadata: Metadata = {
  title: 'Filing redlines prototype | EarningsNerd',
  description: 'Explore exact paragraph changes between two annual filings.',
  robots: { index: false, follow: false },
}

export default function FilingRedlinesPage() {
  return <FilingRedlines />
}
