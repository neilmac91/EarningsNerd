# Lessons

Hard-won operating rules — one per file, 48 of them. Scan the table below and open what applies to your task BEFORE you start (CLAUDE.md points here). Each file's H1 is the one-line rule; the body carries **Area · Date** then the context, the rule, and the evidence.

## Format & upkeep

After ANY correction from the user, or a mistake you catch yourself, add a new file here:

```markdown
# <one-line imperative rule>

**Area:** <area> · **Date:** <YYYY-MM-DD>

<context: what happened / the symptom>

**Rule:** <the operating rule>

<evidence: file:line refs or the concrete case>
```

Keep them greppable and specific. Lessons are the mutable HOW; settled WHY lives in `docs/adr/`.

## Index

### process

- [A mid-session env/secret update does not reach the running shell — fingerprint the value before debugging](mid-session-env-updates-dont-reach-the-running-shell.md)
- [Re-read the actual files before implementing a plan item — confirm the gap is real](verify-against-code-before-implementing-a-plan-item.md)
- [Single-sourcing config canonizes any false promise; moving a file breaks out-of-diff refs — grep the whole repo](canonizing-config-canonizes-false-promises-and-breaks-refs.md)
- [When a plan cites a specific site for a bug, fix and test THAT site — an adjacent fix doesn't discharge the citation](fix-the-plans-exact-cited-site-not-an-adjacent-one.md)

### testing

- [A destructive bulk delete must be FK-safe by construction — SQLite-green is not Postgres-safe](fk-enforced-in-postgres-not-sqlite-tests.md)
- [A test outside the CI collection path gives zero coverage and has rotted — run it isolated before 'adopting'](orphaned-tests-are-bit-rotted-verify-before-adopting.md)
- [CI collects only backend/tests/{unit,integration,smoke,performance} + frontend/tests — a test elsewhere does not run](the-only-test-roots-ci-runs.md)
- [CI e2e (Playwright) runs with NO backend — prod telemetry is the only real end-to-end signal](e2e-runs-without-a-backend.md)
- [Contract tests (SSE stream, auth flow, Stripe webhooks) must not be edited in the same PR as the code they guard](contract-tests-are-locked.md)
- [Every marker you deselect in addopts needs an explicit CI run-path, or it's a silent skip](a-deselected-marker-with-no-ci-run-path-is-a-silent-skip.md)
- [Relocating a test/script breaks its __file__-relative sys.path shims (cwd-on-path masks it under pytest)](moving-a-test-file-breaks-file-relative-shims.md)
- [Run the full vitest suite (not just next build) for any rendered-text/number/copy change — tests assert exact strings](run-vitest-for-user-visible-copy-changes.md)
- [The test SQLite DB (earningsnerd.db) is a persistent file — rm it after a schema change or rebase](the-persistent-sqlite-test-db-goes-stale.md)
- [Turn a review-time rule into a structural test so it can't silently drift](encode-an-invariant-as-a-structural-test.md)

### ci

- [Run the full backend gate (ruff + bandit + pytest) before every push, not just pytest](run-the-full-backend-gate-ruff-bandit-pytest.md)
- [The CI lint gate runs before tests — a trivial unused import reds the build even if pytest is green](lint-runs-before-tests-in-ci.md)

### refactor

- [A mechanical proof must run against COMMITTED state — a proof that can't fail proves nothing](mechanical-proofs-must-run-against-committed-state.md)
- [Every targeted replace in a sweep must assert the old string is present; grep all token variants first](batch-class-string-replaces-need-per-site-asserts.md)
- [Prove a large 'pure move' with an AST-normalized per-symbol diff — don't rely on reviewing the shuffle](verify-a-pure-move-with-an-ast-normalized-per-symbol-diff.md)
- [Verify a risky classification or deletion with N independent refute-first lenses, not one pass](three-lens-adversarial-verification.md)

### backend

- [Prefer a committed, auditable universe over a live feed for a listing surface; make the filter fail OPEN](narrow-a-discovery-surface-to-a-committed-universe.md)
- [Redis is OFF in production — the two-tier cache runs L1 (in-memory) only](redis-is-off-in-prod.md)
- [Summary generation has ONE orchestrator — stream_filing_summary; cron/background drain it](one-summary-orchestrator.md)

### frontend

- [All React Query keys live in lib/queryKeys.ts — enforced by an eslint rule, not convention](query-keys-live-in-one-registry.md)

### frontend-build

- [<Button loading> sets aria-disabled, not native disabled — guard the form submit handler with an early return](button-loading-is-not-native-disabled.md)
- [Client-only exports (buttonVariants, hooks) can't be called in a Server Component — run next build to catch it](buttonvariants-is-a-client-export.md)

### design-system

- [Green CI is not correct visuals — review the preview in both light and dark before done](green-ci-is-not-correct-visuals-eyeball-both-themes.md)
- [Never set a global element-level color that surfaces opt out of](no-global-element-level-colors-that-fight-the-surface.md)
- [Reserve loud status colors (blue/green/red) for real state; brand sage is for actions/accents](reserve-loud-status-colors-for-genuine-status.md)
- [Treat a theme/token migration as app-wide by default; the repo-wide grep is the done-gate](theme-token-migration-is-app-wide.md)
- [Verify a surface's luminance delta vs the background it sits on, not just that a token exists](check-luminance-against-the-actual-background.md)

### ai-evals

- [An LLM judge must get the same (or superset) context the generator did, or it invents 'hallucinations'](an-llm-judge-must-see-the-same-source-as-the-generator.md)
- [Bake off a model swap the way prod runs it — hold every knob (thinking mode, tokens, temp) constant](bake-off-a-model-swap-the-way-prod-runs-it.md)
- [Don't pre-compute deltas (YoY%) into the grounding when the prompt also asks the model to explain changes — it fabricates causes](dont-pre-chew-deltas-into-the-grounding.md)
- [Don't ship an amplifier that adds fabrication risk without a measurable quality gain — bad trade for a trust product](dont-ship-an-amplifier-that-adds-risk-without-measurable-gain.md)
- [Not every judge-flagged category is a prompt problem — stop tuning prose when flags are heterogeneous or prompt-compliant](know-when-to-stop-tuning-prose.md)
- [Smoke 1-2 items and INSPECT the raw model result before a long run — auth/credits/params fail silently as 0](smoke-and-inspect-a-model-run-before-committing-to-it.md)
- [The judge-context rule applies to EVERY grounding channel — audit excerpt AND XBRL AND tool output for truncation caps](audit-every-generator-grounding-channel-for-truncation.md)
- [To change model behavior, edit the lead directive that causes it and pair the rule with a concrete worked example](edit-the-directive-that-causes-behavior-and-show-an-example.md)
- [When an error class is invisible to deterministic scorers (currency/units), add a dedicated guard; inspect worst per-item cases](add-a-deterministic-guard-for-scorer-blind-classes.md)
- [prompt_loader caches at import; re-verify one golden entry by its pinned accession, not the full builder](eval-ergonomics-prompt-cache-and-pinned-reverify.md)

### edgar-data

- [Never derive a semantic event from a regulatory category alone — require an independent corroborating signal](8k-item-2-02-is-not-an-earnings-release.md)
- [The SEC 10 req/s limit is per-IP / per-process, not global — N instances multiply it](sec-rate-limits-are-per-process.md)

### security

- [Enforce any access/gating rule in the backend at the mutation endpoint — middleware is UX only](enforce-access-server-side-not-in-middleware.md)

### deploy

- [Never run schema-altering DDL in the serving container's startup path on a rolling-deploy platform](no-schema-migrations-in-the-serving-startup-path.md)
- [No Alembic — fresh schema via create_all; every table change is an idempotent SQL file re-applied each deploy](no-alembic-idempotent-sql-migrations.md)

### git

- [Treat PRs editing the same file within ~3 lines as conflicting — merge them serially](adjacent-line-edits-conflict-on-merge.md)
- [git add is atomic across pathspecs — one bad path stages nothing; require an empty git status before push](git-add-is-atomic-across-pathspecs.md)
