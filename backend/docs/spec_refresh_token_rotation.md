# Design Spec — Refresh-token rotation

> **Status:** Implemented. Shipped across #269 (backend rotation + reuse detection), #270
> (frontend silent refresh + 30m access-token TTL), and the CI fix #271. Retained as the design
> record; this captures the rationale and proposed sequencing that preceded implementation
> (**this change touched the frontend**, so sequencing mattered — see §6).

## 1. Problem / current state

Auth today (`app/routers/auth.py`) issues a **single long-lived access token** and has no refresh
or revocation story:

- `create_access_token()` (`auth.py:81`) mints a **7-day** JWT
  (`ACCESS_TOKEN_EXPIRE_MINUTES = 60*24*7`, `config.py:61`), stored in an httponly cookie
  (`earningsnerd_access_token`, `_set_auth_cookie` `auth.py:99`).
- A `jti` claim is minted (`auth.py:94`) but **never stored**, so it cannot be used for revocation.
- **Logout** (`auth.py:292`) only clears the cookie client-side — the token stays valid for the
  remainder of its 7 days. A leaked token is replayable for up to a week.
- **No `/refresh` endpoint, no refresh token, no `refresh_tokens` table.** (CLAUDE.md lists
  "refresh" under `/api/auth`, but no such code exists — verified.)
- **Redis is OFF in production** (`SKIP_REDIS_INIT=true`), so any rotation/revocation state must
  live in **PostgreSQL**, not Redis.

The security goal: short-lived access tokens + a rotating, revocable refresh token, giving real
server-side logout and limiting the blast radius of a leaked access token.

## 2. Goals / non-goals

**Goals**
- Short-lived access token (minutes) + long-lived refresh token (days), rotated on every refresh.
- Real logout: server-side revocation of the refresh token.
- Refresh-token **reuse detection** (theft response): replay of an already-rotated token revokes
  the whole token family.
- DB-backed (no Redis dependency in prod).

**Non-goals**
- Not building full OAuth2 / multi-client device management.
- Not adding an access-token `jti` denylist initially (short access TTL makes it largely moot — see §5).
- No change to password hashing or the login credential flow.

## 3. Token model

| | Access token | Refresh token |
|---|---|---|
| Type | JWT (HS256), as today | **Opaque** high-entropy random string (`secrets.token_urlsafe(32)`) |
| TTL | **30 min** (proposed; from 7 days) | **30 days** (proposed) |
| Stored server-side? | No (stateless) | **Yes — only a SHA-256 hash** |
| Cookie | `earningsnerd_access_token`, path `/` | `earningsnerd_refresh_token`, path `/api/auth` (tighter scope) |
| Rotated? | Re-minted on refresh | Rotated (old one revoked) on every refresh |

The refresh token is deliberately **opaque, not a JWT** — it is a pure DB lookup key, so revocation
is authoritative (no "valid signature but revoked" ambiguity). We store only its hash, so a DB read
leak does not expose usable tokens.

## 4. New table: `refresh_tokens`

Added as a SQLAlchemy model in `app/models/__init__.py`; created at startup by
`Base.metadata.create_all()` (no Alembic). A manual `migrations/` SQL file is provided for the
existing prod DB, though `create_all` handles a brand-new table on deploy.

```python
class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    id           = Column(Integer, primary_key=True)
    user_id      = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    token_hash   = Column(String(64), unique=True, index=True, nullable=False)  # sha256 hex
    family_id    = Column(String(36), index=True, nullable=False)               # uuid4 — rotation chain
    expires_at   = Column(DateTime(timezone=True), nullable=False)
    revoked_at   = Column(DateTime(timezone=True), nullable=True)               # NULL = active
    replaced_by  = Column(String(64), nullable=True)                            # hash of successor
    created_at   = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    ip_address   = Column(String(45), nullable=True)
    user_agent   = Column(String(500), nullable=True)
```

`family_id` ties a rotation chain together so reuse detection can revoke the whole lineage.

## 5. Flows

**Login / register** — unchanged credential check, then: mint a 30-min access token **and** create
a refresh token (new `family_id`), set both cookies.

**`POST /api/auth/refresh`** (new):
1. Read refresh cookie → SHA-256 → look up row.
2. If not found, expired, or `revoked_at` set → **reuse/abuse path**: if the row exists but is
   already revoked, revoke the *entire family* (someone replayed a rotated token); return 401.
3. Otherwise **rotate**: mark current row `revoked_at = now`, `replaced_by = hash(new)`; insert a
   new refresh token in the *same* family; mint a new access token; set both cookies; return.

**Logout** (`auth.py:292`, upgraded): revoke the presented refresh token's family server-side and
clear both cookies — logout finally means something.

**Access-token denylist:** *not* included. With a 30-min access TTL the unrevoked window after
logout is ≤30 min, which we accept to avoid a per-request denylist read on the stateless path. The
`jti` claim already exists if we later decide to add one.

## 6. Frontend impact + rollout sequencing (important)

Shortening the access TTL from 7 days to 30 min **will mass-logout users** unless the frontend
transparently refreshes. The axios client (`frontend/lib/api/client.ts`) needs a 401 interceptor:
on 401, call `/api/auth/refresh` once, then retry the original request; on refresh failure, redirect
to login. Cookies are httponly, so the browser carries them automatically — no token handling in JS.

**Rollout order (each step deploys independently; no mass logout):**
1. **Backend, additive only** — add the table, `/refresh`, and refresh-cookie issuance on
   login/register. **Keep `ACCESS_TOKEN_EXPIRE_MINUTES` at 7 days for now.** Existing sessions
   untouched.
2. **Frontend** — add the silent-refresh interceptor and ship it. Now clients can refresh.
3. **Shorten the access TTL** to 30 min (config change) **only after** step 2 is live. Old 7-day
   cookies keep working until they expire; new logins get the short-TTL + refresh pair.

Doing step 3 before step 2 is the one ordering that breaks users — the spec exists partly to make
that explicit.

## 7. Config additions (`config.py`)

```python
ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7   # → 30 only AFTER frontend refresh ships (step 3)
REFRESH_TOKEN_EXPIRE_DAYS: int = 30
REFRESH_COOKIE_NAME: str = "earningsnerd_refresh_token"
REFRESH_COOKIE_PATH: str = "/api/auth"
```

## 8. Testing

- **Unit:** create/hash/lookup; rotate (old revoked + `replaced_by` set, new active in same family);
  expiry rejected; revoked rejected.
- **Reuse detection:** replaying a rotated (revoked) token revokes the whole family and 401s.
- **Integration:** login → access works → expire access → `/refresh` issues new pair → old refresh
  rejected → logout revokes family → subsequent `/refresh` 401s.
- **Cleanup:** a small periodic job (or opportunistic delete) prunes `expires_at < now()` rows so
  the table doesn't grow unbounded.

## 9. Open decisions (need your call)

1. **Access-token TTL** — 30 min proposed. Shorter (15 min) is more secure but more refreshes;
   longer (60 min) is gentler. Drives §6 step 3.
2. **Reuse-detection family revocation** (recommended) vs. plain rotation without theft response.
3. **Refresh-cookie scope** — `path=/api/auth` (recommended, smaller exposure) vs. `path=/`
   (simpler if other routes ever need it).
4. **Do we want an access-token `jti` denylist** for instant revocation despite the short TTL?
   (Recommended: no, defer.)
5. **Scope of this work** — backend-only spec for now, or should the frontend interceptor land in
   the same effort? (It must precede the TTL cut regardless.)
