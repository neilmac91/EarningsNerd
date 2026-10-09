import { describe, it, expect } from 'vitest'
import { regionName } from '@/features/filings/components/copilot/ReaderTable'

// A filing-reader table that scrolls is a named region (EN-04). Its name is the section it sits
// under; statements often share one heading, so a section with several tables numbers them, and no
// two regions in the reader share a name.
describe('ReaderTable regionName', () => {
  function reader(html: string) {
    const el = document.createElement('div')
    el.innerHTML = html
    return Array.from(el.querySelectorAll<HTMLElement>(':scope > .filing-table-scroll'))
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
})
