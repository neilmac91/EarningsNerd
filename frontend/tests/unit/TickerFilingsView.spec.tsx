import React from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { ApiError } from '@/lib/api/client'
import { queryKeys } from '@/lib/queryKeys'
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
afterEach(() => {
  // Unmounted first, so going back online resumes nothing a case left paused.
  cleanup()
  onlineManager.setOnline(true)
  client?.clear()
})

/** Lets React Query's notify (a macrotask) and the renders it schedules run. */
const settle = () => act(async () => new Promise<void>((done) => setTimeout(done, 0)))
const companyState = () => client.getQueryState(queryKeys.tickerCompany('AAPL'))

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
    const retry = screen.getByRole('button', { name: 'Try again' })
    retry.focus()
    fireEvent.click(retry)
    // The refetch puts the data-less query back to pending: the card, and its focused Retry, stay up, busy.
    await act(async () => {})
    expect(screen.getByRole('heading', { level: 1, name: 'Filings unavailable' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Trying again/ })).toHaveAttribute('aria-busy', 'true')
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
    expect(screen.queryByRole('button', { name: 'Try again' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.queryByText(RAW, { exact: false })).not.toBeInTheDocument()
  })

  // A refetch (a reconnect, window focus, an invalidation) puts the data-less query back to pending with its
  // own error cleared; the not-found reading comes from the held 404, so the page stays an answer meanwhile.
  it('keeps a 404 as not found through a refetch, never the load-failure page', async () => {
    api.getCompany.mockRejectedValue(new ApiError(404, RAW))
    renderRoute()
    expect(await screen.findByRole('heading', { level: 1, name: 'Company not found' })).toBeInTheDocument()
    api.getCompany.mockImplementation(() => new Promise<Company>(() => {}))
    act(() => { void client.refetchQueries({ queryKey: queryKeys.tickerCompany('AAPL') }) })
    await waitFor(() => expect(companyState()).toMatchObject({ status: 'pending', fetchStatus: 'fetching', error: null }))
    await settle()
    expect(screen.getByRole('heading', { level: 1, name: 'Company not found' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Filings unavailable' })).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  // networkMode 'online' (the default) holds a first load while the browser is offline: the query is pending
  // with fetchStatus 'paused', neither loading nor failed to TanStack, and nothing has answered, so the route
  // keeps its loading state instead of saying SEC EDGAR has no such ticker (#1292's company page does the same).
  it('keeps a first load paused offline as loading, never "Company not found", and loads when back online', async () => {
    onlineManager.setOnline(false)
    api.getCompany.mockResolvedValue(APPLE)
    api.getCompanyFilings.mockResolvedValue([])
    renderRoute()
    await waitFor(() => expect(companyState()?.fetchStatus).toBe('paused'))
    await settle()
    expect(api.getCompany).not.toHaveBeenCalled()
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
    expect(screen.queryByText(/No company with a ticker on SEC EDGAR/)).not.toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()

    act(() => onlineManager.setOnline(true))
    expect(await screen.findByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
  })

  // The connection drops under the first request: it fails with the browser's TypeError, and its one retry
  // pauses offline. Nothing failed yet to TanStack (the retry is pending), so this too is loading.
  it('keeps a first load whose retry paused offline as loading, never "Company not found"', async () => {
    api.getCompany.mockImplementationOnce(() => {
      onlineManager.setOnline(false)
      return Promise.reject(new TypeError('Failed to fetch'))
    })
    api.getCompany.mockResolvedValue(APPLE)
    api.getCompanyFilings.mockResolvedValue([])
    renderRoute()
    await waitFor(() => expect(companyState()).toMatchObject({ status: 'pending', fetchStatus: 'paused', fetchFailureCount: 1 }))
    await settle()
    expect(api.getCompany).toHaveBeenCalledTimes(1)
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument()
    expect(screen.queryByText(/No company with a ticker on SEC EDGAR/)).not.toBeInTheDocument()
    expect(screen.queryByText('Failed to fetch', { exact: false })).not.toBeInTheDocument()

    act(() => onlineManager.setOnline(true))
    expect(await screen.findByRole('heading', { level: 1, name: 'Apple Inc.' })).toBeInTheDocument()
    expect(api.getCompany).toHaveBeenCalledTimes(2)
  })

  it('a filings failure under a loaded company is an inline Notice with a Retry, without the raw error', async () => {
    api.getCompany.mockResolvedValue(APPLE)
    api.getCompanyFilings.mockRejectedValue(new ApiError(503, RAW))
    renderRoute()
    const notice = await screen.findByRole('alert')
    expect(notice).toHaveTextContent('Couldn’t load the filings')
    expect(notice).toHaveTextContent('Try again in a moment.')
    // Inside the "Recent filings" card, the Notice's scale: never a GuidanceCard's standalone panel (no
    // heading of its own, no shadow) nested in the card (DESIGN_SYSTEM.md, GuidanceCard).
    expect(notice.closest('[class*="rounded-3xl"]')).toContainElement(screen.getByRole('heading', { level: 2, name: 'Recent filings' }))
    expect(screen.queryByRole('heading', { name: 'Couldn’t load the filings' })).not.toBeInTheDocument()
    expect(notice.className).not.toMatch(/shadow/)
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    expect(screen.queryByText(RAW, { exact: false })).not.toBeInTheDocument()
  })
})
