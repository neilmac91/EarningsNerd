import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useViewer, useEarningsAlerts } from '@/features/calendar/hooks/useCalendar'
import { AlertBell } from '@/features/calendar/components/AlertBell'

const mockGetCurrentUserSafe = vi.fn()
const mockEnableEarningsAlert = vi.fn()
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: () => mockGetCurrentUserSafe() }))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: false }) }))
vi.mock('@/features/calendar/api/calendar-api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/calendar/api/calendar-api')>()
  return {
    ...actual,
    getEarningsAlertTickers: async () => [],
    enableEarningsAlert: (ticker: string) => mockEnableEarningsAlert(ticker),
    disableEarningsAlert: vi.fn(),
  }
})

function Harness() {
  const viewer = useViewer()
  const alerts = useEarningsAlerts(viewer)
  return (
    <>
      <AlertBell ticker="AAPL" alerts={alerts} signedIn={viewer.signedIn} />
      {/* Calls the real toggle regardless of the bell's disabled state, so the guard is proven. */}
      <button type="button" onClick={(e) => alerts.toggle('AAPL', e.currentTarget)}>direct toggle</button>
      <output data-testid="blocked">{alerts.blocked?.kind ?? 'none'}</output>
    </>
  )
}

function renderHarness() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <Harness />
    </QueryClientProvider>,
  )
}

describe('calendar alert bell while identity is unresolved', () => {
  beforeEach(() => {
    mockGetCurrentUserSafe.mockReset()
    mockEnableEarningsAlert.mockReset()
    mockEnableEarningsAlert.mockResolvedValue(undefined)
  })

  it('waits for identity instead of treating a pending /me as a guest', async () => {
    let resolveIdentity!: (value: unknown) => void
    mockGetCurrentUserSafe.mockReturnValue(new Promise((resolve) => { resolveIdentity = resolve }))
    renderHarness()

    const bell = screen.getByRole('button', { name: /checking your account/i })
    expect(bell).toBeDisabled()
    expect(bell).not.toHaveAccessibleName(/sign in/i)
    fireEvent.click(screen.getByRole('button', { name: 'direct toggle' }))
    expect(screen.getByTestId('blocked')).toHaveTextContent('none')
    expect(mockEnableEarningsAlert).not.toHaveBeenCalled()

    resolveIdentity({ id: 1, email: 'u@example.test' })
    const ready = await screen.findByRole('button', { name: /get an email the morning AAPL reports/i })
    expect(ready).toBeEnabled()
    fireEvent.click(ready)
    await waitFor(() => expect(mockEnableEarningsAlert).toHaveBeenCalledWith('AAPL'))
    expect(screen.getByTestId('blocked')).toHaveTextContent('none')
  })

  it('treats a failed identity check as a guest instead of checking forever', async () => {
    mockGetCurrentUserSafe.mockRejectedValue(new Error('upstream unavailable'))
    renderHarness()

    const bell = await screen.findByRole('button', { name: /sign in to get earnings alerts/i })
    expect(bell).toBeEnabled()
    expect(screen.queryByRole('button', { name: /checking your account/i })).not.toBeInTheDocument()
    fireEvent.click(bell)
    expect(screen.getByTestId('blocked')).toHaveTextContent('signin')
  })

  it('still routes a confirmed guest to the sign-in prompt', async () => {
    mockGetCurrentUserSafe.mockResolvedValue(null)
    renderHarness()

    const bell = await screen.findByRole('button', { name: /sign in to get earnings alerts/i })
    expect(bell).toBeEnabled()
    fireEvent.click(bell)
    expect(screen.getByTestId('blocked')).toHaveTextContent('signin')
    expect(mockEnableEarningsAlert).not.toHaveBeenCalled()
  })
})
