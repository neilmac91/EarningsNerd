import React from 'react'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

/**
 * The login page's sentence for an OAuth login whose landing page could not exchange its code (E29 (5)), in a build
 * with Sign in with Apple on: it names both providers, as the buttons beside it offer both. A build without Apple names
 * Google alone (authPagesCopy.spec.tsx), so no build names a provider it does not show (chief design on #1963).
 */
const { useSearchParams } = vi.hoisted(() => ({ useSearchParams: vi.fn<() => URLSearchParams>() }))
vi.mock('next/navigation', () => ({
  useSearchParams,
  useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/login',
}))
vi.mock('@/features/auth/api/auth-api', () => ({ getCurrentUserSafe: vi.fn(), login: vi.fn() }))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => null }))
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: vi.fn(async () => null) }))
vi.mock('@/lib/featureFlags', async (original) => ({
  ...(await original<typeof import('@/lib/featureFlags')>()),
  ENABLE_APPLE_SIGNIN: true,
}))

import LoginPage from '@/app/login/page'

describe('login: an OAuth login that did not finish, in a build with Sign in with Apple', () => {
  it('names Google and Apple, the two ways in the page offers', () => {
    useSearchParams.mockReturnValue(new URLSearchParams('error=oauth_handoff_failed'))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><LoginPage /></QueryClientProvider>)
    expect(screen.getByText('Your Google or Apple login did not finish. Log in again.')).toBeInTheDocument()
    expect(screen.getByText('Continue with Apple')).toBeInTheDocument()
  })
})
