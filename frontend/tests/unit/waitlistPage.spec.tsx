import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

/**
 * /waitlist as a reader meets it with the example loaded (audit pub/F12, pub/F13, pub/F14a, WL-01,
 * WL-02, WL-04, WL-05, BG-23). text-floors.spec.ts visits the route in CI, but with no backend the
 * example falls back to a GuidanceCard whose h2 hides the outline this page owns: with the example
 * loaded there is no heading beside the form, so the problem cards are the first headings under the
 * h1 and must be h2. This spec renders that state (the real HeroExample) and the joined state, and
 * reads the outline the way text-floors does, in DOM order.
 */
const api = vi.hoisted(() => ({ joinWaitlist: vi.fn(), getWaitlistStats: vi.fn(() => Promise.reject(new Error('offline'))) }))
vi.mock('@/features/waitlist/api/waitlist-api', () => api)
vi.mock('next/navigation', () => ({ useSearchParams: () => new URLSearchParams() }))
vi.mock('@/lib/analytics', () => ({ default: { exampleCtaClicked: vi.fn() } }))
vi.mock('@/lib/featureFlags', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/featureFlags')>()),
  TURNSTILE_SITE_KEY: '',
  TURNSTILE_ENABLED: false,
}))
vi.mock('@/features/waitlist/components/WaitlistExample', async () => {
  const { default: HeroExample } = await import('@/features/marketing/components/HeroExample')
  const loaded = {
    filingId: 3,
    ticker: 'AAPL',
    companyName: 'Apple Inc.',
    filingType: '10-K',
    filingDate: '2025-10-31',
    secUrl: 'https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/',
    excerpt: 'Total net sales rose 6.4% to $416.2B.',
    qualityTier: 'full',
    metrics: [
      { label: 'Revenue', value: '$416.2B', deltaPercent: 6.4 },
      { label: 'Net income', value: '$112.0B', deltaPercent: 19.5 },
    ],
  }
  return {
    default: () => <HeroExample example={loaded} ctaHref="/filing/3" ctaPlacement="waitlist_preview" ctaLabel="Read this filing summary" />,
    WaitlistExamplePending: () => null,
  }
})

import WaitlistPage from '@/app/waitlist/page'

const RING = ['focus-visible:outline-none', 'focus-visible:shadow-ring-brand', 'dark:focus-visible:shadow-ring-brand-dark']

/** Heading levels in DOM order, as text-floors.spec.ts reads them: every jump of more than one level. */
function headingSkips(root: HTMLElement): string[] {
  const out: string[] = []
  let prev = 0
  for (const h of root.querySelectorAll('h1, h2, h3, h4, h5, h6')) {
    const level = Number(h.tagName[1])
    if (prev && level > prev + 1) out.push(`h${prev} -> h${level} "${h.textContent}"`)
    prev = level
  }
  return out
}

describe('/waitlist', () => {
  it('skips no heading level with the example loaded: the problem cards are h2 under the h1', () => {
    const { container } = render(<WaitlistPage />)
    expect(screen.getByRole('region', { name: 'Example summary' })).toBeInTheDocument()
    expect(within(screen.getByRole('region', { name: 'Example summary' })).queryAllByRole('heading')).toHaveLength(0)
    for (const title of ['Filings are long.', 'Checking takes an afternoon.', 'You still read the filing.']) {
      expect(screen.getByRole('heading', { level: 2, name: title })).toBeInTheDocument()
    }
    expect(headingSkips(container)).toEqual([])
  })

  it('skips no heading level once joined: the success heading is an h2', async () => {
    api.joinWaitlist.mockResolvedValueOnce({ success: true, message: "You're on the list.", position: 42, referral_code: 'abc12345', referral_link: null })
    const { container } = render(<WaitlistPage />)
    fireEvent.change(screen.getByLabelText('Email address'), { target: { value: 'ada@example.test' } })
    fireEvent.click(screen.getByRole('button', { name: 'Join the waitlist' }))
    expect(await screen.findByRole('heading', { level: 2, name: "You're on the list." })).toBeInTheDocument()
    expect(headingSkips(container)).toEqual([])
  })

  it('says where the data comes from without a promise it cannot measure', () => {
    const { container } = render(<WaitlistPage />)
    const heading = screen.getByRole('heading', { level: 2, name: 'Before you join' })
    // The tiles follow the heading with no lead to repeat the first tile's source line.
    expect(heading.nextElementSibling?.tagName).toBe('DIV')
    expect(screen.getByText('Source: SEC EDGAR')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/sourced directly/i)
    expect(screen.getByText('Security')).toBeInTheDocument()
    expect(container.textContent).not.toMatch(/\bclarity\b|not hype|Security-first|trust and transparency/i)
  })

  it('rings both of its own links', () => {
    render(<WaitlistPage />)
    const example = screen.getByRole('link', { name: 'Try a live example summary' })
    const join = screen.getByRole('link', { name: 'Join the waitlist' })
    for (const link of [example, join]) {
      for (const cls of RING) expect(link.className.split(/\s+/)).toContain(cls)
    }
  })
})
