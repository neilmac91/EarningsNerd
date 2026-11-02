import React, { StrictMode } from 'react'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { queryKeys } from '@/lib/queryKeys'

/**
 * The landing page of a Google or Apple login (app/auth/complete/page.tsx, E29 (5)). The callback's navigation sets no
 * session cookie: it hands this page a one-time code in the URL fragment, and the page's exchange
 * (completeOAuthSignIn, which posts under the session cookies' lock: sessionCookiesAcrossTabs.spec.ts holds that)
 * sets the session. What the page itself owes: the code leaves the address bar before anything else runs, it is posted
 * once (React's development double effect included), a login that took reads the new identity and goes home, and a
 * missing or refused code goes to the login page's own sentence, posting nothing when there is no code.
 */
const { replace, completeOAuthSignIn, getCurrentUserSafe } = vi.hoisted(() => ({
  replace: vi.fn(),
  completeOAuthSignIn: vi.fn<(code: string) => Promise<unknown>>(),
  getCurrentUserSafe: vi.fn<() => Promise<unknown>>(),
}))
vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace, push: vi.fn(), refresh: vi.fn() }),
  usePathname: () => '/auth/complete',
}))
vi.mock('@/features/auth/api/auth-api', () => ({ completeOAuthSignIn, getCurrentUserSafe }))
vi.mock('@/features/auth/components/AuthShell', () => ({
  default: ({ children }: { children: React.ReactNode }) => <main>{children}</main>,
}))

import OAuthCompletePage from '@/app/auth/complete/page'

const READER = { id: 7, email: 'y@example.test' }
const FAILED = '/login?error=oauth_handoff_failed'

function land(url: string) {
  window.history.replaceState(null, '', url)
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <StrictMode>
      <QueryClientProvider client={queryClient}>
        <OAuthCompletePage />
      </QueryClientProvider>
    </StrictMode>,
  )
  return queryClient
}

beforeEach(() => {
  replace.mockReset()
  completeOAuthSignIn.mockReset()
  getCurrentUserSafe.mockReset()
  getCurrentUserSafe.mockResolvedValue(READER)
})

afterEach(() => {
  window.history.replaceState(null, '', '/')
})

describe('the OAuth login landing page (E29 (5))', () => {
  it('takes the code off the address bar before it posts, exchanges it once, reads the new identity and goes home', async () => {
    const seenAtPost: string[] = []
    completeOAuthSignIn.mockImplementation(async () => {
      seenAtPost.push(window.location.href)
      return { status: 'signed_in' }
    })
    const queryClient = land('/auth/complete#code=one-time-code')

    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'))
    expect(completeOAuthSignIn.mock.calls).toEqual([['one-time-code']])
    // The fragment was gone by the time the post went out, and stays gone.
    expect(seenAtPost).toEqual([`${window.location.origin}/auth/complete`])
    expect(window.location.hash).toBe('')
    // The home page opens on the new account, read after the exchange, not on the reset's null.
    expect(getCurrentUserSafe).toHaveBeenCalledTimes(1)
    expect(queryClient.getQueryData(queryKeys.currentUser())).toEqual(READER)
    expect(replace.mock.calls).toEqual([['/']])
  })

  it("sends a refused code to the login page's sentence, and never home", async () => {
    completeOAuthSignIn.mockRejectedValue(Object.assign(new Error('Request failed with status code 400'), { status: 400 }))
    land('/auth/complete#code=used-code')
    await waitFor(() => expect(replace).toHaveBeenCalledWith(FAILED))
    expect(completeOAuthSignIn).toHaveBeenCalledTimes(1)
    expect(getCurrentUserSafe).not.toHaveBeenCalled()
    expect(replace.mock.calls).toEqual([[FAILED]])
  })

  it.each(['/auth/complete', '/auth/complete#code=', '/auth/complete#state=other'])(
    'posts nothing for %s, which carries no code, and goes to the login page',
    async (url) => {
      land(url)
      await waitFor(() => expect(replace).toHaveBeenCalledWith(FAILED))
      expect(completeOAuthSignIn).not.toHaveBeenCalled()
      expect(window.location.hash).toBe('')
    },
  )

  it('goes home after a login that took even when the identity read fails: the read does not hold it back', async () => {
    completeOAuthSignIn.mockResolvedValue({ status: 'signed_in' })
    getCurrentUserSafe.mockRejectedValue(new Error('offline'))
    land('/auth/complete#code=one-time-code')
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'))
  })

  it('names the wait in one h1 inside a status region, its spinner hidden from assistive tech', async () => {
    completeOAuthSignIn.mockReturnValue(new Promise(() => {}))
    land('/auth/complete#code=one-time-code')
    const status = screen.getByRole('status')
    expect(screen.getAllByRole('heading', { level: 1 }).map((heading) => heading.textContent)).toEqual(['Logging you in…'])
    expect(status).toContainElement(screen.getByRole('heading', { level: 1 }))
    expect(status.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    await waitFor(() => expect(completeOAuthSignIn).toHaveBeenCalledTimes(1))
  })
})
