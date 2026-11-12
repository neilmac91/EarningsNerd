import React from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { beforeEach, describe, expect, it, vi } from 'vitest'

/**
 * E29 (7): a Google or Apple login returns the reader to where they were headed, as a password login honours
 * `?redirect=`. The provider's round trip drops the login page's query string, so the start control stashes the
 * destination as the sign-in leaves (features/auth/components/OAuthStartControl.tsx), through
 * lib/postAuthRedirect.ts, which keeps only an internal path; the landing page consumes it
 * (oauthCompletePage.spec.tsx). Both shapes of the control stash: the plain link of a login, and the button of an
 * invited or agreed sign-up, which stashes only once its start has answered with the provider's address.
 */
const { startOAuthWithInvite, searchParams } = vi.hoisted(() => ({
  startOAuthWithInvite: vi.fn<(provider: string, invite?: string) => Promise<string>>(),
  searchParams: new URLSearchParams(),
}))
vi.mock('@/features/auth/api/auth-api', () => ({
  startOAuthWithInvite,
  login: vi.fn(),
  getCurrentUserSafe: async () => null,
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), refresh: vi.fn() }),
  useSearchParams: () => searchParams,
}))
vi.mock('@/lib/analytics', () => ({ default: { loginCompleted: vi.fn() } }))
vi.mock('@/lib/featureFlags', () => ({ TURNSTILE_ENABLED: false, ENABLE_APPLE_SIGNIN: true }))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))
vi.mock('@/features/auth/components/TurnstileWidget', () => ({ default: () => null }))
vi.mock('@/features/marketing/api/access-api', () => ({ getRegistrationConfig: async () => null }))

import LoginPage from '@/app/login/page'
import SocialAuthButtons from '@/features/auth/components/SocialAuthButtons'
import { consumePostAuthRedirect } from '@/lib/postAuthRedirect'

/** Presses the control without letting jsdom try the navigation its link asks for; React's handler still runs. */
function press(control: HTMLElement) {
  control.addEventListener('click', (event) => event.preventDefault())
  fireEvent.click(control)
}

beforeEach(() => {
  localStorage.clear()
  startOAuthWithInvite.mockReset()
  Array.from(searchParams.keys()).forEach((key) => searchParams.delete(key))
})

describe('an OAuth start keeps where the reader was headed (E29 (7))', () => {
  it.each(['Google', 'Apple'])("the login page hands its ?redirect= to %s's start, which stashes it as it leaves", (provider) => {
    searchParams.set('redirect', '/filing/123')
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><LoginPage /></QueryClientProvider>)
    // Nothing is stashed by opening the page: a reader who then logs in with a password uses ?redirect= itself.
    expect(localStorage.length).toBe(0)
    press(screen.getByRole('link', { name: `Continue with ${provider}` }))
    expect(consumePostAuthRedirect()).toBe('/filing/123')
  })

  it.each([
    ['no destination', undefined],
    ['an empty one', ''],
    ['a path on another site', '//evil.example/filing/1'],
    ['a backslash path a browser reads as another site', '/\\evil.example'],
    ['a tab path a browser reads as another site', '/\t/evil.example'],
    ['a line-feed path a browser reads as another site', '/\n/evil.example'],
    ['an absolute address', 'https://evil.example/'],
  ])('stashes nothing for %s', (_name, returnTo) => {
    render(<SocialAuthButtons apiBase="https://api.test" returnTo={returnTo} />)
    press(screen.getByRole('link', { name: 'Continue with Google' }))
    expect(consumePostAuthRedirect()).toBeNull()
  })

  it('an invited sign-up stashes it once its start answered, and never when the start failed', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    try {
      startOAuthWithInvite.mockRejectedValueOnce(new Error('offline'))
      render(<SocialAuthButtons apiBase="https://api.test" invite="invite-token" returnTo="/filing/123" />)
      fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
      expect(await screen.findByText("Couldn't continue with Google. Please try again.")).toBeInTheDocument()
      expect(assign).not.toHaveBeenCalled()
      expect(localStorage.length).toBe(0)

      startOAuthWithInvite.mockResolvedValueOnce('https://accounts.example/authorize')
      fireEvent.click(screen.getByRole('button', { name: 'Continue with Google' }))
      await waitFor(() => expect(assign).toHaveBeenCalledWith('https://accounts.example/authorize'))
      expect(consumePostAuthRedirect()).toBe('/filing/123')
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
