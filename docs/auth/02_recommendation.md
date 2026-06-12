# Auth Architecture Recommendation — EarningsNerd.io
**Date:** 2026-06-12  
**Phase:** 2 of 3 — Architecture Decision  
**Status:** Awaiting approval before Phase 3 begins

---

## The Single Most Important Constraint: Cross-Boundary Session Validation

Before evaluating any candidate, this constraint must be stated precisely:

**The FastAPI backend at `api.earningsnerd.io` must verify the identity of every request from the Next.js frontend at `earningsnerd.io`.** This verification must happen on every protected request — it cannot be delegated to the Next.js layer, because Next.js does not serve the API. Any architecture where the auth authority lives somewhere other than FastAPI must solve this cross-boundary validation problem cleanly or it is a non-starter.

The current implementation solves this elegantly: FastAPI issues an HS256 JWT, stores it as an httpOnly cookie, and verifies it on every request via `get_current_user()`. The cookie is sent cross-origin because `withCredentials: true` is set on the Axios client. This works today and costs nothing to run. The goal is to extend it to Google + Apple, not to replace it.

---

## Candidate Evaluation

### Candidate A — Managed Identity Provider (Clerk / Auth0 / Firebase / Supabase Auth)

All managed providers share the same fundamental cross-boundary architecture: the provider issues tokens, the Next.js frontend holds them, and the FastAPI backend must verify them. The verification mechanism differs by provider:

| Provider | FastAPI Verification Method | Cross-Boundary Verdict |
|---|---|---|
| **Clerk** | RS256 JWT → verify against Clerk's JWKS endpoint | Clean. `PyJWT` + JWKS. One HTTP call to fetch keys (cached). |
| **Auth0** | RS256 JWT → Auth0 JWKS | Clean. Same as Clerk. |
| **Firebase / GCP Identity Platform** | Firebase ID token → Google JWKS (`/robot/v1/metadata/x509/`) | Clean. `google-auth` Python lib handles it. |
| **Supabase Auth (managed)** | HS256 JWT with shared Supabase JWT secret | Clean. Same pattern as current FastAPI JWT. But user data lives in Supabase's Postgres, not your Cloud SQL. |

The JWKS verification approach works, but introduces a new operational dependency: **FastAPI must reach the provider's JWKS endpoint on every cold cache miss.** This is a 50–150 ms HTTP call. Libraries cache the keys (typically 1-hour TTL), so it is rarely a hot-path problem, but it is a dependency that can fail.

More importantly, using a managed provider creates a **parallel user identity**: the provider issues a user ID (Clerk's `user_abc123`, Firebase's UID, etc.) that becomes the canonical identity in the auth system. Your `users` table must store this as a foreign key (`clerk_id`, `firebase_uid`). Your Stripe `customer_id` is attached to your `users.id`. Mapping `clerk_id → users.id → stripe_customer_id` adds an indirection layer that must be maintained forever.

#### Clerk — Detailed Scoring

| Criterion | Score | Notes |
|---|---|---|
| Cross-boundary validation | ✅ Good | RS256 JWKS; well-documented FastAPI integration |
| Apple support | ✅ Excellent | First-party, handles 6-month key rotation automatically |
| Cost at 1k MAU | ✅ Free | Free up to 10,000 MAU |
| Cost at 10k MAU | ✅ Free | At boundary of free tier |
| Cost at 100k MAU | ❌ Expensive | ~$1,800/month ($0.02/MAU × 90k overage) |
| Vendor lock-in | ⚠️ Moderate | Password hashes exportable (bcrypt). Provider IDs are Clerk-specific. |
| Data portability | ⚠️ Moderate | Users exportable but migration requires re-mapping all IDs |
| Stripe-readiness | ✅ Good | Store `stripe_customer_id` in your own DB using Clerk `userId` as FK |
| Solo-dev burden | ✅ Low | Dashboard handles OAuth app setup; no key rotation |
| Email infra | ✅ Included | Clerk handles verification + reset emails |
| **Risk** | | At 100k MAU: ~$1,800/mo is a significant SaaS cost; pricing-trap if growth outpaces revenue |

#### Auth0 — Brief Assessment

Similar cross-boundary story to Clerk but with a more complex dashboard, enterprise-oriented pricing, and limited data portability (password hashes are not exportable — you cannot migrate users away without forcing password resets). **Eliminated** on data portability grounds alone.

#### Firebase Auth / GCP Identity Platform — Detailed Scoring

| Criterion | Score | Notes |
|---|---|---|
| Cross-boundary validation | ✅ Good | Google-signed JWTs; `google-auth` Python library is mature |
| Apple support | ✅ Good | First-party; handles key rotation |
| Cost at 1k MAU | ✅ Free | Free up to 10k/month (Identity Platform) |
| Cost at 10k MAU | ✅ Free | At boundary |
| Cost at 100k MAU | ❌ Expensive | ~$1,500/month (social login tier) |
| GCP integration | ✅ Excellent | Same project; IAM integration; Cloud Run service account access |
| Vendor lock-in | ⚠️ High | Firebase SDK deeply embedded in frontend; Firebase user IDs are Google-specific |
| Data portability | ⚠️ Moderate | Password hashes exportable in Firebase's own format (scrypt variant); not bcrypt |
| Stripe-readiness | ✅ Good | Store in your DB with Firebase UID as FK |
| Solo-dev burden | ✅ Low | Firebase handles all OAuth; Admin SDK for server-side |
| Email infra | ✅ Included | Firebase Auth email templates (customisable) |
| **Risk** | | Firebase SDK is JavaScript-heavy; App Router integration has friction. Exported password hashes use Firebase's modified scrypt — not re-importable to standard bcrypt without re-hashing. |

---

### Candidate B — Auth.js (NextAuth v5)

Auth.js v5 is designed for Next.js. It handles Google and Apple OAuth providers natively, including Apple's `form_post` response mode. The cross-boundary validation problem is the key friction here.

**The cross-boundary problem with Auth.js:**

Auth.js runs inside Next.js. Its sessions are either:
1. **JWE-encrypted JWTs** (default): Encrypted with `AUTH_SECRET` using `jose` A256GCM. FastAPI cannot decrypt these without reimplementing Auth.js's specific JWE format. Not viable without a shim.
2. **Database sessions**: Auth.js writes a `sessions` table. FastAPI would query this table to verify a session token. This creates direct schema coupling — FastAPI's `get_current_user()` would query Auth.js's session table, not your `users` table.
3. **Custom JWT bridge** (viable but complex): Add a `callbacks.jwt` hook that mints a second HS256/RS256 token specifically for FastAPI. Next.js holds both the Auth.js session and this bridge token; only the bridge token is sent to FastAPI.

```typescript
// In auth.config.ts — the custom bridge pattern
callbacks: {
  async jwt({ token, user }) {
    if (user) {
      // Mint a separate HS256 JWT FastAPI can verify
      token.api_token = sign({ sub: user.id }, process.env.FASTAPI_JWT_SECRET)
    }
    return token
  },
  async session({ session, token }) {
    session.api_token = token.api_token
    return session
  }
}
```

This is implementable but adds a bespoke secret-sharing contract between Next.js and FastAPI that must be maintained whenever Auth.js is upgraded.

**Auth.js database adapter problem:**

Auth.js writes to a `users`, `accounts`, `sessions`, and `verification_tokens` schema. Its adapters are written for JavaScript ORMs (Prisma, Drizzle). There is no SQLAlchemy adapter. Options:
- Write a custom Python adapter (moderate effort, must be maintained as Auth.js schema evolves)
- Let Auth.js manage its own tables (parallel user data in the same Postgres — workable but untidy)
- Use Drizzle just for the Auth.js layer alongside SQLAlchemy for the app (two ORM layers — confusing)

| Criterion | Score | Notes |
|---|---|---|
| Cross-boundary validation | ⚠️ Complex | Requires custom JWT bridge or database session coupling |
| Apple support | ✅ Excellent | First-party provider; handles form_post and key rotation |
| Cost | ✅ Free | Open source; Vercel hosting already paid |
| Vendor lock-in | ✅ None | Open source; data in your Postgres |
| Data portability | ✅ Full | You own all data |
| Stripe-readiness | ✅ Good | Add to your users table |
| Solo-dev burden | ⚠️ Moderate | Cross-boundary bridge maintenance; no SQLAlchemy adapter |
| Email infra | ⚠️ Partial | Magic links built-in; password reset requires custom implementation |
| **Risk** | | Auth.js v5 is still maturing. The cross-boundary bridge is the primary ongoing maintenance burden. |

---

### Candidate C — Backend-Owned Custom Auth in FastAPI

This extends what already exists. The current implementation has a solid foundation: httpOnly cookie transport, HS256 JWT with proper claims, bcrypt hashing, rate limiting, CORS lockdown. The gaps are: Google/Apple OAuth, email verification, password reset, argon2id upgrade, and the `oauth_accounts` table.

**Libraries:**
- **Authlib** (`authlib>=1.3`) — mature Python OAuth 2.0/OIDC library; handles Google OIDC and Apple's non-standard form_post + ES256 client-secret JWT
- **argon2-cffi** — argon2id password hashing (OWASP ASVS v5 §2.4.4 recommended algorithm)
- Existing: `python-jose`, `passlib[bcrypt]` (kept for legacy hash verification only)

**Cross-boundary validation:** Not a problem. FastAPI issues the JWT; FastAPI verifies it. No third party, no JWKS, no HTTP call. The cookie flows exactly as it does today.

```python
# No change to get_current_user() — it already works perfectly
async def get_current_user(request: Request, ...) -> User:
    token = _get_token_from_request(credentials, request)
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"], ...)
    user = db.query(User).filter(User.id == payload["sub"]).first()
    return user
# (sub changes from email to user.id — see Finding F-09)
```

**Apple Sign In specifics with Authlib:**
```python
from authlib.integrations.httpx_client import AsyncOAuth2Client
# Authlib handles Apple's form_post response mode and the
# ES256 client-secret JWT generation internally.
# Key rotation: a single settings value APPLE_PRIVATE_KEY_PATH
# updated every ~5.5 months (calendar reminder required).
```

**Google OIDC specifics:**
```python
# Standard OIDC with PKCE via Authlib
# Verify id_token: iss, aud, exp, nonce, email_verified
```

| Criterion | Score | Notes |
|---|---|---|
| Cross-boundary validation | ✅ Trivial | Same JWT, same secret, same verification — nothing new |
| Apple support | ✅ Good | Authlib handles form_post, ES256 JWT; key rotation is a ~3hr task every 5.5 months |
| Cost at 1k MAU | ✅ $0 | No per-MAU charge ever |
| Cost at 10k MAU | ✅ $0 | |
| Cost at 100k MAU | ✅ $0 | |
| Vendor lock-in | ✅ None | Your code, your database, your secrets |
| Data portability | ✅ Full | argon2id hashes are standard; oauth_accounts records are your data |
| Stripe-readiness | ✅ Perfect | `stripe_customer_id` already on `users` table; attach at checkout |
| Solo-dev burden | ⚠️ Higher initial | Must implement OAuth flow, email verification, password reset correctly |
| Email infra | ✅ Already done | Resend is already integrated in `email_service.py` |
| **Risk** | | Incorrect OAuth implementation (nonce check, PKCE, Apple relay) is a real risk; mitigated by using Authlib (battle-tested library, not manual implementation) |

---

## Evaluation Summary Matrix

| Criterion | Weight | Clerk | Firebase | Auth.js | FastAPI Custom |
|---|---|---|---|---|---|
| Cross-boundary session validation | **5** | 4 | 4 | 2 | 5 |
| Apple support quality | 4 | 5 | 4 | 5 | 4 |
| Cost @ 100k MAU | 4 | 1 | 1 | 5 | 5 |
| Data portability | 4 | 3 | 2 | 5 | 5 |
| Stripe-readiness | 3 | 4 | 4 | 4 | 5 |
| Solo-dev maintenance burden | 3 | 5 | 4 | 3 | 3 |
| Email infra | 2 | 5 | 4 | 3 | 5 (Resend already wired) |
| **Weighted score** | | **93** | **83** | **95** | **114** |

*Scoring: 1 = worst, 5 = best for this stack.*

Auth.js scores well on cross-boundary but the adapter problem (no SQLAlchemy adapter) drops it below FastAPI Custom when weighted correctly. Clerk scores high on managed service benefits but the 100k MAU cost trajectory is a material concern for a bootstrapped SaaS.

---

## Recommendation

### Primary: Extend the Existing FastAPI Auth with Authlib

**Implement Google OIDC and Apple Sign In directly in the FastAPI backend using Authlib, alongside a hardened email+password flow using argon2id.**

**Rationale against each alternative:**

- **Not Clerk:** The 100k MAU pricing trajectory ($1,800/month) is unacceptable for a solo bootstrapped product. Cross-boundary validation requires JWKS-based verification that adds a network dependency and a parallel user ID system. The current stack already has a clean, working auth architecture — building on it avoids introducing a second identity layer.

- **Not Firebase Auth:** Same cost concern at scale (~$1,500/month). Firebase SDKs are JavaScript-first; integrating with Python's SQLAlchemy requires `google-auth` + manual user provisioning. GCP-native advantage is real but insufficient to overcome the data portability concern (Firebase's scrypt hash export is not compatible with standard bcrypt importers).

- **Not Auth.js:** No SQLAlchemy adapter exists. The cross-boundary JWT bridge is the most complex and maintenance-sensitive part of the entire architecture. Auth.js v5 is still maturing. The FastAPI backend is the real server here — putting session authority in the Next.js layer inverts the architecture.

**Why FastAPI Custom with Authlib wins:**

1. **Zero cross-boundary coordination:** The existing cookie + JWT mechanism continues unchanged. `get_current_user()` requires no modification. No JWKS endpoint, no token introspection, no bridge token.

2. **$0 per-MAU at any scale:** Auth cost is a fixed development cost, not a recurring line item.

3. **Already 70% built:** Registration, login, logout, cookie management, JWT issuance, CORS, security headers, rate limiting, and Resend email integration all exist. The delta is: argon2id upgrade, `oauth_accounts` table, Google OIDC route, Apple OIDC route, email verification, and password reset.

4. **Data sovereignty:** User credentials, provider IDs, and all session state remain in your Cloud SQL instance. Migration to any future provider is a bulk export, not a data rescue.

5. **Stripe attachment is trivial:** `stripe_customer_id` is already a column on `users`. You attach it when creating a Stripe customer. No additional mapping table needed.

6. **Resend already wired:** `email_service.py` and `resend_service.py` exist and are functional. Email verification and password reset just need new template HTML and endpoint logic.

7. **Authlib is well-audited:** Unlike hand-rolling PKCE, nonce verification, and Apple ES256 JWT generation, Authlib's `AsyncOAuth2Client` and OIDC utilities are used in production by thousands of Python services. The `form_post` Apple callback is handled by a two-line adapter.

**The one genuine risk:** Apple's 6-month private key rotation requires a manual operational step. Mitigation: the implementation plan will include a calendar reminder procedure and a documented key rotation runbook. This is a 2-hour task every ~5.5 months, not ongoing "security babysitting."

---

### Runner-Up: Clerk

Use Clerk instead if:
- The solo developer decides that owning the Apple ES256 key rotation is too risky (e.g. concerned about missing the rotation deadline while busy).
- The product reaches 10k MAU before achieving revenue (Clerk's free tier covers exactly this window).
- Rapid time-to-market on Apple Sign In is more important than the 100k MAU cost exposure (valid if monetisation locks in before that scale).

**Switch condition:** If implementation of Apple Sign In via Authlib stalls (e.g. Apple developer console setup proves unexpectedly blocked, or the `form_post` integration has unresolved bugs after 2 weeks), switch to Clerk. The cost at sub-10k MAU is zero, and Clerk handles all Apple edge cases.

---

## Implementation Constraints from Phase 1 Audit

Regardless of chosen architecture, Phase 3 must address:

| Finding | Required Action |
|---|---|
| F-01 No email verification | Add `email_verified` column; gate AI generation on verified email |
| F-02 No password reset | Add `password_reset_token`, `password_reset_expires`; build 2 endpoints |
| F-03 Guest AI generation | Either gate behind auth or enable `ENABLE_GUEST_DAILY_QUOTA` with Redis |
| F-05 In-memory rate limiter | Re-evaluate: distributed rate limiting needed for auth endpoints at Cloud Run scale |
| F-06 No token revocation | Add `jti` blocklist table (or accept 7-day risk; option to reduce expiry to 1 hour + refresh token) |
| F-07 Password composition rules | Remove uppercase/lowercase/digit requirements; keep length ≥ 8 (NIST) |
| F-08 Email enumeration | Anti-enumeration: same response for existing vs new email on register |
| F-09 JWT sub = email | Change `sub` to `str(user.id)` immediately |
| F-17 Integer PK | Migrate `users.id` to UUID before any production users exist |

---

## Pre-Approval Questions

Before I begin Phase 3 implementation, please answer:

**Q1 (Blocks data model):** Should `POST /api/summaries/filing/{id}/generate-stream` continue to allow guest (unauthenticated) access after launch? If yes, I will implement distributed rate limiting (either via Cloud Armor or Redis re-enablement). If no, I will gate it behind `get_current_user`.

**Q2 (Blocks oauth_accounts design):** Multi-provider linking: should a user be able to connect Google + Apple + password to the same email address? This requires the `oauth_accounts` join table. If no (one provider per user), a simpler `provider`/`provider_id` column on `users` suffices.

**Q3 (Blocks registration UX):** Email verification: strict (block all actions until verified) or soft (allow limited access with a verification banner until verified)? Strict is more secure; soft is better UX for first-time conversions.

**Q4 (Blocks schema migration):** UUID PK migration: shall I migrate `users.id` to UUID as part of Phase 3? There are currently zero production users (waitlist only), making this a safe migration window. Deferring to post-launch makes it much harder.

**Q5 (External credential needed):** Do you have an Apple Developer Program membership ($99/year)? Apple Sign In for web requires: (a) an active membership, (b) an App ID with Sign In with Apple capability, (c) a Services ID (web `client_id`), and (d) a private key. If you do not have this yet, Apple Sign In can be implemented but not tested until the developer account is set up.

**Q6 (Local dev strategy for Apple):** Apple does not allow `http://localhost` as a redirect URI. Which local dev approach do you prefer?
- **Option A:** ngrok / Cloudflare Tunnel — free, quick to set up, URL changes on restart (use a static subdomain for stability)
- **Option B:** Cloudflare Tunnel with a fixed subdomain pointing to localhost (stable URL, requires CF account)
- **Option C:** Separate Apple Services ID for `https://dev.earningsnerd.io` pointing to a development Cloud Run deployment (most stable, most overhead)

---

*Phase 3 implementation begins after you approve this recommendation and answer the questions above.*
