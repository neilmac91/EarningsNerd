'use client'

import { useEffect, useState } from 'react'

/**
 * Reactive CSS media-query match. SSR-safe: returns `false` until mounted (keeps server markup
 * deterministic), then tracks the live `matchMedia` result. `enabled=false` opts out entirely
 * (stays `false`), e.g. when a component is in a layout where the query is irrelevant.
 */
export function useMediaQuery(query: string, enabled = true): boolean {
  const [matches, setMatches] = useState(false)

  useEffect(() => {
    if (!enabled) return
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia(query)
    const apply = () => setMatches(mql.matches)
    apply()
    mql.addEventListener('change', apply)
    return () => mql.removeEventListener('change', apply)
  }, [query, enabled])

  return enabled ? matches : false
}

export default useMediaQuery
