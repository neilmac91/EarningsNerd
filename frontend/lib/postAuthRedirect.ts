/**
 * Post-auth redirect stash — closes the leg of the signup funnel that `?redirect=` can't reach.
 *
 * The query-param thread (gate → /register?redirect → /check-email → /login?redirect) only
 * survives navigation within one tab. The PRIMARY new-user path leaves it: the verification email
 * opens `/verify-email` in a fresh tab, and any login from there has no redirect param — the user
 * who converted at a filing's signup gate would land on `/` and have to re-find the filing.
 *
 * So the gate ALSO stashes its destination here (localStorage, deliberately not sessionStorage —
 * it must survive the new-tab hop), and login consumes it as the fallback when no `?redirect=`
 * param is present. Consume-once + a freshness window keep a stale stash from teleporting an
 * unrelated later login. Values are validated as single-slash-rooted internal paths on BOTH ends
 * (same rule as login's `?redirect=` handling: reject `//evil` and `/\evil` open-redirect forms).
 */

const KEY = 'en_post_auth_redirect'
// A gate → verify-email → login round trip is minutes, not days. After this window the stash is
// considered stale and ignored (and cleared), so an abandoned signup can't redirect next week's login.
const MAX_AGE_MS = 60 * 60 * 1000 // 1 hour

const isSafeInternalPath = (path: string): boolean =>
  path.startsWith('/') && !path.startsWith('//') && !path.startsWith('/\\')

export function stashPostAuthRedirect(path: string): void {
  if (!isSafeInternalPath(path)) return
  try {
    localStorage.setItem(KEY, JSON.stringify({ path, at: Date.now() }))
  } catch {
    // Storage unavailable (SSR guard, private mode, quota) — the ?redirect= thread still works.
  }
}

export function consumePostAuthRedirect(): string | null {
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    localStorage.removeItem(KEY) // consume-once, even when stale/invalid
    const { path, at } = JSON.parse(raw) as { path?: unknown; at?: unknown }
    if (typeof path !== 'string' || typeof at !== 'number') return null
    if (Date.now() - at > MAX_AGE_MS) return null
    return isSafeInternalPath(path) ? path : null
  } catch {
    return null
  }
}
