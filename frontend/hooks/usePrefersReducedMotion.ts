'use client'

/* =============================================================================
   usePrefersReducedMotion — hooks/usePrefersReducedMotion.ts
   -----------------------------------------------------------------------------
   THE shared reduced-motion check — replaces the inline matchMedia calls that
   used to live in ui/Chart.tsx. Live: re-renders when the OS setting flips
   mid-session. SSR snapshot is `false` (markup renders motion-capable; anything
   that must be correct without JS renders its final state regardless — see
   useCountUp, whose initial state IS the target value).
============================================================================= */

import { useSyncExternalStore } from 'react'

const QUERY = '(prefers-reduced-motion: reduce)'

function subscribe(onChange: () => void): () => void {
  const mql = window.matchMedia(QUERY)
  mql.addEventListener('change', onChange)
  return () => mql.removeEventListener('change', onChange)
}

export function usePrefersReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => window.matchMedia(QUERY).matches,
    () => false,
  )
}

/** Imperative check for non-component code paths. Prefer the hook in components. */
export function prefersReducedMotion(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(QUERY).matches
}
