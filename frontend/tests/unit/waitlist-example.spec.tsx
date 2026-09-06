import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import type { ReactElement } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import WaitlistPage from '@/app/waitlist/page'
import HeroExample from '@/features/marketing/components/HeroExample'
import analytics from '@/lib/analytics'

const resource = vi.hoisted(() => ({ pending: null as Promise<void> | null, value: null as ReactElement | null }))
vi.mock('@/lib/featureFlags', () => ({
  EXAMPLE_FILING_ID: '42',
  exampleFilingHref: (entry: string) => `/filing/42?entry=${entry}&demo=1`,
}))
vi.mock('@/lib/analytics', () => ({ default: { exampleCtaClicked: vi.fn() } }))
vi.mock('@/features/waitlist/components/WaitlistForm', () => ({
  default: ({ source }: { source: string }) => <form aria-label="Join waitlist" data-source={source}><input aria-label="Email" /></form>,
}))
vi.mock('@/features/waitlist/components/WaitlistCounter', () => ({ default: () => null }))
// React 18 DOM cannot invoke async server components. Resolve the real server child
// through a Suspense resource; its fetch, HeroExample and tracked link remain real.
vi.mock('@/features/waitlist/components/WaitlistExample', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/waitlist/components/WaitlistExample')>()
  return { ...actual, default: () => {
    if (resource.value) return resource.value
    resource.pending ??= actual.default().then(value => { resource.value = value })
    throw resource.pending
  } }
})
const filing = {
  id: 42, company: { ticker: 'ASML', name: 'ASML Holding N.V.' },
  filing_type: '20-F', filing_date: '2026-02-11',
  sec_url: 'https://www.sec.gov/Archives/edgar/data/937966/000093796626000001/',
}
const overview = 'ASML supplies lithography systems. This is the selected filing excerpt.'
const metrics = [{ metric: 'Revenue', currentPeriod: '€32.7B' }, { metric: 'Net Income', currentPeriod: '€9.6B' }]
function respond(tier: string | null = 'full', values = metrics, businessOverview = overview) {
  return vi.fn(async (url: string, _options?: RequestInit) => new Response(JSON.stringify(url.includes('/summaries/')
    ? { business_overview: businessOverview, raw_summary: { quality: { tier } }, financial_highlights: { normalized: { metrics: values } } }
    : filing), { status: 200 }))
}
beforeEach(() => { resource.pending = null; resource.value = null; vi.clearAllMocks() })
afterEach(() => { cleanup(); vi.unstubAllGlobals() })

describe('waitlist grounded example', () => {
  it.each(['full', 'partial', null])('keeps filing identity, source, quality %s and canonical CTA together', async tier => {
    const fetcher = respond(tier)
    vi.stubGlobal('fetch', fetcher)
    render(<WaitlistPage />)
    expect(await screen.findByText('ASML Holding N.V.')).toBeInTheDocument()
    expect(screen.getByText(overview)).toBeInTheDocument()
    expect(screen.getByText('€32.7B')).toBeInTheDocument()
    expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument()
    expect(screen.queryByText('Subscription retention 94%')).not.toBeInTheDocument()
    expect(!!screen.queryByText('Full summary')).toBe(tier === 'full')
    expect(!!screen.queryByText('Partial')).toBe(tier === 'partial')
    expect(screen.getByRole('link', { name: /SEC EDGAR/ })).toHaveAttribute('href', filing.sec_url)
    const cta = screen.getByRole('link', { name: 'Read this filing summary' })
    expect(cta).toHaveAttribute('href', '/filing/42')
    cta.addEventListener('click', event => event.preventDefault())
    fireEvent.click(cta)
    expect(analytics.exampleCtaClicked).toHaveBeenCalledWith('waitlist_preview', '/filing/42')
    expect(fetcher).toHaveBeenCalledTimes(2)
    for (const [, options] of fetcher.mock.calls) {
      expect(options?.headers).toEqual({ accept: 'application/json' })
      expect(options).toHaveProperty('next', { revalidate: 3600 })
      expect(options?.credentials).toBeUndefined()
    }
  })
  it('retains the source for a sparse partial example without fallback metrics', async () => {
    vi.stubGlobal('fetch', respond('partial', []))
    render(<WaitlistPage />)
    expect(await screen.findByText('ASML Holding N.V.')).toBeInTheDocument()
    expect(screen.getByText('Partial')).toBeInTheDocument()
    expect(screen.queryByText('Revenue')).not.toBeInTheDocument()
    expect(screen.queryByText('$394.3B')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Source filing/ })).toHaveAttribute('href', filing.sec_url)
  })
  it.each(['unreachable', 'placeholder', 'empty'])('keeps %s examples neutral and signup available', async state => {
    vi.stubGlobal('fetch', state === 'unreachable'
      ? vi.fn(async () => new Response(null, { status: 503 }))
      : respond(null, [], state === 'placeholder' ? 'Generating summary for this filing…' : ''))
    render(<WaitlistPage />)
    expect(await screen.findByText('Example temporarily unavailable')).toBeInTheDocument()
    expect(screen.getByRole('form', { name: 'Join waitlist' })).toHaveAttribute('data-source', 'waitlist')
    expect(screen.queryByText('Apple Inc.')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Read this filing summary' })).not.toBeInTheDocument()
    expect(screen.queryByText(/Generating summary/)).not.toBeInTheDocument()
  })
  it('renders signup while the real example fetch is pending', async () => {
    let release!: () => void
    const hold = new Promise<void>(resolve => { release = resolve })
    const fetcher = respond()
    vi.stubGlobal('fetch', async (url: string) => { await hold; return fetcher(url) })
    render(<WaitlistPage />)
    expect(screen.getByRole('form', { name: 'Join waitlist' })).toBeInTheDocument()
    expect(screen.getByText('Loading example…')).toBeInTheDocument()
    expect(screen.queryByText('ASML Holding N.V.')).not.toBeInTheDocument()
    await act(async () => { release(); await resource.pending })
    expect(screen.getByText('ASML Holding N.V.')).toBeInTheDocument()
  })
  it('preserves shared homepage fallback and default CTA', () => {
    render(<HeroExample example={null} />)
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument()
    expect(screen.getByText('$394.3B')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Read the full example summary' }))
      .toHaveAttribute('href', '/filing/42?entry=hero_visual_example&demo=1')
  })
})
