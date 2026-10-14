import { notFound } from 'next/navigation'
import { ENABLE_FINANCIAL_REFRESH_REVIEW } from '@/lib/featureFlags'

export default function FinancialRefreshReviewLayout({ children }: { children: React.ReactNode }) {
  if (!ENABLE_FINANCIAL_REFRESH_REVIEW) notFound()
  return <>{children}</>
}
