import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useViewer, useEarningsAlerts } from '@/features/calendar/hooks/useCalendar'
import { AlertBell } from '@/features/calendar/components/AlertBell'

/**
 * A keyboard user who toggles an earnings-alert bell keeps their place. While the toggle is in flight
 * the bell is aria-disabled, never natively `disabled`: Chromium blurs a focused button that turns
 * `disabled` to <body>, so every toggle used to send focus back to the top of the page (measured on a
 * production build). jsdom does not blur disabled elements, so the attribute is what this pins.
 */

let resolveEnable: () => void = () => {}
const mockEnableEarningsAlert = vi.fn(() => new Promise<void>((resolve) => { resolveEnable = resolve }))
vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: async () => ({ id: 1, email: 'a@b.c', full_name: null, is_pro: true, is_beta: false, is_admin: false, email_verified: true }),
}))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({ getUsage: async () => ({ is_pro: true }) }))
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
  return <AlertBell ticker="AAPL" alerts={alerts} signedIn={viewer.signedIn} />
}

describe('the calendar bell while its toggle is in flight', () => {
  it('stays focusable (aria-disabled, not disabled), keeps focus and ignores a second activation', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(
      <QueryClientProvider client={queryClient}>
        <Harness />
      </QueryClientProvider>,
    )
    const bell = await screen.findByRole('button', { name: 'Get an email the morning AAPL reports' })
    bell.focus()
    fireEvent.click(bell)

    await waitFor(() => expect(bell).toHaveAttribute('aria-disabled', 'true'))
    expect(bell).not.toBeDisabled()
    expect(document.activeElement).toBe(bell)
    fireEvent.click(bell)
    expect(mockEnableEarningsAlert).toHaveBeenCalledTimes(1)

    await act(async () => resolveEnable())
    await waitFor(() => expect(bell).not.toHaveAttribute('aria-disabled'))
    expect(bell).toHaveAttribute('aria-pressed', 'true')
    expect(document.activeElement).toBe(bell)
  })
})
