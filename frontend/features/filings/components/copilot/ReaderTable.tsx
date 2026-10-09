'use client'

import { useEffect, useRef, useState, type ComponentProps } from 'react'

type MdExtra = { node?: unknown }

const headingText = (el: Element) => (/^H[1-6]$/.test(el.tagName) ? (el.textContent?.trim() ?? '') : '')
const isTableBox = (el: Element) => el.classList.contains('filing-table-scroll')

/**
 * A scrolling table's region name: the filing section it sits under, when a heading precedes it. A
 * section with more than one table numbers them ("table 2 of 3"): statements often share one heading,
 * and two regions with one name cannot be told apart in a landmark list.
 */
export function regionName(box: HTMLElement): string {
  let heading = ''
  let index = 1
  for (let el = box.previousElementSibling; el && !heading; el = el.previousElementSibling) {
    heading = headingText(el)
    if (!heading && isTableBox(el)) index++
  }
  let count = index
  for (let el = box.nextElementSibling; el && !headingText(el); el = el.nextElementSibling) {
    if (isTableBox(el)) count++
  }
  const name = heading ? `Scrollable table: ${heading}` : 'Scrollable table'
  return count > 1 ? `${name}, table ${index} of ${count}` : name
}

/**
 * A table in the in-app filing reader (EN-04). Each one sits in a horizontal scroll box of its own,
 * so a statement wider than the pane scrolls inside that box instead of widening the reader (which
 * spilled out of its pane: the page scrolled sideways on a desktop, the phone sheet clipped it).
 *
 * While, and only while, the table is wider than its box, the box is a named region in the tab
 * order, so a keyboard user can reach it and scroll it with the arrow keys; a table that fits stays
 * out of the tab order and unnamed. The box measures itself whenever it or its table changes size: a
 * pane resize, the web font arriving, the Filing tab shown again after being hidden.
 */
export default function ReaderTable({ node: _n, ...rest }: ComponentProps<'table'> & MdExtra) {
  const boxRef = useRef<HTMLDivElement>(null)
  const [name, setName] = useState<string | null>(null)

  useEffect(() => {
    const box = boxRef.current
    if (!box || typeof ResizeObserver === 'undefined') return
    const observer = new ResizeObserver(() => setName(box.scrollWidth > box.clientWidth ? regionName(box) : null))
    observer.observe(box)
    if (box.firstElementChild) observer.observe(box.firstElementChild)
    return () => observer.disconnect()
  }, [])

  return (
    <div
      ref={boxRef}
      className="filing-table-scroll overflow-x-auto rounded focus-visible:outline-none focus-visible:shadow-ring-brand dark:focus-visible:shadow-ring-brand-dark"
      {...(name ? { role: 'region', 'aria-label': name, tabIndex: 0 } : {})}
    >
      <table {...rest} />
    </div>
  )
}
