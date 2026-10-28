/**
 * Lightweight, non-sensitive marker that a session probably exists.
 *
 * Auth itself is cookie-based and HttpOnly, so JavaScript cannot inspect the access or
 * refresh tokens. This flag lets the API client decide whether a 401 is worth a silent
 * refresh attempt: it only refreshes for users who have actually logged in, so guests —
 * whose 401s on protected endpoints are expected and routine — never trigger refresh
 * storms. The flag is advisory only and carries no credential value.
 */
const SESSION_KEY = 'en_session_active'

// In-memory fallback for when localStorage is unavailable (Safari private mode, storage
// blocked by browser settings). Without it, hasActiveSession() would always be false there
// and silent refresh would be disabled — logging those users out every time the access token
// expires. The flag still works for the lifetime of the page in that case.
let inMemorySessionActive = false

export function markSessionActive(): void {
  inMemorySessionActive = true
  try {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SESSION_KEY, '1')
    }
  } catch {
    // localStorage unavailable — the in-memory flag above carries the session.
  }
}

export function clearSessionActive(): void {
  inMemorySessionActive = false
  try {
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(SESSION_KEY)
    }
  } catch {
    // ignore
  }
}

export function hasActiveSession(): boolean {
  if (loggingOut()) return false
  try {
    if (typeof window !== 'undefined') {
      return window.localStorage.getItem(SESSION_KEY) === '1'
    }
  } catch {
    // Fall through to the in-memory flag if localStorage is blocked/disabled.
  }
  return inMemorySessionActive
}

// A stamp of the last password login that took in any tab of this browser (E29 (4)): a value each one changes, kept
// beside the marker in the storage every tab of this origin reads. The session cookies belong to the browser, not the
// tab, so a logout that waited for the session cookies' lock behind another tab's login would post with that login's
// cookies and end its account's session: a logout reads the stamp as it starts, before any wait, and posts nothing once
// it has changed, as for a login accepted in its own tab. Only the password login writes it, once its request has
// answered with success and while it still holds the lock (lib/api/client.ts's withoutRefreshBeside); a failed login
// changes no cookies, and an OAuth sign-in's are set by a navigation, which writes none (E29). With no storage there
// is no stamp, and a logout posts as it did before. A tab reads another's write once the browser has passed it on.
const LOGIN_STAMP_KEY = 'en_session_login'

/** A password login took: stamp it for every tab's logout to read. */
export function stampLogin(): void {
  try {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LOGIN_STAMP_KEY, `${Date.now().toString(36)}.${Math.random().toString(36).slice(2)}`)
    }
  } catch {
    // localStorage unavailable: no stamp, and no logout reads one.
  }
}

/** The login stamp as this tab reads it now: null when none was written, or with no storage. */
export function getLoginStamp(): string | null {
  try {
    if (typeof window !== 'undefined') return window.localStorage.getItem(LOGIN_STAMP_KEY)
  } catch {
    // localStorage unavailable: no stamp.
  }
  return null
}

/** Whether no password login has taken, in any tab, since `stamp` was read. */
export const isLoginStampCurrent = (stamp: string | null): boolean => getLoginStamp() === stamp

// JS request ownership only; cookies and /me remain the authentication source. This fences
// late in-tab responses, not concurrent Set-Cookie responses or changes in another tab.
let sessionGeneration = 0
let lastExplicitTransitionGeneration = 0
const lossListeners = new Set<(generation: number) => void>()

export const getSessionGeneration = (): number => sessionGeneration
export const isSessionGenerationCurrent = (generation: number): boolean => generation === sessionGeneration

export const getExplicitSessionGeneration = (): number => lastExplicitTransitionGeneration
export const isExplicitSessionGenerationCurrent = (generation: number): boolean => generation === lastExplicitTransitionGeneration

// The explicit generation a logout in this tab is ending, and how many logouts of it are under way (E133). Until they
// settle, or another login is accepted (which advances the explicit generation), the session reads as inactive here,
// so no 401 starts a refresh whose answer could set the cookies again after the logout's, and a read's answer (a /me a
// refresh replays) cannot mark it active again. Another tab's marker, which this tab reads from localStorage, cannot
// either.
let loggingOutGeneration: number | null = null
let logoutsUnderWay = 0
const loggingOut = (): boolean => loggingOutGeneration === lastExplicitTransitionGeneration

/** A logout is starting: clear the marker, and keep it clear until `endLogout` (see `loggingOut`). */
export function beginLogout(): number {
  if (!loggingOut()) {
    loggingOutGeneration = lastExplicitTransitionGeneration
    logoutsUnderWay = 0
  }
  logoutsUnderWay += 1
  clearSessionActive()
  return lastExplicitTransitionGeneration
}

export function endLogout(generation: number): void {
  if (loggingOutGeneration !== generation) return
  logoutsUnderWay -= 1
  if (logoutsUnderWay <= 0) {
    loggingOutGeneration = null
    logoutsUnderWay = 0
  }
}

/** A read that confirmed the session (/me) marks it active, except while this tab is logging that session out. */
export function markSessionConfirmed(): void {
  if (!loggingOut()) markSessionActive()
}

export function advanceSessionGeneration(reason: 'explicit' | 'session-loss' = 'explicit'): void {
  sessionGeneration += 1
  if (reason === 'explicit') lastExplicitTransitionGeneration = sessionGeneration
}

/** Passive expiry can cancel old reads without vetoing an authoritative new login. */
export function assertExplicitSessionGeneration(generation: number): void {
  if (!isExplicitSessionGenerationCurrent(generation)) {
    throw new DOMException('Another account transition completed while login was pending', 'AbortError')
  }
}

export function assertSessionGeneration(generation: number): void {
  if (!isSessionGenerationCurrent(generation)) {
    throw new DOMException('Account changed while the request was pending', 'AbortError')
  }
}

export function notifySessionLost(generation: number): void {
  if (!isSessionGenerationCurrent(generation)) return
  clearSessionActive()
  for (const listener of lossListeners) listener(generation)
}

export function subscribeSessionLoss(listener: (generation: number) => void): () => void {
  lossListeners.add(listener)
  return () => { lossListeners.delete(listener) }
}
