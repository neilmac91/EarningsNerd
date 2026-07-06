# Enforce every access gate server-side at the mutation endpoint

Date: 2026-06-23   Area: sec

**Context**: Planning the closed beta, assumed `WAITLIST_MODE` kept the public out. It is read only in frontend middleware (redirects `/`→`/waitlist`) while the backend register endpoint accepts anyone — no allowlist, no invite check. Flipping `WAITLIST_MODE=false` would have silently opened registration to the entire internet; a curl to `/api/auth/register` walks straight past the cosmetic gate.

**Rule**: Any access/gating requirement (waitlist, invite-only, beta cohort, role) must be enforced in the backend at the mutation endpoint — frontend middleware/redirect is UX only and trivially bypassed. Before trusting an existing gate, grep for where the server validates it; if the check lives only in `middleware.ts`/route guards, treat the resource as ungated.

**Evidence**: `frontend/middleware.ts` (redirects `/`→`/waitlist`); `backend/app/routers/auth.py:608-676` accepts anyone.
