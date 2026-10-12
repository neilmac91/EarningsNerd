import { describe, it, expect, vi, afterEach } from 'vitest'
import { createElement } from 'react'
import { act, render } from '@testing-library/react'
import ReaderTable, { regionName } from '@/features/filings/components/copilot/ReaderTable'

// A filing-reader table that scrolls is a named region (EN-04). Its name is the section it sits
// under; statements often share one heading, and notes repeat a heading's text, so tables whose
// headings read the same are numbered across the reader, and no two regions share a name.
describe('ReaderTable regionName', () => {
  function reader(html: string) {
    const el = document.createElement('div')
    el.className = 'filing-reader'
    el.innerHTML = html
    return Array.from(el.querySelectorAll<HTMLElement>('.filing-table-scroll'))
  }
  const box = '<div class="filing-table-scroll"><table></table></div>'

  it('names a section\'s only table after its heading, and numbers tables that share one', () => {
    const boxes = reader(
      `${box}<p>Before any heading.</p>${box}` +
        `<h2>Item 7. MD&amp;A</h2><p>Segments.</p>${box}` +
        `<h2>Item 8. Financial Statements</h2><p><strong>Operations</strong></p>${box}<p>Balance sheet</p>${box}<h3></h3>${box}` +
        `<h3>Note 2 – Revenue</h3>${box}`,
    )
    expect(boxes.map(regionName)).toEqual([
      'Scrollable table, table 1 of 2',
      'Scrollable table, table 2 of 2',
      'Scrollable table: Item 7. MD&A',
      // An empty heading is not a section break.
      'Scrollable table: Item 8. Financial Statements, table 1 of 3',
      'Scrollable table: Item 8. Financial Statements, table 2 of 3',
      'Scrollable table: Item 8. Financial Statements, table 3 of 3',
      'Scrollable table: Note 2 – Revenue',
    ])
  })

  it('numbers tables across sections whose headings read the same, so their regions still differ', () => {
    // Two notes both headed "Revenue", one table each: per-section numbering alone named both
    // "Scrollable table: Revenue", and a landmark list could not tell them apart.
    const boxes = reader(
      `<h3>Revenue</h3>${box}<h3>Leases</h3>${box}<h3>Revenue</h3><p>Disaggregated.</p>${box}${box}`,
    )
    expect(boxes.map(regionName)).toEqual([
      'Scrollable table: Revenue, table 1 of 3',
      'Scrollable table: Leases',
      'Scrollable table: Revenue, table 2 of 3',
      'Scrollable table: Revenue, table 3 of 3',
    ])
  })

  it('reads headings and tables in document order across the reader, not only among siblings', () => {
    // react-markdown renders a blockquote's heading and table inside the <blockquote>: a sibling
    // scan named both tables "Scrollable table: Revenue".
    const boxes = reader(
      `<blockquote><h3>Revenue</h3>${box}</blockquote><blockquote><h3>Revenue</h3>${box}</blockquote>` +
        `<h3>Leases</h3><blockquote>${box}</blockquote>`,
    )
    expect(boxes.map(regionName)).toEqual([
      'Scrollable table: Revenue, table 1 of 2',
      'Scrollable table: Revenue, table 2 of 2',
      'Scrollable table: Leases',
    ])
  })

  it('a heading names only the tables in its own container: a quoted heading does not leak to the tables after the quote', () => {
    const boxes = reader(
      `<h2>Item 8</h2><blockquote><h3>Quoted note</h3>${box}</blockquote>${box}` +
        `<ul><li><h4>Listed</h4></li><li>${box}</li></ul>`,
    )
    expect(boxes.map(regionName)).toEqual([
      'Scrollable table: Quoted note',
      // Back outside the quote, the enclosing section's heading applies again.
      'Scrollable table: Item 8, table 1 of 2',
      // A list item's heading does not reach into the next item.
      'Scrollable table: Item 8, table 2 of 2',
    ])
  })
})

// regionName scans the whole reader, and on a pane drag every table's observer fires each frame: a box
// names itself when it starts to overflow and drops the name when it fits, never on a resize that
// leaves it as it was.
describe('ReaderTable naming', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('scans the reader once per overflow change, not on every resize', () => {
    let notify = () => {}
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { notify = callback }
      observe() {}
      disconnect() {}
    })
    const { container } = render(
      createElement('div', { className: 'filing-reader' }, createElement('h2', null, 'Item 8'), createElement(ReaderTable, null, createElement('tbody'))),
    )
    const box = container.querySelector<HTMLElement>('.filing-table-scroll')!
    const widths = (scroll: number) => {
      Object.defineProperty(box, 'scrollWidth', { configurable: true, value: scroll })
      Object.defineProperty(box, 'clientWidth', { configurable: true, value: 400 })
    }
    const scans = vi.spyOn(Element.prototype, 'querySelectorAll')
    const resize = () => act(() => notify())

    widths(900)
    resize()
    resize()
    resize()
    expect(box).toHaveAttribute('aria-label', 'Scrollable table: Item 8')
    expect(scans).toHaveBeenCalledTimes(1)

    widths(400)
    resize()
    resize()
    expect(box).not.toHaveAttribute('role')
    widths(900)
    resize()
    expect(box).toHaveAttribute('aria-label', 'Scrollable table: Item 8')
    expect(scans).toHaveBeenCalledTimes(2)
  })
})
