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
  try {
    if (typeof window !== 'undefined') {
      return window.localStorage.getItem(SESSION_KEY) === '1'
    }
  } catch {
    // Fall through to the in-memory flag if localStorage is blocked/disabled.
  }
  return inMemorySessionActive
}
