import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { CanceledError, type InternalAxiosRequestConfig } from 'axios'

/**
 * E29 (4) and E133, across tabs. The session cookies belong to the browser, not the tab: a silent refresh's answer sets
 * them again for the session it was sent with, a password login's sets the new account's, and a logout's clears them.
 * So a refresh one tab sent before another tab's login that answers after it puts the previous account's cookies over
 * the login's (the browser is that account while the tab shows the new one), and one that answers after another tab's
 * logout signs the browser in again. Every silent refresh holds the session cookies' Web Lock shared, and a login, a
 * logout and a logout of every session hold it exclusive around their post (lib/api/client.ts,
 * withSessionCookiesExclusive), within the one wait each already had: each waits for every tab's refresh in flight, and
 * every tab's next refresh waits for its answer, then goes out with the cookies then current. At the limit it posts
 * without the lock, and a refresh still unanswered can then answer after it: no tab can cancel another's.
 *
 * Two tabs are two module graphs of the real client, auth API and session (a module reset and a dynamic import each,
 * each with its own refresh stub), sharing what a browser shares: a lock manager (FakeLockManager), localStorage (the
 * session marker) and the session cookies, modelled for two accounts as loginWaitsForRefresh.spec.ts models them: a
 * request carries the cookies of the moment it is sent, a refresh's answer sets again the session it was sent with, a
 * login that took sets Y's, and a logout's answer clears them. X is the account signed in before; its access token has
 * expired. jsdom has no lock manager of its own, so every other spec runs each tab alone, as an older browser does.
 */

type LockMode = 'shared' | 'exclusive'
interface Waiting { mode: LockMode; grant: () => void }

/**
 * A LockManager with the Web Locks semantics the client relies on, for each name: requests are granted in the order
 * they are made, a shared one while no exclusive lock is held, an exclusive one while no lock is held, and none ahead of
 * a request queued before it, so a later shared request waits behind a waiting exclusive one. The callback runs once
 * granted, never in the request's own turn, and the lock is held until what it returns settles; the request's promise
 * settles with that outcome only once the lock is released. A request whose signal aborts while it waits leaves the
 * queue and rejects with the signal's reason, its callback never run; one made with an aborted signal rejects at once.
 * A browser grants a lock in a later task, here a microtask: nothing in the client relies on how soon.
 */
class FakeLockManager {
  private readonly held = new Map<string, LockMode[]>()
  private readonly queued = new Map<string, Waiting[]>()

  request(name: string, options: { mode?: LockMode; signal?: AbortSignal }, callback: () => unknown): Promise<unknown> {
    const { mode = 'exclusive', signal } = options
    if (signal?.aborted) return Promise.reject(signal.reason)
    const queue = this.listOf(this.queued, name)
    const held = this.listOf(this.held, name)
    return new Promise((resolve, reject) => {
      const abort = () => {
        queue.splice(queue.indexOf(waiting), 1)
        reject(signal?.reason)
        this.grant(name)
      }
      const waiting: Waiting = {
        mode,
        grant: () => {
          signal?.removeEventListener('abort', abort)
          held.push(mode)
          queueMicrotask(() => {
            const release = () => {
              held.splice(held.indexOf(mode), 1)
              this.grant(name)
            }
            new Promise((settle) => settle(callback())).then(
              (value) => { release(); resolve(value) },
              (error: unknown) => { release(); reject(error) },
            )
          })
        },
      }
      signal?.addEventListener('abort', abort, { once: true })
      queue.push(waiting)
      this.grant(name)
    })
  }

  /** Whether no lock is held or waited for: every lock a case took was released. */
  idle(): boolean {
    return [...this.held.values(), ...this.queued.values()].every((list) => list.length === 0)
  }

  /** Grants, in order, each request at the head of the queue that can be granted now. */
  private grant(name: string): void {
    const queue = this.listOf(this.queued, name)
    const held = this.listOf(this.held, name)
    while (queue.length > 0 && (queue[0].mode === 'exclusive' ? held.length === 0 : !held.includes('exclusive'))) {
      queue.shift()?.grant()
    }
  }

  private listOf<T>(lists: Map<string, T[]>, name: string): T[] {
    const list = lists.get(name) ?? []
    lists.set(name, list)
    return list
  }
}

type Account = 'X' | 'Y'
type TabName = 'A' | 'B'
/** What the tabs share: the browser's session cookies (whose session, none once a logout clears them, and whether its
 * access token is still good), what reached the server, in order, from which tab and as whom, and the lock manager. */
interface Browser {
  cookies: { session: Account | null; fresh: boolean }
  events: string[]
  locks: FakeLockManager
}
/** One tab: its own module graph of the client, the auth API and the session, its refresh stub, and the answers the
 * case holds for it, each next refresh's and each next login's or logout's in order (none held answers at once). */
interface Tab {
  client: typeof import('@/lib/api/client')
  auth: typeof import('@/features/auth/api/auth-api')
  session: typeof import('@/lib/api/session')
  refresh: Mock<(baseUrl: string, signal?: AbortSignal) => Promise<void>>
  refreshAnswers: Promise<void>[]
  postAnswers: Promise<void>[]
}

const EMAIL = 'y@example.test'
const PASSWORD = 'test-only-password'
const POSTS = ['/api/auth/login', '/api/auth/logout', '/api/auth/logout-all']
// Every answer a case holds, let go after it, so that nothing a case left waiting runs into the next.
const held: (() => void)[] = []
let browser: Browser
let tabA: Tab
let tabB: Tab

function hold() {
  let resolve!: () => void
  const promise = new Promise<void>((yes) => { resolve = yes })
  held.push(resolve)
  return { promise, resolve }
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
const ok = (config: InternalAxiosRequestConfig, data: unknown) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const unauthorized = (config: InternalAxiosRequestConfig) => Object.assign(new Error('Request failed with status code 401'), {
  config, isAxiosError: true, response: { status: 401, statusText: 'Unauthorized', data: { detail: 'Token expired' }, headers: {}, config },
})
const withoutLocks = () => { delete (navigator as { locks?: unknown }).locks }

/** A tab of `shared`: a fresh module graph, whose refresh and requests reach the server modelled above. */
async function openTab(name: TabName, shared: Browser): Promise<Tab> {
  const refresh = vi.fn<(baseUrl: string, signal?: AbortSignal) => Promise<void>>()
  vi.resetModules()
  vi.doMock('@/lib/api/refresh', () => ({ refreshAccessToken: refresh }))
  const tab: Tab = {
    client: await import('@/lib/api/client'),
    auth: await import('@/features/auth/api/auth-api'),
    session: await import('@/lib/api/session'),
    refresh,
    refreshAnswers: [],
    postAnswers: [],
  }
  // Sent with the cookies of the moment, it answers when the case lets it, setting that session's again, fresh; sent
  // with none, it is refused. Cancelled first, it fails, and its answer is dropped, as the browser drops one.
  refresh.mockImplementation((_url, signal) => {
    const sentWith = shared.cookies.session
    shared.events.push(`${name}'s refresh sent with ${sentWith ?? 'no session'}`)
    const answer = tab.refreshAnswers.shift() ?? Promise.resolve()
    return new Promise<void>((resolve, reject) => {
      signal?.addEventListener('abort', () => reject(new CanceledError()))
      void answer.then(() => {
        if (signal?.aborted) return
        if (sentWith === null) {
          shared.events.push(`${name}'s refresh refused`)
          reject(Object.assign(new Error('Request failed with status code 401'), { response: { status: 401 } }))
          return
        }
        shared.cookies = { session: sentWith, fresh: true }
        shared.events.push(`${name}'s refresh answered for ${sentWith}`)
        resolve()
      })
    })
  })
  tab.client.default.defaults.adapter = async (config) => {
    const url = config.url ?? ''
    shared.events.push(`${name} ${POSTS.includes(url) ? 'posts' : 'reads'} ${url} as ${shared.cookies.session ?? 'no session'}`)
    if (POSTS.includes(url)) {
      await (tab.postAnswers.shift() ?? Promise.resolve())
      shared.cookies = url === '/api/auth/login' ? { session: 'Y', fresh: true } : { session: null, fresh: false }
      shared.events.push(`${name}'s ${url} answered`)
      return ok(config, { ok: true })
    }
    if (!shared.cookies.fresh) throw unauthorized(config)
    return ok(config, { reader: shared.cookies.session })
  }
  return tab
}

beforeEach(async () => {
  window.localStorage.clear()
  browser = { cookies: { session: 'X', fresh: false }, events: [], locks: new FakeLockManager() }
  Object.defineProperty(navigator, 'locks', { value: browser.locks, configurable: true })
  tabA = await openTab('A', browser)
  tabB = await openTab('B', browser)
  // X's session: the marker both tabs read from the storage they share.
  tabA.session.markSessionActive()
})

afterEach(async () => {
  // First, before anything waits: with the session ended, no refresh a case left waiting can start after it.
  window.localStorage.clear()
  vi.useRealTimers()
  for (const letGo of held.splice(0)) letGo()
  await settle()
  withoutLocks()
})

describe('the fake lock manager', () => {
  it('grants as the Web Locks API does: shared beside shared, in order, a later shared behind a waiting exclusive, and an aborted wait gone', async () => {
    const locks = new FakeLockManager()
    const granted: string[] = []
    const holder = (label: string) => {
      const { promise, resolve } = hold()
      return { release: resolve, run: () => { granted.push(label); return promise } }
    }
    const [first, second, exclusive, later] = ['shared 1', 'shared 2', 'exclusive', 'shared 3'].map(holder)
    const aborted = new AbortController()
    const never = vi.fn()
    const requests = [
      locks.request('n', { mode: 'shared' }, first.run),
      locks.request('n', { mode: 'shared' }, second.run),
      locks.request('n', { mode: 'exclusive' }, exclusive.run),
      locks.request('n', { mode: 'shared' }, later.run),
    ]
    const cancelled = locks.request('n', { mode: 'shared', signal: aborted.signal }, never).catch((error: unknown) => error)
    await settle()
    expect(granted).toEqual(['shared 1', 'shared 2'])

    aborted.abort()
    expect(await cancelled).toMatchObject({ name: 'AbortError' })
    first.release()
    await requests[0]
    await settle()
    expect(granted).toEqual(['shared 1', 'shared 2'])
    second.release()
    await requests[1]
    await settle()
    expect(granted).toEqual(['shared 1', 'shared 2', 'exclusive'])
    exclusive.release()
    await requests[2]
    await settle()
    expect(granted).toEqual(['shared 1', 'shared 2', 'exclusive', 'shared 3'])
    later.release()
    await requests[3]
    expect(await locks.request('n', { signal: aborted.signal }, never).catch((error: unknown) => error)).toMatchObject({ name: 'AbortError' })
    expect(never).not.toHaveBeenCalled()
    expect(locks.idle()).toBe(true)
  })
})

describe("a password login in one tab and another tab's silent refresh (E29 (4))", () => {
  it("waits for the refresh another tab has in flight, then posts, and the browser ends on the login's account", async () => {
    const answer = hold()
    tabA.refreshAnswers.push(answer.promise)
    const refreshing = tabA.client.ensureRefreshed()
    await settle()
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    expect(browser.events).toEqual(["A's refresh sent with X"])

    answer.resolve()
    await Promise.all([refreshing, signingIn])
    expect(browser.events).toEqual([
      "A's refresh sent with X", "A's refresh answered for X", 'B posts /api/auth/login as X', "B's /api/auth/login answered",
    ])
    expect(browser.cookies).toEqual({ session: 'Y', fresh: true })
    expect(browser.locks.idle()).toBe(true)
  })

  it('holds a refresh another tab asks for while the login is out, which then goes out with the cookies then current', async () => {
    const loginAnswer = hold()
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    // A read in tab A, whose access token has expired: its 401 asks for a refresh, which waits for the lock.
    const reading = tabA.client.default.get('/api/watchlist/')
    await settle()
    expect(browser.events).toEqual(['B posts /api/auth/login as X', 'A reads /api/watchlist/ as X'])
    expect(tabA.refresh).not.toHaveBeenCalled()

    loginAnswer.resolve()
    await signingIn
    expect(await reading).toMatchObject({ status: 200, data: { reader: 'Y' } })
    expect(browser.events).toEqual([
      'B posts /api/auth/login as X', 'A reads /api/watchlist/ as X', "B's /api/auth/login answered",
      "A's refresh sent with Y", "A's refresh answered for Y", 'A reads /api/watchlist/ as Y',
    ])
    expect(browser.cookies).toEqual({ session: 'Y', fresh: true })
  })

  it('sends nothing for a refresh cancelled while it waits for the lock, and the next one goes out at once', async () => {
    const loginAnswer = hold()
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    const waiting = tabA.client.ensureRefreshed().catch((error: unknown) => error)
    await settle()
    // Its own signal, which a failed logout's read of /me aborts at its limit (cancelRefresh), as refreshSettled's does.
    tabA.client.cancelRefresh()
    expect(await waiting).toMatchObject({ name: 'AbortError' })

    loginAnswer.resolve()
    await signingIn
    await settle()
    expect(tabA.refresh).not.toHaveBeenCalled()
    // The cancelled request left the queue: tab A's next refresh is granted at once.
    await tabA.client.ensureRefreshed()
    expect(browser.events).toEqual([
      'B posts /api/auth/login as X', "B's /api/auth/login answered", "A's refresh sent with Y", "A's refresh answered for Y",
    ])
    expect(browser.locks.idle()).toBe(true)
  })
})

describe.each([
  ['a logout', 'logout', '/api/auth/logout'],
  ['a logout of every session', 'logoutAllSessions', '/api/auth/logout-all'],
] as const)("%s in one tab and another tab's silent refresh (E133)", (_, method, path) => {
  it('waits for the refresh another tab has in flight, then posts, and nothing sets the cookies again after its answer', async () => {
    const answer = hold()
    tabA.refreshAnswers.push(answer.promise)
    const refreshing = tabA.client.ensureRefreshed()
    await settle()
    const loggingOut = tabB.auth[method]()
    await settle()
    expect(browser.events).toEqual(["A's refresh sent with X"])

    answer.resolve()
    await Promise.all([refreshing, loggingOut])
    await settle()
    expect(browser.events).toEqual(["A's refresh sent with X", "A's refresh answered for X", `B posts ${path} as X`, `B's ${path} answered`])
    expect(browser.cookies).toEqual({ session: null, fresh: false })
    expect(browser.locks.idle()).toBe(true)
  })

  it('holds a refresh another tab asks for while its post is out, which then goes out with no session to renew', async () => {
    const postAnswer = hold()
    tabB.postAnswers.push(postAnswer.promise)
    const loggingOut = tabB.auth[method]()
    await settle()
    // Asked for directly: tab A's own 401s start none now, since the logout cleared the marker both tabs read, but the
    // lock holds a refresh whatever asked for it (a tab whose storage is blocked keeps its own flag in memory).
    const refreshing = tabA.client.ensureRefreshed().catch((error: unknown) => error)
    await settle()
    expect(tabA.refresh).not.toHaveBeenCalled()

    postAnswer.resolve()
    await loggingOut
    expect(await refreshing).toMatchObject({ response: { status: 401 } })
    expect(browser.events).toEqual([`B posts ${path} as X`, `B's ${path} answered`, "A's refresh sent with no session", "A's refresh refused"])
    expect(browser.cookies).toEqual({ session: null, fresh: false })
  })

  it('posts nothing for a login accepted in its tab while it waited for the lock: the check shares the post\'s turn', async () => {
    const answer = hold()
    tabA.refreshAnswers.push(answer.promise)
    const refreshing = tabA.client.ensureRefreshed()
    await settle()
    const outcome = tabB.auth[method]().catch((error: unknown) => error)
    await settle()
    // A login completes in tab B and is accepted while it waits: it marks the session and starts a new explicit
    // generation, whose account a post now would sign out.
    tabB.session.markSessionActive()
    tabB.session.advanceSessionGeneration('explicit')
    answer.resolve()
    await refreshing
    if (method === 'logoutAllSessions') expect(await outcome).toBeInstanceOf(tabB.auth.LogoutAllSuperseded)
    else expect(await outcome).toBeUndefined()
    expect(browser.events).toEqual(["A's refresh sent with X", "A's refresh answered for X"])
    expect(tabB.session.hasActiveSession()).toBe(true)
    expect(browser.locks.idle()).toBe(true)
  })
})

const EACH_POST = [
  ['a login', (tab: Tab) => tab.auth.login(EMAIL, PASSWORD), '/api/auth/login', (tab: Tab) => tab.auth.LOGIN_REFRESH_WAIT_MS],
  ['a logout', (tab: Tab) => tab.auth.logout(), '/api/auth/logout', (tab: Tab) => tab.auth.LOGOUT_REFRESH_WAIT_MS],
  ['a logout of every session', (tab: Tab) => tab.auth.logoutAllSessions(), '/api/auth/logout-all', (tab: Tab) => tab.auth.LOGOUT_REFRESH_WAIT_MS],
] as const

describe.each(EACH_POST)('%s, at the limit', (_, post, path, limitOf) => {
  it("posts without the lock once its one wait is spent, its own tab's refresh's share included, while another tab's refresh is unanswered, which can then still answer after it (the gap the code states)", async () => {
    vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })
    const limit = limitOf(tabB)
    const stalled = hold()
    tabA.refreshAnswers.push(stalled.promise)
    const unanswered = tabA.client.ensureRefreshed().catch(() => undefined)
    // Tab B's own refresh answers 4 s in, a share of the one wait.
    tabB.refreshAnswers.push(new Promise((resolve) => setTimeout(resolve, 4_000)))
    const own = tabB.client.ensureRefreshed()
    await vi.advanceTimersByTimeAsync(0)
    const posting = post(tabB)
    await vi.advanceTimersByTimeAsync(4_000)
    await own
    expect(browser.events).toEqual(["A's refresh sent with X", "B's refresh sent with X", "B's refresh answered for X"])

    await vi.advanceTimersByTimeAsync(limit - 4_000 - 1)
    expect(browser.events).toHaveLength(3)
    await vi.advanceTimersByTimeAsync(1)
    await posting
    expect(browser.events.slice(3)).toEqual([`B posts ${path} as X`, `B's ${path} answered`])
    // Tab A's refresh, which no tab can cancel from here, answers after the post's answer and sets X's cookies again:
    // over the login's, or back after a logout.
    stalled.resolve()
    await unanswered
    expect(browser.events.at(-1)).toBe("A's refresh answered for X")
    expect(browser.cookies).toEqual({ session: 'X', fresh: true })
  })
})

describe('with no navigator.locks (an older browser, a non-secure context)', () => {
  it.each(EACH_POST)("%s posts as one tab did: once its own tab's refresh has answered, never waiting for another tab's", async (_, post, path) => {
    withoutLocks()
    const stalled = hold()
    tabA.refreshAnswers.push(stalled.promise)
    const unanswered = tabA.client.ensureRefreshed().catch(() => undefined)
    const own = hold()
    tabB.refreshAnswers.push(own.promise)
    const ownRefresh = tabB.client.ensureRefreshed()
    await settle()
    const posting = post(tabB)
    await settle()
    expect(browser.events).toEqual(["A's refresh sent with X", "B's refresh sent with X"])

    own.resolve()
    await ownRefresh
    await posting
    expect(browser.events).toEqual([
      "A's refresh sent with X", "B's refresh sent with X", "B's refresh answered for X", `B posts ${path} as X`, `B's ${path} answered`,
    ])
    stalled.resolve()
    await unanswered
    expect(browser.cookies).toEqual({ session: 'X', fresh: true })
  })
})
