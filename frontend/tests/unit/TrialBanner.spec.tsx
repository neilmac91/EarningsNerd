import { describe, expect, it, vi } from 'vitest'
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
 */
describe('TrialBanner', () => {
  it('states the end date of a live Pro trial', () => {
    render(<TrialBanner isPro status="trialing" trialEnd="2026-06-25T00:00:00Z" />)
    expect(screen.getByText('Your Pro trial ends Jun 25, 2026.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Keep Pro' })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByText(/days? left/)).not.toBeInTheDocument()
  })

  it('renders nothing for an expired trial remnant (status trialing, plan resolved to Free)', () => {
    const { container } = render(<TrialBanner isPro={false} status="trialing" trialEnd="2099-01-01T00:00:00Z" />)
    expect(container).toBeEmptyDOMElement()
  })

  it.each([
    ['an unresolved plan', undefined, 'trialing', '2099-01-01T00:00:00Z'],
    ['a paid Pro plan', true, 'active', '2099-01-01T00:00:00Z'],
    ['a trial without an end date', true, 'trialing', null],
    ['an unreadable end date', true, 'trialing', 'soon'],
  ] as const)('renders nothing for %s', (_, isPro, status, trialEnd) => {
    const { container } = render(<TrialBanner isPro={isPro} status={status} trialEnd={trialEnd} />)
    expect(container).toBeEmptyDOMElement()
  })
})
