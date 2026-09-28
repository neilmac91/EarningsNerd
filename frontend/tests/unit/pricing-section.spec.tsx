import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PricingSection from '@/features/marketing/components/PricingSection'
import { ACCESS_COPY } from '@/features/marketing/lib/access'

/**
 * The landing pricing section shows the SAME numbers as the pricing page (one price source, one
 * approved offer), never the design's placeholders; the toggle is an accessible radio group; and the
 * beta line, account CTA and trial copy each follow their one deciding source.
 */

// Live mutable flag so a test can flip ENABLE_PRO_TRIAL without re-importing the component.
const flags = vi.hoisted(() => ({ ENABLE_PRO_TRIAL: false }))
vi.mock('@/lib/featureFlags', () => flags)

vi.mock('@/lib/analytics', () => ({ default: { homepageSectionViewed: vi.fn(), billingCycleToggled: vi.fn() } }))

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const TRIAL_LINE = 'Card required. One trial per account. Cancel any time in the 7 days at no charge.'

const renderSection = (props: Partial<React.ComponentProps<typeof PricingSection>> = {}) =>
  render(<PricingSection accessMode="public" showBeta={false} {...props} />)

describe('PricingSection', () => {
  beforeEach(() => {
    flags.ENABLE_PRO_TRIAL = false
  })

  it('defaults to monthly and shows the full annual charge and saving when selected', () => {
    renderSection()

    expect(screen.getByText('$19')).toBeInTheDocument()
    expect(screen.getByText('Billed monthly. Or $190 a year, with two months free.')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('radio', { name: /annual/i }))
    expect(screen.getByText('$15.83')).toBeInTheDocument()
    expect(screen.queryByText('$19')).not.toBeInTheDocument()
    expect(
      screen.getByText('Billed annually at $190. Two months free, saving $38 a year (17%).'),
    ).toBeInTheDocument()
  })

  it('is a two-option radio group whose checked state and roving focus follow clicks and arrow keys', () => {
    renderSection()
    const group = screen.getByRole('radiogroup', { name: 'Billing period' })
    const radios = within(group).getAllByRole('radio')
    expect(radios).toHaveLength(2)
    const [monthly, annual] = radios

    expect(monthly).toHaveAttribute('aria-checked', 'true')
    expect(annual).toHaveAttribute('aria-checked', 'false')
    expect(monthly).toHaveAttribute('tabindex', '0')
    expect(annual).toHaveAttribute('tabindex', '-1')

    fireEvent.click(annual)
    expect(monthly).toHaveAttribute('aria-checked', 'false')
    expect(annual).toHaveAttribute('aria-checked', 'true')
    expect(annual).toHaveFocus()

    fireEvent.keyDown(group, { key: 'ArrowLeft' })
    expect(monthly).toHaveAttribute('aria-checked', 'true')
    expect(monthly).toHaveFocus()

    fireEvent.keyDown(group, { key: 'End' })
    expect(annual).toHaveAttribute('aria-checked', 'true')
    expect(annual).toHaveFocus()
  })

  it('shows the beta line only when showBeta is set', () => {
    const { unmount } = renderSection({ showBeta: false })
    expect(screen.queryByText('Free for beta members')).not.toBeInTheDocument()
    unmount()

    renderSection({ showBeta: true })
    expect(screen.getByText('Free for beta members')).toBeInTheDocument()
  })

  it('routes the Free CTA through the page access decision', () => {
    const { unmount } = renderSection({ accessMode: 'public' })
    expect(screen.getByRole('link', { name: ACCESS_COPY.public.cta })).toHaveAttribute('href', ACCESS_COPY.public.href)
    expect(screen.queryByRole('link', { name: ACCESS_COPY.invite.cta })).not.toBeInTheDocument()
    unmount()

    renderSection({ accessMode: 'invite' })
    expect(screen.getByRole('link', { name: ACCESS_COPY.invite.cta })).toHaveAttribute('href', ACCESS_COPY.invite.href)
    expect(screen.queryByRole('link', { name: ACCESS_COPY.public.cta })).not.toBeInTheDocument()
  })

  it('advertises the trial only when ENABLE_PRO_TRIAL is on, and always sends Pro to /pricing', () => {
    const { unmount } = renderSection()
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByRole('link', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
    expect(screen.queryByText(TRIAL_LINE)).not.toBeInTheDocument()
    unmount()

    flags.ENABLE_PRO_TRIAL = true
    renderSection()
    expect(screen.getByRole('link', { name: 'Start 7-day free trial' })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByRole('link', { name: 'Upgrade to Pro' })).not.toBeInTheDocument()
    expect(screen.getByText(TRIAL_LINE)).toBeInTheDocument()
  })
})
