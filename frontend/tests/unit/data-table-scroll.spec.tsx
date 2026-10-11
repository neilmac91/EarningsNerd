import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { DataTable, type Column } from '@/components/ui'

type Row = Record<string, unknown> & { id: string }
const columns: Column<Row>[] = [
  { key: 'metric', header: 'Metric', rowHeader: true, render: () => 'Revenue' },
  ...Array.from({ length: 12 }, (_, index) => ({ key: String(index), header: `Q${index}`, render: () => <button type="button">Source {index}</button> })),
]
const rows: Row[] = [{ id: 'r' }]
let resize: () => void
let viewport: number
let periodWidth: number
let metricWidth: number

beforeEach(() => {
  viewport = 316
  periodWidth = 68
  metricWidth = 104
  vi.stubGlobal('ResizeObserver', class {
    constructor(callback: () => void) { resize = callback }
    observe() {}
    disconnect() {}
  })
  vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(function (this: HTMLElement) { return viewport })
  vi.spyOn(HTMLElement.prototype, 'scrollWidth', 'get').mockImplementation(function (this: HTMLElement) {
    return Math.max(viewport, metricWidth + periodWidth * 12 + Number.parseFloat(this.style.paddingInlineEnd || '0'))
  })
  vi.spyOn(HTMLElement.prototype, 'getBoundingClientRect').mockImplementation(function (this: HTMLElement) {
    const width = this.tagName === 'TH' ? (this === this.parentElement?.firstElementChild ? metricWidth : periodWidth) : viewport
    return { x: 0, y: 0, top: 0, bottom: 24, left: 0, right: width, width, height: 24, toJSON: () => ({}) }
  })
})

afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals() })

function Table({ snap = true, newest = false }: { snap?: boolean; newest?: boolean }) {
  return <DataTable columns={columns} rows={rows} rowKey={(row) => row.id}
    layout="fixed" colWidths={['6.5rem', ...Array(12).fill('4.25rem')]}
    stickyFirstColumn snapColumns={snap} scrollRegion={{ label: 'Quarterly metrics', hint: 'Use arrows to scroll', startAtEndOnMobile: newest }} />
}

describe('DataTable opt-in column scrolling', () => {
  it('pads whole-column stops, unsticks narrow labels, and preserves a period after text resize', () => {
    render(<Table />)
    const region = screen.getByRole('region', { name: 'Quarterly metrics' })
    expect(region).toHaveAttribute('tabindex', '0')
    expect(region).toHaveAccessibleDescription('Use arrows to scroll')
    expect(region.style.paddingInlineEnd).toBe('8px')
    expect(region.style.scrollPaddingInlineStart).toBe('104px')
    expect((region.scrollWidth - region.clientWidth) % periodWidth).toBe(0)
    fireEvent.keyDown(region, { key: 'ArrowRight' })
    expect(region.scrollLeft).toBe(68)
    periodWidth = 136
    metricWidth = 208
    act(() => resize())
    expect(region.style.scrollPaddingInlineStart).toBe('0px')
    expect(screen.getByRole('rowheader')).not.toHaveClass('sticky')
    expect(screen.getByRole('columnheader', { name: 'Metric' })).toHaveClass('snap-start')
    expect((region.scrollWidth - region.clientWidth - metricWidth) % periodWidth).toBe(0)
    expect(region.scrollLeft).toBe(344)
    const padding = region.style.paddingInlineEnd
    act(() => resize())
    expect(region.style.paddingInlineEnd).toBe(padding)
    expect(region.scrollLeft).toBe(344)
    fireEvent.keyDown(region, { key: 'Home' })
    expect(region.scrollLeft).toBe(0)
    fireEvent.keyDown(region, { key: 'ArrowRight' })
    expect(region.scrollLeft).toBe(metricWidth)
  })

  it('moves by measured columns with arrows/Home/End without stealing child keys', () => {
    render(<Table />)
    const region = screen.getByRole('region')
    fireEvent.keyDown(region, { key: 'ArrowRight' })
    expect(region.scrollLeft).toBe(68)
    for (const key of ['ArrowLeft', 'Home', 'End', 'PageUp', 'PageDown']) {
      expect(fireEvent.keyDown(screen.getByRole('button', { name: 'Source 1' }), { key })).toBe(true)
      expect(region.scrollLeft).toBe(68)
    }
    for (const modifier of ['altKey', 'ctrlKey', 'metaKey']) {
      expect(fireEvent.keyDown(region, { key: 'Home', [modifier]: true })).toBe(true)
      expect(region.scrollLeft).toBe(68)
    }
    fireEvent.keyDown(region, { key: 'End' })
    expect(region.scrollLeft).toBe(612)
    fireEvent.keyDown(region, { key: 'ArrowLeft' })
    expect(region.scrollLeft).toBe(544)
    fireEvent.keyDown(region, { key: 'Home' })
    expect(region.scrollLeft).toBe(0)
    expect(fireEvent.keyDown(region, { key: 'PageDown' })).toBe(false)
    expect(region.scrollLeft).toBe(272)
    expect(fireEvent.keyDown(region, { key: 'PageUp' })).toBe(false)
    expect(region.scrollLeft).toBe(0)
  })

  it('cleans up owned geometry when snapping is disabled and leaves plain tables opt-in', () => {
    const { rerender } = render(<Table />)
    rerender(<Table snap={false} />)
    const region = screen.getByRole('region')
    expect(region.style.paddingInlineEnd).toBe('')
    expect(region.style.scrollPaddingInlineStart).toBe('')
    viewport = 2000
    act(() => resize())
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
    expect(region).not.toHaveAttribute('aria-label')
    expect(region).not.toHaveAttribute('tabindex')
    rerender(<DataTable columns={[{ key: 'id', header: 'ID' }]} rows={rows} rowKey={(row) => row.id} />)
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
    expect(screen.queryByRole('rowheader')).not.toBeInTheDocument()
    expect(screen.getByRole('table').querySelector('colgroup')).toBeNull()
    expect(screen.getByRole('cell', { name: 'r' })).toBeInTheDocument()
  })

  it('starts phones at the newest column once, then preserves the reader’s position on resize', () => {
    const media = window.matchMedia('(max-width: 767px)')
    vi.spyOn(window, 'matchMedia').mockReturnValue({ ...media, matches: true })
    render(<Table newest />)
    const region = screen.getByRole('region')
    expect(region.scrollLeft).toBe(612)
    region.scrollLeft = 68
    fireEvent.scroll(region)
    act(() => resize())
    expect(region.scrollLeft).toBe(68)
  })

  it('scrolls a focused source clear of the sticky row header', () => {
    render(<Table />)
    const region = screen.getByRole('region')
    const source = screen.getByRole('button', { name: 'Source 1' })
    const cell = source.closest('td')!
    const original = cell.getBoundingClientRect()
    cell.getBoundingClientRect = () => {
      const left = 50 + 204 - region.scrollLeft
      return { ...original, left, right: left + 68, width: 68 }
    }
    region.scrollLeft = 204
    fireEvent.focus(source)
    expect(region.scrollLeft).toBe(136)
  })
})
