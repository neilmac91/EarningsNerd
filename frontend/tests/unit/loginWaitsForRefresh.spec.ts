import { execFileSync } from 'node:child_process'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CanceledError, type InternalAxiosRequestConfig } from 'axios'
import { QueryClient } from '@tanstack/react-query'
import { bindingReferences, bindingResolver } from './astBindings'

// The refresh is mocked so each case decides when it answers; the cookies it carries and sets are modelled below.
vi.mock('@/lib/api/refresh', () => ({ refreshAccessToken: vi.fn() }))

import api, { ensureRefreshed, isRefreshableRequest } from '@/lib/api/client'
import { refreshAccessToken } from '@/lib/api/refresh'
import { postStreamWithRefresh } from '@/lib/api/streamRefresh'
import { LOGIN_REFRESH_WAIT_MS, login, logout } from '@/features/auth/api/auth-api'
import { acceptLoginAndResetAccount } from '@/features/auth/lib/accountQueryState'
import { advanceSessionGeneration, clearSessionActive, getExplicitSessionGeneration, hasActiveSession, markSessionActive, subscribeSessionLoss } from '@/lib/api/session'

/**
 * E29 (4): a silent refresh's answer sets the session cookies, and one sent with the previous session's cookies that
 * answers after a login's answer sets them over the new login's, so the browser is signed in as the previous account
 * while the tab shows the new one. The generation fences stop its replay and its cache writes, not its cookies. So a
 * login lets the refresh in flight answer first, or cancels it at its limit, as a logout does (E133), and holds every
 * refresh a 401 asks for until its own request has answered: sent after that answer, a refresh carries whatever cookies
 * are current. The cases model the browser's cookies (`cookies`): a request carries the ones of the moment it is sent,
 * a refresh's answer sets again the session it was sent with, and a login that took sets its own. Another tab's
 * refresh, which the session cookies' lock keeps apart from a login, is sessionCookiesAcrossTabs.spec.ts's: jsdom has
 * no lock manager, so these cases run one tab alone.
 */

type Session = 'A' | 'B'
type LoginOutcome = 'took' | 'failed'

const refreshMock = vi.mocked(refreshAccessToken)
const originalAdapter = api.defaults.adapter
const EMAIL = 'b@example.test'
const PASSWORD = 'test-only-password'
// The browser's session cookies: whose session they hold, and whether its access token is still good. A, the reader
// signed in before the login, starts with an access token that has expired.
let cookies: { session: Session; fresh: boolean }
// What reached the server, in order, and as whom; and when each login, logout and refresh answered.
const events: string[] = []
// Each login's answer, in the order the logins are sent; a login with none takes at once. And each logout's, alike.
const loginAnswers: Promise<LoginOutcome>[] = []
const logoutAnswers: Promise<void>[] = []
// Every answer a case holds, let go after it, so that no refresh or login outlives its case in the client's state.
const held: (() => void)[] = []

function hold<T>(fallback: T) {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  held.push(() => resolve(fallback))
  return { promise, resolve }
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
const ok = (config: InternalAxiosRequestConfig, data: unknown) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const unauthorized = (config: InternalAxiosRequestConfig, detail: string) => Object.assign(new Error('Request failed with status code 401'), {
  config, isAxiosError: true, response: { status: 401, statusText: 'Unauthorized', data: { detail }, headers: {}, config },
})

/** The refresh, answering once `answer` settles: sent with the cookies of the moment, its answer sets that session's
 * again, with a fresh access token. Cancelled first, it fails, and its answer is dropped, its cookies with it, as the
 * browser drops a cancelled request's. */
function refreshAnswersWhen(answer: Promise<void>) {
  refreshMock.mockImplementation((_url, signal) => {
    const sentWith = cookies.session
    events.push(`refresh sent with ${sentWith}`)
    return new Promise<void>((resolve, reject) => {
      signal?.addEventListener('abort', () => reject(new CanceledError()))
      void answer.then(() => {
        if (signal?.aborted) return
        cookies = { session: sentWith, fresh: true }
        events.push(`refresh answered for ${sentWith}`)
        resolve()
      })
    })
  })
}

/** A login whose request is out, and a read sent meanwhile, whose expired access token answers 401. */
async function readingWhileTheLoginIsOut() {
  const loginAnswer = hold<LoginOutcome>('failed')
  loginAnswers.push(loginAnswer.promise)
  const signingIn = login(EMAIL, PASSWORD)
  await settle()
  const reading = api.get('/api/watchlist/').catch((error: unknown) => error)
  await settle()
  return { loginAnswer, signingIn, reading }
}

beforeEach(() => {
  cookies = { session: 'A', fresh: false }
  events.length = 0
  refreshMock.mockReset()
  refreshAnswersWhen(Promise.resolve())
  clearSessionActive()
  markSessionActive()
  api.defaults.adapter = async (config) => {
    if (config.url === '/api/auth/login') {
      events.push(`${config.method} ${config.url}`)
      const outcome = await (loginAnswers.shift() ?? 'took')
      events.push(`login ${outcome}`)
      if (outcome === 'failed') throw unauthorized(config, 'Incorrect email or password')
      cookies = { session: 'B', fresh: true }
      return ok(config, { ok: true })
    }
    if (config.url === '/api/auth/logout') {
      events.push(`${config.method} ${config.url}`)
      await logoutAnswers.shift()
      events.push('logout answered')
      return ok(config, { ok: true })
    }
    events.push(`${config.method} ${config.url} as ${cookies.session}`)
    if (!cookies.fresh) throw unauthorized(config, 'Token expired')
    return ok(config, { reader: cookies.session })
  }
})

afterEach(async () => {
  // First, before anything waits: with the session ended, no refresh a case left waiting can start after it.
  clearSessionActive()
  vi.useRealTimers()
  for (const letGo of held.splice(0)) letGo()
  loginAnswers.length = 0
  logoutAnswers.length = 0
  await settle()
  api.defaults.adapter = originalAdapter
})

describe('a login waits for the refresh in flight', () => {
  it('sends the login only once the refresh in flight has answered, and a refresh asked for meanwhile joins that one', async () => {
    const answer = hold<void>(undefined)
    refreshAnswersWhen(answer.promise)
    const refreshing = ensureRefreshed()
    const signingIn = login(EMAIL, PASSWORD)
    const joined = ensureRefreshed()
    await settle()
    expect(events).toEqual(['refresh sent with A'])

    answer.resolve()
    await Promise.all([refreshing, joined, signingIn])
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(events).toEqual(['refresh sent with A', 'refresh answered for A', 'post /api/auth/login', 'login took'])
    expect(cookies).toEqual({ session: 'B', fresh: true })
  })

  it('cancels a refresh still unanswered at the limit, then sends the login', async () => {
    vi.useFakeTimers()
    const answer = hold<void>(undefined)
    refreshAnswersWhen(answer.promise)
    const refreshing = ensureRefreshed().catch((error: unknown) => error)
    const signal = refreshMock.mock.calls[0][1] as AbortSignal
    const signingIn = login(EMAIL, PASSWORD)
    await vi.advanceTimersByTimeAsync(LOGIN_REFRESH_WAIT_MS - 1)
    expect(events).toEqual(['refresh sent with A'])
    expect(signal.aborted).toBe(false)

    await vi.advanceTimersByTimeAsync(1)
    expect(signal.aborted).toBe(true)
    await signingIn
    // Its answer comes after all, and is dropped: cancelled, it cannot set A's cookies over the login's.
    answer.resolve()
    expect(await refreshing).toBeInstanceOf(CanceledError)
    expect(events).toEqual(['refresh sent with A', 'post /api/auth/login', 'login took'])
    expect(cookies).toEqual({ session: 'B', fresh: true })
  })
})

describe('a refresh asked for while a login is under way', () => {
  it('is held from the moment the login starts, before the login has waited on anything', async () => {
    const answer = hold<void>(undefined)
    refreshAnswersWhen(answer.promise)
    const signingIn = login(EMAIL, PASSWORD)
    // A 401's, landing as the login starts.
    const refreshing = ensureRefreshed()
    expect(refreshMock).not.toHaveBeenCalled()

    await signingIn
    answer.resolve()
    await refreshing
    expect(events).toEqual(['post /api/auth/login', 'login took', 'refresh sent with B', 'refresh answered for B'])
    expect(cookies).toEqual({ session: 'B', fresh: true })
  })

  it('is not sent for a 401 that lands while the login is out, until the login has answered', async () => {
    const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
    expect(events).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A'])
    expect(refreshMock).not.toHaveBeenCalled()
    // A login is no logout: the session still reads as active, so the 401 is held, not taken for a lost session.
    expect(hasActiveSession()).toBe(true)

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    await reading
    expect(events.slice(0, 4)).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A', 'login failed', 'refresh sent with A'])
  })

  it('renews the previous session after a login that failed, and the request replays', async () => {
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    try {
      const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
      loginAnswer.resolve('failed')
      await expect(signingIn).rejects.toMatchObject({ status: 401 })
      expect(await reading).toMatchObject({ status: 200, data: { reader: 'A' } })
      expect(events).toEqual([
        'post /api/auth/login', 'get /api/watchlist/ as A', 'login failed',
        'refresh sent with A', 'refresh answered for A', 'get /api/watchlist/ as A',
      ])
      expect(cookies).toEqual({ session: 'A', fresh: true })
      expect(hasActiveSession()).toBe(true)
      expect(lost).not.toHaveBeenCalled()
    } finally {
      unsubscribe()
    }
  })

  it('sends one refresh for every 401 held behind a login that failed, and every request replays', async () => {
    const loginAnswer = hold<LoginOutcome>('failed')
    loginAnswers.push(loginAnswer.promise)
    const signingIn = login(EMAIL, PASSWORD)
    await settle()
    const reads = ['/api/watchlist/', '/api/notifications/'].map((url) => api.get(url).catch((error: unknown) => error))
    await settle()
    expect(refreshMock).not.toHaveBeenCalled()

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    expect(await Promise.all(reads)).toMatchObject([{ status: 200, data: { reader: 'A' } }, { status: 200, data: { reader: 'A' } }])
    // Held, they share one refresh, as concurrent 401s do: two on the single-use rotating token would undo each other.
    expect(refreshMock).toHaveBeenCalledTimes(1)
    expect(events).toEqual([
      'post /api/auth/login', 'get /api/watchlist/ as A', 'get /api/notifications/ as A', 'login failed',
      'refresh sent with A', 'refresh answered for A', 'get /api/watchlist/ as A', 'get /api/notifications/ as A',
    ])
  })

  it('sends nothing once a logout has started, for a refresh held behind a login', async () => {
    const logoutAnswer = hold<void>(undefined)
    logoutAnswers.push(logoutAnswer.promise)
    const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
    // The logout starts while the 401's refresh is held, and the session reads as inactive until it settles.
    const loggingOut = logout()
    await settle()
    expect(hasActiveSession()).toBe(false)

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    // The held refresh finds the session ended: a refresh sent now would set the cookies the logout's answer clears.
    expect(await reading).toMatchObject({ name: 'ApiError', status: 401 })
    logoutAnswer.resolve()
    await loggingOut
    expect(refreshMock).not.toHaveBeenCalled()
    expect(events).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A', 'post /api/auth/logout', 'login failed', 'logout answered'])
  })

  it('sends nothing once the account has changed under it, for a refresh held behind a login', async () => {
    const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
    // Another tab signed in as the second account (the browser's cookies are its own now), and its sign-in reaches this
    // tab through /me while the refresh is held, moving the session generation (accountQueryState's watchReader): the
    // held 401 belongs to the account the tab showed before.
    cookies = { session: 'B', fresh: true }
    advanceSessionGeneration('session-loss')
    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    // The held refresh finds another generation: sent now, it would renew the account the tab no longer shows.
    expect(await reading).toMatchObject({ name: 'ApiError', status: 401 })
    expect(refreshMock).not.toHaveBeenCalled()
    expect(events).toEqual(['post /api/auth/login', 'get /api/watchlist/ as A', 'login failed'])
  })

  it('sends nothing as the previous account, and brings it nothing, after a login that took and was accepted', async () => {
    const lost = vi.fn()
    const unsubscribe = subscribeSessionLoss(lost)
    try {
      // A refresh answers only once the login has answered and been accepted: one sent before the login's answer, with
      // A's cookies, would set them over B's.
      const refreshAnswer = hold<void>(undefined)
      refreshAnswersWhen(refreshAnswer.promise)
      const explicitGeneration = getExplicitSessionGeneration()
      const { loginAnswer, signingIn, reading } = await readingWhileTheLoginIsOut()
      loginAnswer.resolve('took')
      await signingIn
      // app/login/page.tsx's order: the login is accepted in the turn its answer resumes in.
      acceptLoginAndResetAccount(new QueryClient(), explicitGeneration)
      refreshAnswer.resolve()
      // The held refresh woke before the acceptance and went out with B's cookies, and the acceptance fences its replay
      // (woken after it, the refresh would abort): nothing reaches the server as A once the login has answered, and
      // nothing comes back to the request.
      expect(await reading).toMatchObject({ name: 'ApiError', status: 401 })
      expect(events.slice(events.indexOf('login took')).filter((event) => event.endsWith(' A'))).toEqual([])
      expect(events.filter((event) => event.startsWith('get '))).toEqual(['get /api/watchlist/ as A'])
      expect(cookies.session).toBe('B')
      expect(hasActiveSession()).toBe(true)
      expect(lost).not.toHaveBeenCalled()
    } finally {
      unsubscribe()
    }
  })

  it('is held for the stream readers too, which ask ensureRefreshed for theirs (postStreamWithRefresh)', async () => {
    const loginAnswer = hold<LoginOutcome>('failed')
    loginAnswers.push(loginAnswer.promise)
    const signingIn = login(EMAIL, PASSWORD)
    await settle()
    const post = vi.fn(async () => {
      events.push(`stream as ${cookies.session}`)
      return { status: cookies.fresh ? 200 : 401, ok: cookies.fresh } as Response
    })
    const streaming = postStreamWithRefresh(post)
    await settle()
    expect(refreshMock).not.toHaveBeenCalled()

    loginAnswer.resolve('failed')
    await expect(signingIn).rejects.toMatchObject({ status: 401 })
    expect((await streaming).status).toBe(200)
    expect(events).toEqual([
      'post /api/auth/login', 'stream as A', 'login failed', 'refresh sent with A', 'refresh answered for A', 'stream as A',
    ])
  })

  it('stays held while a later login is out, after an earlier one has answered', async () => {
    const first = hold<LoginOutcome>('failed')
    const second = hold<LoginOutcome>('failed')
    loginAnswers.push(first.promise, second.promise)
    const one = login(EMAIL, PASSWORD)
    const two = login(EMAIL, PASSWORD)
    await settle()
    first.resolve('failed')
    await expect(one).rejects.toMatchObject({ status: 401 })
    const refreshing = ensureRefreshed()
    await settle()
    expect(refreshMock).not.toHaveBeenCalled()

    second.resolve('took')
    await two
    await refreshing
    expect(events).toEqual([
      'post /api/auth/login', 'post /api/auth/login', 'login failed', 'login took', 'refresh sent with B', 'refresh answered for B',
    ])
  })

  it('is sent at once after the login has answered: nothing stays held', async () => {
    loginAnswers.push(Promise.resolve<LoginOutcome>('failed'))
    await expect(login(EMAIL, PASSWORD)).rejects.toMatchObject({ status: 401 })
    const refreshing = ensureRefreshed().catch((error: unknown) => error)
    expect(refreshMock).toHaveBeenCalledTimes(1)
    await refreshing
    expect(cookies).toEqual({ session: 'A', fresh: true })
  })
})

/**
 * Gate (CLAUDE.md rule 12), both ends of the hold, in this tab and across tabs (E29 (4), E133). The posts whose answer
 * sets or clears the session cookies: a literal (a string, or a template's text) that names /api/auth/login is an
 * argument of the call returned (its expression body, or a `return` of its own, through `await` and parentheses) by a
 * function handed inline, as the second argument, to a call of `withoutRefreshBeside` imported by that name from
 * lib/api/client, so the helper's promise is that request's; one that names /api/auth/logout, /api/auth/logout-all or
 * /api/auth/change-password is so, alike, for `withSessionCookiesForPost`, which holds the session cookies' lock,
 * shared, around it. In
 * lib/api/client.ts, withoutRefreshBeside hands its send by name, as the second argument, to the module's own
 * withSessionCookiesForPost (a function it declares at its top level), and names it nowhere else, so the login holds
 * the lock too. The refresh: none starts outside ensureRefreshed, which holds it behind a login, and its one call there
 * is returned, as above, by a function handed inline as the second argument to the module's own
 * withSessionCookiesForRefresh, which holds the lock for it, one refresh at a time. The lock's callers: every use of
 * either hold's name, or of sessionCookiesSettled's (the identity read's wait for the refreshes queued before it),
 * anywhere, is one of the six calls the client and the auth API make (HOLD_SITES: the refresh in ensureRefreshed, the
 * login's hand-off in withoutRefreshBeside, the two logouts, the password change's post in postPasswordChange and the
 * wait in getCurrentUser), so no other request runs under the lock and nothing else waits on it, and each of the four
 * routes posted under it is one whose own 401 asks for no refresh (isRefreshableRequest): a refresh asked for under the
 * lock would wait for the lock its own caller holds, and every tab's refresh behind it. lib/api/refresh, whose
 * refreshAccessToken posts to /api/auth/refresh, is imported or exported anywhere only by lib/api/client.ts, by that one
 * name, whose one use of it is that call, and no other literal names that path; client.ts's NO_REFRESH_PATHS, a list of
 * paths and not a request, is pinned for the login's, the logout's, the password change's and the refresh's paths to its
 * one site. The identity read's path, /api/auth/me, is named by a literal only in getCurrentUser (ME_SITES), so every
 * /me read waits for the refreshes before it, as a tab landing from an OAuth sign-in needs; that the wait is awaited
 * before the read is the specs' to hold (planted as a gap). What the holds and the wait themselves do (the lock and its two modes, the waits and their bounds, the post
 * at its limit, the password change's renewal after its hold) is sessionCookiesAcrossTabs.spec.ts's to hold. What it
 * reads: every tracked
 * file under frontend/ (`git ls-files`) of each JS and TS extension, in every directory but tests/, in one walk per
 * file. Refused though the rule may hold: a path held in a const, a helper renamed on import or read off a namespace, a
 * send declared apart, a send that awaits the post and returns its answer, the login's send wrapped in an arrow before
 * it is handed on, a hold imported or declared other than as the client's own top-level function, a hold's name used
 * but as the callee of one of its calls (a value, a re-export, a string), withoutRefreshBeside declared as a
 * const, and any import of the refresh module but client.ts's, a type-only one included. lib/api/refresh.ts's own uses
 * of refreshAccessToken are read too (its name resolves to the declaration there, not to an import), so a keep-alive
 * inside it that calls refreshAccessToken is refused. Out of its reach (planted as gaps): a path or a hold's name
 * assembled at run time; a send that returns a call of an async local helper which posts without returning the post;
 * another request one of the five sends makes before its own (getCurrentUser's among them, whose wait would keep it
 * waiting under the hold, until its limit, for the lock its own caller holds; a call of the wait itself there is
 * refused); a call site that passes its own limit, or a request given
 * its own timeout, which the refresh's bound does not allow for (sessionCookiesAcrossTabs.spec.ts's constants check
 * covers the constants, not the calls); a hold whose own body takes no lock; and, inside refreshAccessToken itself, a
 * second post of its own path (a timer it sets there), which reads as the one path where it stands.
 */
const FRONTEND = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const SOURCE = /\.(?:[cm]?[jt]s|[jt]sx)$/
const REFRESH_PATH = /\/api\/auth\/refresh(?![\w-])/
const CLIENT = 'lib/api/client.ts'
const AUTH_API = 'features/auth/api/auth-api.ts'
const REFRESH_MODULE = 'lib/api/refresh'
// The client's two holds of the session cookies' lock: the refresh's, exclusive, and the posts', shared; and the
// identity read's wait for the refreshes queued before it, which takes the lock shared and lets it go at once.
const REFRESH_HOLD = 'withSessionCookiesForRefresh'
const POST_HOLD = 'withSessionCookiesForPost'
const SETTLED = 'sessionCookiesSettled'
// The posts whose answer sets or clears the session cookies: each route, the literals that name it, and the helper
// whose send must post it. The login's helper keeps its one-tab gate and hands the send on to the posts' hold.
const HELD_POSTS = {
  login: { route: '/api/auth/login', names: /\/api\/auth\/login(?![\w-])/, helper: 'withoutRefreshBeside' },
  logout: { route: '/api/auth/logout', names: /\/api\/auth\/logout(?![\w-])/, helper: POST_HOLD },
  logoutAll: { route: '/api/auth/logout-all', names: /\/api\/auth\/logout-all(?![\w-])/, helper: POST_HOLD },
  changePassword: { route: '/api/auth/change-password', names: /\/api\/auth\/change-password(?![\w-])/, helper: POST_HOLD },
} as const
type HeldPost = keyof typeof HELD_POSTS
const HELD = Object.keys(HELD_POSTS) as HeldPost[]
// What withoutRefreshBeside does with its send, all of it: anything else is a login that could post outside the lock.
const LOGIN_SEND = ["handed to the posts' hold"]
// The refresh's sites, all of them: anything else, anywhere, is a refresh that could start outside ensureRefreshed.
const REFRESH_SITES: Record<string, string[]> = {
  [CLIENT]: ["call of refreshAccessToken in ensureRefreshed under the refresh's hold", 'import { refreshAccessToken } from lib/api/refresh', 'path in NO_REFRESH_PATHS'],
  'lib/api/refresh.ts': ['path in refreshAccessToken'],
}
const HOLD_NAMES: string[] = [REFRESH_HOLD, POST_HOLD, SETTLED]
// The identity read's path, and where a literal may name it: anywhere else is a /me read that skips the wait.
const ME_PATH = /\/api\/auth\/me(?![\w-])/
const ME_SITES: Record<string, string[]> = { [AUTH_API]: ['path in getCurrentUser'] }
// The lock's calls, all of them: any other use of a hold's name, anywhere, is another request that could run under the
// lock, or a hold that could be taken around one, and any other use of the wait's is a wait that could stand in a send.
const HOLD_SITES: Record<string, string[]> = {
  [CLIENT]: [`call of ${POST_HOLD} in withoutRefreshBeside`, `call of ${REFRESH_HOLD} in ensureRefreshed`],
  [AUTH_API]: [`call of ${POST_HOLD} in logout`, `call of ${POST_HOLD} in logoutAllSessions`, `call of ${POST_HOLD} in postPasswordChange`, `call of ${SETTLED} in getCurrentUser`],
}

const scriptKind = (file: string): ts.ScriptKind =>
  file.endsWith('.tsx') ? ts.ScriptKind.TSX : file.endsWith('.jsx') ? ts.ScriptKind.JSX : /\.[cm]?js$/.test(file) ? ts.ScriptKind.JS : ts.ScriptKind.TS
/** The module a specifier names from `file`, `@/` and relative alike, without its script extension. */
const moduleOf = (specifier: string, file: string): string | undefined =>
  (specifier.startsWith('@/') ? path.posix.normalize(specifier.slice(2)) : specifier.startsWith('.') ? path.posix.join(path.posix.dirname(file), specifier) : undefined)
    ?.replace(SOURCE, '')
/** A value without the wrappers it passes through unchanged here: parentheses, `await`, `as`, `satisfies` and `!`. */
const unwrap = (node: ts.Expression): ts.Expression =>
  ts.isParenthesizedExpression(node) || ts.isAwaitExpression(node) || ts.isAsExpression(node) || ts.isSatisfiesExpression(node) || ts.isNonNullExpression(node)
    ? unwrap(node.expression) : node
/** What a function returns: its expression body, or each `return` of its own (a nested function's are its own). */
function returnedBy(fn: ts.ArrowFunction | ts.FunctionExpression): ts.Expression[] {
  if (!ts.isBlock(fn.body)) return [unwrap(fn.body)]
  const found: ts.Expression[] = []
  const walk = (node: ts.Node): void => {
    if (ts.isReturnStatement(node) && node.expression) found.push(unwrap(node.expression))
    if (!ts.isFunctionLike(node)) ts.forEachChild(node, walk)
  }
  ts.forEachChild(fn.body, walk)
  return found
}
/** Where a node stands: the named function that holds it, else the variable, else the module. */
function holder(node: ts.Node): string {
  let variable: string | undefined
  for (let at = node.parent; at; at = at.parent) {
    if ((ts.isFunctionDeclaration(at) || ts.isMethodDeclaration(at)) && at.name) return at.name.getText()
    if ((ts.isArrowFunction(at) || ts.isFunctionExpression(at)) && ts.isVariableDeclaration(at.parent) && ts.isIdentifier(at.parent.name)) return at.parent.name.text
    if (!variable && ts.isVariableDeclaration(at) && ts.isIdentifier(at.name)) variable = at.name.text
  }
  return variable ?? 'module'
}

interface Placement {
  /** Lines of the literals naming the route outside a send of its helper. */
  outside: number[]
  /** How many are inside one, and in NO_REFRESH_PATHS. */
  inside: number
  exempt: number
}
interface Reading {
  posts: Record<HeldPost, Placement>
  /** The refresh's sites, sorted. */
  refresh: string[]
  /** In lib/api/client.ts, what withoutRefreshBeside does with its send: each use of it, sorted. */
  loginSend: string[]
  /** Each use of a hold's name, but its declaration in the client and an import that keeps the name, sorted. */
  holds: string[]
  /** Where each literal naming /api/auth/me stands, sorted. */
  me: string[]
}

/** One walk over a module for both ends of the hold. */
function read(source: string, file: string): Reading {
  const sf = ts.createSourceFile(file, source, ts.ScriptTarget.Latest, true, scriptKind(file))
  const resolve = bindingResolver(sf)
  const named = (statement: ts.Statement, module: string): ts.ImportSpecifier[] =>
    ts.isImportDeclaration(statement) && ts.isStringLiteral(statement.moduleSpecifier) && moduleOf(statement.moduleSpecifier.text, file) === module &&
    statement.importClause?.namedBindings && ts.isNamedImports(statement.importClause.namedBindings) ? [...statement.importClause.namedBindings.elements] : []
  // The names imported from the client as themselves, not renamed.
  const imported = new Set(sf.statements.flatMap((statement) => named(statement, 'lib/api/client'))
    .filter((element) => !element.propertyName).map((element) => element.name.text))
  // The local names refreshAccessToken is imported under.
  const refreshNames = new Set(sf.statements.flatMap((statement) => named(statement, REFRESH_MODULE))
    .filter((element) => (element.propertyName ?? element.name).text === 'refreshAccessToken').map((element) => element.name.text))
  /** Whether a callee is this module's own function of that name, declared at its top level: not a local, a parameter or an import. */
  const ownFunction = (callee: ts.Expression, name: string): boolean => {
    if (!ts.isIdentifier(callee) || callee.text !== name) return false
    const decl = resolve(callee)?.decl
    return !!decl && ts.isFunctionDeclaration(decl) && decl.parent === sf
  }
  /** The call a function handed inline, as its second argument, returns `call` to; undefined where `call` is no such return. */
  const handedTo = (call: ts.CallExpression): ts.CallExpression | undefined => {
    let fn: ts.Node | undefined = call.parent
    while (fn && !ts.isFunctionLike(fn)) fn = fn.parent
    if (!fn || !(ts.isArrowFunction(fn) || ts.isFunctionExpression(fn)) || !returnedBy(fn).includes(call)) return undefined
    return ts.isCallExpression(fn.parent) && fn.parent.arguments[1] === fn ? fn.parent : undefined
  }
  // The literal is an argument of the call a send of the helper returns: the helper imported from the client by its own
  // name, and not shadowed where it is called.
  const sentBy = (literal: ts.Node, helper: string): boolean => {
    const call = literal.parent
    if (!ts.isCallExpression(call) || !call.arguments.some((argument) => argument === literal)) return false
    const to = handedTo(call)
    return !!to && ts.isIdentifier(to.expression) && to.expression.text === helper && imported.has(helper) && !resolve(to.expression)
  }
  /** What a use of a hold's name is: nothing to report for the hold's declaration at the client's top level or an
      import that keeps its name; else a call (by the name, or read off a namespace) and where it is, or anything else. */
  const holdUse = (node: ts.Identifier): string | undefined => {
    const parent = node.parent
    if (ts.isFunctionDeclaration(parent) && parent.name === node) return file === CLIENT && parent.parent === sf ? undefined : `declaration of ${node.text}`
    if (ts.isImportSpecifier(parent)) return parent.propertyName ? `renamed import of ${node.text}` : undefined
    if (ts.isExportSpecifier(parent)) return `export of ${node.text}`
    const callee = ts.isPropertyAccessExpression(parent) && parent.name === node ? parent : node
    return ts.isCallExpression(callee.parent) && callee.parent.expression === callee
      ? `call of ${node.text} in ${holder(callee.parent)}` : `reference to ${node.text} in ${holder(node)}`
  }
  const inNoRefreshPaths = (node: ts.Node): boolean =>
    file === CLIENT && ts.isArrayLiteralExpression(node.parent) && ts.isVariableDeclaration(node.parent.parent) &&
    ts.isIdentifier(node.parent.parent.name) && node.parent.parent.name.text === 'NO_REFRESH_PATHS'
  const found: Reading = {
    posts: {
      login: { outside: [], inside: 0, exempt: 0 },
      logout: { outside: [], inside: 0, exempt: 0 },
      logoutAll: { outside: [], inside: 0, exempt: 0 },
      changePassword: { outside: [], inside: 0, exempt: 0 },
    },
    refresh: [],
    loginSend: [],
    holds: [],
    me: [],
  }
  const refreshModule = (specifier: ts.Node | undefined): boolean =>
    !!specifier && ts.isStringLiteralLike(specifier) && moduleOf(specifier.text, file) === REFRESH_MODULE
  const clause = (text: string | undefined) => (text ?? '*').replace(/\s+/g, ' ')
  const visit = (node: ts.Node): void => {
    const texts = ts.isStringLiteralLike(node) ? [node.text]
      : ts.isTemplateExpression(node) ? [node.head.text, ...node.templateSpans.map((span) => span.literal.text)] : []
    for (const post of HELD) {
      if (!texts.some((text) => HELD_POSTS[post].names.test(text))) continue
      const placement = found.posts[post]
      if (inNoRefreshPaths(node)) placement.exempt += 1
      else if (sentBy(node, HELD_POSTS[post].helper)) placement.inside += 1
      else placement.outside.push(sf.getLineAndCharacterOfPosition(node.getStart(sf)).line + 1)
    }
    if (texts.some((text) => REFRESH_PATH.test(text))) found.refresh.push(`path in ${holder(node)}`)
    if (texts.some((text) => ME_PATH.test(text))) found.me.push(`path in ${holder(node)}`)
    if (ts.isImportDeclaration(node) && refreshModule(node.moduleSpecifier)) found.refresh.push(`import ${clause(node.importClause?.getText(sf))} from ${REFRESH_MODULE}`)
    if (ts.isExportDeclaration(node) && refreshModule(node.moduleSpecifier)) found.refresh.push(`export ${clause(node.exportClause?.getText(sf))} from ${REFRESH_MODULE}`)
    if (ts.isImportEqualsDeclaration(node) && ts.isExternalModuleReference(node.moduleReference) && refreshModule(node.moduleReference.expression)) {
      found.refresh.push(`import ${node.name.text} = require of ${REFRESH_MODULE}`)
    }
    if (ts.isCallExpression(node) && refreshModule(node.arguments[0])) {
      if (node.expression.kind === ts.SyntaxKind.ImportKeyword) found.refresh.push(`dynamic import of ${REFRESH_MODULE}`)
      else if (ts.isIdentifier(node.expression) && node.expression.text === 'require') found.refresh.push(`require of ${REFRESH_MODULE}`)
    }
    // A use of the imported refreshAccessToken: not its import, not a property's name, not a local of the same name. Its
    // call reads as held only when a function handed to the module's own refresh hold returns it.
    if (ts.isIdentifier(node) && refreshNames.has(node.text) && !ts.isImportSpecifier(node.parent) && !resolve(node) &&
      !((ts.isPropertyAccessExpression(node.parent) || ts.isPropertyAssignment(node.parent)) && node.parent.name === node)) {
      const call = ts.isCallExpression(node.parent) && node.parent.expression === node ? node.parent : undefined
      const to = call && handedTo(call)
      const held = !!to && ownFunction(to.expression, REFRESH_HOLD)
      found.refresh.push(`${call ? 'call of' : 'reference to'} ${node.text} in ${holder(node)}${held ? " under the refresh's hold" : ''}`)
    }
    // In the module that declares it, every use of refreshAccessToken but its declaration's own name: there the name
    // resolves to the declaration, not to an import, so the rule above does not see it, and a keep-alive there would
    // skip the hold, the one refresh in flight and a logout's wait.
    if (file === `${REFRESH_MODULE}.ts` && ts.isIdentifier(node) && node.text === 'refreshAccessToken' &&
      !((ts.isFunctionDeclaration(node.parent) || ts.isVariableDeclaration(node.parent)) && node.parent.name === node) &&
      !((ts.isPropertyAccessExpression(node.parent) || ts.isPropertyAssignment(node.parent)) && node.parent.name === node)) {
      const called = ts.isCallExpression(node.parent) && node.parent.expression === node
      found.refresh.push(`${called ? 'call of' : 'reference to'} refreshAccessToken in ${holder(node)}`)
    }
    // Each use of a hold, by its name or as a string.
    const use = ts.isIdentifier(node) && HOLD_NAMES.includes(node.text) ? holdUse(node) : undefined
    if (use) found.holds.push(use)
    if (ts.isStringLiteralLike(node) && HOLD_NAMES.includes(node.text)) found.holds.push(`string ${node.text} in ${holder(node)}`)
    // In the client, each use of withoutRefreshBeside's send (its second parameter).
    if (file === CLIENT && ts.isFunctionDeclaration(node) && node.parent === sf && node.name?.text === 'withoutRefreshBeside' && node.parameters[1]) {
      for (const use of bindingReferences(sf, resolve)(node.parameters[1])) {
        const at = use.parent
        found.loginSend.push(ts.isCallExpression(at) && at.arguments[1] === use && ownFunction(at.expression, POST_HOLD) ? "handed to the posts' hold"
          : ts.isCallExpression(at) && at.expression === use ? 'called' : 'used otherwise')
      }
    }
    ts.forEachChild(node, visit)
  }
  visit(sf)
  found.refresh.sort()
  found.loginSend.sort()
  found.holds.sort()
  found.me.sort()
  return found
}

const API = "import api from '@/lib/api/client'\n"
const HELPER = "import { withoutRefreshBeside } from '@/lib/api/client'\n"
const LOGIN_FORMS: { form: string; source: string; file?: string; outside: number; inside: number; exempt?: number; gap?: true }[] = [
  { form: 'posted in the send, an arrow', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 0, inside: 1 },
  { form: 'posted in the send, a function expression', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, function () { return api.post('/api/auth/login', {}) })`, outside: 0, inside: 1 },
  { form: 'returned through await', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, async () => await api.post('/api/auth/login', {}))`, outside: 0, inside: 1 },
  { form: 'the helper imported by a relative path', file: 'lib/api/auth.ts', source: "import api, { withoutRefreshBeside } from './client'\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))", outside: 0, inside: 1 },
  { form: 'posted directly', source: `${API}export const login = () => api.post('/api/auth/login', {})`, outside: 1, inside: 0 },
  { form: 'a template literal', source: `${API}export const login = () => api.post(\`/api/auth/login\`, {})`, outside: 1, inside: 0 },
  { form: 'a template with a base before the path', source: "export const login = (base: string) => fetch(`${base}/api/auth/login`, { method: 'POST' })", outside: 1, inside: 0 },
  { form: 'a query after the path', source: `${API}export const login = () => api.post('/api/auth/login?remember=1', {})`, outside: 1, inside: 0 },
  { form: 'a form that posts to it', file: 'app/fixture.tsx', source: 'export const Form = () => <form action="/api/auth/login" method="post" />', outside: 1, inside: 0 },
  { form: 'posted in the send, but not returned', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => { void api.post('/api/auth/login', {}); return Promise.resolve() })`, outside: 1, inside: 0 },
  { form: 'posted beside the promise the send returns', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => (api.post('/api/auth/login', {}), Promise.resolve()))`, outside: 1, inside: 0 },
  { form: 'in the send, in a function it never calls', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, () => { const later = () => api.post('/api/auth/login', {}); void later; return api.post('/x') })`, outside: 1, inside: 0 },
  { form: 'awaited in the send, its answer returned', source: `${API}${HELPER}export const login = () => withoutRefreshBeside(1, async () => { const answer = await api.post('/api/auth/login', {}); return answer })`, outside: 1, inside: 0 },
  { form: 'the path in a const, posted in the send', source: `${API}${HELPER}const LOGIN = '/api/auth/login'\nexport const login = () => withoutRefreshBeside(1, () => api.post(LOGIN, {}))`, outside: 1, inside: 0 },
  { form: 'a send declared apart, handed over by name', source: `${API}${HELPER}const send = () => api.post('/api/auth/login', {})\nexport const login = () => withoutRefreshBeside(1, send)`, outside: 1, inside: 0 },
  { form: 'the path in the first argument', source: `${API}${HELPER}export const login = () => withoutRefreshBeside((() => api.post('/api/auth/login', {})) as never, () => api.post('/x'))`, outside: 1, inside: 0 },
  { form: 'the helper not imported', source: `${API}export const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper imported from another module', source: `${API}import { withoutRefreshBeside } from '@/lib/other'\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper renamed on import', source: `${API}import { withoutRefreshBeside as hold } from '@/lib/api/client'\nexport const login = () => hold(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper read off a namespace', source: `${API}import * as client from '@/lib/api/client'\nexport const login = () => client.withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper shadowed by a local of its name', source: `${API}const withoutRefreshBeside = (_ms: number, send: () => unknown) => send()\nexport const login = () => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: 'the helper shadowed by a parameter', source: `${API}${HELPER}export const login = (withoutRefreshBeside: (ms: number, send: () => unknown) => unknown) => withoutRefreshBeside(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: "the posts' hold in its place, which skips the login's one-tab gate", source: `${API}import { withSessionCookiesForPost } from '@/lib/api/client'\nexport const login = () => withSessionCookiesForPost(1, () => api.post('/api/auth/login', {}))`, outside: 1, inside: 0 },
  { form: "lib/api/client.ts's NO_REFRESH_PATHS", file: CLIENT, source: "const NO_REFRESH_PATHS = ['/api/auth/refresh', '/api/auth/login']", outside: 0, inside: 0, exempt: 1 },
  { form: 'a list of that name elsewhere', source: "const NO_REFRESH_PATHS = ['/api/auth/login']", outside: 1, inside: 0 },
  // Look-alikes, which pass.
  { form: 'a longer path that starts with it', source: `${API}export const history = () => api.get('/api/auth/login-history')`, outside: 0, inside: 0 },
  { form: 'another auth path', source: `${API}export const me = () => api.get('/api/auth/me')`, outside: 0, inside: 0 },
  { form: 'the path in a comment', source: `${API}// the login posts to /api/auth/login\nexport const x = 1`, outside: 0, inside: 0 },
  // Out of its reach.
  { form: 'the path assembled at run time', source: `${API}export const login = () => api.post('/api/auth/' + 'login', {})`, outside: 0, inside: 0, gap: true },
  { form: 'the last segment substituted into a template', source: `${API}export const login = () => api.post(\`/api/auth/\${'login'}\`, {})`, outside: 0, inside: 0, gap: true },
  { form: 'the post behind a local helper that does not return it', source: `${API}${HELPER}const fire = async (url: string) => { void api.post(url, {}) }\nexport const login = () => withoutRefreshBeside(10, () => fire('/api/auth/login'))`, outside: 0, inside: 1, gap: true },
]

const POST_IMPORT = "import { withSessionCookiesForPost } from '@/lib/api/client'\n"
const LOGOUT_FORMS: { form: string; post: Exclude<HeldPost, 'login'>; source: string; file?: string; outside: number; inside: number; exempt?: number; gap?: true }[] = [
  { form: "the logout's post in the send, after the check", post: 'logout', source: `${API}${POST_IMPORT}export const logout = () => withSessionCookiesForPost(1, async () => {\n  if (!current()) return undefined\n  return api.post('/api/auth/logout')\n})`, outside: 0, inside: 1 },
  { form: "the logout of every session's post in the send, after a check that throws", post: 'logoutAll', source: `${API}${POST_IMPORT}export const logoutAll = () => withSessionCookiesForPost(1, async () => {\n  if (!current()) throw new Error('superseded')\n  return api.post('/api/auth/logout-all')\n})`, outside: 0, inside: 1 },
  { form: 'posted in the send, a function expression', post: 'logout', source: `${API}${POST_IMPORT}export const logout = () => withSessionCookiesForPost(1, function () { return api.post('/api/auth/logout') })`, outside: 0, inside: 1 },
  { form: "lib/api/client.ts's NO_REFRESH_PATHS", post: 'logout', file: CLIENT, source: "const NO_REFRESH_PATHS = ['/api/auth/refresh', '/api/auth/logout']", outside: 0, inside: 0, exempt: 1 },
  // Each way out of the hold.
  { form: 'posted directly', post: 'logout', source: `${API}export const logout = () => api.post('/api/auth/logout')`, outside: 1, inside: 0 },
  { form: "posted once this tab's refresh has settled, as before the lock", post: 'logout', source: `${API}import { refreshSettled } from '@/lib/api/client'\nexport const logout = async () => {\n  await refreshSettled(1)\n  return api.post('/api/auth/logout')\n}`, outside: 1, inside: 0 },
  { form: 'posted once the hold has ended', post: 'logoutAll', source: `${API}${POST_IMPORT}export const logoutAll = async () => {\n  await withSessionCookiesForPost(1, async () => undefined)\n  return api.post('/api/auth/logout-all')\n}`, outside: 1, inside: 0 },
  { form: "posted in the login's helper", post: 'logout', source: `${API}${HELPER}export const logout = () => withoutRefreshBeside(1, () => api.post('/api/auth/logout'))`, outside: 1, inside: 0 },
  { form: "posted under the refresh's hold", post: 'logout', source: `${API}import { withSessionCookiesForRefresh } from '@/lib/api/client'\nexport const logout = (signal: AbortSignal) => withSessionCookiesForRefresh(signal, () => api.post('/api/auth/logout'))`, outside: 1, inside: 0 },
  { form: 'posted in the send, but not returned', post: 'logoutAll', source: `${API}${POST_IMPORT}export const logoutAll = () => withSessionCookiesForPost(1, async () => { void api.post('/api/auth/logout-all') })`, outside: 1, inside: 0 },
  { form: 'posted beside the promise the send returns', post: 'logout', source: `${API}${POST_IMPORT}export const logout = () => withSessionCookiesForPost(1, () => (api.post('/api/auth/logout'), Promise.resolve()))`, outside: 1, inside: 0 },
  { form: 'in the send, in a function it never calls', post: 'logout', source: `${API}${POST_IMPORT}export const logout = () => withSessionCookiesForPost(1, () => { const later = () => api.post('/api/auth/logout'); void later; return Promise.resolve() })`, outside: 1, inside: 0 },
  { form: 'awaited in the send, its answer returned', post: 'logout', source: `${API}${POST_IMPORT}export const logout = () => withSessionCookiesForPost(1, async () => { const answer = await api.post('/api/auth/logout'); return answer })`, outside: 1, inside: 0 },
  { form: 'the path in a const, posted in the send', post: 'logoutAll', source: `${API}${POST_IMPORT}const ROUTE = '/api/auth/logout-all'\nexport const logoutAll = () => withSessionCookiesForPost(1, () => api.post(ROUTE))`, outside: 1, inside: 0 },
  { form: 'a send declared apart, handed over by name', post: 'logout', source: `${API}${POST_IMPORT}const send = () => api.post('/api/auth/logout')\nexport const logout = () => withSessionCookiesForPost(1, send)`, outside: 1, inside: 0 },
  { form: 'the hold renamed on import', post: 'logout', source: `${API}import { withSessionCookiesForPost as alone } from '@/lib/api/client'\nexport const logout = () => alone(1, () => api.post('/api/auth/logout'))`, outside: 1, inside: 0 },
  { form: 'the hold read off a namespace', post: 'logout', source: `${API}import * as client from '@/lib/api/client'\nexport const logout = () => client.withSessionCookiesForPost(1, () => api.post('/api/auth/logout'))`, outside: 1, inside: 0 },
  { form: 'the hold imported from another module', post: 'logout', source: `${API}import { withSessionCookiesForPost } from '@/lib/locks'\nexport const logout = () => withSessionCookiesForPost(1, () => api.post('/api/auth/logout'))`, outside: 1, inside: 0 },
  { form: 'the hold shadowed by a parameter', post: 'logoutAll', source: `${API}${POST_IMPORT}export const logoutAll = (withSessionCookiesForPost: (ms: number, send: () => unknown) => unknown) => withSessionCookiesForPost(1, () => api.post('/api/auth/logout-all'))`, outside: 1, inside: 0 },
  { form: 'a list of that name elsewhere', post: 'logout', source: "const NO_REFRESH_PATHS = ['/api/auth/logout']", outside: 1, inside: 0 },
  // The password change: its post in a function of its own, called twice (its renewal posts once more), and its path in
  // NO_REFRESH_PATHS.
  { form: "the password change's post in the send of a function of its own", post: 'changePassword', source: `${API}${POST_IMPORT}function postPasswordChange(body: object) {\n  return withSessionCookiesForPost(1, () => api.post('/api/auth/change-password', body))\n}\nexport const changePassword = async () => (await postPasswordChange({})).data`, outside: 0, inside: 1 },
  { form: "lib/api/client.ts's NO_REFRESH_PATHS, the password change's path", post: 'changePassword', file: CLIENT, source: "const NO_REFRESH_PATHS = ['/api/auth/refresh', '/api/auth/change-password']", outside: 0, inside: 0, exempt: 1 },
  { form: 'the password change posted directly, as before its hold', post: 'changePassword', source: `${API}export const changePassword = () => api.post('/api/auth/change-password', {})`, outside: 1, inside: 0 },
  { form: "the password change's renewal posting outside the hold", post: 'changePassword', source: `${API}${POST_IMPORT}export const changePassword = async () => {\n  try { return await withSessionCookiesForPost(1, () => api.post('/api/auth/change-password', {})) } catch { return api.post('/api/auth/change-password', {}) }\n}`, outside: 1, inside: 1 },
  // Look-alikes, which pass.
  { form: 'a longer path that starts with it', post: 'logout', source: `${API}export const history = () => api.get('/api/auth/logout-history')`, outside: 0, inside: 0 },
  { form: 'a longer path that starts with the password change\'s', post: 'changePassword', source: `${API}export const policy = () => api.get('/api/auth/change-password-policy')`, outside: 0, inside: 0 },
  // Out of its reach.
  { form: 'the path assembled at run time', post: 'logout', source: `${API}export const logout = () => api.post('/api/auth/' + 'logout')`, outside: 0, inside: 0, gap: true },
  { form: 'the last segment substituted into a template', post: 'logoutAll', source: `${API}export const logoutAll = () => api.post(\`/api/auth/\${'logout-all'}\`)`, outside: 0, inside: 0, gap: true },
  { form: 'the post behind a local helper that does not return it', post: 'logoutAll', source: `${API}${POST_IMPORT}const fire = async (url: string) => { void api.post(url) }\nexport const logoutAll = () => withSessionCookiesForPost(10, () => fire('/api/auth/logout-all'))`, outside: 0, inside: 1, gap: true },
  { form: 'another request a send makes before its post', post: 'logout', source: `${API}${POST_IMPORT}export const logout = () => withSessionCookiesForPost(1, async () => {\n  await api.get('/api/auth/me')\n  return api.post('/api/auth/logout')\n})`, outside: 0, inside: 1, gap: true },
]

// withoutRefreshBeside in a client that declares the posts' hold (`head`), with each body.
const HOLDS_POST = "function withSessionCookiesForPost<T>(limitMs: number, send: () => Promise<T>) {\n  return navigator.locks.request('session', { mode: 'shared' }, send)\n}\n"
const besideTheLogin = (body: string, head = HOLDS_POST) =>
  `${head}export function withoutRefreshBeside<T>(limitMs: number, send: () => Promise<T>) {\n${body}\n}\n`
const LOGIN_SEND_FORMS: { form: string; source: string; uses: string[]; flag: boolean; gap?: true }[] = [
  { form: "its send handed to the posts' hold", source: besideTheLogin('  const sent = withSessionCookiesForPost(limitMs, send)\n  loginInFlight = sent.then(clear, clear)\n  return sent'), uses: LOGIN_SEND, flag: false },
  { form: "its send once this tab's refresh has settled, as before the lock", source: besideTheLogin('  return refreshSettled(limitMs).then(send)'), uses: ['used otherwise'], flag: true },
  { form: 'its send called beside the hold', source: besideTheLogin('  void withSessionCookiesForPost(limitMs, send)\n  return send()'), uses: ['called', "handed to the posts' hold"], flag: true },
  { form: 'its send wrapped in an arrow', source: besideTheLogin('  return withSessionCookiesForPost(limitMs, () => send())'), uses: ['called'], flag: true },
  { form: 'its send in the first argument', source: besideTheLogin('  return withSessionCookiesForPost(send as never, async () => undefined)'), uses: ['used otherwise'], flag: true },
  { form: "its send under the refresh's hold", source: besideTheLogin('  return withSessionCookiesForRefresh(new AbortController().signal, send)', `function withSessionCookiesForRefresh(signal: AbortSignal, refresh: () => Promise<void>) {\n  return navigator.locks.request('session', { mode: 'exclusive', signal }, refresh)\n}\n`), uses: ['used otherwise'], flag: true },
  { form: "the posts' hold shadowed by a local", source: besideTheLogin('  const withSessionCookiesForPost = (_ms: number, run: () => Promise<T>) => run()\n  return withSessionCookiesForPost(limitMs, send)'), uses: ['used otherwise'], flag: true },
  { form: "the posts' hold imported from another module", source: besideTheLogin('  return withSessionCookiesForPost(limitMs, send)', "import { withSessionCookiesForPost } from './locks'\n"), uses: ['used otherwise'], flag: true },
  { form: 'no withoutRefreshBeside in the client', source: HOLDS_POST, uses: [], flag: true },
  { form: 'withoutRefreshBeside declared as a const', source: `${HOLDS_POST}export const withoutRefreshBeside = <T,>(limitMs: number, send: () => Promise<T>) => withSessionCookiesForPost(limitMs, send)\n`, uses: [], flag: true },
  // Out of its reach.
  { form: "a posts' hold that takes no lock", source: besideTheLogin('  return withSessionCookiesForPost(limitMs, send)', 'function withSessionCookiesForPost<T>(limitMs: number, send: () => Promise<T>) {\n  return refreshSettled(limitMs).then(send)\n}\n'), uses: LOGIN_SEND, flag: false, gap: true },
]

// A client with the refresh's sanctioned sites and its hold (`hold`), and a body for each form.
const HOLDS_REFRESH = "function withSessionCookiesForRefresh(signal: AbortSignal, refresh: () => Promise<void>) {\n  return navigator.locks.request('session', { mode: 'exclusive', signal }, refresh)\n}\n"
const client = (body: string, head = "import { refreshAccessToken } from './refresh'\n", hold = HOLDS_REFRESH) =>
  `${head}const NO_REFRESH_PATHS = ['/api/auth/refresh', '/api/auth/login']\n${hold}${body}`
const ENSURE = 'export function ensureRefreshed() { return withSessionCookiesForRefresh(signal, () => refreshAccessToken(getApiUrl())) }\n'
const ensure = (callback: string) => client(`export function ensureRefreshed() { return withSessionCookiesForRefresh(signal, ${callback}) }\n`)
// The client's sites with the one call in ensureRefreshed outside the refresh's hold.
const UNHELD = ['call of refreshAccessToken in ensureRefreshed', 'import { refreshAccessToken } from lib/api/refresh', 'path in NO_REFRESH_PATHS']
const KEEP_ALIVE = 'features/session/keepAlive.ts'
const REFRESH_TS = "import axios from 'axios'\n"
  + 'export async function refreshAccessToken(baseUrl: string, signal?: AbortSignal): Promise<void> {\n'
  + '  await axios.post(`${baseUrl}/api/auth/refresh`, {}, { withCredentials: true, signal })\n}\n'
const REFRESH_FORMS: { form: string; source: string; file: string; sites: string[]; flag: boolean; gap?: true }[] = [
  { form: "the client: one call, in ensureRefreshed, under the refresh's hold", file: CLIENT, source: client(ENSURE), sites: REFRESH_SITES[CLIENT], flag: false },
  { form: 'refresh.ts posting to its path', file: 'lib/api/refresh.ts', source: "import axios from 'axios'\nexport async function refreshAccessToken(baseUrl: string) { await axios.post(`${baseUrl}/api/auth/refresh`, {}) }", sites: REFRESH_SITES['lib/api/refresh.ts'], flag: false },
  { form: 'a second call in ensureRefreshed', file: CLIENT, source: client('export function ensureRefreshed() { if (gate) return gate.then(() => refreshAccessToken(getApiUrl())); return withSessionCookiesForRefresh(signal, () => refreshAccessToken(getApiUrl())) }'), sites: ['call of refreshAccessToken in ensureRefreshed', ...REFRESH_SITES[CLIENT]], flag: true },
  { form: 'a call outside ensureRefreshed', file: CLIENT, source: client(`${ENSURE}export function keepAlive() { return refreshAccessToken(getApiUrl()) }`), sites: ['call of refreshAccessToken in keepAlive', ...REFRESH_SITES[CLIENT]], flag: true },
  { form: 'handed over as a value', file: CLIENT, source: client(`${ENSURE}setInterval(refreshAccessToken, 60_000)`), sites: [...REFRESH_SITES[CLIENT], 'reference to refreshAccessToken in module'], flag: true },
  { form: 'exported on from the client', file: CLIENT, source: client(`${ENSURE}export { refreshAccessToken }`), sites: [...REFRESH_SITES[CLIENT], 'reference to refreshAccessToken in module'], flag: true },
  { form: 'renamed on import', file: CLIENT, source: client('export function ensureRefreshed() { return withSessionCookiesForRefresh(signal, () => renew(getApiUrl())) }', "import { refreshAccessToken as renew } from './refresh'\n"), sites: ["call of renew in ensureRefreshed under the refresh's hold", 'import { refreshAccessToken as renew } from lib/api/refresh', 'path in NO_REFRESH_PATHS'], flag: true },
  { form: 'a keep-alive module importing it', file: KEEP_ALIVE, source: "import { refreshAccessToken } from '@/lib/api/refresh'\nexport const keepAlive = () => setInterval(() => refreshAccessToken(''), 60_000)", sites: ['call of refreshAccessToken in keepAlive', 'import { refreshAccessToken } from lib/api/refresh'], flag: true },
  { form: 'imported by a relative path from lib/api', file: 'lib/api/keepAlive.ts', source: "import { refreshAccessToken } from './refresh.ts'\nexport const keepAlive = () => refreshAccessToken('')", sites: ['call of refreshAccessToken in keepAlive', 'import { refreshAccessToken } from lib/api/refresh'], flag: true },
  { form: 'a type-only import', file: KEEP_ALIVE, source: "import type { refreshAccessToken } from '@/lib/api/refresh'\nexport type Renew = typeof refreshAccessToken", sites: ['import type { refreshAccessToken } from lib/api/refresh', 'reference to refreshAccessToken in module'], flag: true },
  { form: 'a namespace import', file: KEEP_ALIVE, source: "import * as refresh from '@/lib/api/refresh'\nexport const keepAlive = () => refresh.refreshAccessToken('')", sites: ['import * as refresh from lib/api/refresh'], flag: true },
  { form: 'a re-export', file: 'lib/api/index.ts', source: "export { refreshAccessToken } from './refresh'", sites: ['export { refreshAccessToken } from lib/api/refresh'], flag: true },
  { form: 'a re-export of everything', file: 'lib/api/index.ts', source: "export * from './refresh'", sites: ['export * from lib/api/refresh'], flag: true },
  { form: 'a dynamic import', file: KEEP_ALIVE, source: "export const keepAlive = () => import('@/lib/api/refresh').then((m) => m.refreshAccessToken(''))", sites: ['dynamic import of lib/api/refresh'], flag: true },
  { form: 'a require', file: 'scripts/keepAlive.cjs', source: "const { refreshAccessToken } = require('../lib/api/refresh')\nrefreshAccessToken('')", sites: ['require of lib/api/refresh'], flag: true },
  { form: 'its own post to the path', file: KEEP_ALIVE, source: "import axios from 'axios'\nexport const keepAlive = (base: string) => axios.post(`${base}/api/auth/refresh`, {}, { withCredentials: true })", sites: ['path in keepAlive'], flag: true },
  { form: 'a fetch to the path', file: KEEP_ALIVE, source: "void fetch('/api/auth/refresh', { method: 'POST', credentials: 'include' })", sites: ['path in module'], flag: true },
  { form: 'the path in a const', file: KEEP_ALIVE, source: "export const REFRESH = '/api/auth/refresh'", sites: ['path in REFRESH'], flag: true },
  { form: 'NO_REFRESH_PATHS elsewhere', file: KEEP_ALIVE, source: "const NO_REFRESH_PATHS = ['/api/auth/refresh']", sites: ['path in NO_REFRESH_PATHS'], flag: true },
  // Each way out of the refresh's hold.
  { form: "the one call in ensureRefreshed, outside the refresh's hold", file: CLIENT, source: client('export function ensureRefreshed() { return refreshAccessToken(getApiUrl()) }\n'), sites: UNHELD, flag: true },
  { form: "under the refresh's hold, but not returned", file: CLIENT, source: ensure('() => { void refreshAccessToken(getApiUrl()); return Promise.resolve() }'), sites: UNHELD, flag: true },
  { form: "beside the promise the hold's callback returns", file: CLIENT, source: ensure('() => (refreshAccessToken(getApiUrl()), Promise.resolve())'), sites: UNHELD, flag: true },
  { form: "awaited in the hold's callback, which returns nothing", file: CLIENT, source: ensure('async () => { await refreshAccessToken(getApiUrl()) }'), sites: UNHELD, flag: true },
  { form: "in a function the hold's callback never calls", file: CLIENT, source: ensure('() => { const later = () => refreshAccessToken(getApiUrl()); void later; return Promise.resolve() }'), sites: ['call of refreshAccessToken in later', ...UNHELD.slice(1)], flag: true },
  { form: 'the callback handed as the first argument', file: CLIENT, source: client('export function ensureRefreshed() { return withSessionCookiesForRefresh((() => refreshAccessToken(getApiUrl())) as never, async () => undefined) }\n'), sites: UNHELD, flag: true },
  { form: "under the posts' hold", file: CLIENT, source: client(`${HOLDS_POST}export function ensureRefreshed() { return withSessionCookiesForPost(1, () => refreshAccessToken(getApiUrl())) }\n`), sites: UNHELD, flag: true },
  { form: "the refresh's hold shadowed by a parameter", file: CLIENT, source: client('export function ensureRefreshed(withSessionCookiesForRefresh: (signal: AbortSignal, run: () => Promise<void>) => Promise<void>) { return withSessionCookiesForRefresh(signal, () => refreshAccessToken(getApiUrl())) }\n'), sites: UNHELD, flag: true },
  { form: "the refresh's hold imported from another module", file: CLIENT, source: client(ENSURE, "import { refreshAccessToken } from './refresh'\nimport { withSessionCookiesForRefresh } from './locks'\n", ''), sites: UNHELD, flag: true },
  // Look-alikes, which pass.
  { form: 'a longer path that starts with it', file: KEEP_ALIVE, source: "export const STATUS = '/api/auth/refresh-status'", sites: [], flag: false },
  { form: 'another module named refresh', file: KEEP_ALIVE, source: "import { refresh } from '@/features/filings/api/refresh'\nexport const go = () => refresh()", sites: [], flag: false },
  { form: 'a local of the same name, not the import', file: KEEP_ALIVE, source: 'const refreshAccessToken = () => undefined\nexport const go = () => refreshAccessToken()', sites: [], flag: false },
  { form: 'the path in a comment', file: KEEP_ALIVE, source: '// a refresh posts to /api/auth/refresh\nexport const x = 1', sites: [], flag: false },
  { form: 'refresh.ts as it stands, its own path and nothing else', file: 'lib/api/refresh.ts', source: REFRESH_TS, sites: ['path in refreshAccessToken'], flag: false },
  { form: 'a keep-alive inside refresh.ts itself', file: 'lib/api/refresh.ts', source: `${REFRESH_TS}if (typeof window !== 'undefined') setInterval(() => void refreshAccessToken(''), 25 * 60_000)\n`, sites: ['call of refreshAccessToken in module', 'path in refreshAccessToken'], flag: true },
  { form: 'imported by an @/ path with a ./ segment', file: KEEP_ALIVE, source: "import { refreshAccessToken } from '@/lib/api/./refresh'\nexport const keepAlive = () => refreshAccessToken('')", sites: ['call of refreshAccessToken in keepAlive', 'import { refreshAccessToken } from lib/api/refresh'], flag: true },
  // Out of its reach.
  { form: 'the path assembled at run time', file: KEEP_ALIVE, source: "export const keepAlive = () => fetch('/api/auth/' + 'refresh', { method: 'POST' })", sites: [], flag: false, gap: true },
  { form: 'a timer inside refreshAccessToken posting its own path again', file: 'lib/api/refresh.ts', source: "import axios from 'axios'\n"
    + 'export async function refreshAccessToken(baseUrl: string): Promise<void> {\n  const url = `${baseUrl}/api/auth/refresh`\n'
    + '  setInterval(() => void axios.post(url, {}, { withCredentials: true }), 25 * 60_000)\n  await axios.post(url, {}, { withCredentials: true })\n}\n',
    sites: ['path in refreshAccessToken'], flag: false, gap: true },
  { form: 'a refresh hold that takes no lock', file: CLIENT, source: client(ENSURE, undefined, 'function withSessionCookiesForRefresh(_signal: AbortSignal, refresh: () => Promise<void>) {\n  return refresh()\n}\n'), sites: REFRESH_SITES[CLIENT], flag: false, gap: true },
]

// The auth API's two logouts under the posts' hold, and the client's two calls beside its declarations of both holds.
// The auth API's password change and identity read, as the planted auth APIs below end.
const REST_OF_AUTH_API = "import { sessionCookiesSettled } from '@/lib/api/client'\n"
  + "function postPasswordChange(body: object) { return withSessionCookiesForPost(1, () => api.post('/api/auth/change-password', body)) }\n"
  + "export const getCurrentUser = async () => { await sessionCookiesSettled(1); return api.get('/api/auth/me') }\n"
const LOGOUTS = `${API}${POST_IMPORT}export const logoutAllSessions = async () => withSessionCookiesForPost(1, async () => api.post('/api/auth/logout-all'))\n`
  + "export const logout = async () => withSessionCookiesForPost(1, async () => api.post('/api/auth/logout'))\n" + REST_OF_AUTH_API
const CLIENT_HOLDS = `${HOLDS_REFRESH}${HOLDS_POST}export function ensureRefreshed() { return withSessionCookiesForRefresh(signal, () => refreshAccessToken(getApiUrl())) }\n`
  + 'export function withoutRefreshBeside<T>(limitMs: number, send: () => Promise<T>) { return withSessionCookiesForPost(limitMs, send) }\n'
const NAMESPACE = "import * as client from '@/lib/api/client'\n"
const HOLD_FORMS: { form: string; source: string; file: string; sites: string[]; flag: boolean; gap?: true }[] = [
  { form: "the auth API's two logouts, its password change and its identity read", file: AUTH_API, source: LOGOUTS, sites: HOLD_SITES[AUTH_API], flag: false },
  { form: "the client's two calls, beside its declarations of both holds", file: CLIENT, source: CLIENT_HOLDS, sites: HOLD_SITES[CLIENT], flag: false },
  // Another request under the lock, or a hold taken around one.
  { form: "another caller: a profile update under the posts' hold", file: AUTH_API, source: `${LOGOUTS}export const updateProfile = () => withSessionCookiesForPost(1, () => api.patch('/api/users/me', {}))\n`, sites: [...HOLD_SITES[AUTH_API], `call of ${POST_HOLD} in updateProfile`], flag: true },
  { form: "the identity read's wait in another reader", file: AUTH_API, source: `${LOGOUTS}export const getConnections = async () => { await sessionCookiesSettled(1); return api.get('/api/auth/connections') }\n`, sites: [...HOLD_SITES[AUTH_API], `call of ${SETTLED} in getConnections`], flag: true },
  { form: "the identity read's wait in a logout's send, which a refresh queued behind that hold would keep waiting", file: AUTH_API, source: LOGOUTS.replace("async () => api.post('/api/auth/logout'))", "async () => { await sessionCookiesSettled(1); return api.post('/api/auth/logout') })"), sites: [...HOLD_SITES[AUTH_API], `call of ${SETTLED} in logout`], flag: true },
  { form: 'a caller in another module', file: 'features/fixture.ts', source: `${API}${POST_IMPORT}export const rename = () => withSessionCookiesForPost(1, () => api.patch('/api/users/me', {}))\n`, sites: [`call of ${POST_HOLD} in rename`], flag: true },
  { form: "a second caller of the refresh's hold", file: CLIENT, source: `${CLIENT_HOLDS}export function keepAlive() { return withSessionCookiesForRefresh(signal, () => api.get('/api/auth/me')) }\n`, sites: [...HOLD_SITES[CLIENT], `call of ${REFRESH_HOLD} in keepAlive`], flag: true },
  { form: 'the hold renamed on import', file: 'features/fixture.ts', source: "import { withSessionCookiesForPost as alone } from '@/lib/api/client'\nexport const go = () => alone(1, async () => undefined)\n", sites: [`renamed import of ${POST_HOLD}`], flag: true },
  { form: 'another name imported as the hold', file: 'features/fixture.ts', source: "import { withoutRefreshBeside as withSessionCookiesForPost } from '@/lib/api/client'\nexport const go = () => withSessionCookiesForPost(1, async () => undefined)\n", sites: [`call of ${POST_HOLD} in go`, `renamed import of ${POST_HOLD}`], flag: true },
  { form: 'read off a namespace', file: 'features/fixture.ts', source: `${NAMESPACE}export const go = () => client.withSessionCookiesForPost(1, async () => undefined)\n`, sites: [`call of ${POST_HOLD} in go`], flag: true },
  { form: 'handed on as a value', file: 'features/fixture.ts', source: `${POST_IMPORT}export const hold = withSessionCookiesForPost\n`, sites: [`reference to ${POST_HOLD} in hold`], flag: true },
  { form: 're-exported', file: 'lib/api/index.ts', source: "export { withSessionCookiesForPost } from './client'\n", sites: [`export of ${POST_HOLD}`], flag: true },
  { form: 'its name as a string key', file: 'features/fixture.ts', source: `${NAMESPACE}export const go = () => client['withSessionCookiesForPost'](1, async () => undefined)\n`, sites: [`string ${POST_HOLD} in go`], flag: true },
  { form: 'declared again in another module', file: 'features/fixture.ts', source: 'export function withSessionCookiesForRefresh() { return undefined }\n', sites: [`declaration of ${REFRESH_HOLD}`], flag: true },
  // Out of its reach.
  { form: 'a call site passing its own limit, longer than the refresh\'s bound allows for', file: AUTH_API, source: `${API}${POST_IMPORT}export const logoutAllSessions = async () => withSessionCookiesForPost(LOGOUT_REFRESH_WAIT_MS, async () => api.post('/api/auth/logout-all'))\n`
    + "export const logout = async () => withSessionCookiesForPost(60_000, async () => api.post('/api/auth/logout'))\n" + REST_OF_AUTH_API, sites: HOLD_SITES[AUTH_API], flag: false, gap: true },
  { form: 'one request given its own timeout, longer than the refresh\'s bound allows for', file: AUTH_API, source: `${API}${POST_IMPORT}export const logoutAllSessions = async () => withSessionCookiesForPost(LOGOUT_REFRESH_WAIT_MS, async () => api.post('/api/auth/logout-all', undefined, { timeout: 120_000 }))\n`
    + "export const logout = async () => withSessionCookiesForPost(LOGOUT_REFRESH_WAIT_MS, async () => api.post('/api/auth/logout'))\n" + REST_OF_AUTH_API, sites: HOLD_SITES[AUTH_API], flag: false, gap: true },
  { form: "the hold's name assembled at run time", file: 'features/fixture.ts', source: `${NAMESPACE}export const go = () => (client as unknown as Record<string, (ms: number, send: () => Promise<void>) => unknown>)['withSessionCookies' + 'ForPost'](1, async () => undefined)\n`, sites: [], flag: false, gap: true },
]

// Where a literal names the identity read's path.
const ME_FORMS: { form: string; source: string; file: string; sites: string[]; flag: boolean; gap?: true }[] = [
  { form: 'the identity read in getCurrentUser, after its wait', file: AUTH_API, source: `${API}import { sessionCookiesSettled } from '@/lib/api/client'\nexport const getCurrentUser = async () => {\n  await sessionCookiesSettled(1)\n  return api.get('/api/auth/me')\n}\n`, sites: ['path in getCurrentUser'], flag: false },
  // A /me read that skips the wait.
  { form: 'a second reader of /me in the auth API', file: AUTH_API, source: `${API}export const getCurrentUser = async () => api.get('/api/auth/me')\nexport const whoAmI = () => api.get('/api/auth/me')\n`, sites: ['path in getCurrentUser', 'path in whoAmI'], flag: true },
  { form: 'a reader in another module', file: 'features/fixture.ts', source: `${API}export const peek = () => api.get('/api/auth/me')\n`, sites: ['path in peek'], flag: true },
  { form: 'a template with a base before the path', file: 'lib/serverApi.ts', source: 'export const me = (base: string) => fetch(`${base}/api/auth/me`)\n', sites: ['path in me'], flag: true },
  { form: 'the path in a const outside getCurrentUser', file: AUTH_API, source: `${API}const ME = '/api/auth/me'\nexport const getCurrentUser = async () => api.get(ME)\n`, sites: ['path in ME'], flag: true },
  // Look-alikes, which pass.
  { form: 'a longer path that starts with it', file: 'features/fixture.ts', source: `${API}export const settings = () => api.get('/api/auth/me-settings')\n`, sites: [], flag: false },
  // Out of its reach.
  { form: 'the wait not awaited before the read', file: AUTH_API, source: `${API}import { sessionCookiesSettled } from '@/lib/api/client'\nexport const getCurrentUser = async () => {\n  void sessionCookiesSettled(1)\n  return api.get('/api/auth/me')\n}\n`, sites: ['path in getCurrentUser'], flag: false, gap: true },
  { form: 'the path assembled at run time', file: 'features/fixture.ts', source: `${API}export const peek = () => api.get('/api/auth/' + 'me')\n`, sites: [], flag: false, gap: true },
]

type Counts = { outside: number; inside: number; exempt: number }
const NONE: Counts = { outside: 0, inside: 0, exempt: 0 }
const countsOf = (reading: Reading): Record<HeldPost, Counts> => Object.fromEntries(HELD.map((post) =>
  [post, { outside: reading.posts[post].outside.length, inside: reading.posts[post].inside, exempt: reading.posts[post].exempt }])) as Record<HeldPost, Counts>
const NOWHERE: Record<HeldPost, Counts> = { login: NONE, logout: NONE, logoutAll: NONE, changePassword: NONE }

describe("both ends of the hold stay in the client: each post in its helper's send, the login's handed on to the posts' hold, and the refresh in ensureRefreshed under its own", () => {
  it('scores each planted form', () => {
    const postScores = [
      ...LOGIN_FORMS.map(({ form, source, file = 'features/fixture.ts', outside, inside, exempt = 0 }) =>
        ({ form, expected: { ...NOWHERE, login: { outside, inside, exempt } }, got: countsOf(read(source, file)) })),
      ...LOGOUT_FORMS.map(({ form, post, source, file = 'features/fixture.ts', outside, inside, exempt = 0 }) =>
        ({ form, expected: { ...NOWHERE, [post]: { outside, inside, exempt } }, got: countsOf(read(source, file)) })),
    ]
    expect(postScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
    const sendScores = LOGIN_SEND_FORMS.map(({ form, source, uses, flag }) => {
      const got = read(source, CLIENT).loginSend
      return { form, expected: { uses: [...uses].sort(), flag }, got: { uses: got, flag: JSON.stringify(got) !== JSON.stringify(LOGIN_SEND) } }
    })
    expect(sendScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
    const refreshScores = REFRESH_FORMS.map(({ form, source, file, sites, flag }) => {
      const got = read(source, file).refresh
      const flagged = JSON.stringify(got) !== JSON.stringify([...(REFRESH_SITES[file] ?? [])].sort())
      return { form, expected: { sites: [...sites].sort(), flag }, got: { sites: got, flag: flagged } }
    })
    expect(refreshScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
    const holdScores = HOLD_FORMS.map(({ form, source, file, sites, flag }) => {
      const got = read(source, file).holds
      const flagged = JSON.stringify(got) !== JSON.stringify([...(HOLD_SITES[file] ?? [])].sort())
      return { form, expected: { sites: [...sites].sort(), flag }, got: { sites: got, flag: flagged } }
    })
    expect(holdScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
    const meScores = ME_FORMS.map(({ form, source, file, sites, flag }) => {
      const got = read(source, file).me
      const flagged = JSON.stringify(got) !== JSON.stringify([...(ME_SITES[file] ?? [])].sort())
      return { form, expected: { sites: [...sites].sort(), flag }, got: { sites: got, flag: flagged } }
    })
    expect(meScores.filter(({ expected, got }) => JSON.stringify(expected) !== JSON.stringify(got))).toEqual([])
  })

  it("finds no other in the tree, and reads each post's own send, the login's hand-off and the refresh's sites where they are", () => {
    const listed = execFileSync('git', ['ls-files', '-z'], { cwd: FRONTEND, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 }).split('\0').filter(Boolean)
    const files = listed.filter((file) => SOURCE.test(file) && !file.startsWith('tests/'))
    // Anchored to the tree: a listing that matched nothing would pass every check below.
    expect(files.length).toBeGreaterThan(300)
    const readings = files.map((file) => ({ file, ...read(readFileSync(path.join(FRONTEND, file), 'utf8'), file) }))
    expect(Object.fromEntries(HELD.map((post) => [post, readings.flatMap(({ file, posts }) => posts[post].outside.map((line) => `${file}:${line}`))])))
      .toEqual({ login: [], logout: [], logoutAll: [], changePassword: [] })
    const where = (count: (placement: Placement) => number) => Object.fromEntries(HELD.map((post) =>
      [post, readings.filter(({ posts }) => count(posts[post]) > 0).map(({ file, posts }) => [file, count(posts[post])])]))
    expect(where(({ inside }) => inside)).toEqual({ login: [[AUTH_API, 1]], logout: [[AUTH_API, 1]], logoutAll: [[AUTH_API, 1]], changePassword: [[AUTH_API, 1]] })
    expect(where(({ exempt }) => exempt)).toEqual({ login: [[CLIENT, 1]], logout: [[CLIENT, 1]], logoutAll: [], changePassword: [[CLIENT, 1]] })
    expect(Object.fromEntries(readings.filter(({ loginSend }) => loginSend.length > 0).map(({ file, loginSend }) => [file, loginSend])))
      .toEqual({ [CLIENT]: LOGIN_SEND })
    expect(Object.fromEntries(readings.filter(({ refresh }) => refresh.length > 0).map(({ file, refresh }) => [file, refresh])))
      .toEqual(Object.fromEntries(Object.entries(REFRESH_SITES).map(([file, sites]) => [file, [...sites].sort()])))
    expect(Object.fromEntries(readings.filter(({ holds }) => holds.length > 0).map(({ file, holds }) => [file, holds])))
      .toEqual(Object.fromEntries(Object.entries(HOLD_SITES).map(([file, sites]) => [file, [...sites].sort()])))
    expect(Object.fromEntries(readings.filter(({ me }) => me.length > 0).map(({ file, me }) => [file, me])))
      .toEqual(Object.fromEntries(Object.entries(ME_SITES).map(([file, sites]) => [file, [...sites].sort()])))
  })

  it("holds under the posts' hold only posts whose own 401 asks for no refresh, which would wait for the lock its caller holds", () => {
    expect(Object.fromEntries(HELD.map((post) => [post, isRefreshableRequest(HELD_POSTS[post].route)])))
      .toEqual({ login: false, logout: false, logoutAll: false, changePassword: false })
  })
})
