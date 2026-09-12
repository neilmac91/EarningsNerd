# Current-main frontend gate — 2026-09-12

Full frontend gate passed on clean committed `8e9ad24cb643688b7cbc146e0ecd1cfe4a2d069f`. Final process session 5399 exited 0; git status remained empty afterward. No source or configuration edits were made.

Commands: `npm run lint && npx --no-install tsc -p tsconfig.ci.json && npm run test -- --run && npm run build`. Node 22.14.0, npm 10.9.2; package and lock were unchanged. ESLint and standalone TypeScript emitted no diagnostics.

```text
 Test Files  106 passed (106)
      Tests  592 passed (592)
   Start at  11:09:45
   Duration  48.18s (transform 5.89s, setup 9.27s, import 193.39s, tests 16.18s, environment 86.02s)
✓ Compiled successfully in 7.6s
  Finished TypeScript in 6.3s ...
✓ Generating static pages using 7 workers (27/27) in 1799ms
```

Full log: `work/migration-frontend-gate-2026-09-12.log` (SHA-256 `cb937ce931b10f9ae1cbd0d29cd0f3182e3dc602b50bc633ff4a9bb84feb063a`).

## Environment recovery and excluded attempts

The initial run was stopped with exit 143 when the root agent reported concurrent docs edits in the audited worktree. That run is invalidated and does not count; `migration-frontend-gate-2026-09-12-invalidated.log` is preserved. Root restored clean committed state before every subsequent full run.

An external ignored node_modules symlink then caused a deterministic Turbopack filesystem-root failure (exit 1). Two refutations: the path was confirmed to be an external symlink, and the build panic explicitly failed package resolution before application compilation. A stalled copy was stopped before any reinstall. Exact dependencies were restored with `npm ci --offline --no-audit --no-fund`: 1,077 packages in 12s, exit 0, no version or lockfile changes. Failure log retained as `migration-frontend-gate-2026-09-12-symlink-failure.log`.

The sandboxed build then failed on public Google Fonts connections and local Turbopack worker port binding. Escalation resolved fonts but reused cached worker failures. Two checks established the environment cause: explicit EPERM/connection errors matched next/font/google and the loader worker; the same source passed after moving only generated .next cache outside the worktree and rerunning the full chain with escalation. Both `migration-frontend-gate-2026-09-12-sandbox-failure.log` and `migration-frontend-gate-2026-09-12-escalated-cache-failure.log` are preserved. These are deterministic environment failures, not flakes.

## Scope and limitations

The gate covers all current frontend source, including the #814 landing redesign. DESIGN_SYSTEM.md was read. Its legacy brand/type grep returned no matches across app/components/features. This does not establish both-theme Vercel preview acceptance, browser behavior, real account access, or factual acceptance of marketing claims.

The successful build emitted the existing middleware-convention deprecation and Sentry missing-auth-token warnings (no release or source-map upload). The build log also reports Sentry build telemetry. Vitest emitted expected error-boundary and jsdom navigation stderr while all tests passed.
