# Task: Review & land Dependabot PRs #463 (frontend) + #464 (backend)

## Context
- **#463** frontend npm minor-group: `@sentry/nextjs 10.59→10.62`, `@tanstack/react-query 5.101.0→5.101.2`,
  `autoprefixer 10.5.0→10.5.2`, `posthog-js 1.392→1.395`, `recharts 3.8.1→3.9.0`,
  `@playwright/test 1.61.0→1.61.1`, `@types/node 26.0.0→26.0.1`, `@vitejs/plugin-react 6.0.2→6.0.3`.
- **#464** backend pip minor-group: `edgartools 5.39→5.40`, `fastapi 0.138.0→0.138.1`, `openai 2.43→2.44`,
  `pandas 3.0.3→3.0.4`, `posthog 7.19.2→7.21.0`, `redis 8.0.0→8.0.1`, `stripe 15.2.1→15.3.0`.
- Both PRs are **green CI** but based on a **stale main** (`25b50a46`; main now `2a8b040`).
- Decision: **consolidate** both validated bumps onto designated branch `claude/pr-463-464-review-y06jsx`,
  verify lockfiles, run full suites locally on up-to-date main, supersede both PRs with one PR.

## Plan
- [x] Pull both Dependabot branches; confirm manifest deltas are clean (only bumped lines).
- [x] Apply exact Dependabot manifests + lockfiles onto designated branch.
- [x] Install backend (venv) + frontend (`npm ci`) — lockfiles consistent (npm ci exit 0; pip exit 0).
- [ ] Expert review (workflow): per-package usage × changelog × **latest-available** × code-change risk.
- [ ] Adversarial verify on any flagged breaking change.
- [ ] Apply any required compatibility code changes.
- [ ] Run suites: backend `pytest`, frontend `lint`/`typecheck`/`test`/`build`.
- [ ] Decide on "bump further" (newer releases since 06-29) — stay within minor/patch risk class.
- [ ] Commit, push, open draft PR superseding #463/#464.

## Expert review outcome (16-agent workflow + adversarial verify)
- **Every bump: risk none/low; ZERO code changes attributable to any dependency.** Matches green suites.
- High-risk deps cleared at changelog level:
  - `edgartools 5.40`: new proxy/registration/prospectus section extraction + offerings fixes do **not**
    touch our 10-K (1A/7/8) / 10-Q / XBRL paths. Safe.
  - `recharts 3.9`: no breaking prop/axis/tooltip changes for our charts. Safe.
- **Bumped-further check (user ask):** 5 packages had newer releases since 06-29, all low-risk same-class.
  Decision: **roll all 5 forward** — edgartools 5.40.1, fastapi 0.138.2, posthog 7.21.1, recharts 3.9.1
  (patches) + posthog-js 1.396.3 (minor). Others already at latest.
- **Pre-existing bug found (orthogonal to bumps):** `posthog_client.py:60` called PostHog's event-first
  `capture()` with the legacy positional `(distinct_id, event, properties)` → `TypeError` silently
  swallowed → backend funnel + copilot-cost events dropped. Broken on main since posthog 6.x (event-first),
  NOT caused by this bump. Decision: **fix in a separate commit** + lock with updated test assertions.

## Results
- [x] Pull both Dependabot branches; confirm manifest deltas clean.
- [x] Apply exact Dependabot manifests + lockfiles; verify lockfile consistency (npm ci / pip).
- [x] Expert review (workflow) + adversarial verify.
- [x] Roll 5 packages forward to latest; regenerate lockfiles.
- [x] Fix pre-existing posthog capture bug (separate commit) + update test_funnel_telemetry.py.
- [x] Re-run suites on rolled-forward pins: pip check clean, backend pytest 907 passed; frontend
      lint + typecheck + vitest (236) + next build all green. posthog 7.21.1 capture sig verified event-first.
- [x] Commit (deps roll-forward + posthog fix as separate commits), push, open draft PR superseding #463/#464.

## Done
- Draft PR **#482** opened (supersedes #463 + #464). Commits: `19f274c` (deps), `9ed5444` (posthog fix).
- Action determined: both Dependabot PRs were safe minor bumps on a stale base → consolidated, rebased,
  rolled forward to latest same-risk-class releases, re-verified on current main. One pre-existing
  analytics bug fixed as a byproduct. No dependency required a compatibility code change.
