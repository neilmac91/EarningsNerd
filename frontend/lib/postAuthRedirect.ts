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

/**
 * Build `/login` and `/register` hrefs that forward a post-signup `?redirect=` destination. One
 * home for the pattern so a call site can't reintroduce it un-encoded — the receiving page
 * validates the value again (internal paths only), so these only carry it, not trust it.
 *
 * IMPORTANT: pass a RAW path (e.g. `/filing/123`), never a pre-encoded one — these encode exactly
 * once. A double-encode would survive the receiver's single decode as `%2Ffiling%2F123`, fail its
 * `startsWith('/')` internal-path check, and silently drop the redirect to `/`.
 */
export function loginHrefWithRedirect(redirect?: string | null): string {
  return redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'
}

export function registerHrefWithRedirect(redirect?: string | null): string {
  return redirect ? `/register?redirect=${encodeURIComponent(redirect)}` : '/register'
}

export function stashPostAuthRedirect(path: string): void {
  if (typeof window === 'undefined' || !isSafeInternalPath(path)) return
  try {
    localStorage.setItem(KEY, JSON.stringify({ path, at: Date.now() }))
  } catch {
    // Storage unavailable (private mode, quota) — the ?redirect= thread still works.
  }
}

export function consumePostAuthRedirect(): string | null {
  if (typeof window === 'undefined') return null
  try {
    const raw = localStorage.getItem(KEY)
    if (!raw) return null
    localStorage.removeItem(KEY) // consume-once, even when stale/invalid
    const parsed: unknown = JSON.parse(raw)
    if (!parsed || typeof parsed !== 'object') return null
    const { path, at } = parsed as { path?: unknown; at?: unknown }
    if (typeof path !== 'string' || typeof at !== 'number') return null
    if (Date.now() - at > MAX_AGE_MS) return null
    return isSafeInternalPath(path) ? path : null
  } catch {
    return null
  }
}
