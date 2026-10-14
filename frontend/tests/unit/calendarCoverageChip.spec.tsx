import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import EarningsCalendarPage from '@/features/calendar/components/EarningsCalendarPage'
import type { CalendarEvent, CalendarUniverse } from '@/features/calendar/api/calendar-api'

/**
 * The calendar's coverage chip renders only when the backend reports the index universe
 * (`universe: 'sp500_nasdaq100'`), which the page's fixture mode never does, so the chip is checked
 * here on a bounded payload instead: seven reports on the week's Monday (so the week view also shows
 * its "+N more" control) under the known universe. The chip shows its caption there and is absent
 * while the universe is 'all'. Its colour and the "+N more" control's are rule 2's to hold
 * (brandCopyRules.spec.ts; D-030): the chip carries "500" and "100", so a sage chip fails that rule.
 */

let universe: CalendarUniverse = 'sp500_nasdaq100'

// The page takes its week from the clock. Pinned to a week with no market holiday, since a holiday
// Monday renders "Market closed" in place of the reports (and of the "+N more" control) this spec waits for.
beforeAll(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date('2026-03-10T15:00:00Z'))
})
afterAll(() => {
  vi.useRealTimers()
})

vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => null }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: false }) }))
vi.mock('@/features/calendar/api/calendar-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/calendar/api/calendar-api')>()
  const day = (from: string): CalendarEvent[] =>
    Array.from({ length: 7 }, (_, i) => ({
      ticker: `T${i}X`,
      company_name: `Company ${i}`,
      event_date: from,
      event_time: i % 2 ? 'amc' : 'bmo',
      status: 'estimated',
      confidence: 'high',
      eps_estimate: 1,
      eps_actual: null,
      anticipation_score: 100 - i,
    }))
  return {
    ...actual,
    getCalendar: async (from: string) => ({ events: day(from), universe }),
    getEarningsAlertTickers: async () => [],
  }
})

async function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={queryClient}>
      <EarningsCalendarPage />
    </QueryClientProvider>,
  )
  // The first render of the page in a cold multi-file run can take over a second to transform; the wait allows it.
  await waitFor(() => expect(screen.getAllByRole('button', { name: /^\+\d+ more$/ }).length).toBeGreaterThan(0), { timeout: 5000 })
}

describe('the calendar coverage chip under the known universe', () => {
  it('shows its caption under the known universe, beside the week view\'s "+N more"', async () => {
    universe = 'sp500_nasdaq100'
    await renderPage()
    expect(await screen.findByText(/^Covering the S&P 500 & Nasdaq 100$/)).toBeInTheDocument()
  })

  it('is absent while the backend serves every company', async () => {
    universe = 'all'
    await renderPage()
    expect(screen.queryByText(/^Covering the S&P 500/)).not.toBeInTheDocument()
  })
})
