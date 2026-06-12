# Auth Audit Report — EarningsNerd.io
**Date:** 2026-06-12  
**Auditor:** Principal Security Review (Phase 1)  
**Status:** Read-only discovery. No files modified.

---

## Table of Contents

1. [Architecture Inventory](#1-architecture-inventory)
2. [Data Layer](#2-data-layer)
3. [Existing Security Posture](#3-existing-security-posture)
4. [Endpoint Protection Inventory](#4-endpoint-protection-inventory)
5. [Findings — Ranked by Severity](#5-findings-ranked-by-severity)
6. [Blockers and Unknowns](#6-blockers-and-unknowns)

---

## 1. Architecture Inventory

### 1.1 System Topology

```
┌────────────────────────────────────────────────────────────────────┐
│  User Browser                                                       │
│                                                                     │
│  earningsnerd.io  ──────► Vercel CDN/Edge                          │
│                              │                                      │
│                              ▼                                      │
│                       Next.js 16.2.6                               │
│                       App Router + SSR                             │
│                       (WAITLIST_MODE=false in prod)                │
│                                                                     │
│  Cross-domain CORS request (credentials: include)                  │
│                              │                                      │
│                              ▼                                      │
│  api.earningsnerd.io  ──► Cloud Run (us-west1)                     │
│                              │                                      │
│                              ├──► Cloud SQL / PostgreSQL 15         │
│                              │    (earningsnerd-db)                 │
│                              │                                      │
│                              └──► Redis (LOCAL DEV ONLY)            │
│                                   SKIP_REDIS_INIT=true in prod      │
└────────────────────────────────────────────────────────────────────┘
```

**Key topology facts:**
- Frontend and backend are on **different origins** (`earningsnerd.io` vs `api.earningsnerd.io`). This is a cross-site cookie scenario — `SameSite` policy is critical.
- Vercel hosts the Next.js frontend; GCP Cloud Run hosts the FastAPI backend.
- Both use HTTPS in production (Cloud Run auto-TLS; Vercel auto-TLS).
- Redis is disabled in production (`SKIP_REDIS_INIT=true`). All rate limiting is **in-process only**.

### 1.2 Next.js Version and Rendering Model

| Property | Value |
|---|---|
| Next.js version | **16.2.6** |
| React version | 18.2.0 |
| TypeScript | 6.0.3 |
| Router | **App Router** (confirmed by `app/` directory structure) |
| Middleware | `frontend/middleware.ts` — Edge middleware for route gating |
| Server Components | Used throughout (layout, page-level RSC where no interactivity) |
| Auth libraries | **None currently** — custom cookie check in middleware |

The App Router + Edge Middleware model means Auth.js v5 (NextAuth) is viable without compatibility shims.

### 1.3 Frontend → Backend Communication

**Library:** Axios (`lib/api/client.ts`), plus raw `fetch` for SSE streams.

```typescript
// lib/api/client.ts (simplified)
const api = axios.create({
  baseURL: getBaseUrl(),           // https://api.earningsnerd.io in production
  withCredentials: true,           // sends httpOnly cookie with every request
  timeout: 30000,
})
```

- All axios calls send cookies (`withCredentials: true`).
- SSE fetch calls also use `credentials: 'include'`.
- **No explicit `Authorization: Bearer` header** is set by the frontend — all auth goes via cookie.
- The token is also returned in the login/register JSON response body, but the frontend does not appear to store it (React Query cache only).
- Base URL: `NEXT_PUBLIC_API_BASE_URL` env var → `https://api.earningsnerd.io`.

### 1.4 Backend Auth Stack

**Framework:** FastAPI + `python-jose` + `bcrypt` (via `passlib[bcrypt]`)

```
python-jose[cryptography]>=3.5.0   # JWT encode/decode
passlib[bcrypt]==1.7.4             # Password hashing context (legacy compat)
bcrypt                             # Direct bcrypt calls (unpinned — transitive dep)
```

- JWT algorithm: **HS256** (symmetric HMAC-SHA256, single secret key).
- Token stored in httpOnly cookie named `earningsnerd_access_token`.
- Token expiry: **7 days** (`ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7`).
- No refresh token. No token rotation. No revocation.
- Cookie attributes: `httpOnly=True`, `Secure=True` (production), `SameSite="lax"`, `Domain=None`.

### 1.5 GCP Deployment Topology

| Component | Service | Details |
|---|---|---|
| Backend | Cloud Run (`earningsnerd-backend`) | Region: `us-west1`, Project: `earnings-nerd` |
| Database | Cloud SQL PostgreSQL 15 | `earningsnerd-db`, Cloud SQL connector socket |
| Cache | None in production | Redis only for local dev |
| Secrets | GCP Secret Manager | Mounted as env vars on Cloud Run |
| CI/CD | GitHub Actions | Keyless auth via Workload Identity Federation |
| Frontend | Vercel | `NEXT_PUBLIC_API_BASE_URL=https://api.earningsnerd.io` |
| Custom domain | Cloud Run domain mapping | `api.earningsnerd.io` → `ghs.googlehosted.com` (Cloudflare CNAME) |

**Cookie scoping implication:** Because frontend (`earningsnerd.io`) and API (`api.earningsnerd.io`) are on the same registrable domain, a `Domain=.earningsnerd.io` cookie *could* be shared. Currently `COOKIE_DOMAIN=None` (defaults to the setting origin, `api.earningsnerd.io`) — the cookie is sent cross-site only because `withCredentials: true` is set on all requests. `SameSite=Lax` allows cross-site cookie sending for top-level navigations, but for cross-origin `fetch`/XHR, the browser only includes the cookie if `SameSite=None; Secure` OR if the cookie was set by the target origin. This currently works because the backend sets the cookie (the API origin), and the frontend sends requests back to that same origin — but it warrants explicit validation in the context of Apple's `form_post` callback (see Finding F-04).

---

## 2. Data Layer

### 2.1 Migration Tooling

**No Alembic.** Schema is created at startup via `Base.metadata.create_all(bind=engine)` in `main.py:77`. One-off changes are applied as hand-written SQL files in `backend/migrations/`:

| File | Purpose |
|---|---|
| `20260120_create_waitlist_signups.sql` | Creates `waitlist_signups` table |
| `20260122_add_markdown_cache_columns.sql` | Adds markdown cache columns to `filing_content_cache` |
| `20260126_add_is_admin_to_users.sql` | Adds `is_admin` boolean to `users` |

Applied manually. No migration state tracking (no `alembic_version` table). Any future auth schema additions (e.g. `oauth_accounts`, `email_verified`, password reset tokens) will require new manual SQL migrations and ORM model updates.

### 2.2 Current User Schema (`users` table)

```sql
CREATE TABLE users (
  id                    INTEGER PRIMARY KEY,          -- Integer, not UUID
  email                 VARCHAR UNIQUE NOT NULL,      -- Lowercased at input
  hashed_password       VARCHAR NOT NULL,             -- bcrypt; NOT NULL blocks social-only accounts
  full_name             VARCHAR,
  is_active             BOOLEAN DEFAULT TRUE,
  is_pro                BOOLEAN DEFAULT FALSE,
  is_admin              BOOLEAN DEFAULT FALSE,
  stripe_customer_id    VARCHAR,
  stripe_subscription_id VARCHAR,
  created_at            TIMESTAMPTZ DEFAULT NOW(),
  updated_at            TIMESTAMPTZ
);
-- Missing: email_verified, last_login_at, password_reset_token, password_reset_expires
```

**Critical gaps for auth implementation:**
- No `email_verified` column.
- No `password_reset_token` or `password_reset_expires`.
- `hashed_password` is `NOT NULL` — social-only accounts cannot be created without a schema change.
- Primary key is `INTEGER`, not `UUID` — the spec calls for UUID PKs. Migration required.
- `stripe_customer_id` already exists (Stripe-readiness is present).

### 2.3 Waitlist Schema (`waitlist_signups` table)

```sql
CREATE TABLE waitlist_signups (
  id               INTEGER PRIMARY KEY,
  email            VARCHAR UNIQUE NOT NULL,
  name             VARCHAR,
  referral_code    VARCHAR(8) UNIQUE NOT NULL,
  referred_by      VARCHAR(8),                    -- References another referral_code
  source           VARCHAR,
  created_at       TIMESTAMPTZ DEFAULT NOW(),
  email_verified   BOOLEAN DEFAULT FALSE NOT NULL,
  welcome_email_sent BOOLEAN DEFAULT FALSE NOT NULL,
  position         INTEGER NOT NULL,
  priority_score   INTEGER DEFAULT 0 NOT NULL
);
```

**Migration path:** These emails must be importable into the future `users` table with a `waitlist_joined_at` provenance field. The `email_verified` flag is available to determine whether the waitlist email was confirmed. The `name` field maps to `full_name`. No accounts should be auto-created — import as metadata only.

---

## 3. Existing Security Posture

### 3.1 What Currently Exists

The site has **a working custom auth implementation** for email+password:

- `POST /api/auth/register` — creates user, returns JWT in cookie + body
- `POST /api/auth/login` — verifies bcrypt hash, returns JWT in cookie + body
- `GET /api/auth/me` — JWT-protected user info
- `POST /api/auth/logout` — clears cookie (server-side)

The implementation is **structurally sound** (httpOnly cookie, bcrypt, JWT with `iss`/`aud`/`exp`/`nbf`/`jti` claims, CORS locked to production origins, security headers). However, it has significant gaps enumerated below.

### 3.2 CORS Configuration

**File:** `backend/app/config.py:88`, `backend/main.py:175-196`

```python
CORS_ORIGINS = [
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "https://earningsnerd.io",
  "https://www.earningsnerd.io",
]
# Dev only: allow_origin_regex = r"http://localhost:\d+"
```

- Production origins are correctly restricted to `earningsnerd.io` only.
- `allow_credentials=True` is set, which is required for cookie-based cross-origin auth.
- The dev `localhost:\d+` regex is correctly gated behind `ENVIRONMENT != "production"`.

### 3.3 Security Headers

**File:** `backend/main.py:199-210`

| Header | Status | Value |
|---|---|---|
| `X-Content-Type-Options` | ✓ Set | `nosniff` |
| `X-Frame-Options` | ✓ Set | `DENY` |
| `Referrer-Policy` | ✓ Set | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | ✓ Set | `geolocation=(), microphone=(), camera=()` |
| `Strict-Transport-Security` | ✓ Set (prod) | `max-age=31536000; includeSubDomains` |
| `Content-Security-Policy` | Partial | `default-src 'none'` on `/api/` routes only |
| `Cache-Control` | Not set | Should be `no-store` on auth endpoints |

Missing: `Cache-Control: no-store` on `/api/auth/login`, `/api/auth/register`, and `/api/auth/me` responses. Auth tokens returned in response bodies can be stored by proxies/CDN without this.

### 3.4 Rate Limiting

**File:** `backend/app/services/rate_limiter.py`, `backend/app/routers/auth.py:21-22`

```python
LOGIN_LIMITER    = RateLimiter(limit=10, window_seconds=60)   # 10 attempts/min/IP
REGISTER_LIMITER = RateLimiter(limit=5,  window_seconds=60)   # 5 attempts/min/IP
SUMMARY_LIMITER  = RateLimiter(limit=5,  window_seconds=60)   # 5 summaries/min/IP or user
```

**Implementation:** In-memory sliding window using `collections.deque` with a `threading.Lock`. IP extracted from `X-Forwarded-For` (first hop only).

**Critical flaw:** Cloud Run can run **multiple container instances**. This in-memory limiter is **per-instance** — an attacker who distributes requests across instances (Cloud Run's default load balancing) bypasses all rate limits. In production with no Redis, there is no distributed rate limiting for auth endpoints.

### 3.5 Secrets Hygiene

- `.env` is in `.gitignore` ✓
- Only `backend/.env.bak` is committed, containing placeholder values only (`your_key_here`, `dev-secret-key-change-in-production`) ✓
- `SECRET_KEY` validated at startup — rejects the known-weak default in production ✓
- Production secrets managed via GCP Secret Manager ✓
- No API keys in client-side code ✓
- `NEXT_PUBLIC_*` vars contain only feature flags and public URLs — no secrets ✓

**Minor issue:** `bcrypt` is not directly pinned in `requirements.txt`. It is installed as a transitive dependency of `passlib[bcrypt]==1.7.4`. A future `pip install` on a fresh environment could install a different bcrypt version. The work factor defaults to 12 rounds via `bcrypt.gensalt()`, which is acceptable today but should be made explicit.

### 3.6 Existing Admin Access Control

**File:** `backend/app/routers/admin.py:21-35`

Admin endpoints check `user.is_admin == True` after JWT verification. This is a basic but functional RBAC check. There is no rate limiting on admin endpoints and no second-factor requirement — acceptable for a solo dev with a known admin account, but worth noting.

---

## 4. Endpoint Protection Inventory

### 4.1 Currently Protected Endpoints (require valid JWT)

These use `Depends(get_current_user)`:

| Router | Endpoint | Risk Level |
|---|---|---|
| auth | `GET /api/auth/me` | Low |
| auth | `POST /api/auth/logout` | Low |
| users | `GET /api/users/export` | High (GDPR data) |
| users | `DELETE /api/users/me` | Critical (destructive) |
| users | `PUT /api/users/profile` | Medium |
| subscriptions | `GET /api/subscriptions/subscription` | Medium |
| subscriptions | `GET /api/subscriptions/usage` | Low |
| subscriptions | `POST /api/subscriptions/create-checkout-session` | **Critical** (payment trigger) |
| subscriptions | `POST /api/subscriptions/create-portal-session` | **Critical** (billing access) |
| saved_summaries | `GET /api/saved-summaries` | Low |
| saved_summaries | `POST /api/saved-summaries` | Low |
| saved_summaries | `DELETE /api/saved-summaries/{id}` | Low |
| watchlist | `GET /api/watchlist` | Low |
| watchlist | `POST /api/watchlist/{ticker}` | Low |
| watchlist | `DELETE /api/watchlist/{ticker}` | Low |
| watchlist | `GET /api/watchlist/insights` | Medium |
| summaries | `POST /api/summaries/filing/{id}/generate` | **Critical** (AI cost) |
| summaries | `GET /api/summaries/filing/{id}/export/pdf` | Medium (Pro feature) |
| summaries | `GET /api/summaries/filing/{id}/export/csv` | Medium (Pro feature) |
| admin | `DELETE /api/admin/filing/{id}/summary` | High |
| admin | `DELETE /api/admin/filing/{id}/xbrl` | High |
| admin | `DELETE /api/admin/filing/{id}/reset` | High |
| admin | `POST /api/admin/xbrl/clear-memory-cache` | High |
| admin | `GET /api/admin/xbrl/cache-stats` | Medium |
| admin | `GET /api/admin/filings/audit-xbrl` | Medium |
| admin | `POST /api/admin/filings/bulk-reset-stale` | High |

### 4.2 UNPROTECTED Endpoints with AI Cost Exposure (CRITICAL)

```
POST /api/summaries/filing/{filing_id}/generate-stream
```

**File:** `backend/app/routers/summaries.py:189-196`

This endpoint uses `Depends(get_current_user_optional)` — **guests (unauthenticated users) can trigger LLM summary generation**. This is the primary AI cost-amplification attack surface. The only protection is:
- An in-memory (per-instance) rate limiter: 5 summaries/60s per IP.
- An optional per-IP daily quota (`ENABLE_GUEST_DAILY_QUOTA=False` — **disabled by default**).
- `force=False` by default — a cached summary is returned without triggering AI.

The `force=True` parameter allows forced regeneration; no additional auth check gates `force=True` for guests. An attacker who knows different `filing_id` values can trigger a fresh AI generation for each one.

### 4.3 Publicly Accessible Endpoints (appropriate — no auth needed)

| Endpoint | Notes |
|---|---|
| `GET /api/companies/search` | Public company search |
| `GET /api/companies/{ticker}` | Company info |
| `GET /api/filings/*` | Filing metadata |
| `GET /api/summaries/filing/{id}` | Fetch existing summary |
| `GET /api/summaries/filing/{id}/progress` | Generation progress |
| `GET /api/hot-filings` | Trending filings |
| `GET /api/trending-tickers` | Trending tickers |
| `GET /api/waitlist/*` | Waitlist signup |
| `GET /health`, `/health/detailed` | Health checks |
| `GET /metrics` | **Operational metrics — no auth** (see Finding F-10) |

---

## 5. Findings — Ranked by Severity

### F-01 · CRITICAL · No Email Verification
**Files:** `backend/app/routers/auth.py:206-249`, `backend/app/models/__init__.py`

`POST /api/auth/register` creates a user and immediately issues a valid JWT. There is no `email_verified` column on `User`, no verification token, no verification email sent, and no check that prevents unverified accounts from performing sensitive actions (generating AI summaries, creating Stripe checkout sessions). Any email address — valid or not — can be used to create an account and consume resources.

**Impact:** Fake-account abuse, resource consumption, inability to link social login to a verified email (account-takeover prerequisite), inability to send password resets reliably.

---

### F-02 · CRITICAL · No Password Reset Flow
**Files:** `backend/app/routers/auth.py` (only 4 endpoints), `backend/app/models/__init__.py`

There is no `POST /api/auth/forgot-password` endpoint, no `POST /api/auth/reset-password` endpoint, no `password_reset_token` or `password_reset_expires` column on `User`. A user who forgets their password has no self-service recovery path.

**Impact:** Users are permanently locked out. This blocks launch.

---

### F-03 · CRITICAL · AI Generation Endpoint Accessible to Guests Without Distributed Rate Limiting
**Files:** `backend/app/routers/summaries.py:189-196`, `backend/app/services/rate_limiter.py`

`POST /api/summaries/filing/{filing_id}/generate-stream` accepts unauthenticated requests (`get_current_user_optional`). The only guard is an in-memory rate limiter (5/60s per IP per Cloud Run instance). With multiple Cloud Run instances, the effective rate limit per IP is `5 × N instances`. The per-IP daily quota feature exists but is **disabled** (`ENABLE_GUEST_DAILY_QUOTA=False`).

Each AI generation call invokes the Google AI Studio API (Gemini), incurring real cost. An attacker with a pool of IPs (or spoofed X-Forwarded-For) can trigger unlimited AI calls.

**Impact:** Unbounded LLM API cost. A single coordinated request flood across distinct filing IDs with `force=True` could incur thousands of dollars in API charges.

---

### F-04 · CRITICAL · No Social Login Infrastructure
**Files:** `backend/requirements.txt`, `backend/app/models/__init__.py`, `backend/app/routers/`

No OAuth/OIDC libraries are installed. No `oauth_accounts` table exists. No Google or Apple OAuth routes exist in any router. `User.hashed_password` is `NOT NULL`, which prevents social-only accounts at the database level. This is an expected finding (not a regression), but it is the primary gap to be filled by this project.

**Impact:** Blocks the launch requirement of Google + Apple sign-in.

---

### F-05 · HIGH · In-Memory Rate Limiter Ineffective in Production
**Files:** `backend/app/services/rate_limiter.py`, `backend/app/routers/auth.py:21-22`

All rate limiters (`LOGIN_LIMITER`, `REGISTER_LIMITER`, `SUMMARY_LIMITER`) use in-process `collections.deque` state. Cloud Run scales horizontally — each instance has independent state. An attacker who sends requests to N instances gets N× the allowed rate. Since Redis is disabled in production (`SKIP_REDIS_INIT=true`), there is no shared state store.

**Impact:** Login brute-force, credential stuffing, and mass registration attacks at 10N attempts/minute/IP.

---

### F-06 · HIGH · No Token Revocation
**Files:** `backend/app/routers/auth.py:292-296`

`POST /api/auth/logout` clears the client-side cookie but **does not invalidate the JWT**. Any token that was extracted from the cookie (e.g. from the response body, from a XSS payload, from a compromised proxy) remains valid for the full 7-day lifetime. There is no token blocklist and no refresh/rotation mechanism.

**Impact:** Post-logout session hijacking. Stolen tokens cannot be revoked short of rotating `SECRET_KEY` (which invalidates all sessions globally).

---

### F-07 · HIGH · Password Policy Violates NIST SP 800-63B / OWASP ASVS v5
**Files:** `backend/app/routers/auth.py:35-46`, `backend/app/config.py:62`

The password validator requires lowercase + uppercase + digit (composition rules) in addition to the 12-character minimum:

```python
if not any(char.islower() for char in value):
    raise ValueError("Password must include at least one lowercase letter.")
if not any(char.isupper() for char in value):
    raise ValueError("Password must include at least one uppercase letter.")
if not any(char.isdigit() for char in value):
    raise ValueError("Password must include at least one number.")
```

NIST SP 800-63B §5.1.1.2 and OWASP ASVS v5 §2.1 explicitly prohibit arbitrary composition rules. They reduce effective password entropy by encouraging predictable patterns (e.g. `Password1`) and frustrate users, increasing the rate of reuse from breach databases.

**Impact:** Weaker security posture than a length-only policy; OWASP compliance gap.

---

### F-08 · HIGH · Email Enumeration on Registration
**Files:** `backend/app/routers/auth.py:222-226`

```python
if existing_user:
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Email already registered"   # ← explicit enumeration
    )
```

An attacker can enumerate whether a given email is registered by calling `POST /api/auth/register`. The `login` endpoint correctly returns `"Incorrect email or password"` (opaque), but the `register` endpoint leaks existence. Combined, an attacker can distinguish "email registered + wrong password" from "email not registered."

**Impact:** User email enumeration. Enables targeted credential stuffing and phishing.

---

### F-09 · HIGH · JWT Subject (`sub`) Is Email Address
**Files:** `backend/app/routers/auth.py:247`, `backend/app/routers/auth.py:149-155`

```python
access_token = create_access_token(data={"sub": user.email})
# ...
email: str = payload.get("sub")
user = db.query(User).filter(User.email == email).first()
```

Using email as `sub` has two problems:
1. Email is PII — it is now encoded (base64, not encrypted) in the JWT and visible to any party that holds the token.
2. If a user changes their email address, all outstanding tokens (up to 7 days old) break silently because the `sub` no longer matches any user.

Best practice is `sub = str(user.id)` (or UUID), with email only as a non-identifier claim.

---

### F-10 · MEDIUM · `/metrics` Endpoint Has No Authentication
**Files:** `backend/main.py:450-463`

`GET /metrics` returns request counts, error rates, cache statistics, circuit breaker state, thread pool details, and database pool checkout counts — with no authentication required. This leaks operational intelligence to an unauthenticated caller.

**Impact:** Moderate operational intelligence leak. Low direct exploitability, but aids reconnaissance.

---

### F-11 · MEDIUM · `Cache-Control` Missing on Auth Responses
**Files:** `backend/main.py:199-210`

Auth endpoints (`/api/auth/login`, `/api/auth/register`, `/api/auth/me`) do not set `Cache-Control: no-store`. Tokens returned in JSON response bodies could be cached by intermediate proxies or browser cache.

**Impact:** Potential token disclosure via cache. Low likelihood in practice given HTTPS, but a compliance gap.

---

### F-12 · MEDIUM · Token Returned in Response Body (Redundant Dual Transport)
**Files:** `backend/app/routers/auth.py:249`, `frontend/features/auth/api/auth-api.ts`

Login and register return `{"access_token": "...", "token_type": "bearer"}` **in addition** to setting the httpOnly cookie. The frontend does not appear to store the body token (React Query discards it), but the dual-transport pattern is a hazard: any code that accidentally stores `response.data.access_token` in localStorage would create an XSS-exploitable token store.

**Impact:** Low currently, but increases attack surface as features are added.

---

### F-13 · MEDIUM · No Audit Logging for Auth Events
**Files:** `backend/app/models/audit_log.py`, `backend/app/routers/auth.py`

The `AuditLog` table and `audit_service` exist and are wired for GDPR events (`user_deleted`, `data_exported`). However, auth events — login success, login failure, registration, logout, password reset — are not logged. OWASP ASVS v5 §7.2 requires logging of authentication events including failures.

**Impact:** No forensic trail for account compromise, brute-force detection, or compliance audits.

---

### F-14 · MEDIUM · bcrypt Version Not Pinned
**Files:** `backend/requirements.txt:17`

```
passlib[bcrypt]==1.7.4
```

`passlib` installs `bcrypt` as an unversioned dependency. `auth.py` imports `bcrypt` directly (`import bcrypt`) and calls `bcrypt.gensalt()` with no explicit `rounds` parameter, defaulting to 12. A future dependency resolution could install a different bcrypt version that changes default behavior or has a known vulnerability.

**Impact:** Low currently. Should be pinned for reproducibility.

---

### F-15 · LOW · `COOKIE_SAMESITE = "lax"` in Cross-Origin Setup
**Files:** `backend/app/config.py:84`

The cookie is `SameSite=lax`. The frontend (`earningsnerd.io`) sends requests to a **different subdomain** (`api.earningsnerd.io`). For cross-origin `fetch`/XHR with `credentials: include`, the browser will include `SameSite=lax` cookies **only if the cookie was set by the target origin** — which it was (the API sets the cookie). This is fine for normal flows.

However, Apple Sign In uses `response_mode=form_post`, delivering the callback as a cross-site POST to the backend. `SameSite=lax` will **block the session cookie** on this POST, breaking any state/nonce verification stored in a cookie. This requires `SameSite=None; Secure` for the Apple callback flow, or a server-side nonce store.

---

### F-16 · LOW · No `HttpOnly` Flag Verification in Frontend Middleware
**Files:** `frontend/middleware.ts:24-33`

The Next.js middleware checks `request.cookies.has('earningsnerd_access_token')` for route protection. This is a **presence check only** — it does not validate the token. A user who manually sets a cookie with that name bypasses the middleware redirect (they will still hit a 401 from the backend on any actual API call, but the frontend will render the protected page skeleton before that occurs).

**Impact:** Very low — cosmetic only. Backend validation is the real gate. Noted for completeness.

---

### F-17 · INFO · Integer Primary Key on `users` Table
**Files:** `backend/app/models/__init__.py`

The `users` table uses `INTEGER` PK. The implementation spec calls for a UUID PK to prevent ID enumeration (`GET /api/users/1`, `GET /api/users/2`, etc.) and to provide stable opaque identifiers for external systems (Stripe, PostHog). Migrating from integer to UUID after data exists requires careful migration planning.

**Recommendation:** Change to UUID before any production users are in the database. At waitlist stage, there are no production user accounts, making this a safe migration window.

---

## 6. Blockers and Unknowns

### 6.1 Decisions Required from You

| # | Question | Why it blocks architecture |
|---|---|---|
| Q1 | Should the `/api/summaries/filing/{id}/generate-stream` endpoint require authentication after launch (no more guest generation), or remain guest-accessible with proper distributed rate limiting? | Determines whether auth gates AI cost or just features. |
| Q2 | Do you want to allow users to link multiple social providers to one account (e.g. Google + Apple + password on same email)? | Determines whether `oauth_accounts` table is needed or a simpler `provider`/`provider_id` on `users` suffices. |
| Q3 | Email verification flow: send verification on registration and block sensitive actions until verified, or allow immediate access with a grace period? | Affects UX at registration and complexity of email infrastructure. |
| Q4 | For the `users` PK: migrate to UUID now (while no production data exists) or keep integer and add a `public_id UUID` column? | There are no production user accounts today — this is the safest migration window. UUID migration after launch is painful. |

### 6.2 External Credentials / Console Actions Needed from You

These cannot be completed from the codebase alone:

| Item | Where | Notes |
|---|---|---|
| Apple Developer Program membership | developer.apple.com | Required for Sign in with Apple web integration |
| Apple Services ID (web `client_id`) | Apple Dev Console | Distinct from iOS App ID |
| Apple private key (ES256 `.p8` file) | Apple Dev Console | Used to mint client-secret JWTs; **max 6-month validity** |
| Apple domain verification files | Must be served at `/.well-known/apple-developer-domain-association.txt` | Apple requires HTTPS on the registered domain before enabling Sign In |
| Google Cloud OAuth 2.0 client | Google Cloud Console → Credentials | Needs authorized redirect URIs for localhost + production |
| Google OAuth consent screen | Google Cloud Console | Domain verification required for production; may take days |
| Resend sending domain configuration | resend.com | For email verification and password reset emails; domain must be verified |
| Apple email relay domain registration | developer.apple.com → Sign in with Apple → Email Sources | Required if sending transactional email to Apple private relay addresses |

### 6.3 Localhost / Dev Environment Gap for Apple

Apple Sign In does **not** allow `http://localhost` as a redirect URI. Options for local development:
1. Use a tunnelled HTTPS URL (ngrok, Cloudflare Tunnel, or Vercel's dev tunnel).
2. Maintain a separate Apple Services ID for development pointing to the tunnel domain.
3. Use a wildcard subdomain + self-signed cert with hosts file trick.

This must be decided before Phase 3 to include in the dev setup documentation.

---

## Summary Table

| Finding | Severity | Blocks Launch? | Effort to Fix |
|---|---|---|---|
| F-01 No email verification | CRITICAL | Yes | Medium |
| F-02 No password reset | CRITICAL | Yes | Medium |
| F-03 Unauth AI generation + no distributed RL | CRITICAL | Yes (cost risk) | Medium |
| F-04 No social login infrastructure | CRITICAL | Yes (requirement) | High |
| F-05 In-memory rate limiter | HIGH | Partial | Low–Medium |
| F-06 No token revocation | HIGH | No | Medium |
| F-07 Password composition rules (OWASP) | HIGH | No | Low |
| F-08 Email enumeration on register | HIGH | No | Low |
| F-09 JWT sub = email | HIGH | No | Low |
| F-10 `/metrics` no auth | MEDIUM | No | Low |
| F-11 No Cache-Control on auth | MEDIUM | No | Low |
| F-12 Token in response body | MEDIUM | No | Low |
| F-13 No auth event audit logs | MEDIUM | No | Low |
| F-14 bcrypt version unpinned | MEDIUM | No | Trivial |
| F-15 SameSite=lax + Apple form_post | LOW | Partial | Low |
| F-16 Middleware presence-only check | LOW | No | Trivial |
| F-17 Integer PK on users | INFO | No (but migrate now) | Low |

**Architecture note:** Findings F-01 through F-04 will be resolved by the Phase 3 implementation regardless of which candidate architecture is chosen. F-05 (distributed rate limiting) may require re-enabling Redis or adopting Cloud Armor — this depends on the Phase 2 recommendation.
