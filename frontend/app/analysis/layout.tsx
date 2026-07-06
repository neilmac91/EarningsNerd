import { notFound } from 'next/navigation'
import { ENABLE_ANALYSIS } from '@/lib/featureFlags'

/**
 * Gate for Multi-Period Analysis. When NEXT_PUBLIC_ENABLE_ANALYSIS is off, /analysis 404s — so
 * the feature is hidden even from direct URLs / bookmarks, not just from the nav. Server
 * component (build-time flag), so there's no client-side flash.
 */
export default function AnalysisLayout({ children }: { children: React.ReactNode }) {
  if (!ENABLE_ANALYSIS) {
    notFound()
  }
  return <>{children}</>
}
