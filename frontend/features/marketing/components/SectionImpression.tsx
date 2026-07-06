'use client'

import { useEffect, useRef, type ReactNode } from 'react'

import analytics from '@/lib/analytics'

/**
 * Fires `homepage_section_viewed` once per pageview when ~30% of the wrapped section scrolls
 * into view — the per-section impression denominator the homepage-sections review found missing
 * (CTR was uncomputable with click-only events; findings §3).
 *
 * Server components pass their server-rendered content in as children, so wrapping adds a client
 * boundary without client-rendering the section itself. Must never throw: the homepage e2e spec
 * asserts zero page errors, so environments without IntersectionObserver just skip tracking.
 */
export default function SectionImpression({
  section,
  children,
}: {
  section: string
  children: ReactNode
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const fired = useRef(false)

  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return
    const node = ref.current
    if (!node) return

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting && !fired.current) {
            fired.current = true
            analytics.homepageSectionViewed(section)
            observer.disconnect()
          }
        }
      },
      { threshold: 0.3 }
    )
    observer.observe(node)
    return () => observer.disconnect()
  }, [section])

  return <div ref={ref}>{children}</div>
}
