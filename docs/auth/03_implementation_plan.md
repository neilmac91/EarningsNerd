# Auth Implementation Plan — EarningsNerd.io
**Date:** 2026-06-12  
**Phase:** 3 of 3 — Implementation  
**Architecture:** Extend existing FastAPI auth — Authlib for Google/Apple OAuth, argon2id passwords

---

## Pre-Implementation Decisions (Confirmed)

| Question | Answer | Impact |
|---|---|---|
| Guest AI generation | Keep open | Distributed rate limiting deferred; Cloud Armor documented |
| Multi-provider linking | `oauth_accounts` table (proper multi-provider) | Users can link Google + Apple + password to one account |
| Email verification | Strict | Sensitive actions gated on `email_verified = true` |
| UUID PK migration | Yes — now, while no production users exist | Schema migration in Increment 1 |
| Apple Developer Program | Not yet — user purchasing | Apple Sign In in Increment 4 (after account setup) |
| Local dev for Apple | Cloudflare Tunnel → `dev.earningsnerd.io` | Document in Increment 4 runbook |

---

## Implementation Increments

### Increment 1 — Schema Foundation + Core Auth Hardening ← CURRENT
*Independently testable: existing login/register flow continues to work; new fields added safely.*

- [ ] SQL migration: UUID PK on `users`, `email_verified`, `password_reset_*`, nullable `hashed_password`, `last_login_at`
- [ ] SQL migration: create `oauth_accounts` table
- [ ] SQLAlchemy ORM models updated to match new schema
- [ ] argon2id replaces bcrypt for new passwords (bcrypt fallback for existing hashes)
- [ ] JWT `sub` changed from email to `str(user.id)`
- [ ] Remove password composition rules (keep length ≥ 8 per OWASP; frontend min stays 12 as UX)
- [ ] Anti-enumeration on register: opaque response matching login timing
- [ ] `Cache-Control: no-store` on all auth endpoint responses
- [ ] Auth event audit logging wired in

### Increment 2 — Email Verification + Password Reset
*Independently testable: can verify email flow and reset flow end-to-end.*

- [ ] `POST /api/auth/verify-email` — validate token, set `email_verified = true`
- [ ] `POST /api/auth/resend-verification` — send new verification email
- [ ] `POST /api/auth/forgot-password` — generate reset token, email link
- [ ] `POST /api/auth/reset-password` — validate token, hash new password, invalidate token
- [ ] Registration: send verification email immediately after account creation
- [ ] Gate summary generation + Stripe checkout behind `email_verified`
- [ ] Frontend pages: verify-email landing page, forgot-password form, reset-password form

### Increment 3 — Google OAuth (OIDC)
*Independently testable: Google sign-in flow works end-to-end in dev.*

- [ ] Google Cloud Console: create OAuth 2.0 client, configure redirect URIs
- [ ] `GET /api/auth/google` — redirect to Google with PKCE + nonce
- [ ] `GET /api/auth/google/callback` — verify id_token, create/link account
- [ ] Account linking logic (email match + `email_verified` guard)
- [ ] Frontend: "Sign in with Google" button
- [ ] Local dev: `http://localhost:3000` callback works (Google allows localhost)

### Increment 4 — Apple Sign In (requires Apple Developer membership first)
*Independently testable: Apple sign-in flow works end-to-end in dev tunnel.*

- [ ] Apple Developer Console setup (Services ID, private key, domain verification)
- [ ] Cloudflare Tunnel dev setup: `dev.earningsnerd.io` → `localhost:8000`
- [ ] ES256 client-secret JWT generation + rotation runbook
- [ ] `GET /api/auth/apple` — redirect to Apple
- [ ] `POST /api/auth/apple/callback` — handle `form_post`, verify id_token
- [ ] First-authorization name/email capture (only returned once)
- [ ] Apple private relay email handling
- [ ] Frontend: "Sign in with Apple" button (must meet Apple HIG)
- [ ] Key rotation: calendar reminder procedure

### Increment 5 — Session Hardening + Rate Limiting
*Can be done in parallel with Increment 4.*

- [ ] Shorten access token to 1 hour; add 30-day refresh token (stored in DB)
- [ ] `POST /api/auth/refresh` — rotate refresh token, issue new access token
- [ ] `POST /api/auth/logout` — invalidate refresh token in DB
- [ ] Cloud Armor rate limiting documentation (GCP Console steps for production)
- [ ] `GET /metrics` — add `Depends(get_current_user)` + admin check
- [ ] Remove `access_token` from login/register response bodies

---

## 3.1 Data Model

### users table changes

```sql
-- Migration: 20260612_auth_foundation.sql
-- SAFE: zero production user accounts exist at migration time.

-- 1. Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Drop all user FK constraints (referencing integer users.id)
ALTER TABLE watchlist        DROP CONSTRAINT watchlist_user_id_fkey;
ALTER TABLE user_usage       DROP CONSTRAINT user_usage_user_id_fkey;
ALTER TABLE user_searches    DROP CONSTRAINT user_searches_user_id_fkey;
ALTER TABLE saved_summaries  DROP CONSTRAINT saved_summaries_user_id_fkey;
ALTER TABLE audit_logs       DROP CONSTRAINT IF EXISTS audit_logs_user_id_fkey;

-- 3. Truncate user-related tables (no production data)
TRUNCATE TABLE watchlist, user_usage, user_searches, saved_summaries, audit_logs CASCADE;

-- 4. Migrate users.id to UUID
ALTER TABLE users DROP CONSTRAINT users_pkey;
ALTER TABLE users DROP COLUMN id;
ALTER TABLE users ADD COLUMN id UUID PRIMARY KEY DEFAULT gen_random_uuid();

-- 5. Add new auth columns
ALTER TABLE users
  ADD COLUMN email_verified          BOOLEAN      NOT NULL DEFAULT FALSE,
  ADD COLUMN password_reset_token    TEXT,
  ADD COLUMN password_reset_expires  TIMESTAMPTZ,
  ADD COLUMN last_login_at           TIMESTAMPTZ;

-- 6. Make hashed_password nullable (social-only accounts have no password)
ALTER TABLE users ALTER COLUMN hashed_password DROP NOT NULL;

-- 7. Migrate FK columns on dependent tables to UUID
ALTER TABLE watchlist       ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
ALTER TABLE user_usage      ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
ALTER TABLE user_searches   ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
ALTER TABLE saved_summaries ALTER COLUMN user_id TYPE UUID USING gen_random_uuid();
ALTER TABLE audit_logs      ALTER COLUMN user_id TYPE UUID;

-- 8. Restore FK constraints
ALTER TABLE watchlist       ADD CONSTRAINT watchlist_user_id_fkey       FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_usage      ADD CONSTRAINT user_usage_user_id_fkey      FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE user_searches   ADD CONSTRAINT user_searches_user_id_fkey   FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;
ALTER TABLE saved_summaries ADD CONSTRAINT saved_summaries_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

-- 9. Index on reset token for fast lookup
CREATE INDEX CONCURRENTLY idx_users_password_reset_token
  ON users (password_reset_token)
  WHERE password_reset_token IS NOT NULL;
```

### oauth_accounts table (new)

```sql
CREATE TABLE oauth_accounts (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  provider            TEXT NOT NULL,                 -- 'google' | 'apple'
  provider_account_id TEXT NOT NULL,                 -- provider's sub claim
  provider_email      TEXT,                          -- email from provider (may be relay)
  created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (provider, provider_account_id)
);

CREATE INDEX idx_oauth_accounts_user_id ON oauth_accounts (user_id);
CREATE INDEX idx_oauth_accounts_provider_email ON oauth_accounts (provider, provider_email)
  WHERE provider_email IS NOT NULL;
```

### waitlist migration script (for later, Increment 2)

```python
# backend/scripts/migrate_waitlist_to_users.py
# Copies waitlist emails to a reference table with provenance.
# Does NOT create user accounts — just preserves email + joined_at + priority_score.
# Run manually before launch, after schema is in place.
```

---

## 3.2 Account-Linking Policy

All social login callbacks follow this decision tree:

```
Incoming OAuth callback (provider, provider_account_id, provider_email, email_verified)
│
├─► Does oauth_accounts record exist for (provider, provider_account_id)?
│   YES → user found → log in → done
│
└─► No existing oauth_accounts record
    │
    ├─► Is provider_email verified by provider? (email_verified = true)
    │   NO → create new user with provider email (possibly a relay address)
    │         create oauth_accounts record → log in
    │
    └─► Provider asserts email_verified = true
        │
        ├─► Does a users record exist with this email AND users.email_verified = true?
        │   YES → LINK: create oauth_accounts record pointing to existing user → log in
        │          (sends "we linked your accounts" email for transparency)
        │
        └─► No existing verified user with this email
            → create new user
            → create oauth_accounts record → log in
```

**Apple private relay addresses** (`@privaterelay.appleid.com`): These will never match an existing `users.email`. Always treated as new account creation. Manual linking via dashboard (Settings → "Connect accounts") planned as a post-launch feature.

**Social-first user setting a password later:** `PUT /api/users/password` — requires current session, hashes and stores argon2id hash, sets `email_verified = true` (provider already verified).

**Password user adding Google/Apple later:** Covered by the linking flow above — if existing verified email matches, link and add `oauth_accounts` record.

**Duplicate accounts (same person, different provider, different email):** Not auto-merged. User must contact support or use the future "link accounts" settings page.

---

## 3.3 Sign in with Apple — Implementation Specifics

### Apple Developer Console Setup (one-time, requires membership)

1. Create an **App ID** with "Sign in with Apple" capability (even if there's no iOS app — required as the parent entity).
2. Create a **Services ID** — this is the web `client_id`. Set it to e.g. `io.earningsnerd.web`.
3. Register domains: `earningsnerd.io` (production) and `dev.earningsnerd.io` (local dev via Cloudflare Tunnel).
4. Add redirect URIs: `https://api.earningsnerd.io/api/auth/apple/callback` and `https://dev.earningsnerd.io/api/auth/apple/callback`.
5. Generate a **private key** (ES256, `.p8` file). Download it **once** — it cannot be re-downloaded.
6. Store in GCP Secret Manager as `APPLE_PRIVATE_KEY` (multiline value).
7. Note the **Key ID** and **Team ID** — needed for JWT minting.

### ES256 Client-Secret JWT (must be refreshed every ≤ 6 months)

```python
# backend/app/services/apple_auth.py
import jwt as pyjwt  # or authlib's JWT utilities
from datetime import datetime, timedelta

def generate_apple_client_secret(
    team_id: str,
    client_id: str,
    key_id: str,
    private_key_pem: str,
) -> str:
    now = datetime.utcnow()
    payload = {
        "iss": team_id,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=180)).timestamp()),  # 6 months max
        "aud": "https://appleid.apple.com",
        "sub": client_id,
    }
    return pyjwt.encode(payload, private_key_pem, algorithm="ES256", headers={"kid": key_id})
```

**Rotation procedure (calendar reminder every 5.5 months):**
1. Go to developer.apple.com → Certificates, IDs & Profiles → Keys
2. Revoke the old key; create a new one
3. Download the new `.p8` file
4. Update `APPLE_PRIVATE_KEY` in GCP Secret Manager
5. Update `APPLE_KEY_ID` in Secret Manager
6. Redeploy Cloud Run service (secrets are mounted at startup; a new revision picks up the updated value)
7. Set a new calendar reminder for 5.5 months out

### First-Authorization Name/Email Capture

Apple only returns `user.name` and `user.email` on the **first** authorization. These must be persisted immediately in the callback handler.

```python
# In the Apple callback:
# user_data is present only on first auth; absent on subsequent logins
user_info = id_token_payload  # always present
first_auth_data = request.form.get("user")  # present ONLY on first auth; parse as JSON
if first_auth_data:
    user_json = json.loads(first_auth_data)
    given_name = user_json.get("name", {}).get("firstName", "")
    family_name = user_json.get("name", {}).get("lastName", "")
    full_name = f"{given_name} {family_name}".strip() or None
```

**Recovery path if name was missed:** The user must go to their iPhone/Mac → Settings → Apple ID → Password & Security → Sign in with Apple → [Your app] → Stop Using Apple ID → revoke. On next sign-in, Apple prompts again. Document this in the support FAQ.

### `form_post` Callback and SameSite Cookie

Apple's `response_mode=form_post` delivers the callback as a cross-site POST. This means:
- **State/nonce cannot be stored in `SameSite=Lax` cookies** — the browser blocks that cookie on the cross-site POST
- Solution: store the nonce/state in the **database** or **server-side session** keyed by a random token placed in a `SameSite=None; Secure` short-lived cookie (or simply pass state through the session store)
- Simplest approach: store `apple_auth_state` in a short-lived DB table or Redis; look it up on callback

---

## 3.4 Sign in with Google — Implementation Specifics

### Google Cloud Console Setup

1. APIs & Services → Credentials → Create OAuth 2.0 Client ID
2. Application type: **Web application**
3. Authorized redirect URIs:
   - `http://localhost:8000/api/auth/google/callback` (local dev — Google allows plain HTTP localhost)
   - `https://api.earningsnerd.io/api/auth/google/callback` (production)
4. OAuth consent screen: External, app name "EarningsNerd", scopes: `openid email profile`
5. For testing (unverified app): add test users. For production: submit for Google verification.

### OIDC Flow with PKCE (Authlib)

```python
from authlib.integrations.starlette_client import OAuth

oauth = OAuth()
oauth.register(
    name="google",
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_id=settings.GOOGLE_CLIENT_ID,
    client_secret=settings.GOOGLE_CLIENT_SECRET,
    client_kwargs={"scope": "openid email profile"},
)
```

Server-side id_token verification (all claims required):
```python
# Verify: iss in ["https://accounts.google.com", "accounts.google.com"]
# Verify: aud == settings.GOOGLE_CLIENT_ID
# Verify: exp > now
# Verify: nonce == stored nonce (prevents replay)
# Use: email only if email_verified == true
```

---

## 3.5 Email + Password — Security Baseline

### argon2id Password Hashing

```python
# requirements.txt addition: argon2-cffi>=23.1.0
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher(
    time_cost=3,       # OWASP 2023 recommendation
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

def get_password_hash(password: str) -> str:
    return _ph.hash(password)

def verify_password(plain: str, hashed: str) -> bool:
    # argon2id first (new hashes)
    if hashed.startswith("$argon2"):
        try:
            return _ph.verify(hashed, plain)
        except VerifyMismatchError:
            return False
    # bcrypt fallback (existing users)
    return _bcrypt_verify(plain, hashed)
```

Existing bcrypt hashes are verified as-is; argon2id is used for all new passwords and on password change. No forced re-hash migration needed at launch.

### Password Policy (OWASP ASVS v5 §2.1)

- Minimum length: **8 characters** (NIST/OWASP minimum — frontend can enforce a higher UX bar of 12)
- Maximum length: **128 characters** (prevent DoS via hashing)
- **No composition rules** (no required uppercase/lowercase/digit)
- **No character set restrictions**
- Breached-password check: flag for Increment 2+ (use `pwned-passwords` API or local k-anonymity hash set)

### Anti-Enumeration

Both register and login return identical error messages and use `hmac.compare_digest`-based timing-safe comparison to prevent timing attacks that distinguish "user exists" from "wrong password":

```python
# register: when email already exists
# Instead of: raise 400 "Email already registered"
# Do: silently succeed; send "you already have an account" email to that address
# Return HTTP 200 with generic message: "If that email is new, check your inbox."

# login: unchanged — "Incorrect email or password" is already opaque
```

### Email Verification Token

```python
import secrets, hashlib
from datetime import datetime, timedelta, timezone

def generate_verification_token() -> tuple[str, str]:
    """Returns (raw_token, hashed_token). Store hashed; send raw."""
    raw = secrets.token_urlsafe(32)
    hashed = hashlib.sha256(raw.encode()).hexdigest()
    return raw, hashed

# Expiry: 24 hours
# On verify: compare sha256(submitted_token) == users.email_verification_token_hash
# After use: clear token columns
```

### Password Reset Token

Same pattern as verification token:
- Single-use: clear token after first use
- Expiry: 1 hour
- Store only the SHA-256 hash in DB (never the raw token)
- Rate-limit reset requests: 3/hour/email (prevents email flooding)

---

## 3.6 Session Strategy

### Current (being replaced)

Single 7-day JWT. No refresh. No revocation.

### Target

| Token | Transport | Expiry | Revocable |
|---|---|---|---|
| **Access token** (JWT HS256) | httpOnly cookie `earningsnerd_access_token` | **1 hour** | Via refresh token invalidation |
| **Refresh token** (opaque, 64-byte random) | httpOnly cookie `earningsnerd_refresh_token` | **30 days** | Yes — stored in DB |

```sql
-- New table: refresh_tokens
CREATE TABLE refresh_tokens (
  id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,   -- sha256(raw_token)
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at TIMESTAMPTZ             -- set on logout or rotation
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens (user_id);
```

**Rotation with reuse detection:**
```python
# On POST /api/auth/refresh:
# 1. Hash the incoming refresh token
# 2. Look up in DB — must exist, not expired, not revoked
# 3. Mark old token as revoked (set revoked_at = now)
# 4. Issue new access token + new refresh token
# 5. If old token was already revoked → possible reuse attack → revoke ALL tokens for this user
```

**Logout:**
```python
# POST /api/auth/logout:
# Mark current refresh_token as revoked
# Clear both cookies
```

**Global logout ("sign out all devices"):**
```python
# DELETE all refresh_tokens for user_id
# Clear current cookies
```

### CSRF Protection

The existing `SameSite=Lax` cookie combined with the strict CORS `allow_origins` list provides CSRF protection for standard cross-origin fetch requests. This is because:
- `SameSite=Lax` blocks the cookie from being sent in cross-site `fetch`/XHR from any origin not in the CORS allow list
- The production CORS list only includes `earningsnerd.io` origins

The one exception: Apple's `form_post` callback is a cross-site POST. The CSRF mitigation for Apple is server-side nonce validation (stored in DB, not in a cookie).

### FastAPI Token Verification (updated for new sub claim)

```python
# auth.py — get_current_user() updated
payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], ...)
user_id: str = payload.get("sub")           # Now a UUID string
user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
```

---

## 3.7 Hardening and Operations

### Distributed Rate Limiting (Production Gap)

Redis is disabled in production. Options ranked by implementation effort:

| Option | Effort | Cost | Notes |
|---|---|---|---|
| **Cloud Armor** (recommended) | Low (GCP Console) | ~$5/month + usage | GCP WAF at Cloud Run ingress; rate limits by IP before traffic hits app |
| Re-enable Redis (Memorystore) | Medium | ~$40/month (1 GB) | Proper distributed cache; also fixes other degraded-mode warnings |
| Keep in-memory (current) | None | Free | Acceptable for launch if Cloud Armor is in place |

**Recommended for launch:** Implement Cloud Armor rate limiting (the GCP Console runbook is in the appendix below). The in-memory limiter provides defense-in-depth within each instance. Together they are sufficient for launch scale.

### Security Headers Update

Add `Cache-Control: no-store` to all auth endpoint responses:
```python
# In auth router, add to each response:
response.headers["Cache-Control"] = "no-store"
response.headers["Pragma"] = "no-cache"
```

### Auth Event Audit Logging

Wire to existing `AuditLog` table:

```python
# Events to log: login_success, login_failure, register, logout,
#                password_reset_requested, password_reset_completed,
#                email_verified, oauth_linked, oauth_login
from app.services.audit_service import log_auth_event
```

### Secrets in GCP Secret Manager

New secrets to add before Increment 3/4:
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`
- `APPLE_TEAM_ID`, `APPLE_CLIENT_ID`, `APPLE_KEY_ID`, `APPLE_PRIVATE_KEY`
- `EMAIL_VERIFICATION_SECRET` (for HMAC-signed email verification links, alternative to DB tokens)

---

## 3.8 Test Plan

### Unit Tests (new files)

```
backend/tests/unit/test_auth_tokens.py
  - argon2id hash + verify
  - bcrypt fallback verify
  - verification token generation + hash comparison
  - JWT sub as UUID round-trip
  - Token expiry validation

backend/tests/unit/test_oauth_linking.py
  - link to existing verified email → success
  - link to existing unverified email → new account
  - duplicate provider_account_id → returns existing user
  - Apple relay email → new account (never matches existing)
```

### Manual Test Checklist (pre-launch)

| # | Test | Expected Result |
|---|---|---|
| 1 | Register with new email | Verification email sent; account created; NOT logged in until verified (strict mode) |
| 2 | Click verification link | `email_verified = true`; logged in; redirected to dashboard |
| 3 | Register with duplicate email | 200 OK (same as new email — anti-enumeration); "you already have an account" email sent to existing address |
| 4 | Login with wrong password | 401 "Incorrect email or password" (no timing difference) |
| 5 | Forgot password flow | Email arrives; link works once; link rejected on second use; link rejected after 1 hour |
| 6 | First-time Google sign-in | Account created; `email_verified = true` (Google assertion); logged in |
| 7 | Google sign-in with email matching existing verified account | Accounts linked; existing account logged in |
| 8 | First-time Apple sign-in | Name + email captured; account created; logged in |
| 9 | Apple private relay email | New account created (relay address stored); no match to existing accounts |
| 10 | Returning Apple user (no name in payload) | Existing `oauth_accounts` record found; logged in |
| 11 | Login → logout → use old access token | Old access token rejected (expired within 1 hour); old refresh token rejected (revoked) |
| 12 | Session expiry (1 hour) | Access token expires; refresh automatically issues new pair |
| 13 | Refresh token reuse (replay attack) | All user's sessions revoked; user logged out everywhere |
| 14 | Generate AI summary before email verified | 403 "Please verify your email first" |
| 15 | Add Google to existing password account | `oauth_accounts` record created; can log in via Google |

---

## 3.9 Rollout Strategy

### Feature Flag (waitlist mode currently active)

`WAITLIST_MODE=false` is already set in `frontend/vercel.json`. The auth rollout doesn't need a new feature flag — the waitlist is being replaced by auth. The migration path:
1. Deploy schema changes (Increment 1) with zero downtime (no production users)
2. Deploy auth hardening (same deploy)
3. Flip `WAITLIST_MODE=false` in Vercel after Google OAuth is live (Increment 3)
4. Apple Sign In can be added live after launch without disruption

### Go-Live Checklist

- [ ] GCP Secret Manager: `SECRET_KEY` (64+ random chars), all OAuth client IDs/secrets
- [ ] Cloud Armor: rate limiting rules configured on Cloud Run ingress
- [ ] Google OAuth consent screen: verified (submit to Google for production approval)
- [ ] Apple Developer: domain `earningsnerd.io` verified, Services ID registered, redirect URIs confirmed
- [ ] Resend: `earningsnerd.io` domain verified for sending; SPF/DKIM configured
- [ ] Apple email relay: `no-reply@earningsnerd.io` (or chosen from address) registered in Apple Dev Console
- [ ] `APPLE_PRIVATE_KEY` calendar reminder set for 5.5 months from key creation date
- [ ] Auth event monitoring: PostHog dashboard or Sentry alert on auth failure rate > 5%
- [ ] Run manual test checklist items 1–15

---

## Appendix: Cloud Armor Rate Limiting Setup (GCP Console)

*One-time setup, no code changes required.*

1. GCP Console → Network Security → Cloud Armor → Create policy
2. Policy type: **Backend security policy**
3. Add rule:
   - Condition: `request.path.matches('/api/auth/login')` OR `request.path.matches('/api/auth/register')`
   - Action: **Rate-based ban** — threshold 30 req/min/IP; ban duration 60s
4. Add rule:
   - Condition: `request.path.matches('/api/auth/forgot-password')`
   - Action: Rate-based ban — threshold 3 req/min/IP; ban duration 3600s
5. Attach policy to the Cloud Run load balancer backend service
6. Test: `ab -n 100 -c 10 https://api.earningsnerd.io/api/auth/login` should return 429s after threshold

---

*Implementation begins with Increment 1 immediately following this document.*
