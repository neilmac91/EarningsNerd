import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import LoginPage from '@/app/login/page'
import { consumePostAuthRedirect, stashPostAuthRedirect } from '@/lib/postAuthRedirect'

const mockLogin = vi.fn()
const mockPush = vi.fn()
const searchParams = new URLSearchParams()

vi.mock('@/features/auth/api/auth-api', () => ({
  login: (...args: unknown[]) => mockLogin(...args),
  getCurrentUserSafe: async () => ({ id: 1, email: 'reader@example.com' }),
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, refresh: vi.fn() }),
  useSearchParams: () => searchParams,
}))
vi.mock('@/lib/analytics', () => ({ default: { loginCompleted: vi.fn() } }))
vi.mock('@/lib/featureFlags', () => ({ TURNSTILE_ENABLED: false }))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/SocialAuthButtons', () => ({ default: () => null }))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => null }))

function renderLogin() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(<QueryClientProvider client={client}><LoginPage /></QueryClientProvider>)
}

function submitLogin() {
  fireEvent.click(screen.getByRole('button', { name: 'Continue with email' }))
  fireEvent.change(screen.getByLabelText('Email'), { target: { value: 'reader@example.com' } })
  fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'test-password' } })
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('completed email-login redirect consumption', () => {
  beforeEach(() => {
    localStorage.clear()
    Array.from(searchParams.keys()).forEach((key) => searchParams.delete(key))
    mockLogin.mockReset().mockResolvedValue(undefined)
    mockPush.mockReset()
  })

  it.each([
    ['/pricing?billing=monthly', '/pricing?billing=monthly'],
    ['/dashboard/watchlist', '/dashboard/watchlist'],
    ['//example.com', '/'],
    ['/\\example.com', '/'],
  ])('consumes the stash when explicit destination %s completes at %s', async (explicit, expected) => {
    stashPostAuthRedirect('/pricing?billing=monthly')
    searchParams.set('redirect', explicit)
    const firstLogin = renderLogin()
    submitLogin()
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith(expected))
    firstLogin.unmount()

    // A later ordinary login must not replay the completed pricing signup's destination.
    // Do not consume the stash in the assertion: exercise the real login consumer twice.
    searchParams.delete('redirect')
    mockPush.mockClear()
    renderLogin()
    submitLogin()
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/'))
    expect(consumePostAuthRedirect()).toBeNull()
  })

  it('retains the fallback across a rejected login and consumes it on the successful retry', async () => {
    stashPostAuthRedirect('/pricing?billing=yearly')
    mockLogin.mockRejectedValueOnce(new Error('Credentials rejected'))
    renderLogin()
    submitLogin()
    await screen.findByText('Credentials rejected')
    expect(mockPush).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith('/pricing?billing=yearly'))
    expect(consumePostAuthRedirect()).toBeNull()
  })
})
