import { notFound } from 'next/navigation'
import { ENABLE_FILING_REDLINES } from '@/lib/featureFlags'

export default function FilingRedlinesLayout({ children }: { children: React.ReactNode }) {
  if (!ENABLE_FILING_REDLINES) notFound()
  return <>{children}</>
}
