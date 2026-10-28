import { afterEach, beforeEach, describe, expect, it, vi, type Mock } from 'vitest'
import { CanceledError, type InternalAxiosRequestConfig } from 'axios'

/**
 * E29 (4) and E133, across tabs. The session cookies belong to the browser, not the tab: a silent refresh's answer sets
 * them again for the session it was sent with, a password login's sets the new account's, and a logout's clears them.
 * So a refresh one tab sent before another tab's login that answers after it puts the previous account's cookies over
 * the login's (the browser is that account while the tab shows the new one), one that answers after another tab's
 * logout signs the browser in again, and two refreshes sent at once carry the one refresh cookie, so the second
 * presents the token the first rotated away and meets the replay sweep, which ends every session of the account (E96).
 * Each silent refresh holds the session cookies' Web Lock exclusive, and a login, a logout and a logout of every
 * session hold it shared around their post (lib/api/client.ts), requests granted in the order made: refreshes go out
 * one at a time, a post waits for the refreshes queued before it, within the one wait it already had, and the refreshes
 * queued after it wait for its answer, then go out with the cookies then current, while posts in two tabs do not wait
 * for each other, as on main, unless a refresh is queued between them (requests are granted in order). At its limit a
 * post goes out without the lock, and a refresh still unanswered can answer after it: no tab can cancel another's. A
 * refresh waits at most REFRESH_LOCK_WAIT_MS, as long as a post ahead of it can keep it waiting, and goes out without
 * the lock when the browser refuses it.
 *
 * Two tabs (a third where a case says so) are module graphs of the real client, auth API and session (a module reset
 * and a dynamic import each, each with its own refresh stub), sharing what a browser shares: a lock manager
 * (FakeLockManager), localStorage (the session marker) and the session cookies, modelled for two accounts as
 * loginWaitsForRefresh.spec.ts models them: a request carries the cookies of the moment it is sent, a refresh's answer
 * sets again the session it was sent with, a login that took sets Y's, and a logout's answer clears them. The API
 * answers a refresh as it arrives (Browser.server): the live token rotates, one rotated away is a replay that ends
 * every session of its account, and anything else is refused; a logout revokes its session's live token, whichever of
 * its tokens it carries. X is the account signed in before; its access token has expired. jsdom has no lock manager of
 * its own, so every other spec runs each tab alone, as an older browser does.
 */

type LockMode = 'shared' | 'exclusive'
interface LockRequestOptions { mode?: LockMode; signal?: AbortSignal; ifAvailable?: boolean; steal?: boolean }
type LockCallback = (lock: { name: string; mode: LockMode } | null) => unknown
interface Waiting { mode: LockMode; grant: () => void }

/**
 * A LockManager with the Web Locks semantics the client relies on, for each name: requests are granted in the order
 * they are made, a shared one while no exclusive lock is held, an exclusive one while no lock is held, and none ahead
 * of a request queued before it, so a later shared request waits behind a waiting exclusive one and exclusive ones are
 * granted one at a time. The callback runs once granted, never in the request's own turn, and the lock is held until
 * what it returns settles; the request's promise settles with that outcome only once the lock is released. A request
 * whose signal aborts while it waits leaves the queue and rejects with the signal's reason, its callback never run; one
 * made with an aborted signal rejects at once. It refuses, before granting anything, what a browser refuses: a name
 * that starts with '-', steal with ifAvailable or a shared mode, and a signal with steal or ifAvailable
 * (NotSupportedError), and every request while `refusing` is set, as a browser answers an origin whose site data is
 * blocked (SecurityError). ifAvailable calls back with no lock when it cannot be granted at once; steal is not
 * modelled. A browser grants a lock in a later task, here a microtask: nothing in the client relies on how soon.
 */
class FakeLockManager {
  refusing: DOMException | undefined
  private readonly held = new Map<string, LockMode[]>()
  private readonly queued = new Map<string, Waiting[]>()

  request(name: string, ...args: [LockRequestOptions, LockCallback] | [LockCallback]): Promise<unknown> {
    const [options, callback] = args.length === 2 ? args : [{}, args[0]]
    const { mode = 'exclusive', signal, ifAvailable = false, steal = false } = options
    const notSupported = (why: string) => Promise.reject(new DOMException(why, 'NotSupportedError'))
    if (this.refusing) return Promise.reject(this.refusing)
    if (name.startsWith('-')) return notSupported("a lock's name may not start with '-'")
    if (steal && ifAvailable) return notSupported('steal and ifAvailable together')
    if (steal && mode !== 'exclusive') return notSupported('steal with a shared mode')
    if (signal && (steal || ifAvailable)) return notSupported('a signal with steal or ifAvailable')
    if (signal?.aborted) return Promise.reject(signal.reason)
    if (steal) return Promise.reject(new Error('the fake lock manager does not model steal'))
    const queue = this.listOf(this.queued, name)
    const held = this.listOf(this.held, name)
    return new Promise((resolve, reject) => {
      const run = (lock: { name: string; mode: LockMode } | null, release: () => void) => queueMicrotask(() => {
        new Promise((settle) => settle(callback(lock))).then(
          (value) => { release(); resolve(value) },
          (error: unknown) => { release(); reject(error) },
        )
      })
      if (ifAvailable && !(queue.length === 0 && this.grantable(mode, held))) {
        run(null, () => undefined)
        return
      }
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
          run({ name, mode }, () => {
            held.splice(held.indexOf(mode), 1)
            this.grant(name)
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

  private grantable(mode: LockMode, held: LockMode[]): boolean {
    return mode === 'exclusive' ? held.length === 0 : !held.includes('exclusive')
  }

  /** Grants, in order, each request at the head of the queue that can be granted now. */
  private grant(name: string): void {
    const queue = this.listOf(this.queued, name)
    const held = this.listOf(this.held, name)
    while (queue.length > 0 && this.grantable(queue[0].mode, held)) queue.shift()?.grant()
  }

  private listOf<T>(lists: Map<string, T[]>, name: string): T[] {
    const list = lists.get(name) ?? []
    lists.set(name, list)
    return list
  }
}

type Account = 'X' | 'Y'
type TabName = 'A' | 'B' | 'C'
type Outcome = 'took' | 'refused'
/** An account's session as the API holds it: its live refresh token (a serial), and whether a logout revoked it or a
 * replay swept the account's sessions. */
interface ServerSession { tip: number; revoked: boolean; swept: boolean }
/** What the tabs share: the browser's session cookies (whose session, none once a logout clears them, which refresh token,
 * and whether the access token is still good), the API's side of each account's session, what reached the API, in
 * order, from which tab and as whom, and the lock manager. */
interface Browser {
  cookies: { session: Account | null; token: number; fresh: boolean }
  server: Record<Account, ServerSession>
  events: string[]
  locks: FakeLockManager
}
/** One tab: its own module graph of the client, the auth API and the session, its refresh stub, and the answers the
 * case holds for it, each next refresh's and each next login's or logout's in order (none held answers at once, a post
 * as one that took). */
interface Tab {
  client: typeof import('@/lib/api/client')
  auth: typeof import('@/features/auth/api/auth-api')
  session: typeof import('@/lib/api/session')
  refresh: Mock<(baseUrl: string, signal?: AbortSignal) => Promise<void>>
  refreshAnswers: Promise<void>[]
  postAnswers: Promise<Outcome>[]
}

const EMAIL = 'y@example.test'
const PASSWORD = 'test-only-password'
const POSTS = ['/api/auth/login', '/api/auth/logout', '/api/auth/logout-all']
// Every answer a case holds, let go after it, so that nothing a case left waiting runs into the next.
const held: (() => void)[] = []
let browser: Browser
let tabA: Tab
let tabB: Tab

function hold<T = void>(fallback?: T) {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((yes) => { resolve = yes })
  held.push(() => resolve(fallback as T))
  return { promise, resolve }
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0))
const ok = (config: InternalAxiosRequestConfig, data: unknown) => ({ data, status: 200, statusText: 'OK', headers: {}, config })
const unauthorized = (config: InternalAxiosRequestConfig, detail: string) => Object.assign(new Error('Request failed with status code 401'), {
  config, isAxiosError: true, response: { status: 401, statusText: 'Unauthorized', data: { detail }, headers: {}, config },
})
const withoutLocks = () => { delete (navigator as { locks?: unknown }).locks }
const fakeTimers = () => vi.useFakeTimers({ toFake: ['setTimeout', 'clearTimeout'] })

/** A tab of `shared`: a fresh module graph, whose refresh and requests reach the API modelled above. */
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
  // Sent with the cookies of the moment (axios sends none for a cancelled request), it reaches the API at once, which
  // rotates a live token, sweeps the account's sessions on one rotated away (E96) and refuses anything else; its answer
  // comes when the case lets it, setting the rotated session's cookies, fresh. Cancelled first, its answer is dropped.
  refresh.mockImplementation((_url, signal) => {
    if (signal?.aborted) return Promise.reject(new CanceledError())
    const { session, token } = shared.cookies
    shared.events.push(`${name}'s refresh sent with ${session ?? 'no session'}`)
    const account = session ? shared.server[session] : undefined
    let rotated: number | undefined
    if (account && token < account.tip) {
      Object.assign(account, { revoked: true, swept: true })
      shared.events.push(`${name}'s refresh replays ${session}'s rotated token, and every session of ${session} ends`)
    } else if (account && token === account.tip && !account.revoked) {
      account.tip += 1
      rotated = account.tip
    }
    const answer = tab.refreshAnswers.shift() ?? Promise.resolve()
    return new Promise<void>((resolve, reject) => {
      signal?.addEventListener('abort', () => reject(new CanceledError()))
      void answer.then(() => {
        if (signal?.aborted) return
        if (session === null || rotated === undefined) {
          shared.events.push(`${name}'s refresh refused`)
          reject(Object.assign(new Error('Request failed with status code 401'), { response: { status: 401 } }))
          return
        }
        shared.cookies = { session, token: rotated, fresh: true }
        shared.events.push(`${name}'s refresh answered for ${session}`)
        resolve()
      })
    })
  })
  tab.client.default.defaults.adapter = async (config) => {
    const url = config.url ?? ''
    const { session } = shared.cookies
    if (POSTS.includes(url)) {
      shared.events.push(`${name} posts ${url} as ${session ?? 'no session'}`)
      // A logout reaches the API as it is sent, and revokes its session's live token, whichever of its tokens it carries.
      if (url !== '/api/auth/login' && session) shared.server[session].revoked = true
      if ((await (tab.postAnswers.shift() ?? 'took')) === 'refused') {
        shared.events.push(`${name}'s ${url} refused`)
        throw unauthorized(config, 'Incorrect email or password')
      }
      if (url === '/api/auth/login') {
        const tip = shared.server.Y.tip + 1
        shared.server.Y = { tip, revoked: false, swept: false }
        shared.cookies = { session: 'Y', token: tip, fresh: true }
      } else {
        shared.cookies = { session: null, token: 0, fresh: false }
      }
      shared.events.push(`${name}'s ${url} answered`)
      return ok(config, { ok: true })
    }
    shared.events.push(`${name} reads ${url} as ${session ?? 'no session'}`)
    if (!shared.cookies.fresh) throw unauthorized(config, 'Token expired')
    return ok(config, { reader: shared.cookies.session })
  }
  return tab
}

beforeEach(async () => {
  window.localStorage.clear()
  browser = {
    cookies: { session: 'X', token: 1, fresh: false },
    server: { X: { tip: 1, revoked: false, swept: false }, Y: { tip: 0, revoked: false, swept: false } },
    events: [],
    locks: new FakeLockManager(),
  }
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
  it('grants as the Web Locks API does: shared beside shared, in order, a later shared behind a waiting exclusive, exclusive ones one at a time, and an aborted wait gone', async () => {
    const locks = new FakeLockManager()
    const granted: string[] = []
    const holder = (label: string) => {
      const { promise, resolve } = hold()
      return { release: resolve, run: () => { granted.push(label); return promise } }
    }
    const [first, second, exclusive, later, last] = ['shared 1', 'shared 2', 'exclusive 1', 'shared 3', 'exclusive 2'].map(holder)
    const aborted = new AbortController()
    const never = vi.fn()
    const requests = [
      locks.request('n', { mode: 'shared' }, first.run),
      locks.request('n', { mode: 'shared' }, second.run),
      locks.request('n', { mode: 'exclusive' }, exclusive.run),
      locks.request('n', { mode: 'shared' }, later.run),
      locks.request('n', { mode: 'exclusive' }, last.run),
    ]
    const cancelled = locks.request('n', { mode: 'shared', signal: aborted.signal }, never).catch((error: unknown) => error)
    await settle()
    expect(granted).toEqual(['shared 1', 'shared 2'])

    aborted.abort()
    expect(await cancelled).toMatchObject({ name: 'AbortError' })
    const steps: [{ release: () => void }, string[]][] = [
      [first, ['shared 1', 'shared 2']],
      [second, ['shared 1', 'shared 2', 'exclusive 1']],
      [exclusive, ['shared 1', 'shared 2', 'exclusive 1', 'shared 3']],
      [later, ['shared 1', 'shared 2', 'exclusive 1', 'shared 3', 'exclusive 2']],
    ]
    for (const [[step, expected], request] of steps.map((entry, index) => [entry, requests[index]] as const)) {
      step.release()
      await request
      await settle()
      expect(granted).toEqual(expected)
    }
    last.release()
    await requests[4]
    expect(await locks.request('n', { signal: aborted.signal }, never).catch((error: unknown) => error)).toMatchObject({ name: 'AbortError' })
    expect(never).not.toHaveBeenCalled()
    expect(locks.idle()).toBe(true)
  })

  it('refuses what a browser refuses, before granting anything', async () => {
    const locks = new FakeLockManager()
    const never = vi.fn()
    const { signal } = new AbortController()
    const nameOf = (request: Promise<unknown>) => request.then(() => 'granted', (error: unknown) => (error as DOMException).name)
    expect(await Promise.all([
      locks.request('-reserved', {}, never),
      locks.request('n', { steal: true, ifAvailable: true }, never),
      locks.request('n', { steal: true, mode: 'shared' }, never),
      locks.request('n', { ifAvailable: true, signal }, never),
      locks.request('n', { steal: true, signal }, never),
    ].map(nameOf))).toEqual(Array(5).fill('NotSupportedError'))
    locks.refusing = new DOMException('Site data is blocked for this origin.', 'SecurityError')
    expect(await nameOf(locks.request('n', { mode: 'exclusive' }, never))).toBe('SecurityError')
    await settle()
    expect(never).not.toHaveBeenCalled()
    expect(locks.idle()).toBe(true)
  })
})

describe("silent refreshes across tabs: one at a time (E96's two-tab trigger)", () => {
  it("sends two tabs' refreshes asked for together one at a time, the second with the cookies the first set", async () => {
    const first = hold()
    tabA.refreshAnswers.push(first.promise)
    const refreshing = [tabA.client.ensureRefreshed(), tabB.client.ensureRefreshed()]
    await settle()
    expect(browser.events).toEqual(["A's refresh sent with X"])

    first.resolve()
    await Promise.all(refreshing)
    expect(browser.events).toEqual(["A's refresh sent with X", "A's refresh answered for X", "B's refresh sent with X", "B's refresh answered for X"])
    // Each presented the live token: no replay, no sweep.
    expect(browser.server.X).toEqual({ tip: 3, revoked: false, swept: false })
    expect(browser.locks.idle()).toBe(true)
  })

  it("sends a refresh at once without the lock when the browser refuses it, as it does a login's post, and leaves no wait's timer behind", async () => {
    fakeTimers()
    browser.locks.refusing = new DOMException('Site data is blocked for this origin.', 'SecurityError')
    await tabA.client.ensureRefreshed()
    expect(browser.events).toEqual(["A's refresh sent with X", "A's refresh answered for X"])

    await tabB.auth.login(EMAIL, PASSWORD)
    expect(browser.events.slice(2)).toEqual(['B posts /api/auth/login as X', "B's /api/auth/login answered"])
    expect(vi.getTimerCount()).toBe(0)
  })

  it('holds a refresh asked for while posts are out in two tabs until both have answered, then sends it alone with the cookies then current', async () => {
    const tabC = await openTab('C', browser)
    const loginAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    const logoutAnswer = hold<Outcome>('took')
    tabA.postAnswers.push(logoutAnswer.promise)
    const loggingOut = tabA.auth.logout()
    await settle()
    const refreshing = tabC.client.ensureRefreshed()
    await settle()
    expect(browser.events).toEqual(['B posts /api/auth/login as X', 'A posts /api/auth/logout as X'])

    logoutAnswer.resolve('took')
    await loggingOut
    await settle()
    // The logout has answered, the login has not: the refresh still waits.
    expect(tabC.refresh).not.toHaveBeenCalled()
    loginAnswer.resolve('took')
    await Promise.all([signingIn, refreshing])
    expect(browser.events).toEqual([
      'B posts /api/auth/login as X', 'A posts /api/auth/logout as X', "A's /api/auth/logout answered",
      "B's /api/auth/login answered", "C's refresh sent with Y", "C's refresh answered for Y",
    ])
    expect(browser.locks.idle()).toBe(true)
  })

  it("bounds a refresh's wait by the longest a post ahead of it can keep it waiting: the post's own wait, then its whole request", () => {
    const { REFRESH_LOCK_WAIT_MS, REQUEST_TIMEOUT_MS } = tabA.client
    // The client's own request timeout is the one `api` sends with.
    expect(tabA.client.default.defaults.timeout).toBe(REQUEST_TIMEOUT_MS)
    expect(REFRESH_LOCK_WAIT_MS).toBeGreaterThanOrEqual(Math.max(tabA.auth.LOGIN_REFRESH_WAIT_MS, tabA.auth.LOGOUT_REFRESH_WAIT_MS) + REQUEST_TIMEOUT_MS)
  })

  it('keeps a refresh queued behind a post that waited most of its budget and then held the lock for most of its request waiting until it answers', async () => {
    const tabC = await openTab('C', browser)
    fakeTimers()
    // Tab A's refresh holds the lock for 9 s, tab B's login waits for it (within its 10 s), then holds the lock until
    // its answer at 38 s, under the client's 30 s request timeout.
    tabA.refreshAnswers.push(new Promise((resolve) => setTimeout(resolve, 9_000)))
    const refreshingA = tabA.client.ensureRefreshed()
    await vi.advanceTimersByTimeAsync(0)
    tabB.postAnswers.push(new Promise((resolve) => setTimeout(() => resolve('took'), 38_000)))
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await vi.advanceTimersByTimeAsync(1_000)
    // Tab C asks for a refresh 1 s in: it is queued behind the login's request, and so waits for the login too.
    const refreshingC = tabC.client.ensureRefreshed()
    await vi.advanceTimersByTimeAsync(9_000)
    await refreshingA
    expect(browser.events).toEqual(["A's refresh sent with X", "A's refresh answered for X", 'B posts /api/auth/login as X'])
    // Past what a 30 s bound would have allowed it: still waiting, so it does not go out beside the login.
    await vi.advanceTimersByTimeAsync(27_500)
    expect(tabC.refresh).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(500)
    await Promise.all([signingIn, refreshingC])
    expect(browser.events.slice(3)).toEqual(["B's /api/auth/login answered", "C's refresh sent with Y", "C's refresh answered for Y"])
  })

  it('sends a refresh still waiting for the lock at REFRESH_LOCK_WAIT_MS without it, which then meets the replay sweep: the trigger the bound leaves (E96)', async () => {
    fakeTimers()
    // Tab A's refresh holds the lock and never answers: its request had no timeout of its own.
    const stalled = hold()
    tabA.refreshAnswers.push(stalled.promise)
    void tabA.client.ensureRefreshed().catch(() => undefined)
    await vi.advanceTimersByTimeAsync(0)
    const waiting = tabB.client.ensureRefreshed().catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(tabB.client.REFRESH_LOCK_WAIT_MS - 1)
    expect(browser.events).toEqual(["A's refresh sent with X"])

    await vi.advanceTimersByTimeAsync(1)
    expect(browser.events).toEqual([
      "A's refresh sent with X", "B's refresh sent with X", "B's refresh replays X's rotated token, and every session of X ends", "B's refresh refused",
    ])
    expect(await waiting).toMatchObject({ response: { status: 401 } })
    expect(browser.server.X.swept).toBe(true)
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
    expect(browser.cookies).toMatchObject({ session: 'Y', fresh: true })
    expect(browser.locks.idle()).toBe(true)
  })

  it('holds a refresh another tab asks for while the login is out, which then goes out with the cookies then current', async () => {
    const loginAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    // A read in tab A, whose access token has expired: its 401 asks for a refresh, which waits for the lock.
    const reading = tabA.client.default.get('/api/watchlist/')
    await settle()
    expect(browser.events).toEqual(['B posts /api/auth/login as X', 'A reads /api/watchlist/ as X'])
    expect(tabA.refresh).not.toHaveBeenCalled()

    loginAnswer.resolve('took')
    await signingIn
    expect(await reading).toMatchObject({ status: 200, data: { reader: 'Y' } })
    expect(browser.events).toEqual([
      'B posts /api/auth/login as X', 'A reads /api/watchlist/ as X', "B's /api/auth/login answered",
      "A's refresh sent with Y", "A's refresh answered for Y", 'A reads /api/watchlist/ as Y',
    ])
    expect(browser.cookies).toMatchObject({ session: 'Y', fresh: true })
  })

  it("sends the refreshes held behind it one at a time, another tab's and its own tab's, each with the cookies the one before set: none presents a rotated token", async () => {
    const loginAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    // Both tabs' access tokens have expired: tab A's 401 asks for a refresh, which waits for the lock, and tab B's for
    // one its own login holds back (loginInFlight).
    const answerA = hold()
    tabA.refreshAnswers.push(answerA.promise)
    const reads = [tabA.client.default.get('/api/watchlist/'), tabB.client.default.get('/api/notifications/')]
    await settle()
    loginAnswer.resolve('took')
    await signingIn
    await settle()
    expect(browser.events.filter((event) => event.includes('refresh'))).toEqual(["A's refresh sent with Y"])
    expect(tabB.refresh).not.toHaveBeenCalled()

    answerA.resolve()
    expect(await Promise.all(reads)).toMatchObject([{ status: 200, data: { reader: 'Y' } }, { status: 200, data: { reader: 'Y' } }])
    expect(browser.events.filter((event) => event.includes('refresh'))).toEqual([
      "A's refresh sent with Y", "A's refresh answered for Y", "B's refresh sent with Y", "B's refresh answered for Y",
    ])
    expect(browser.server.Y).toEqual({ tip: 3, revoked: false, swept: false })
  })

  it('sends nothing for a refresh cancelled while it waits for the lock, and the next one goes out at once', async () => {
    const loginAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    const waiting = tabA.client.ensureRefreshed().catch((error: unknown) => error)
    await settle()
    // Its own signal, which a failed logout's read of /me aborts at its limit (cancelRefresh), as refreshSettled's does.
    tabA.client.cancelRefresh()
    expect(await waiting).toMatchObject({ name: 'AbortError' })

    loginAnswer.resolve('took')
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

  it('posts a login refused under the lock once', async () => {
    tabB.postAnswers.push(Promise.resolve<Outcome>('refused'))
    expect(await tabB.auth.login(EMAIL, PASSWORD).catch((error: unknown) => error)).toMatchObject({ status: 401 })
    await settle()
    expect(browser.events).toEqual(['B posts /api/auth/login as X', "B's /api/auth/login refused"])
    expect(browser.locks.idle()).toBe(true)
  })
})

describe.each([
  ['a logout', 'logout', '/api/auth/logout'],
  ['a logout of every session', 'logoutAllSessions', '/api/auth/logout-all'],
] as const)("%s in one tab and another tab's silent refresh or login (E133, E29 (4))", (_, method, path) => {
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
    expect(browser.cookies).toMatchObject({ session: null, fresh: false })
    expect(browser.locks.idle()).toBe(true)
  })

  it('holds a refresh another tab asks for while its post is out, which then goes out with no session to renew', async () => {
    const postAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(postAnswer.promise)
    const loggingOut = tabB.auth[method]()
    await settle()
    // Asked for directly: tab A's own 401s start none now, since the logout cleared the marker both tabs read, but the
    // lock holds a refresh whatever asked for it (a tab whose storage is blocked keeps its own flag in memory).
    const refreshing = tabA.client.ensureRefreshed().catch((error: unknown) => error)
    await settle()
    expect(tabA.refresh).not.toHaveBeenCalled()

    postAnswer.resolve('took')
    await loggingOut
    expect(await refreshing).toMatchObject({ response: { status: 401 } })
    expect(browser.events).toEqual([`B posts ${path} as X`, `B's ${path} answered`, "A's refresh sent with no session", "A's refresh refused"])
    expect(browser.cookies).toMatchObject({ session: null, fresh: false })
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

  it("posts beside another tab's login, neither waiting for the other: posts hold the lock shared", async () => {
    const loginAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    const postAnswer = hold<Outcome>('took')
    tabA.postAnswers.push(postAnswer.promise)
    const loggingOut = tabA.auth[method]()
    await settle()
    // Both are out at once, each with the cookies of its moment: the reader's own two actions race, as on main.
    expect(browser.events).toEqual(['B posts /api/auth/login as X', `A posts ${path} as X`])

    postAnswer.resolve('took')
    loginAnswer.resolve('took')
    await Promise.all([signingIn, loggingOut])
    expect(browser.locks.idle()).toBe(true)
  })

  it("posts with the cookies of another tab's login when its own tab's refresh, queued behind that login, held it back (the gap the code states)", async () => {
    const loginAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(loginAnswer.promise)
    const signingIn = tabB.auth.login(EMAIL, PASSWORD)
    await settle()
    // Tab A still shows X, whose access token has expired: a read's 401 asks for a refresh, which queues behind the login.
    const reading = tabA.client.default.get('/api/watchlist/').catch((error: unknown) => error)
    await settle()
    // The reader presses Log out in tab A before the login answers: its refreshSettled waits on that refresh.
    const loggingOut = tabA.auth[method]()
    await settle()
    expect(browser.events).toEqual(['B posts /api/auth/login as X', 'A reads /api/watchlist/ as X'])

    loginAnswer.resolve('took')
    await Promise.all([signingIn, loggingOut, reading])
    // The refresh goes out after the login's answer, with its cookies, and the logout after the refresh, with them too:
    // Y's session ends, two tabs being enough.
    expect(browser.events.filter((event) => !event.includes(' reads '))).toEqual([
      'B posts /api/auth/login as X', "B's /api/auth/login answered", "A's refresh sent with Y", "A's refresh answered for Y",
      `A posts ${path} as Y`, `A's ${path} answered`,
    ])
    expect(browser.server.Y.revoked).toBe(true)
  })
})

const EACH_POST = [
  ['a login', (tab: Tab) => tab.auth.login(EMAIL, PASSWORD), '/api/auth/login', (tab: Tab) => tab.auth.LOGIN_REFRESH_WAIT_MS],
  ['a logout', (tab: Tab) => tab.auth.logout(), '/api/auth/logout', (tab: Tab) => tab.auth.LOGOUT_REFRESH_WAIT_MS],
  ['a logout of every session', (tab: Tab) => tab.auth.logoutAllSessions(), '/api/auth/logout-all', (tab: Tab) => tab.auth.LOGOUT_REFRESH_WAIT_MS],
] as const

describe.each(EACH_POST)('%s, at the limit', (_, post, path, limitOf) => {
  it("posts without the lock once its one wait is spent, its own tab's refresh's share included, while another tab's refresh is unanswered, which can then still answer after it (the gap the code states)", async () => {
    fakeTimers()
    const limit = limitOf(tabB)
    // Tab B's own refresh holds the lock first and answers 4 s in, a share of the one wait.
    tabB.refreshAnswers.push(new Promise((resolve) => setTimeout(resolve, 4_000)))
    const own = tabB.client.ensureRefreshed()
    await vi.advanceTimersByTimeAsync(0)
    // Tab A's, queued behind it, then holds the lock and does not answer in time.
    const stalled = hold()
    tabA.refreshAnswers.push(stalled.promise)
    const unanswered = tabA.client.ensureRefreshed().catch(() => undefined)
    const posting = post(tabB)
    await vi.advanceTimersByTimeAsync(4_000)
    await own
    expect(browser.events).toEqual(["B's refresh sent with X", "B's refresh answered for X", "A's refresh sent with X"])

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
    expect(browser.cookies).toMatchObject({ session: 'X', fresh: true })
  })

  it("cancels its own tab's refresh still unanswered at the limit, and posts: that refresh's answer is dropped", async () => {
    fakeTimers()
    const limit = limitOf(tabB)
    const stalled = hold()
    tabB.refreshAnswers.push(stalled.promise)
    const own = tabB.client.ensureRefreshed().catch((error: unknown) => error)
    await vi.advanceTimersByTimeAsync(0)
    const signal = tabB.refresh.mock.calls[0][1] as AbortSignal
    const posting = post(tabB)
    await vi.advanceTimersByTimeAsync(limit - 1)
    expect(signal.aborted).toBe(false)
    expect(browser.events).toEqual(["B's refresh sent with X"])

    await vi.advanceTimersByTimeAsync(1)
    expect(signal.aborted).toBe(true)
    await posting
    // Its answer comes after all, and is dropped: cancelled, it cannot set the cookies again after the post's answer.
    stalled.resolve()
    expect(await own).toBeInstanceOf(CanceledError)
    await vi.advanceTimersByTimeAsync(0)
    expect(browser.events).toEqual(["B's refresh sent with X", `B posts ${path} as X`, `B's ${path} answered`])
  })

  it('lets a refresh queued behind its request go out beside its unlocked post once the lock frees (the gap the code states)', async () => {
    const tabC = await openTab('C', browser)
    fakeTimers()
    const limit = limitOf(tabB)
    const stalled = hold()
    tabA.refreshAnswers.push(stalled.promise)
    const unanswered = tabA.client.ensureRefreshed().catch(() => undefined)
    await vi.advanceTimersByTimeAsync(0)
    const postAnswer = hold<Outcome>('took')
    tabB.postAnswers.push(postAnswer.promise)
    const posting = post(tabB)
    await vi.advanceTimersByTimeAsync(1_000)
    // Tab C asks for a refresh after the post's request: it is queued behind it.
    const queued = tabC.client.ensureRefreshed().catch(() => undefined)
    await vi.advanceTimersByTimeAsync(limit - 1_000)
    expect(browser.events).toEqual(["A's refresh sent with X", `B posts ${path} as X`])

    // The post went out without the lock at the limit and is still out; tab A's refresh answers and frees the lock, and
    // tab C's goes out beside the post.
    stalled.resolve()
    await unanswered
    await vi.advanceTimersByTimeAsync(0)
    postAnswer.resolve('took')
    await Promise.all([posting, queued])
    expect(browser.events.slice(0, 4)).toEqual(["A's refresh sent with X", `B posts ${path} as X`, "A's refresh answered for X", "C's refresh sent with X"])
    expect(browser.events.indexOf("C's refresh sent with X")).toBeLessThan(browser.events.indexOf(`B's ${path} answered`))
  })
})

describe('with no navigator.locks (an older browser, a non-secure context)', () => {
  it.each(EACH_POST)("%s posts at once, never waiting for another tab's refresh, which can then answer after it", async (_, post, path) => {
    withoutLocks()
    const stalled = hold()
    tabA.refreshAnswers.push(stalled.promise)
    const unanswered = tabA.client.ensureRefreshed().catch(() => undefined)
    await settle()
    await post(tabB)
    expect(browser.events).toEqual(["A's refresh sent with X", `B posts ${path} as X`, `B's ${path} answered`])

    stalled.resolve()
    await unanswered
    expect(browser.events.at(-1)).toBe("A's refresh answered for X")
    expect(browser.cookies).toMatchObject({ session: 'X', fresh: true })
  })

  it("sends two tabs' refreshes at once, and the second meets the replay sweep: E96's trigger, without a lock manager", async () => {
    withoutLocks()
    const first = hold()
    tabA.refreshAnswers.push(first.promise)
    const refreshing = [tabA.client.ensureRefreshed(), tabB.client.ensureRefreshed()].map((refresh) => refresh.catch(() => undefined))
    await settle()
    first.resolve()
    await Promise.all(refreshing)
    expect(browser.events).toEqual([
      "A's refresh sent with X", "B's refresh sent with X", "B's refresh replays X's rotated token, and every session of X ends",
      "B's refresh refused", "A's refresh answered for X",
    ])
    expect(browser.server.X.swept).toBe(true)
  })
})

