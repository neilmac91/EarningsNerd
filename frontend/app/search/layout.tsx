import { notFound } from 'next/navigation'
import { ENABLE_FULLTEXT_SEARCH } from '@/lib/featureFlags'

/**
 * Gate for full-text filing search. When NEXT_PUBLIC_ENABLE_FULLTEXT_SEARCH is off, /search 404s —
 * so the feature is hidden even from direct URLs / bookmarks, not just from the nav. Server
 * component (build-time flag), so there's no client-side flash. Same pattern as ENABLE_ANALYSIS.
 */
export default function SearchLayout({ children }: { children: React.ReactNode }) {
  if (!ENABLE_FULLTEXT_SEARCH) {
    notFound()
  }
  return <>{children}</>
}
