import { describe, expect, it } from 'vitest'
import { layoutChartNotes, type ChartNoteAnchor, type ChartNoteBounds } from '@/features/analysis/lib/chartNoteLayout'

const plot = { x: 72, y: 24, width: 392, height: 158 }
const intersects = (a: ChartNoteBounds, b: ChartNoteBounds) => Math.min(a.x + a.width, b.x + b.width) > Math.max(a.x, b.x)
  && Math.min(a.y + a.height, b.y + b.height) > Math.max(a.y, b.y)

function expectReadable(anchors: ChartNoteAnchor[], bounds = plot) {
  const positions = layoutChartNotes(anchors, bounds)
  const letters = anchors.filter((anchor) => anchor.letter)
  expect(positions.size).toBe(letters.length)
  // Browser-measured 11px mono glyphs: 7px advance, 11px ascent and 3px descent.
  // These visible extents are deliberately independent of the helper's safety padding.
  const boxes = letters.map((anchor) => {
    const position = positions.get(anchor.key)!
    const width = anchor.letter!.length * 7
    return { x: position.x - width / 2, y: position.y - 11, width, height: 14 }
  })
  for (const [index, box] of boxes.entries()) {
    expect(box.x).toBeGreaterThanOrEqual(bounds.x)
    expect(box.y).toBeGreaterThanOrEqual(bounds.y)
    expect(box.x + box.width).toBeLessThanOrEqual(bounds.x + bounds.width)
    expect(box.y + box.height).toBeLessThanOrEqual(bounds.y + bounds.height)
    for (const anchor of anchors) {
      // Include the 2px stroke around the 4px-radius marker, including its own point.
      expect(intersects(box, { x: anchor.x - 5, y: anchor.y - 5, width: 10, height: 10 })).toBe(false)
    }
    for (const other of boxes.slice(index + 1)) expect(intersects(box, other)).toBe(false)
  }
  return positions
}

describe('same-axis chart note placement', () => {
  it('keeps both close META margin notes clear of the other marker without moving data', () => {
    // Real 390px rendered coordinates from Q2 2025 and Q2 2026, before the correction.
    const anchors = [
      { key: 'operating:2025Q2', x: 321.45, y: 64.19, letter: 'a' },
      { key: 'net:2025Q2', x: 321.45, y: 74.67, letter: 'a' },
      { key: 'operating:2026Q2', x: 464, y: 92.92, letter: 'a' },
      { key: 'net:2026Q2', x: 464, y: 104.31, letter: 'a' },
    ]
    const original = structuredClone(anchors)
    const positions = expectReadable(anchors)
    expect(positions.get('operating:2025Q2')!.y).toBeLessThan(64.19)
    expect(positions.get('net:2025Q2')!.y).toBeGreaterThan(74.67)
    expect(anchors).toEqual(original)
  })

  it('follows actual plotted order when net margin exceeds operating margin', () => {
    const anchors = [
      { key: 'operating', x: 160, y: 78, letter: 'a' },
      { key: 'net', x: 160, y: 68, letter: 'b' },
    ]
    const positions = expectReadable(anchors)
    expect(positions.get('net')!.y).toBeLessThan(68)
    expect(positions.get('operating')!.y).toBeGreaterThan(78)
  })

  it('retains a third close series and multi-letter notes beside neighbouring periods', () => {
    expectReadable([
      { key: 'gross', x: 160, y: 60, letter: 'aa' },
      { key: 'operating', x: 160, y: 64, letter: 'ab' },
      { key: 'net', x: 160, y: 68, letter: 'ac' },
      { key: 'next-gross', x: 188, y: 62, letter: 'aa' },
      { key: 'next-operating', x: 188, y: 66, letter: 'ab' },
      { key: 'next-net', x: 188, y: 70, letter: 'ac' },
    ])
  })

  it.each([[72, 24], [464, 24], [72, 182], [464, 182]])('keeps tied notes distinct at plot corner %s,%s', (x, y) => {
    const anchors = ['gross', 'operating', 'net'].map((key) => ({ key, x, y, letter: 'a' }))
    const positions = expectReadable(anchors)
    expect([...layoutChartNotes(anchors, plot)]).toEqual([...positions])
  })

  it('does not assign a note to a clean or non-plottable value', () => {
    const positions = layoutChartNotes([
      { key: 'clean', x: 150, y: 60, letter: null },
      { key: 'missing', x: 160, y: Number.NaN, letter: 'a' },
    ], plot)
    expect(positions.size).toBe(0)
  })
})
