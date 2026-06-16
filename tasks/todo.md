# Auth, Privacy & Conversion Hardening — Implementation Tracker

Branch: `claude/clever-keller-l0v83e`
Context: Phase 2 of the auth/security/privacy plan. User authorized autonomous
execution of the safely-implementable items (P0 + self-contained P1/P2),
"balanced" risk appetite, B2C, ~$50–100/mo budget, keep-and-harden custom auth.

Baseline before changes: **259 passed** (unit + smoke).

## Decisions / guardrails
- Do not break tested behavior or the auth flow while unattended. Verify every change with pytest.
- External-credential or frontend-build-risking items are scaffolded/documented, not forced in blind.

## In scope (this pass) — backend, pytest-verifiable

- [x] **Login anti-enumeration + timing**: unify inactive-account `403` → generic `401`;
      run a dummy bcrypt verify when the user is unknown to remove the timing oracle. (`auth.py`)
- [x] **Wire audit logging**: login success/failure, register, logout, OAuth login/link —
      helpers already existed but were never called; pass a hashed client IP. (`auth.py` + `audit_service.py`)
- [x] **Verify Google `id_token`** against Google's JWKS (audience/issuer/signature),
      replacing the unverified `/userinfo` trust — parity with the existing Apple path. (`auth.py`)
- [x] **Stop sending user email to PostHog** (`subscription_activated`, `$delete`). (`subscriptions.py`, `users.py`)
- [x] **NIST password policy**: keep 12-char min, drop forced upper/lower/digit composition,
      dedupe the two copies of the validator, cap max length; pin bcrypt rounds explicitly. (`auth.py`)
- [x] **Breached-password check** via HIBP k-anonymity (fail-open) on register + reset. (`pwned_passwords.py`, `auth.py`, `config.py`, `conftest.py`)
- [x] **Fail closed** on a sqlite `DATABASE_URL` in production. (`config.py`)
- [x] **Per-account login throttle** (bounds distributed brute-force on one account). (`rate_limiter.py`, `auth.py`)
- [x] **Entitlements abstraction** (`get_entitlements(user)` → limits/features), stub FREE/PRO from `is_pro`,
      so monetization is a config change later. (`entitlements.py`, `subscription_service.py`)
- [x] **Notify-on-link**: email the user when an OAuth identity is linked to an existing account. (`email_service.py`, `auth.py`)
- [ ] Tests for the new behavior; full suite stays green.
- [ ] Docs: this tracker, DSAR + breach-notification runbook, `.env.example` updates, lessons.

## Deferred (with rationale) — documented, not implemented this pass

- **Register account-enumeration (P0 in plan):** DEFERRED. `test_duplicate_registration_rejected`
  asserts register→`400`, and auto-login-on-register is the stated conversion preference (Section E).
  Full anti-enumeration requires a verify-first signup (no auto-login), which conflicts with both.
  A genuine product decision, not a cheap fix → left for explicit owner sign-off.
- **Cloudflare Turnstile (P0):** needs a site/secret key (external) and a frontend widget; documented for when keys exist.
- **Consent-gating of analytics + privacy policy/ToS (P0/P1):** frontend + legal copy; documented (avoid risking the Next build unattended; UI/legal wants human review).
- **Cookie-only access token:** tests assert `access_token` in the body and the frontend ignores it; low value vs. breakage risk → deferred.
- **MFA, passkeys, lifecycle email, distributed (Redis) rate limiting, B2B org layer:** P2/P3, defer per "balanced".
- **X-Forwarded-For trusted-proxy depth:** environment-specific; documented (the per-account throttle is the higher-value half of that item).

## Review

Implemented the safely-autonomous, pytest-verifiable backend hardening. Full unit+smoke suite:
**259 → 272 passed** (+13 new tests, 0 regressions). Ruff clean (project `backend/ruff.toml`).

Shipped in three commits:
1. `harden authentication, credentials, and entitlements foundation` — login enumeration/timing,
   per-account throttle, NIST password policy + HIBP breach check, bcrypt rounds pinned, Google
   id_token verification (parity with Apple), audit-log wiring with hashed IP, OAuth link
   notifications, DATABASE_URL fail-closed in prod, and the `get_entitlements()` abstraction.
2. `stop sending user email to PostHog` — dropped the email property from `subscription_activated`
   and the GDPR `$delete` event (both already keyed by user id).
3. `docs:` — this tracker, `tasks/security_privacy_runbook.md` (DSAR/breach/retention/processors +
   exact next steps for deferred items), `.env.example` auth/security section.

Verification:
- New tests cover: login unified-401 for unknown email and inactive account; per-account lockout
  → 429; HIBP hit/padding/miss/network-fail-open/disabled; `RateLimiter.is_exhausted` peek
  semantics; entitlements free/pro mapping. `test_auth_flow` made hermetic against rate-limit
  cross-test coupling via an autouse limiter reset.
- Behavior preserved on the happy path: register/login/refresh/logout, Apple flow, and Stripe
  webhook tests all still green; `check_usage_limit` returns identical results (free=5, pro=∞).

Notable deltas vs. the original P0 list (rationale in the Deferred section above):
- **Register enumeration** intentionally NOT changed (tested 400-on-duplicate + auto-login-on-
  register conflict with full anti-enumeration; needs a product decision). The higher-value
  **login** enumeration + timing oracle were closed instead.
- **Turnstile / consent-gating / privacy policy** need external keys or frontend+legal work and
  human review; scaffolding/steps documented rather than forced in blind.

Not done (deferred per "balanced" appetite / external deps): MFA, passkeys, lifecycle email,
Redis-backed distributed rate limiting, B2B org layer, log scrubbing, retention purge jobs.
Next-step details for each are in `tasks/security_privacy_runbook.md` §6.
