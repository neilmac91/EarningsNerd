import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * The waitlist counter (docs/brand/03-strategy.md S5: never a counter at zero). Below COUNT_FLOOR the
 * pill names the list, not a number; at or above it the count shows, in neutral ink inside the
 * sage pill (sage never colours a number), and the count-up never passes through a figure below
 * the floor. useCountUp is replaced by its first or last frame so both ends are observable.
 */
const frame = vi.hoisted(() => ({ at: 'end' as 'start' | 'end' }))
vi.mock('@/hooks/useCountUp', () => ({
  useCountUp: (value: number, options: { format: (v: number) => string }) => options.format(frame.at === 'start' ? 0 : value),
}))
const api = vi.hoisted(() => ({ getWaitlistStats: vi.fn() }))
vi.mock('@/features/waitlist/api/waitlist-api', () => api)

import WaitlistCounter, { COUNT_FLOOR } from '@/features/waitlist/components/WaitlistCounter'

beforeEach(() => {
  frame.at = 'end'
})
afterEach(() => {
  api.getWaitlistStats.mockReset()
})

describe('WaitlistCounter', () => {
  it('below the floor, names the list and shows no number', async () => {
    api.getWaitlistStats.mockResolvedValue({ total_signups: COUNT_FLOOR - 1 })
    const { container } = render(<WaitlistCounter />)
    await waitFor(() => expect(api.getWaitlistStats).toHaveBeenCalled())
    expect(await screen.findByText('Join the waitlist')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\d/)
    expect(container.querySelector('[data-waitlist-count]')).toBeNull()
  })

  it('when the stats cannot load, names the list and shows no number', async () => {
    api.getWaitlistStats.mockRejectedValue(new TypeError('Failed to fetch'))
    const { container } = render(<WaitlistCounter />)
    expect(await screen.findByText('Join the waitlist')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\d/)
  })

  it('at or above the floor, shows the count in neutral ink, not sage', async () => {
    api.getWaitlistStats.mockResolvedValue({ total_signups: 120 })
    const { container } = render(<WaitlistCounter />)
    await waitFor(() => expect(container.textContent).toBe('Join 120+ others'))
    const count = container.querySelector('[data-waitlist-count]')!
    expect(count.textContent).toBe('120+')
    expect(count.className).toMatch(/\btext-text-primary-light\b/)
    expect(count.className).not.toMatch(/text-brand/)
  })

  it("the count-up's first frame shows the floor, never 0+", async () => {
    frame.at = 'start'
    api.getWaitlistStats.mockResolvedValue({ total_signups: 120 })
    const { container } = render(<WaitlistCounter />)
    await waitFor(() => expect(container.querySelector('[data-waitlist-count]')).not.toBeNull())
    expect(container.querySelector('[data-waitlist-count]')!.textContent).toBe(`${COUNT_FLOOR}+`)
    expect(container.textContent).not.toMatch(/Join 0\+/)
  })
})
