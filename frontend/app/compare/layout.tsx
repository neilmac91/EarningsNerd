import { notFound } from 'next/navigation'
import { ENABLE_COMPARE } from '@/lib/featureFlags'

/**
 * Gate for the Compare feature. When NEXT_PUBLIC_ENABLE_COMPARE is off, both /compare and
 * /compare/result 404 — so the feature is hidden even from direct URLs / bookmarks, not just
 * from the nav. Server component (build-time flag), so there's no client-side flash.
 */
export default function CompareLayout({ children }: { children: React.ReactNode }) {
  if (!ENABLE_COMPARE) {
    notFound()
  }
  return <>{children}</>
}
