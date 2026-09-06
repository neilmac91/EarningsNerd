import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import posthog from 'posthog-js'
import { SummaryDisplay } from '@/features/summaries/components/SummaryDisplay'
import type { Filing } from '@/features/filings/api/filings-api'

const actions = vi.hoisted(() => ({ save: vi.fn(), pdf: vi.fn(), csv: vi.fn() }))
vi.mock('posthog-js', () => ({ default: { capture: vi.fn() } }))
vi.mock('@/lib/featureFlags', async importOriginal => ({
  ...await importOriginal<typeof import('@/lib/featureFlags')>(),
  ENABLE_QUALITY_BADGE: true,
  ENABLE_FINANCIAL_CHARTS: false,
}))
vi.mock('@/features/summaries/api/summaries-api', async importOriginal => ({
  ...await importOriginal<typeof import('@/features/summaries/api/summaries-api')>(),
  getWhatChanged: async () => null,
}))
vi.mock('@/features/summaries/hooks/useSummaryExports', () => ({
  useSummaryExports: () => ({ exportPdf: actions.pdf, exportCsv: actions.csv }),
}))

const filing: Filing = {
  id: 42, filing_type: '20-F', filing_date: '2026-02-11', accession_number: 'test-accession',
  document_url: 'https://www.sec.gov/Archives/test/doc.htm', sec_url: 'https://www.sec.gov/Archives/test/',
  company: { id: 1, ticker: 'ASML', name: 'ASML Holding N.V.' },
}
const canonical = 'https://www.earningsnerd.io/filing/42'
const clients: QueryClient[] = []
function view(authenticated = false, pro = false, tier: string | undefined = undefined, selected = filing) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  clients.push(client)
  return <QueryClientProvider client={client}>
    <SummaryDisplay filing={selected} summary={{ id: 91, filing_id: selected.id, business_overview: 'The selected filing narrative.', raw_summary: { quality: { tier } } }}
      isAuthenticated={authenticated} isPro={pro} isSaved={false}
      saveMutation={{ mutate: actions.save, isPending: false }} onAsk={vi.fn()} />
  </QueryClientProvider>
}
function installClipboard(writeText = vi.fn().mockResolvedValue(undefined)) {
  Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } })
  return writeText
}
const originalClipboard = Object.getOwnPropertyDescriptor(navigator, 'clipboard')
beforeEach(() => {
  vi.clearAllMocks()
  window.history.replaceState(null, '', '/filing/999?demo=1&debug=1&invite=private&token=secret&ref=person#citation')
})
afterEach(() => {
  cleanup()
  clients.splice(0).forEach(client => client.clear())
  if (originalClipboard) Object.defineProperty(navigator, 'clipboard', originalClipboard)
  else Reflect.deleteProperty(navigator, 'clipboard')
  window.history.replaceState(null, '', '/')
  vi.mocked(posthog.capture).mockReset()
})

describe('canonical filing link action', () => {
  it.each([
    [false, false, 'full'], [true, false, 'partial'], [true, true, undefined],
  ] as const)('copies the actual filing for auth=%s pro=%s quality=%s without changing access', async (authenticated, pro, tier) => {
    const write = installClipboard()
    render(view(authenticated, pro, tier))
    const copy = screen.getByRole('button', { name: 'Copy filing link' })
    expect(copy).toHaveAttribute('type', 'button')
    fireEvent.click(copy)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Filing link copied.'))
    expect(write).toHaveBeenCalledExactlyOnceWith(canonical)
    expect(posthog.capture).toHaveBeenCalledExactlyOnceWith('filing_link_copied', { filing_id: 42 })
    expect(screen.getByText('The selected filing narrative.')).toBeInTheDocument()
    expect(!!screen.queryByText('Full summary')).toBe(tier === 'full')
    expect(!!screen.queryByText('Partial')).toBe(tier === 'partial')
    expect(!!screen.queryByRole('button', { name: 'Save Summary' })).toBe(authenticated)
    expect(!!screen.queryByRole('button', { name: 'Export PDF' })).toBe(pro)
    if (authenticated) { fireEvent.click(screen.getByRole('button', { name: 'Save Summary' })); expect(actions.save).toHaveBeenCalledWith(91) }
    if (pro) { fireEvent.click(screen.getByRole('button', { name: 'Export PDF' })); fireEvent.click(screen.getByRole('button', { name: 'Export CSV' })); expect(actions.pdf).toHaveBeenCalledOnce(); expect(actions.csv).toHaveBeenCalledOnce() }
  })

  it('waits for the write, blocks repeated activation, and offers manual copying plus retry on denial', async () => {
    let reject!: (reason: Error) => void
    const pending = new Promise<void>((_, fail) => { reject = fail })
    const write = installClipboard(vi.fn().mockReturnValueOnce(pending).mockResolvedValue(undefined))
    render(view())
    const copy = screen.getByRole('button', { name: 'Copy filing link' })
    act(() => { copy.click(); copy.click() })
    expect(write).toHaveBeenCalledTimes(1)
    expect(copy).toHaveAttribute('aria-busy', 'true')
    expect(screen.getByRole('status')).not.toHaveTextContent('copied')
    expect(posthog.capture).not.toHaveBeenCalled()
    await act(async () => { reject(new Error('Clipboard denied')); await pending.catch(() => {}) })
    expect(screen.getByRole('alert')).toHaveTextContent('Could not copy the link.')
    expect(screen.getByRole('link', { name: canonical })).toHaveAttribute('href', canonical)
    expect(posthog.capture).not.toHaveBeenCalled()
    fireEvent.click(copy)
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Filing link copied.'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(write).toHaveBeenCalledTimes(2)
    expect(posthog.capture).toHaveBeenCalledExactlyOnceWith('filing_link_copied', { filing_id: 42 })
  })

  it('offers the manual canonical link when the Clipboard API is absent', async () => {
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: undefined })
    render(view())
    fireEvent.click(screen.getByRole('button', { name: 'Copy filing link' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not copy the link.')
    expect(screen.getByRole('link', { name: canonical })).toHaveAttribute('href', canonical)
    expect(posthog.capture).not.toHaveBeenCalled()
  })

  it('does not turn a completed write into a failure when telemetry throws', async () => {
    installClipboard()
    vi.mocked(posthog.capture).mockImplementation(() => { throw new Error('Telemetry unavailable') })
    render(view())
    fireEvent.click(screen.getByRole('button', { name: 'Copy filing link' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Filing link copied.'))
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('does not transfer a pending old filing acknowledgment to the next filing', async () => {
    let resolve!: () => void
    const pending = new Promise<void>(done => { resolve = done })
    const write = installClipboard(vi.fn().mockReturnValueOnce(pending).mockResolvedValue(undefined))
    const rendered = render(view())
    fireEvent.click(screen.getByRole('button', { name: 'Copy filing link' }))
    rendered.rerender(view(false, false, 'partial', { ...filing, id: 84 }))
    await act(async () => { resolve(); await pending })
    expect(screen.getByRole('status')).not.toHaveTextContent('copied')
    fireEvent.click(screen.getByRole('button', { name: 'Copy filing link' }))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('Filing link copied.'))
    expect(write).toHaveBeenLastCalledWith('https://www.earningsnerd.io/filing/84')
    expect(posthog.capture).toHaveBeenLastCalledWith('filing_link_copied', { filing_id: 84 })
  })
})
