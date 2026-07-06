# All React Query keys live in lib/queryKeys.ts — enforced by an eslint rule, not convention

**Area:** frontend · **Date:** 2026-07-06

F1 reconciled the drifted query keys (`['user']` vs `['current-user']`, etc.) into a single `frontend/lib/queryKeys.ts` registry. An eslint `no-restricted-syntax` rule fails a build that uses a string-literal query key for a registered entity, so the registry can't silently re-drift.

**Rule:** never inline a `queryKey`/`invalidateQueries` string for an entity in the registry — import from `queryKeys.ts`. Adding an entity means adding it there. (Same structural-enforcement move as the components allowlist and the naive-utcnow allowlist.)
