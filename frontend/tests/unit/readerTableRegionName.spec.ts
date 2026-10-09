import { describe, it, expect } from 'vitest'
import { regionName } from '@/features/filings/components/copilot/ReaderTable'

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
})
