'use client'

import { useEffect, useRef } from 'react'

/**
 * A link that names a section lands on it once that section exists: the company page's "Open change
 * report" opens /filing/{id}#what-changed, and the browser's own jump to the fragment runs before
 * the summary and its change report have rendered. `ids` is the page's section ids, space-joined.
 * Only the fragment the page was opened with counts, once: a section that appears later never moves
 * a reader who has scrolled on or followed a table-of-contents link.
 */
export function useSectionArrival(ids: string) {
  const target = useRef<string | null>(null)
  useEffect(() => {
    if (target.current === null) target.current = window.location.hash.slice(1)
    const id = target.current
    if (!id || !ids.split(' ').includes(id)) return
    target.current = ''
    document.getElementById(id)?.scrollIntoView({ block: 'start' })
  }, [ids])
}
