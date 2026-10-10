# Apple Sign In — Configuration Runbook (Increment 4)

Status: **blocked on Apple Developer membership approval.** Run this the moment your
account shows **Active** (not "Pending"). Everything below is split into *what you do*
and *what I build*.

---

## Part 1 — Apple Developer Console (you)

### 1.1 App ID
1. [developer.apple.com](https://developer.apple.com) → **Certificates, Identifiers & Profiles**
2. **Identifiers** → **+** → **App IDs** → **App** → Continue
3. Description: `EarningsNerd`; Bundle ID (Explicit): `io.earningsnerd.app`
4. Capabilities → check **Sign In with Apple** → **Enable as primary App ID**
5. Continue → Register

### 1.2 Services ID  (this becomes `APPLE_CLIENT_ID`)
1. **Identifiers** → **+** → **Services IDs** → Continue
2. Description: `EarningsNerd Web`; Identifier: `io.earningsnerd.web` → Register
3. Click `io.earningsnerd.web` → check **Sign In with Apple** → **Configure**
4. Primary App ID: `EarningsNerd`
5. **Domains and Subdomains**: `api.earningsnerd.io` *(and `dev.earningsnerd.io` for local — see Part 3)*
6. **Return URLs** — add both:
   - `https://api.earningsnerd.io/api/auth/apple/callback`
   - `https://dev.earningsnerd.io/api/auth/apple/callback`
7. Next → Done → Continue → Save

### 1.3 Private Key (.p8)
1. **Keys** → **+**; Name: `EarningsNerd Sign In with Apple`
2. Check **Sign In with Apple** → **Configure** → Primary App ID: `EarningsNerd` → Save
3. Continue → Register
4. **Download the `.p8` immediately** (one-time download) and note the **Key ID** (`APPLE_KEY_ID`)

### 1.4 Team ID
Top-right → your name → **Membership details** → copy **Team ID** (`APPLE_TEAM_ID`)

### 1.5 (World-class) Private-relay email deliverability
Apple users can hide their email; you'll receive a `…@privaterelay.appleid.com` address.
Mail to that address is **only forwarded if your sending domain is registered with Apple.**
- **Certificates, Identifiers & Profiles** → **More** → **Configure Sign in with Apple for Email Communication**
- Add your Resend sending domain + from-address (e.g. the domain behind `RESEND_FROM_EMAIL`)
- Add the SPF record Apple shows you to that domain's DNS

This guarantees account/transactional emails reach relay users. (Apple-verified accounts skip
the verification email, but other mail — receipts, security notices — still needs this.)

---

## Part 2 — Send me

```
APPLE_TEAM_ID=...
APPLE_KEY_ID=...
APPLE_CLIENT_ID=io.earningsnerd.web
```
Plus the **full contents of the `.p8`** (starts with `-----BEGIN PRIVATE KEY-----`).

---

## Part 3 — Local dev tunnel (you, one-time)

Apple requires HTTPS for the redirect URI. `dev.earningsnerd.io` tunnels to your local backend.

```bash
brew install cloudflare/cloudflare/cloudflared
cloudflared tunnel login                      # pick the earningsnerd.io zone
cloudflared tunnel create earningsnerd-dev    # prints a UUID — save it
```
`~/.cloudflared/config.yml`:
```yaml
tunnel: <UUID>
credentials-file: /Users/<you>/.cloudflared/<UUID>.json
ingress:
  - hostname: dev.earningsnerd.io
    service: http://localhost:8000
  - service: http_status:404
```
Cloudflare DNS → **earningsnerd.io** → add `CNAME` `dev` → `<UUID>.cfargotunnel.com` (proxied).
Run while developing: `cloudflared tunnel run earningsnerd-dev`.
In the shell that launches the local backend, export both settings before starting it.
A `COOKIE_SECURE` value supplied only in `.env` is overwritten by the development default
(see [Settings precedence](../CONFIGURATION.md#backend-settings-inventory)).

```bash
export APPLE_REDIRECT_URI=https://dev.earningsnerd.io/api/auth/apple/callback
export COOKIE_SECURE=true
```

Start plain Apple sign-in at `https://dev.earningsnerd.io/api/auth/apple`. The browser-binding
cookie is host-only, so starting on `localhost` while returning to `dev.earningsnerd.io` fails.
Apple's cross-site callback requires that cookie to have both `SameSite=None` and `Secure`; the
backend sets it `Secure` unconditionally (independent of `COOKIE_SECURE`), so the start request
itself must be HTTPS or the browser discards the cookie and the callback ends in
`oauth_state_mismatch`. `COOKIE_SECURE=true` above is for the session cookies the sign-in issues.
For invited sign-in, send the JSON `POST` to `https://dev.earningsnerd.io/api/auth/apple/start`
from the browser with credentials enabled and the frontend origin allowed by CORS; keep the
invite in the JSON body, never in a URL. Local UI testing must target this same HTTPS API
origin for its backend requests because `COOKIE_SECURE=true` also secures the session cookies.

---

## Part 4 — Production secrets (you, in GCP)

Secret Manager → create `APPLE_TEAM_ID`, `APPLE_KEY_ID`, `APPLE_CLIENT_ID`,
`APPLE_PRIVATE_KEY` (paste the multi-line `.p8` PEM as the secret value).
Cloud Run → `earningsnerd-backend` → Edit & Deploy → Variables & Secrets → reference each
as an env var of the same name. `APPLE_REDIRECT_URI` defaults to the prod callback — leave unset.

---

## Part 5 — What I build (world-class implementation notes)

- **Dynamic client secret (zero manual rotation).** Apple's "client secret" is an ES256 JWT
  signed with the `.p8`, valid ≤ 6 months. I generate it *at runtime* from `APPLE_PRIVATE_KEY`
  (`iss`=Team ID, `sub`=Services ID, `aud`=`https://appleid.apple.com`, `kid`=Key ID), cache
  ~50 min. You never rotate a secret by hand.
- **`form_post` callback.** Because we request `name email` scope, Apple **POSTs** to the
  callback (not GET) and returns the user's name **only on first authorization**. The route is
  a POST handler that captures the name on that first hit.
- **State/nonce stored server-side, state bound to the browser.** A cross-site POST drops
  `SameSite=Lax` cookies, so `state`+`nonce` live in a short-lived `oauth_states` table (10-min
  TTL) instead of the state cookie used for Google; the row is validated + consumed on callback.
  `/api/auth/apple` also sets a `SameSite=None; Secure; HttpOnly` cookie holding an HMAC of the
  state, and the callback requires it, so a posted state is accepted only from the browser that
  started the flow.
- **ID-token verification.** Verify Apple's ID token against Apple's JWKS
  (`https://appleid.apple.com/auth/keys`); check `iss`/`aud`/`exp`/`nonce`.
- **Account linking.** Same policy as Google: link to an existing account only when the email
  matches an existing **verified** account; otherwise create a new user — only when Apple asserts
  `email_verified=true`, and under `REGISTRATION_MODE=invite_only` only when the sign-in started
  from `POST /api/auth/apple/start` with the magic-link invite in the request body (never in a
  URL: request logs record query strings); the callback validates and redeems it in the same
  transaction as the insert. Private-relay
  emails are treated as that user's email.
- **Tests + frontend wiring.** Apple button (HIG-compliant) ships with the design work; the
  backend exchange + the button's live wiring land in this increment once credentials arrive.
