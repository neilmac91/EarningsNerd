'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from './cx'

/**
 * The brand device's margin (DESIGN.md › Graphic device; DESIGN_SYSTEM.md §7): a gutter with a
 * hairline on its inner edge, holding a twin of every bracketed marker in the content
 * (`[data-en-ref]` elements), each positioned on the line its marker sits on. The content is passed
 * in as children; this boundary only measures. Twins are decorative (`aria-hidden`): the in-text
 * marker is the accessible one. Before the first measurement (and under SSR) the gutter is empty
 * and the content is unchanged, so nothing depends on it; where `ResizeObserver` is missing the
 * twins are placed once and not re-measured. A twin is anchored at its marker's measured midpoint
 * and centred on it by `.en-margin-mark`'s own `translateY(-50%)`, so it stays on its line whatever
 * height the twin renders at, a 200% root font included.
 *
 * Two features render it, which is why it lives here: the landing's evidence row
 * (features/marketing HeroExample) and the filing page's Risks section (features/summaries
 * SummaryRisks), each only around a passage the server located (D-044; the places are pinned in
 * tests/unit/brandCopyRules.spec.ts rule 3). Ask answers and the Multi-Period narrative keep their
 * citation chips: a cited line carries several markers there, and their twins would overprint.
 */
export function MarkedCopy({ children, className }: { children: ReactNode; className?: string }) {
  const bodyRef = useRef<HTMLDivElement | null>(null)
  const [marks, setMarks] = useState<{ key: string; label: string; top: number }[]>([])

  useEffect(() => {
    const body = bodyRef.current
    if (!body) return
    const measure = () => {
      const base = body.getBoundingClientRect().top
      const next = Array.from(body.querySelectorAll<HTMLElement>('[data-en-ref]')).map((el, index) => {
        const rect = el.getBoundingClientRect()
        return { key: `${index}-${el.dataset.enRef}`, label: el.dataset.enRef ?? el.textContent ?? '', top: rect.top - base + rect.height / 2 }
      })
      setMarks(next)
    }
    measure()
    if (typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(measure)
    observer.observe(body)
    return () => observer.disconnect()
  }, [children])

  return (
    <div className={cx('grid grid-cols-[2.25rem_minmax(0,1fr)] sm:grid-cols-[2.75rem_minmax(0,1fr)]', className)}>
      <div aria-hidden="true" className="en-margin">
        {marks.map((mark) => (
          <span key={mark.key} className="en-margin-mark" style={{ top: `${mark.top}px` }}>
            {mark.label}
          </span>
        ))}
      </div>
      <div ref={bodyRef} className="min-w-0">
        {children}
      </div>
    </div>
  )
}

/** An in-text marker: the product's citation form (data face, semibold, brackets) at the
 *  provenance chip's 12px, with the `data-en-ref` hook the margin twins. The label is the
 *  accessible text; the 11px twin in the margin is decorative. */
export function EnRef({ label, className }: { label: string; className?: string }) {
  return (
    <span data-en-ref={label} className={cx('ml-0.5 font-data text-xs font-semibold text-brand-strong dark:text-brand-strong-dark', className)}>
      {label}
    </span>
  )
}
