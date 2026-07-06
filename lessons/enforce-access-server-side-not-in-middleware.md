# Enforce any access/gating rule in the backend at the mutation endpoint — middleware is UX only

**Area:** security · **Date:** 2026-06-23

While planning the closed beta I assumed `WAITLIST_MODE` kept the public out. It does not: it's read
**only** in `frontend/middleware.ts` (redirects `/`→`/waitlist`), while the backend register endpoint
(`backend/app/routers/auth.py:608-676`) accepts **anyone** — no allowlist, no invite check. Flipping
`WAITLIST_MODE=false` would have silently opened registration to the entire internet. The "gate" was
cosmetic; a curl to `/api/auth/register` walks straight past it.

**Rule:** any access/gating requirement (waitlist, invite-only, beta cohort, role) must be enforced
in the **backend** at the mutation endpoint — the frontend middleware/redirect is UX only and is
trivially bypassed. Before trusting an existing gate, grep for where the *server* validates it; if the
check lives only in `middleware.ts`/route guards, treat the resource as ungated.
