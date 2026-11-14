import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useViewer, useEarningsAlerts } from '@/features/calendar/hooks/useCalendar'
import { AlertBell } from '@/features/calendar/components/AlertBell'
import { canonicalTicker } from '@/features/calendar/lib/tickers'

// The alert list names the companies' tickers (SEC's BRK-B); a calendar event carries Alpha Vantage's (BRK.B).
const mockAlertTickers = vi.fn()
const mockEnableEarningsAlert = vi.fn()
const mockDisableEarningsAlert = vi.fn()
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: async () => ({ id: 1, email: 'u@example.test' }) }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: false }) }))
vi.mock('@/features/calendar/api/calendar-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/calendar/api/calendar-api')>()
  return {
    ...actual,
    getEarningsAlertTickers: async () => mockAlertTickers(),
    enableEarningsAlert: (ticker: string) => mockEnableEarningsAlert(ticker),
    disableEarningsAlert: (ticker: string) => mockDisableEarningsAlert(ticker),
  }
})

function Harness({ tickers }: { tickers: string[] }) {
  const viewer = useViewer()
  const alerts = useEarningsAlerts(viewer)
  return (
    <>
      {tickers.map((t) => (
        <AlertBell key={t} ticker={t} alerts={alerts} signedIn={viewer.signedIn} />
      ))}
      <output data-testid="blocked">{alerts.blocked?.kind ?? 'none'}</output>
    </>
  )
}

function renderHarness(tickers: string[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <Harness tickers={tickers} />
    </QueryClientProvider>,
  )
}

describe('a dual-class company on the calendar', () => {
  beforeEach(() => {
    mockAlertTickers.mockReset()
    mockEnableEarningsAlert.mockReset().mockResolvedValue(undefined)
    mockDisableEarningsAlert.mockReset().mockResolvedValue(undefined)
  })

  it('compares tickers as the backend does', () => {
    expect(canonicalTicker(' brk-b ')).toBe('BRK.B')
    expect(canonicalTicker('BRK.B')).toBe('BRK.B')
    expect(canonicalTicker('aapl')).toBe('AAPL')
  })

  it('reads its bell on when the alert list names the company and turns it off', async () => {
    mockAlertTickers.mockResolvedValue(['BRK-B', 'AAPL'])
    renderHarness(['BRK.B', 'AAPL', 'BF.B'])

    const brk = await screen.findByRole('button', { name: 'Turn off earnings alerts for BRK.B' })
    expect(brk).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'Turn off earnings alerts for AAPL' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: /get an email the morning BF\.B reports/i })).toHaveAttribute('aria-pressed', 'false')

    fireEvent.click(brk)
    await waitFor(() => expect(mockDisableEarningsAlert).toHaveBeenCalledWith('BRK.B'))
    expect(mockEnableEarningsAlert).not.toHaveBeenCalled()
    expect(await screen.findByRole('button', { name: /get an email the morning BRK\.B reports/i })).toHaveAttribute('aria-pressed', 'false')
  })

  it('frees a Free slot when its alert is turned off, whichever side spells the class with a dot', async () => {
    mockAlertTickers.mockResolvedValue(['BRK.B', 'AAPL', 'MSFT'])
    renderHarness(['BRK-B', 'BF-B'])

    fireEvent.click(await screen.findByRole('button', { name: 'Turn off earnings alerts for BRK-B' }))
    await waitFor(() => expect(mockDisableEarningsAlert).toHaveBeenCalledWith('BRK-B'))
    fireEvent.click(await screen.findByRole('button', { name: /get an email the morning BF-B reports/i }))
    await waitFor(() => expect(mockEnableEarningsAlert).toHaveBeenCalledWith('BF-B'))
    expect(screen.getByTestId('blocked')).toHaveTextContent('none')
  })
})
