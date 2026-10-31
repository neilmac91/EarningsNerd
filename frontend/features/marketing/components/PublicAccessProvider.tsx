'use client'

import { createContext, useContext, useEffect, useRef, type ReactNode } from 'react'
import { usePathname } from 'next/navigation'
import type { LegalReadiness } from '@/features/legal/api/legal-api'
import { useLegalReadiness } from '@/features/legal/hooks/useLegalReadiness'
import { publicAccessCopy, type AccessMode } from '@/features/marketing/lib/access'

const CHECKING = { readiness: null, loading: true }
const PublicReadiness = createContext<{ readiness: LegalReadiness | null; loading: boolean }>(CHECKING)

/** Presentation only. Collection forms retain their own fresh read and pre-submit recheck. */
export function PublicAccessProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname()
  const { readiness, loading, recheck } = useLegalReadiness()
  const previousPath = useRef(pathname)

  useEffect(() => {
    if (previousPath.current !== pathname) {
      previousPath.current = pathname
      void recheck()
    }
    // A tab returning to the site must not keep an earlier open-intake promise indefinitely.
    const onFocus = () => { void recheck() }
    window.addEventListener('focus', onFocus)
    return () => {
      window.removeEventListener('focus', onFocus)
    }
  }, [pathname, recheck])

  // The hook retains its last answer during background reads and rejects stale responses.
  // Only the first read shows checking; forms separately enforce fresh admission before sending.
  return (
    <PublicReadiness.Provider value={loading ? CHECKING : { readiness, loading: false }}>
      {children}
    </PublicReadiness.Provider>
  )
}

export const usePublicReadiness = () => useContext(PublicReadiness)

export function usePublicAccess(mode: AccessMode) {
  const { readiness, loading } = usePublicReadiness()
  return publicAccessCopy(mode, readiness, loading)
}
