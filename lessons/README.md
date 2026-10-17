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

- ops-a-bare-proceed-continues-the-last-instruction.md — Read a bare "proceed" as the founder's last instruction on the decision; only without one does it accept your recommendation
- ops-a-flag-several-processes-read-is-set-in-every-env-map.md — List every process that reads a flag and flip it in every deploy map it is configured from, with its job cadence, in one change (partly gated by `backend/tests/unit/test_section_changes_flag_placement.py` for `ENABLE_SECTION_CHANGES`; the next multi-process flag's gate is review-checked)
- ops-a-piped-gate-does-not-gate.md — Run every verification step of a committing chain unpiped with its exit status checked explicitly; the records-gate wrapper carries the rule
- ops-auth-lookups-must-let-request-cleanup-progress.md — Keep authentication pool waits off the event loop while preserving request-owned sessions
- ops-bound-drain-batches-to-job-memory.md — Bound a regeneration batch by the job container's memory, not by its time budget alone
- ops-ci-images-avoid-docker-hub.md — Pull CI and deploy images through a mirror, never anonymously from Docker Hub
- ops-checkout-never-charges-more-than-the-page-shows.md — Never let checkout charge more than the page shows: lower a price on the backend first, raise it on the page first (a CI job on offer changes and a daily run against the live page check it with the backend's public charge report; a binding change or frontend rollback outside CI is found, not prevented)
- ops-closing-keywords-close-what-they-name.md — Never put a closing keyword before a reference you do not mean to close; the merge closes it, a pull request included (partly gated by `backend/scripts/review_gate.py`, which fails it in a pull request's title, body and commit messages; a squash message typed at merge is review-checked)
- ops-continue-approved-engineering.md — Continue the approved queue after verified releases and preserve specific founder holds
- ops-demote-a-lesson-only-when-its-whole-rule-is-gated.md — Demote a lesson from session reading only when every clause of its rule is machine-gated and proven on the bad case
- ops-denied-reads-report-unverified.md — A denied optional read-back reports UNVERIFIED with a closed failure class; fail closed only on readable evidence
- ops-deploy-owned-state-needs-a-distinctive-name.md — Give deploy-owned tables a name nothing else could have created; CREATE TABLE IF NOT EXISTS adopts strangers
- ops-finish-only-job-owned-read-transactions.md — Finish the CLI's read transaction before transport while preserving attached inputs
- ops-fix-the-exact-cited-site.md — Fix and test the plan's exact cited site, not an adjacent manifestation
- ops-git-add-atomic-empty-status-gate.md — Require an empty git status after every completing commit; never chain add-path recovery
- ops-grep-verify-negative-claims.md — Grep-verify every "no X exists" claim from a workstream report before it enters a synthesis
- ops-hand-over-when-the-harness-refuses-the-conversation.md — Hand over to a fresh session when the harness refuses the conversation, not the action
- ops-job-success-needs-outcome-evidence.md — Persist actual job outcomes; swallowed failures and dry runs never advance last success
- ops-keep-moving-under-standing-authorization.md — Keep moving under a standing founder authorization; stop only at the boundaries still held
- ops-mutate-only-committed-state.md — mutation proofs run on committed state only; `git checkout --` restores HEAD, not your edit
- ops-name-codex-without-its-at-mention.md — Name Codex in GitHub text without its at-mention; one outside a review request starts a Codex task (partly gated by `.claude/hooks/codex_mention_guard.py`; text a command builds as it runs, sessions that load no repository hooks and a person's own write are not)
- ops-never-echo-environment-values.md — Never let a settings error, an output or Sentry carry a secret; a caught error's errors()/json() pass include_input=False, outputs give a secret's presence and length only, Sentry sends no frame locals and withholds each secret setting's whole value on every channel that carries text, and agent probes run under env -i in an export with no .env at any level
- ops-no-ddl-in-startup-path.md — Never run schema-altering DDL in the serving container's startup path
- ops-one-test-process-per-worktree.md — give each test process its own database, and never let a test depend on another test's order or leftovers
- ops-release-cached-filing-reads-before-yield.md — Close completed filing reads before async dependency cleanup can be blocked by a competing checkout (partly gated by `backend/tests/unit/test_cached_filings_pool_lifetime.py`: a burst over the routes it lists, and an AST ratchet that fails a session call on the loop in an async route's own body above that route's ceiling; a session handed to a service on the loop is review-checked)
- ops-serial-merge-adjacent-line-prs.md — Serialize merges of PRs that edit the same file within a few lines
- ops-true-config-descriptions-grep-file-moves.md — Make canonized config descriptions literally true and grep the whole repo when moving files
- ops-unmergeable-pr-runs-no-pull-request-workflows.md — Check the PR's mergeable state before diagnosing missing `pull_request` workflow runs
- ops-validate-workflow-inputs-before-pipeline.md — Validate workflow inputs before `pipeline()`; a throw inside a stage is a silent drop, and a `null` agent result is no result, never clearance
- ops-verify-env-updates-reach-session.md — Fingerprint env values in the running shell before debugging a rotated secret
- ops-verify-plan-gaps-against-code.md — Re-read the actual code before implementing any plan item marked missing, or listing one as open
- ops-write-down-the-second-anomaly-before-chasing-the-first.md — Write down the second anomaly before chasing the first — a parked finding is a lost finding

## Evals, judging, paid runs and the founder's machine (read for that work)

- evals-accept-a-prompt-change-on-two-runs-not-one.md — one generated run sets a direction, never an effect size; report the range across two
- evals-gate-the-primary-sources-share-not-only-its-scores.md — when an output has a primary source and a degrading fallback, gate the share the primary source serves (provenance, absolute HARD floor), not only quality scores; E28's fallback passed every run on a WARN (partly gated by `backend/evals/regression_gate.py`'s native-section check)
- evals-measure-a-copilot-change-on-the-source-production-uses.md — accept a Copilot draw only if its sources were prepared as production's are; record each system-message revision and its measured source (partly gated by `backend/tests/unit/test_copilot_prompt_revisions.py`, which requires the row; what a row says, an overwrite made in both the table and the test, the context message, tool schemas and generation options, a copilot-eval draw's source check (E80; eval-baseline has a native-section share floor since #1347) and classifying a red draw's generations are review-checked)
- evals-test-the-row-shape-the-producer-writes.md — a consumer of another module's records is tested on that producer's real row shape, and its identity rule against the committed data
- ops-ai-evidence-is-not-human-acceptance.md — Use explicit model/source evidence when the founder cannot supply a human panel
- ops-capacity-projection-withholds-command-values.md — Withhold command values and execute the real readback projection in a privacy gate
- ops-copilot-eval-red-is-triaged-never-rerun.md — Triage a red copilot-eval run by the RUNBOOK rule; never re-run it to get a green one
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
- arch-cache-only-reads-that-succeeded.md — Cache only a read that succeeded: a read that degrades to empty on failure tells its caller so, serves that one request and leaves the cache for the next to retry; an off-loop read takes a single-flight lock (partly gated by `backend/tests/unit/test_reporting_this_week_service.py` for reporting-this-week; other caches are review-checked)
- arch-capital-comparisons-need-source-ownership.md — Own qualified comparisons and source-attributed capital passages in code
- arch-code-owned-render-eligibility.md — Keep application-owned render eligibility separate from model payloads and generation stamps
- arch-committed-universe-fail-open.md — Bound discovery surfaces to a committed universe with a fail-open filter
- arch-corroborate-semantic-events.md — Corroborate a semantic event; never derive it from a regulatory category alone
- arch-cross-filing-counts-are-read-behind-an-access-check.md — Read `section_reviews` through `section_review_service` and the cached comparison counts through an allow-listed caller that checks the flag and the viewer's access, never raw (partly gated by `backend/tests/unit/test_section_review_rows_read_through_the_service_allowlist.py` and `backend/tests/unit/test_wording_summaries_access_allowlist.py`, which pin every reader by file and scope; that a listed scope makes its check is review-checked)
- arch-drop-neutral-amplifiers-with-risk.md — Don't ship an amplifier that adds no measurable quality but any fabrication risk
- arch-edit-causal-directive-add-example.md — Edit the directive that causes the behavior and pair it with a worked example
- arch-fk-safe-bulk-deletes.md — Make destructive bulk deletes FK-safe by construction, not by trusting the test DB
- arch-gate-reference-values-are-themselves-gated.md — A gate that compares against a token or an exemption set must pin those too
- arch-guard-every-model-facing-surface.md — Suppress a value on EVERY model-facing surface, or the model parrots what the render dropped
- arch-guard-every-writer-of-the-billing-binding.md — Guard every Stripe handler that writes the account's subscription binding; another subscription's non-entitling event never revokes an entitled one (partly gated by `backend/tests/unit/test_subscription_identity.py`: the late-event cases for the three writers, and a counted inventory of every mention of the binding that fails on a new one; that a newly listed writer carries the guard and asks entitlements.py is review-checked)
- arch-migrations-no-alembic.md — No Alembic: fresh schema via create_all, changes via idempotent SQL applied once through the migration_ledger table
- arch-moved-code-resolves-seams-through-the-patched-module.md — Code moved out of a patched module keeps resolving its collaborators through that module at call time
- arch-no-precomputed-deltas-in-grounding.md — Don't pre-chew derived deltas into the grounding without a groundedness guardrail
- arch-one-summary-orchestrator.md — There is ONE summary orchestrator — never add a second generation path
- arch-only-a-rotated-refresh-token-signals-theft.md — Key the refresh-token theft sweep on a rotated-away token (`replaced_by_id` set), never on any revoked one; before reading a column's state as evidence of an event, list every writer of that column (gated for refresh tokens by `backend/tests/unit/test_refresh_token_revocation_kinds.py` and, for every mention of `replaced_by_id`, so rotation stays its only writer, `test_replaced_by_id_writers_allowlist.py`; the general clause is review-checked)
- arch-operand-matches-do-not-authorize-financial-assertions.md — Use tagged operands for bounded withholding without promoting them to assertion authority
- arch-own-a-librarys-silent-input-limit.md — Apply a library's input limit in our own code and test past it when stored records depend on it; a major bump can turn its silent truncation into an error (partly gated by `backend/tests/unit/test_password_byte_limit.py` for bcrypt's 72 bytes: hash, verify, breach screening of the text bcrypt keys on, and an AST walk of every bcrypt import and call in backend code, its gaps named in its header; other libraries' limits are review-checked)
- arch-payments-need-allocation-evidence.md — Measure canonical allocations with explicit attribution, coverage and deletion limits
- arch-per-process-state-on-cloud-run.md — In-memory state is per-process — count every Cloud Run instance and job before trusting it
- arch-plan-caps-hold-where-the-effect-fires.md — Apply a plan cap where its effect fires, not only where the setting is written; a downgrade rewrites no settings (partly gated by `backend/tests/unit/test_earnings_alerts.py` for the earnings-day alert send; the next capped setting is review-checked)
- arch-qualified-income-deltas-need-source-ownership.md — Withhold qualified income arithmetic when attribution and entity ownership are unsupported
- arch-reconciliation-follows-values-and-growth.md — Carry reconciliation quality through values, growth, citations and exports
- arch-redis-off-in-prod.md — Production runs with Redis OFF — the two-tier cache is L1-only in prod
- arch-sitemap-page-eligibility.md — Match sitemap eligibility to the existing page predicates
- arch-source-supplements-preserve-existing-context.md — Retain complete bounded omitted source without displacing existing context
- arch-sqlalchemy-json-none-is-json-null.md — A JSON column's None is a JSON null, not SQL NULL: read "no value yet" off a scalar column (partly gated by `backend/tests/unit/test_wording_summaries_access_allowlist.py` for `diff_summary`; other JSON columns are review-checked)
- arch-stop-tuning-prose-know-the-floor.md — Stop tuning prompt prose when judge flags are heterogeneous or prompt-compliant
- arch-structural-gates-over-prose-rules.md — Encode every "never do X again" rule as a machine-checked gate, not prose
- arch-validate-inline-source-identities.md — Validate namespace bindings and qualified tags before selecting inline source facts

## SEC / EDGAR data

- sec-cap-6-ks-apart-from-reports.md — Cap a mixed-form filings list per form group, 6-Ks apart, so a daily 6-K filer never hides its 20-F/40-F (partly gated by `backend/tests/unit/test_filings_endpoint_db_first.py` for the company filings list; a new mixed-form list is review-checked)
- sec-edgar-resilience-layer.md — Preserve SEC pacing and distinguish selected breaker coverage from limiter-only paths
- sec-enforce-gates-server-side.md — Enforce every access gate server-side at the mutation endpoint
- sec-filing-date-is-a-calendar-date.md — `Filing.filing_date` is a calendar date stored as UTC midnight, never an instant: open a window at the start of a UTC day, let a watermark copied from a filing date admit its own date while it is recent, and leave exactness to per-filing dedupe (partly gated by `backend/tests/unit/test_filing_alert_calendar_dates.py` for the alert engine; other comparisons are review-checked)
- sec-listing-fetch-recent-window-and-cheap-fields.md — List filings in ONE recent-window fetch and read cheap metadata fields — never edgartools properties that hit the network
- sec-run-our-entry-point-before-ruling-an-upstream-fix-out.md — Run our entry point against the failure before ruling that an upstream fix does not reach us (a grep of `app/` misses calls the library makes for us), never let a `getattr` default or bare `except` hide a failing read, and treat a path the change revives as a model-input change, gated on its effect (partly gated: `test_edgartools_compat.py`, the X0.2 cases in `test_xbrl_service_anchors.py`, `test_summary_sections_parity.py`)
- sec-runtime-facts-carry-no-duration.md — Runtime per-filing facts carry no duration: abstain, never substitute an annual-looking label
- sec-xbrl-period-selection.md — XBRL facts: select for the filing's OWN reporting period — fy/fp label the filing, not the fact

## Testing & verification

- test-absence-claims-come-from-git-grep.md — Make an absence claim only from `git grep` over every tracked file (and never from a suffix allow-list in a test)
- test-adversarial-lens-verification.md — Verify large mechanical changes with independent adversarial lenses, not one review pass
- test-allowlist-caps-are-equalities.md — An allowlist cap is an equality, never a ceiling: the shrinking PR lowers the cap in the same commit (gate: allowlistCapsAreEqualities.spec.ts)
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
- test-gates-must-be-as-wide-as-their-rule.md — A gate narrower than its rule is worse than no gate; evaluate the source, don't text-match it, and score it on planted forms of the rule before a record says what it holds, kept as its fixture when the gate reads code; when a review finds one form of a claim it misses, probe the claim's whole family, taken from the language's and the framework's binding forms rather than the forms reviews have named, and give a gate's checks one walk
- test-isolate-process-wide-contextvars.md — Isolate process-wide ContextVars per test; CI's file order can hide a leak
- test-judge-context-parity.md — Give an LLM judge the same (or a superset of the) grounding the generator used
- test-layout-numbers-are-one-environments-run.md — Accept a layout measurement on its invariants, never on equal pixels; one pinned browser still measures differently on another machine
- test-leave-the-tree-alone-during-a-background-suite.md — Leave the working tree untouched while a background full-suite run reads it
- test-parser-callback-positions.md — Match whole-input callbacks to exact raw-source positions before accepting event capacity
- test-persistent-sqlite-db-goes-stale.md — The dev SQLite DB (backend/earningsnerd.db) is persistent — rm it after a schema change; the test suite never uses it
- test-pin-a-row-lock-with-a-statement-spy.md — Pin a row lock with a statement spy; a race test under SQLite cannot see FOR UPDATE
- test-probes-assert-what-only-success-renders.md — A probe asserts what only a successful render shows, counted from its input; a heading that also frames the error state proves nothing
- test-proofs-run-on-committed-state.md — Mechanical proofs must run against committed state — a proof that cannot fail proves nothing
- test-pure-move-ast-proof.md — Verify "pure move" refactors with an AST-normalized per-symbol diff, not by eyeballing the diff
- test-smoke-model-runs-before-sweeps.md — Smoke one or two items and inspect raw output before any long or expensive model run
- test-smoke-targets-feature-semantics.md — Distinguish the actual smoke target from similarly named calls to action
- test-sqlite-savepoint-release-hides-a-dropped-commit.md — Pin a commit that follows a SAVEPOINT with a commit spy; under SQLite the RELEASE already committed the row
- test-tracked-file-gates-run-after-staging.md — Run a `git ls-files` gate after staging its own module, and select targets by name pattern
- test-verbatim-fixtures-keep-the-source-bytes.md — Copy verbatim fixtures from the source payload and assert them on textContent
- test-verify-orphaned-tests-before-adopting.md — Verify orphaned or uncollected tests before adopting them
- test-vitest-for-copy-changes.md — Run vitest before pushing any change to rendered text, numbers, or copy
- test-vitest4-mock-error-tracking.md — Plain-function error mocks avoid handled-error failures; reproduced on Vitest 4 and rechecked on Vitest 5
- test-wire-format-coverage.md — Pin serialized wire formats with tests — suites that only check values let format drift through

## Frontend & design system

- brand-a-colour-rule-recolours-a-value-and-never-deletes-it.md — When a colour, type or device rule forbids a value's styling, restyle and keep the value: a control that carries a count rests in the secondary ink as one text run and turns sage only under the pointer, composing `countControlClass` when it does (the count control, frontend/DESIGN_SYSTEM.md); remove a value only as a named copy decision, never to turn a gate green (partly gated: frontend/tests/unit/filingFeedOverflowCount.spec.tsx and narrative-pane.spec.tsx keep the two counts the founder sent back, brandCopyRules.spec.ts rule 2 keeps a count out of sage, out of a span of its own ink inside a sage control and out of a copy of the recipe written in its file; the general rule is review-checked)
- brand-a-promise-names-what-the-code-enforces.md — Before a public sentence promises a behaviour, trace each surface it covers to the code that enforces it, flag defaults included, and scope the sentence to those; an "only" or "never" claim in a comment or record is traced the same way, and a remedy names the reader's next action (partly gated by `frontend/tests/unit/brandCopyRules.spec.ts`, rules 1, 1b and 1c, and `authPagesCopy.spec.tsx` for the verification and account-conflict lines; a new kind of promise is review-checked)
- brand-the-mark-is-protected.md — Never change the EN monogram or the wordmark; brand work composes around them (arrangements, clear space and minimum sizes only) (partly gated by `frontend/tests/unit/markSingleSource.spec.ts`, which holds the outlines and their placement, and `wordmarkSingleSource.spec.ts`; the colours, the wordmark's composition and the small-size rule are review-checked)
- frontend-a-notice-title-is-one-phrase.md — Give a Notice or GuidanceCard title one phrase; the second clause goes in the description (partly gated by `frontend/tests/unit/noticeTitlesAreOnePhrase.spec.ts`; a title passed in as a variable is review-checked)
- frontend-a-return-notice-claims-only-what-the-return-shows.md — After a redirect back from checkout, say only what the return URL and the page's own reads show, never a charge outcome (partly gated by `frontend/tests/unit/PricingPage.spec.tsx` and `dashboardCheckoutReturn.spec.tsx` for the two return notices; a new one is review-checked)
- frontend-check-brand-layouts-at-200-percent-text.md — Check a brand layout at 390px under a 200% root font: a figure pair wraps on its own content width, and a positioned twin centres on its anchor's measured midpoint
- frontend-auth-optional-reads-wait-for-the-session-read.md — A per-viewer read served by an auth-optional endpoint waits for the session read, keys by the reader, reconciles a Pro teaser once and has one owner (partly gated by `frontend/tests/unit/whatChangedReadOwner.spec.ts`; the next such endpoint is review-checked)
- frontend-busy-controls-stay-focusable.md — A control busy with its own request stays focusable: aria-disabled plus an early return, never native disabled (partly gated by `frontend/tests/unit/busyControlsStayFocusable.spec.ts` (AST scan of every .tsx); the keyboard and focus hand-off rules are not)
- frontend-check-luminance-vs-background.md — Verify surface luminance against the actual background, not token validity
- frontend-citation-offset-boundaries.md — Resolve citation starts to the first matched character's text node and pin the actual flash target
- frontend-client-exports-need-next-build.md — Never call a 'use client' module's export from server code; the gate checks what next build may not render
- frontend-count-a-completion-on-the-transition-the-server-names.md — Count a completion event on the transition the server names (`completed_now`), never on the client's optimistic count; `scope` serializes requests, not optimistic writes
- frontend-design-docs-need-agent-entrypoints.md — Connect new design references to agent entrypoints, authority and maintenance
- frontend-dialog-opener-outlives-the-dialog.md — Keep a dialog's opener mounted while the dialog is open, so focus has somewhere to return
- frontend-dialog-openers-stay-focusable.md — Keep a dialog's opener focusable through its pending and cooldown states — aria-disabled, not native disabled
- frontend-dialog-trap-arms-once-per-open.md — Arm a dialog's focus trap once per open; never key its effect on a callback prop's identity
- frontend-focus-opened-popovers-survive-the-focusing-scroll.md — A popover that opens on focus re-anchors on the scroll that focusing caused; only a hover popover closes on scroll
- frontend-guard-a-loader-two-effects-can-start-in-one-commit.md — Guard a loader with a synchronous in-flight ref when two effects can start it in one commit
- frontend-guard-submit-on-loading-buttons.md — Guard submit handlers with an early return when the button uses loading, not disabled
- frontend-hidden-name-tails-bring-their-own-space.md — A visually hidden tail on a control's name brings its own space and starts with a word or bracket
- frontend-jsdom-sdk-browser-entry.md — Resolve browser SDK imports as browser code in jsdom tests while preserving real capture behavior
- frontend-locked-page-dialog-scrolls-itself.md — A dialog that locks the page must bound itself to the viewport and scroll inside
- frontend-native-modal-dialog-makes-body-portals-inert.md — Under a native showModal() dialog, portal into the dialog and preventDefault the keys you own (partly gated by `frontend/tests/unit/dialogAllowlist.spec.ts`; the keyboard and focus hand-off rules are not)
- frontend-no-surface-fighting-global-colors.md — Never set a global element-level color that surfaces must opt out of
- frontend-overrides-rot-when-the-constrained-package-moves.md — An npm override's meaning is set by the package it constrains — re-check every override on a major bump
- frontend-preview-both-themes-before-done.md — Eyeball the deployed preview in both themes before declaring visual work done
- frontend-price-copy-derives-from-the-module.md — Compute every displayed Pro price and saving claim from PRO_PRICING; never type one (partly gated by `frontend/tests/unit/pricingFollowsModule.spec.tsx`, which covers the pricing page and homepage section; a new price surface joining it is review-checked)
- frontend-reserve-fixed-chrome-with-scroll-padding.md — A focus scroll stops at the viewport edge, not at a fixed overlay: reserve the overlay with scroll-padding
- frontend-route-redesign-needs-a-mount-gate.md — A self-omitting section needs a source-level mount gate — render tests cannot see it go missing
- frontend-sanitize-telemetry-before-transport.md — Sanitize every telemetry transport, persisted attribution and recording lifecycle before authentication data can leave
- frontend-site-overlays-outrank-in-page-sticky-chrome.md — A fixed site-level overlay ranks above in-page sticky chrome, and the ladder gate scans sticky sites too
- frontend-sitemap-cache-ownership.md — Cache the rendered sitemap hourly while bypassing Next's fetch Data Cache
- frontend-snapped-scrollers-reveal-the-focused-cell.md — A snap-scrolled table picks the snap stop that reveals a focused cell; the browser's focus scroll plus the mandatory snap can hide it
- frontend-spinner-gate-on-shared-errored-query.md — Gate a page's spinner on the retained failure when its children observe the same query
- frontend-sr-only-needs-a-positioned-clip.md — Give a clip that holds an sr-only box a position (`relative`); an unpositioned clip lets the absolutely positioned box out and the page scrolls sideways (partly gated: the page-width check of `frontend/tests/e2e/reflow-200.spec.ts` on the routes it visits, whose report names an escaped box, and #1344's admin spec once it lands; no static scan reads it, since the clip and the box can sit in different components)
- frontend-status-colors-for-status-only.md — Reserve loud status colors for genuine status messages
- frontend-sweep-replaces-need-per-site-asserts.md — Assert every targeted replace in a sweep script and grep all token variants first
- frontend-tailwind-classes-are-written-whole.md — Write every Tailwind class whole, variant prefix included; never assemble one from an interpolated prefix or suffix (gate: `frontend/tests/unit/tailwindClassesWrittenWhole.spec.ts`; the emitted CSS is proven in a browser or by the done gate)
- frontend-tailwind-content-scans-class-maps.md — Put every module that composes Tailwind classes under a content glob
- frontend-top-dialog-owns-the-keyboard.md — The top dialog owns the keyboard: listen in window capture and stop the keys it handles
- frontend-trial-labels-use-entitlements.md — Derive current-trial presentation from the resolved entitlement
- frontend-validate-design-sidecars-in-their-consumer.md — Validate design-sidecar specimens in their consumer, and check what its engine reads
- frontend-variable-text-must-not-size-a-wrapping-row.md — Every responsive grid sets its base track (gated: ESLint `earningsnerd/responsive-grid-base-track`); variable-length text must not size a wrapping row (`[contain:inline-size]`, `min-w-0`, `truncate`; review-checked)
- frontend-verify-chart-annotations-on-dense-data.md — Acceptance-test chart annotations on a dense real-world series, never only fixtures
- frontend-xbrl-amounts-carry-their-own-currency.md — Label an XBRL amount with the filer's reporting currency, never with a default dollar sign

## Enforced by a machine gate — not session reading

The rule is checked by the named gate; open the lesson only when that gate fails or you change it.

- arch-sweep-dead-integration-consumers.md — When an integration is declared dead, sweep every consumer in the same pass — gate: `backend/tests/unit/test_dead_integrations_allowlist.py`
- ops-a-review-you-triggered-is-a-review-you-wait-for.md — A review you triggered is a review you wait for; merging inside it discards what you asked for — gate: `.github/workflows/review-gate.yml` (required status check `review-gate`)
- ops-deploy-detector-mirrors-the-image-context.md — Make the deploy change detector exclude exactly what `.dockerignore` excludes, and gate it with a test — gate: `backend/tests/unit/test_backend_deploy_scope.py`
- ops-migrations-need-lock-timeout.md — Give every migration session a lock_timeout and every deploy job a timeout — idempotent is not lock-free — gate: `backend/tests/unit/test_migration_lock_safety.py`; CLAUDE.md rule 3
- ops-pin-ci-toolchain.md — Pin the lint/security toolchain and select lint rules explicitly — CI must not drift with the tool — gate: `backend/tests/unit/test_migration_lock_safety.py` (unpinned `pip install` check)
- ops-prove-the-permission-route-before-a-gated-session.md — Prove the permission route with a `--help` no-op in the exact allow-rule form before any gated step; a denial there is a stop, not a failed restore; name the mode (Accept edits, not Plan) — gate: `backend/tests/unit/test_e8_launch_kit_matches_allow_rules.py`
- sec-filing-url-format.md — SEC archive URLs: strip CIK leading zeros, strip accession dashes — and sec_url is NOT NULL — gate: `backend/tests/unit/test_filing_url_listeners.py`, `test_sec_gov_importers_allowlist.py`; CLAUDE.md rule 10
- sec-parse-app-fetched-html-not-edgartools-filing-objects.md — Section text: fetch the primary document through the app transport and parse it locally with edgartools' HTMLParser; the Filing/CompanyReport `obj()` accessors re-fetch through edgartools' own client, outside the app's limiter and breaker, and fail where the homepage does not resolve — gate: `backend/tests/unit/test_edgartools_obj_allowlist.py`
- test-one-test-home.md — Tests live in exactly one home per stack — a test outside it does not run in CI — gate: `frontend/tests/unit/testHomesAllowlist.spec.ts`

## Archived (`lessons/archive/`) — superseded by a rule or a gate

- archive/frontend-query-keys-registry.md — React Query keys come from lib/queryKeys.ts — inline key literals are a stale-cache bug class — superseded by the `no-restricted-syntax` queryKey selector in `frontend/eslint.config.mjs`
- archive/frontend-theme-migration-app-wide.md — Treat a design-token/theme migration as app-wide by default — superseded by `frontend/tests/unit/designSystemDoneGate.spec.ts` and CLAUDE.md rule 11
- archive/ops-lint-before-every-push.md — Run ruff (and bandit) before every push, not just pytest — superseded by the CI `backend-tests` job (ruff + bandit) and the FULL gate line in CLAUDE.md
- archive/ops-run-full-backend-gate-before-push.md — Run the full local gate (ruff + bandit + pytest) before any backend push — superseded by the CI `backend-tests` job (ruff + bandit + pytest) and the FULL gate line in CLAUDE.md
