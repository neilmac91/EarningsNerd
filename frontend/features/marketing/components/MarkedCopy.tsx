'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from '@/components/ui'

/**
 * The brand device's margin (DESIGN.md › Graphic device; DESIGN_SYSTEM.md §7): a gutter with a
 * hairline on its inner edge, holding a twin of every bracketed marker in the content
 * (`[data-en-ref]` elements), each positioned on the line its marker sits on. The content is
 * server-rendered and passed in as children; this boundary only measures. Twins are decorative
 * (`aria-hidden`): the in-text marker is the accessible one. Under SSR, before layout, and in an
 * environment without `ResizeObserver` (the unit tests), the gutter renders empty and the content
 * is unchanged, so nothing depends on the measurement.
 */
export default function MarkedCopy({ children, className }: { children: ReactNode; className?: string }) {
  const bodyRef = useRef<HTMLDivElement | null>(null)
  const [marks, setMarks] = useState<{ key: string; label: string; top: number }[]>([])

  useEffect(() => {
    const body = bodyRef.current
    if (!body) return
    const measure = () => {
      const base = body.getBoundingClientRect().top
      const next = Array.from(body.querySelectorAll<HTMLElement>('[data-en-ref]')).map((el, index) => {
        const rect = el.getBoundingClientRect()
        return { key: `${index}-${el.dataset.enRef}`, label: el.dataset.enRef ?? el.textContent ?? '', top: rect.top - base + (rect.height - 16) / 2 }
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

/** An in-text marker: the product's citation form (data face, semibold, brackets) with the
 *  `data-en-ref` hook the margin twins. The label is the accessible text. */
export function EnRef({ label, className }: { label: string; className?: string }) {
  return (
    <span data-en-ref={label} className={cx('ml-0.5 font-data text-data-xs font-semibold text-brand-strong dark:text-brand-strong-dark', className)}>
      {label}
    </span>
  )
}
