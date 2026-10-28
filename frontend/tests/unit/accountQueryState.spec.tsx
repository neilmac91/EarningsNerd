import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, MutationObserver, useQuery } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import type { ReactNode } from 'react'
import { toast } from 'sonner'
import api from '@/lib/api/client'
import { getCurrentUser, getCurrentUserSafe, login, logout, type CurrentUser } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus, getUsage } from '@/features/subscriptions/api/subscriptions-api'
import { ACCOUNT_QUERY_FAMILIES, LOGOUT_FAILED_MESSAGE, logoutAndResetAccount, resetAccountQueries, subscribeAccountIdentityChange, subscribeAccountQueryReset, acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getSessionGeneration, getExplicitSessionGeneration, assertExplicitSessionGeneration, hasActiveSession, markSessionActive, notifySessionLost } from '@/lib/api/session'
import { queryKeys } from '@/lib/queryKeys'
import { refreshAccessToken } from '@/lib/api/refresh'
import ProfileForm from '@/features/settings/components/ProfileForm'
import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'
import NotificationBell from '@/features/notifications/components/NotificationBell'
import * as notificationsApi from '@/features/notifications/api/notifications-api'

const { identify } = vi.hoisted(() => ({ identify: vi.fn() }))
vi.mock('@/lib/analytics', () => ({ analytics: { identify } }))
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))
vi.mock('@/components/CookieConsent', () => ({ getCookiePreferences: () => ({ analytics: true }) }))

const makeUser = (id: number): CurrentUser => ({
  id, email: `${id}@example.test`, full_name: null, is_pro: false,
  is_beta: false, is_admin: false, email_verified: true,
})
const response = (config: InternalAxiosRequestConfig, data: unknown) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const deferred = <T,>() => {
  let resolve!: (value: T) => void
  let reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
const clients: QueryClient[] = []
const disposers: (() => void)[] = []
const originalAdapter = api.defaults.adapter
const newClient = () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } } })
  clients.push(client)
  return client
}
function Viewer() {
  usePostHogUserIdentification()
  const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })
  const { data: sub } = useQuery({ queryKey: queryKeys.subscription.byUser(user?.id), queryFn: getSubscriptionStatus, enabled: !!user })
  const { data: usage } = useQuery({ queryKey: queryKeys.usage.byUser(user?.id), queryFn: getUsage, enabled: !!user })
  return <output>{JSON.stringify({ id: user?.id ?? null, pro: sub?.is_pro ?? null, used: usage?.summaries_used ?? null })}</output>
}
const rendered = () => JSON.parse(screen.getByRole('status').textContent!)

beforeEach(() => { advanceSessionGeneration(); clearSessionActive(); identify.mockReset(); vi.mocked(refreshAccessToken).mockReset() })
afterEach(() => {
  cleanup()
  disposers.splice(0).forEach((dispose) => dispose())
  clients.splice(0).forEach((client) => client.clear())
  api.defaults.adapter = originalAdapter
  vi.restoreAllMocks()
})

describe('account snapshots follow the resolved identity', () => {
  it('a late mark-seen receipt cannot replace the next account’s notification list', async () => {
    const client = newClient()
    const first = { items: [], unread_count: 1 }
    const second = { items: [], unread_count: 2 }
    const receipt = deferred<notificationsApi.NotificationList>()
    vi.spyOn(notificationsApi, 'getNotifications').mockResolvedValue(first)
    vi.spyOn(notificationsApi, 'markNotificationsSeen').mockReturnValue(receipt.promise)
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.notifications(), first)
    const view = render(<QueryClientProvider client={client}><NotificationBell /></QueryClientProvider>)
    fireEvent.click(screen.getByRole('button', { name: 'Notifications (1 unread)' }))
    await waitFor(() => expect(notificationsApi.markNotificationsSeen).toHaveBeenCalledTimes(1))
    view.unmount()
    resetAccountQueries(client)
    client.setQueryData(queryKeys.currentUser(), makeUser(2))
    client.setQueryData(queryKeys.notifications(), second)
    await act(async () => receipt.resolve({ items: [], unread_count: 0 }))
    expect(client.getQueryData(queryKeys.notifications())).toEqual(second)
  })

  it.each(['guest-first', 'login-first'])('guest /me cannot invalidate a successful password login (%s)', async (order) => {
    const client = newClient()
    disposers.push(subscribeAccountQueryReset(client))
    const guest = deferred<unknown>()
    const credential = deferred<unknown>()
    let meCalls = 0
    let loginCalls = 0
    api.defaults.adapter = async (config) => {
      if (config.url === '/api/auth/login') {
        loginCalls += 1
        return response(config, await credential.promise)
      }
      meCalls += 1
      if (meCalls === 1) {
        await guest.promise
        throw Object.assign(new Error('guest'), { config, response: { status: 401, data: { detail: 'Not authenticated' } } })
      }
      return response(config, makeUser(2))
    }
    const priorGeneration = getSessionGeneration()
    const explicitGeneration = getExplicitSessionGeneration()
    const oldIdentity = client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })
    const signedIn = login('2@example.test', 'test-only-password')
    await waitFor(() => { expect(meCalls).toBe(1); expect(loginCalls).toBe(1) })
    if (order === 'guest-first') {
      guest.resolve(undefined)
      expect(await oldIdentity).toBeNull()
      credential.resolve({ ok: true })
      await expect(signedIn).resolves.toEqual({ ok: true })
    } else {
      credential.resolve({ ok: true })
      await expect(signedIn).resolves.toEqual({ ok: true })
      // Resolve the old guest before the login caller's reset to expose marker side effects too.
      guest.resolve(undefined)
      expect(await oldIdentity).toBeNull()
    }
    expect(getSessionGeneration()).toBe(priorGeneration)
    expect(hasActiveSession()).toBe(true)
    acceptLoginAndResetAccount(client, explicitGeneration)
    expect(hasActiveSession()).toBe(true)
    await client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(2))
    expect(hasActiveSession()).toBe(true)
  })

  it.each(['passive-loss', 'passive-loss-then-logout'])('pending login handles %s without losing explicit ownership', async (order) => {
    const client = newClient()
    disposers.push(subscribeAccountQueryReset(client))
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    markSessionActive()
    const credential = deferred<unknown>()
    const logoutDone = deferred<unknown>()
    const refreshAnswer = deferred<void>()
    let logoutRequests = 0
    vi.mocked(refreshAccessToken).mockImplementation(() => refreshAnswer.promise)
    api.defaults.adapter = async (config) => {
      if (config.url === '/api/auth/login') return response(config, await credential.promise)
      if (config.url === '/api/auth/logout') {
        logoutRequests += 1
        return response(config, await logoutDone.promise)
      }
      throw Object.assign(new Error('expired A'), { config, response: { status: 401, data: { detail: 'Expired access' } } })
    }
    const explicitGeneration = getExplicitSessionGeneration()
    const signedIn = login('2@example.test', 'test-only-password').catch((error) => error)
    const oldIdentity = client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 }).catch((error) => error)
    await waitFor(() => expect(refreshAccessToken).toHaveBeenCalledTimes(1))
    // The logout starts while that refresh is in flight and waits for its answer (E133); the refresh's 401 then
    // lands as a passive loss while the logout is under way, and the logout must still send its request.
    const pendingLogout = order === 'passive-loss-then-logout' ? logoutAndResetAccount(client, logout) : null
    refreshAnswer.reject({ response: { status: 401 } })
    await oldIdentity
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(getExplicitSessionGeneration()).toBe(explicitGeneration)
    if (pendingLogout) {
      logoutDone.resolve({ ok: true })
      await pendingLogout
      expect(logoutRequests).toBe(1)
      expect(getExplicitSessionGeneration()).not.toBe(explicitGeneration)
    }
    credential.resolve({ ok: true })
    if (pendingLogout) {
      expect(await signedIn).toMatchObject({ name: 'AbortError' })
      expect(hasActiveSession()).toBe(false)
      expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    } else {
      expect(await signedIn).toEqual({ ok: true })
      acceptLoginAndResetAccount(client, explicitGeneration)
      api.defaults.adapter = async (config) => response(config, makeUser(2))
      await client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })
      expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(2))
      expect(hasActiveSession()).toBe(true)
    }
  })

  it('rejects credential publication if explicit logout completes in the API-to-page continuation gap', async () => {
    const client = newClient()
    const explicitGeneration = getExplicitSessionGeneration()
    api.defaults.adapter = async (config) => response(config, { ok: true })
    await login('2@example.test', 'test-only-password')
    await logoutAndResetAccount(client, logout)
    expect(() => acceptLoginAndResetAccount(client, explicitGeneration)).toThrow(/transition/)
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(hasActiveSession()).toBe(false)
  })

  it.each(['pending', 'resolved'])('rejects stale login continuation after %s identity and later logout', async (state) => {
    const client = newClient()
    const accepted = acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
    const identity = deferred<unknown>()
    api.defaults.adapter = async (config) => response(config, await identity.promise)
    const pending = client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe }).catch((error) => error)
    if (state === 'resolved') {
      identity.resolve(makeUser(2))
      await pending
    }
    resetAccountQueries(client) // A later completed logout/explicit transition wins.
    identity.resolve(makeUser(2))
    await pending
    expect(() => assertExplicitSessionGeneration(accepted)).toThrow(/transition/)
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
  })

  it.each([true, false])('logout UI callbacks skip stale unmounted mutations and preserve current success=%s', async (succeeded) => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    const logoutDone = deferred<unknown>()
    const sendLogout = vi.fn(() => logoutDone.promise)
    const navigate = vi.fn()
    const clearAnalytics = vi.fn()
    const continued = vi.fn((success: boolean) => { navigate(); if (success) clearAnalytics() })
    const observer = new MutationObserver(client, {
      mutationFn: () => logoutAndResetAccount(client, sendLogout, continued),
    })
    const unsubscribe = observer.subscribe(() => {})
    const oldMutation = observer.mutate().catch((error) => error)
    await waitFor(() => expect(sendLogout).toHaveBeenCalledTimes(1))
    unsubscribe() // Real option-level mutation callbacks otherwise still run after unmount.
    resetAccountQueries(client)
    client.setQueryData(queryKeys.currentUser(), makeUser(2))
    logoutDone.resolve({ ok: true })
    await oldMutation
    expect(continued).not.toHaveBeenCalled()
    expect(navigate).not.toHaveBeenCalled()
    expect(clearAnalytics).not.toHaveBeenCalled()
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(2))

    const requestError = new Error('current logout failed')
    // A failed logout reads /me before it settles (logoutAndResetAccount); offline, that read cannot tell either.
    api.defaults.adapter = async () => { throw new Error('offline') }
    const current = new MutationObserver(client, {
      mutationFn: () => logoutAndResetAccount(client, async () => {
        if (!succeeded) throw requestError
      }, continued),
    })
    const result = await current.mutate().catch((error) => error)
    if (!succeeded) expect(result).toBe(requestError)
    expect(continued).toHaveBeenCalledWith(succeeded)
    expect(navigate).toHaveBeenCalledTimes(1)
    expect(clearAnalytics).toHaveBeenCalledTimes(succeeded ? 1 : 0)
    // A logout that did not take, and whose /me read could not tell, puts back the identity it reset.
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(succeeded ? null : makeUser(2))
  })

  it('a late unmounted profile mutation cannot publish A while the canonical B refetch waits', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.subscription.byUser(1), { is_pro: true })
    client.setQueryData(queryKeys.usage.byUser(1), { summaries_used: 91 })
    const patch = deferred<unknown>()
    const me = deferred<unknown>()
    let patchStarted = false
    let meReads = 0
    api.defaults.adapter = async (config) => {
      if (config.method === 'patch') {
        patchStarted = true
        return response(config, await patch.promise)
      }
      if (config.url === '/api/auth/me') {
        meReads += 1
        return response(config, await me.promise)
      }
      return response(config, config.url?.endsWith('/usage') ? { summaries_used: 2 } : { is_pro: false })
    }
    const tree = (showProfile: boolean) => <QueryClientProvider client={client}>
      {showProfile ? <ProfileForm /> : null}<Viewer />
    </QueryClientProvider>
    const view = render(tree(true))
    fireEvent.change(screen.getByLabelText('Display name'), { target: { value: 'Edited A' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(patchStarted).toBe(true))
    act(() => {
      view.rerender(tree(false))
      resetAccountQueries(client)
      client.setQueryData(queryKeys.currentUser(), makeUser(2))
      client.setQueryData(queryKeys.subscription.byUser(2), { is_pro: false })
      client.setQueryData(queryKeys.usage.byUser(2), { summaries_used: 2 })
    })
    await waitFor(() => expect(rendered()).toEqual({ id: 2, pro: false, used: 2 }))
    await act(async () => {
      patch.resolve({ ...makeUser(1), full_name: 'Edited A' })
      await waitFor(() => expect(meReads).toBe(1))
    })
    expect(rendered()).toEqual({ id: 2, pro: false, used: 2 })
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(2))
    await act(async () => { me.resolve(makeUser(2)) })
    expect(rendered()).toEqual({ id: 2, pro: false, used: 2 })
  })

  it.each([true, false])('isolates A Pro=%s from pending/failed B reads and late A responses', async (aPro) => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.subscription.byUser(1), { is_pro: aPro })
    client.setQueryData(queryKeys.usage.byUser(1), { summaries_used: 91 })
    // Retained entries for another identity must not alias the currently displayed account.
    client.setQueryData(queryKeys.subscription.byUser(2), { is_pro: !aPro })
    client.setQueryData(queryKeys.usage.byUser(2), { summaries_used: 2 })
    render(<QueryClientProvider client={client}><Viewer /></QueryClientProvider>)
    expect(rendered()).toEqual({ id: 1, pro: aPro, used: 91 })

    const a = [deferred<unknown>(), deferred<unknown>(), deferred<unknown>()]
    let aCalls = 0
    api.defaults.adapter = async (config) => response(config, await a[aCalls++].promise)
    const oldRequests = [
      client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 }),
      client.fetchQuery({ queryKey: queryKeys.subscription.byUser(1), queryFn: getSubscriptionStatus, staleTime: 0 }),
      client.fetchQuery({ queryKey: queryKeys.usage.byUser(1), queryFn: getUsage, staleTime: 0 }),
    ].map((request) => request.catch(() => undefined))
    await waitFor(() => expect(aCalls).toBe(3))

    const bSub = deferred<unknown>()
    const bUsage = deferred<unknown>()
    api.defaults.adapter = async (config) => response(config, config.url === '/api/auth/me' ? makeUser(2)
      : await (config.url?.endsWith('/usage') ? bUsage.promise : bSub.promise))
    markSessionActive() // A successful password login has already set this before reset.
    await act(async () => {
      resetAccountQueries(client)
      expect(hasActiveSession()).toBe(true)
      await client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })
    })
    await waitFor(() => expect(rendered()).toEqual({ id: 2, pro: null, used: null }))
    await act(async () => {
      a[0].resolve(makeUser(1)); a[1].resolve({ is_pro: aPro }); a[2].resolve({ summaries_used: 91 })
      await Promise.all(oldRequests)
    })
    expect(rendered()).toEqual({ id: 2, pro: null, used: null })
    expect(identify.mock.calls).toEqual([['1', { is_pro: aPro, plan: aPro ? 'pro' : 'free' }]])
    expect(client.getQueryData(queryKeys.subscription.byUser(1))).toBeUndefined()
    expect(client.getQueryData(queryKeys.usage.byUser(1))).toBeUndefined()

    await act(async () => { bSub.reject(new Error('temporary billing failure')); bUsage.resolve({ summaries_used: 2 }) })
    await waitFor(() => expect(rendered()).toEqual({ id: 2, pro: null, used: 2 }))
    let requests = 0
    api.defaults.adapter = async (config) => {
      requests += 1
      return response(config, config.url?.endsWith('/usage') ? { summaries_used: 3 } : { is_pro: !aPro })
    }
    await act(async () => {
      await client.invalidateQueries({ queryKey: queryKeys.subscription.all() })
      await client.invalidateQueries({ queryKey: queryKeys.usage.all() })
    })
    await waitFor(() => expect(rendered()).toEqual({ id: 2, pro: !aPro, used: 3 }))
    expect(requests).toBe(2)
    expect(identify).toHaveBeenLastCalledWith('2', { is_pro: !aPro, plan: !aPro ? 'pro' : 'free' })
    act(() => resetAccountQueries(client))
    await waitFor(() => expect(rendered()).toEqual({ id: null, pro: null, used: null }))
  })

  it('fences uncancelled identity side effects, stale loss notifications and late logout cleanup', async () => {
    const client = newClient()
    disposers.push(subscribeAccountQueryReset(client))
    const firstGeneration = getSessionGeneration()
    const late = deferred<unknown>()
    api.defaults.adapter = async (config) => response(config, await late.promise)
    const oldIdentity = getCurrentUser().catch((error) => error)
    const oldLogout = logoutAndResetAccount(client, () => late.promise)
    resetAccountQueries(client)
    client.setQueryData(queryKeys.currentUser(), makeUser(2))
    client.setQueryData(queryKeys.subscription.byUser(2), { is_pro: false })
    // If A's late /me calls markSessionActive it will incorrectly restore this marker.
    clearSessionActive()
    late.resolve(makeUser(1))
    expect(await oldIdentity).toMatchObject({ name: 'AbortError' })
    await oldLogout
    expect(hasActiveSession()).toBe(false)
    notifySessionLost(firstGeneration)
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(2))
    expect(client.getQueryData(queryKeys.subscription.byUser(2))).toEqual({ is_pro: false })
    notifySessionLost(getSessionGeneration())
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(client.getQueryData(queryKeys.subscription.byUser(2))).toBeUndefined()
  })

  it('resets the account families, the wording reviews included, even when the ordinary logout request fails', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.subscription.byUser(1), { is_pro: true })
    client.setQueryData(queryKeys.usage.byUser(1), { summaries_used: 9 })
    client.setQueryData(queryKeys.wordingReview.byFiling(42), { status: 'ok', labels: { a1: 'reviewed' } })
    markSessionActive()
    api.defaults.adapter = async () => { throw new Error('offline logout') }
    await expect(logoutAndResetAccount(client, logout)).rejects.toThrow('offline logout')
    // Its /me read failed too, so nothing says the session ended: the flag and the identity stay as the logout found them.
    expect(hasActiveSession()).toBe(true)
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(1))
    expect(client.getQueryCache().findAll({ queryKey: queryKeys.subscription.all() })).toHaveLength(0)
    expect(client.getQueryCache().findAll({ queryKey: queryKeys.usage.all() })).toHaveLength(0)
    // The previous account's labels and receipts never show to the next account in this tab.
    expect(client.getQueryCache().findAll({ queryKey: queryKeys.wordingReview.all() })).toHaveLength(0)
  })

  it('an account change removes every account-owned snapshot and keeps the shared ones', async () => {
    const client = newClient()
    // One entry in each account-owned family; most keys name no reader, so the next account would read them.
    const owned = [
      queryKeys.subscription.byUser(1), queryKeys.usage.byUser(1), queryKeys.wordingReview.byFiling(42),
      queryKeys.whatChanged.byViewer(7, 1),
      queryKeys.whatChanged.byViewer(7, null), // the anonymous entry, which a reader whose /me failed reads with their session
      queryKeys.savedSummaries(), queryKeys.savedSummaryStatus(5, 1), queryKeys.watchlist(), queryKeys.watchlistInsights(),
      queryKeys.earningsAlertTickers(), queryKeys.dashboardFeed(), queryKeys.dashboardCalendar(), queryKeys.notifications(),
      queryKeys.notificationPreferences(), queryKeys.authConnections(), queryKeys.adminInvites(),
      queryKeys.adminFeedback.list({ status: 'new' }),
    ]
    const shared = [
      queryKeys.company('AAPL'), queryKeys.summary(7), queryKeys.filing(7), queryKeys.registrationConfig(),
    ]
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    for (const key of [...owned, ...shared]) client.setQueryData(key, { owner: 1 })
    markSessionActive()
    api.defaults.adapter = async (config) => response(config, {})
    await logoutAndResetAccount(client, logout)
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(owned.filter((key) => client.getQueryData(key) !== undefined)).toEqual([])
    expect(shared.filter((key) => client.getQueryData(key) === undefined)).toEqual([])
  })

  it('a logout in this tab leaves a mounted read whose placeholder is its previous data with none of the reader’s', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.whatChanged.byViewer(7, 1), { owner: 1 })
    const renders: string[] = []
    // As useWhatChanged reads its report where no server seed stands in: keyed by the reader, the anonymous key once
    // the reader is gone, with the previous key's data as the placeholder.
    function Report() {
      const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })
      const { data: report } = useQuery({
        queryKey: queryKeys.whatChanged.byViewer(7, user?.id ?? null),
        queryFn: () => new Promise<{ owner: number }>(() => {}),
        placeholderData: (previous) => previous,
      })
      const shown = `${user === null ? 'guest' : user?.id}:${JSON.stringify(report ?? null)}`
      renders.push(shown)
      return <output>{shown}</output>
    }
    render(<QueryClientProvider client={client}><Report /></QueryClientProvider>)
    expect(screen.getByRole('status')).toHaveTextContent('1:{"owner":1}')

    const before = renders.length
    act(() => resetAccountQueries(client))
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/^guest:/))
    expect(screen.getByRole('status')).toHaveTextContent('guest:null')
    expect(renders.slice(before).filter((shown) => shown.includes('"owner":1'))).toEqual([])
  })

  // The admin pages' shape: a layout that reads the reader renders the page as `children`, an element its own re-render
  // does not re-render, so only the reset itself reaches the page's read.
  it('after a failed logout, a family read handed in as children shows its loading state, then the restored reader’s own data', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.adminInvites(), [{ owner: 1, read: 'before' }])
    markSessionActive()
    api.defaults.adapter = async (config) => {
      if (config.url !== '/api/auth/me') throw new Error('offline logout')
      return response(config, makeUser(1))
    }
    const renders: string[] = []
    function Layout({ children }: { children: ReactNode }) {
      const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })
      return user ? <>{children}</> : null
    }
    function Invites() {
      const { data, status } = useQuery({ queryKey: queryKeys.adminInvites(), queryFn: async () => [{ owner: 1, read: 'after' }] })
      const shown = `${status}:${JSON.stringify(data ?? null)}`
      renders.push(shown)
      return <output>{shown}</output>
    }
    render(<QueryClientProvider client={client}><Layout><Invites /></Layout></QueryClientProvider>)
    expect(screen.getByRole('status')).toHaveTextContent('success:[{"owner":1,"read":"before"}]')

    const before = renders.length
    await act(async () => { await logoutAndResetAccount(client, logout).catch(() => undefined) })
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('success:[{"owner":1,"read":"after"}]'))
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(1))
    const after = renders.slice(before)
    expect(after[0]).toBe('pending:null')
    expect(after.filter((shown) => shown !== 'pending:null' && !shown.includes('"owner":1'))).toEqual([])
  })
})

// A login in another tab reaches this one only through /me (the Header re-reads it on focus): no reset runs here.
describe('a /me that names another reader drops the previous reader’s families (subscribeAccountIdentityChange)', () => {
  /** Reader 1 shown, a snapshot under every account family, and one shared entry. */
  const seedReaderOne = (client: QueryClient) => {
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    for (const queryKey of ACCOUNT_QUERY_FAMILIES) client.setQueryData(queryKey, { owner: 1 })
    client.setQueryData(queryKeys.company('AAPL'), { owner: 1 })
  }
  /** Every entry under an account family that holds data. */
  const familyData = (client: QueryClient) => ACCOUNT_QUERY_FAMILIES
    .flatMap((queryKey) => client.getQueryCache().findAll({ queryKey }))
    .filter((query) => query.state.data !== undefined)
    .map((query) => query.queryHash)
  const answerMe = (reader: CurrentUser | null) => {
    api.defaults.adapter = async (config) => {
      if (reader) return response(config, reader)
      throw Object.assign(new Error('guest'), { config, response: { status: 401, data: { detail: 'Not authenticated' } } })
    }
  }
  const readMe = (client: QueryClient) => client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 })

  it('a /me naming another reader removes every account family before the new reader renders, and moves the generation passively', async () => {
    const client = newClient()
    seedReaderOne(client)
    disposers.push(subscribeAccountIdentityChange(client))
    const generation = getSessionGeneration()
    const explicit = getExplicitSessionGeneration()
    const renders: string[] = []
    function Probe() {
      const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })
      const { data: list } = useQuery({ queryKey: queryKeys.watchlist(), queryFn: () => new Promise<never>(() => {}), enabled: !!user })
      renders.push(`${user?.id}:${JSON.stringify(list ?? null)}`)
      return null
    }
    render(<QueryClientProvider client={client}><Probe /></QueryClientProvider>)
    expect(renders[renders.length - 1]).toBe('1:{"owner":1}')

    answerMe(makeUser(2))
    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await waitFor(() => expect(renders.some((shown) => shown.startsWith('2:'))).toBe(true))
    expect(renders.filter((shown) => shown.startsWith('2:') && shown !== '2:null')).toEqual([])
    expect(client.getQueryData(queryKeys.currentUser())).toEqual(makeUser(2))
    // The Probe's reader-2 render builds the watchlist entry again, to read it for reader 2: it holds nothing.
    expect(familyData(client)).toEqual([])
    expect(client.getQueryData(queryKeys.company('AAPL'))).toEqual({ owner: 1 })
    expect(getSessionGeneration()).toBe(generation + 1)
    // Passively: a login this tab has under way keeps its explicit ownership.
    expect(getExplicitSessionGeneration()).toBe(explicit)
  })

  it('a mounted read whose placeholder is its previous data shows none of the previous reader’s under the new one', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.whatChanged.byViewer(7, 1), { owner: 1 })
    disposers.push(subscribeAccountIdentityChange(client))
    const renders: string[] = []
    // As useWhatChanged reads its report: keyed by the reader, with the previous key's data as the placeholder.
    function Report() {
      const { data: user } = useQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe })
      const { data: report } = useQuery({
        queryKey: queryKeys.whatChanged.byViewer(7, user?.id ?? null),
        queryFn: () => new Promise<{ owner: number }>(() => {}),
        placeholderData: (previous) => previous,
        enabled: !!user,
      })
      const shown = `${user?.id}:${JSON.stringify(report ?? null)}`
      renders.push(shown)
      return <output>{shown}</output>
    }
    render(<QueryClientProvider client={client}><Report /></QueryClientProvider>)
    expect(screen.getByRole('status')).toHaveTextContent('1:{"owner":1}')

    answerMe(makeUser(2))
    await act(async () => { await client.refetchQueries({ queryKey: queryKeys.currentUser() }) })
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent(/^2:/))
    expect(screen.getByRole('status')).toHaveTextContent('2:null')
    expect(renders.filter((shown) => shown.startsWith('2:') && shown !== '2:null')).toEqual([])
  })

  it('a /me for the same reader, its other fields changed, keeps every family and the generation', async () => {
    const client = newClient()
    seedReaderOne(client)
    disposers.push(subscribeAccountIdentityChange(client))
    const generation = getSessionGeneration()
    answerMe({ ...makeUser(1), full_name: 'Renamed', email: 'renamed@example.test', is_pro: true })
    await readMe(client)
    expect(familyData(client)).toHaveLength(ACCOUNT_QUERY_FAMILIES.length)
    expect(getSessionGeneration()).toBe(generation)
  })

  it.each([
    ['answers no reader (another tab logged out)', async (client: QueryClient) => {
      answerMe(null)
      expect(await readMe(client)).toBeNull()
    }],
    ['entry is removed (clear(), garbage collection)', async (client: QueryClient) => {
      client.removeQueries({ queryKey: queryKeys.currentUser() })
    }],
  ])('reader 1 shown, then the /me %s, then a /me naming reader 2: every family is dropped', async (_between, between) => {
    const client = newClient()
    seedReaderOne(client)
    disposers.push(subscribeAccountIdentityChange(client))
    const generation = getSessionGeneration()
    await between(client)
    // Nothing has named another reader yet.
    expect(familyData(client)).toHaveLength(ACCOUNT_QUERY_FAMILIES.length)
    expect(getSessionGeneration()).toBe(generation)
    answerMe(makeUser(2))
    await readMe(client)
    expect(familyData(client)).toEqual([])
    expect(getSessionGeneration()).toBe(generation + 1)
  })

  it('a /me that answers no reader, then the same reader again, keeps every family', async () => {
    const client = newClient()
    seedReaderOne(client)
    disposers.push(subscribeAccountIdentityChange(client))
    const generation = getSessionGeneration()
    answerMe(null)
    await readMe(client)
    answerMe(makeUser(1))
    await readMe(client)
    expect(familyData(client)).toHaveLength(ACCOUNT_QUERY_FAMILIES.length)
    expect(getSessionGeneration()).toBe(generation)
  })

  it.each([
    ['the reader it restored', 1, 1, [{ owner: 1 }], true],
    ['another reader (another tab’s login)', 2, 2, undefined, false],
  ] as const)('a failed logout whose /me names %s compares it with that restored reader, and reports to that reader alone', async (_who, readerId, advances, kept, reported) => {
    const failed = vi.spyOn(toast, 'error')
    const continued = vi.fn()
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    disposers.push(subscribeAccountIdentityChange(client))
    markSessionActive()
    const me = deferred<unknown>()
    let meRead = false
    api.defaults.adapter = async (config) => {
      if (config.url !== '/api/auth/me') throw new Error('offline logout')
      meRead = true
      return response(config, await me.promise)
    }
    const generation = getSessionGeneration()
    const settled = logoutAndResetAccount(client, logout, continued).catch((error: Error) => error.message)
    await waitFor(() => expect(meRead).toBe(true))
    // While /me is read, a family refetches under the reader the logout restored.
    client.setQueryData(queryKeys.watchlist(), [{ owner: 1 }])
    me.resolve(makeUser(readerId))
    expect(await settled).toBe('offline logout')
    expect(client.getQueryData(queryKeys.watchlist())).toEqual(kept)
    // The reset's own advance, and the listener's when /me names another reader.
    expect(getSessionGeneration()).toBe(generation + advances)
    // Another reader owns the tab now: the logout is superseded, and that reader hears nothing of it.
    expect(failed.mock.calls).toEqual(reported ? [[LOGOUT_FAILED_MESSAGE]] : [])
    expect(continued.mock.calls).toEqual(reported ? [[false]] : [])
  })

  it('the identity a transition in this tab publishes is not read as another change', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    disposers.push(subscribeAccountIdentityChange(client))
    const generation = getSessionGeneration()
    // The reset's null is this tab's own write: it clears the reader the listener compares with.
    acceptLoginAndResetAccount(client, getExplicitSessionGeneration())
    client.setQueryData(queryKeys.watchlist(), [{ owner: 2 }])
    answerMe(makeUser(2))
    await readMe(client)
    expect(getSessionGeneration()).toBe(generation + 1)
    expect(client.getQueryData(queryKeys.watchlist())).toEqual([{ owner: 2 }])
  })
})

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(file) : /\.tsx?$/.test(file) ? [file] : []
  })
}

/** setQueryData or setQueriesData, called by name on any receiver: the writes the fence gate reads. */
function isCacheWrite(node: ts.Node): node is ts.CallExpression & { expression: ts.PropertyAccessExpression } {
  return ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
    && ['setQueryData', 'setQueriesData'].includes(node.expression.name.text)
}

const GENERATION_FENCES = ['isSessionGenerationCurrent', 'assertSessionGeneration']
const waits = (inner: ts.Node) => ts.isAwaitExpression(inner) || (ts.isForOfStatement(inner) && inner.awaitModifier !== undefined)
/** An await in `inner` outside any function nested in it. */
const holdsWait = (inner: ts.Node): boolean =>
  !ts.isFunctionLike(inner) && (waits(inner) || ts.forEachChild(inner, holdsWait) === true)

/** The const a name reads, from the innermost scope around it that declares it (a block, a function's body, the file);
 *  undefined for a parameter, which cannot be traced to a capture, for a let or var, or for a name no scope here
 *  declares. */
function bindingOf(name: ts.Identifier): ts.VariableDeclaration | undefined {
  for (let scope: ts.Node | undefined = name.parent; scope; scope = scope.parent) {
    if (ts.isFunctionLike(scope) && scope.parameters.some((parameter) => ts.isIdentifier(parameter.name) && parameter.name.text === name.text)) return undefined
    const statements = ts.isBlock(scope) || ts.isSourceFile(scope) ? scope.statements : []
    for (const statement of statements) {
      if (!ts.isVariableStatement(statement)) continue
      const declaration = statement.declarationList.declarations.find((candidate) => ts.isIdentifier(candidate.name) && candidate.name.text === name.text)
      // Only a const holds what it was set to: a let can be set again after the wait.
      if (declaration) return statement.declarationList.flags & ts.NodeFlags.Const ? declaration : undefined
    }
  }
  return undefined
}

/** The name a function goes by: its own, or the variable or property that holds it; undefined for an anonymous one. */
function nameOf(fn: ts.Node): string | undefined {
  if ((ts.isFunctionDeclaration(fn) || ts.isFunctionExpression(fn) || ts.isMethodDeclaration(fn)) && fn.name && ts.isIdentifier(fn.name)) return fn.name.text
  const holder = fn.parent
  return holder && (ts.isVariableDeclaration(holder) || ts.isPropertyAssignment(holder)) && ts.isIdentifier(holder.name) ? holder.name.text : undefined
}

/** The lib/queryKeys.ts family a write names: in its key, or in the `queryKey` of the filters setQueriesData takes. */
function writtenFamily(node: ts.CallExpression, source: ts.SourceFile): string | undefined {
  const first = node.arguments[0]
  const key = first && ts.isObjectLiteralExpression(first)
    ? first.properties.find((property): property is ts.PropertyAssignment => ts.isPropertyAssignment(property) && property.name.getText(source) === 'queryKey')?.initializer
    : first
  return /^queryKeys\.(\w+)/.exec(key?.getText(source) ?? '')?.[1]
}

/** Whether one write into an account-owned family is fenced, as the gate below reads it (its comment says how, and what
 *  it cannot see). Scored on FENCE_FORMS. */
export function fencedWrite(node: ts.CallExpression & { expression: ts.PropertyAccessExpression }, source: ts.SourceFile): boolean {
  // The function that makes the write; a function nested in it (the updater) runs inside the write.
  let owner: ts.Node | undefined = node.parent
  while (owner && !ts.isFunctionLike(owner)) owner = owner.parent
  const writer = owner
  const write = node.getStart(source)
  let wait = -1
  let firstWait = Infinity
  const waitAt = (at: number) => {
    wait = Math.max(wait, at)
    firstWait = Math.min(firstWait, at)
  }
  const fences: ts.CallExpression[] = []
  const scan = (inner: ts.Node): void => {
    if (inner.getStart(source) >= write || (inner !== writer && ts.isFunctionLike(inner))) return
    if (waits(inner)) waitAt(inner.getStart(source))
    // A loop around the write that waits anywhere in it waits again before its next turn writes: at its body's start.
    if (ts.isIterationStatement(inner, false) && inner.statement.getStart(source) <= write && write < inner.statement.getEnd() && holdsWait(inner)) {
      waitAt(inner.statement.getStart(source))
    }
    if (ts.isCallExpression(inner) && ts.isIdentifier(inner.expression) && GENERATION_FENCES.includes(inner.expression.text)) fences.push(inner)
    ts.forEachChild(inner, scan)
  }
  if (!writer) return false
  scan(writer)
  // The generation a fence compares is one captured before the function first waits: the `generation` of one of the
  // writing function's own parameters (the mutation's context), or a getSessionGeneration() const ahead of its first wait,
  // or outside it in a function that is not a component's or a hook's body. One read in the same run as its check cannot
  // have moved. A component or a hook reads it again at each render, and a pending mutation takes the options of the
  // latest render (TanStack's MutationObserver.setOptions), so it compares that render's generation, not the press's.
  const captured = (generation: ts.Expression | undefined): boolean => {
    if (generation && ts.isPropertyAccessExpression(generation)) {
      const of = generation.expression
      return generation.name.text === 'generation' && ts.isIdentifier(of) && ts.isFunctionLike(writer)
        && writer.parameters.some((parameter) => ts.isIdentifier(parameter.name) && parameter.name.text === of.text)
    }
    const binding = generation && ts.isIdentifier(generation) ? bindingOf(generation) : undefined
    if (binding?.initializer?.getText(source) !== 'getSessionGeneration()') return false
    const inside = binding.getStart(source) > writer.getStart(source) && binding.getEnd() <= writer.getEnd()
    if (inside) return firstWait !== Infinity && binding.getEnd() <= firstWait
    let holder: ts.Node | undefined = binding.parent
    while (holder && !ts.isFunctionLike(holder)) holder = holder.parent
    const holderName = holder && nameOf(holder)
    return holder !== undefined && !/^(?:[A-Z]|use(?:[A-Z0-9]|$))/.test(holderName ?? '')
  }
  const fence = Math.max(-1, ...fences.filter((call) => captured(call.arguments[0])).map((call) => call.getStart(source)))
  // The write's receiver and arguments are evaluated before it, so an await among them comes after any fence ahead of it.
  return fence >= 0 && wait <= fence && ![node.expression.expression, ...node.arguments].some(holdsWait)
}

/** The fence gate's fixture: one write in each top-level const, each named for its case. */
const FENCE_FORMS = `
const checkAfterTheLastAwait = async () => {
  const generation = getSessionGeneration()
  await client.cancelQueries({ queryKey: queryKeys.watchlist() })
  assertSessionGeneration(generation)
  client.setQueryData(queryKeys.watchlist(), (old) => old ?? [])
}
const guardInASynchronousCallback = (fresh, _variables, context) => {
  if (!context || !isSessionGenerationCurrent(context.generation)) return
  client.setQueryData(queryKeys.notifications(), fresh)
}
const checkInsideTheLoopBeforeTheWrite = async (lists) => {
  const generation = getSessionGeneration()
  for (const list of lists) {
    if (!isSessionGenerationCurrent(generation)) return
    client.setQueryData(queryKeys.watchlist(), list)
    await later()
  }
}
const capturedByTheEnclosingFunction = () => {
  const generation = getSessionGeneration()
  return later().then((data) => {
    if (!isSessionGenerationCurrent(generation)) return
    client.setQueryData(queryKeys.watchlist(), data)
  })
}
const checkBeforeTheAwait = async () => {
  const generation = getSessionGeneration()
  if (!isSessionGenerationCurrent(generation)) return
  await client.cancelQueries({ queryKey: queryKeys.wordingReview.all() })
  client.setQueryData(queryKeys.wordingReview.byFiling(7), labelled)
}
const noCheck = (updated) => {
  client.setQueryData(queryKeys.notificationPreferences(), updated)
}
const checkOnlyInANestedFunction = async () => {
  const generation = getSessionGeneration()
  await client.cancelQueries({ queryKey: queryKeys.watchlist() })
  const current = () => isSessionGenerationCurrent(generation)
  if (!current()) return
  client.setQueryData(queryKeys.watchlist(), [])
}
const publishedByAHelper = (data) => client.setQueryData(queryKeys.watchlist(), data)
const awaitInsideTheWrite = async (context) => {
  if (!context || !isSessionGenerationCurrent(context.generation)) return
  client.setQueryData(queryKeys.watchlist(), await getWatchlist())
}
const awaitInsideTheReceiver = async (context) => {
  if (!context || !isSessionGenerationCurrent(context.generation)) return
  ;(await clientFor()).setQueryData(queryKeys.watchlist(), [])
}
const checkBeforeAForAwaitLoop = async (pages, context) => {
  assertSessionGeneration(context.generation)
  for await (const page of pages) client.setQueryData(queryKeys.savedSummaries(), page)
}
const checkBeforeALoopThatAwaitsAfterItsWrite = async (lists, context) => {
  if (!context || !isSessionGenerationCurrent(context.generation)) return
  for (const list of lists) {
    client.setQueryData(queryKeys.watchlist(), list)
    await later()
  }
}
const generationReadAfresh = async () => {
  await client.cancelQueries({ queryKey: queryKeys.watchlist() })
  assertSessionGeneration(getSessionGeneration())
  client.setQueryData(queryKeys.watchlist(), [])
}
const generationCapturedAfterTheAwait = async () => {
  await client.cancelQueries({ queryKey: queryKeys.watchlist() })
  const generation = getSessionGeneration()
  assertSessionGeneration(generation)
  client.setQueryData(queryKeys.watchlist(), [])
}
const captureAndCheckInOneRun = (data) => {
  const generation = getSessionGeneration()
  if (!isSessionGenerationCurrent(generation)) return
  client.setQueryData(queryKeys.watchlist(), data)
}
const generationHandedInAsAParameter = (data, generation) => {
  if (!isSessionGenerationCurrent(generation)) return
  client.setQueryData(queryKeys.watchlist(), data)
}
const generationOnAnotherObject = (data) => {
  if (!isSessionGenerationCurrent(latest.generation)) return
  client.setQueryData(queryKeys.watchlist(), data)
}
const letReassignedAfterTheAwait = async () => {
  let generation = getSessionGeneration()
  await client.cancelQueries({ queryKey: queryKeys.watchlist() })
  generation = getSessionGeneration()
  assertSessionGeneration(generation)
  client.setQueryData(queryKeys.watchlist(), [])
}
const generationCapturedInRender = function PreferencesForm() {
  const generation = getSessionGeneration()
  return useMutation({
    mutationFn: save,
    onSuccess: (updated) => {
      if (!isSessionGenerationCurrent(generation)) return
      client.setQueryData(queryKeys.notificationPreferences(), updated)
    },
  })
}
const generationCapturedInAHook = function useSavePreferences() {
  const generation = getSessionGeneration()
  return useMutation({
    mutationFn: save,
    onSuccess: (updated) => {
      if (!isSessionGenerationCurrent(generation)) return
      client.setQueryData(queryKeys.notificationPreferences(), updated)
    },
  })
}
const filtersWriteWithNoCheck = (data) => client.setQueriesData({ queryKey: queryKeys.watchlist() }, data)
const theIdentity = () => client.setQueryData(queryKeys.currentUser(), null)
const aSharedFamily = async () => {
  await later()
  client.setQueryData(queryKeys.company('AAPL'), company)
}
const gapCheckThatDecidesNothing = (data, _variables, context) => {
  isSessionGenerationCurrent(context.generation)
  client.setQueryData(queryKeys.watchlist(), data)
}
const gapCheckInABranchTheWriteDoesNotFollow = (data, _variables, context) => {
  if (data.length) {
    if (!isSessionGenerationCurrent(context.generation)) return
  }
  client.setQueryData(queryKeys.watchlist(), data)
}
const gapCaptureInAnAnonymousComponent = memo(function () {
  const generation = getSessionGeneration()
  return useMutation({
    mutationFn: save,
    onSuccess: (updated) => {
      if (!isSessionGenerationCurrent(generation)) return
      client.setQueryData(queryKeys.notificationPreferences(), updated)
    },
  })
})
const gapElementAccess = async () => {
  await later()
  client['setQueryData'](queryKeys.watchlist(), [])
}
const gapDestructuredMethod = async () => {
  const { setQueryData } = client
  await later()
  setQueryData(queryKeys.watchlist(), [])
}
const gapAliasedMethod = async () => {
  const write = client.setQueryData.bind(client)
  await later()
  write(queryKeys.watchlist(), [])
}
const gapAnotherCacheApi = async () => {
  await later()
  client.getQueryCache().find({ queryKey: queryKeys.watchlist() })?.setData([])
}
const gapFetchQuery = async () => {
  await later()
  await client.fetchQuery({ queryKey: queryKeys.watchlist(), queryFn: () => list })
}
`

describe('account query ownership structural gate', () => {
  const accountOwned = [
    'subscription', 'usage', 'wordingReview', 'whatChanged', 'savedSummaries', 'savedSummaryStatus', 'watchlist',
    'watchlistInsights', 'earningsAlertTickers', 'dashboardFeed', 'dashboardCalendar', 'notifications',
    'notificationPreferences', 'authConnections', 'adminInvites', 'adminFeedback', 'feedback',
  ]

  it('every query family is classified, and an account change removes exactly the account-owned ones', () => {
    // A new family in lib/queryKeys.ts fails here until it is placed. An account-owned one joins
    // ACCOUNT_QUERY_FAMILIES (features/auth/lib/accountQueryState.ts), which logout and login remove.
    const identity = ['currentUser'] // the reset publishes null for it
    const shared = [
      'registrationConfig', 'turnstileScript', 'insiders', 'peers', 'calendar', 'fullTextSearch', 'filingFundamentals',
      'analysisCoverage', 'analysisCompany', 'tickerCompany', 'tickerFilings', 'filing', 'filingContent', 'summary',
      'summaryProgress', 'company', 'companyFilings', 'companies',
    ]
    const classified = [...accountOwned, ...identity, ...shared]
    expect(new Set(classified).size).toBe(classified.length)
    expect([...classified].sort()).toEqual(Object.keys(queryKeys).sort())
    type Factory = (...args: unknown[]) => readonly unknown[]
    // The first element of every key a family builds: its one factory, or each member of an object family.
    const prefixesOf = (name: string) => {
      const entry = (queryKeys as unknown as Record<string, Factory | Record<string, Factory>>)[name]
      const factories = typeof entry === 'function' ? [entry] : Object.values(entry)
      return new Set(factories.map((factory) => factory(...Array<unknown>(factory.length).fill('x'))[0]))
    }
    // An owned family's members share one prefix, so removing it removes them all; a member under a
    // prefix of its own (a re-split like the copilot usage key F1 merged) would outlive the account.
    expect(accountOwned.filter((name) => prefixesOf(name).size !== 1)).toEqual([])
    const ownedPrefixes = new Set(accountOwned.flatMap((name) => [...prefixesOf(name)]))
    expect(new Set(ACCOUNT_QUERY_FAMILIES.map((key) => key[0]))).toEqual(ownedPrefixes)
    expect(ACCOUNT_QUERY_FAMILIES.every((key) => key.length === 1)).toBe(true) // whole families, by prefix
    // No other family builds a key under an owned prefix, or the reset would remove it too.
    expect([...identity, ...shared].filter((name) => [...prefixesOf(name)].some((prefix) => ownedPrefixes.has(prefix)))).toEqual([])
  })

  it('the canonical fetcher is the only positive current-user publisher', () => {
    const errors: string[] = []
    const identityWrites: string[] = []
    const allWrites: string[] = []
    for (const file of ['app', 'components', 'features', 'hooks', 'lib'].flatMap((dir) => sourceFiles(path.join(frontend, dir)))) {
      const source = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      const relative = path.relative(frontend, file)
      function visit(node: ts.Node) {
        if (ts.isCallExpression(node) && ts.isPropertyAccessExpression(node.expression)
          && ['setQueryData', 'setQueriesData'].includes(node.expression.name.text)) {
          const key = node.arguments[0]?.getText(source) ?? ''
          allWrites.push(`${relative}:${key}`)
          // Existing direct writers all name their registry key. A new indirect writer needs
          // an explicit ownership review rather than silently escaping this identity inventory.
          if (!key.startsWith('queryKeys.')) errors.push(`${relative}: indirect cache writer ${key}`)
          if (key.includes('currentUser')) {
            identityWrites.push(relative)
            // The reset owner publishes null, and puts back the snapshot its own reset took (restoreIdentity: a logout
            // whose request failed, while no transition has followed its reset).
            let owner: ts.Node | undefined = node.parent
            while (owner && !ts.isFunctionDeclaration(owner)) owner = owner.parent
            const restores = owner !== undefined && ts.isFunctionDeclaration(owner) && owner.name?.text === 'restoreIdentity' &&
              node.arguments[1]?.getText(source) === 'shown.data'
            if (relative !== 'features/auth/lib/accountQueryState.ts' || (node.arguments[1]?.kind !== ts.SyntaxKind.NullKeyword && !restores)) {
              errors.push(`${relative}: only the reset owner may directly publish null identity, or restore its own snapshot`)
            }
          }
        }
        if (ts.isObjectLiteralExpression(node)) {
          const fields = node.properties.filter(ts.isPropertyAssignment)
          const key = fields.find((field) => field.name.getText(source) === 'queryKey')?.initializer.getText(source)
          const fetcher = fields.find((field) => field.name.getText(source) === 'queryFn')?.initializer.getText(source)
          if (key === 'queryKeys.currentUser()' && fetcher && fetcher !== 'getCurrentUserSafe') {
            errors.push(`${relative}: identity query bypasses getCurrentUserSafe`)
          }
          if (key === 'queryKeys.currentUser()' && fields.some((field) => field.name.getText(source) === 'initialData')) {
            errors.push(`${relative}: initial identity bypasses the canonical fetcher`)
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
    }
    expect(errors).toEqual([])
    expect(identityWrites).toEqual(['features/auth/lib/accountQueryState.ts', 'features/auth/lib/accountQueryState.ts'])
    // current user null and its restore, watchlist x2, notification x2, saved summaries x1 (Delete prunes its row),
    // wording review x3 (the label applied as it is pressed, its rollback, the server's state).
    expect(allWrites).toHaveLength(10)
  })

  it('every write into an account-owned family checks the session generation first, with no await after the check (E29)', () => {
    // The reset removes the account families before the next account reads them, so a write that lands after it (a
    // mutation's answer, or code after an await) would start that account's snapshot with this one's data. Each write
    // is fenced in the function that makes it: an isSessionGenerationCurrent check (the write returns early when it
    // fails) or assertSessionGeneration, with no await between the fence and the write, since an await can span a
    // transition; an await in the write's receiver or arguments, or a `for await` loop, is one too, and so is a loop
    // around the write that waits anywhere in it, at its body's start, since its next turn writes after that wait. The
    // fence compares a generation captured before the function first waits: the `generation` of one of the writing
    // function's own parameters (the mutation's context), or a getSessionGeneration() const ahead of its first wait, or
    // outside it in a function that is not a component's or a hook's body (a name with a capital, or use…), since a pending
    // mutation runs the options of the latest render. A generation read afresh, one read in the same run as its check,
    // one handed in as a parameter, a `generation` on any other object, and a let do not count. The family is read from the
    // write's key, or from the `queryKey` of the filters setQueriesData takes. The reader is fencedWrite, scored on its
    // planted forms (FENCE_FORMS) by the next case. The gate reads source order, not control flow, so that the check's
    // result guards the write is review-checked: a check whose result is dropped, or one in a branch the write does not
    // follow, passes; so does a capture in a component it cannot name (an anonymous function). Nor does it see a write not
    // called as setQueryData or setQueriesData by name (element access, a destructured or aliased method) or one through
    // another cache API (query.setData, fetchQuery). Each of these is planted as a gap. Out of reach the same way, and not
    // planted: ensureQueryData, prefetchQuery and hydrate. The late answers themselves: tests/unit/lateMutationAnswers.spec.tsx
    // and the mark-seen case above.
    // Writes left unfenced, each at its count, so a second write beside an exempt one is not exempt by accident.
    const exempt: Record<string, number> = {
      // The saved-summary Delete: its updater returns nothing once the reset has removed the family, and otherwise keeps
      // every row but the one it deleted, by that row's own id, so it cannot carry one account's rows into another's.
      'app/dashboard/page.tsx:savedSummaries': 1,
    }
    const unfenced: string[] = []
    const exemptions: Record<string, number> = {}
    for (const file of ['app', 'components', 'features', 'hooks', 'lib'].flatMap((dir) => sourceFiles(path.join(frontend, dir)))) {
      const source = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      const relative = path.relative(frontend, file)
      function visit(node: ts.Node) {
        if (isCacheWrite(node)) {
          const key = node.arguments[0]?.getText(source) ?? ''
          const family = writtenFamily(node, source)
          const site = `${relative}:${family}`
          if (family && accountOwned.includes(family) && site in exempt) exemptions[site] = (exemptions[site] ?? 0) + 1
          else if (family && accountOwned.includes(family) && !fencedWrite(node, source)) {
            unfenced.push(`${relative}:${source.getLineAndCharacterOfPosition(node.getStart(source)).line + 1} ${key}`)
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
    }
    expect(unfenced).toEqual([])
    expect(exemptions).toEqual(exempt)
  })

  it('the fence reader scores its planted forms, its gaps included (E29)', () => {
    const source = ts.createSourceFile('planted.tsx', FENCE_FORMS, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const verdicts: Record<string, string> = {}
    const visit = (node: ts.Node): void => {
      if (isCacheWrite(node)) {
        let top: ts.Node = node
        while (!ts.isSourceFile(top.parent)) top = top.parent
        const family = writtenFamily(node, source)
        const verdict = family && accountOwned.includes(family) ? (fencedWrite(node, source) ? 'fenced' : 'unfenced') : 'not owned'
        if (ts.isVariableStatement(top)) verdicts[top.declarationList.declarations[0].name.getText(source)] = verdict
      }
      ts.forEachChild(node, visit)
    }
    visit(source)
    const planted = [...FENCE_FORMS.matchAll(/^const (\w+) =/gm)].map((match) => match[1])
    expect(Object.fromEntries(planted.map((name) => [name, verdicts[name] ?? 'unseen']))).toEqual({
      checkAfterTheLastAwait: 'fenced',
      guardInASynchronousCallback: 'fenced',
      checkInsideTheLoopBeforeTheWrite: 'fenced',
      capturedByTheEnclosingFunction: 'fenced',
      checkBeforeTheAwait: 'unfenced',
      noCheck: 'unfenced',
      checkOnlyInANestedFunction: 'unfenced',
      publishedByAHelper: 'unfenced', // the check must sit in the writing function; its caller's does not count
      awaitInsideTheWrite: 'unfenced',
      awaitInsideTheReceiver: 'unfenced',
      checkBeforeAForAwaitLoop: 'unfenced',
      checkBeforeALoopThatAwaitsAfterItsWrite: 'unfenced',
      generationReadAfresh: 'unfenced',
      generationCapturedAfterTheAwait: 'unfenced',
      captureAndCheckInOneRun: 'unfenced',
      generationHandedInAsAParameter: 'unfenced',
      generationOnAnotherObject: 'unfenced',
      letReassignedAfterTheAwait: 'unfenced',
      generationCapturedInRender: 'unfenced',
      generationCapturedInAHook: 'unfenced',
      filtersWriteWithNoCheck: 'unfenced',
      theIdentity: 'not owned',
      aSharedFamily: 'not owned',
      // Gaps: each breaks the rule, and the gate passes it.
      gapCheckThatDecidesNothing: 'fenced',
      gapCheckInABranchTheWriteDoesNotFollow: 'fenced',
      gapCaptureInAnAnonymousComponent: 'fenced',
      gapElementAccess: 'unseen',
      gapDestructuredMethod: 'unseen',
      gapAliasedMethod: 'unseen',
      gapAnotherCacheApi: 'unseen',
      gapFetchQuery: 'unseen',
    })
  })

  it('all subscription/usage reads carry identity and an enabled condition, never a family prefix', () => {
    const errors: string[] = []
    const owners = new Set<string>()
    for (const file of ['app', 'components', 'features', 'hooks'].flatMap((dir) => sourceFiles(path.join(frontend, dir)))) {
      const source = ts.createSourceFile(file, readFileSync(file, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      function visit(node: ts.Node) {
        if (ts.isObjectLiteralExpression(node)) {
          const fields = node.properties.filter(ts.isPropertyAssignment)
          const fetcher = fields.find((field) => field.name.getText(source) === 'queryFn')?.initializer.getText(source)
          if (fetcher === 'getSubscriptionStatus' || fetcher === 'getUsage') {
            const family = fetcher === 'getUsage' ? 'usage' : 'subscription'
            const key = fields.find((field) => field.name.getText(source) === 'queryKey')?.initializer.getText(source)
            const enabled = fields.find((field) => field.name.getText(source) === 'enabled')?.initializer.getText(source)
            const identity = key?.includes('currentUser?.id') ? 'currentUser' : 'user'
            if (!key?.match(new RegExp(`^queryKeys\\.${family}\\.byUser\\((?:user|currentUser)\\?\\.id\\)$`)) || !enabled?.match(new RegExp(`^!!${identity}(?:$| && )`))) {
              errors.push(`${path.relative(frontend, file)}: ${fetcher} needs a resolved identity key and enabled guard`)
            }
            owners.add(`${path.relative(frontend, file)}:${family}`)
          }
        }
        ts.forEachChild(node, visit)
      }
      visit(source)
    }
    expect(errors).toEqual([])
    expect(owners.size).toBe(11) // Deliberately inventory new consumers alongside the key owner (SubscriptionGate, deleted unused, was the twelfth).
  })

  it('ordinary transitions use the shared owner, and completion invalidates both scoped families', () => {
    for (const file of ['components/Header.tsx', 'features/auth/components/UserMenu.tsx', 'app/dashboard/page.tsx']) {
      const source = readFileSync(path.join(frontend, file), 'utf8')
      // Which files call logoutAndResetAccount, each call's continuation, and what runs whatever the logout's outcome:
      // tests/unit/logoutCallSitesGate.spec.ts.
      expect(source, file).not.toMatch(/invalidateQueries\(\{ queryKey: queryKeys\.currentUser\(\)/)
    }
    const login = readFileSync(path.join(frontend, 'app/login/page.tsx'), 'utf8')
    expect(login).toContain('acceptLoginAndResetAccount(queryClient, explicitGeneration)')
    expect(login).toContain('const explicitGeneration = getExplicitSessionGeneration()')
    expect(login).toContain('queryClient.fetchQuery(')
    const afterIdentity = login.indexOf('assertExplicitSessionGeneration(acceptedGeneration)')
    expect(afterIdentity).toBeGreaterThan(login.indexOf('await queryClient.fetchQuery('))
    expect(afterIdentity).toBeLessThan(login.indexOf('analytics.loginCompleted('))
    expect(afterIdentity).toBeLessThan(login.indexOf('router.push(safe)'))
    expect(login).not.toMatch(/await getCurrentUser\(/)
    expect(login).toContain('queryKeys.subscription.all()')
    expect(login).toContain('queryKeys.usage.all()')
    for (const file of ['features/analysis/components/AnalysisPageClient.tsx', 'features/filings/components/copilot/AskCopilotRail.tsx']) {
      expect(readFileSync(path.join(frontend, file), 'utf8')).toContain('invalidateQueries({ queryKey: queryKeys.usage.all() })')
    }
    // Providers subscribes the app's client to both account listeners, each in an effect that returns its unsubscribe. Read
    // from the parsed source, so a call left in a comment does not count.
    const providersFile = path.join(frontend, 'app/providers.tsx')
    const providers = ts.createSourceFile(providersFile, readFileSync(providersFile, 'utf8'), ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
    const component = providers.statements.find((statement): statement is ts.FunctionDeclaration => ts.isFunctionDeclaration(statement) && statement.name?.text === 'Providers')
    const subscribed = (component?.body?.statements ?? []).flatMap((statement) => {
      const call = ts.isExpressionStatement(statement) ? statement.expression : undefined
      if (!call || !ts.isCallExpression(call) || call.expression.getText(providers) !== 'useEffect') return []
      const effect = call.arguments[0]
      return effect && ts.isArrowFunction(effect) && !ts.isBlock(effect.body) ? [effect.body.getText(providers)] : []
    })
    expect(subscribed).toEqual(['subscribeAccountQueryReset(queryClient)', 'subscribeAccountIdentityChange(queryClient)'])
    expect(readFileSync(path.join(frontend, 'lib/api/client.ts'), 'utf8')).not.toContain('QueryClient')
  })
})
