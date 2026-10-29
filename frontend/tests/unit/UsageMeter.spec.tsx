import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { UsageMeter, usageMeterFill } from '@/components/ui'

/**
 * The usage meter (components/ui/UsageMeter.tsx, E196): the dashboard's plan card and the pricing page's usage box draw
 * a plan's monthly usage through it. Its fill is the brand's sage below 80% of the limit, warning from 80% and error
 * at 100%, and never runs past its track; a label names it as a progress bar with its value, and without one it is
 * drawn only, beside counts the surface prints in words.
 */
const SAGE = 'bg-brand-strong dark:bg-brand-dark'
const WARNING = 'bg-warning-light dark:bg-warning-dark'
const ERROR = 'bg-error-light dark:bg-error-dark'

const fillOf = (container: HTMLElement) => container.firstElementChild!.firstElementChild as HTMLElement

describe('UsageMeter', () => {
  it.each([
    [0, SAGE],
    [79.9, SAGE],
    [80, WARNING],
    [99.9, WARNING],
    [100, ERROR],
    [140, ERROR],
  ])('fills %s%% of the limit in its own ink', (percent, ink) => {
    expect(usageMeterFill(percent)).toBe(ink)
  })

  it.each([
    [0, 5, '0%', SAGE],
    [3, 5, '60%', SAGE],
    [4, 5, '80%', WARNING],
    [5, 5, '100%', ERROR],
    [7, 5, '100%', ERROR],
    [2, 0, '0%', SAGE],
    [2, null, '0%', SAGE],
  ])('draws %s of %s as a fill %s wide, never past its track', (used, limit, width, ink) => {
    const { container } = render(<UsageMeter used={used} limit={limit} />)
    const fill = fillOf(container)
    expect(fill.style.width).toBe(width)
    for (const token of ink.split(' ')) expect(fill).toHaveClass(token)
  })

  it('a label names it as a progress bar with its value', () => {
    render(<UsageMeter used={4} limit={5} label="4 of 5 summaries used this month" />)
    const meter = screen.getByRole('progressbar', { name: '4 of 5 summaries used this month' })
    expect(meter).toHaveAttribute('aria-valuenow', '4')
    expect(meter).toHaveAttribute('aria-valuemin', '0')
    expect(meter).toHaveAttribute('aria-valuemax', '5')
  })

  it('without a label it is drawn only, no progress bar to read beside the counts in words', () => {
    const { container } = render(<UsageMeter used={4} limit={5} />)
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    expect(container.firstElementChild).not.toHaveAttribute('aria-valuenow')
  })

  it("takes the caller's spacing on its track", () => {
    const { container } = render(<UsageMeter used={1} limit={5} className="mt-3" />)
    expect(container.firstElementChild).toHaveClass('mt-3', 'h-3', 'w-full', 'rounded-full')
  })
})
