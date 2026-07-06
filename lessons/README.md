# Lessons — hard-won operating rules, one per file

The project's mutable HOW, complementing `docs/adr/` (the immutable WHY). Each file is one
lesson: an imperative one-line rule as the title, then Date/Area, **Context** (what
happened), **Rule** (mechanically followable), **Evidence** (file:line / PR refs).

**Workflow**: after ANY correction from the founder — or any hard-won discovery — add or
update a file here (never append to a monolith). Scan this index at session start; open
what applies to your task. Filenames are greppable: `arch-*`, `sec-*`, `test-*`,
`frontend-*`, `ops-*`.


## Architecture

- [`arch-committed-universe-fail-open.md`](./arch-committed-universe-fail-open.md) — Bound discovery surfaces to a committed universe with a fail-open filter
- [`arch-corroborate-semantic-events.md`](./arch-corroborate-semantic-events.md) — Corroborate a semantic event; never derive it from a regulatory category alone
- [`arch-drop-neutral-amplifiers-with-risk.md`](./arch-drop-neutral-amplifiers-with-risk.md) — Don't ship an amplifier that adds no measurable quality but any fabrication risk
- [`arch-edit-causal-directive-add-example.md`](./arch-edit-causal-directive-add-example.md) — Edit the directive that causes the behavior and pair it with a worked example
- [`arch-fk-safe-bulk-deletes.md`](./arch-fk-safe-bulk-deletes.md) — Make destructive bulk deletes FK-safe by construction, not by trusting the test DB
- [`arch-migrations-no-alembic.md`](./arch-migrations-no-alembic.md) — No Alembic: fresh schema via create_all, changes via idempotent SQL re-applied on EVERY deploy
- [`arch-no-precomputed-deltas-in-grounding.md`](./arch-no-precomputed-deltas-in-grounding.md) — Don't pre-chew derived deltas into the grounding without a groundedness guardrail
- [`arch-one-summary-orchestrator.md`](./arch-one-summary-orchestrator.md) — There is ONE summary orchestrator — never add a second generation path
- [`arch-per-process-state-on-cloud-run.md`](./arch-per-process-state-on-cloud-run.md) — In-memory state is per-process — count every Cloud Run instance and job before trusting it
- [`arch-redis-off-in-prod.md`](./arch-redis-off-in-prod.md) — Production runs with Redis OFF — the two-tier cache is L1-only in prod
- [`arch-stop-tuning-prose-know-the-floor.md`](./arch-stop-tuning-prose-know-the-floor.md) — Stop tuning prompt prose when judge flags are heterogeneous or prompt-compliant
- [`arch-structural-gates-over-prose-rules.md`](./arch-structural-gates-over-prose-rules.md) — Encode every "never do X again" rule as a machine-checked gate, not prose
- [`arch-sweep-dead-integration-consumers.md`](./arch-sweep-dead-integration-consumers.md) — When an integration is declared dead, sweep every consumer in the same pass

## SEC / EDGAR data

- [`sec-edgar-resilience-layer.md`](./sec-edgar-resilience-layer.md) — All SEC/EDGAR access goes through the edgar layer: limiter + circuit breaker + timeout — and keep local-parse timeouts out of the breaker
- [`sec-enforce-gates-server-side.md`](./sec-enforce-gates-server-side.md) — Enforce every access gate server-side at the mutation endpoint
- [`sec-filing-url-format.md`](./sec-filing-url-format.md) — SEC archive URLs: strip CIK leading zeros, strip accession dashes — and sec_url is NOT NULL
- [`sec-xbrl-period-selection.md`](./sec-xbrl-period-selection.md) — XBRL facts: select for the filing's OWN reporting period — fy/fp label the filing, not the fact

## Testing & verification

- [`test-adversarial-lens-verification.md`](./test-adversarial-lens-verification.md) — Verify large mechanical changes with independent adversarial lenses, not one review pass
- [`test-audit-every-judge-channel-for-truncation.md`](./test-audit-every-judge-channel-for-truncation.md) — Audit every grounding channel the judge sees for its own truncation cap
- [`test-audit-file-relative-shims-on-move.md`](./test-audit-file-relative-shims-on-move.md) — Audit __file__-relative shims whenever relocating a test or script
- [`test-bakeoff-hold-knobs-constant.md`](./test-bakeoff-hold-knobs-constant.md) — Bake off model swaps with every knob held constant, verified by one raw-inspected call
- [`test-conftest-hermetic-env.md`](./test-conftest-hermetic-env.md) — The backend suite is hermetic: conftest sets mock env (incl. SKIP_REDIS_INIT) before app import
- [`test-contract-tests-are-locked.md`](./test-contract-tests-are-locked.md) — Contract anchors are locked: never edit them in the same PR as the code they guard
- [`test-deselected-markers-need-ci-paths.md`](./test-deselected-markers-need-ci-paths.md) — Give every deselected pytest marker an explicit CI execution path
- [`test-deterministic-guards-for-scorer-blind-spots.md`](./test-deterministic-guards-for-scorer-blind-spots.md) — Add a dedicated deterministic guard for every error class invisible to existing scorers
- [`test-e2e-runs-without-backend.md`](./test-e2e-runs-without-backend.md) — CI Playwright runs against `next start` with NO backend — specs must tolerate a dead API
- [`test-eval-iteration-ergonomics.md`](./test-eval-iteration-ergonomics.md) — Exploit prompt-cache and pinned-accession ergonomics when iterating on evals
- [`test-judge-context-parity.md`](./test-judge-context-parity.md) — Give an LLM judge the same (or a superset of the) grounding the generator used
- [`test-one-test-home.md`](./test-one-test-home.md) — Tests live in exactly one home per stack — a test outside it does not run in CI
- [`test-persistent-sqlite-db-goes-stale.md`](./test-persistent-sqlite-db-goes-stale.md) — The test SQLite DB (earningsnerd.db, CWD-relative — usually backend/) is a persistent file — rm it after a schema change or rebase
- [`test-proofs-run-on-committed-state.md`](./test-proofs-run-on-committed-state.md) — Mechanical proofs must run against committed state — a proof that cannot fail proves nothing
- [`test-pure-move-ast-proof.md`](./test-pure-move-ast-proof.md) — Verify "pure move" refactors with an AST-normalized per-symbol diff, not by eyeballing the diff
- [`test-smoke-model-runs-before-sweeps.md`](./test-smoke-model-runs-before-sweeps.md) — Smoke one or two items and inspect raw output before any long or expensive model run
- [`test-verify-orphaned-tests-before-adopting.md`](./test-verify-orphaned-tests-before-adopting.md) — Verify orphaned or uncollected tests before adopting them
- [`test-vitest-for-copy-changes.md`](./test-vitest-for-copy-changes.md) — Run vitest before pushing any change to rendered text, numbers, or copy
- [`test-vitest4-mock-error-tracking.md`](./test-vitest4-mock-error-tracking.md) — Don't test error paths through a vi.fn-mocked module — vitest 4 re-reports the handled error and fails the test
- [`test-wire-format-coverage.md`](./test-wire-format-coverage.md) — Pin serialized wire formats with tests — suites that only check values let format drift through

## Frontend & design system

- [`frontend-check-luminance-vs-background.md`](./frontend-check-luminance-vs-background.md) — Verify surface luminance against the actual background, not token validity
- [`frontend-client-exports-need-next-build.md`](./frontend-client-exports-need-next-build.md) — Run next build before moving design-system client exports across page files
- [`frontend-guard-submit-on-loading-buttons.md`](./frontend-guard-submit-on-loading-buttons.md) — Guard submit handlers with an early return when the button uses loading, not disabled
- [`frontend-no-surface-fighting-global-colors.md`](./frontend-no-surface-fighting-global-colors.md) — Never set a global element-level color that surfaces must opt out of
- [`frontend-preview-both-themes-before-done.md`](./frontend-preview-both-themes-before-done.md) — Eyeball the deployed preview in both themes before declaring visual work done
- [`frontend-query-keys-registry.md`](./frontend-query-keys-registry.md) — React Query keys come from lib/queryKeys.ts — inline key literals are a stale-cache bug class
- [`frontend-status-colors-for-status-only.md`](./frontend-status-colors-for-status-only.md) — Reserve loud status colors for genuine status messages
- [`frontend-sweep-replaces-need-per-site-asserts.md`](./frontend-sweep-replaces-need-per-site-asserts.md) — Assert every targeted replace in a sweep script and grep all token variants first
- [`frontend-theme-migration-app-wide.md`](./frontend-theme-migration-app-wide.md) — Treat a design-token/theme migration as app-wide by default

## Operations & workflow

- [`ops-eval-gate-for-ai-changes.md`](./ops-eval-gate-for-ai-changes.md) — Gate every AI/prompt/model change on the eval regression gate — and re-pin the baseline in the same PR
- [`ops-fix-the-exact-cited-site.md`](./ops-fix-the-exact-cited-site.md) — Fix and test the plan's exact cited site, not an adjacent manifestation
- [`ops-git-add-atomic-empty-status-gate.md`](./ops-git-add-atomic-empty-status-gate.md) — Require an empty git status after every completing commit; never chain add-path recovery
- [`ops-lint-before-every-push.md`](./ops-lint-before-every-push.md) — Run ruff (and bandit) before every push, not just pytest
- [`ops-no-ddl-in-startup-path.md`](./ops-no-ddl-in-startup-path.md) — Never run schema-altering DDL in the serving container's startup path
- [`ops-run-full-backend-gate-before-push.md`](./ops-run-full-backend-gate-before-push.md) — Run the full local gate (ruff + bandit + pytest) before any backend push
- [`ops-serial-merge-adjacent-line-prs.md`](./ops-serial-merge-adjacent-line-prs.md) — Serialize merges of PRs that edit the same file within a few lines
- [`ops-true-config-descriptions-grep-file-moves.md`](./ops-true-config-descriptions-grep-file-moves.md) — Make canonized config descriptions literally true and grep the whole repo when moving files
- [`ops-verify-env-updates-reach-session.md`](./ops-verify-env-updates-reach-session.md) — Fingerprint env values in the running shell before debugging a rotated secret
- [`ops-verify-plan-gaps-against-code.md`](./ops-verify-plan-gaps-against-code.md) — Re-read the actual code before implementing any plan item marked missing
