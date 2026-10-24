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
/** A layout class (display, width, wrap, flex sizing) behind a px breakpoint: a named screen (`sm:`, `max-sm:`) or a
 *  variant that carries a px width (`min-[640px]:`, `[@media(min-width:640px)]:`). */
const LAYOUT = /^(inline-flex|flex|inline-block|block|grid|hidden|w-.+|flex-(wrap|nowrap|wrap-reverse|none|1|auto|initial)|grow(-0)?|shrink(-0)?|basis-.+)$/
const pxLayout = (cls: string) => {
  const at = cls.lastIndexOf(':')
  if (at < 0) return false
  const variant = cls.slice(0, at + 1)
  return LAYOUT.test(cls.slice(at + 1)) && (/(^|:)(max-)?(sm|md|lg|xl|2xl):/.test(variant) || /\d+(\.\d+)?px/.test(variant))
}

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
    // Anti-vacuity: the old recipe's layout classes, and a px switch in any other form, are what this refuses; the
    // adaptive size's height, padding and type, and the 40rem switch, are not.
    const refused = ['sm:inline-flex', 'sm:w-auto', 'sm:flex-nowrap', 'sm:flex-none', 'min-[640px]:flex-nowrap', '[@media(min-width:640px)]:w-auto', 'max-sm:flex-wrap', 'sm:basis-auto', 'sm:grow-0']
    expect(refused.filter(pxLayout)).toEqual(refused)
    expect(['sm:h-[1.625rem]', 'sm:px-3.5', 'sm:text-xs', `${AT_40REM}w-auto`, `${AT_40REM}flex-none`, 'flex-1', 'w-full'].filter(pxLayout)).toEqual([])
  })
})
