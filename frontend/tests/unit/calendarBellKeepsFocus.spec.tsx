import { describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useViewer, useEarningsAlerts } from '@/features/calendar/hooks/useCalendar'
import { AlertBell, BellPopover } from '@/features/calendar/components/AlertBell'

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

function Harness({ showBell = true }: { showBell?: boolean }) {
  const viewer = useViewer()
  const alerts = useEarningsAlerts(viewer)
  return <>
    {showBell && <AlertBell ticker="AAPL" alerts={alerts} signedIn={viewer.signedIn} />}
    {alerts.blocked && <BellPopover blocked={alerts.blocked} onClose={alerts.clearBlocked} />}
  </>
}

describe('the calendar bell while its toggle is in flight', () => {
  it.each([false, true])('anchors a delayed failure to the bell after it moved (inside day dialog: %s)', async (inDialog) => {
    let reject!: (error: Error) => void
    mockEnableEarningsAlert.mockImplementationOnce(() => new Promise<void>((_resolve, fail) => { reject = fail }))
    const container = document.createElement(inDialog ? 'dialog' : 'div')
    if (inDialog) container.setAttribute('open', '')
    document.body.appendChild(container)
    try {
      const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
      render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>, { container })
      const bell = await screen.findByRole('button', { name: 'Get an email the morning AAPL reports' })
      const rect = vi.spyOn(bell, 'getBoundingClientRect').mockReturnValue(new DOMRect(100, 400, 28, 28))
      fireEvent.click(bell)
      await waitFor(() => expect(bell).toHaveAttribute('aria-disabled', 'true'))
      rect.mockReturnValue(new DOMRect(100, 160, 28, 28))
      await act(async () => reject(new Error('The alert could not be saved.')))
      const popover = await screen.findByRole('group', { name: 'Alert not enabled for AAPL' })
      expect(popover.style.top).toBe('196px')
      if (inDialog) expect(container).toContainElement(popover)
      expect(popover).toHaveAccessibleDescription('The alert could not be saved.')
    } finally {
      container.remove()
    }
  })

  it.each(['removed', 'hidden', 'above', 'below'] as const)('centres a delayed failure when the triggering bell is %s', async (location) => {
    let reject!: (error: Error) => void
    mockEnableEarningsAlert.mockImplementationOnce(() => new Promise<void>((_resolve, fail) => { reject = fail }))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    const view = render(<QueryClientProvider client={client}><Harness /></QueryClientProvider>)
    const bell = await screen.findByRole('button', { name: 'Get an email the morning AAPL reports' })
    fireEvent.click(bell)
    await waitFor(() => expect(bell).toHaveAttribute('aria-disabled', 'true'))
    if (location === 'removed') {
      view.rerender(<QueryClientProvider client={client}><Harness showBell={false} /></QueryClientProvider>)
    } else {
      const rect = location === 'hidden' ? new DOMRect() : new DOMRect(100, location === 'above' ? -500 : window.innerHeight + 100, 28, 28)
      vi.spyOn(bell, 'getBoundingClientRect').mockReturnValue(rect)
    }
    await act(async () => reject(new Error('The alert could not be saved.')))
    const popover = await screen.findByRole('group', { name: 'Alert not enabled for AAPL' })
    expect(popover.style.left).toBe(`${window.innerWidth / 2 - 150}px`)
    expect(popover.style.top).toBe(`${window.innerHeight / 2 + 8}px`)
  })

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
