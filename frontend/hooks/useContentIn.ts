'use client'

/* =============================================================================
   useContentIn — hooks/useContentIn.ts
   -----------------------------------------------------------------------------
   The skeleton→content handoff (DESIGN_SYSTEM.md §11), in one place: whatever
   replaces a skeleton (rows, an answer, a page's sections) crossfades in with
   animate-content-in (duration-base / ease-standard); reduced motion gets it at
   once. A view that never loaded paints without an entrance.
============================================================================= */

import { useState } from 'react'

export const CONTENT_IN = 'animate-content-in motion-reduce:animate-none'

/**
 * `CONTENT_IN` from the render where `loading` turns false until it turns true again, else
 * undefined. The flip is caught during render (React's "storing information from previous renders"),
 * not in an effect, so the class is on the same commit as the content: the content never paints
 * at full opacity for a frame before its fade starts.
 */
export function useContentIn(loading: boolean): string | undefined {
  const [flip, setFlip] = useState({ loading, entered: false })
  if (flip.loading !== loading) setFlip({ loading, entered: flip.loading && !loading })
  return flip.entered ? CONTENT_IN : undefined
}
