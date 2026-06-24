# Security Audit — Pre-Beta Sweep (Roadmap Week 7)

**Date:** 2026-06-24 · **Scope:** the closed-beta attack surface (invite gate, billing/entitlements,
auth/session/secrets/transport, data exposure/PII/IDOR). **Method:** four parallel adversarial code
audits (each told to *break* its surface) + the full automated test suite.

## Headline

**No Critical findings. No exploitable account-takeover, token-forgery, or public-free-Pro path.**
The auth/billing/crypto core is well-built: JWT algorithm pinned + all claims required, refresh-token
rotation with reuse/theft detection, OAuth ID-tokens verified against provider JWKS (audience/issuer/
nonce), Stripe webhook signature-verified on the **raw** body + idempotent + fail-closed, the 100%-off
promo gated purely on server-set `is_beta` (regression-tested against a client param), IDOR scoped to
`current_user`, injection clean (`html.escape` + ORM-only), CORS allowlist + security headers + CSP,
internal job endpoints fail-closed + constant-time.

**QA:** backend `691 passed` (unit+smoke+integration+performance); frontend typecheck + lint + 173
vitest + e2e (CI). 

## Findings & disposition

| # | Sev | Finding | Status |
|---|-----|---------|--------|
| H1 | High | `REGISTRATION_MODE` failed open — any non-exact value (`INVITE_ONLY`, trailing space, typo) silently opened public registration | ✅ **Fixed** — `field_validator` normalizes case/whitespace and **rejects** unknown values (fail-closed; crashes config load so the old revision keeps serving) |
| H2 | High | Frontend `analytics.identify()` sent the user's **email** to PostHog as a person property | ✅ **Fixed** — `identify`/`signupCompleted`/`loginCompleted` + dashboard/login call sites now send id-only (+ non-PII `plan`) |
| M1 | Med | JWT minted with `nbf=now` but decoded with **no leeway**; `JWT_LEEWAY_SECONDS=10` was dead config → tokens rejected "not yet valid" under multi-instance clock skew | ✅ **Fixed** — leeway wired into both `jwt.decode` paths |
| M2 | Med | No DB `UNIQUE(provider, provider_account_id)` on `OAuthAccount` → concurrent callbacks could dup-link | ✅ **Fixed** — `UniqueConstraint` on the model + idempotent migration |
| M3 | Med | Rate-limit / IP-hash keys trusted spoofable left-most `X-Forwarded-For` | ⚙️ **Mechanism shipped** — `TRUSTED_PROXY_HOPS` (right-most-Nth) in a shared `get_client_ip` used by rate_limiter/contact/feedback. **Default 0 = legacy behavior; needs you to set it (see Action items).** |
| L1 | Low | Raw client **IP** written to request logs at INFO | ✅ **Fixed** — dropped from request log context (hashed IPs in audit/feedback/contact remain) |
| L2 | Low | Raw **email** logged at INFO on the contact path | ✅ **Fixed** — removed from both INFO lines |
| L3 | Low | Apple ID-token decode didn't `require` claim presence | ✅ **Fixed** — `options={"require": [...]}` added (sig was already the real gate) |
| L4 | Low | Refresh POST relies on SameSite=Lax, no explicit Origin check | 🏷️ Flagged — Lax already blocks the cross-site POST; optional `SameSite=Strict` (cookie is already path-scoped to `/api/auth`) |
| I1 | Info | Reverse-trial re-grantable by re-registration / account-deletion churn | 🏷️ Flagged — **inert: `REVERSE_TRIAL_ENABLED` is off.** Gate on a persistent (hashed-email) trial ledger *before* ever enabling it |
| I2 | Info | `GET /api/waitlist/status/{email}` is unauthenticated + email-enumerable (echoes referral code) | 🏷️ Flagged — low sensitivity; optionally rate-limit / stop echoing the referral code |
| I3 | Info | Login does not require a verified email | 🏷️ By design (documented); blast radius contained by the "link only when both verified" OAuth rule |
| I4 | Info | 39 Dependabot alerts (17 high) on the default branch | 🏷️ **Action item** — triage separately (`npm audit` / `pip-audit`); out of scope for a code audit |

## Fixes shipped in this PR

Backend: `config.py` (REGISTRATION_MODE validator + `TRUSTED_PROXY_HOPS`), `services/rate_limiter.py`
(trusted-proxy `get_client_ip`), `routers/auth.py` (JWT leeway ×2, Apple `require`), `models/__init__.py`
(+ `migrations/…_add_oauth_account_unique.sql`), `services/logging_service.py` (drop raw IP),
`routers/contact.py` + `routers/feedback.py` (shared IP helper; drop raw email log). Frontend:
`lib/analytics.ts` + `app/login/page.tsx` + `app/dashboard/page.tsx` (id-only identify). Tests:
`tests/unit/test_security_hardening_week7.py`.

## Action items for the operator (not code)

1. **Set `TRUSTED_PROXY_HOPS`** to match the prod ingress so per-IP throttling/IP-hashing is
   trustworthy. For **direct Cloud Run** ingress this is `1`. If an external HTTPS LB sits in front,
   add its hop too. (Default `0` keeps today's spoofable-but-unchanged behavior, so this is the one
   knob to turn before opening the beta widely.) — *needs your confirmation of the topology.*
2. **Triage the 39 Dependabot alerts** (17 high) before go-live.
3. **Before ever flipping `REVERSE_TRIAL_ENABLED=true`**, add a persistent trial ledger (I1).

## Verified-secure (high-value invariants confirmed)

Promo self-grant (no client path), webhook forgery/replay (raw-body signature + idempotent +
fail-closed), `$0 active = Pro` only reachable via `is_beta`, IDOR on saved-summaries/watchlist/
profile/export/deletion/feedback/copilot, copilot single-filing scoping, SQL/email-HTML injection,
`alg=none`/key-confusion, SECRET_KEY non-default-in-prod, refresh rotation + reuse-theft detection,
password-reset token hygiene, OAuth state/nonce CSRF, CORS allowlist, security headers + CSP,
internal-endpoint fail-closed + constant-time, prod error-message redaction, audit-log IP hashing.
