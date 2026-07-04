import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}))

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
}))

// Stub chrome/children so the test isolates Header's auth-state branching.
vi.mock('@/components/ThemeToggle', () => ({ ThemeToggle: () => null }))
vi.mock('@/components/EarningsNerdLogo', () => ({ default: () => null }))
vi.mock('@/components/NotificationBell', () => ({
  default: () => <div data-testid="notification-bell" />,
}))
vi.mock('@/components/UserMenu', () => ({
  default: ({ user }: { user: { email: string } }) => <div data-testid="user-menu">{user.email}</div>,
}))

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: vi.fn(),
  logout: vi.fn(),
}))

import { getCurrentUserSafe } from '@/features/auth/api/auth-api'
import Header from '@/components/Header'

const mockUser = {
  id: 1,
  email: 'neil@earningsnerd.io',
  full_name: 'Neil Mac',
  is_pro: true,
  is_beta: false,
  is_admin: true,
  email_verified: true,
}

function renderHeader() {
  // retry:false so a thrown queryFn surfaces as an error immediately (no backoff in tests).
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <Header />
    </QueryClientProvider>,
  )
  return { queryClient, ...utils }
}

describe('Header auth state', () => {
  beforeEach(() => {
    vi.mocked(getCurrentUserSafe).mockReset()
  })

  it('shows the user menu (avatar) when logged in', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(mockUser)
    renderHeader()

    expect(await screen.findByTestId('user-menu')).toHaveTextContent('neil@earningsnerd.io')
    expect(screen.getByTestId('notification-bell')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument()
  })

  it('shows Log In / Get Started only on a definitive logged-out (null)', async () => {
    vi.mocked(getCurrentUserSafe).mockResolvedValue(null)
    renderHeader()

    expect(await screen.findByRole('link', { name: /log in/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /get started/i })).toBeInTheDocument()
    expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
  })

  // While the auth check is still in flight (pending, including retry backoff) we hold the
  // skeleton — never flash the logged-out CTAs to a user who may actually be signed in.
  it('holds the skeleton while the auth check is pending', () => {
    // A promise that never resolves keeps the query pending.
    vi.mocked(getCurrentUserSafe).mockReturnValue(new Promise<never>(() => {}))
    const { container } = renderHeader()

    // The auth-loading bone is the DS <Skeleton> (shimmer sweep), not a raw animate-pulse.
    expect(container.querySelector('.animate-shimmer')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: /log in/i })).not.toBeInTheDocument()
    expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
  })

  // Safety net: once the check has *settled* into an error (non-401 failure, all retries
  // exhausted), the header degrades to the logged-out CTAs so the user is never trapped on a
  // dead placeholder circle — the bug that hid the account menu behind a stuck skeleton.
  it('falls back to the logged-out CTAs once the auth check settles in error', async () => {
    // The query retries with backoff (retry: 3); drive fake timers to exhaust the retries so we
    // assert the settled *error* state, not the (still-skeleton) pending state.
    vi.useFakeTimers()
    try {
      vi.mocked(getCurrentUserSafe).mockRejectedValue(new Error('timeout of 30000ms exceeded'))
      const { queryClient, container } = renderHeader()

      await vi.advanceTimersByTimeAsync(30_000) // past the full retry backoff (~1s+2s+4s)

      expect(queryClient.getQueryState(['current-user'])?.status).toBe('error')
      expect(screen.getByRole('link', { name: /log in/i })).toBeInTheDocument()
      expect(screen.getByRole('link', { name: /get started/i })).toBeInTheDocument()
      expect(container.querySelector('.animate-shimmer')).not.toBeInTheDocument()
      expect(screen.queryByTestId('user-menu')).not.toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })
})
