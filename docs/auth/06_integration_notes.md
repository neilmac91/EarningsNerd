# Auth Integration Notes — reconciling with shipped `main`

While this auth work was in progress, `main` independently shipped a refresh-token
system (#269/#270) and diverged ~90 commits (DeepSeek model migration, dependency
bumps, summary-pipeline refactor, legacy-SEC removal). This branch was integrated
onto current `main` rather than merged blindly. Decisions:

## Foundation: adopted main's, not this branch's original plan
- **User id stays `INTEGER`** (not the originally-planned UUID). main shipped integer
  ids to production; a destructive UUID migration was not worth the risk. The original
  UUID migration files were removed.
- **Refresh tokens use main's `refresh_tokens` table** (opaque, rotated, reuse-detection
  via `refresh_token_service`) — a better design than this branch's columns-on-`users`.
  This branch's refresh columns/migration were dropped.
- **Password hashing stays bcrypt** (main's `get_password_hash`), not argon2id. Avoids a
  new dependency and a mixed-hash state; bcrypt remains industry-standard.
- **JWT subject is the email** (main's convention); `get_current_user` looks up by email.
- **Password policy is main's**: min 12 chars + upper/lower/digit (frontend hints updated
  to match).

## Kept from this branch (genuinely additive, not on main)
- Google OAuth (`/api/auth/google`, `/api/auth/google/callback`) — implemented with
  `httpx` (already a dependency) instead of Authlib, so **no new backend dependency**.
- Email verification (`/verify-email`, `/resend-verification`) + `email_verified` column,
  surfaced in `/me`, gating Stripe checkout.
- Password reset (`/forgot-password`, `/reset-password`), single-use SHA-256-hashed tokens.
- `oauth_accounts` table (integer FK) for multi-provider linking.
- Apple Sign In button + backend stubs remain flag-gated (`ENABLE_APPLE_SIGNIN`) pending
  Apple Developer credentials.
- The whole split-screen auth UI, header user menu, and email-verification nudge system.

## Notable consequence
- AI generation gating by `email_verified` is **moot**: main made generation a guest-open
  streaming endpoint (`/generate-stream`), consistent with the "keep guest generation open"
  decision. `email_verified` now gates **Stripe checkout** (and any future authed-only action).

## New migration
`20260615_oauth_and_email_verification.sql` (additive, integer-id): adds the email
verification + password reset columns, makes `hashed_password` nullable, and creates
`oauth_accounts`. main's `20260613_create_refresh_tokens.sql` is unchanged.

## Deviations from the original plan worth a future look
- **argon2id** (audit-recommended) was not adopted — kept bcrypt. Revisit if desired.
- **Register anti-enumeration**: kept main's `400 "Email already registered"` rather than
  the opaque-message approach, to match deployed behavior. Revisit if desired.
