# Audit Execution — todo (COMPLETE)

Branch: `claude/earnings-nerd-audit-ovjet5`. Approved plan, executed as 6 commits.

## PR 1 — Secret hygiene & dead-config removal (P0) ✅ 6c4313c
- [x] Untrack backend/.env.bak; gitignore .env.*/*.env.bak (root + backend, with !.example negations)
- [x] Removed Firebase stack (firebase.json, .firebaserc, firestore.rules/indexes, .firebase/,
      public/ default pages, root deploy.sh, root package.json + lock)
- [x] Removed start_production.sh (Render), sync.sh (bypassed CI), duplicate root runtime.txt
- [x] Untracked + gitignored tsconfig.tsbuildinfo, .lighthouseci/, playwright-report/, test-results/

## PR 2 — Deploy config (P1) ✅ 0175887
- [x] engines.node=20.x + frontend/.nvmrc
- [~] vercel.json consolidation + DSN: SKIPPED per maintainer (root-dir unconfirmed); documented in DEPLOYMENT.md

## PR 3 — Documentation overhaul (P0) ✅ bf486f4
- [x] Root .md 39 -> 3 (README, CLAUDE, CONTRIBUTING)
- [x] docs/history/{render,stage1_5,fix-notes,plans}/ via git mv (history preserved)
- [x] Deleted PR_DESCRIPTION.md + docs/codebase-restructuring-prompt.md
- [x] New: README (rewritten), CONTRIBUTING, docs/{ARCHITECTURE,DEPLOYMENT,DATA_COMPLIANCE}.md,
      backend/.env.example, frontend/.env.local.example
- [x] Moved DATA_RETENTION_POLICY, TROUBLESHOOTING, resend-webhooks into docs/
- NOTE: compliance "gaps" were already implemented (export/delete endpoints, CookieConsent) ->
  wrote an accurate DATA_COMPLIANCE.md instead of concatenating the stale plan (archived it).

## PR 4 — Accuracy fixes (P1) ✅ 002a84c
- [x] gemini-3-pro-preview -> gemini-3.1-pro-preview; Stripe webhook location; Next 14 -> 16

## PR 5 — Karpathy skill (P2) ✅ e6b75c1
- [x] Vendored to .claude/skills/meta/karpathy-guidelines/ pinned to 2c60614 (reviewed); CLAUDE.md pointer
- Skipped plugin (per-user) + Cursor rule (minimal footprint)

## PR 6 — Test & CI hardening (P0/High) ✅ ef911cc
- [x] Stripe webhook tests (+ fixed a real 500-masking bug in the handler)
- [x] Auth register->login->/me round-trip tests
- [x] Fixed N+1 in filings.py
- [x] tsconfig target es5->ES2020; added typecheck script + CI gate (app code clean)
- [~] ruff blocking DEFERRED: 146 existing findings to clear first
- [~] `next lint` gate DEFERRED: removed in Next 16, needs ESLint flat-config migration
- Verified: backend 228 passed (incl. 10 new); frontend 30 passed; tsc app-only exit 0; ci.yml valid

## Deferred (separate design sign-off, NOT done this pass)
- H2 reconcile the two summary pipelines (partial-cache divergence — correctness)
- H3 retire legacy sec_edgar.py / dead app/services/xbrl_service.py
- A11 route cheap AI tasks to gemini-2.5-flash (validate via evals)
- Frontend: ESLint flat-config migration; Next16+React18 version skew; ruff cleanup
