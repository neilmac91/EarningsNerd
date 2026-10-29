import { afterEach, describe, expect, it } from 'vitest'
import { cleanup, render } from '@testing-library/react'
import { Skeleton } from '@/components/ui/Skeleton'

/**
 * E233: a bone keeps its rem width, so under 200% text the settings page's bones (`w-56`, 448px) ran past a phone's
 * screen until the reads behind them answered. A bone stops at its container (`max-w-full`) unless its caller sets its
 * own max width, which then decides alone: cx only joins classes, so with both on the element Tailwind's emission order
 * would pick the winner. The page itself is held in loading-and-motion.spec.ts.
 */

afterEach(cleanup)

const classes = (className: string) => {
  const { container } = render(<Skeleton className={className} />)
  return container.firstElementChild!.className.split(/\s+/)
}

describe('Skeleton', () => {
  it('stops a fixed-width bone at its container', () => {
    expect(classes('h-5 w-56')).toContain('max-w-full')
  })

  it("leaves a caller's own max width alone", () => {
    const own = classes('h-11 max-w-md rounded-lg')
    expect(own).toContain('max-w-md')
    expect(own).not.toContain('max-w-full')
    expect(classes('h-10 w-48 max-w-full rounded-lg').filter((c) => c === 'max-w-full')).toHaveLength(1)
  })

  it("keeps the cap below a breakpoint whose own max width starts there", () => {
    expect(classes('h-5 w-56 sm:max-w-md')).toEqual(expect.arrayContaining(['max-w-full', 'sm:max-w-md']))
  })
})
