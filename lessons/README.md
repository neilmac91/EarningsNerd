# Lessons — hard-won operating rules, one per file

The project's mutable HOW, complementing `docs/adr/` (the immutable WHY). Each file is one
lesson: an imperative one-line rule as the title, then Date/Area, **Context** (what happened),
**Rule** (mechanically followable), **Evidence** (file:line / PR refs).

**Workflow**: after ANY correction from the founder — or any hard-won discovery — add or update a
file here (never append to a monolith). At session start read "Operations & workflow (every
task)" plus the section for your task area; read "Evals, judging, paid runs and the founder's
machine" only for that work; skip "Enforced by a machine gate" (CI fails those on its own) and
"Archived". Filenames are greppable by prefix: `arch-*`, `sec-*`, `test-*`, `frontend-*`,
`evals-*`, `ops-*`. Entries are `file — rule`.


## Operations & workflow (every task)

- ops-auth-lookups-must-let-request-cleanup-progress.md — Keep authentication pool waits off the event loop while preserving request-owned sessions
- ops-bound-drain-batches-to-job-memory.md — Bound a regeneration batch by the job container's memory, not by its time budget alone
- ops-continue-approved-engineering.md — Continue the approved queue after verified releases and preserve specific founder holds
- ops-demote-a-lesson-only-when-its-whole-rule-is-gated.md — Demote a lesson from session reading only when every clause of its rule is machine-gated and proven on the bad case
- ops-deploy-owned-state-needs-a-distinctive-name.md — Give deploy-owned tables a name nothing else could have created; CREATE TABLE IF NOT EXISTS adopts strangers
- ops-finish-only-job-owned-read-transactions.md — Finish the CLI's read transaction before transport while preserving attached inputs
- ops-fix-the-exact-cited-site.md — Fix and test the plan's exact cited site, not an adjacent manifestation
- ops-git-add-atomic-empty-status-gate.md — Require an empty git status after every completing commit; never chain add-path recovery
- ops-grep-verify-negative-claims.md — Grep-verify every "no X exists" claim from a workstream report before it enters a synthesis
- ops-job-success-needs-outcome-evidence.md — Persist actual job outcomes; swallowed failures and dry runs never advance last success
- ops-keep-moving-under-standing-authorization.md — Keep moving under a standing founder authorization; stop only at the boundaries still held
- ops-mutate-only-committed-state.md — mutation proofs run on committed state only; `git checkout --` restores HEAD, not your edit
- ops-no-ddl-in-startup-path.md — Never run schema-altering DDL in the serving container's startup path
- ops-one-test-process-per-worktree.md — one test process per worktree; never run pytest beside a running gate
- ops-release-cached-filing-reads-before-yield.md — Close completed filing reads before async dependency cleanup can be blocked by a competing checkout
- ops-serial-merge-adjacent-line-prs.md — Serialize merges of PRs that edit the same file within a few lines
- ops-true-config-descriptions-grep-file-moves.md — Make canonized config descriptions literally true and grep the whole repo when moving files
- ops-unmergeable-pr-runs-no-pull-request-workflows.md — Check the PR's mergeable state before diagnosing missing `pull_request` workflow runs
- ops-validate-workflow-inputs-before-pipeline.md — Validate workflow inputs before `pipeline()`; a throw inside a stage is a silent drop, and a `null` agent result is no result, never clearance
- ops-verify-env-updates-reach-session.md — Fingerprint env values in the running shell before debugging a rotated secret
- ops-verify-plan-gaps-against-code.md — Re-read the actual code before implementing any plan item marked missing
- ops-write-down-the-second-anomaly-before-chasing-the-first.md — Write down the second anomaly before chasing the first — a parked finding is a lost finding

## Evals, judging, paid runs and the founder's machine (read for that work)

- evals-accept-a-prompt-change-on-two-runs-not-one.md — one generated run sets a direction, never an effect size; report the range across two
- evals-test-the-row-shape-the-producer-writes.md — a consumer of another module's records is tested on that producer's real row shape, and its identity rule against the committed data
- ops-ai-evidence-is-not-human-acceptance.md — Use explicit model/source evidence when the founder cannot supply a human panel
- ops-capacity-projection-withholds-command-values.md — Withhold command values and execute the real readback projection in a privacy gate
- ops-eval-gate-for-ai-changes.md — Gate every AI/prompt/model change on the eval regression gate — and re-pin the baseline in the same PR
- ops-evidence-exports-verify-themselves-and-survive-git.md — An evidence export copies everything, verifies its copy, states its own eligibility, and is gated against ignore rules that silently drop inventoried files; a verdict that depends on another tool reruns that tool on the current inputs, and a receipt on disk is evidence only
- ops-founder-runs-claude-in-the-mac-app.md — Address founder instructions to the Claude desktop app, and give `claude -p` its own login
- ops-judge-cli-pins-need-a-drift-plan.md — Pin the judge CLI by version, but decide in advance what happens when the container image drifts
- ops-keep-worktrees-out-of-icloud-documents.md — Keep worktrees, virtual environments and bytecode caches out of iCloud-synced Documents
- ops-place-a-provider-stall-before-paying-again.md — Place a provider stall at one layer with free probes before paying for another corpus
- ops-price-the-actual-provider-model.md — Price each actual returned model at its own published tariff
- ops-repin-binds-advisory-dims-sync-doc.md — A re-pin that first records an advisory eval dimension makes its "advisory" doc stale — sync it in the same PR
- ops-the-subscription-judge-has-a-usage-limit.md — probe `is_error` before a long judge run; an exhausted subscription looks like exit 1 with empty stderr

## Architecture

- arch-acquisition-period-withholding-needs-whole-claims.md — Preserve closed authored continuations when withholding ambiguous acquisition-period claims
- arch-admit-authored-evidence-before-repair.md — Match the real evidence selector and admit authored evidence before fuzzy repair
- arch-admit-copilot-answers-before-publication.md — Hold answer prose until citation admission and preserve truthful request completion
- arch-bind-bare-table-figures-to-the-declared-scale.md — Bind a bare dollar figure copied from a scaled table to the table's declared scale
- arch-capital-comparisons-need-source-ownership.md — Own qualified comparisons and source-attributed capital passages in code
- arch-code-owned-render-eligibility.md — Keep application-owned render eligibility separate from model payloads and generation stamps
- arch-committed-universe-fail-open.md — Bound discovery surfaces to a committed universe with a fail-open filter
- arch-corroborate-semantic-events.md — Corroborate a semantic event; never derive it from a regulatory category alone
- arch-drop-neutral-amplifiers-with-risk.md — Don't ship an amplifier that adds no measurable quality but any fabrication risk
- arch-edit-causal-directive-add-example.md — Edit the directive that causes the behavior and pair it with a worked example
- arch-fk-safe-bulk-deletes.md — Make destructive bulk deletes FK-safe by construction, not by trusting the test DB
- arch-gate-reference-values-are-themselves-gated.md — A gate that compares against a token or an exemption set must pin those too
- arch-guard-every-model-facing-surface.md — Suppress a value on EVERY model-facing surface, or the model parrots what the render dropped
- arch-migrations-no-alembic.md — No Alembic: fresh schema via create_all, changes via idempotent SQL applied once through the migration_ledger table
- arch-no-precomputed-deltas-in-grounding.md — Don't pre-chew derived deltas into the grounding without a groundedness guardrail
- arch-one-summary-orchestrator.md — There is ONE summary orchestrator — never add a second generation path
- arch-operand-matches-do-not-authorize-financial-assertions.md — Use tagged operands for bounded withholding without promoting them to assertion authority
- arch-payments-need-allocation-evidence.md — Measure canonical allocations with explicit attribution, coverage and deletion limits
- arch-per-process-state-on-cloud-run.md — In-memory state is per-process — count every Cloud Run instance and job before trusting it
- arch-qualified-income-deltas-need-source-ownership.md — Withhold qualified income arithmetic when attribution and entity ownership are unsupported
- arch-reconciliation-follows-values-and-growth.md — Carry reconciliation quality through values, growth, citations and exports
- arch-redis-off-in-prod.md — Production runs with Redis OFF — the two-tier cache is L1-only in prod
- arch-sitemap-page-eligibility.md — Match sitemap eligibility to the existing page predicates
- arch-source-supplements-preserve-existing-context.md — Retain complete bounded omitted source without displacing existing context
- arch-stop-tuning-prose-know-the-floor.md — Stop tuning prompt prose when judge flags are heterogeneous or prompt-compliant
- arch-structural-gates-over-prose-rules.md — Encode every "never do X again" rule as a machine-checked gate, not prose
- arch-validate-inline-source-identities.md — Validate namespace bindings and qualified tags before selecting inline source facts

## SEC / EDGAR data

- sec-edgar-resilience-layer.md — Preserve SEC pacing and distinguish selected breaker coverage from limiter-only paths
- sec-enforce-gates-server-side.md — Enforce every access gate server-side at the mutation endpoint
- sec-listing-fetch-recent-window-and-cheap-fields.md — List filings in ONE recent-window fetch and read cheap metadata fields — never edgartools properties that hit the network
- sec-runtime-facts-carry-no-duration.md — Runtime per-filing facts carry no duration: abstain, never substitute an annual-looking label
- sec-xbrl-period-selection.md — XBRL facts: select for the filing's OWN reporting period — fy/fp label the filing, not the fact

## Testing & verification

- test-adversarial-lens-verification.md — Verify large mechanical changes with independent adversarial lenses, not one review pass
- test-audit-every-judge-channel-for-truncation.md — Audit every grounding channel the judge sees for its own truncation cap
- test-audit-file-relative-shims-on-move.md — Audit __file__-relative shims whenever relocating a test or script
- test-bakeoff-hold-knobs-constant.md — Bake off model swaps with every knob held constant, verified by one raw-inspected call
- test-conftest-hermetic-env.md — The backend suite is hermetic: conftest sets mock env (incl. SKIP_REDIS_INIT) before app import
- test-contract-tests-are-locked.md — Contract anchors are locked: never edit them in the same PR as the code they guard
- test-deselected-markers-need-ci-paths.md — Give every deselected pytest marker an explicit CI execution path
- test-deterministic-guards-for-scorer-blind-spots.md — Add a dedicated deterministic guard for every error class invisible to existing scorers
- test-e2e-runs-without-backend.md — CI Playwright runs against `next start` with NO backend — specs must tolerate a dead API
- test-empty-truth-sets-score-perfect.md — An empty truth set scores 1.0, not 0 — guard the decision, not the scorer
- test-eval-iteration-ergonomics.md — Exploit prompt-cache and pinned-accession ergonomics when iterating on evals
- test-fixture-months-are-never-the-wall-clock-month.md — Seed fixture months that can never be the wall-clock month; pin the clock where cases depend on it
- test-fresh-bytecode-prefix-before-trusting-local-timing.md — Give every local Python run on this Mac a fresh bytecode-cache prefix before trusting its timing
- test-gates-must-be-as-wide-as-their-rule.md — A gate narrower than its rule is worse than no gate; evaluate the source, don't text-match it
- test-isolate-process-wide-contextvars.md — Isolate process-wide ContextVars per test; CI's file order can hide a leak
- test-judge-context-parity.md — Give an LLM judge the same (or a superset of the) grounding the generator used
- test-leave-the-tree-alone-during-a-background-suite.md — Leave the working tree untouched while a background full-suite run reads it
- test-parser-callback-positions.md — Match whole-input callbacks to exact raw-source positions before accepting event capacity
- test-persistent-sqlite-db-goes-stale.md — The test SQLite DB (earningsnerd.db, CWD-relative — usually backend/) is a persistent file — rm it after a schema change or rebase
- test-proofs-run-on-committed-state.md — Mechanical proofs must run against committed state — a proof that cannot fail proves nothing
- test-pure-move-ast-proof.md — Verify "pure move" refactors with an AST-normalized per-symbol diff, not by eyeballing the diff
- test-smoke-model-runs-before-sweeps.md — Smoke one or two items and inspect raw output before any long or expensive model run
- test-smoke-targets-feature-semantics.md — Distinguish the actual smoke target from similarly named calls to action
- test-tracked-file-gates-run-after-staging.md — Run a `git ls-files` gate after staging its own module, and select targets by name pattern
- test-verify-orphaned-tests-before-adopting.md — Verify orphaned or uncollected tests before adopting them
- test-vitest-for-copy-changes.md — Run vitest before pushing any change to rendered text, numbers, or copy
- test-vitest4-mock-error-tracking.md — Plain-function error mocks avoid handled-error failures; reproduced on Vitest 4 and rechecked on Vitest 5
- test-wire-format-coverage.md — Pin serialized wire formats with tests — suites that only check values let format drift through

## Frontend & design system

- frontend-busy-controls-stay-focusable.md — A control busy with its own request stays focusable: aria-disabled plus an early return, never native disabled (partly gated by `frontend/tests/unit/busyControlsStayFocusable.spec.ts` (AST scan of every .tsx); the keyboard and focus hand-off rules are not)
- frontend-check-luminance-vs-background.md — Verify surface luminance against the actual background, not token validity
- frontend-citation-offset-boundaries.md — Resolve citation starts to the first matched character's text node and pin the actual flash target
- frontend-client-exports-need-next-build.md — Run next build before moving design-system client exports across page files
- frontend-design-docs-need-agent-entrypoints.md — Connect new design references to agent entrypoints, authority and maintenance
- frontend-dialog-opener-outlives-the-dialog.md — Keep a dialog's opener mounted while the dialog is open, so focus has somewhere to return
- frontend-dialog-openers-stay-focusable.md — Keep a dialog's opener focusable through its pending and cooldown states — aria-disabled, not native disabled
- frontend-dialog-trap-arms-once-per-open.md — Arm a dialog's focus trap once per open; never key its effect on a callback prop's identity
- frontend-focus-opened-popovers-survive-the-focusing-scroll.md — A popover that opens on focus re-anchors on the scroll that focusing caused; only a hover popover closes on scroll
- frontend-guard-a-loader-two-effects-can-start-in-one-commit.md — Guard a loader with a synchronous in-flight ref when two effects can start it in one commit
- frontend-guard-submit-on-loading-buttons.md — Guard submit handlers with an early return when the button uses loading, not disabled
- frontend-jsdom-sdk-browser-entry.md — Resolve browser SDK imports as browser code in jsdom tests while preserving real capture behavior
- frontend-locked-page-dialog-scrolls-itself.md — A dialog that locks the page must bound itself to the viewport and scroll inside
- frontend-native-modal-dialog-makes-body-portals-inert.md — Under a native showModal() dialog, portal into the dialog and preventDefault the keys you own (partly gated by `frontend/tests/unit/dialogAllowlist.spec.ts`; the keyboard and focus hand-off rules are not)
- frontend-no-surface-fighting-global-colors.md — Never set a global element-level color that surfaces must opt out of
- frontend-overrides-rot-when-the-constrained-package-moves.md — An npm override's meaning is set by the package it constrains — re-check every override on a major bump
- frontend-preview-both-themes-before-done.md — Eyeball the deployed preview in both themes before declaring visual work done
- frontend-reserve-fixed-chrome-with-scroll-padding.md — A focus scroll stops at the viewport edge, not at a fixed overlay: reserve the overlay with scroll-padding
- frontend-route-redesign-needs-a-mount-gate.md — A self-omitting section needs a source-level mount gate — render tests cannot see it go missing
- frontend-site-overlays-outrank-in-page-sticky-chrome.md — A fixed site-level overlay ranks above in-page sticky chrome, and the ladder gate scans sticky sites too
- frontend-sitemap-cache-ownership.md — Cache the rendered sitemap hourly while bypassing Next's fetch Data Cache
- frontend-spinner-gate-on-shared-errored-query.md — Gate a page's spinner on the retained failure when its children observe the same query
- frontend-status-colors-for-status-only.md — Reserve loud status colors for genuine status messages
- frontend-sweep-replaces-need-per-site-asserts.md — Assert every targeted replace in a sweep script and grep all token variants first
- frontend-tailwind-content-scans-class-maps.md — Put every module that composes Tailwind classes under a content glob
- frontend-top-dialog-owns-the-keyboard.md — The top dialog owns the keyboard: listen in window capture and stop the keys it handles
- frontend-trial-labels-use-entitlements.md — Derive current-trial presentation from the resolved entitlement
- frontend-validate-design-sidecars-in-their-consumer.md — Validate design-sidecar specimens in their consumer, and check what its engine reads
- frontend-variable-text-must-not-size-a-wrapping-row.md — Every responsive grid sets its base track (gated: ESLint `earningsnerd/responsive-grid-base-track`); variable-length text must not size a wrapping row (`[contain:inline-size]`, `min-w-0`, `truncate`; review-checked)
- frontend-verify-chart-annotations-on-dense-data.md — Acceptance-test chart annotations on a dense real-world series, never only fixtures

## Enforced by a machine gate — not session reading

The rule is checked by the named gate; open the lesson only when that gate fails or you change it.

- arch-sweep-dead-integration-consumers.md — When an integration is declared dead, sweep every consumer in the same pass — gate: `backend/tests/unit/test_dead_integrations_allowlist.py`
- ops-a-review-you-triggered-is-a-review-you-wait-for.md — A review you triggered is a review you wait for; merging inside it discards what you asked for — gate: `.github/workflows/review-gate.yml` (required status check `review-gate`)
- ops-deploy-detector-mirrors-the-image-context.md — Make the deploy change detector exclude exactly what `.dockerignore` excludes, and gate it with a test — gate: `backend/tests/unit/test_backend_deploy_scope.py`
- ops-migrations-need-lock-timeout.md — Give every migration session a lock_timeout and every deploy job a timeout — idempotent is not lock-free — gate: `backend/tests/unit/test_migration_lock_safety.py`; CLAUDE.md rule 3
- ops-pin-ci-toolchain.md — Pin the lint/security toolchain and select lint rules explicitly — CI must not drift with the tool — gate: `backend/tests/unit/test_migration_lock_safety.py` (unpinned `pip install` check)
- ops-prove-the-permission-route-before-a-gated-session.md — Prove the permission route with a `--help` no-op in the exact allow-rule form before any gated step; a denial there is a stop, not a failed restore; name the mode (Accept edits, not Plan) — gate: `backend/tests/unit/test_e8_launch_kit_matches_allow_rules.py`
- sec-filing-url-format.md — SEC archive URLs: strip CIK leading zeros, strip accession dashes — and sec_url is NOT NULL — gate: `backend/tests/unit/test_filing_url_listeners.py`, `test_sec_gov_importers_allowlist.py`; CLAUDE.md rule 10
- test-one-test-home.md — Tests live in exactly one home per stack — a test outside it does not run in CI — gate: `frontend/tests/unit/testHomesAllowlist.spec.ts`

## Archived (`lessons/archive/`) — superseded by a rule or a gate

- archive/frontend-query-keys-registry.md — React Query keys come from lib/queryKeys.ts — inline key literals are a stale-cache bug class — superseded by the `no-restricted-syntax` queryKey selector in `frontend/eslint.config.mjs`
- archive/frontend-theme-migration-app-wide.md — Treat a design-token/theme migration as app-wide by default — superseded by `frontend/tests/unit/designSystemDoneGate.spec.ts` and CLAUDE.md rule 11
- archive/ops-lint-before-every-push.md — Run ruff (and bandit) before every push, not just pytest — superseded by the CI `backend-tests` job (ruff + bandit) and the FULL gate line in CLAUDE.md
- archive/ops-run-full-backend-gate-before-push.md — Run the full local gate (ruff + bandit + pytest) before any backend push — superseded by the CI `backend-tests` job (ruff + bandit + pytest) and the FULL gate line in CLAUDE.md
