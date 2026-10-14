import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/client'
import type { Company } from '@/features/companies/api/companies-api'
import type { Filing } from '@/features/filings/api/filings-api'
import { TickerFilingsView } from '@/features/filings/components/TickerFilingsView'

const api = vi.hoisted(() => ({
  getCompany: vi.fn<(ticker: string) => Promise<Company>>(),
  getCompanyFilings: vi.fn<(ticker: string) => Promise<Filing[]>>(),
}))
vi.mock('@/features/companies/api/companies-api', () => ({ getCompany: api.getCompany }))
vi.mock('@/features/filings/api/filings-api', () => ({ getCompanyFilings: api.getCompanyFilings }))
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

const APPLE = { id: 1, ticker: 'AAPL', name: 'Apple Inc.' } as Company
// What the backend's raw detail might say: the route never prints it.
const RAW = 'upstream pool exhausted (psycopg2.OperationalError)'

let client: QueryClient
const renderRoute = () => {
  // The route asks for one retry; a zero delay keeps that retry inside the test's wait.
  client = new QueryClient({ defaultOptions: { queries: { retryDelay: 0 } } })
  return render(
    <QueryClientProvider client={client}>
      <TickerFilingsView ticker="aapl" />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  api.getCompany.mockReset()
  api.getCompanyFilings.mockReset()
})
afterEach(() => client?.clear())

// The company page's two states (#1292), on the /filing/<TICKER> route: a load failure is a sentence and a
// Retry held through its refetch, a 404 is "not found", and neither prints the raw error.
describe('TickerFilingsView failures', () => {
  it('a load failure says so with a Retry, holds its card through the refetch, and never prints the raw error', async () => {
    api.getCompany.mockRejectedValue(new ApiError(500, RAW))
    renderRoute()
    expect(await screen.findByRole('heading', { level: 1, name: 'Filings unavailable' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('We couldn’t load filings for AAPL. Try again in a moment.')
    expect(screen.queryByText(RAW, { exact: false })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Go to the homepage' })).not.toBeInTheDocument()

    let answer!: (company: Company) => void
    api.getCompany.mockImplementation(() => new Promise<Company>((resolve) => { answer = resolve }))
    api.getCompanyFilings.mockResolvedValue([])
    const retry = screen.getByRole('button', { name: 'Retry' })
    retry.focus()
    fireEvent.click(retry)
    // The refetch puts the data-less query back to pending: the card, and its focused Retry, stay up, busy.
    await act(async () => {})
    expect(screen.getByRole('heading', { level: 1, name: 'Filings unavailable' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Retrying/ })).toHaveAttribute('aria-busy', 'true')
    await act(async () => answer(APPLE))
    const heading = await screen.findByRole('heading', { level: 1, name: 'Apple Inc.' })
    // The Retry left while it held focus: focus goes to the loaded page's h1, never to <body>.
    expect(heading).toHaveFocus()
  })

  it('a 404 reads as not found, with the way home and no Retry', async () => {
    api.getCompany.mockRejectedValue(new ApiError(404, RAW))
    renderRoute()
    expect(await screen.findByRole('heading', { level: 1, name: 'Company not found' })).toBeInTheDocument()
    expect(screen.getByText(/No company with a ticker on SEC EDGAR matches/)).toHaveTextContent(
      'No company with a ticker on SEC EDGAR matches AAPL.',
    )
    expect(screen.getByRole('link', { name: 'Go to the homepage' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(RAW, { exact: false })).not.toBeInTheDocument()
  })

  it('a filings failure under a loaded company is a card with a Retry, without the raw error', async () => {
    api.getCompany.mockResolvedValue(APPLE)
    api.getCompanyFilings.mockRejectedValue(new ApiError(503, RAW))
    renderRoute()
    expect(await screen.findByRole('heading', { level: 3, name: 'Couldn’t load the filings' })).toBeInTheDocument()
    expect(screen.getByRole('alert')).toHaveTextContent('Try again in a moment.')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
    expect(screen.queryByText(RAW, { exact: false })).not.toBeInTheDocument()
  })
})
