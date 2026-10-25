'use client'

import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react'
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
  const [confirmedPath, setConfirmedPath] = useState(pathname)
  const [refreshing, setRefreshing] = useState(false)
  const previousPath = useRef(pathname)
  const sequence = useRef(0)

  const refresh = useCallback(async () => {
    const request = ++sequence.current
    setRefreshing(true)
    await recheck()
    if (request !== sequence.current) return
    setConfirmedPath(pathname)
    setRefreshing(false)
  }, [pathname, recheck])

  useEffect(() => {
    if (previousPath.current !== pathname) {
      previousPath.current = pathname
      void refresh()
    }
    // A tab returning to the site must not keep an earlier open-intake promise indefinitely.
    const onFocus = () => { void refresh() }
    window.addEventListener('focus', onFocus)
    return () => {
      sequence.current += 1
      window.removeEventListener('focus', onFocus)
    }
  }, [pathname, refresh])

  const checking = loading || refreshing || confirmedPath !== pathname
  return (
    <PublicReadiness.Provider value={checking ? CHECKING : { readiness, loading: false }}>
      {children}
    </PublicReadiness.Provider>
  )
}

export const usePublicReadiness = () => useContext(PublicReadiness)

export function usePublicAccess(mode: AccessMode) {
  const { readiness, loading } = usePublicReadiness()
  return publicAccessCopy(mode, readiness, loading)
}
