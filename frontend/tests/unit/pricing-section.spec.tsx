import { fireEvent, render, screen, within } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PricingSection from '@/features/marketing/components/PricingSection'
import { ACCESS_COPY } from '@/features/marketing/lib/access'
import { FREE_COPILOT_QUESTIONS, FREE_EARNINGS_ALERT_LIMIT, FREE_SUMMARY_LIMIT } from '@/lib/planLimits'

/**
 * The landing pricing section shows the SAME numbers as the pricing page (one price source, one
 * approved offer), never the design's placeholders; it is one table, the plans as its columns and what
 * each includes as its rows (D-045); the toggle is an accessible radio group; and the beta line, account
 * CTA and trial copy each follow their one deciding source.
 */

// Live mutable flag so a test can flip ENABLE_PRO_TRIAL without re-importing the component.
// The flags ship off: the plan lists leave out the lines they decide (lib/planLimits.ts shipped).
const flags = vi.hoisted(() => ({ ENABLE_PRO_TRIAL: false, ENABLE_ANALYSIS: false, ENABLE_FPI_FILINGS: false }))
vi.mock('@/lib/featureFlags', async (original) => ({ ...(await original<typeof import('@/lib/featureFlags')>()), ...flags,
  get ENABLE_PRO_TRIAL() { return flags.ENABLE_PRO_TRIAL },
  get ENABLE_ANALYSIS() { return flags.ENABLE_ANALYSIS },
  get ENABLE_FPI_FILINGS() { return flags.ENABLE_FPI_FILINGS },
}))

// These offer/layout cases assume released checkout; publicAccess.spec.tsx exercises the hold.
vi.mock('@/features/marketing/components/PublicAccessProvider', async () => {
  const { ACCESS_COPY } = await import('@/features/marketing/lib/access')
  const { legalReady } = await import('./fixtures/legalReady')
  return {
    usePublicAccess: (mode: keyof typeof ACCESS_COPY) => ACCESS_COPY[mode],
    usePublicReadiness: () => ({ readiness: legalReady, loading: false }),
  }
})

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

  it('opens on annual at the $20 per month headline with its full charge, and shows $25 on monthly', () => {
    renderSection()

    expect(screen.getByText('$20')).toBeInTheDocument()
    expect(screen.getByText('per month')).toBeInTheDocument()
    expect(screen.getByText('Billed annually at $240, saving $60 a year.')).toBeInTheDocument()
    expect(screen.getByText('· save 20%')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('radio', { name: /monthly/i }))
    expect(screen.getByText('$25')).toBeInTheDocument()
    expect(screen.queryByText('$20')).not.toBeInTheDocument()
    expect(screen.getByText('Billed monthly. Or $20 a month, billed annually at $240.')).toBeInTheDocument()
  })

  it('is a two-option radio group whose checked state and roving focus follow clicks and arrow keys', () => {
    renderSection()
    const group = screen.getByRole('radiogroup', { name: 'Billing period' })
    const radios = within(group).getAllByRole('radio')
    expect(radios).toHaveLength(2)
    const [monthly, annual] = radios

    expect(annual).toHaveAttribute('aria-checked', 'true')
    expect(monthly).toHaveAttribute('aria-checked', 'false')
    expect(annual).toHaveAttribute('tabindex', '0')
    expect(monthly).toHaveAttribute('tabindex', '-1')

    fireEvent.click(monthly)
    expect(annual).toHaveAttribute('aria-checked', 'false')
    expect(monthly).toHaveAttribute('aria-checked', 'true')
    expect(monthly).toHaveFocus()

    fireEvent.keyDown(group, { key: 'ArrowRight' })
    expect(annual).toHaveAttribute('aria-checked', 'true')
    expect(annual).toHaveFocus()

    fireEvent.keyDown(group, { key: 'ArrowLeft' })
    expect(monthly).toHaveAttribute('aria-checked', 'true')
    expect(monthly).toHaveFocus()

    fireEvent.keyDown(group, { key: 'End' })
    expect(annual).toHaveAttribute('aria-checked', 'true')
    expect(annual).toHaveFocus()

    fireEvent.keyDown(group, { key: 'Home' })
    expect(monthly).toHaveAttribute('aria-checked', 'true')
    expect(monthly).toHaveFocus()
  })

  // The Filings row names 20-F only while NEXT_PUBLIC_ENABLE_FPI_FILINGS mirrors the API's ENABLE_FPI_FILINGS
  // (tasks/todo.md F39), and never the "Supported" hedge, as /pricing does (PricingPage.spec.tsx); both plans read it.
  it.each([true, false])('names the filing forms in both plans without a hedge, 20-F only while the FPI flag ships it (flag %s)', (on) => {
    flags.ENABLE_FPI_FILINGS = on
    const { container } = renderSection()
    const row = screen.getByRole('rowheader', { name: 'Filings' }).closest('tr')!
    expect(within(row).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(
      Array(2).fill(on ? '10-K, 10-Q and 20-F filings from SEC EDGAR' : '10-K and 10-Q filings from SEC EDGAR'),
    )
    if (!on) expect(container).not.toHaveTextContent('20-F')
    expect(container).not.toHaveTextContent(/Supported/i)
    flags.ENABLE_FPI_FILINGS = false
  })

  // D-045: pricing on the landing is one table, a real one: a caption that names it, the two plans as column headers,
  // what each includes as row headers, one cell per plan in every row, read from lib/planLimits.ts. A plan that does
  // not include a row's thing reads "Not included" to a screen reader, never a bare dash.
  it('is one table: the plans as its columns and what each includes as its rows, from the plan-line mirror', () => {
    const { container } = renderSection()
    expect(container.querySelectorAll('table')).toHaveLength(1)
    const table = screen.getByRole('table', { name: 'What each plan includes' })
    expect(within(table).getAllByRole('columnheader').map((header) => header.textContent)).toEqual(['Free', 'Pro'])
    expect(within(table).getAllByRole('rowheader').map((header) => header.textContent)).toEqual([
      'Price',
      'Summaries',
      'Filings',
      'Company search and historical filings',
      'Ask this Filing',
      'Change Report',
      'Alerts',
      'Exports',
      'Watchlist',
      'Priority support',
    ])
    const cells = (label: string) =>
      within(screen.getByRole('rowheader', { name: label }).closest('tr')!).getAllByRole('cell').map((cell) => cell.textContent)
    expect(cells('Summaries')).toEqual([`${FREE_SUMMARY_LIMIT} a month`, 'Unlimited'])
    expect(cells('Ask this Filing')).toEqual([`${FREE_COPILOT_QUESTIONS} questions`, 'Included'])
    expect(cells('Alerts')).toEqual([`${FREE_EARNINGS_ALERT_LIMIT} earnings-day alerts`, 'Hourly filing alerts and 8-K alerts'])
    expect(cells('Exports')).toEqual(['—Not included', 'PDF and CSV exports'])
    expect(cells('Priority support')).toEqual(['—Not included', 'Included'])
    // Every row is a row header and one cell per plan; the closing row holds the two calls to action under their plans.
    for (const row of within(table).getAllByRole('row').slice(1, -1)) {
      expect(within(row).getAllByRole('rowheader')).toHaveLength(1)
      expect(within(row).getAllByRole('cell')).toHaveLength(2)
    }
    const actions = within(table).getAllByRole('row').at(-1)!
    expect(within(actions).getAllByRole('link').map((link) => link.textContent)).toEqual([ACCESS_COPY.public.cta, 'Upgrade to Pro'])
    // The dash is decoration: the reading is the words.
    for (const dash of within(table).getAllByText('—')) expect(dash).toHaveAttribute('aria-hidden', 'true')
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

  it('preserves the selected cycle and advertises a trial only on monthly when enabled', () => {
    const { unmount } = renderSection()
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).toHaveAttribute('href', '/pricing?billing=yearly')
    fireEvent.click(screen.getByRole('radio', { name: /monthly/i }))
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).toHaveAttribute('href', '/pricing?billing=monthly')
    expect(screen.queryByRole('link', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
    expect(screen.queryByText(TRIAL_LINE)).not.toBeInTheDocument()
    unmount()

    flags.ENABLE_PRO_TRIAL = true
    renderSection()
    // Annual, the default, carries no trial.
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).toHaveAttribute('href', '/pricing?billing=yearly')
    expect(screen.queryByRole('link', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
    expect(screen.queryByText(TRIAL_LINE)).not.toBeInTheDocument()

    fireEvent.click(screen.getByRole('radio', { name: /monthly/i }))
    expect(screen.getByRole('link', { name: 'Start 7-day free trial' })).toHaveAttribute('href', '/pricing?billing=monthly')
    expect(screen.queryByRole('link', { name: 'Upgrade to Pro' })).not.toBeInTheDocument()
    expect(screen.getByText(TRIAL_LINE)).toBeInTheDocument()
  })

  it('does not pair the free beta offer with a card-required trial promise', () => {
    flags.ENABLE_PRO_TRIAL = true
    renderSection({ showBeta: true })
    // Monthly is the cycle that would otherwise carry the trial.
    fireEvent.click(screen.getByRole('radio', { name: /monthly/i }))
    expect(screen.getByText('Free for beta members')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Upgrade to Pro' })).toHaveAttribute('href', '/pricing')
    expect(screen.queryByRole('link', { name: 'Start 7-day free trial' })).not.toBeInTheDocument()
    expect(screen.queryByText(TRIAL_LINE)).not.toBeInTheDocument()
  })
})
