import React, { StrictMode } from 'react'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { queryKeys } from '@/lib/queryKeys'
import { ApiError, SessionLockUnavailable, SessionStillRenewing } from '@/lib/api/client'

/**
 * The landing page of a Google or Apple login (app/auth/complete/page.tsx, E29 (5)). The callback's navigation sets no
 * session cookie: it hands this page a one-time code in the URL fragment, and the page's exchange
 * (completeOAuthSignIn, which posts under the session cookies' lock: sessionCookiesAcrossTabs.spec.ts holds that)
 * sets the session. What the page itself owes: the code leaves the address bar before anything else runs, it is posted
 * once (React's development double effect included), a login that took reads the new identity and goes home, and a
 * missing or refused code goes to the login page's own sentence, posting nothing when there is no code. An exchange
 * that posted nothing (another tab still renewing its session, or a browser that cannot hold the lock) or got no
 * answer it could use leaves a notice in place of the wait, which takes focus, with Log in again and, where another
 * press can help, Try again, which posts the code the page kept (the address bar no longer holds it).
 */
const { replace, completeOAuthSignIn, getCurrentUserSafe, flags } = vi.hoisted(() => ({
  replace: vi.fn(),
  completeOAuthSignIn: vi.fn<(code: string) => Promise<unknown>>(),
  getCurrentUserSafe: vi.fn<() => Promise<unknown>>(),
  // Sign in with Apple, read as the page renders: off, as in CI's build, unless a case turns it on.
  flags: { apple: false },
}))
vi.mock('@/lib/featureFlags', async (original) => ({
  ...(await original<typeof import('@/lib/featureFlags')>()),
  get ENABLE_APPLE_SIGNIN() {
    return flags.apple
  },
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
  flags.apple = false
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

/** The notice that replaced the wait: its alert, the element that takes focus around it, and its Try again, if any. */
async function noticeShown() {
  const alert = await screen.findByRole('alert')
  return { alert, answer: alert.parentElement as HTMLElement, tryAgain: screen.queryByRole('button', { name: 'Try again' }) }
}

const timedOut = () => new ApiError(0, 'The request timed out. Please try again.')

describe('the landing page when the exchange did not finish (E29 (5))', () => {
  it('says another tab is renewing its login, takes focus, and its Try again posts the same code, then goes home', async () => {
    completeOAuthSignIn.mockRejectedValueOnce(new SessionStillRenewing()).mockResolvedValueOnce({ status: 'signed_in' })
    land('/auth/complete#code=one-time-code')
    const { alert, answer, tryAgain } = await noticeShown()
    expect(alert).toHaveTextContent('Another EarningsNerd tab is renewing its login')
    expect(alert).toHaveTextContent('Your login can finish once it is done. Try again in a moment.')
    expect(screen.getAllByRole('heading', { level: 1 }).map((heading) => heading.textContent)).toEqual(['Login not finished'])
    expect(screen.queryByRole('status')).toBeNull()
    expect(document.activeElement).toBe(answer)
    expect(answer).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('link', { name: 'Log in again' })).toHaveAttribute('href', '/login')
    expect(replace).not.toHaveBeenCalled()
    // The fragment is long gone: the press posts the code the page kept.
    expect(window.location.hash).toBe('')

    fireEvent.click(tryAgain as HTMLElement)
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'))
    expect(completeOAuthSignIn.mock.calls).toEqual([['one-time-code'], ['one-time-code']])
    expect(getCurrentUserSafe).toHaveBeenCalledTimes(1)
    expect(replace.mock.calls).toEqual([['/']])
  })

  it('keeps the notice and its focused Try again, busy, while the second post is out', async () => {
    let answer!: (value: unknown) => void
    completeOAuthSignIn.mockRejectedValueOnce(new SessionStillRenewing()).mockReturnValueOnce(new Promise((resolve) => { answer = resolve }))
    land('/auth/complete#code=one-time-code')
    const { tryAgain } = await noticeShown()
    const button = tryAgain as HTMLElement
    act(() => button.focus())
    fireEvent.click(button)
    await waitFor(() => expect(button).toHaveAttribute('aria-busy', 'true'))
    expect(button).toHaveTextContent('Trying again…')
    expect(document.activeElement).toBe(button)
    expect(screen.getByRole('alert')).toHaveTextContent('Another EarningsNerd tab is renewing its login')
    // A press while it is busy posts nothing more.
    fireEvent.click(button)
    expect(completeOAuthSignIn).toHaveBeenCalledTimes(2)

    await act(async () => answer({ status: 'signed_in' }))
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'))
  })

  it('goes to the login page when Try again finds the code already redeemed: a retry is safe', async () => {
    completeOAuthSignIn
      .mockRejectedValueOnce(timedOut())
      .mockRejectedValueOnce(Object.assign(new Error('Request failed with status code 400'), { status: 400 }))
    land('/auth/complete#code=one-time-code')
    const { tryAgain } = await noticeShown()
    fireEvent.click(tryAgain as HTMLElement)
    await waitFor(() => expect(replace).toHaveBeenCalledWith(FAILED))
    expect(completeOAuthSignIn.mock.calls).toEqual([['one-time-code'], ['one-time-code']])
    expect(getCurrentUserSafe).not.toHaveBeenCalled()
  })

  it('says this browser could not finish the Google login, offers Log in again and no Try again (another press would fail the same way)', async () => {
    completeOAuthSignIn.mockRejectedValue(new SessionLockUnavailable())
    land('/auth/complete#code=one-time-code')
    const { alert, answer, tryAgain } = await noticeShown()
    expect(alert).toHaveTextContent("This browser couldn't finish the Google login")
    expect(alert).not.toHaveTextContent(/Apple/)
    expect(alert).toHaveTextContent(
      "It may be an older browser, or one that blocks this site's data. Log in again from an up-to-date browser that allows it.",
    )
    expect(tryAgain).toBeNull()
    expect(screen.getByRole('link', { name: 'Log in again' })).toHaveAttribute('href', '/login')
    expect(document.activeElement).toBe(answer)
    expect(completeOAuthSignIn).toHaveBeenCalledTimes(1)
    expect(replace).not.toHaveBeenCalled()
  })

  it('names Google and Apple where the build offers Sign in with Apple', async () => {
    flags.apple = true
    completeOAuthSignIn.mockRejectedValue(new SessionLockUnavailable())
    land('/auth/complete#code=one-time-code')
    const { alert } = await noticeShown()
    expect(alert).toHaveTextContent("This browser couldn't finish the Google or Apple login")
  })

  it('hands focus to the notice when a Try again ends where this browser cannot hold the lock, and its Try again leaves', async () => {
    completeOAuthSignIn.mockRejectedValueOnce(new SessionStillRenewing()).mockRejectedValueOnce(new SessionLockUnavailable())
    land('/auth/complete#code=one-time-code')
    const { answer, tryAgain } = await noticeShown()
    act(() => (tryAgain as HTMLElement).focus())
    fireEvent.click(tryAgain as HTMLElement)
    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent("This browser couldn't finish the Google login"))
    expect(screen.queryByRole('button', { name: 'Try again' })).toBeNull()
    expect(document.activeElement).toBe(answer)
  })

  it.each([
    ['a network error', () => new ApiError(0, 'Could not reach the server. Try again in a moment.')],
    ['a timeout', timedOut],
    ['a server error', () => new ApiError(503, 'Service temporarily unavailable.')],
    ['an error with no status', () => new Error('offline')],
  ])('says the login could not be finished just now after %s, with Try again and Log in again', async (_, failure) => {
    completeOAuthSignIn.mockRejectedValueOnce(failure()).mockResolvedValueOnce({ status: 'signed_in' })
    land('/auth/complete#code=one-time-code')
    const { alert, answer, tryAgain } = await noticeShown()
    expect(alert).toHaveTextContent("We couldn't finish your login just now")
    expect(alert).toHaveTextContent('Try again in a minute, or log in again.')
    expect(alert).not.toHaveTextContent(/connection/i)
    expect(document.activeElement).toBe(answer)
    expect(screen.getByRole('link', { name: 'Log in again' })).toHaveAttribute('href', '/login')
    expect(replace).not.toHaveBeenCalled()
    fireEvent.click(tryAgain as HTMLElement)
    await waitFor(() => expect(replace).toHaveBeenCalledWith('/'))
    expect(completeOAuthSignIn.mock.calls).toEqual([['one-time-code'], ['one-time-code']])
  })
})
