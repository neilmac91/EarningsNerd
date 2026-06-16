# EarningsNerd — Security & Privacy Runbook

Operational reference for the auth/privacy surface. Pairs with the Phase-2 plan.
Last updated alongside the auth-hardening pass on branch `claude/clever-keller-l0v83e`.

---

## 1. Auth architecture (current state)

Self-hosted, custom FastAPI auth (no managed provider). Three sign-in methods:
email+password, Google OAuth, Apple Sign In (Apple is feature-flagged off by default).

- **Passwords:** salted bcrypt, work factor pinned at 12. Policy = ≥12 chars, ≤128 chars,
  no forced composition (NIST 800-63B), screened against HaveIBeenPwned (k-anonymity, fail-open).
- **Sessions:** short-lived HS256 access JWT (30 min) in an HttpOnly cookie + opaque refresh
  token (30 d), stored hashed, rotated single-use, with reuse/theft detection and revocation.
- **OAuth:** both Google and Apple id_tokens are cryptographically verified (signature +
  audience + issuer; Apple also binds a nonce). Linking a social identity to a pre-existing
  account emails the owner and writes an audit row.
- **Login hardening:** unified 401 for all failure modes (no enumeration), bcrypt run on
  unknown emails (no timing oracle), per-IP + per-account throttles.
- **Audit trail:** login success/failure, register, logout, OAuth login/link, data export,
  account deletion — all with a SHA-256-hashed client IP. See `audit_logs` table.

---

## 2. Data-subject request (DSAR) runbook  — GDPR Art. 15/17/20, CCPA

The endpoints exist and are authenticated as the requesting user:

- **Access / portability:** `GET /api/users/export` → JSON of profile, searches, saved
  summaries, watchlist, usage. Writes a `data_exported` audit row.
- **Erasure:** `DELETE /api/users/me` → cancels active Stripe subscriptions, sends a PostHog
  `$delete`, clears Sentry context, writes a `user_deleted` audit row, then cascade-deletes the
  user and all child rows (searches, saved summaries, usage, watchlist, refresh tokens, oauth
  accounts). Target SLA: **30 days** (GDPR).

**Manual steps for an emailed/out-of-band request** (until a self-serve UI button ships):
1. Verify the requester controls the account email (reply-to + logged-in confirmation).
2. For deletion of non-account records keyed only by email — `contact_submissions`,
   `waitlist_signups` — delete by email (no FK to `users`, so cascade does not cover them).
3. **Retained by design, disclose in the privacy policy:** the Stripe customer object (7-year
   tax retention) and `audit_logs` rows (which store `user_email` to survive deletion).
4. Record the action; the deletion endpoint already audits, but log the manual residual cleanup.

---

## 3. Breach-notification readiness (GDPR Art. 33/34 — 72-hour clock)

Minimal runbook (formal tooling deferred until traction):
1. **Contain & assess** — what data, how many subjects, is it likely to risk their rights?
2. **Clock starts** when you become *aware*. GDPR: notify the lead supervisory authority within
   **72 hours** if there is risk; notify affected users without undue delay if high risk.
3. **Evidence** — `audit_logs`, application logs (correlation IDs), Sentry. Note: refresh-token
   theft auto-revokes the user's chain (reuse detection) — capture that signal.
4. **Rotate** — `SECRET_KEY` (note: rotating it invalidates all access tokens; refresh still
   works), and any leaked third-party keys in Secret Manager.
5. **Comms** — pre-draft a user notification template; route through legal before sending.

---

## 4. Data retention (disclose these in the privacy policy)

| Data | Retention |
|------|-----------|
| Account (`users`) | Until deletion request |
| Refresh tokens | 30 days, then expired/purgeable |
| `audit_logs` (incl. `user_email`) | Retained post-deletion for security/compliance; pick a window (suggest 1–2y) and add a purge job |
| Stripe customer object | 7 years (tax) — subscriptions cancelled on deletion, customer retained |
| Search history (`user_searches`) | Table exists but is **never written** — drop it or define a purpose+retention before using |

---

## 5. Processors & DPAs (sign the click-through DPA with each before EU users)

Google Cloud / DeepSeek (or Gemini) — AI + infra · Stripe — payments · Resend — email ·
PostHog — analytics · Vercel — frontend hosting · Sentry — error tracking · Cloudflare — DNS/CDN.

Confirmed: **no user PII reaches the LLM** (only filing text + financial metrics).
**No card data is stored** locally (Stripe Checkout handles it).

---

## 6. Deferred items — exact next steps

- **Cloudflare Turnstile (bot defense, P0):** create a Turnstile widget; set
  `TURNSTILE_SECRET_KEY`; add a backend verify call at the top of register/login/contact/waitlist
  (fail-open when unset); render the widget on those forms. Free tier.
- **Consent-gating + privacy policy/ToS (P0/P1):** gate PostHog/Sentry load behind the existing
  `CookieConsent` component for EU/CH (reject-all as easy as accept-all, no pre-ticked boxes);
  publish a Privacy Policy + ToS (Termly/iubenda to start, lawyer review before monetizing).
- **Register account-enumeration (P0, product decision):** the register endpoint returns 400 on
  a duplicate email (tested behavior) and auto-logs-in new users (stated conversion preference).
  True non-enumeration requires verify-first signup (no auto-login). Decide instant-access vs.
  non-enumeration before changing; the login path is already hardened.
- **MFA (P2):** optional TOTP via `pyotp` + hashed recovery codes, opt-in.
- **Distributed rate limiting (P2):** the in-memory limiters don't share across instances; move
  to Redis/Memorystore when scaling past one Cloud Run instance.
- **X-Forwarded-For trust (P2):** `_get_client_ip` trusts the left-most (spoofable) XFF value;
  set a trusted-proxy depth for the actual Cloud Run topology.
- **Retention purge jobs (P2):** scheduled cleanup of expired refresh tokens and aged audit logs.
- **Log scrubbing (P3):** plaintext email/IP still appear in some application logs (e.g. contact).
