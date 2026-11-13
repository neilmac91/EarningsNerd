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
 * unrelated later login. Values are validated as internal paths on BOTH ends, by the one rule
 * login's `?redirect=` handling uses (`safeInternalPath` below).
 */

const KEY = 'en_post_auth_redirect'
// A gate → verify-email → login round trip is minutes, not days. After this window the stash is
// considered stale and ignored (and cleared), so an abandoned signup can't redirect next week's login.
const MAX_AGE_MS = 60 * 60 * 1000 // 1 hour

/**
 * The destination as a path on this origin, or null when it is not one. The one rule for every
 * post-auth destination: login's `?redirect=` value and the stash, written and read.
 *
 * The URL parser decides, not a prefix test. It drops tabs and line breaks anywhere in its input and
 * reads a backslash as a slash, so `/\t/evil.example`, `/\n/evil.example` and `/\\evil.example` all
 * parse as `//evil.example`, another site, while each begins with one slash and passes a check of
 * the first two characters. What the router would navigate to is what gets compared, and the
 * parsed path is what is returned.
 *
 * The parsed path is checked too, since it is what the router is handed. Removing dot segments can
 * leave one that names another site: a destination that opens with a dot segment and then two
 * slashes before a host parses on this origin, with a path that opens with those two slashes. So
 * the returned path must itself parse to this origin.
 */
export function safeInternalPath(dest: string | null | undefined): string | null {
  if (typeof window === 'undefined' || !dest || !dest.startsWith('/')) return null
  const { origin } = window.location
  try {
    const url = new URL(dest, origin)
    if (url.origin !== origin) return null
    const path = `${url.pathname}${url.search}${url.hash}`
    return new URL(path, origin).origin === origin ? path : null
  } catch {
    return null
  }
}

/**
 * Build `/login` and `/register` hrefs that forward a post-signup `?redirect=` destination. One
 * home for the pattern so a call site can't reintroduce it un-encoded — the receiving page
 * validates the value again (internal paths only), so these only carry it, not trust it.
 *
 * IMPORTANT: pass a RAW path (e.g. `/filing/123`), never a pre-encoded one — these encode exactly
 * once. A double-encode would survive the receiver's single decode as `%2Ffiling%2F123`, fail its
 * internal-path check (`safeInternalPath`), and silently drop the redirect to `/`.
 */
export function loginHrefWithRedirect(redirect?: string | null): string {
  return redirect ? `/login?redirect=${encodeURIComponent(redirect)}` : '/login'
}

export function registerHrefWithRedirect(redirect?: string | null): string {
  return redirect ? `/register?redirect=${encodeURIComponent(redirect)}` : '/register'
}

export function stashPostAuthRedirect(path: string): void {
  const safe = safeInternalPath(path)
  if (!safe) return
  try {
    localStorage.setItem(KEY, JSON.stringify({ path: safe, at: Date.now() }))
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
    return safeInternalPath(path)
  } catch {
    return null
  }
}
