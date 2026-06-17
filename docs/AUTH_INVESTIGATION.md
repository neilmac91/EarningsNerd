# Auth Redirect-Loop Investigation

**Status:** Root cause confirmed. Fix prepared, **NOT applied** — awaiting go-ahead.
**Author:** Claude (Opus) · **Date:** 2026-06-17 · **Branch:** `claude/zen-newton-upsnh9`

---

## ⚠️ Critical-path fix, awaiting go-ahead

> This blocks everything else — you cannot verify Dashboard / Watchlist / Settings behind broken auth.
>
> **One-line cause:** In production the session cookie is **host-only on `api.earningsnerd.io`** because `COOKIE_DOMAIN` is never set, so the Next.js middleware running on `earningsnerd.io` never sees it and bounces every protected route back to `/login`.
>
> **One-line fix (immediate unblock):** Set `COOKIE_DOMAIN=.earningsnerd.io` on the Cloud Run backend. No code change is required to stop the loop. (The PR below also adds a durable-session cookie + regression tests so the bug class can't return.)

---

## 1. How auth actually works here (ground truth, verified from code)

| Layer | Reality | Evidence |
|---|---|---|
| Frontend host | Vercel, served on `earningsnerd.io` **and** `www.earningsnerd.io` | `frontend/vercel.json`, `docs/DEPLOYMENT.md:122` (`CORS_ORIGINS_STR`) |
| Backend host | Cloud Run on `api.earningsnerd.io` (different **origin**, same **site**) | `frontend/next.config.js:9`, `docs/DEPLOYMENT.md:12` |
| Auth mechanism | **Custom, no auth library.** HttpOnly cookies set by the backend: `earningsnerd_access_token` (JWT, 30 min) + `earningsnerd_refresh_token` (opaque, rotated, 30 days, path-scoped to `/api/auth`) | `backend/app/routers/auth.py:238-282`, `config.py:62-69,123-126` |
| Token storage | **Not in localStorage.** JS only keeps a non-credential boolean `en_session_active` to decide whether to attempt a silent refresh | `frontend/lib/api/session.ts`, `auth-api.ts:24` |
| Client → API | axios with `withCredentials: true`; silent refresh on 401 via `/api/auth/refresh` | `frontend/lib/api/client.ts:58,95-137`, `refresh.ts` |
| CORS | `allow_credentials=True`, explicit origin allow-list (apex + www) | `backend/main.py:189-210` |
| Route gate | **Next.js Edge middleware** checks for the access cookie on protected routes and redirects to `/login?redirect=…` if absent | `frontend/middleware.ts:26-45` |

Providers: **Google OIDC** and **Apple Sign In** are implemented directly (no NextAuth/Auth.js/Clerk/Supabase). Both OAuth callbacks set the same two cookies (`auth.py:944-957`, `1107-1121`). **The provider/library is custom — confirm you're happy with this before we touch it (clarifying Q1).**

---

## 2. Reproduction (deterministic, no live access needed)

The loop is fully determined by version-controlled config. Reproduced the cookie-scoping + middleware logic faithfully (Starlette emits `Domain=` only when `domain is not None`; the middleware reads `request.cookies`):

```
PROD TODAY  (COOKIE_DOMAIN=None):
   earningsnerd_access_token=…; HttpOnly; Max-Age=1800; Path=/; SameSite=lax; Secure
   -> No Domain attribute => HOST-ONLY cookie, bound to api.earningsnerd.io
   -> NOT sent by the browser on requests to earningsnerd.io / www.earningsnerd.io

middleware on earningsnerd.io:      sees cookie TODAY=False  -> REDIRECT to /login (the loop)
middleware on www.earningsnerd.io:  sees cookie TODAY=False  -> REDIRECT to /login (the loop)

PROPOSED FIX (COOKIE_DOMAIN=.earningsnerd.io):
   earningsnerd_access_token=…; Domain=.earningsnerd.io; HttpOnly; …
   -> sent to apex, www, AND api subdomains
   middleware on earningsnerd.io / www: sees cookie AFTER-FIX=True -> pass
```

**The tell-tale signature** that distinguishes this from "login is broken": API calls to `api.earningsnerd.io` (e.g. `GET /api/auth/me`) *succeed* — the host-only cookie is correctly sent to the API — so the user looks logged in everywhere **except** the middleware-gated pages. Sign-in genuinely worked; only the server-side route guard is blind to it.

---

## 3. Root cause (confirmed)

**The production access-token cookie is host-only on `api.earningsnerd.io`, so the Next.js middleware on the frontend origin can't see it and redirects every protected route to `/login`.**

Chain of evidence:

1. `backend/app/config.py:126` — `COOKIE_DOMAIN: str | None = None` (default).
2. `backend/app/routers/auth.py:238-248` — `_set_auth_cookie()` passes `domain=settings.COOKIE_DOMAIN`. With `None`, Starlette omits the `Domain` attribute → **host-only** cookie.
3. `docs/DEPLOYMENT.md:122` — the production Cloud Run env-var list (`ENVIRONMENT`, `SKIP_REDIS_INIT`, `OPENAI_BASE_URL`, `CORS_ORIGINS_STR`, …) **contains no `COOKIE_DOMAIN`**.
4. `.github/workflows/ci.yml:214-218` — the authoritative CD deploy uses `--update-env-vars=OPENAI_BASE_URL,AI_DEFAULT_MODEL` only; **`COOKIE_DOMAIN` is never set.** So prod runs with the `None` default.
5. `frontend/middleware.ts:33-44` — for `/dashboard|/profile|/settings` it checks `request.cookies.has('earningsnerd_access_token')` **on the frontend host**; absent → `NextResponse.redirect('/login?redirect=…')`.
6. A host-only cookie set by `api.earningsnerd.io` is, by RFC 6265, **not** sent to `earningsnerd.io` / `www.earningsnerd.io`. Hence step 5 always redirects. **Loop.**

This matches both of your starting observations:
- *"`?redirect=` is preserved → the guard works; the session isn't recognised on the protected side."* ✔ Exactly — the guard fires because the cookie is invisible to it.
- *"Cookie scoped to a single host instead of `.earningsnerd.io`."* ✔ Correct — the single host is the **backend** (`api.`), not an apex-vs-`www` split. `Domain=.earningsnerd.io` fixes the api→frontend visibility **and** any apex/www inconsistency in one move.

### One residual uncertainty (only you can close it)
I cannot read the live Cloud Run environment. Everything version-controlled says `COOKIE_DOMAIN` is unset, which fully explains the loop. **Please confirm with either:**
- Browser: DevTools → Application → Cookies → check the **Domain** column of `earningsnerd_access_token` after logging in. `api.earningsnerd.io` = confirmed bug; `.earningsnerd.io` = already correct (then the cause is the secondary issue in §4).
- CLI: `gcloud run services describe earningsnerd-backend --region=us-west1 --format='value(spec.template.spec.containers[0].env)'` and look for `COOKIE_DOMAIN`.

---

## 4. Secondary defect (same bug class — fix in the same PR)

Even **after** `COOKIE_DOMAIN` is correct, the middleware gates on the **30-minute access cookie** (`max_age=1800`, `config.py:64`). The durable session is the **30-day refresh cookie**, which is path-scoped to `/api/auth` (`auth.py:261`) and therefore *also* invisible to `earningsnerd.io/dashboard`. So a user who returns after the access token expires gets bounced to `/login` despite a valid 30-day session — the client's silent-refresh never runs because the **server** middleware redirects before the page loads. This will surface as intermittent "it keeps logging me out." It is the same root failure mode: *the server route-guard can't see the durable session.* Fix 2 below removes it.

---

## 5. Hypotheses eliminated (with evidence)

| Hypothesis | Verdict | Evidence |
|---|---|---|
| Cookie **domain** mismatch (apex vs www; not `.earningsnerd.io`) | ✅ **ROOT CAUSE** | §3 |
| Cookie **name** mismatch (middleware literal vs backend) | ❌ Ruled out | `middleware.ts:36` `'earningsnerd_access_token'` == `config.py:123` `COOKIE_NAME` default |
| `SameSite` / `Secure` / `HttpOnly` / `Path` / expiry | ❌ Not the cause | `Secure` auto-true in prod (`config.py:228-229`); `SameSite=lax` is fine because apex/api are **same-site** (no `SameSite=None` needed); `HttpOnly` doesn't block server middleware or network send, only `document.cookie`; `Path=/` correct |
| CORS / `credentials` / cookie not reaching API | ❌ Correctly configured | `withCredentials:true` (`client.ts:58`) + `allow_credentials=True` + explicit origins (`main.py:189-210`). This is *why* the API works while the middleware fails |
| Middleware/SSR runs before client auth hydrates (race) | ❌ Not the mechanism | Middleware is purely cookie-based and deterministic; it never waits on client state. (Related: the durable session isn't *available* to it — see §4, Fix 2) |
| Token in `localStorage` that middleware can't read | ❌ N/A | No token in JS; only the non-credential `en_session_active` flag (`session.ts`) |
| Post-login handler doesn't consume `redirect` | ⚠️ Real, but **not** the loop | `login/page.tsx:59` always `router.push('/')`. Cosmetic; addressed by Fix 3 |
| Silent JWT validation failure (sig/aud/iss/skew/expiry) | ❌ Ruled out | `/api/auth/me` validates the same JWT and would 401 if broken; it succeeds. Issuer/audience/leeway all set (`config.py:74-76`, `auth.py:337-344`) |

---

## 6. Recommended fix (prepared — do not apply until greenlit)

Three changes, in priority order. **Fix 1 alone stops the reported loop.** Fixes 2–3 prevent recurrence and close the redirect UX gap; ship them in the same PR.

### Fix 1 — Scope the cookie to the parent domain (the keystone)

**Immediate unblock (no deploy):** set the env var on the running service —
```bash
gcloud run services update earningsnerd-backend --region=us-west1 \
  --update-env-vars=COOKIE_DOMAIN=.earningsnerd.io
```
**Make it durable + reviewable** — bake it into CI and the runbook:

```diff
# .github/workflows/ci.yml  (deploy-backend → "Deploy Cloud Run service", ~line 217)
-            --update-env-vars=OPENAI_BASE_URL=https://api.deepseek.com/v1,AI_DEFAULT_MODEL=deepseek-v4-pro \
+            --update-env-vars=OPENAI_BASE_URL=https://api.deepseek.com/v1,AI_DEFAULT_MODEL=deepseek-v4-pro,COOKIE_DOMAIN=.earningsnerd.io \
```
```diff
# docs/DEPLOYMENT.md  (manual `gcloud run deploy` env-var string, line 122)
-@CORS_ORIGINS_STR=https://earningsnerd.io,https://www.earningsnerd.io"
+@CORS_ORIGINS_STR=https://earningsnerd.io,https://www.earningsnerd.io@COOKIE_DOMAIN=.earningsnerd.io"
```

> `COOKIE_DOMAIN` must stay **unset** in local dev (cookies on `localhost`). No code default change.

**Optional hardening (recommended):** fail-fast if prod is misconfigured, so this can never silently regress. In `backend/app/config.py`, after the existing production guards in `__init__` (~line 236):
```python
if self.ENVIRONMENT == "production" and not self.COOKIE_DOMAIN:
    import logging
    logging.getLogger("uvicorn.error").warning(
        "COOKIE_DOMAIN is unset in production. If the frontend and API are on "
        "different hosts of the same site (earningsnerd.io vs api.earningsnerd.io), "
        "session cookies will be host-only and protected routes will redirect-loop. "
        "Set COOKIE_DOMAIN=.earningsnerd.io."
    )
```
(Warn, not raise — a single-host deployment is legitimately fine with it unset.)

### Fix 2 — Gate the middleware on a durable session-presence cookie (kills the bug class)

Add a non-credential `en_session` cookie whose lifetime matches the **refresh** token and that is scoped to `Domain=.earningsnerd.io, Path=/`, set wherever we establish a session and cleared on logout. The middleware reads **that** instead of the short-lived access cookie. Real authentication is unchanged (still the HttpOnly JWT/refresh validated by the backend on every API call); this cookie only answers "is there a session?" for the edge guard, so the gate stays true for the whole 30-day session.

```diff
# backend/app/routers/auth.py  (near _set_auth_cookie, ~line 238)
+SESSION_PRESENCE_COOKIE = "en_session"  # non-credential; mirrors refresh-token lifetime.
+                                        # Read by frontend/middleware.ts — keep the name in sync.
+
+def _set_session_presence_cookie(response: Response) -> None:
+    response.set_cookie(
+        key=SESSION_PRESENCE_COOKIE, value="1",
+        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
+        httponly=True, secure=settings.COOKIE_SECURE,
+        samesite=settings.COOKIE_SAMESITE, domain=settings.COOKIE_DOMAIN, path="/",
+    )
+
+def _clear_session_presence_cookie(response: Response) -> None:
+    response.delete_cookie(SESSION_PRESENCE_COOKIE, domain=settings.COOKIE_DOMAIN, path="/")
```
Call `_set_session_presence_cookie(response)` immediately after each `_set_auth_cookie(...)` /
`_set_auth_cookie(redirect, ...)` — i.e. in **login** (`:674`), **refresh** (`:721`),
**google_callback** (`:947`), **apple_callback** (`:1109`). Call `_clear_session_presence_cookie(response)`
alongside the `_clear_auth_cookie` calls in **logout** (`:1154`), **logout-all** (`:1171`), and the two
refresh-failure branches (`:702-703`, `:711-712`).

```diff
# frontend/middleware.ts:36
-    const hasSessionCookie = request.cookies.has('earningsnerd_access_token')
+    // Durable, non-credential session marker (set by the backend for the whole refresh-token
+    // lifetime). Real auth is still enforced by the API on every request; this only tells the
+    // edge guard a session exists, so it doesn't bounce users when the 30-min access token rotates.
+    const hasSessionCookie = request.cookies.has('en_session')
```
> Fix 2 **depends on Fix 1** — without the correct `Domain`, `en_session` would also be host-only.

### Fix 3 — Honour the `redirect` param after login (UX)

```diff
# frontend/app/login/page.tsx  (LoginContent)
-      router.push('/')
-      router.refresh()
+      const dest = searchParams.get('redirect')
+      // Only allow internal, single-segment-rooted paths (no protocol-relative "//evil").
+      const safe = dest && dest.startsWith('/') && !dest.startsWith('//') ? dest : '/'
+      router.push(safe)
+      router.refresh()
```
(OAuth callbacks currently always return to `/`; carrying `redirect` through the OAuth `state` is a nice-to-have, tracked in the implementation plan, not required to fix the loop.)

---

## 7. Verification & regression plan

### Manual verification (post-deploy, staging or prod)
1. Sign in (email, Google, Apple). DevTools → Application → Cookies: `earningsnerd_access_token` and `en_session` show **Domain `.earningsnerd.io`**.
2. Navigate to `/dashboard`, `/dashboard/watchlist`, `/dashboard/settings` → all render; **no** bounce to `/login`.
3. Visit `/login?redirect=/dashboard/watchlist`, sign in → land on `/dashboard/watchlist` (Fix 3).
4. **Expiry test (Fix 2):** after sign-in, delete only `earningsnerd_access_token` in DevTools (simulates 30-min expiry), reload `/dashboard` → still renders (middleware sees `en_session`; API silently refreshes). Pre-fix this redirects to `/login`.
5. Repeat 1–2 on both `earningsnerd.io` and `www.earningsnerd.io`.
6. Logout → both cookies cleared; `/dashboard` redirects to `/login`.

### Automated regression tests (so it can't silently return)

**Backend** — `backend/tests/unit/test_auth_cookies.py` (new):
```python
import os, pytest
from starlette.responses import Response

def _set(domain):
    from app.routers.auth import _set_auth_cookie
    r = Response()
    # patch settings.COOKIE_DOMAIN for the call, then read the Set-Cookie header
    ...
def test_access_cookie_is_domain_scoped(monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "COOKIE_DOMAIN", ".earningsnerd.io")
    r = Response(); from app.routers.auth import _set_auth_cookie
    _set_auth_cookie(r, "jwt")
    sc = r.headers["set-cookie"]
    assert "Domain=.earningsnerd.io" in sc        # regression guard for the loop
    assert "HttpOnly" in sc and "Path=/" in sc

def test_login_sets_session_presence_cookie():
    # via TestClient login (mock_user), assert 'en_session' present + Domain scoped
    ...
```

**Frontend** — `frontend/__tests__/middleware.test.ts` (new, Vitest):
```ts
import { describe, it, expect } from 'vitest'
import { middleware } from '@/middleware'
import { NextRequest } from 'next/server'

const req = (path: string, cookie?: string) => {
  const r = new NextRequest(new URL(`https://earningsnerd.io${path}`))
  if (cookie) r.cookies.set('en_session', '1')
  return r
}
describe('protected-route middleware', () => {
  it('redirects to /login with redirect param when no session', () => {
    const res = middleware(req('/dashboard'))
    expect(res.headers.get('location')).toContain('/login?redirect=%2Fdashboard')
  })
  it('passes through when the session cookie is present', () => {
    const res = middleware(req('/dashboard/watchlist', '1'))
    expect(res.headers.get('location')).toBeNull()  // no redirect
  })
})
```
Add a test that pins the cookie-name contract (`en_session`) on both sides so they can never drift.

### Rollback
- Fix 1 is a single env var: `gcloud run services update … --remove-env-vars=COOKIE_DOMAIN` (instant).
- Fixes 2–3 are additive and revertable via git; `en_session` is non-credential, so adding/removing it carries no security risk.
- All cookie attributes except `Domain` are unchanged → blast radius is the cookie scope only.

---

## 8. Why this is the elegant fix, not a patch
The real defect is **a single deployment-config omission** plus **an edge guard coupled to the wrong (short-lived) token**. Fix 1 corrects the omission at its version-controlled source; Fix 2 decouples the guard from access-token rotation so the *class* of "server can't see the session" bugs is closed; both ship with tests that pin the contract. Nothing about the (sound) cryptographic auth design changes.
</content>
</invoke>
