# React Query keys come from lib/queryKeys.ts — inline key literals are a stale-cache bug class

Date: 2026-07-06   Area: frontend

**Context**: The same entity cached under two ad-hoc keys (`['user']` AND
`['current-user']`, `['usage']` AND `['copilot-usage']`) meant an update invalidated one
copy and the UI served the other — a split-brain cache users see as stale data. F1
created a single registry of key factories and migrated every call site; an ESLint
`no-restricted-syntax` rule now bans array-literal `queryKey:` values outside the
registry, so the invariant is machine-enforced.

**Rule**: Every query key — including in `invalidateQueries` / `setQueryData` /
`cancelQueries` — comes from a `queryKeys.*` factory. New entities add a factory first.
Prefix-invalidation families get an `all()` + `list(filters)` pair (TanStack partial
matching). Never bypass the lint rule; if it fires, the fix is a registry entry, not a
disable comment.

**Evidence**: `frontend/lib/queryKeys.ts` (registry + reconciliation notes);
`frontend/eslint.config.mjs` (the enforcing rule); PRs #551 (F1 core) / #553 (full
adoption, tuple-identity verified).
