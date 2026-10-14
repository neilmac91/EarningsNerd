import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { ReactNode } from 'react'
import TrialBanner from '@/features/subscriptions/components/TrialBanner'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

/**
 * DSW-16 and DSW-17 (lessons/frontend-trial-labels-use-entitlements.md): the banner reads the
 * resolved plan, not the raw status, and states the end date rather than counting down from the
 * browser clock. An expired trial keeps status 'trialing' after the API resolves it to Free.
 *
 * trial_end is a Stripe instant, so the date is the day it falls on in the reader's zone. The fixtures sit
 * at midday UTC, which is the same calendar day only from UTC-12 to UTC+11 (from UTC+12 it is the next day),
 * so every case reads in UTC, pinned with vi.stubEnv, and one case pins a US zone over it: Node re-reads
 * process.env.TZ when it is assigned (as the per-file pin in filing-date-local-day.spec.tsx relies on), and
 * that case's control proves the pin applied.
 */
describe('TrialBanner', () => {
  beforeEach(() => {
    vi.stubEnv('TZ', 'UTC')
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('states the end date of a live Pro trial', () => {
    render(<TrialBanner isPro status="trialing" trialEnd="2026-06-25T12:00:00Z" />)
    expect(screen.getByText('Your Pro trial ends Jun 25, 2026.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Keep Pro' })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByText(/days? left/)).not.toBeInTheDocument()
  })

  it('states the day the trial ends where the reader is, not the UTC day', () => {
    vi.stubEnv('TZ', 'America/New_York')
    const trialEnd = '2026-10-21T01:05:33Z'
    // Control: the pin applied, so the instant is Oct 20, 9:05 PM EDT while its UTC day is Oct 21.
    expect(new Date(trialEnd).getTimezoneOffset()).toBe(240)
    render(<TrialBanner isPro status="trialing" trialEnd={trialEnd} />)
    expect(screen.getByText('Your Pro trial ends Oct 20, 2026.')).toBeInTheDocument()
  })

  it('renders nothing for an expired trial remnant (status trialing, plan resolved to Free)', () => {
    const { container } = render(<TrialBanner isPro={false} status="trialing" trialEnd="2099-01-01T12:00:00Z" />)
    expect(container).toBeEmptyDOMElement()
  })

  it.each([
    ['an unresolved plan', undefined, 'trialing', '2099-01-01T12:00:00Z'],
    ['a paid Pro plan', true, 'active', '2099-01-01T12:00:00Z'],
    ['a trial without an end date', true, 'trialing', null],
    ['an unreadable end date', true, 'trialing', 'soon'],
  ] as const)('renders nothing for %s', (_, isPro, status, trialEnd) => {
    const { container } = render(<TrialBanner isPro={isPro} status={status} trialEnd={trialEnd} />)
    expect(container).toBeEmptyDOMElement()
  })
})
