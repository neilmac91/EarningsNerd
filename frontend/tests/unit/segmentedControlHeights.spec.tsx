/**
 * SegmentedControl's segment heights are rem, never a fixed px (E52, #1292).
 *
 * The segment's line box is set in rem (text-xs, text-sm), so a fixed px height cannot hold it once the
 * root grows: at a 32px root (200% text) text-xs's 32px line box overflowed the old h-[26px], clipping
 * the insider window and FilingIndex's filter from sm up and the calendar view at every width. Holds:
 * sm is 1.625rem with text-xs (26px at the default root), md is h-9 with text-sm, adaptive is md below
 * sm and sm from sm up, and no size carries a px height under any variant. insider-activity-panel.spec
 * pins the adaptive recipe at its call site; this spec pins each recipe at the primitive, where the
 * calendar's sm size has no other pin.
 */
import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SegmentedControl, type SegmentedControlSize } from '@/components/ui'

const OPTIONS = [
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
] as const

function segmentClasses(size: SegmentedControlSize): string[][] {
  render(<SegmentedControl label={`View ${size}`} options={OPTIONS} value="week" onChange={vi.fn()} size={size} />)
  const group = screen.getByRole('group', { name: `View ${size}` })
  const segments = Array.from(group.querySelectorAll('button'))
  expect(segments).toHaveLength(OPTIONS.length)
  return segments.map((segment) => segment.className.split(/\s+/).filter(Boolean))
}

describe('SegmentedControl heights scale with the root (E52)', () => {
  it('sm is 1.625rem with text-xs', () => {
    for (const classes of segmentClasses('sm')) {
      expect(classes).toEqual(expect.arrayContaining(['h-[1.625rem]', 'text-xs']))
    }
  })

  it('md is h-9 with text-sm', () => {
    for (const classes of segmentClasses('md')) {
      expect(classes).toEqual(expect.arrayContaining(['h-9', 'text-sm']))
    }
  })

  it('adaptive is md below sm and sm from sm up', () => {
    for (const classes of segmentClasses('adaptive')) {
      expect(classes).toEqual(expect.arrayContaining(['h-9', 'text-sm', 'sm:h-[1.625rem]', 'sm:text-xs']))
    }
  })

  it('no size holds a segment at a fixed px height, under any variant', () => {
    const fixed = /(^|:)h-\[\d+(\.\d+)?px\]$/
    for (const size of ['sm', 'md', 'adaptive'] as const) {
      for (const classes of segmentClasses(size)) {
        expect(classes.filter((cls) => fixed.test(cls)), size).toEqual([])
      }
    }
    // Anti-vacuity: the old recipe's classes are what this check refuses.
    expect(['h-[26px]', 'sm:h-[26px]'].filter((cls) => fixed.test(cls))).toEqual(['h-[26px]', 'sm:h-[26px]'])
    expect(['h-[1.625rem]', 'sm:h-[1.625rem]', 'h-9'].filter((cls) => fixed.test(cls))).toEqual([])
  })
})
