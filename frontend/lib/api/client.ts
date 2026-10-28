import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'
import { hasActiveSession, getSessionGeneration, isSessionGenerationCurrent, assertSessionGeneration, notifySessionLost } from './session'
import { getErrorStatus } from './types'
import { refreshAccessToken } from './refresh'

// Custom error class that preserves backend error details
export class ApiError extends Error {
  status: number
  detail: string
  isRetryable: boolean
  // Internal classification only: an original access 401 after transient refresh failure
  // is not evidence that the refresh session is gone. HTTP status/detail stay unchanged.
  sessionLossConfirmed?: boolean
  // The backend's own words: set only when the response body carried a readable `detail`, a string or
  // a validation 422's `{ loc, msg, type }` list, whose first `msg` it takes (detailMessage).
  // Undefined when `detail` is this client's status fallback or axios's message ("Request failed
  // with status code N"), so a surface that shows backend text verbatim reads this, never `detail`.
  backendDetail?: string

  constructor(status: number, detail: string) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    // 503 (Service Unavailable), 429 (Rate Limited), and 5xx errors are retryable
    this.isRetryable = status === 503 || status === 429 || (status >= 500 && status < 600)
  }
}

/**
 * The message a backend `detail` carries, as one sentence a person can read. A string detail is the
 * backend's own message. FastAPI's validation 422 sends a list of `{ loc, msg, type }` objects, which
 * used to reach the UI as "[object Object]": its first `msg` stands for it, without the "Value error, "
 * or "Assertion failed, " that pydantic puts before a custom validator's own sentence (a msg that is
 * only the prefix stays as sent). Anything else yields undefined, so the status-based message below
 * applies.
 */
export function detailMessage(detail: unknown): string | undefined {
  if (typeof detail === 'string') return detail || undefined
  const first: unknown = Array.isArray(detail) ? detail[0] : detail
  if (first && typeof first === 'object' && 'msg' in first) {
    const msg = (first as { msg: unknown }).msg
    if (typeof msg === 'string' && msg) return msg.replace(/^(?:Value error|Assertion failed), /, '') || msg
  }
  return undefined
}

// Determine API URL: prefer env var, fallback based on environment
export const getApiUrl = () => {
  // Always use environment variable if set (for production deployments)
  if (typeof process !== 'undefined' && process.env.NEXT_PUBLIC_API_BASE_URL) {
    return process.env.NEXT_PUBLIC_API_BASE_URL
  }
  // For client-side: check window location
  if (typeof window !== 'undefined') {
    const hostname = window.location.hostname
    if (hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '0.0.0.0') {
      return 'http://localhost:8000'
    }
  }
  // For server-side: check NODE_ENV
  if (typeof process !== 'undefined' && process.env.NODE_ENV === 'development') {
    return 'http://localhost:8000'
  }
  // Default to production API
  return 'https://api.earningsnerd.io'
}

// Get the API URL - for client-side this will be determined at runtime
const getBaseUrl = () => {
  if (typeof window !== 'undefined') {
    return getApiUrl()
  }
  // Server-side: use localhost in development
  return process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://api.earningsnerd.io'
}

// How long any request through `api` may take, a login's and a logout's post among them (REFRESH_LOCK_WAIT_MS).
export const REQUEST_TIMEOUT_MS = 30_000

// Create axios instance with baseURL
const api = axios.create({
  baseURL: getBaseUrl(),
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: REQUEST_TIMEOUT_MS,
  withCredentials: true,
})

type SessionRequestConfig = InternalAxiosRequestConfig & { _retry?: boolean; _sessionGeneration?: number; _sessionWasActive?: boolean }

// Set baseURL dynamically on each request (for client-side)
api.interceptors.request.use((config: SessionRequestConfig) => {
  config._sessionGeneration ??= getSessionGeneration()
  config._sessionWasActive ??= hasActiveSession()
  // Always set baseURL dynamically to ensure correct URL in client-side
  if (typeof window !== 'undefined') {
    config.baseURL = getApiUrl()
  }
  return config
})

// Endpoints whose own 401s must never trigger a silent refresh (the refresh itself, plus
// the credential-issuing endpoints — a failed login is not an expired session). The password
// change posts under the session cookies' lock, where a refresh would wait for the lock its own
// post holds, so its 401 is renewed after the hold instead (changePassword in auth-api.ts).
const NO_REFRESH_PATHS = [
  '/api/auth/refresh',
  '/api/auth/login',
  '/api/auth/register',
  '/api/auth/logout',
  '/api/auth/change-password',
]

// Dispatched on a 403 whose detail asks the user to verify their email, so a global
// listener (EmailVerificationModal) can show a graceful prompt instead of a raw error.
export const EMAIL_VERIFICATION_REQUIRED_EVENT = 'email-verification-required'

export function isRefreshableRequest(url?: string): boolean {
  if (!url) return true
  // Match on the path only, so a query param that happens to contain an auth path
  // (e.g. ?redirect=/api/auth/login) doesn't wrongly mark the request non-refreshable.
  const pathname = url.split('?')[0]
  return !NO_REFRESH_PATHS.some((path) => pathname.includes(path))
}

// Single in-flight refresh shared across concurrent 401s, so a burst of requests that all
// expire together triggers exactly one /refresh call rather than a stampede. Exported so the
// sanctioned raw-fetch SSE path (features/summaries/api) shares this ONE promise — otherwise a
// concurrent 401 there + here would fire two /refresh calls on the same single-use rotating
// refresh token, and the loser would 401 and log the user out.
let refreshPromise: Promise<void> | null = null
let refreshGeneration: number | null = null
let refreshAbort: AbortController | null = null
// The password login under way in this tab (withoutRefreshBeside, E29 (4)): settles once its request has answered,
// whatever the answer, and is null when no login is under way.
let loginInFlight: Promise<void> | null = null

// The Web Lock every tab of this origin takes on the session cookies (E29 (4), E133). The cookies belong to the
// browser, not the tab: a silent refresh's answer sets them, a login's sets the new session's and a logout's clears
// them, so a refresh another tab sent before a login answers after it and sets the previous session's cookies over the
// login's, or one answering after a logout signs the browser in again; and two refreshes sent at once carry the one
// refresh cookie, so the second presents the token the first rotated away and meets the replay sweep, which signs the
// account out on every device (E96). Requests for it are granted in the order made. A silent refresh holds it exclusive
// (withSessionCookiesForRefresh): it waits for every refresh and post queued before it, in any tab, and every one
// queued after it waits for it, so refreshes go out one at a time, each with the cookies the one before it set. A
// password login, a logout, a logout of every session and a password change, whose answer mints the session a new
// refresh token, hold it shared around their post (withSessionCookiesForPost): each waits for the refreshes queued
// before it and holds back those queued after it, but posts in two tabs do not wait for each other, as on main, where
// they race as the reader's own actions, unless a refresh is queued between them (requests are granted in order). An
// OAuth sign-in's answer sets the cookies too, but it is a navigation, which cannot hold the lock: the identity read
// (getCurrentUser in auth-api.ts) waits instead for the refreshes queued before it (sessionCookiesSettled), so a tab
// landing from a sign-in reads the account the browser holds once a refresh another tab sent with the previous
// session's cookies has answered. A browser with no lock manager (an older browser, a non-secure context; jsdom) runs
// each tab alone, as before. Locks are per origin: tabs of two origins under the cookie domain (the apex and www) share
// the cookies but no lock, as they share no session marker either.
const SESSION_COOKIES_LOCK = 'earningsnerd-session-cookies'
const sessionCookieLocks = (): LockManager | undefined =>
  (typeof navigator === 'undefined' ? undefined : navigator.locks)

/**
 * How long a silent refresh waits, at most, for the session cookies' lock before it goes out without it: as long as a
 * login's, a logout's or a password change's post queued ahead of it can keep it waiting. Such a post may first wait
 * its own budget for the refreshes before it (LOGIN_REFRESH_WAIT_MS, LOGOUT_REFRESH_WAIT_MS and
 * PASSWORD_CHANGE_REFRESH_WAIT_MS in features/auth/api/auth-api.ts, 10 s each), then hold the lock for its whole
 * request, which `api` times out at REQUEST_TIMEOUT_MS (30 s): 40 s in all, which sessionCookiesAcrossTabs.spec.ts
 * holds against all three. It is exactly their sum, with no slack: at the extreme a refresh queued behind such a post
 * gives up a task before that post's own timeout fires, which is harmless, since the post is timing out. It covers the
 * posts as their call sites make them, each with its wait constant and `api`'s timeout: a call site that passed a
 * longer limit, or gave one request a longer timeout, would fall outside it, which the constants' check does not see
 * (planted as gaps in loginWaitsForRefresh.spec.ts). A shorter bound would send a refresh beside a slow post, the race
 * the lock closes; with none, one hung refresh in another tab (the refresh has no timeout of its own,
 * lib/api/refresh.ts) would stall every tab's for good.
 */
export const REFRESH_LOCK_WAIT_MS = 10_000 + REQUEST_TIMEOUT_MS

/**
 * A silent refresh, holding the session cookies' lock exclusive: it waits for every refresh, login and logout queued
 * for the lock before it, in any tab, then goes out with the cookies the last of them set, and every one queued after
 * it waits for its answer. So of two tabs refreshing at once, the second presents the token the first one's answer set,
 * not the one it rotated away, and E96's replay sweep is not met where the browser has a lock manager. Still waiting,
 * it is cancelled by its own signal (refreshSettled's limit, cancelRefresh) and sends nothing. It goes out without the
 * lock after REFRESH_LOCK_WAIT_MS, or at once when the browser refuses the lock: Chromium and Gecko answer a
 * SecurityError where site data is blocked for the origin (the case session.ts's in-memory flag exists for), while the
 * API's cookies may still flow, and a refresh the refusal failed would renew nothing and log nothing out. Its promise
 * settles only once the lock is released.
 */
function withSessionCookiesForRefresh(signal: AbortSignal, refresh: () => Promise<void>): Promise<void> {
  const locks = sessionCookieLocks()
  if (!locks) return refresh()
  const wait = new AbortController()
  const stopWaiting = () => wait.abort()
  const limit = setTimeout(stopWaiting, REFRESH_LOCK_WAIT_MS)
  signal.addEventListener('abort', stopWaiting)
  let refreshing: Promise<void> | undefined
  // Once the hold has ended: the refresh made under it, or, never granted the lock, nothing when its own signal
  // aborted, else the refresh without it (the wait ran out, or the browser refused the lock).
  const afterTheHold = () => {
    clearTimeout(limit)
    signal.removeEventListener('abort', stopWaiting)
    return refreshing ?? (signal.aborted ? Promise.reject(signal.reason) : refresh())
  }
  return locks.request(SESSION_COOKIES_LOCK, { mode: 'exclusive', signal: wait.signal }, () => {
    clearTimeout(limit)
    refreshing = new Promise<void>((resolve) => resolve(refresh()))
    return refreshing
  }).then(afterTheHold, afterTheHold)
}

/** After a wait that a refresh may not run beside: the caller's account still, and still a session, or no refresh. */
function refreshAfterWaiting(generation: number): Promise<void> {
  assertSessionGeneration(generation)
  // A logout, or a lost session, cleared the flag meanwhile: a refresh started now would set the cookies the
  // logout's answer clears (E133). Callers treat this like the generation abort above.
  if (!hasActiveSession()) throw new DOMException('The session ended while the refresh was pending', 'AbortError')
  return ensureRefreshed()
}

export function ensureRefreshed(): Promise<void> {
  const generation = getSessionGeneration()
  // Wait out an earlier account's refresh, without interpreting its result as this account's
  // result or starting concurrent rotating-cookie refreshes. This does not control Set-Cookie.
  if (refreshPromise && refreshGeneration !== generation) {
    return refreshPromise.catch(() => undefined).then(() => refreshAfterWaiting(generation))
  }
  // A login under way: a refresh sent now carries the previous session's cookies, and one that answers after the login
  // sets them over the new login's, which no generation fence stops (E29 (4)). It waits for the login's answer, then
  // goes out with whatever cookies are current: after a login that failed, the previous session's, which it renews;
  // after one that took, the new session's (one extra rotation), for the gate clears before login() resumes, so it
  // wakes before app/login/page.tsx accepts the login, and the generation that acceptance moves fences its replay.
  if (!refreshPromise && loginInFlight) return loginInFlight.then(() => refreshAfterWaiting(generation))
  if (!refreshPromise) {
    const abort = new AbortController()
    refreshGeneration = generation
    refreshAbort = abort
    refreshPromise = withSessionCookiesForRefresh(abort.signal, () => refreshAccessToken(getApiUrl(), abort.signal))
      .finally(() => {
        refreshPromise = null
        refreshGeneration = null
        if (refreshAbort === abort) refreshAbort = null
      })
  }
  return refreshPromise
}

/**
 * Settles once the refresh in flight, if any, can no longer set the session cookies: once it has answered, whatever
 * its outcome, or, when `limitMs` passes first, once it is cancelled. A logout waits on it before it posts: the
 * refresh's answer sets the session cookies, and one that lands after the logout's answer sets them again, the access
 * token among them, which keeps the tab signed in until that token expires (E133). A refresh still in flight at the
 * limit is aborted, and the browser drops a cancelled request's answer, so it cannot outlast the logout either; one
 * still waiting for the session cookies' lock is aborted too, and sends nothing. A login waits on it too. Both then
 * wait for the refreshes queued for the lock before their own request (withSessionCookiesForPost).
 */
export function refreshSettled(limitMs: number): Promise<void> {
  const inFlight = refreshPromise
  const abort = refreshAbort
  if (!inFlight) return Promise.resolve()
  let timer: ReturnType<typeof setTimeout> | undefined
  const limit = new Promise<'limit'>((resolve) => { timer = setTimeout(() => resolve('limit'), limitMs) })
  return Promise.race([inFlight.then(() => 'answered' as const, () => 'answered' as const), limit])
    .then((outcome) => {
      if (outcome === 'limit') abort?.abort()
    })
    .finally(() => clearTimeout(timer))
}

/**
 * Sends a request whose answer sets or clears the session cookies (a password login, a logout, a logout of every
 * session, a password change) with no silent refresh of any tab beside it (E29 (4), E133). This tab's refresh in flight
 * answers first, or is cancelled at `limitMs` (refreshSettled); then `send` runs holding the session cookies' lock
 * shared, so it waits for the refreshes queued for the lock before its own request, in any tab, one at a time, a
 * refresh another tab asks for while this tab's own settles among them, and those asked for after its request wait for
 * its answer (bounded by REQUEST_TIMEOUT_MS), then go out with whatever cookies are current. Shared, it waits for no
 * other post unless a refresh is queued between them (requests are granted in order, below): a login in one tab and a
 * logout in another post side by side, as on main. The lock wait gets what is left of `limitMs`, not a second one, and
 * at the limit `send` runs without the lock. What this leaves open: at the limit, a refresh another tab has in flight,
 * which cannot be cancelled from here, can answer after `send`'s answer and set the cookies it was sent with, and any
 * refresh still waiting for the lock, queued before this request or after it, may go out beside it. Posts in two tabs
 * wait for each other only through a refresh queued between them, since requests are granted in order: given a login, a
 * refresh asked for while it is out (the logout's own tab's among them, which its refreshSettled waits on), and a
 * logout pressed after that refresh, all within one post's time, the logout posts after the login has answered, with
 * its cookies. A refresh that waited past REFRESH_LOCK_WAIT_MS goes out beside whatever holds the lock; and where the
 * browser has no lock manager, or refuses the lock, `send` runs once this tab's refresh has settled, as before, and any
 * other tab's refresh can answer after it. A check that must share a turn with the request (a logout's explicit
 * generation) goes in `send`, after both waits. `send` must be a request whose own 401 starts no refresh
 * (NO_REFRESH_PATHS): a refresh asked for under the hold would wait for the lock its own caller holds.
 */
export function withSessionCookiesForPost<T>(limitMs: number, send: () => Promise<T>): Promise<T> {
  const locks = sessionCookieLocks()
  if (!locks) return refreshSettled(limitMs).then(send)
  const wait = new AbortController()
  const limit = setTimeout(() => wait.abort(), limitMs)
  return refreshSettled(limitMs).then(() => {
    let sent: Promise<T> | undefined
    // Once the hold has ended: the request made under it, or, never granted the lock (the wait ran out, or the browser
    // refused it), the request without it.
    const afterTheHold = () => {
      clearTimeout(limit)
      return sent ?? send()
    }
    return locks.request(SESSION_COOKIES_LOCK, { mode: 'shared', signal: wait.signal }, () => {
      clearTimeout(limit)
      sent = new Promise<T>((resolve) => resolve(send()))
      return sent
    }).then(afterTheHold, afterTheHold)
  })
}

/**
 * Sends the password login with no silent refresh beside it (E29 (4)). A refresh's answer sets the session cookies, and
 * one sent with the previous session's cookies that answers after the login's sets them over the new login's: the
 * browser is signed in as the previous account while the tab shows the new one. The generation fences stop its replay
 * and its cache writes, not its cookies. So the login goes through withSessionCookiesForPost: this tab's refresh in
 * flight answers first, or is cancelled at `limitMs`, as before a logout, then the refreshes queued for the session
 * cookies' lock before the login's request, in any tab, within what is left of it. From this call until the login's
 * request has answered, a refresh a 401 asks for here waits (ensureRefreshed), as another tab's asked for after the
 * login's request waits on the lock: sent after that answer, it carries whatever cookies are current. The login sets
 * the gate before it waits on anything, and clears it only while it is still its own. Unlike a logout (beginLogout),
 * the session reads as active meanwhile, so a failed login's concurrent 401s renew the previous session rather than
 * lose it. The cancel at the limit is E96's one-tab case, as it is before a logout: the server may already have rotated
 * the refresh it drops, and if the login then fails, the browser keeps the token rotated away, which its next refresh
 * replays. `send` must be a request whose own 401 starts no refresh (NO_REFRESH_PATHS holds /api/auth/login): a refresh
 * it asked for would wait on the login it belongs to, which would never answer, and every later refresh with it. One
 * login at a time (the login form's busy guard): a later login that answers first clears the gate while an earlier one
 * is still out. What this leaves open is withSessionCookiesForPost's: at the limit, another tab's refresh, in flight or
 * still waiting for the lock; a logout another tab presses behind a refresh queued while the login is out; a refresh
 * that waited past REFRESH_LOCK_WAIT_MS; and, where the browser has no lock manager or refuses the lock, any other
 * tab's refresh.
 */
export function withoutRefreshBeside<T>(limitMs: number, send: () => Promise<T>): Promise<T> {
  const sent = withSessionCookiesForPost(limitMs, send)
  const clear = () => { if (loginInFlight === answered) loginInFlight = null }
  const answered: Promise<void> = sent.then(clear, clear)
  loginInFlight = answered
  return sent
}

/**
 * Settles once every silent refresh queued for the session cookies' lock before this call, in any tab, has answered:
 * each holds the lock exclusive until its answer has set the cookies, and this asks for it shared and lets it go at
 * once. The identity read waits on it (getCurrentUser in features/auth/api/auth-api.ts), so it reads the cookies the
 * last of those answers set. An OAuth sign-in's answer sets the new session's cookies as a navigation, which cannot
 * hold the lock, so a refresh another tab sent before it with the previous session's cookies can answer after it and
 * set those over the new ones: a tab that read its identity in between would show the new account while the browser
 * holds the previous one (E29). Waiting here, the tab that lands from the sign-in reads the account the browser holds
 * once that refresh has answered: the previous account, when its answer set the previous session's cookies again.
 * Shared, it waits for no post, unless a refresh is queued between them, and nothing waits on it. It settles at
 * `limitMs`, or once `signal` aborts, without the lock, and at once where the browser has no lock manager or refuses
 * the lock. What it leaves open: a refresh still unanswered at the limit, one that waited past REFRESH_LOCK_WAIT_MS
 * and went out without the lock, and, with no lock manager or a refused lock, any refresh, can answer after the read.
 * Never wait on it in a hold's send: a refresh queued behind that hold would keep it waiting, until the limit, for the
 * lock its own caller holds.
 */
export function sessionCookiesSettled(limitMs: number, signal?: AbortSignal): Promise<void> {
  const locks = sessionCookieLocks()
  if (!locks || signal?.aborted) return Promise.resolve()
  const wait = new AbortController()
  const stopWaiting = () => wait.abort()
  const limit = setTimeout(stopWaiting, limitMs)
  signal?.addEventListener('abort', stopWaiting)
  const done = () => {
    clearTimeout(limit)
    signal?.removeEventListener('abort', stopWaiting)
  }
  return locks.request(SESSION_COOKIES_LOCK, { mode: 'shared', signal: wait.signal }, () => undefined).then(done, done)
}

/**
 * Cancels the refresh in flight, if any, so it can no longer set the session cookies: the browser drops a cancelled
 * request's answer, the cookies with it, and one still waiting for the session cookies' lock sends nothing. A failed
 * logout calls it when its read of /me runs out of time. The generation fences stop such a refresh's replay but not
 * its cookies, which would land over a login that followed.
 */
export function cancelRefresh(): void {
  refreshAbort?.abort()
}

// Response error interceptor: silent token refresh on 401, then backend error extraction.
api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<{ detail?: unknown }>) => {
    // Extract the status code and detail message from the backend
    const status = error.response?.status || 0
    const original = error.config as SessionRequestConfig | undefined
    const generation = original?._sessionGeneration ?? getSessionGeneration()
    let sessionLossConfirmed: boolean | undefined
    const currentGeneration = () => isSessionGenerationCurrent(generation)

    // Expired access token on a logged-in session: refresh once and replay the request.
    // Gated on hasActiveSession() so guests never attempt a (pointless) refresh, and on
    // _retry so a request is only ever retried a single time.
    if (
      status === 401 &&
      currentGeneration() &&
      original &&
      !original._retry &&
      isRefreshableRequest(original.url) &&
      original._sessionWasActive &&
      hasActiveSession()
    ) {
      original._retry = true
      let refreshed = false
      try {
        await ensureRefreshed()
        refreshed = true
      } catch (refreshError) {
        // Network/429/5xx failures do not prove the refresh session is gone. Keep the marker
        // so a later request can recover, and classify BEFORE /me interprets this access 401.
        sessionLossConfirmed = getErrorStatus(refreshError) === 401
      }
      // Replay outside the try: an error from the *retried* request (e.g. 500/429, or a
      // persistent 401) must propagate as-is, not be mistaken for a refresh failure.
      if (refreshed && currentGeneration()) {
        return await api(original)
      }
    }

    if (status === 401 && isRefreshableRequest(original?.url) && currentGeneration()) {
      sessionLossConfirmed ??= true
      if (sessionLossConfirmed && original?._sessionWasActive) notifySessionLost(generation)
    }

    const backendDetail = detailMessage(error.response?.data?.detail)

    // Surface the email-verification gate as a friendly global prompt (e.g. on checkout).
    if (
      status === 403 &&
      backendDetail &&
      /verify your email/i.test(backendDetail) &&
      typeof window !== 'undefined'
    ) {
      window.dispatchEvent(new CustomEvent(EMAIL_VERIFICATION_REQUIRED_EVENT, { detail: backendDetail }))
    }

    // Create user-friendly error message based on status and backend detail
    let errorMessage: string

    if (backendDetail) {
      // Use the backend's user-friendly message
      errorMessage = backendDetail
    } else if (status === 503) {
      errorMessage = 'Service temporarily unavailable. Please try again in a moment.'
    } else if (status === 429) {
      errorMessage = 'Too many requests. Please wait a moment before trying again.'
    } else if (status === 404) {
      errorMessage = 'The requested resource was not found.'
    } else if (status >= 500) {
      errorMessage = 'A server error occurred. Please try again later.'
    } else if (error.message?.includes('Network Error') || error.message?.includes('ECONNREFUSED')) {
      errorMessage = 'Could not reach the server. Try again in a moment.'
    } else if (error.message?.includes('timeout')) {
      errorMessage = 'The request timed out. Please try again.'
    } else {
      errorMessage = error.message || 'An unexpected error occurred.'
    }

    // Throw our custom ApiError with the extracted details
    const apiError = new ApiError(status, errorMessage)
    apiError.sessionLossConfirmed = sessionLossConfirmed
    if (typeof backendDetail === 'string' && backendDetail) apiError.backendDetail = backendDetail
    throw apiError
  }
)

export default api
