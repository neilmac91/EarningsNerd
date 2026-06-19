import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const push = vi.fn()
vi.mock('next/navigation', () => ({ useRouter: () => ({ push }) }))

const searchFullText = vi.fn()
vi.mock('@/features/search/api/search-api', () => ({
  searchFullText: (...args: unknown[]) => searchFullText(...args),
}))

vi.mock('@/lib/analytics', () => ({ default: { filingsSearched: vi.fn() } }))

import CommandPalette from '@/components/CommandPalette'

function renderPalette() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={qc}>
      <CommandPalette />
    </QueryClientProvider>,
  )
}

const hit = {
  accession_no: '0000320193-23-000106',
  form: '10-K',
  filed_date: '2023-11-03',
  period_ending: '2023-09-30',
  cik: '0000320193',
  company: 'Apple Inc.',
  ticker: 'AAPL',
  document: 'aapl.htm',
  sec_url: 'https://www.sec.gov/x/',
  document_url: 'https://www.sec.gov/x/aapl.htm',
}

describe('CommandPalette', () => {
  beforeEach(() => {
    push.mockReset()
    searchFullText.mockReset()
  })

  it('is closed by default and opens on Cmd+K', () => {
    renderPalette()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('closes on Escape', () => {
    renderPalette()
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('renders results for a query', async () => {
    searchFullText.mockResolvedValue({ query: 'going concern', total: 1, count: 1, hits: [hit] })
    renderPalette()
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'going concern' } })

    expect(await screen.findByText('Apple Inc.')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    expect(searchFullText).toHaveBeenCalledWith({ q: 'going concern', forms: undefined })
  })

  it('navigates to the company page when a result is clicked', async () => {
    searchFullText.mockResolvedValue({ query: 'apple', total: 1, count: 1, hits: [hit] })
    renderPalette()
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'apple' } })

    fireEvent.click(await screen.findByText('Apple Inc.'))
    expect(push).toHaveBeenCalledWith('/company/AAPL')
  })

  it('opens the SEC document on Cmd+Enter instead of navigating in-app', async () => {
    const openSpy = vi.spyOn(window, 'open').mockImplementation(() => null)
    searchFullText.mockResolvedValue({ query: 'apple', total: 1, count: 1, hits: [hit] })
    renderPalette()
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    const input = screen.getByRole('combobox')
    fireEvent.change(input, { target: { value: 'apple' } })
    await screen.findByText('Apple Inc.')

    fireEvent.keyDown(input, { key: 'Enter', metaKey: true })

    expect(openSpy).toHaveBeenCalledWith(
      'https://www.sec.gov/x/aapl.htm',
      '_blank',
      'noopener,noreferrer',
    )
    expect(push).not.toHaveBeenCalled()
    openSpy.mockRestore()
  })

  it('shows an empty state when there are no matches', async () => {
    searchFullText.mockResolvedValue({ query: 'zzzzz', total: 0, count: 0, hits: [] })
    renderPalette()
    fireEvent.keyDown(document, { key: 'k', metaKey: true })
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'zzzzz' } })

    expect(await screen.findByText(/No filings match/i)).toBeInTheDocument()
  })
})
