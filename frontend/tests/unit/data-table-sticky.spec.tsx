import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import { DataTable, type Column } from '@/components/ui'

interface Row {
  id: string
  name: string
  value: number
  [key: string]: unknown
}

const columns: Column<Row>[] = [
  { key: 'name', header: 'Name' },
  { key: 'value', header: 'Value', align: 'right', numeric: true },
]
const rows: Row[] = [
  { id: 'a', name: 'Alpha', value: 1 },
  { id: 'b', name: 'Beta', value: 2 },
]

describe('DataTable stickyFirstColumn', () => {
  it('does nothing when the flag is off (no sticky classes anywhere)', () => {
    const { container } = render(
      <DataTable<Row> columns={columns} rows={rows} rowKey={(r) => r.id} />
    )
    expect(container.querySelector('.sticky')).toBeNull()
  })

  it('sticks the first column of both header and body, with an opaque fill and a right hairline', () => {
    const { container } = render(
      <DataTable<Row> columns={columns} rows={rows} rowKey={(r) => r.id} stickyFirstColumn />
    )
    const headerCell = container.querySelector('thead th')
    const bodyCell = container.querySelector('tbody tr td')
    for (const cell of [headerCell, bodyCell]) {
      expect(cell).toHaveClass('sticky')
      expect(cell).toHaveClass('left-0')
      expect(cell).toHaveClass('border-r')
      expect(cell).toHaveClass('bg-panel-light')
    }
    // Only the first column gets the treatment — the second (Value) column stays plain.
    const secondHeaderCell = container.querySelectorAll('thead th')[1]
    expect(secondHeaderCell).not.toHaveClass('sticky')
  })

  it('gives the corner cell (sticky header × sticky first column) the highest z-index', () => {
    const { container } = render(
      <DataTable<Row>
        columns={columns}
        rows={rows}
        rowKey={(r) => r.id}
        stickyHeader
        stickyFirstColumn
        className="h-40"
      />
    )
    const corner = container.querySelector('thead th')
    const bodyStickyCell = container.querySelector('tbody tr td')
    const plainHeaderCell = container.querySelectorAll('thead th')[1]
    expect(corner).toHaveClass('z-20')
    expect(bodyStickyCell).toHaveClass('z-[5]')
    expect(plainHeaderCell).toHaveClass('z-10')
    // Exactly one z-* utility on the corner cell — no ambiguous z-10/z-20 double-application.
    const zClasses = Array.from(corner?.classList ?? []).filter((c) => /^z-/.test(c))
    expect(zClasses).toEqual(['z-20'])
  })

  it('keeps the first column sticky in loading-skeleton rows (no snap when data lands)', () => {
    const { container } = render(
      <DataTable<Row> columns={columns} rows={[]} rowKey={(r) => r.id} stickyFirstColumn loading />
    )
    const skeletonCells = container.querySelectorAll('tbody tr td')
    expect(skeletonCells.length).toBeGreaterThan(0)
    const firstCell = skeletonCells[0]
    expect(firstCell).toHaveClass('sticky')
    expect(firstCell).toHaveClass('left-0')
    expect(firstCell).toHaveClass('bg-panel-light')
    expect(firstCell).toHaveClass('z-[5]')
    // Only the first column — the second stays plain, same as real rows.
    expect(skeletonCells[1]).not.toHaveClass('sticky')
  })

  it('gives the sticky body cell a group-hover fill so it repaints on row hover', () => {
    const { container } = render(
      <DataTable<Row> columns={columns} rows={rows} rowKey={(r) => r.id} stickyFirstColumn />
    )
    const row = container.querySelector('tbody tr')
    const bodyCell = container.querySelector('tbody tr td')
    expect(row).toHaveClass('group')
    expect(bodyCell?.className).toMatch(/group-hover:bg-white/)
  })
})
