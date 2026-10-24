/**
 * SegmentedControl's full-width form takes its one auto-width row at 40rem, never at a px breakpoint (E183, chief
 * design on #1570, comment 6380853186).
 *
 * What the row must hold is set in rem (each segment's label and padding), so a px switch chose the one-row form
 * whatever the reader's text size: at `sm`, 640px at any size, a five-form filter (All, 10-K, 10-Q, 10-K/A, 10-Q/A)
 * painted its "10-Q/A" segment to 692px past a card ending at 592px at 640px under 200% text. Holds: below 40rem the
 * shell spans its row and wraps whole segments, each segment stretching; from 40rem the shell is one auto-width row and
 * each segment keeps its own width; and no layout class on the shell or a segment switches at a px breakpoint. The
 * adaptive size's height still switches at `sm`, a device's touch size, not a layout. tests/e2e/reflow-200.spec.ts
 * holds the filings index's five-form filter inside its card at 640 and 700px under 200% text.
 */
import { render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SegmentedControl } from '@/components/ui'

const FORMS = [
  { value: 'all', label: 'All' },
  { value: '10-K', label: '10-K', mono: true },
  { value: '10-Q', label: '10-Q', mono: true },
  { value: '10-K/A', label: '10-K/A', mono: true },
  { value: '10-Q/A', label: '10-Q/A', mono: true },
] as const

const AT_40REM = '[@media(min-width:40rem)]:'
/** A layout class (display, width, wrap, flex sizing) behind a px breakpoint. */
const pxLayout = (cls: string) => /^(sm|md|lg|xl|2xl):(inline-flex|flex|w-auto|w-full|flex-wrap|flex-nowrap|flex-none|flex-1)$/.test(cls)

function renderFullWidth() {
  render(<SegmentedControl label="Filter by form" options={FORMS} value="all" onChange={vi.fn()} size="adaptive" fullWidth />)
  const group = screen.getByRole('group', { name: 'Filter by form' })
  return { group, segments: within(group).getAllByRole('button') }
}

describe("SegmentedControl's full-width form switches at 40rem (E183)", () => {
  it('spans and wraps its row below 40rem, and takes one auto-width row from 40rem', () => {
    const { group, segments } = renderFullWidth()
    expect(group).toHaveClass('flex', 'w-full', 'flex-wrap', `${AT_40REM}inline-flex`, `${AT_40REM}w-auto`, `${AT_40REM}flex-nowrap`)
    expect(segments).toHaveLength(5)
    for (const segment of segments) expect(segment).toHaveClass('flex-1', `${AT_40REM}flex-none`)
  })

  it('switches no layout class at a px breakpoint', () => {
    const { group, segments } = renderFullWidth()
    const classes = [group, ...segments].flatMap((el) => el.className.split(/\s+/).filter(Boolean))
    expect(classes.filter(pxLayout)).toEqual([])
    // Anti-vacuity: the old recipe's layout classes are what this refuses, and the adaptive size's height is not one.
    expect(['sm:inline-flex', 'sm:w-auto', 'sm:flex-nowrap', 'sm:flex-none'].filter(pxLayout)).toHaveLength(4)
    expect(['sm:h-[1.625rem]', 'sm:text-xs', `${AT_40REM}w-auto`].filter(pxLayout)).toEqual([])
  })
})
