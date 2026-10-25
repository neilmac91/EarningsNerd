import { describe, it, expect, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider, onlineManager } from '@tanstack/react-query'
import { queryKeys } from '@/lib/queryKeys'

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
import NotificationBell from '@/features/notifications/components/NotificationBell'

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

function renderBell(cached?: typeof sample) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  if (cached) queryClient.setQueryData(queryKeys.notifications(), cached)
  const view = render(
    <QueryClientProvider client={queryClient}>
      <NotificationBell />
    </QueryClientProvider>,
  )
  return { ...view, queryClient }
}

const deferred = <T,>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
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
    const link = screen.getByRole('menuitem', { name: /New 10-Q from AAPL/i })
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

  it.each([true, false])('does not claim empty before the first read settles (online=%s)', async (online) => {
    onlineManager.setOnline(online)
    vi.mocked(getNotifications).mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    const { unmount, queryClient } = renderBell()
    try {
      await user.click(screen.getByRole('button', { name: 'Notifications' }))
      expect(screen.getByRole('status')).toHaveTextContent('Loading filing alerts')
      expect(screen.queryByText(/no filing alerts yet/i)).not.toBeInTheDocument()
      expect(markNotificationsSeen).not.toHaveBeenCalled()
    } finally {
      unmount()
      queryClient.clear()
      onlineManager.setOnline(true)
    }
  })

  it('keeps a failed read and focused recovery through a repeated attempt, then shows the confirmed result', async () => {
    vi.mocked(getNotifications).mockRejectedValueOnce(new Error('offline'))
    const user = userEvent.setup()
    renderBell()
    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Could not load filing alerts.')
    expect(screen.queryByText(/no filing alerts yet/i)).not.toBeInTheDocument()
    const recovery = deferred<typeof sample>()
    vi.mocked(getNotifications).mockReturnValueOnce(recovery.promise)
    const retry = screen.getByRole('button', { name: 'Try again' })
    retry.focus()
    await user.keyboard('{Enter}{Enter}')
    expect(getNotifications).toHaveBeenCalledTimes(2)
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load filing alerts.')
    expect(screen.queryByText('Loading filing alerts…')).not.toBeInTheDocument()
    expect(retry).toHaveFocus()
    await act(async () => recovery.resolve({ items: [], unread_count: 0 }))
    expect(await screen.findByText(/no filing alerts yet/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('Notifications')).toHaveFocus())
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('keeps cached alerts visible when a refresh fails and does not call stale emptiness current', async () => {
    vi.mocked(getNotifications).mockRejectedValue(new Error('offline'))
    const user = userEvent.setup()
    const { queryClient } = renderBell({ ...sample, unread_count: 0 })
    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    await act(async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.notifications() }) })
    expect(await screen.findByRole('alert')).toHaveTextContent('Showing the last loaded alerts.')
    expect(screen.getByRole('menuitem', { name: /New 10-Q from AAPL/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Try again' })).toBeInTheDocument()
    // A known empty snapshot also remains stale; it cannot become today's empty-data claim.
    act(() => { queryClient.setQueryData(queryKeys.notifications(), { items: [], unread_count: 0 }) })
    await act(async () => { await queryClient.invalidateQueries({ queryKey: queryKeys.notifications() }) })
    expect(await screen.findByRole('alert')).toHaveTextContent('Showing the last loaded alerts.')
    expect(screen.queryByText(/no filing alerts yet/i)).not.toBeInTheDocument()
  })

  it.each(['inside', 'outside', 'modal', 'handled'])('returns Escape focus only when the bell owns it (%s)', async (owner) => {
    vi.mocked(getNotifications).mockRejectedValue(new Error('offline'))
    const user = userEvent.setup()
    renderBell()
    await user.click(screen.getByRole('button', { name: 'Notifications' }))
    const retry = await screen.findByRole('button', { name: 'Try again' })
    render(owner === 'modal'
      ? <div role="dialog" aria-modal="true"><button>Other action</button></div>
      : <button>Other action</button>)
    const target = owner === 'inside' ? retry : screen.getByRole('button', { name: 'Other action' })
    target.focus()
    if (owner === 'handled') target.addEventListener('keydown', (event) => event.preventDefault(), { once: true })
    fireEvent.keyDown(target, { key: 'Escape' })
    if (owner === 'modal' || owner === 'handled') {
      expect(screen.getByRole('menu')).toBeInTheDocument()
    } else {
      expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    }
    expect(owner === 'inside' ? screen.getByRole('button', { name: 'Notifications' }) : target).toHaveFocus()
  })

  // The header's two menus sit on one rung, the header's own (z-header 50; DESIGN_SYSTEM.md Stacking),
  // inside its stacking context: the notification menu as the token, the account menu (UserMenu.tsx)
  // still as the numeric z-50 until its owner moves it to the token.
  it('opens its menu on the same rung as the account menu, the header rung', async () => {
    vi.mocked(getNotifications).mockResolvedValue({ items: [], unread_count: 0 })
    const user = userEvent.setup()
    renderBell()

    await user.click(await screen.findByRole('button', { name: /notifications/i }))
    const menu = await screen.findByRole('menu')
    const rung = (classes: string[]) => classes.filter((c) => /^z-/.test(c)).map((c) => HEADER_RUNG[c] ?? c)
    expect(rung([...menu.classList])).toEqual([50])

    const userMenu = readFileSync(path.resolve(__dirname, '../../features/auth/components/UserMenu.tsx'), 'utf8')
    expect(rung(userMenu.match(/(?<![\w-])z-[\w[\]-]+/g) ?? [])).toEqual([50])
  })
})

const HEADER_RUNG: Record<string, number> = { 'z-header': 50, 'z-50': 50 }
