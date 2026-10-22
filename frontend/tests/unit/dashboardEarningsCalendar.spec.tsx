import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

vi.mock('@/features/dashboard/api/dashboard-api', () => ({ getUpcomingCalendar: vi.fn() }))

import { getUpcomingCalendar } from '@/features/dashboard/api/dashboard-api'
import EarningsCalendar from '@/features/dashboard/components/EarningsCalendar'

/**
 * The dashboard's upcoming earnings name each company as the calendar's own rows do: EDGAR's conformed name, often in
 * capitals, in its display casing (E146, lib/formatCompanyName.ts). The ticker leads the row as served.
 */
describe('the dashboard’s upcoming earnings', () => {
  it('prints a served name in capitals in its display casing', async () => {
    vi.mocked(getUpcomingCalendar).mockResolvedValue([
      { ticker: 'AAPL', company_name: 'APPLE INC.', earnings_date: '2026-10-29', time: 'amc', eps_estimated: null, revenue_estimated: null },
    ])
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={client}>
        <EarningsCalendar />
      </QueryClientProvider>,
    )
    const row = (await screen.findByText('AAPL')).closest('li') as HTMLElement
    expect(row).toHaveTextContent('Apple Inc.')
    expect(row).not.toHaveTextContent('APPLE INC.')
  })
})
