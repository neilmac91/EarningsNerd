'use client'

import { useEffect, useRef, useState, type ReactNode } from 'react'
import { cx } from './cx'
import { markedCopyColumnsClass, markedMarginCollapseClass } from './markedCopyLayout'

/**
 * The brand device's margin (DESIGN.md › Graphic device; DESIGN_SYSTEM.md §7): a gutter with a
 * hairline on its inner edge, holding a twin of every bracketed marker in the content
 * (`[data-en-ref]` elements), each positioned on the line its marker sits on. The content is passed
 * in as children; this boundary only measures. Twins are decorative (`aria-hidden`), and so is the
 * in-text marker (EnRef): the chip beside the passage carries the claim. Before the first
 * measurement (and under SSR) the gutter is empty
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
 *
 * Below a measure, the margin goes. Its column and a row's inset are rem, so they double with the
 * reader's text: at 320px under 200% text they left a Risks excerpt 101px of 32px serif, and about a
 * third of its words broke mid-word. So the root is a query container, in em, which follows the text
 * size where `sm:` or a rem column cannot: narrower than 13em, the margin and its twins give way and
 * the rows drop their inset (markedCopyLayout.ts), while the marker in the heading stays. 13em is the
 * middle of the measured window. The margin stays at the default size on a 320px phone: this copy is
 * 18em wide on the filing page there and 15.4em in the landing's card. It goes under 200% text at
 * 390px and below: 10.2em and 7.6em at 390, 8em and 5.4em at 320, where giving it up leaves the
 * excerpt 197px of serif and no word breaks. A word still longer than the measure breaks inside the
 * marked block (`.en-marked`): at a hyphen where the browser hyphenates, anywhere where it cannot.
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
    <div className={cx('[container-type:inline-size]', className)}>
      <div className={markedCopyColumnsClass}>
        <div aria-hidden="true" className={cx('en-margin', markedMarginCollapseClass)}>
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
    </div>
  )
}

/** An in-text marker: the product's citation form (data face, semibold, brackets) at the
 *  provenance chip's 12px, with the `data-en-ref` hook the margin twins. Hidden from assistive
 *  tech, as its 11px twin is: the number points at a twin it never reaches, and the chip beside
 *  the passage says what was located ("Verified in filing", "Located in the filing"), so a
 *  heading's name reads as its words alone, never "…their components…[1]". */
export function EnRef({ label, className }: { label: string; className?: string }) {
  return (
    <span data-en-ref={label} aria-hidden="true" className={cx('ml-0.5 font-data text-xs font-semibold text-brand-strong dark:text-brand-strong-dark', className)}>
      {label}
    </span>
  )
}
