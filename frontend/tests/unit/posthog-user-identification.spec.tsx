/**
 * The identification hook's own duties, on a stand-in facade: it identifies an account only once PostHog is ready and
 * analytics is allowed, asks to forget the account for every guest and when the current-user query leaves the cache,
 * and reports each settled read of the session, which PostHog's start waits on for a browser with a session
 * (lib/posthogIdentity.ts). Its cases write the guest's null or clear a bare QueryClient themselves. Whether each way a
 * session ends in the app writes that null or clears the cache is review-checked
 * (lessons/frontend-an-sdk-that-captures-nothing-can-still-store.md). What the facade and the provider then do with the
 * SDK is pinned on real clients in posthogConsentGuard.spec.tsx.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, cleanup, render, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const getCurrentUserSafe = vi.fn()
const getSubscriptionStatus = vi.fn()
const getCookiePreferences = vi.fn()
const identify = vi.fn()
const forgetAccount = vi.fn()
const reportAccountRead = vi.fn()

vi.mock('@/features/auth/api/auth-api', () => ({
  getCurrentUserSafe: () => getCurrentUserSafe(),
}))
vi.mock('@/features/subscriptions/api/subscriptions-api', () => ({
  getSubscriptionStatus: () => getSubscriptionStatus(),
}))
vi.mock('@/components/CookieConsent', () => ({
  getCookiePreferences: () => getCookiePreferences(),
}))
vi.mock('@/lib/analytics', () => ({
  analytics: {
    identify: (...args: unknown[]) => identify(...args),
    forgetAccount: (...args: unknown[]) => forgetAccount(...args),
  },
}))
vi.mock('@/lib/posthogIdentity', () => ({
  reportAccountRead: (...args: unknown[]) => reportAccountRead(...args),
}))

import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'
import { PostHogReadyContext } from '@/lib/posthogReady'
import { queryKeys } from '@/lib/queryKeys'

function Probe() {
  usePostHogUserIdentification()
  return null
}

function renderProbe() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <Probe />
    </QueryClientProvider>,
  )
  return qc
}

/** The probe under a PostHog readiness the test sets, as app/posthog-provider.tsx sets it on each consent change. */
function renderWithReadiness(ready: boolean) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const tree = (value: boolean) => (
    <QueryClientProvider client={qc}>
      <PostHogReadyContext.Provider value={value}>
        <Probe />
      </PostHogReadyContext.Provider>
    </QueryClientProvider>
  )
  const view = render(tree(ready))
  return { qc, setReady: (value: boolean) => view.rerender(tree(value)) }
}

describe('usePostHogUserIdentification (roadmap 2.4)', () => {
  beforeEach(() => {
    getCurrentUserSafe.mockReset()
    getSubscriptionStatus.mockReset()
    getCookiePreferences.mockReset()
    identify.mockReset()
    forgetAccount.mockReset()
    reportAccountRead.mockReset()
    getCookiePreferences.mockReturnValue({ analytics: true })
  })

  it('reports each settled read of the session: the account, no account, or a read that failed as none', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    renderProbe()
    await waitFor(() => expect(reportAccountRead).toHaveBeenLastCalledWith('7'))
    for (const read of [() => getCurrentUserSafe.mockResolvedValue(null), () => getCurrentUserSafe.mockRejectedValue(new Error('planted: /me failed'))]) {
      cleanup()
      reportAccountRead.mockReset()
      read()
      renderProbe()
      await waitFor(() => expect(reportAccountRead).toHaveBeenCalledWith(null))
      expect(reportAccountRead).not.toHaveBeenCalledWith('7')
    }
  })

  it('reports each later read on the same page: the account, then no account after a logout', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    const qc = renderProbe()
    await waitFor(() => expect(reportAccountRead).toHaveBeenLastCalledWith('7'))
    act(() => qc.setQueryData(queryKeys.currentUser(), null))
    await waitFor(() => expect(reportAccountRead).toHaveBeenLastCalledWith(null))
    expect(reportAccountRead.mock.calls).toEqual([['7'], [null]])
  })

  it('reports nothing while the read is pending', async () => {
    getCurrentUserSafe.mockReturnValue(new Promise(() => undefined))
    renderProbe()
    await act(async () => { await new Promise(resolve => setTimeout(resolve, 20)) })
    expect(reportAccountRead).not.toHaveBeenCalled()
  })

  it('reports no account when a refetch fails, though the cache keeps the account', async () => {
    getCurrentUserSafe.mockResolvedValueOnce({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    const qc = renderProbe()
    await waitFor(() => expect(reportAccountRead).toHaveBeenLastCalledWith('7'))
    getCurrentUserSafe.mockRejectedValueOnce(new Error('planted: /me failed'))
    await act(async () => { await qc.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await waitFor(() => expect(reportAccountRead).toHaveBeenLastCalledWith(null))
    expect(qc.getQueryData(queryKeys.currentUser())).toEqual({ id: 7, email: 'u@x.com', is_pro: false })
  })

  it('identifies the same account again after the cache is cleared', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    const { qc, setReady } = renderWithReadiness(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    act(() => qc.clear())
    // The same account signs in again, as after "Log out of all devices" on another browser and a login here.
    setReady(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(2))
    expect(identify).toHaveBeenLastCalledWith('7', { is_pro: false, plan: 'free' })
  })

  it('identifies a free user with is_pro/plan once user + subscription resolve', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    renderProbe()
    await waitFor(() =>
      expect(identify).toHaveBeenCalledWith('7', { is_pro: false, plan: 'free' }),
    )
    expect(forgetAccount).not.toHaveBeenCalled() // Neither while the account loads nor once it is known.
  })

  it('identifies a pro subscriber as pro (subscription is authoritative over the mirror)', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 9, email: 'p@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: true })
    renderProbe()
    await waitFor(() =>
      expect(identify).toHaveBeenCalledWith('9', { is_pro: true, plan: 'pro' }),
    )
  })

  it('does not identify without analytics consent', async () => {
    getCookiePreferences.mockReturnValue({ analytics: false })
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    renderProbe()
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).not.toHaveBeenCalled()
  })

  it('does not identify a logged-out visitor', async () => {
    getCurrentUserSafe.mockResolvedValue(null)
    renderProbe()
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).not.toHaveBeenCalled()
  })

  // An account deletion and "Log out of all devices" clear the whole cache instead of writing a guest, and React Query
  // tells no observer of the removed query.
  it('forgets the account when the cache is cleared', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    const { qc } = renderWithReadiness(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    expect(forgetAccount).not.toHaveBeenCalled()
    act(() => qc.clear())
    expect(forgetAccount).toHaveBeenCalledTimes(1)
    // The read reported before no longer holds, so PostHog's next start must not trust it.
    expect(reportAccountRead).toHaveBeenLastCalledWith(null)
  })

  it('identifies again after a cache clear, though another reader re-reads the account before the hook renders', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    const { qc, setReady } = renderWithReadiness(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    act(() => qc.clear())
    // The login page's header reads the same account again, as after "Log out of all devices" and a login.
    await act(async () => { await qc.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe }) })
    setReady(false)
    setReady(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(2))
  })

  // A guest carries no account: lib/analytics.ts resets an identity PostHog still holds, from an earlier visit or from a
  // logout by a control that does not reset it, and asks again once PostHog is ready.
  it('forgets any account for a guest, and again once PostHog is ready', async () => {
    getCurrentUserSafe.mockResolvedValue(null)
    const { setReady } = renderWithReadiness(false)
    await waitFor(() => expect(forgetAccount).toHaveBeenCalledTimes(1))
    setReady(true)
    await waitFor(() => expect(forgetAccount).toHaveBeenCalledTimes(2))
  })

  // The consent clause (lib/consentCopy.ts) says a logged-in reader's statistics are tied to their account id, so a
  // failed subscription read must not leave them anonymous (Codex r4331497824 on #1397).
  it('identifies by the id alone, with no plan, when the subscription read fails', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: true })
    getSubscriptionStatus.mockRejectedValue(new Error('500'))
    renderProbe()
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    expect(identify.mock.calls[0]).toEqual(['7'])
  })

  it('waits while the subscription read is in flight, so the first identify carries the plan', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockReturnValue(new Promise(() => {}))
    renderProbe()
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).not.toHaveBeenCalled()
  })

  it('adds the plan when a later subscription read succeeds, even one that matches the mirror', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: true })
    getSubscriptionStatus.mockRejectedValueOnce(new Error('500')).mockResolvedValue({ is_pro: true })
    const qc = renderProbe()
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    await qc.refetchQueries({ type: 'all' })
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(2))
    expect(identify).toHaveBeenLastCalledWith('7', { is_pro: true, plan: 'pro' })
  })

  // Any logout (the dashboard's, the menus', "Log out of all devices", a lost session) makes the reader a guest, whose
  // account lib/analytics.ts forgets, and lib/analytics.ts identifies nothing while analytics is refused. So after a
  // refusal, a logout and a login to the same account, the next allow must identify the account again.
  it('identifies the same account again after a logout and login, once PostHog is ready again', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockResolvedValue({ is_pro: false })
    const { qc, setReady } = renderWithReadiness(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    setReady(false) // A refusal.
    // React Query tells its observers on a timer, so each step waits for the hook to see it.
    const settle = (user: unknown) => act(async () => {
      qc.setQueryData(queryKeys.currentUser(), user)
      await new Promise((r) => setTimeout(r, 20))
    })
    await settle(null) // A logout (resetAccountQueries).
    expect(forgetAccount).toHaveBeenCalledTimes(1)
    await settle({ id: 7, email: 'u@x.com', is_pro: false }) // A login to the same account.
    expect(identify).toHaveBeenCalledTimes(1) // Not while analytics is refused.
    setReady(true) // The next allow.
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(2))
    expect(identify).toHaveBeenLastCalledWith('7', { is_pro: false, plan: 'free' })
  })

  // A failed refetch keeps the earlier read's data while the query reports the error (Codex r4331603917 on #1448).
  it('tags no cached plan when a refetch fails, even once PostHog becomes ready', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: true })
    getSubscriptionStatus.mockResolvedValueOnce({ is_pro: true }).mockRejectedValue(new Error('500'))
    const { qc, setReady } = renderWithReadiness(false)
    await waitFor(() => expect(qc.getQueryData(queryKeys.subscription.byUser(7))).toEqual({ is_pro: true }))
    await qc.refetchQueries({ type: 'all' })
    expect(qc.getQueryState(queryKeys.subscription.byUser(7))?.status).toBe('error')
    expect(qc.getQueryData(queryKeys.subscription.byUser(7))).toEqual({ is_pro: true })
    expect(identify).not.toHaveBeenCalled()
    setReady(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    expect(identify.mock.calls[0]).toEqual(['7'])
  })

  it('identifies a failed read once, however often PostHog readiness changes', async () => {
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockRejectedValue(new Error('500'))
    const { setReady } = renderWithReadiness(true)
    await waitFor(() => expect(identify).toHaveBeenCalledTimes(1))
    setReady(false)
    setReady(true)
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).toHaveBeenCalledTimes(1)
  })

  it('does not identify after a failed subscription read without analytics consent', async () => {
    getCookiePreferences.mockReturnValue({ analytics: false })
    getCurrentUserSafe.mockResolvedValue({ id: 7, email: 'u@x.com', is_pro: false })
    getSubscriptionStatus.mockRejectedValue(new Error('500'))
    renderProbe()
    await new Promise((r) => setTimeout(r, 50))
    expect(identify).not.toHaveBeenCalled()
  })
})
