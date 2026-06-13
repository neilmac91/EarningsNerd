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

export function markSessionActive(): void {
  try {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(SESSION_KEY, '1')
    }
  } catch {
    // localStorage may be unavailable (private mode, SSR). Refresh simply won't be gated;
    // the worst case is a single wasted /refresh attempt, which fails closed.
  }
}

export function clearSessionActive(): void {
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
    return typeof window !== 'undefined' && window.localStorage.getItem(SESSION_KEY) === '1'
  } catch {
    return false
  }
}
