import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('@/features/notifications/api/notifications-api', () => ({
  getNotifications: vi.fn(),
  markNotificationsSeen: vi.fn(),
}))

import {
  getNotifications,
  markNotificationsSeen,
} from '@/features/notifications/api/notifications-api'
import NotificationBell from '@/components/NotificationBell'

const sample = {
  items: [
    {
      id: 1,
      filing_id: 123,
      ticker: 'AAPL',
      company_name: 'Apple Inc.',
      filing_type: '10-Q',
      filing_date: '2026-01-03T00:00:00Z',
      created_at: '2026-01-03T00:00:00Z',
      read: false,
    },
  ],
  unread_count: 1,
}

function renderBell() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={queryClient}>
      <NotificationBell />
    </QueryClientProvider>,
  )
}

describe('NotificationBell', () => {
  beforeEach(() => {
    vi.mocked(getNotifications).mockReset()
    vi.mocked(markNotificationsSeen).mockReset()
  })

  it('shows the unread count badge', async () => {
    vi.mocked(getNotifications).mockResolvedValue(sample)
    renderBell()
    expect(await screen.findByText('1')).toBeInTheDocument()
  })

  it('opens the dropdown, lists alerts, and marks them seen', async () => {
    vi.mocked(getNotifications).mockResolvedValue(sample)
    vi.mocked(markNotificationsSeen).mockResolvedValue({
      items: [{ ...sample.items[0], read: true }],
      unread_count: 0,
    })
    const user = userEvent.setup()
    renderBell()

    await screen.findByText('1') // wait for data
    await user.click(screen.getByRole('button', { name: /notifications/i }))

    expect(await screen.findByRole('menu')).toBeInTheDocument()
    expect(screen.getByText('AAPL')).toBeInTheDocument()
    const link = screen.getByRole('menuitem', { name: /AAPL filed a 10-Q/i })
    expect(link).toHaveAttribute('href', '/filing/123')
    expect(markNotificationsSeen).toHaveBeenCalledTimes(1)
  })

  it('renders an empty state with no badge when there are no alerts', async () => {
    vi.mocked(getNotifications).mockResolvedValue({ items: [], unread_count: 0 })
    const user = userEvent.setup()
    renderBell()

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    expect(await screen.findByText(/no filing alerts yet/i)).toBeInTheDocument()
    expect(screen.queryByText('1')).not.toBeInTheDocument()
    expect(markNotificationsSeen).not.toHaveBeenCalled()
  })
})
