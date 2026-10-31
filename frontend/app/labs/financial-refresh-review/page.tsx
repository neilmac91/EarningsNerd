import type { Metadata } from 'next'
import { FinancialRefreshReview } from '@/features/financial-refresh-review/components/FinancialRefreshReview'

export const metadata: Metadata = {
  title: 'Financial refresh review prototype | EarningsNerd',
  robots: { index: false, follow: false },
}

export default function FinancialRefreshReviewPage() {
  return <FinancialRefreshReview />
}
