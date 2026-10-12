'use client'

import { useEffect, useRef, useState, type ComponentProps } from 'react'

type MdExtra = { node?: unknown }

const headingText = (el: Element) => (/^H[1-6]$/.test(el.tagName) ? (el.textContent?.trim() ?? '') : '')
const isTableBox = (el: Element) => el.classList.contains('filing-table-scroll')

/**
 * A scrolling table's region name: the filing section it sits under, when a heading precedes it.
 * Tables whose headings read the same are numbered across the reader ("table 2 of 3"): statements
 * often share one heading, notes repeat a heading's text ("Revenue"), and two regions with one name
 * cannot be told apart in a landmark list.
 */
export function regionName(box: HTMLElement): string {
  // One pass over the reader's headings and table boxes in document order. The heading a table sits
  // under is the last one before it whose own container also holds the table: a heading inside a
  // blockquote or list item names that container's tables only, and the section's heading applies
  // again after it.
  const root = box.closest('.filing-reader') ?? box.parentElement ?? box
  const headings: Element[] = []
  const tables: Array<[Element, string]> = []
  for (const el of Array.from(root.querySelectorAll('h1, h2, h3, h4, h5, h6, .filing-table-scroll'))) {
    if (headingText(el)) headings.push(el)
    else if (isTableBox(el)) {
      let scope = ''
      for (let i = headings.length - 1; i >= 0 && !scope; i--) {
        if (headings[i].parentElement?.contains(el)) scope = headingText(headings[i])
      }
      tables.push([el, scope])
    }
  }
  const heading = tables.find(([el]) => el === box)?.[1] ?? ''
  const peers = tables.filter(([, text]) => text === heading).map(([el]) => el)
  const name = heading ? `Scrollable table: ${heading}` : 'Scrollable table'
  return peers.length > 1 ? `${name}, table ${peers.indexOf(box) + 1} of ${peers.length}` : name
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
    // The box names itself only when it starts to overflow, not on every notification: the reader's
    // headings and tables are fixed for its content, and regionName scans the whole reader, so with every
    // table's observer firing on each frame of a pane drag a long filing cost O(tables x (headings +
    // tables)) per frame.
    let overflowing = false
    const observer = new ResizeObserver(() => {
      const overflows = box.scrollWidth > box.clientWidth
      if (overflows === overflowing) return
      overflowing = overflows
      setName(overflows ? regionName(box) : null)
    })
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
