# Audit Execution — todo

Branch: `claude/earnings-nerd-audit-ovjet5`. Approved plan, 6 commits.

## PR 1 — Secret hygiene & dead-config removal (P0)
- [ ] `git rm --cached backend/.env.bak`; gitignore `.env.bak`/`.env.*` (root + backend)
- [ ] Remove Firebase stack: firebase.json, .firebaserc, firestore.rules, firestore.indexes.json, .firebase/, root deploy.sh, root package.json + package-lock.json
- [ ] Remove start_production.sh (Render), sync.sh (bypasses CI), duplicate root runtime.txt
- [ ] Untrack + gitignore build artifacts: tsconfig.tsbuildinfo, .lighthouseci/, playwright-report/, test-results/
- [ ] Verify: no runtime firebase refs; git status clean

## PR 2 — Deploy config consolidation (P1)
- [ ] Verify Vercel root-dir, then delete one vercel.json; strip hardcoded Sentry DSN
- [ ] Add engines.node + .nvmrc
- [ ] Verify build

## PR 3 — Documentation overhaul (P0)
- [ ] docs/history/{render,stage1_5,fix-notes,plans}/ + git mv abandoned/planning docs
- [ ] rm PR_DESCRIPTION.md, docs/codebase-restructuring-prompt.md
- [ ] Merge compliance -> docs/DATA_COMPLIANCE.md; move retention/troubleshooting/resend into docs/
- [ ] Create docs/DEPLOYMENT.md, docs/ARCHITECTURE.md, CONTRIBUTING.md, backend/.env.example, frontend/.env.local.example
- [ ] Rewrite README.md (investor-grade, accurate stack)
- [ ] Verify: links resolve; root has only README/CLAUDE/CONTRIBUTING md

## PR 4 — CLAUDE.md accuracy (P1)
- [ ] Fix model name, Stripe handler location, Next 16, Firebase removed

## PR 5 — Karpathy skill vendored+pinned (P2)
- [ ] Vendor skill into .claude/skills/meta/karpathy-guidelines/ with pinned SHA + provenance
- [ ] One-line pointer in CLAUDE.md

## PR 6 — Test & CI hardening (P0/High)
- [ ] Stripe webhook + auth round-trip tests
- [ ] Fix N+1 in filings.py:377
- [ ] CI: frontend lint + tsc job; assess ruff blocking
- [ ] Verify: tests + CI green

## Deferred (separate design): H2 pipelines, H3 SEC backends, A11 AI cost routing
