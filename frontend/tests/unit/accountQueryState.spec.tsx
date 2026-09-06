import { readFileSync, readdirSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider, MutationObserver, useQuery } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import api from '@/lib/api/client'
import { getCurrentUser, getCurrentUserSafe, login, logout, type CurrentUser } from '@/features/auth/api/auth-api'
import { getSubscriptionStatus, getUsage } from '@/features/subscriptions/api/subscriptions-api'
import { logoutAndResetAccount, resetAccountQueries, subscribeAccountQueryReset, acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getSessionGeneration, getExplicitSessionGeneration, assertExplicitSessionGeneration, hasActiveSession, markSessionActive, notifySessionLost } from '@/lib/api/session'
import { queryKeys } from '@/lib/queryKeys'
import { refreshAccessToken } from '@/lib/api/refresh'
import ProfileForm from '@/features/settings/components/ProfileForm'
import { usePostHogUserIdentification } from '@/hooks/usePostHogUserIdentification'

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
})

describe('account snapshots follow the resolved identity', () => {
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
    vi.mocked(refreshAccessToken).mockRejectedValue({ response: { status: 401 } })
    api.defaults.adapter = async (config) => {
      if (config.url === '/api/auth/login') return response(config, await credential.promise)
      if (config.url === '/api/auth/logout') return response(config, await logoutDone.promise)
      throw Object.assign(new Error('expired A'), { config, response: { status: 401, data: { detail: 'Expired access' } } })
    }
    const explicitGeneration = getExplicitSessionGeneration()
    const signedIn = login('2@example.test', 'test-only-password').catch((error) => error)
    const pendingLogout = order === 'passive-loss-then-logout' ? logoutAndResetAccount(client, logout) : null
    const oldIdentity = client.fetchQuery({ queryKey: queryKeys.currentUser(), queryFn: getCurrentUserSafe, staleTime: 0 }).catch((error) => error)
    await waitFor(() => expect(refreshAccessToken).toHaveBeenCalledTimes(1))
    await oldIdentity
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(getExplicitSessionGeneration()).toBe(explicitGeneration)
    if (pendingLogout) {
      logoutDone.resolve({ ok: true })
      await pendingLogout
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
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
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

  it('resets both families even when the ordinary logout request fails', async () => {
    const client = newClient()
    client.setQueryData(queryKeys.currentUser(), makeUser(1))
    client.setQueryData(queryKeys.subscription.byUser(1), { is_pro: true })
    client.setQueryData(queryKeys.usage.byUser(1), { summaries_used: 9 })
    markSessionActive()
    api.defaults.adapter = async () => { throw new Error('offline logout') }
    await expect(logoutAndResetAccount(client, logout)).rejects.toThrow('offline logout')
    expect(hasActiveSession()).toBe(false)
    expect(client.getQueryData(queryKeys.currentUser())).toBeNull()
    expect(client.getQueryCache().findAll({ queryKey: queryKeys.subscription.all() })).toHaveLength(0)
    expect(client.getQueryCache().findAll({ queryKey: queryKeys.usage.all() })).toHaveLength(0)
  })
})

const frontend = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
function sourceFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const file = path.join(directory, entry.name)
    return entry.isDirectory() ? sourceFiles(file) : /\.tsx?$/.test(file) ? [file] : []
  })
}

describe('account query ownership structural gate', () => {
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
            if (relative !== 'features/auth/lib/accountQueryState.ts' || node.arguments[1]?.kind !== ts.SyntaxKind.NullKeyword) {
              errors.push(`${relative}: only the reset owner may directly publish null identity`)
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
    expect(identityWrites).toEqual(['features/auth/lib/accountQueryState.ts'])
    expect(allWrites).toHaveLength(5) // current user null, watchlist x2, notification x2.
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
    expect(owners.size).toBe(12) // Deliberately inventory new consumers alongside the key owner.
  })

  it('ordinary transitions use the shared owner, and completion invalidates both scoped families', () => {
    for (const file of ['components/Header.tsx', 'features/auth/components/UserMenu.tsx', 'app/dashboard/page.tsx']) {
      const source = readFileSync(path.join(frontend, file), 'utf8')
      expect(source, file).toContain('logoutAndResetAccount(queryClient, logout,')
      const ast = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX)
      const callbacks: ts.ArrowFunction[] = []
      const find = (node: ts.Node) => {
        if (ts.isCallExpression(node) && node.expression.getText(ast) === 'logoutAndResetAccount') {
          const callback = node.arguments[2]
          if (callback && ts.isArrowFunction(callback)) callbacks.push(callback)
        }
        ts.forEachChild(node, find)
      }
      find(ast)
      expect(callbacks).toHaveLength(1)
      expect(callbacks[0].modifiers?.some((m) => m.kind === ts.SyntaxKind.AsyncKeyword) ?? false).toBe(false)
      expect(callbacks[0].body.getText(ast)).toContain('router.push(')
      expect(callbacks[0].body.getText(ast)).toContain('router.refresh()')
      if (file === 'app/dashboard/page.tsx') {
        expect(callbacks[0].body.getText(ast)).toContain('if (!succeeded) return')
        expect(callbacks[0].body.getText(ast)).toContain('analytics.logout()')
      }
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
    expect(readFileSync(path.join(frontend, 'app/providers.tsx'), 'utf8')).toContain('subscribeAccountQueryReset(queryClient)')
    expect(readFileSync(path.join(frontend, 'lib/api/client.ts'), 'utf8')).not.toContain('QueryClient')
  })
})
