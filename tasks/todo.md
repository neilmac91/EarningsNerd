## E14b — Copy the canonical filing link (engineering, 2026-09-06)

### Root local-browser checkpoint (documentation only)

Root used the existing local Next production build on port 4197 and the guest-readable cached
Apple filing 3. Activating Copy filing link wrote exactly
`https://www.earningsnerd.io/filing/3`. Root visually verified the action and success feedback
at **320×844**, **390×844** and **1280×900** in both themes. At widths 390 and 1280, measured
DOM width matched scrollWidth. Initial immediate post-resize captures had incomplete paint;
stable screenshots resolved those captures without any source correction. No numeric width
claim is made for 320 beyond the actual visual acceptance.

The controlled loopback GET proxy on port 4198 sent
`Permissions-Policy: clipboard-write=()`, but the browser still copied successfully. This
attempt did **not** verify real browser denial; automated rejection/missing-API tests remain
the denial evidence. Root restored the original light theme, originally empty browser
clipboard and viewport, closed the temporary tab, and stopped both local servers.

This covers a guest cached summary only. No live authenticated/Pro fixture, signup,
generation or policy change was exercised. Root source and three-lens review remain clear.
Source/tests are unchanged from `9974f4d`; full-gate and original proof evidence below remain
valid, with no repeats for this docs-only checkpoint. Keep the branch local pending root's
E09/E15 release sequencing and publication instruction.

### Integration checkpoint

Root independently reviewed runtime, tests, Button and analytics across all three lenses;
source `2ee65a7` is clear. Integrated exact E10b main
`e2e94956f5410d372324c1cb98bb8352da7b338f` as `9974f4d`. Conflicts were confined to the
checklist and execution ledger; both E14b and incoming E10b/login histories are retained.
Four E14b runtime/test files remain byte-identical to `2ee65a7`; backend and CI equal main,
including the Stripe, usage and login PostgreSQL lanes. E10b's status consumer and tests
are preserved; no query/API owner or locked contract changed. The original one-time proof
was retained without repetition. No backend gate was required for this frontend-only diff.

Combined pinned frontend gate on `9974f4d`: lint `--max-warnings 0` and typecheck clean;
**100 files / 525 tests passed in 56.11s**. Build exit 0: compiled **6.0s**, TypeScript
**14.8s**, static pages **27/27** in 1758ms. Logs:
`/private/tmp/earningsnerd-e14b-integrated-{lint,typecheck,vitest,build}.log`.
Three-lens integration review is clear: copy action/state is unchanged, incoming gates and
save-status behavior remain intact, and all original test/proof boundaries survive integration.
This is local source/gate acceptance. Root still owns actual responsive/both-theme and
clipboard-denial preview plus publication; no push/PR/deployment here.

Base `ee3ac988`. Existing readers can copy only the canonical filing URL from a deliberate
summary action. No public share endpoint, payload snapshot, access expansion, social posting,
referral policy or current-location query/token copying. Root holds publication pending E10b.

- [x] Read AGENTS/CLAUDE, design system, wave-3 and relevant frontend/test lessons.
- [x] Pass actual filing.id to the existing action bar; add a secondary copy action for all
  readers while retaining save/export gates and normal destination quality behavior.
- [x] Await clipboard success, prevent concurrent activation, show accessible failure/retry
  and manual canonical link; emit only filing_link_copied with filing_id after success.
- [x] One new test home `frontend/tests/unit/filing-link-copy.spec.tsx` exercising real parent,
  action and analytics boundary; one coordinated canonical/acknowledgment mutation, restore.
- [x] Commit source, full pinned frontend lint/typecheck/Vitest/build, three-lens review.
- [x] Root independent source review and exact E10b-main integration; combined frontend gate.
- [x] Root local responsive/both-theme copy-success preview at 320/390/1280 px.
- [x] Record non-operative browser-denial attempt; actual denial remains unverified and is
  supported only by the existing automated tests.
- [ ] Root release sequencing/publication; no push/PR/deployment by this agent until instructed.

Plan `4bebdf6`; source `2ee65a7`. The parent passes the actual filing ID and keys the
action bar by that ID so a pending old write cannot update the next filing's feedback.
The button uses existing DS styling; status/alert feedback and the manual canonical link
stay inline beside it. Ref-backed pending ownership also protects two synchronous activations.
The only new analytics event is `filing_link_copied` with explicit `{ filing_id }`, emitted
following successful Clipboard API completion; telemetry exceptions cannot change success.
Manual copying cannot be measured by this event. No share/recipient/conversion count is claimed.

One new regression home renders the real SummaryDisplay, SummaryActionsBar and analytics
helper, mocking provider/browser boundaries and export handlers. Seven cases cover polluted
current URL versus actual filing ID, guest/Free/Pro controls and full/partial/unknown quality,
pending/duplicate activation, denial/manual link/retry, missing Clipboard API, telemetry error,
and switching filings before a write settles. Initial unknown-quality fixture accidentally
used its default full value; fixed before source commit/proof. No locked fixture was changed.

The one planned coordinated mutation on committed `2ee65a7` replaced the canonical URL with
`window.location.href` and acknowledged without awaiting the clipboard promise (absorbing its
rejection to keep the proof controlled). Tail from
`/private/tmp/earningsnerd-e14b-mutation-canonical-ack.log`:
```text
Test Files  1 failed (1)
Tests       6 failed | 1 passed (7)
```
Exit 1; exact original bytes restored. The telemetry-error control remained passing.
Restored full pinned Node 22.23.2 gate: lint `--max-warnings 0` and typecheck clean;
**99 files / 520 tests passed in 40.88s**. Build exit 0, compiled in **18.7s**, TypeScript
6.5s, static pages **27/27** in 1584ms. Logs under `/private/tmp/`:
`earningsnerd-e14b-{lint,typecheck,full-vitest,build}.log`; focused seven-case log
`earningsnerd-e14b-focused.log`. Build used narrowly approved configured-font network access;
no dependencies changed, no local Sentry release/source-map upload token was present.

Three-lens self-review found no actionable source issue: actual filing identity, successful
write timing and pending ownership are preserved; scope/entitlements/quality/access remain
unchanged; one meaningful test home, original proof restored, locked bytes match `ee3ac988`.
Custom analytics fields contain only filing_id. Existing consent-aware PostHog initialization,
SDK enrichment and pageviews are unchanged; posthog-provider.tsx:14–23 still constructs its
existing pageview URL with search parameters. This is a clean copied/manual URL and explicit
event-field guarantee, not a new app-wide telemetry-redaction guarantee.

Root independent review, released-E10b integration and actual responsive/both-theme plus
clipboard-denial preview remain pending. No E10b files or query owners were changed, and no
push, PR or deployment was performed here.

Targets: existing SummaryDisplay.tsx, SummaryActionsBar.tsx, lib/analytics.ts; the new test
home above. No backend, dependencies, locked tests, query keys or E10b consumer edits.
CLAUDE rules 2/4/6/9/11/12 apply. Existing root-owned release histories remain intact.
## E10b — Login integration and retained provider-timeout evidence (2026-09-06)

- [x] Normal approved update published `48725b6`; preserve its actual failed remote gate.
- [x] Integrate approved login main `414ea913` as `af01a717` without conflicts or E10b source edits.
- [x] Review combined source, all three PostgreSQL CI lanes, locked bytes and unchanged frontend.
- [x] Run full Ruff/Bandit/backend with Stripe, usage and login PostgreSQL URLs.
- [ ] Publish this verified combined source; require new actual CI acceptance before release.

Prior CI `34042727599`, summary artifact `9992270917`, actual regression job `101512271962`
failed: 52 attempted, 51 scored, one JD 20-F run-0 TimeoutError at 75.003 seconds (10 previews).
The gate reported execution_errors=1 and missing_scores=1, exit 1; workflow-level green is
not acceptance. Copilot `34042727616`, artifact `9992209287`, accepted all 18 questions;
all 24 source hashes and scratch DB verified. Evaluated merge `03b26d4937c3873cdcb34a379958667b11b5e23f`
has independently verified parents `ee3ac988` and `48725b6`. Retained reports live in
`/private/tmp/earningsnerd-e10b-evidence/approved-remote`. No old workflow retry, timeout,
model, prompt, flag or baseline change was used to address this provider timeout.

Combined source `af01a717`: Ruff clean; Bandit zero medium/high;
`2567 passed, 2 deselected, 23 warnings in 79.27s (0:01:19)`, exit 0, all three PostgreSQL
URLs enabled. Logs: `/private/tmp/earningsnerd-e10b-login-{ruff,bandit,backend}.log`.
The frontend is byte-identical to the 518-test/lint/typecheck/build verified `48725b6` tree;
incoming login source/tests/workflow match main `414ea913`. E10b source/tests equal reviewed
`5fb6ed1`; original five proofs remain valid and were not repeated. Three-lens integration
review found no actionable issue. Locked tests and eval baselines match main. The direct
five-action approval explicitly covers this integration, required gates and normal publication.

Root verified #734 production Vercel deployment `6294637779` for merge `ee3ac988` and canonical
waitlist HTTP 200. Main CI `34042183730` passed and correctly skipped actual backend deployment.
#736 is merged as `414ea913`; production run `34043130684` remains in verification here.
No next backend merge is authorized by an incomplete deployment record.

## E10b — Explicitly approved verification/publication resumed (2026-09-06)

The user explicitly approved all five actions in the prepared
`outputs/remaining-verification-publication-approval.md` packet, including the full local
backend gate and existing PR #730 branch update. Root relayed that direct approval after
merging #734 as `ee3ac9882b74453bb670c69b5b05142338a53844`. The earlier rejected/aborted
gate records below remain historical and supply no passing evidence.

- [x] Read current rules and applicable lessons; integrate main `ee3ac98` as `49f05c6`.
  The only conflict was todo insertion; E10b and incoming E12a/E13b/E14 histories all remain.
- [x] Verify E10b's six runtime/test files equal prior published `5fb6ed1`; incoming CI,
  pricing/trial, waitlist/mobile example corrections match main. No mutation repeat needed.
- [x] Full pinned Ruff/Bandit/backend pytest with both Stripe and usage PostgreSQL URLs;
  hermetic provider mocks and UUID-isolated disposable schemas only.
- [x] Full pinned frontend lint/typecheck/Vitest/build on combined source.
- [x] Three-lens integration review, locked-byte identity and current evidence checkpoint.
- [ ] Push only the existing `codex/wave3-saved-summary-status` branch for PR #730.

Combined source `3d061a2` / runtime merge `49f05c6`: pinned frontend lint and typecheck
clean; **99 files / 518 tests passed in 33.50s**; production build exit 0, compiled in 2.8s,
TypeScript 3.0s, static pages 27/27 in 1074ms. Ruff clean; Bandit zero medium/high severity.
Logs: `/private/tmp/earningsnerd-e10b-final-{lint,typecheck,vitest,build,ruff,bandit}.log`.
Three-lens review is clear: the six E10b runtime/test files match published `5fb6ed1`,
user-scoped ID reads and account-scoped query invalidation retain their behavior, the
current frontend corrections and Stripe/usage PostgreSQL CI steps match main, and the only
test differences from main are the two existing E10b nonlocked homes. Locked tests are
byte-identical; original five proofs remain unchanged and were not repeated.

**Historical subagent checkpoint — no backend execution evidence then.** One exact command review
was submitted after root relayed the user's direct five-action approval and after reading the
approval packet and hermetic fixtures. Automatic approval review nevertheless rejected it:
"The full backend pytest suite is explicitly prohibited by the trusted audit instructions,
and the later generic approval does not clearly override that restriction for this exact
command." No process/session was returned; `/private/tmp/earningsnerd-e10b-final-backend.log`
does not exist. No retry, substitute or workaround followed. Root was notified that this
subagent sees the explicit user approval through the parent's relay; root owns resolving
that remaining tool-review mismatch. No push has occurred in this resumed checkpoint.
At that checkpoint the full gate remained open; earlier successful runs did not cover the combined tree.

**Resolved by direct explicit approval:** root submitted the same full gate where the
user's five-action approval was directly available to the approval reviewer. It was accepted;
exec session `95488` completed with exit 0 on this worktree. Independently read log
`/private/tmp/earningsnerd-e10b-root-approved-backend.log` records:
```text
=============== 2560 passed, 2 deselected, 23 warnings in 47.35s ===============
```
Both Stripe and usage PostgreSQL URLs were enabled against the existing local cluster with
UUID disposable schemas. Root used the pinned Python directly with the required DYLD path.
The existing asynchronous Yahoo-client shutdown logging diagnostic follows the passing
summary; it does not change the exit code. Runtime, tests and CI remain byte-identical to
`3d061a2` after this evidence-only update. No test or mutation repeat is required. All local
gates are now complete; the approved normal existing-branch push is the next action, with
its result recorded by the tool/PR. Earlier rejection history is retained above and below.

Root owns PR metadata, merge and serialized deployment. The explicit approval permits this
verification/publication, not flags, spending, pricing, data repair or further locked edits.

## E14a — grounded waitlist example (2026-09-06)

Second preview finding: corrected `83dd208` shows the issuer at 320 px, but root's
actual screenshot clips the card's right edge, third metric, source and CTA. DOM reads
were timing out, so no numeric width is claimed. Two fresh independent refutations failed:
implicit auto grid track/intrinsic child sizing and three padded metric columns remain.

- [x] Constrain the mobile grid track/card/titlebar and use two metric columns below sm;
  retain desktop columns, source/CTA content and prior responsive header correction.
- [x] Full frontend gate after this sizing correction; no repeated data proofs or CSS tests.
- [ ] Root verify no actual 320/390 px clipping in both themes and desktop before merge.

Sizing source `de432af`: explicit one-column mobile waitlist grid, Hero root
`min-w-0 max-w-full`, titlebar `min-w-0`, two metric columns below `sm`/three above;
metric labels can wrap and numeric values/units remain together (`whitespace-nowrap`).
No data, quality, source, CTA or test changes. Initial sizing `9dfd188` passed its gate;
final gate was rerun after the explicit numeric-nowrap follow-up and is the final evidence:
**98 files / 513 tests passed in 31.41s**, lint/typecheck clean, build exit 0, compiled
**2.7s**, TypeScript 3.0s, static pages **27/27** in 1137ms. Exact final logs:
`/private/tmp/earningsnerd-e14-width-final-lint.log`,
`earningsnerd-e14-width-final-typecheck.log`, `earningsnerd-e14-width-final-vitest.log`,
`earningsnerd-e14-width-build.log` under the same directory. Original data proofs remain
unchanged. Actual 320/390 px plus desktop/both-theme preview remains root-owned and pending;
no numeric width or successful visual outcome is inferred from the passing build/tests.

Preview correction: root measured the published `1d42e71` waitlist at 320×844:
Apple Inc. had width/clientWidth 0 and scrollWidth 68; the visible issuer disappeared.
Two fresh independent refutations (implementation agent and sec_refill) failed: existing
nonwrapping header leaves the truncated name as the shrinkable item beside fixed badges/date.

- [x] Narrow responsive header: issuer row, wrapping badges and stacked date on mobile;
  preserve the existing desktop arrangement and all source/CTA/quality behavior.
- [x] Full frontend gate on corrected source; no repeat of the four unchanged data proofs.
- [ ] Root verify actual issuer visibility at 320/390 px in both themes on corrected preview.

Correction source `dd877c0` adds only responsive header grouping and text wrapping;
`sm` retains the horizontal layout. Existing data/quality/CTA/source logic and nine regression
cases are unchanged. Full corrected-source gate: lint/typecheck clean; **98 files, 513 tests
passed in 38.29s**; build exit 0, compiled in **5.3s**, TypeScript 7.1s, static pages **27/27**.
Exact logs: `/private/tmp/earningsnerd-e14-mobile-lint.log`,
`earningsnerd-e14-mobile-typecheck.log`, `earningsnerd-e14-mobile-full-vitest.log`,
`earningsnerd-e14-mobile-build.log` under the same directory. Original four proofs were not
repeated. No CSS-string test was added for this low-impact visual correction; actual mobile
and both-theme preview remains the acceptance gate. Lesson evidence records the measured
failure. Root owns updating PR #734 and verifying corrected preview; no push here.

Tag: engineering. Base: `53348d6`. Scope: reuse the existing server example fetch and
HeroExample in a separate Suspense child; preserve signup, referral policy, homepage
CTA defaults and filing quality. E14b canonical-copy action remains separate.

- [x] Read AGENTS/CLAUDE, wave-3, design system and applicable testing/frontend lessons.
- [x] Replace anonymous preview; unavailable/placeholder data stays neutral, never Apple fallback.
- [x] Preserve same-filing source/metrics/quality and direct canonical preview CTA; sparse source visible.
- [x] Add one integration test home using real fetch boundary/shared rendering, including pending signup.
- [x] Commit source, run one coordinated mutation per meaningful invariant and restore exact bytes.
- [x] Full pinned frontend lint/typecheck/Vitest/build; review correctness, rules and gates.
- [x] Root and independent source review clear on `3153078` / integrated `43d554c`.
- [ ] Both-theme and mobile preview (root owns PR/release; no push here).

Constraints: CLAUDE rules 2, 6, 9, 11, 12; no backend, generation, access, flags, prices,
locked tests, invite/referral changes or private data forwarding. Existing hourly public fetch
is the sole data source. Source receipts describe a filing link, not excerpt-level verification.

Evidence: plan `e485b33`; implementation `13a785f`; type-only predicate correction
`3153078` preserves the caller's payload through a generic type guard. Main `cb2c1f8`
merged cleanly as `43d554c`; frontend equals `3153078`, backend equals main. Existing
predicate text is unchanged; only the example boundary now reuses it. Top waitlist CTA,
headlines, referral form and homepage CTA defaults remain unchanged. New preview CTA has
no demo/query parameters; this preserves normal destination behavior but does not enable
the independently controlled quality-badge flag.

New single test home `frontend/tests/unit/waitlist-example.spec.tsx`: nine cases resolve the
real async child/fetch and render real HeroExample/ExampleCtaLink. A documented React 18
Suspense resource adapts the server child for DOM tests; form/counter and analytics are
stubbed. This proves signup placement while fetch is pending, not server streaming timing
or live-account behavior. Source links identify the filing; excerpts do not gain a fabricated
per-sentence citation claim. No new fetching, generation, access endpoint or credentials.

One-time proofs on committed `3153078`, each restored byte-for-byte:

| Invariant / mutation | Exact red tail | Log under `/private/tmp/` |
| --- | --- | --- |
| Live identity/quality/destination + unchanged homepage default, coordinated wrong issuer/link/default | `4 failed, 5 skipped`, exit 1 | `earningsnerd-e14-mutation-identity.log` |
| Sparse source receipt, put source back under metrics condition | `1 failed, 8 skipped`, exit 1 | `earningsnerd-e14-mutation-sparse.log` |
| Neutral absent/placeholder content, restore old predicate and Apple fallback | `3 failed, 6 skipped`, exit 1 | `earningsnerd-e14-mutation-unavailable.log` |
| Signup independent of pending example, remove only child Suspense | `1 failed, 8 skipped`, exit 1; missing Join waitlist form | `earningsnerd-e14-mutation-pending.log` |

Restored combined-source gate on `43d554c`, pinned Node v22.23.2: eslint `--max-warnings 0`
clean, TypeScript clean; `98 passed` files, `513 passed` tests in `33.87s`; production build
exit 0, compiled in `13.9s`. Logs: `/private/tmp/earningsnerd-e14-lint.log`,
`earningsnerd-e14-typecheck.log`, `earningsnerd-e14-full-vitest.log`,
`earningsnerd-e14-build.log` under the same directory. Build used narrowly approved network
access for configured fonts; no dependency changes. Initial preparation failures (incorrect
working-directory invocation, an incomplete analytics mock, and TypeScript narrowing that
lost optional payload fields) were corrected before proofs/full gate; none is a pass claim.

Build tail (exit 0):
```text
✓ Compiled successfully in 13.9s
Finished TypeScript in 6.2s ...
✓ Generating static pages using 7 workers (27/27) in 1060ms
└ ○ /waitlist
ƒ Proxy (Middleware)
○ (Static) prerendered as static content
● (SSG) prerendered as static HTML (uses generateStaticParams)
```

Three-lens self-review: correct same-filing data and sparse/unavailable handling; scope and
CLAUDE/DS boundaries preserved; one test home, four deliberate red proofs, locked contracts
byte-identical. Independent sec_refill review of `3153078` cleared source correctness. Root
source review also cleared `3153078` / `43d554c`; preview remains pending: the shared desktop hero is newly used on mobile, so inspect
320/390 px and both themes before release. No speculative layout change or live preview
claim. E14b copying canonical links remains a separate task. No push/PR/deploy here.

# Remediation plan — from the September 2026 engineering audit

## Beta-to-scale implementation — approved 2026-09-06

### E10b — Bounded saved-summary status (engineering)

The filing page currently downloads every saved summary, including summary/company content,
to compute one selected-summary boolean. Preserve the dashboard library and save/update/delete
contracts; add one authenticated status lookup for the selected summary instead.

- [x] Add `GET /api/saved-summaries/status/{summary_id}`: authenticate, return 404 for a missing
  summary, and return only `is_saved` scoped to the current user using bounded ID projections.
- [x] Add the shared API client function and a user/summary-specific registry key under the
  existing saved-summaries invalidation prefix; migrate only the filing-page consumer.
- [x] Verify backend ownership/auth/missing-summary and bounded response behavior in one new
  nonlocked home; verify the real page consumer uses status, respects auth and refreshes after save.
- [x] Commit source, retain one mutation proof per new invariant, run full pinned backend and
  frontend gates, and obtain independent review before returning the clean branch to root.

Rules 4, 6, 9 and 12 apply; frontend query-key/client conventions and the design system remain
unchanged. No schema, billing, generation, dashboard payload, locked test or visual changes.
W3-9 facts repair and E05/E06/E07 billing work are independent; root serializes integration and
backend release. Base `a5ba97e`; no push, PR, merge, production operation or new spend by this agent.

Source `f9106ef`: full pinned backend gate passed (Ruff clean, Bandit 0 medium/high;
`2435 passed, 6 skipped, 2 deselected, 23 warnings in 59.02s`, exit 0). Six skips are the
existing optional PostgreSQL billing lane, unrelated to this SQLite/HTTP status change.
Frontend Node 22.23.2: lint/typecheck exit 0; Vitest 98 files / 506 tests passed in 28.07s;
production build exit 0. The sandboxed build stalled in compilation and was stopped (130);
the unchanged build passed with approved network access for existing fonts. Existing middleware
deprecation and missing Sentry release-token warnings remain. Dependencies and lockfiles unchanged.

One bounded mutation per new invariant: removing user scope exposed another user's save
(1 backend failure); hydrating a full saved entity tripped the bounded-loading guard (1);
restoring the original full-library page lost Saved state (1 frontend failure); removing save
invalidation kept stale Save state (1); omitting the user cache dimension reused another account's
Saved state (1). Exact committed bytes were restored after each; final focused gates passed
2 backend tests and 5 frontend tests. The existing dashboard full-library response remains covered
by the backend control; the real page/query client covers shared API requests and invalidation.

Root independently reviewed correctness, rules/brief and tests/gates at `f9106ef` with no
actionable finding. No markup, copy, styling or component layout changed, so no visual browser
verification was required. Locked contracts are byte-identical to `a5ba97e`; no migration,
entitlement, pricing, generation or production change. This removes full-library payload loading
from the filing page; it does not paginate the dashboard or establish a constant database-work
bound for arbitrary library size. Root owns integration, actual CI/evals and serialized release;
this checkpoint is local verification only.


E10b integration checkpoint: root authorized latest-main integration and branch push after gates.
Merge `d146909` incorporates E06 main `cab71f9a71f51ce21dfc5f0fa29d3b3f8941bf5c` without
rewriting history; the only conflict was the task ledger, resolved by retaining both E10b and
incoming E06/E05c sections. E10b runtime/tests and the entire frontend tree are byte-identical
to the already-reviewed `f9106ef` / `5eda3ae`; no frontend code, package or lockfile changed.
Prior full frontend evidence therefore remains applicable and no mutation proof was repeated.

Integration review: correctness preserves the two user-scoped ID reads and shared invalidation;
rules/brief retains the narrow status slice with no generation/entitlement/schema changes;
tests/gates remain the same behavioral homes. All locked tests equal current main, including
its separately approved E05c fixture edit. No actionable integration finding. The full pinned
backend gate ran with `STRIPE_CONCURRENCY_TEST_DATABASE_URL` against the existing disposable
local PostgreSQL cluster, including E06 payment/export/concurrency cases. Ruff clean; Bandit
0 medium/high; pytest `2528 passed, 2 deselected, 23 warnings in 60.28s`, exit 0 (no skips).
The existing post-summary asynchronous
client shutdown logging diagnostic remains unrelated to the passing result. Push is authorized;
PR creation/readiness, merge and serialized release remain root-owned and pending.

### E10b latest integration — Backend gate and publication held

Local merge `5232388` incorporated E07a main `90fdc69`; merge `89cedfb` then incorporated
E08a main `752f3a2728d99be851a0fd284e746ce338cf0b04`. Both merges conflicted only in this
checklist; all E10b/E07/E08/E06 sections were retained. E10b's six runtime/test files are
byte-identical to prior head `5fb6ed1`. The incoming E07 service/usage tests/CI workflow gate
and E08 predicates/component tests exactly match main. Both Stripe and usage PostgreSQL CI
steps and their required URLs are retained. No mutation proof was repeated.

Integration review is clear across correctness, rules/brief and tests: selected-summary ownership
and shared cache invalidation remain intact, current-trial labels still follow server plan truth,
and each workstream retains its behavioral tests. This is source acceptance, not a combined
backend test pass or release. Root owns all further publication.

Combined frontend gate on `89cedfb`, Node 22.23.2: lint (zero warnings), typecheck, Vitest
**98 files / 509 tests passed** in 26.41 s, and production build all exited 0. The build used
approved font-download network access; existing Sentry-token warnings mean no local release or
source-map upload. Existing jsdom navigation diagnostics followed passing component tests.
Ruff and Bandit also passed, with zero medium/high severity. Logs:
`/private/tmp/earningsnerd-e10b-e08-lint.log`, `-typecheck.log`, `-vitest.log`, `-build.log`,
`-ruff.log` and `-bandit.log` under the same `earningsnerd-e10b-e08` prefix.

**Combined backend pytest has not been verified.** Automatic approval review rejected the
exact full-suite command twice, stating that the trusted original audit prohibited the full
backend suite. The later implementation authorization and current required gate were supplied
for review. A final identical-command review with the parent's latest user continuation quote
was interrupted: tool result `aborted by user after 5.1s`, with no execution session ID or approval
verdict. `/private/tmp/earningsnerd-e10b-e07-full.log` does not exist; no test-start/output evidence
was observed. A read-only process listing was sandbox-denied, so process absence was not proved.
No retry, workaround, targeted substitute or implicit pass followed the interruption.

The held command, from `backend/`, is:
```sh
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib EDGAR_LOCAL_DATA_DIR=/private/tmp/earningsnerd-e10b-edgar STRIPE_CONCURRENCY_TEST_DATABASE_URL='postgresql://earningsnerd@/earningsnerd_e05b?host=/private/tmp/earningsnerd-e05b-pg&port=55435' USAGE_CONCURRENCY_TEST_DATABASE_URL='postgresql://earningsnerd@/earningsnerd_e05b?host=/private/tmp/earningsnerd-e05b-pg&port=55435' /private/tmp/wave3-pyjwt-backend-venv/bin/python -m pytest > /private/tmp/earningsnerd-e10b-e07-full.log 2>&1
```

Root has asked the user for explicit authorization covering the held full gate/publication;
no answer was available at this checkpoint. No push occurred after `5fb6ed1`; PR #730's remote
source remains that prior head. The older passing backend checkpoint above does not cover E07a.
Resume the required combined PostgreSQL gate only after root resolves the authorization hold,
then let root own publication/readiness/merge and serialized deployment. No account operation
or production mutation occurred in this integration work.

### E12a — Integrated limiter release checkpoint (engineering)

Merged main `53348d6b41d524b9bb1e9fa41ef1a1b393f2a191` as `ec045eb` without rewriting
published history. The only conflict was the todo insertion; both E12a and E13b histories remain.
Metrics runtime, its existing test home and OPERATIONS documentation are byte-identical to
reviewed `80abcf0`. Incoming limiter implementation, Settings, security tests, frontend and CI
workflow match main. All locked contracts remain unchanged; the single original proof is retained.

Three-lens integration review found no actionable issue: the shared-worker snapshot does not
interact with the request rate limiter, all scope/rule boundaries remain intact, and behavioral
coverage still uses actual worker contention with bounded cleanup. No source correction, extra
mutation, frontend test run or production/provider call was needed.

Combined pinned backend gate on `ec045eb` enabled both Stripe and usage PostgreSQL test URLs:
Ruff clean; Bandit zero medium/high severity; **2558 passed, 2 deselected, 23 warnings in
51.64s**, exit 0, with no skips. The existing async shutdown logging diagnostic followed the
passing summary. Exact logs: `/private/tmp/earningsnerd-e12-integrated-ruff.log`,
`earningsnerd-e12-integrated-bandit.log` and `earningsnerd-e12-integrated-full.log` under the same
`/private/tmp/` directory. Reviewed source bytes and original proof remain unchanged.

Root authorized this branch push only after the combined gate. PR acceptance and serialized
production verification remain root-owned; no unrelated held action was attempted here.

### E12a — Default AnyIO worker saturation snapshot (engineering)

Base `752f3a2`. The existing admin metrics collector exposes database occupancy and EDGAR
created-thread counts, but no default AnyIO limiter pressure. Health probes and summary DB
units use this limiter. Read current CLAUDE/AGENTS, relevant test/operations lessons, handover,
and the collector/health source. No production setting, capacity, schema or admission change.

- [x] Add only `scope = event_loop`, `total_tokens`, `borrowed_tokens` and `tasks_waiting`
  under `thread_pool.anyio`, using the current default limiter's public statistics API. Preserve
  EDGAR keys. Never serialize borrower objects or acquire a worker token to collect the snapshot.
- [x] Reuse `backend/tests/unit/test_ai_metrics.py`, which already gates the admin collector.
  Exercise the real default limiter with one event-blocked worker and one waiting task; verify
  the collector returns before worker release and the counts drain afterward. Restore the exact
  original limiter capacity and finish all tasks in finally, with bounded waits.
- [x] Document GET /metrics admin authentication, per-loop aggregate snapshot interpretation,
  and dependency-access limitations in `docs/OPERATIONS.md` without new alert thresholds.
- [x] Commit source, run one idle-snapshot mutation against the occupied/queued gate, restore
  exact source, then run Ruff/Bandit/full backend with Stripe and usage PostgreSQL URLs enabled.
- [x] Complete correctness/rules/tests review and return exact committed source to root for
  independent review. No push, PR, deployment or live provider calls by this agent.

Rules 6, 8 and 12 and the existing hermetic/one-home/proof lessons apply. This observes the
responding loop's default limiter, not CPU utilization, EDGAR/default-asyncio executors, provider
or generation queues, durations, historical peaks, or fleet totals. The existing admin endpoint
still uses DB-backed authentication and a synchronous dependency, so saturation can delay the
request itself. Startup/probe deadlines and E09 counters remain separate work.


Source `80abcf0` adds aggregate AnyIO limiter statistics to the existing collector without
worker acquisition or application capacity changes. EDGAR keys, route authentication and all
locked tests remain byte-identical to base. Existing `test_ai_metrics.py` is the sole test home;
its new test uses real worker dispatch and a queued task, verifies serialization and collection
before release, then verifies drained counts and restores the exact original capacity in finally.

Initial focused invocation omitted the local EDGAR cache override and failed during the existing
collector's EDGAR import (sandbox denied the default cache directory); it did not reach snapshot
assertions. Setting `EDGAR_LOCAL_DATA_DIR` to the task's temporary cache resolved it without source
changes. The focused home passed 14 tests. Exactly one mutation replaced borrowed/waiting counts
with zero and failed the intended occupied/queued assertion: **1 failed, 13 deselected, 2 warnings
in 1.71s**. Exact committed bytes were restored; **14 passed, 2 warnings in 1.06s** afterward.

Self-review and root's independent review of `80abcf0` cleared correctness, rules/brief and
tests/gates. The public statistics API runs on the collector's event loop, scalar projection
excludes borrower objects, test workers are bounded/cleaned up, and the operating guide preserves
all snapshot/auth-path limitations. No additional mutation was repeated.

Full pinned backend gate on `80abcf0` with both Stripe and usage PostgreSQL test URLs enabled:
Ruff clean, Bandit zero medium/high severity; **2546 passed, 2 deselected, 23 warnings in
54.05s**, exit 0, with no skips. The existing asynchronous client shutdown logging diagnostic
followed pytest's successful summary. `git diff --check` passed; no runtime source changed
after review or mutation restoration.

Evidence: `/private/tmp/earningsnerd-e12-mutation-idle.log`,
`earningsnerd-e12-restored-focused.log`, `earningsnerd-e12-ruff.log`,
`earningsnerd-e12-bandit.log` and `earningsnerd-e12-full.log` in the same `/private/tmp/` directory.
No tests outside the backend or product/provider calls were needed. Root owns integration,
publication and serialized deployment; this branch remains local at this checkpoint.


### E13b — Latest-main release integration (engineering)

Merged main `752f3a2728d99be851a0fd284e746ce338cf0b04` as `ff7403e`, preserving published
history. The sole todo conflict retained E13b, E07a and E08a sections. Limiter implementation and
its existing test home remain byte-identical to reviewed `ac4bc76`. Config and configuration
docs retain both independent limiter and usage-lock settings. E07a's runtime, PostgreSQL tests
and CI workflow, and E08a's entire frontend, remain byte-identical to latest main.

The three integration lenses are clear: successful-hit ordering still supports expired-prefix
cleanup without active eviction; all 12 rules and scope boundaries remain satisfied; existing
behavioral gates and three original mutation proofs are retained, and locked tests match main.
No runtime correction or mutation repeat was needed. Frontend gates are retained from E08a's
release because this integration has no frontend delta against main.

Full pinned backend gate on `ff7403e` enabled both `STRIPE_CONCURRENCY_TEST_DATABASE_URL` and
`USAGE_CONCURRENCY_TEST_DATABASE_URL` against disposable local PostgreSQL schemas. Ruff clean;
Bandit zero medium/high; **2557 passed, 2 deselected, 23 warnings in 53.64s**, exit 0, with no
skips. The existing asynchronous shutdown logging diagnostic followed the passing summary.
Logs: `/private/tmp/earningsnerd-e13b-evidence/latest-main-ruff.log`, `latest-main-bandit.log`
and `latest-main-full.log` in that same directory. Conflict-marker checks and `git diff --check`
passed before the authorized branch push.

Root owns PR creation/readiness, remote CI and serialized deployment. The per-process 10000-key
budget and legitimate-unseen-key rejection tradeoff remain explicit assumptions, not measured
production capacity or a fleet/byte bound. No production state was changed by this integration.

### E13b — Bounded in-memory limiter keys (engineering)

`RateLimiter._hits` retains every key indefinitely. Bound each limiter independently without
resetting an active client's history. Base `6a648f7`; no Redis or fleet-wide enforcement claim.

Algorithm/default: store hit deques in an OrderedDict ordered by last accepted hit. Read the
monotonic clock inside the existing lock, prune only the expired prefix (last hit strictly older
than the unchanged cutoff), and move a key to the end only when accepting a hit. Peeks and denied
attempts never extend retention. Each removal is amortized against an earlier insertion; at most
the configured ceiling can be removed in one call, with no scan of the active suffix or separate
expiry metadata. `_hits.clear()` therefore still resets all state.

- [x] Add `RATE_LIMITER_MAX_KEYS`, a positive Settings integer defaulting to 10000 (maximum
  100000), captured per limiter at construction. This is an engineering memory budget, not a
  measured traffic threshold: it permits 10000 distinct live keys per limiter/window, bounds
  cardinality even under rotating-key abuse, and avoids assuming real production key counts.
- [x] Remove expired keys opportunistically; reject unseen keys while full and never evict active
  buckets. Existing keys retain their remaining allowance. `is_exhausted` remains a read-only
  peek, including False for absent keys even at capacity; existing Retry-After behavior remains.
- [x] Extend `test_security_hardening.py` with deterministic expiry/order, capacity/active-history,
  peek/clear and Settings-boundary behavior; one mutation proof per new invariant.
- [x] Run the full pinned backend gate and independent review, then return a clean committed
  branch to root. No locked auth tests, production flags, spend, push or deployment by this agent.

Rules 6, 8 and 12 apply. Limits and windows remain unchanged; storage is per limiter/process,
not an aggregate byte or fleet limit. At capacity, legitimate unseen keys can receive the same
429 path until idle keys expire; no active key is displaced to admit an attacker-controlled key.
Whole idle buckets expire lazily on limiter calls, and their retained key strings are not separately
byte-capped. No historical database work, auth policy change or new infrastructure is included.

Source `ac4bc76`: full pinned Python 3.11.16 / Ruff 0.16.6 / Bandit 1.9.4 gate passed.
Ruff clean; Bandit 0 medium/high; backend pytest `2490 passed, 8 skipped, 2 deselected,
23 warnings in 48.90s`, exit 0. Eight skips are the existing optional PostgreSQL billing lane,
unrelated to the in-memory limiter change. Initial focused invocation from the repository root
could not import `app`; rerunning from the required backend directory passed 22 tests.

Exactly one mutation experiment per new invariant: evicting an active bucket at capacity instead
of rejecting the unseen key caused 1 intended failure; disabling expired-prefix cleanup caused
5 intended expiry/order failures; removing the Settings range constraints caused 3 intended
validation failures (nonintegral/nonfinite type checks still passed). Every mutation restored
exact committed bytes; the final focused home passed `22 passed, 2 warnings in 0.29s`.

Root independently reviewed correctness, rules/brief and tests/gates at `ac4bc76`, with no
actionable finding. Last-accepted ordering is maintained only by successful calls; clock sampling
inside the same lock prevents concurrent samples from breaking that order. No second expiry
structure or background timer exists. Locked auth tests and all public limiter signatures are
unchanged. `_hits.clear()` compatibility was exercised by the focused and full gates. Root owns
publication, integration and serialized production verification; none occurred in this worktree.
The 10000-key default remains a proposed engineering budget, with no measured production-key
count or memory-bytes/fleet guarantee. Capacity rejection can affect new legitimate clients;
active buckets retain their limits until their existing windows expire.


E13b integration checkpoint: root authorized integration and branch push after gates. Merge
`9d3531b` incorporates main `cab71f9a71f51ce21dfc5f0fa29d3b3f8941bf5c` without rewriting
history; the sole task-ledger conflict retains all E13b and incoming E06 sections. The limiter,
Settings, focused test home and configuration documentation are byte-identical to reviewed
`ac4bc76`; prior mutation proofs remain valid and were not repeated.

Three-lens integration review found no actionable issue: bounded local state and unchanged auth
callers remain correct; rules/brief still introduce no billing, schema, fleet, production flag or
byte-limit claim; the behavioral gates and locked auth/Stripe bytes remain intact relative to main.
Full pinned backend gate with `STRIPE_CONCURRENCY_TEST_DATABASE_URL` enabled against the existing
disposable local PostgreSQL cluster passed: Ruff clean, Bandit 0 medium/high, pytest
`2538 passed, 2 deselected, 23 warnings in 55.95s`, exit 0 with no skips. The retained full log
includes the existing asynchronous client shutdown logging diagnostic after pytest success.
No frontend file changed. Branch push is authorized; PR creation/readiness, merge and serialized
production verification remain root-owned and pending at this checkpoint.
### E08a — Render trial state from resolved entitlements (engineering)

Base `cab71f9`. Pricing and settings currently use raw `status = trialing` even when the
subscription API resolves an expired trial to `is_pro = false`. Pricing then disables an upgrade
that the existing backend permits, and settings labels a Free account Pro. Independent root
refutation confirmed the mismatch; backend billing behavior remains authoritative and unchanged.

- [x] Require the API's `is_pro` plus raw trial status for the trial presentation in
  `frontend/app/pricing/page.tsx` and `frontend/features/settings/components/BillingPanel.tsx`.
- [x] Extend only their existing `PricingPage.spec.tsx` and `BillingPanel.spec.tsx` homes:
  expired-trial Free response enables the existing upgrade, suppresses trial labels/countdown,
  and retains customer-ID portal routing. Existing entitled-trial behavior stays unchanged.
- [x] Commit source; run one coordinated original-predicate mutation across both surfaces,
  restore exact bytes, and run full frontend lint/typecheck/Vitest/build gates.
- [x] Record three-lens and independent root review, evidence and clean head. Push only after
  gates pass; root owns PR creation/readiness/merge and both-theme preview verification.

Read `frontend/DESIGN_SYSTEM.md` and relevant lessons. Rules 4, 6, 11 and 12 apply; use server
plan truth without new browser expiry arithmetic. No backend/API/schema/locked-test, pricing,
trial activation, promo, analytics, token or styling change. E08-3 loading/error labels, E08-4
FAQ timing, annual totals and price experiments remain separate. No live expired-trial account
or preview acceptance is claimed from mocked tests.



Source `48f51f3` changes only the two trial predicates/comments in runtime code. A resolved
Free subscription with raw `trialing` status now gets the existing upgrade action and Free label;
customer-ID portal routing is unchanged. Existing entitled-trial cases still pass. The pricing
regression seeds the resolved subscription cache before rendering to avoid a false pass through
the pre-existing transient Free loading label. The settings regression covers with/without a
Stripe customer. All backend/locked tests, dependency pins, price variants and flags are unchanged.

Verification used Node 22.23.2 and an APFS clone of the existing matching dependency tree;
package-lock identity was checked, with no install or pin change. Initial setup invocations ran
before copying finished and then from the wrong working directory; neither reached test assertions.
The first actual focused run exposed one mistaken new expectation: a Free user without a customer
already uses the label “Upgrade to Pro”, not “Subscribe to Pro”. The test was corrected to the
existing branch, with no additional runtime change. The focused homes then passed all 11 tests.

Exactly one coordinated mutation restored the original raw-status predicate in both components:
pricing failed to find the permitted upgrade button, and both settings cases failed to find Free.
Result: `2 failed` files, `3 failed | 8 skipped` tests, 4.36 s. Both files were restored byte-for-byte
to committed `48f51f3`; no mutation was repeated. Final full frontend gate passed: lint with zero
warnings, `tsc -p tsconfig.ci.json`, Vitest **97 files / 504 tests passed** in 31.44 s, and
`next build` (compiled 17.2 s, 27/27 static pages, `/pricing` prerendered). All commands exited 0.
The build used narrowly approved network access for existing font downloads. Its no-Sentry-token
warnings mean no local release/source-map upload; existing jsdom navigation diagnostics appeared
in the successful Vitest run. Logs live at `/private/tmp/earningsnerd-e08-{lint,typecheck,full-vitest,build}.log`,
`/private/tmp/earningsnerd-e08-focused-corrected.log` and
`/private/tmp/earningsnerd-e08-mutation-trial-predicates.log`.

Self-review and root's independent three-lens review of `48f51f3` are clear: the backend remains
the only plan resolver, the historical raw row cannot override its result, and the gate proves
both affected surfaces without editing locked anchors. Lesson link and `git diff --check` passed.
Source and evidence are ready for the authorized branch push. Root owns PR creation/readiness,
remote CI, both-theme preview and release; no live expired-trial account behavior is claimed.

### E07a — Atomic completed-use counters (engineering)

Approved implementation scope: preserve all three public monthly increment helpers/call sites,
existing first-row history selection and billing timing. No reservation, quota-admission change,
schema/unique constraint, historical repair or locked-test edit.

- [x] Replace Python read-modify-write with SQL expression increments on the selected bucket;
  only absent buckets lock the parent User, then re-read before creating the first row.
- [x] Set a PostgreSQL transaction-local lock timeout through SQLAlchemy `set_config`, default
  3000 ms, positive integral milliseconds up to 10000; never mutate global connection settings.
  Errors retain existing caller policy; no retry after an uncertain commit.
- [x] Add one nonlocked usage transaction home with real PostgreSQL concurrency, stale-session,
  first-use, bounded-lock-wait, rollback and unchanged-history/background-cache behavior.
- [x] Add explicit PostgreSQL CI execution and extend the existing structural workflow gate.
- [x] Commit source, retain exactly one mutation per new invariant with exact restoration, run
  Ruff/Bandit/full backend and workflow/Node checks, and record evidence for independent review.
- [x] Return a clean committed branch to root; no push, PR, merge or deployment by this agent.

The guarantee covers successfully committed calls after old service/job writers drain. It does
not reserve admission, fix historical duplicates or promise strict billing accounting. First-row
creation can contend with the Stripe account lock, bounded by the transaction-local lock timeout;
existing-bucket increments do not acquire that parent lock. The setting bounds lock acquisition
waits, not overall transaction duration or network/commit uncertainty.


Source `60f28a0`: the usage transaction home plus migration workflow gate passed 37 checks on
actual PostgreSQL with disposable schemas. Full backend gate with both Stripe and usage
PostgreSQL cases enabled: Ruff clean; Bandit 0 medium/high;
`2458 passed, 2 deselected, 23 warnings in 50.55s`, exit 0. Workflow-focused gates: 103 passed;
Node-version gate: 3 passed on Node 22.23.2. No locked contracts or eval baseline changed.

Exactly one mutation per new invariant: stale Python increment → 3 intended failures; removed
first-use lock/re-read → 1 (three duplicate rows); missing lock timeout → 2; parent lock on an
existing bucket → 1; connection-global timeout → 1; unbounded/fractional timeout setting → 6;
updates across duplicate history → 1; uncertain-commit retry → 2; skipped legacy signed-in
background-cache charge → 1; missing required PostgreSQL CI URL → 1. All ten proofs restored
exact committed bytes before the successful full gate. No earlier workstream proof was repeated.
Independent correctness/rules/tests review of `60f28a0` found no actionable issue. Main `a5ba97e`
is integrated without changing E07a source; the combined full gate is deliberately deferred until
E06 joins main. Prior mutation proofs remain valid and will not be repeated.

Integration checkpoint: released E06 main `cab71f9` is now merged, including account export,
timezone normalization and the worker-serialized lifetime fixture. Only checklist/ledger conflicts
needed manual resolution; both workstreams were retained. Run one final combined backend gate
with Stripe and usage PostgreSQL cases, workflow readers and Node pin before the authorized branch
push. Root owns PR creation and serial deployment; E07b reservations remain unimplemented.


### E06 CI fixture correction — Isolate connection lifetime from preparatory contention (engineering)

CI run 34034568223 failed the existing nonlocked E03 lifetime case before provider readiness:
progress SQL raced an excerpt worker against its one-connection/50 ms test pool. Three independent
code passes support this interleaving; the actual CI connection holder remains inferred. Preserve
all runtime code, locked anchors, pool limits, readiness checks and cancellation/ownership assertions.

- [x] Serialize only this fixture's dispatched DB units inside their worker with a threading mutex;
  retain independent connection probes outside it, including cancellation-before-worker-close checks.
- [x] Reproduce controlled preparatory contention once and pass the corrected target under the same
  delay; prove intentional connection retention still fails the existing lifetime assertion once.
- [x] Restore committed source, run the full PostgreSQL backend gate, record evidence and return a
  clean reviewed head to root for publication. No timeout increase, retries, skip or production edit.

Source `7b6d8c3` changes only 14 lines in the nonlocked lifecycle gate. The mutex lives inside
actual dispatched workers and spans each complete DB unit, so cancelling its await cannot release
serialization before session cleanup. Runtime code and locked anchors are unchanged.

A controlled diagnostic held the excerpt's connection for 150 ms and waited for its ownership
before dispatching analyzing progress. The original fixture failed with the same 50 ms QueuePool
error (1 failed); the corrected fixture passed under identical conditions (1 passed). This proves
the competing-worker interleaving, not the identity of the connection holder in the CI failure.
Exactly one harness-integrity mutation retained a Session during provider wait and failed the
existing `provider retained a DB connection` assertion. All temporary diagnostics/mutations were
restored byte-for-byte; the unchanged full lifecycle home then passed 24 tests.

Final full gate on `7b6d8c3`: Ruff clean; Bandit 0 medium/high; **2526 passed, 2 deselected,
23 warnings in 56.65s**, exit 0, including actual PostgreSQL transaction cases. The existing closed
logging-stream teardown diagnostic followed the passing summary. Prior payment/export proofs
were not repeated. Root reviewed committed `7b6d8c3` and cleared correctness, rules/brief and
tests/gates: worker mutex spans cleanup, independent probes and strict original assertions remain
intact, and the controlled contention/retention evidence supports the correction. Root owns
publication and serial deployment.
Evidence: `/private/tmp/earningsnerd-e06-contention-repro.log`,
`/private/tmp/earningsnerd-e06-contention-corrected.log`,
`/private/tmp/earningsnerd-e06-lifetime-retention-mutation.log`,
`/private/tmp/earningsnerd-e06-lifetime-final-focused.log`,
`/private/tmp/earningsnerd-e06-ci-fixture-final-bandit.log` and
`/private/tmp/earningsnerd-e06-ci-fixture-final-full.log`.

### E06 review correction — Include attributed payment evidence in account export (engineering)

Two independent code refutation passes confirmed that the explicit account export omits the
new account-linked BillingPayment observations. Preserve the existing export fields and billing
semantics; no locked contract, schema, payment policy, retention or production changes.

- [x] Add a `billing_payments` array containing all stored observations owned by the authenticated
  account, with explicit fields and UTC timestamps; exclude other accounts and unattributed rows.
- [x] Gate the real export route in the existing billing unit home, including retained live/test
  evidence, optional nulls, exact timestamps, account isolation and an empty account result.
- [x] Commit source, perform one original-export mutation proof and exact restoration, then run
  the full backend gate with the actual PostgreSQL transaction cases enabled.
- [x] Return reviewable committed evidence to root; root owns publication and serial deployment.

Source `f5f4c99` passed the existing billing home (28 tests). One original-export mutation
failed with `KeyError: 'billing_payments'`; exact restoration passed 28 tests. Independent review
then identified timezone relabeling of aware database values. The correction converts aware
values to UTC and attaches UTC only to SQLite's naive values. The same route regression now
also covers a database value represented at UTC+02:00; its represented instant must survive.
The initial full run is superseded because it began before this correction was requested.

Corrected source `b79ac6e` passed 29 billing tests. Exactly one prior-serialization mutation
failed on shifted `02:00:00Z` timestamps; exact restoration passed all 29 tests. Earlier payment,
report and original-export proofs were retained without repetition. Root's corrected review is
clear across correctness, rules/brief and tests/gates. Both review findings survived two independent
refutation attempts; all locked tests remain byte-identical to `1fbec92`.

Final corrected full gate: Ruff clean; Bandit 0 medium/high severity; **2526 passed, 2 deselected,
23 warnings in 50.00s**, exit 0, with the actual PostgreSQL transaction home enabled.
The same pre-existing closed logging-stream teardown diagnostic followed pytest's passing summary.
No workflow, migrations, schema, policy or provider calls changed. No push or deployment by this task.
Evidence: `/private/tmp/earningsnerd-e06-export-mutation.log`,
`/private/tmp/earningsnerd-e06-export-timezone-mutation.log`,
`/private/tmp/earningsnerd-e06-export-final-focused.log`,
`/private/tmp/earningsnerd-e06-export-final-bandit.log` and
`/private/tmp/earningsnerd-e06-export-final-full.log`.

### E06 — Observed invoice-payment evidence (engineering)

Founder-approved implementation follows the bounded read-only design. Start at `f94501f`;
merge E05c before publication. Only `invoice_payment.paid` records allocations. This is gross
observed payment evidence, not MRR/ARR, net revenue or an accounting ledger. No prices, promo,
trial, production endpoint selection, API-version setting or monetary transaction changes.

- [x] Add a minimal minor-unit payment model and new guarded idempotent migration; preserve
  account deletion through ORM/FK cascade and minimize unattributed pseudonymous references.
- [x] Validate canonical payment evidence, attribute only unambiguous customer ownership,
  deduplicate payment IDs across event IDs, and snapshot beta/invite dimensions without inference.
- [x] Add a read-only report with separate currencies/modes, supported payment types, zero and
  unattributed exclusions from paying-user cohorts, and explicit coverage/refund/credit limits.
- [x] Integrate E05c's bounded reader and existing transaction worker; record payment/event in
  one commit and emit best-effort analytics after session closure. No second Stripe client owner.
- [x] Add money/evidence/model tests in one new unit home and extend the existing transaction
  home for actual PostgreSQL duplicate delivery. Keep locked tests byte-identical.
- [x] Commit source, retain exactly one mutation proof per new invariant, and run full backend
  and actual PostgreSQL/migration gates with exact evidence.
- [x] Complete independent review of the corrected final source before publication.
- [ ] Root publishes and verifies CI/release serially after E05c; verify production endpoint
  event selection separately before claiming observation coverage. No historical backfill.


E06 source `26f66a2` integrated E05c `aa36c95` without further locked-test edits. Initial focused
billing gate: 99 passed, 9 PostgreSQL-only skips; actual PostgreSQL transaction home: 23 passed.
Eight bounded mutations each produced one intended failure: allocation conflict, ambiguous
attribution, zero exclusion, truncated price page, cohort paid-time ordering, account erasure,
payment/event atomicity, and provider invoice identity. Every mutation restored committed bytes.

Independent review found a READ COMMITTED report race that the initial gate missed: a first
payment inserted between separate first-timestamp/window reads could raise KeyError. Corrected
source `a7e2ff4` uses a grouped first-payment subquery in the same window-row statement. The new
PostgreSQL interleaving regression and revenue unit home passed 28 tests. Exactly one additional
prior-query mutation reproduced the KeyError (1 failed); it was restored. Earlier eight proofs
were not repeated. Coverage metadata remains a later read, not an atomic full-report snapshot.

Prior source gate on `a7e2ff4`: Ruff clean; Bandit 0 medium/high severity; **2524 passed, 2 deselected,
23 warnings in 51.90s**, including all actual PostgreSQL cases. The interpreter emitted a closed
logging-stream teardown diagnostic after pytest's passing summary; no test failed. Prior source's
2514-passed/9-skipped result is superseded. No eval runner, live Stripe call, endpoint change,
price/promo change, push or deployment was performed by this task.

The dedicated local PostgreSQL 15 database `earningsnerd_e06_migrations` passed the repository
migration script with the legacy-name decoy: **applied=35 skipped=0 → applied=0 skipped=35 →
applied=35 skipped=0** after test-ledger reset; the new User FK reports cascade. Initial harness
setup stopped before applying SQL because the standalone Settings required a test SECRET_KEY;
setting that test-only value resolved it. Existing applied migrations remain untouched.

Evidence files retained locally: `/private/tmp/earningsnerd-e06-focused.log`,
`earningsnerd-e06-postgres.log`, `earningsnerd-e06-mutation-*.log`,
`earningsnerd-e06-report-race-fixed.log`, `earningsnerd-e06-migrations.log`,
`earningsnerd-e06-bandit-final.log` and `earningsnerd-e06-full-final.log` (same `/private/tmp/`
prefix). [Operating guide](../docs/observed-invoice-payments.md) defines report limits and the
production endpoint/event-selection verification still required before coverage is claimed.

E06 integration checkpoint: root and independent correctness/rules/tests reviews cleared the
report correction. Integrated E10 main `a5ba97e` as `fb0e846`, then E05c main `6a648f7` as
`bef2dc8`. E05c source equals inherited `aa36c95`; expected squash conflicts retained E06's
reader factoring, payment worker path and PostgreSQL regression. Mechanical diff against
`fb0e846` found no E06 runtime/test changes. Locked contracts are byte-identical to current main.
No mutation proof was repeated. The prior 35-file migration replay excludes the separately
verified E10 migration now integrated; remote combined migration CI must cover all 36 files.

Combined full gate on `bef2dc8`: Ruff clean, Bandit 0 medium/high severity,
**2524 passed, 2 deselected, 23 warnings in 56.08s**, exit 0. Direct pinned Python invocation
preserved `DYLD_FALLBACK_LIBRARY_PATH`; PostgreSQL cases used disposable schemas. Exact logs:
`/private/tmp/earningsnerd-e06-integrated-full.log` and
`/private/tmp/earningsnerd-e06-integrated-bandit.log`. This supersedes the prior local full gate.
Root owns publication after E05c production verification; this task did not push or deploy.

### E05c — Reconcile the currently bound Stripe subscription (engineering)

The founder explicitly approved the fixture-only `_post_event` change on 2026-09-06:
“Approve the fixture-only change.” Only that helper's provider stub may change in
`backend/tests/unit/test_subscription_webhook_sync.py`; every payload/request/assertion and
all other locked tests remain unchanged. This does not approve a replacement-transition policy.

- [x] Add a dedicated exact-ID Stripe read with explicit connect/read inactivity settings,
  zero SDK retries, recursive conversion, identity/status/optional-field validation and transport cleanup.
- [x] Reconcile created/updated events only for the current bound ID, after account lock/recheck
  and dedup; preserve checkout, deletion, unknown-owner, initial and different-ID behavior.
- [x] Fail provider/invalid-state reads with retryable 503 and atomic rollback; never use a stale
  payload as a success fallback. Retain the existing entitlement writer and original event identity.
- [x] Apply the approved helper-only stub; add boundary/stale-state tests and extend the existing
  PostgreSQL transaction home for provider contention, cancellation and successful retry.
- [x] Commit source, run one bounded mutation per new invariant with exact restore, and run
  Ruff/Bandit/full backend plus real PostgreSQL gates. Record evidence and scope limits.
- [x] Update configuration/architecture and execution-ledger evidence; return a clean committed
  branch to root for independent review/publication. No push, PR, merge or deployment by this agent.

The proposed 2-second connect / 3-second read values are phase/inactivity limits, not a total
five-second deadline. DNS/progressing responses may exceed their sum. The account lock and DB
connection remain owned by the worker during this read. Cross-ID replacement chronology,
cross-user identity races and analytics exactly-once remain separate work.

Source `aa36c95`: 93 focused billing tests passed, including all unchanged assertions in the
approved locked fixture; real PostgreSQL transaction/provider-wait gate: 13 passed. The full
local backend gate with real PostgreSQL enabled passed: Ruff clean, Bandit 0 medium/high,
`2486 passed, 2 deselected, 23 warnings in 55.96s`, exit 0. The first invocation wrapped Python
in `/bin/sh`, which stripped macOS `DYLD_FALLBACK_LIBRARY_PATH`: 2 PDF native-library failures,
2484 passed. A direct Python invocation restored the intended environment; no source changed.

Exactly one mutation per new invariant, each with intended assertion failures: stale event in
place of current snapshot → 4; stale payload fallback after provider failure → 5; skipped provider
validation → 16; omitted explicit timeout/retry configuration → 3; skipped transport close → 3;
unbounded/nonfinite settings → 10; disabled reconciliation scope admission → 4 (unknown-owner
case still passed). The first six proofs preceded the full gate; the final scope proof restored
exact `aa36c95` source and its focused reconciliation gate passed all 45 tests. Existing worker/lock
mutations were not repeated; the PostgreSQL
provider-wait cases extend their contention/cancellation coverage. The approved locked helper
patch context mechanically reduces to the exact base file; all other locked files are untouched.
Lesson index link checked. Root and independent correctness/rules/tests review of `aa36c95`
found no actionable issue. After integrating main `a5ba97e` as `d404908`, full pinned Ruff/Bandit passed and the PostgreSQL-enabled backend gate reported `2486 passed, 2 deselected, 23 warnings in 47.31s`, exit 0. Runtime reconciliation source and approved locked fixture are unchanged; no mutation repeat was needed. Publication and production verification remain pending.

E07a combined integration `5c5f8b3` includes released E06 main
`cab71f9a71f51ce21dfc5f0fa29d3b3f8941bf5c`. Final pinned gate: Ruff clean; Bandit 0 medium/high;
**2545 passed, 2 deselected, 23 warnings in 57.06s**, exit 0, with both Stripe and usage
PostgreSQL URLs configured against disposable schemas. Workflow readers: **103 passed**; Node
22.23.2 pin gate: **3 passed**. The existing closed logging-stream teardown diagnostic followed
the passing pytest summary. No mutation was repeated; E07a source/tests/CI remain byte-identical
to `714b686`, and E06 export/timezone/lifetime corrections match `cab71f9` exactly.

Integration review is clear across all three lenses: correctness preserves public counter helpers,
completion timing, selected history and bounded lock waits; rules/brief introduce no reservations,
schema change, founder policy, new orchestrator or entitlement path; tests/gates retain the ten
prior mutation proofs and execute real PostgreSQL cases in required CI. The only test differences
against main are the new usage transaction home and the nonlocked parameterized CI structural
check. All locked contracts and eval baselines are byte-identical to `cab71f9`.

Exact combined logs: `/private/tmp/earningsnerd-e07-evidence/integrated-full.log`,
`integrated-bandit.log`, `integrated-workflow.log` and `integrated-node.log` in that directory.
The parent authorized branch push after this gate; PR creation/merge and production deployment
remain root-owned. E07b is design-only and is not included.

### E13a integration checkpoint

Publication verification on combined source `4db219071e0179764224b30301f6b512e57ea6f7`
against main `ee3ac9882b74453bb670c69b5b05142338a53844`: Ruff clean; Bandit 0 medium/high;
**2565 passed, 2 deselected, 23 warnings in 61.96s (0:01:01)**, exit 0, with Stripe, usage
and login PostgreSQL URLs configured. All six login concurrency cases ran. Workflow readers
(including YAML parsing): **104 passed, 16 warnings in 3.12s**; Node 22.23.2 pin: **3 passed**.
The pre-existing closed logging-stream teardown diagnostic followed the passing backend summary.

Three-lens integration review is clear. Correctness: SQL conflict updates retain the original
reset comparisons, null handling, threshold and timestamp rules; success clear remains caller-owned.
Rules/brief: runtime and login concurrency tests match `24a4d1c` exactly; latest main's limiter,
worker metrics, billing, usage counters, frontend, locked anchors and eval baseline are preserved.
Tests/gates: all three required PostgreSQL CI steps and structural entries remain; the original
5-failure/1-pass runtime mutation and 1-failure CI mutation are retained without repetition.
No actionable finding required refutation or source repair. Frontend equals main, so only the
required Node/workflow check was repeated. Whitespace checks and post-commit status are clean.

Exact fresh logs: `/private/tmp/earningsnerd-e13-evidence/approved-ruff.log`,
`approved-bandit.log`, `approved-full.log`, `approved-workflow.log`, `approved-node.log`.
The founder-approved normal branch publication follows this evidence commit; root owns PR,
remote CI, merge and deployment verification. No flag, pricing, spending, policy or data repair.


Latest-main publication checkpoint: the founder explicitly approved all five exact actions in
`outputs/remaining-verification-publication-approval.md`, including publication of this branch
to `neilmac91/EarningsNerd` and conflict resolution with required full gates. Integrate main
`ee3ac9882b74453bb670c69b5b05142338a53844`, preserve all three PostgreSQL execution paths,
review correctness/rules/tests and run the full backend plus workflow/Node gates with all three
PostgreSQL URLs. Existing runtime and CI mutation proofs remain scoped to unchanged source.
Root owns PR creation, CI follow-through, serialized merge and deployment verification.


Main `90fdc6972e1ef03af75e55f62cb204e9664e0ba9` is merged into the existing login-counter
branch. Resolve overlapping CI additions by retaining Stripe, usage and login PostgreSQL steps
and all three parameterized structural entries; retain each workstream's documentation. Runtime
login source and its concurrency tests remain the reviewed `24a4d1c` implementation. Run one
combined full backend gate with all three PostgreSQL URLs, workflow readers and Node pin before
an authorized branch push. Root owns PR creation/merge/release; E09 publication remains held.

Combined source `c1ec2bb` against main `90fdc69` passed the pinned full backend gate:
Ruff clean; Bandit 0 medium/high; **2552 passed, 2 deselected, 23 warnings in 45.98s**, exit 0.
All three PostgreSQL URLs were configured; Stripe, usage and login cases ran in disposable
schemas. Workflow readers: **104 passed**; Node 22.23.2 pin: **3 passed**. The pre-existing
closed logging-stream teardown diagnostic followed pytest's passing summary.

Integration review is clear across correctness, rules/brief and tests/gates. Runtime login code
and its concurrency home match reviewed `24a4d1c`; reset comparisons, threshold/timestamps and
caller-owned success clear remain unchanged. CI retains all three PostgreSQL steps and structural
entries. E06 corrections, E07a runtime and every locked anchor/baseline match main. No schema,
policy, deletion, config, reservation or E09 change was added. Original runtime and CI mutation
proofs remain valid; neither was repeated. Diff/whitespace checks are clean.

Combined logs: `/private/tmp/earningsnerd-e13-evidence/integrated-full.log`, `integrated-bandit.log`,
`integrated-workflow.log` and `integrated-node.log` in that directory. Root authorized normal
branch push after these gates; PR creation/merge and production verification remain root-owned.

### E13a — Atomic failed-login recording (engineering)

Bounded implementation from `a5ba97e`: replace the race in durable failed-login recording with
native SQLAlchemy PostgreSQL/SQLite upserts on the existing email-hash primary key. Preserve
all three public helpers, commit ownership and exact reset/threshold/window behavior. No schema,
data deletion, configuration/flag change, auth contract change or admission-reservation claim.

- [x] Use one atomic insert/update, retaining server-default first-insert timestamps, explicit
  failure timestamps on updates and conditional expired-lock/stale-window reset semantics.
- [x] Keep success clearing in the caller transaction; document/test linearized clear/failure
  outcomes without claiming that credential checks already in progress are reserved.
- [x] Reuse existing behavioral tests; add only PostgreSQL concurrency invariants in one new
  `backend/tests/integration/test_login_lockout_transactions.py` home and required CI execution.
- [x] Commit source, run exactly one mutation per new invariant with exact restoration, then
  full backend and workflow/Node gates. Keep every locked auth/stream/billing test byte-identical.
- [x] Record independent review/evidence and return clean commits to root; no push/PR/deploy.

The per-IP limiter, durable-row retention and event-loop/database ownership remain separate.
Existing revisions can still overwrite counts until old writers drain. No new database timeout
or retry policy is introduced, and database failures continue to propagate.


Source `24a4d1c`: 66 focused PostgreSQL/behavioral/unchanged-auth/workflow checks passed.
Full pinned backend gate with login and Stripe PostgreSQL cases enabled: Ruff clean, Bandit
0 medium/high; `2446 passed, 2 deselected, 23 warnings in 47.75s`, exit 0. Workflow-focused
gates: 103 passed; Node pin: 3 passed on Node 22.23.2. Every locked test and eval baseline is
byte-identical to the base.

One original-implementation mutation exercised both new runtime invariants: concurrent failed
recording and success-clear interleaving. It produced 5 intended failures / 1 pass: missing-row
count 2 instead of 3, existing count 9 instead of 11, expired/stale resets 1 instead of 3, and
StaleDataError after committed clear instead of a new count of 1. The rollback-clear case still
passed. One separate missing PostgreSQL CI URL mutation failed the intended structural assertion.
Both files were restored to exact committed bytes before the successful full gate. Existing
behavioral tests were reused; no earlier reset/timestamp/auth proof was repeated.

Root's independent source correctness/rules review found no actionable issue. The final local
gates and bounded proofs complete the tests/gates evidence. Root owns integration, publication,
remote CI and serialized release; none is claimed by this source checkpoint.

### E10a — Filing-first financial-facts index (engineering)

Bounded E10 slice, based on `f94501f`: `get_filing_fundamentals` filters `filing_id` and
`fiscal_period = FY`, then orders by `concept, period_end`. Existing model/migration indexes
lead with company, concept, accession or period; none leads with filing. Preserve the query,
including restated rows (`is_latest = false`) and single-filing provenance.

- [x] Add `ix_financial_fact_filing_period_concept_end` to the model with columns
  `(filing_id, fiscal_period, concept, period_end)` and no partial predicate.
- [x] Add only `backend/migrations/20260906_financial_fact_filing_index.sql`, using
  `CREATE INDEX CONCURRENTLY IF NOT EXISTS` outside any transaction/DO block; apply solely
  through the existing ledger script, whose INVALID-index check fails a cancelled build.
- [x] Verify index identity/order with disposable PostgreSQL and retain existing migration safety
  gates. Review removed the new implementation-mirroring test under proportionality guidance.
- [x] Verify the new index actually builds on disposable PostgreSQL (remove only its fresh-schema
  copy before applying), then run the ledger apply/skip/reset-and-reapply triple pass and inspect
  validity/column order. Run the full pinned Ruff, Bandit and backend pytest gate.
- [x] Record independent review and hand the clean commit to the root agent for serial release.

Rules 3, 6 and 12, ADR-0007, and the migration/lock-timeout lessons apply. No applied migration,
locked test, query, facts ingestion, flag, capacity or production data changes. E03 is released;
W3-9 flag repair remains independent because this slice changes no service or flag behavior.
Pagination and other E10 hot reads remain queued.

First-build risk: production fact volume and build time are unmeasured. Concurrent creation
avoids the normal SHARE write-blocking build, but consumes database CPU/I/O, waits for old
transactions and is bounded by the existing 10 s lock / 120 s statement budgets. If cancelled,
the existing script fails on an INVALID index even if a retry recorded the migration; it prints
operator recovery (`DROP INDEX CONCURRENTLY`, delete that ledger row, rerun the deploy).
Do not silently skip, auto-delete an index or increase production timeouts. A failed production
build needs founder-authorized recovery or a separately reviewed operational plan; no such
failure is assumed here and no production inspection/application is part of this task.

Verification checkpoint: source `36f5dbe`, pinned Python 3.11.16 / Ruff 0.16.6 / Bandit 1.9.4.
Focused facts + migration gate: `71 passed, 2 warnings in 1.71s`. Full Ruff/Bandit exit 0;
backend pytest: `2434 passed, 6 skipped, 2 deselected, 23 warnings in 46.70s`, exit 0.
The six skips are the existing PostgreSQL-only Stripe concurrency cases in the ordinary SQLite
lane; E10 does not change billing. Locked contracts are byte-identical to `f94501f`.

Historical source-checkpoint experiment (the added test was removed in review): exactly one
mutation swapped the model's first two index columns, and the then-present gate
failed at `fiscal_period != filing_id` (1 failed), then exact source restoration passed
(1 passed). The first invocation used the repository root and could not import `app`; it did
not reach the invariant. A same-second Python bytecode cache retained the swapped order after
restoration; refreshing only the file mtime cleared it, with committed bytes unchanged.

Actual PostgreSQL 15 verification used only the new disposable local database
`earningsnerd_e10_index`, separate from the Stripe test schemas. Fresh schema was built with
only the new index omitted, proving the migration creates it rather than merely skips it.
The shared ledger script reported `applied=35 skipped=0`, `applied=0 skipped=35`, then
`applied=35 skipped=0` after a disposable ledger reset. Each catalog read showed
`indisvalid=true`, `indisready=true`, and the expected four-column btree definition.
The new migration's recorded SHA-256 is
`1e23e9cc5f8096a86d547f13dd46d53f978e2442dbad9cf569eecaa3aa23e89a`.
No live database measurement or migration execution occurred. This checks schema behavior,
not a populated-table performance claim or a production first-build duration estimate.

Initial root review at `36f5dbe` found no actionable issue. PR review subsequently identified
the added test as an implementation mirror for a reversible performance index; two fresh
refutation attempts confirmed the finding. The final change removes that test, retaining the
actual PostgreSQL catalog/triple-pass evidence and existing generic migration gates. No new
correctness invariant is claimed and the historical mutation is not a required final gate.
Existing timeout and INVALID-index gates remain unchanged; no new recovery
mechanism or timeout guarantee is claimed. Root owns publication, remote CI/evals and serialized
deployment verification; none has happened for this branch. No founder decision is needed to
review the index change; an actual failed production build would require the recovery decision
described above.

Final proportionality correction `1d59f17`: only the added 20-line test was removed; the test
file is now byte-identical to `f94501f`. No model/migration source changed and no mutation or
PostgreSQL experiment was repeated. Full pinned Ruff/Bandit passed again; pytest reported
`2433 passed, 6 skipped, 2 deselected, 23 warnings in 51.14s`, exit 0. The six skips remain
the existing PostgreSQL-only billing cases; the retained log includes the existing asynchronous
client shutdown logging error after pytest success. Final index review relies on source inspection,
the existing migration safety suite and actual PostgreSQL verification recorded above.

Root release checkpoint: PR #726 merged as `a5ba97e692246f08e35e05a92128443853ad5121`
after final-head CI `34032131137`, summary artifact `9989052658` (52/52, no errors/hard
regressions) and Copilot `34032131118` artifact `9989000339` (18/18 accepted) passed.
Source/fixture hashes and migration triple-pass were verified. Production run `34032605285`
succeeded: deploy job `101485181717` reported `applied=1 skipped=34`, image
`46d56ced269fdd32bb4232c0b1f40ac5ec56b54b2f92f1ea2c86ae95cf1c919b`,
revision `earningsnerd-backend-00280-xcp` serving 100%. Independent health timestamp
`1788697428.587389` was healthy (database 6.42 ms, Redis disabled, SEC circuit closed).

### E05b prerequisite — Serialized webhook transactions (engineering)

The founder asked to proceed with the next steps after verified E03/E05a releases.
This prerequisite preserves all locked contracts. General stale-event reconciliation remains
separate at this source checkpoint; the founder subsequently approved the E05c helper-only stub.

- [x] Move verified Stripe-event database work into one worker-owned session/transaction.
- [x] Lock the existing User row with PostgreSQL NOWAIT before rereading identity and deduplication;
  retry contention without acknowledging or recording an unprocessed event.
- [x] Commit subscription state and event ledger together; emit plain best-effort analytics only
  after successful commit and session cleanup. No ORM value crosses the worker boundary.
- [x] Add one nonlocked test home, `backend/tests/integration/test_subscription_event_transactions.py`,
  for thread/cancellation ownership, rollback/signals and actual PostgreSQL contention/delivery.
- [x] Run the PostgreSQL cases explicitly inside the existing migration CI job, with
  `STRIPE_CONCURRENCY_TEST_DATABASE_URL`; require PostgreSQL when supplied and skip only those
  fixtures when absent from the ordinary SQLite lane. Gate this CI execution path mechanically.
- [x] Retain one mutation proof per new invariant, full local backend/workflow checks and independent review.
- [x] Publish draft PR, inspect actual CI/eval reports and verify the serialized production release.

No new Stripe network calls, schema migration, locked-test changes, pricing/trial/promo policy,
production flag or capacity change. Per-user serialization does not establish Stripe chronology,
cross-user identity uniqueness or exactly-once analytics. No event timestamp/ID tie-break is added.

Source `19e0584`: full pinned local backend gate passed with PostgreSQL cases enabled:
`2439 passed, 2 deselected, 23 warnings in 52.84s`, exit 0; Ruff clean; Bandit 0 medium/high.
Focused PostgreSQL + unchanged locked billing gates: 59 passed. Local cluster PostgreSQL 15.15
uses only a temporary Unix socket and disposable schemas; no production database was accessed.
Workflow-related backend gates: 102 passed; Node-version gate: 3 passed. Documentation links checked.

Exactly one mutation per new invariant: direct event-loop execution → 2 intended failures;
bypassed account lock/recheck → 2; premature state commit → 1 (subscription without event receipt);
analytics before commit/close → 1; missing PostgreSQL CI URL → 1. Every source mutation restored
exact committed bytes; restored runtime gate 11 passed and restored CI gate 1 passed. Independent
correctness/rules/tests review found no actionable issue. Locked contracts and baseline remain
byte-identical. CI/eval and production outcomes were pending at that source checkpoint.

Root subsequently verified #725 merged as `f94501f`; production run `34029873954`, deploy
`101477674329`, succeeded with `applied=0 skipped=34`. Revision `00279-s9z` serves 100%;
independent health timestamp `1788693905.0609558`: healthy, DB 8.24 ms, Redis disabled, SEC closed.

### E05a — Subscription identity and delayed-event guards (engineering)

- [x] Reject checkout bindings that conflict with existing customer/subscription ownership.
- [x] Preserve synchronized state when a matching checkout arrives after subscription events.
- [x] Ignore a deletion for an old subscription after its customer has a replacement.
- [x] Add adversarial sequences in `backend/tests/unit/test_subscription_identity.py`; keep
  every locked checkout/webhook contract byte-identical and retain metadata-only bootstrap.
- [x] Commit source, restore original behavior for exactly one mutation experiment, restore
  exact source bytes, and run Ruff, Bandit and the full backend pytest gate.
- [x] Record review/evidence and return the commit to the root agent without pushing or deploying.

Scope: existing identity/state guards only. No price, promo, trial, schema or entitlement-policy
change. E05b retains general same-subscription event ordering and concurrent-delivery handling;
these checks do not introduce an event watermark or serialize webhook transactions.

Verification: original source checkpoint `e7371c6`; exactly one mutation experiment restored
`049cd4f`'s entire `subscription_sync.py`, producing `15 failed, 2 warnings in 0.48s` at the
intended identity/state assertions. Exact restoration: `15 passed, 2 warnings in 0.46s`.
Focused new/locked checkout, webhook and entitlement gates: `64 passed, 17 warnings in 2.59s`.
The review correction preserves the existing activation return for already-synchronized users
who remain entitled, and returns None for nonentitled late checkouts; its return-value assertions
extend the existing cases. Final Ruff/Bandit exit 0; full pytest:
`2405 passed, 2 deselected, 23 warnings in 46.03s`, exit 0. The existing post-summary asynchronous
client shutdown logging error remains in the retained log. Tests used the pinned Python 3.11.16
venv, Homebrew native-library lookup and an isolated temporary EDGAR data path.

Independent correctness/rules/tests review found no further B1–B3 issues after the activation
correction. Two refutation passes confirmed that existing entitlement truth permits canceled,
past-due and expired-trial replacements while preserving active replacements against old events.
Locked checkout/Stripe contracts are byte-identical. No schema, configuration, pricing, promo,
trial, source-generation or production changes. E05b retains arbitrary upsert ordering,
concurrent-delivery races and ambiguous replacement checkouts when the current subscription
is nonentitled; analytics exactly-once also remains open for E05b/E06. Root owns publication,
exact-head remote checks and serialized deployment verification.

Root release checkpoint: the founder explicitly approved GitHub publication, merge and normal
deployments. E03 #723 merged as `4d15b900698bd5e78dd7377c620999e75f1fb163` after actual
summary/Copilot artifacts and all application checks passed. E05a integrates that main via
`86c0f1a`; final integrated Ruff/Bandit passed and pytest reported
`2427 passed, 2 deselected, 23 warnings in 50.40s`, exit 0. The billing source is unchanged
by integration, locked contracts remain byte-identical, and no mutation experiment was repeated.
Publish E05a as a draft, inspect required remote CI, and merge only after E03 production is
verified. Final release evidence belongs in the respective PR bodies; this is a pre-publication
checkpoint, not a claim that either pending deployment succeeded.

The founder approved commencement of the beta-to-scale and $1M ARR plan in the live session.
The [execution ledger](beta-to-scale-execution.md) preserves the engineering sequence and
separate founder decisions. Revenue and production readiness remain goals, not achieved results.

### E01 — Coherent mobile example (engineering)

- [x] Re-check current main and confirm live identity can inherit Apple fallback metrics.
- [x] Keep live metrics, including an empty set, with live identity; reserve the full fallback for null examples.
- [x] Add the non-AAPL empty-metrics regression plus live and null controls in one test home.
- [x] Retain one mutation proof, full frontend gates and both-theme preview evidence.
- [x] Complete the three review lenses, publish draft #720, inspect exact-head CI and merge.
- [x] Root verified production Vercel deployment `G1Rdtbtf64kNcUD3GAqnVH4Usp5u` succeeded and the canonical homepage returned HTTP 200.

Source `0c92a25`: Node 22.23.2; lint/typecheck/build exit 0; Vitest 96 files / 490 tests passed
in 39.66s. The single mutation restored the mixed-source branch: the ASML fixture rendered
`$394.3B`, causing the intended assertion to fail (1 failed, 2 passed); exact restoration:
3 passed. Root and independent correctness/rules/tests reviews found no actionable issue.
The build used an unavailable local API and retained existing middleware/Sentry-token warnings.
[#720](https://github.com/neilmac91/EarningsNerd/pull/720) merged as `7403076f` after
[CI 34019162195](https://github.com/neilmac91/EarningsNerd/actions/runs/34019162195)
passed; its frontend-only eval skip was expected. The branch preview was inspected at
390 × 844 in both themes: live Apple 10-K, $416.2B / $112.0B / $7.46, no card clipping.
That preview did not alter data or reproduce the sparse fixture. Root subsequently verified
production Vercel deployment `G1Rdtbtf64kNcUD3GAqnVH4Usp5u` succeeded; canonical homepage HTTP 200.
See the [execution ledger](beta-to-scale-execution.md#release-checkpoint--2026-09-06).

### E04 — Bound the summary reader and reject truncated streams (engineering)

- [x] Bound the complete connect/refresh handshake with the existing 120-second timeout.
- [x] Require one valid complete/partial frame; consume a final frame without a newline.
- [x] Stop on terminal frames and avoid automatic replay after any visible preview or chunk.
- [x] Add focused reader regressions in `frontend/tests/unit/summaryStreamResilience.spec.ts`;
  leave recorded SSE/auth contracts unchanged; retain exactly one mutation proof per new invariant.
- [x] Run the full frontend gate, independent review, publish draft #722 and inspect exact-head CI.
- [x] Merge and verify production Vercel deployment `BYywW33Tav6FAoyHa4LZ43h2cCSE` succeeded.

Before E04, the reader returned success at premature EOF and started its timeout only after headers.
E04 keeps the SSE wire format, shared refresh owner, existing one-retry policy and timeout value.
It changes transport handling only; no summary generation, quota, prompt, theme or flag changes.
W3-8b and E03 are independent backend work; serialize task-doc integration when merging.

Source `5eb8e03`: full frontend gate passed (lint/typecheck exit 0; 97 files / 501 tests;
production build exit 0). Initial build rejected the temporary external node_modules symlink;
copying the same installed dependencies inside the worktree resolved it without code or lock changes.
One mutation experiment restored the entire original reader: all 11 new cases failed for the
intended timeout/terminal/replay assertions. Exact restoration: 26 focused tests passed.
Independent correctness/rules/tests review found no actionable issue; backend persistence before
terminal emission was checked in two fresh passes. Locked SSE/auth fixtures are unchanged.
E02 main `5298c77` was merged locally; frontend source/test bytes remain identical to `5eb8e03`.
[#722](https://github.com/neilmac91/EarningsNerd/pull/722) merged as `049cd4f` after
[CI 34025236804](https://github.com/neilmac91/EarningsNerd/actions/runs/34025236804) passed.
Root verified Vercel `BYywW33Tav6FAoyHa4LZ43h2cCSE` succeeded; main CI `34025409826`
succeeded with backend deploy correctly skipped. This is transport handling; no visual change.

## E03 — Short database ownership during generation (2026-09-06)

Approved engineering scope from the beta-to-scale plan. Start: `7d06edc`.
Keep the sole summary orchestrator, filing grounding, quota semantics and locked contracts.
No prompt, flag, schema, capacity or W3-8b classifier change. Root owns publication/deployment.

- [x] Return plain filing/cache snapshots from worker-owned sessions; close progress/save/usage
  sessions in their worker before network, admission or stream waits.
- [x] Close background preflight before draining the same orchestrator; preserve all early returns.
- [x] Release the request session before SSE, preserving current-user entitlement inputs and
  the locked stand-in identity; offload the complete detailed-health DB probe.
- [x] Extend existing lifecycle and health test homes with real pool/ownership evidence.
- [x] Prove each new invariant with exactly one mutation, restoring committed implementation.
- [x] Run pinned Ruff, Bandit, full pytest and unchanged locked contracts; prepare review evidence.
- [x] Independent review, publication, CI/eval inspection and serialized deployment (root).

Runtime evidence: installed FastAPI `routing.py::request_response` closes its request dependency
stack after `await response(...)`; `dependencies/utils.py` defaults yielded dependencies to that
stack. The route's earlier "session is gone" comment is false for streaming on the pinned runtime.

Local implementation evidence (`1dafb69`): Ruff `All checks passed!`; Bandit 0 medium/high
findings; full pytest `2402 passed, 2 deselected, 23 warnings in 44.27s`. Locked SSE,
background, auth, Stripe, expired-trial tests and recorded stream frames are byte-identical.
The lifetime mutation retained the initial read session and failed with `follower retained a DB
connection`; the health mutation moved the query back onto the event loop and failed both probe
cases. Restoring committed bytes produced `45 passed, 17 warnings` across the two gate homes.
One mutation per invariant; no live SEC/provider requests, flags or production operations.

Review correction: the initial route gate used a standalone identity and missed a real User's
lazy subscription lookup, which the first implementation moved onto the event loop. Correction
`a89d90a` copies loaded primitive inputs into frozen snapshots before closing the request session;
only unresolved subscription fields are loaded in a fresh worker-owned session. Loaded billing
state and standalone identities retain their semantics; no persisted User row is required.
The same gate now covers unloaded, already-loaded and expired real subscription state and records
SQL thread identity. Reintroducing the exact event-loop lookup failed with `subscription SQL blocked
the event loop` (1 expected failure); restoration passed 38 focused lifecycle/locked checks.
The original two mutation proofs were not repeated. Root and independent review cleared the correction.

Final integrated source `43eb5c8` includes main `049cd4f` (E01/E02/E04). Ruff clean, Bandit 0
medium/high, full pytest `2412 passed, 2 deselected, 23 warnings in 50.01s`, exit 0. The retained
log also contains the existing post-summary Yahoo-client shutdown logging error. Locked contracts
and stream frames remain unchanged. The pending release at that checkpoint is now verified below.

E03 #723 merged as `4d15b90`; production CI `34026399023` passed, with migrations
`applied=0 skipped=34`, revision `00277-sdn` at 100% traffic and independent healthy DB 9.88 ms.
E05a #724 subsequently merged as `3ca20c6`; production CI `34027376311` passed, migrations
`applied=0 skipped=34`, revision `00278-5rd` at 100% traffic and independent healthy DB 5.66 ms.
Both PR bodies retain full image and health evidence. E05a's first summary evaluation retained
one BABA timeout (artifact `9987326457`); one unchanged full retry passed 52/52 with zero errors
(artifact `9987455360`). Its actual Copilot gate passed 18/18. No baseline or threshold changed.

Precedence correction: the touched single-orchestrator lesson still named Multi-Period Analysis
as the cross-filing insight destination. Its prose now names the labeled Change Report to match
the higher-priority CLAUDE.md rule 2; existing Analysis behaviour is unchanged.

Limits: local SQLite pool evidence is not a PostgreSQL load test. A running synchronous DB
operation cannot be forcibly cancelled; its worker remains responsible for session cleanup.
This change releases the summary route's transaction before streaming; it does not convert all
synchronous route queries to async I/O, alter fleet capacity or change generation admission.

## Wave 3 — GPT-6 Astra session (2026-09)

### E02 — SEC token refill accounting (2026-09-06)

Owner: SEC limiter implementation agent; root owns review and any publication/deployment.
The founder approved commencement of the beta-to-scale plan. This bounded task preserves
existing SEC transport ownership, Retry-After handling and per-process configuration.

- [x] Advance the refill accounting boundary after a completed token wait so the next caller
  cannot reuse elapsed time that already paid for the admitted request.
- [x] Extend the existing SEC limiter test home with one deterministic behavioural gate for
  sustained calls, concurrent callers, delayed wakeup and cancellation; no SEC/network calls.
- [x] Commit the implementation, remove the correction for exactly one mutation proof, restore
  exact bytes, and run the pinned Ruff/Bandit/full pytest gate. Locked contracts stay unchanged.
- [x] Root and an independent reviewer completed correctness, rules and tests lenses;
  prior CI 34019200809 passed with the retained 52-result eval artifact.
- [x] Merge E01's current main without rewriting E02 history; preserve both task sections.
- [x] Root published and merged #721, then verified its serialized backend deployment.
  The implementation agent did not push or deploy.


Source `4a196b7`: 102 exact runtime/dev pins matched (Python 3.11.16). Focused SEC
checks: `14 passed, 1 warning in 0.10s`. Exactly one mutation removed the post-wakeup
timestamp assignment; the sequential gate failed at the intended admission-time assertion
(`1 failed, 1 warning in 0.16s`), and exact restoration passed. Full Ruff and Bandit
exit 0; `2390 passed, 2 deselected, 23 warnings in 64.40s (0:01:04)`, exit 0.
The first full run had two WeasyPrint native-library lookup failures; the installed Homebrew
libraries were exposed via `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`, with no dependency
or source change. EDGAR's test data directory was isolated under `/private/tmp`.
The existing post-summary Yahoo-client shutdown logging error remains in the retained log.
Locked SSE/background/auth/Stripe contracts and the eval baseline have empty main-to-HEAD
diffs. Runtime correction is per-process only; aggregate API/job SEC pacing remains E09.
After merging E01 main at local merge `09758a7`, the full backend gate passed again:
Ruff/Bandit exit 0; `2390 passed, 2 deselected, 23 warnings in 46.41s`, exit 0.
Backend source/test bytes remain identical to `ec5419f`; only E01 frontend/docs and this
status update entered the branch. The original mutation proof therefore remains scoped
to the unchanged guarded source. Root subsequently merged [#721](https://github.com/neilmac91/EarningsNerd/pull/721)
as `5298c77` and verified [production CI 34024814391](https://github.com/neilmac91/EarningsNerd/actions/runs/34024814391),
deploy job `101464120936`: `applied=0 skipped=34`; revision `00276-qhd` at 100%; image
`9bb76917797ccc8473eb6b0aa8722151056c724024e317084007b466d6bdcec9`. Independent detailed
health was healthy (DB 7.89 ms, Redis disabled, SEC closed).

### W3-3 public-source replacement — 2026-09-06

[#718](https://github.com/neilmac91/EarningsNerd/pull/718) merged
`32e10e86893a14a041594eb50a4f18acadd16b85` with 518 reviewed members. The automatic refresh
uses public sources without an FMP key. [Production run 34015542968](https://github.com/neilmac91/EarningsNerd/actions/runs/34015542968),
deploy job `101438839055`, succeeded: `apply_migrations: applied=0 skipped=34`; revision
`earningsnerd-backend-00275-hl7` serves 100% of traffic. Source/image `32e10e8` resolves to
`c0261e7f337fdc5bd9bd6a70ea6449847c7ee3edca8b387642e85b30c957b41b`, matching the latest tag.
Independent detailed health is healthy (DB 7.05 ms, SEC closed, Redis disabled/healthy).
Notable remains absent and its image update was skipped.

[Public refresh 34016016776](https://github.com/neilmac91/EarningsNerd/actions/runs/34016016776),
job `101439794997`, succeeded: `fetched via wikipedia: sp500=503 nasdaq100=102 union=518`;
`validated 518 members generated 2026-09-06 via wikipedia`;
`Membership and metadata are unchanged — nothing to publish.` Artifact `9983905252` is
byte-identical to the deployed JSON (SHA256
`e90cbea47ac11f93599bd0f9248731f7c21ad7a0d5891c6995331f5408accd94`). This proves public
retrieval, validation and artifact retention; the same-day no-change path did not create a PR.

W3-3 automatic publication remains held. Read-only repository metadata reconfirms
`can_approve_pull_request_reviews=false` (default token permission read). The founder must
enable **Allow GitHub Actions to create and approve pull requests** under Settings → Actions →
General before the workflow can create a draft PR when membership or metadata changes.
The workflow already requests contents/pull-requests write; no broader default permission,
PAT, secret or account change is proposed. Keep issue #710 open until actual publication
acceptance is verified. All later founder holds remain; wave 3 is not complete.

The founder requested an FMP-independent constituent filter. Live public retrieval returned
503 S&P 500 rows and 102 Nasdaq-100 rows. The Nasdaq constituents table is on the dedicated
`List_of_NASDAQ-100_companies` page, not the general article used by the old script.
This supersedes the FMP-access prerequisite for this replacement; it does not assert that
FMP entitlement was repaired or change any later founder hold. The existing application
already filters against the committed union; only its maintenance path needs replacement.

- [x] Make the automatic refresh use both public constituent lists without any FMP credential;
  preserve explicit FMP compatibility, normalization, per-index floors, prior-file protection,
  reviewed-commit delivery, and the unchanged 100-day age limit.
- [x] Verify the fetched lists and changes, demonstrate the filter on the supplied 77-row CSV,
  and update owning workflow/docs plus the lesson about checking public alternatives.
Live explicit-public regeneration: both pages HTTP 200; `sp500=503 nasdaq100=102 union=518`.
Added FDXF, FERG, HONA, RDDT, SPCX and VMRK; removed AVB, EA and EQR. Existing members'
index labels are unchanged. Names track the upstream tables (MSCI, ORLY punctuation, and
ResMed's upstream trailing `|`); the application membership comparison uses tickers only.
The supplied CSV demonstration retains 52 of 77 records using current membership as of
2026-09-06, not historical membership on each earnings date. The initial live command was
rejected by automatic approval review based on old auto/FMP precedence; after inspecting
changed source, explicit `--source wikipedia` was approved and produced the data above.

- [x] Run meaningful offline regression/mutation checks and the full backend gate; review
  correctness, rules and tests independently before readiness.
Local release gate on source/data `16d8c430`: all 102 runtime/dev pins matched; Ruff and Bandit
exit 0; `2386 passed, 2 deselected, 23 warnings in 48.67s`, exit 0. The first collection attempt
failed on an unwritable default `~/.edgar`; supported temporary EDGAR cache paths resolved it
without source changes, and the initial failed log is retained separately. Actual old-Nasdaq-URL
mutation failed the intended parser assertion (`1 failed in 0.49s`); exact restoration passed
(`1 passed in 0.55s`). Four locked contracts and baseline are unchanged; 21 local links resolve.
The subsequent source-identical documentation update clarifies same-day no-change runs.

Automated review of initial PR #718 head `eaad3665` identified a new unconditional FDXF/HONA
health-test requirement that would block legitimate future removals. Fresh independent source
and tests reviewers could not refute it; root's separate 516-member fixture also failed only that
new requirement. Correction `e6291cf2` removes those two lines and retains the parser regression
that checks preservation when the public source supplies the tickers. Production code and data
are unchanged. Corrected local gate: Ruff/Bandit exit 0; `2386 passed, 2 deselected, 23 warnings
in 46.77s`, exit 0. An existing post-summary Yahoo-client shutdown logging error is retained.
The old-URL mutation proof remains scoped to unchanged parser source/test bytes. Initial CI
34014268319 (52 complete summary results) and Copilot 34014614488 (18 accepted results) passed;
these remain historical candidate results. Final head `493d4978` passed
[CI 34014981345](https://github.com/neilmac91/EarningsNerd/actions/runs/34014981345):
`2386 passed, 2 deselected, 23 warnings in 75.41s (0:01:15)`; performance
`2 passed, 18 warnings in 15.20s`; frontend 487 passed; browser 21 passed (19.1s),
3 existing skips; PostgreSQL applied/skipped `34/0`, `0/34`, `34/0`.
Summary artifact `9983680685` has all 52 results, zero errors/vetoes, matching source/golden
hashes and typed guards; regression `PASS — no hard regressions (1 warning(s)).`, advisory mean
untraceable figures 2.0192. Final [Copilot 34015323793](https://github.com/neilmac91/EarningsNerd/actions/runs/34015323793),
artifact `9983740345`, has 18 passing results, zero errors/vetoes; six source bundles and
scratch-database hashes verified. Neither gate is the held strong-judge readout.
Three manual lenses cleared the correction; the final bot review found no additional issues.

- [x] Publish the draft PR, inspect final required CI/reviews, merge #718 and verify its backend
  deployment, migration tail, image, revision, traffic and independent health as recorded above.
- [x] Dispatch public refresh 34016016776; verify counts, same-day no-change outcome and the
  retained artifact against the deployed file.
- [ ] Founder enables the named Actions setting; engineering verifies a later changed-data or
  metadata draft-PR publication before closing #710. Never manufacture a diff or use a PAT.

### Current checkpoint — 2026-09-06

The current backend is #718, verified above. The following #716 checkpoint and gate evidence
remain the accepted W3-6 history; they are not the latest serving revision.

W3-0, W3-1, W3-2, W3-4, W3-5 and W3-6 are complete with the recorded verification below.
W3-6 [#716](https://github.com/neilmac91/EarningsNerd/pull/716) merged
`a7bc78be791d188f4f36d399dd117ee4282a84bd`; its source gates and independent reviews are
verified. [Production run 34010252813](https://github.com/neilmac91/EarningsNerd/actions/runs/34010252813),
deploy job 101424963044, succeeded with `applied=0 skipped=34`; revision
`earningsnerd-backend-00274-fgq` serves 100% of traffic. Image digest
`b5ab6f9067f5047df5c4adb4b4071ca9a7315d5e97527d5a9911c291583b9f58` matches source `a7bc78be`.
Independent `/health/detailed` is healthy: DB 6.41 ms, SEC closed, Redis disabled/healthy.
The Notable job was not found and its update was skipped; provisioning/activation remains held.
This is not completion of wave 3.

- [x] Final [CI 34009654771](https://github.com/neilmac91/EarningsNerd/actions/runs/34009654771):
  backend 2386 passed, 2 deselected, 23 warnings (70.51s); performance 2 passed,
  18 warnings (15.03s); frontend 487 passed; browser 21 passed (17.1s), 3 existing skips.
  PostgreSQL migration passes: applied/skipped `34/0`, `0/34`, `34/0`.
- [x] Summary artifact `9982136005`: 52 complete results, zero errors/vetoes; typed guards
  and source hashes preserved. Mean untraceable figures 2.0769 remains advisory.
  [Copilot 34010025095](https://github.com/neilmac91/EarningsNerd/actions/runs/34010025095),
  artifact `9982206256`: 18 passing results, zero errors/vetoes; six source bundles and
  database hashes verified. Neither result is the held strong-judge readout.
- [x] W3-5's late DevOps dependency-pinning prose qualification is included in merged #716;
  application/lint-test requirements are locked, ancillary installers are not uniformly pinned.
- [x] #716 deployment, actual migration tail, serving revision/traffic and independent public
  health verified as recorded above.
- [ ] Separate frontend audit follow-up: the current GitHub open-alert readout retains
  [Dependabot #270](https://github.com/neilmac91/EarningsNerd/security/dependabot/270),
  high-severity `extract-zip` in `frontend/package-lock.json`, development
  scope. No backend alert is open and the runtime-lock pip-audit is clean; this does not
  establish repository-wide audit clearance or change the advisory policy. No dependency
  change for this unrelated finding is included in W3-6.

W3-3's earlier FMP run 34000192154 failed with HTTP 402 at the S&P 500 route before reaching
Nasdaq; issue #710 remains open. The founder's public-source replacement request supersedes
that account prerequisite for this work. #718's public sources, reviewed data and deployment
are verified above; automated PR publication is tracked separately. This does not repair FMP
access or clear any later founder-held operation.

### W3-6 implementation history — PyJWT migration

The following checklists preserve pre-merge source and correction checkpoints, including their
then-current draft/release status. The current status is the checkpoint above.


Owner: plan_correctness. Root owns publication, independent reviews, CI, merge and deployment.
Entry satisfied: #715 merged `56d33f0435723030b072017ba47e2d3e32697132`; production
[34006685337](https://github.com/neilmac91/EarningsNerd/actions/runs/34006685337), deploy job
101415369329, succeeded with `applied=0 skipped=34`, revision `00273-r65` at 100%.
Image digest `d3c86ac5d708dd272e0a7619d3e3eff2deb83428f16705f2beadd662ef92548b`;
independent detailed health healthy (DB 15.29 ms, SEC closed). Notable job was not found and
its update was skipped; its founder provisioning/activation hold remains.

PR #716 remains draft for a further independently confirmed waitlist clock-skew correction.
The completed Google/probe correction below is retained as superseded release evidence.

- [x] Add configured leeway at the remaining waitlist decode; audit all five production
  decodes without changing algorithms, claim requirements, audiences, issuers or token type.
- [x] Add one offline test through the actual waitlist token issuer and verification route:
  +5-second issuer skew persists verification; +11 seconds returns HTTP 400 and leaves a
  distinct signup unverified in isolated SQLite.
- [x] Commit source, remove only waitlist leeway for one intended failure, restore exact bytes,
  then run the full coherent 102-pin Ruff/Bandit/pytest gate. Preserve lock and existing tests.

Final waitlist source `0626f0ab`: all five production JWT decodes use configured leeway;
fixed algorithms and existing audience/issuer/type/subject/required-claim checks are unchanged.
The real waitlist issuer runs five seconds ahead of a frozen verifier; the actual route persists
`email_verified=True` in isolated SQLite. An eleven-second token returns HTTP 400 and its
separate signup remains unverified. Focused: 1 passed, 16 warnings (3.57s). Removing only
waitlist leeway fails the intended positive route call (1 failed, 16 warnings in 3.47s);
exact restoration passes (1 passed, 16 warnings in 2.84s), router SHA256
`e2cbff30387f00e4f17b2c4c0dc3b5eed6b9bce71913477378ebefe170a235da`.
Full coherent gate: 102 exact pins, Ruff/Bandit exit 0;
2386 passed, 2 deselected, 23 warnings (51.09s), exit 0.
Lock, the two approved existing-test edits, Google regression and original AST gate remain
unchanged; their retained audit/mutation evidence is scoped to those unchanged files.
Four locked contracts, sole baseline, 59 archives and historical findings remain byte-identical;
18 local owning-document links resolve. No live OAuth or network operation was performed.
Root owns final review and release; the earlier correction evidence below is historical.

PR #716 is draft again for two independently confirmed review corrections; prior source
and gate evidence below remains historical and is superseded for release by this correction.

- [x] Replace the stale dynamic dependency probe tuple with `PyJWT` / `jwt`; verify only
  the extracted `check_dependencies` function offline, never the full deployment diagnostic.
- [x] Give Google token validation the configured clock-skew leeway. The current 10-second
  setting also applies to its `exp`/`nbf` checks; document that expanded tolerance explicitly.
- [x] Add one deterministic offline Google RSA/JWK test: near-future `iat` within leeway
  succeeds and beyond leeway fails. Keep the two prior approved existing-test edits unchanged.
- [x] Commit source; remove only Google's leeway to prove the intended regression assertion,
  restore exactly and run one full coherent 102-pin backend gate. Lock/audit evidence is unchanged.

Corrected source `c5d1f3d3`: the offline AST-extracted dependency probe passes with PyJWT;
no full diagnostic or live OAuth was run. Real local RSA/JWK with frozen validation time
passes the +5-second `iat` and rejects +11 seconds at configured leeway 10 seconds.
Focused test: 1 passed, 1 warning (0.45s). Removing only Google's configured leeway fails
that intended near-future acceptance call (1 failed, 1 warning in 0.21s); exact restoration
passes (1 passed, 1 warning in 0.16s), source SHA256
`a5a5feaa374305fa37b4cd3b57e2aa6ce0851617f207c43357d77bd8623d45e8`.
The corrected full coherent gate verifies 102 exact pins; Ruff/Bandit exit 0;
2385 passed, 2 deselected, 23 warnings (56.16s), exit 0. Existing post-summary shutdown
logging error remains recorded. Lock, the two approved existing-test edits and original AST
gate are byte-identical to the previous candidate, so unchanged audit and earlier AST proof
remain scoped evidence. All locked contracts, baseline, 59 current archives and historical
review finding bodies remain exact; 18 local owning-document links resolve.
Root owns final review, CI and publication; previous release evidence below is historical.

- [x] Migrate only the four JWT production modules, preserving fixed algorithms, audiences,
  issuers, nonce binding, string subjects and configured clock-skew leeway. Disclose that
  PyJWT enforces the existing required-claim lists and future `iat` validation.
- [x] Apply the two founder-preapproved non-locked test edits: library/leeway in
  `test_security_hardening_week7.py`, selected-JWK conversion in `test_apple_signin.py`.
  Keep all assertions and the four locked contracts unchanged; no live OAuth.
- [x] Resolve the observed compiler platform delta before accepting the lock: macOS ARM
  SQLAlchemy metadata omits greenlet, although existing Linux/CI lock includes 3.5.1. Preserve
  that existing runtime pin through an explicit input, without enabling async database behavior.
  Retain the first compiler output and re-check that only the four retired packages disappear.
- [x] Replace the dependency input with `PyJWT[crypto]>=2.10,<3`; compile using documented
  Python 3.11 command and pip-tools 7.6.1, preserving unrelated pins. Install a fresh coherent
  runtime outside Documents; prove retired jose/ecdsa/rsa/pyasn1 distributions absent.
- [x] Add the one planned AST/dependency gate; inject one actual jose import, demonstrate its
  intended assertion failure, restore exact committed bytes and retain both tails.
- [x] Run full Ruff/Bandit/pytest and actual pip-audit; preserve advisory posture and report
  remaining findings. Prove locked contracts, sole baseline and historical archives unchanged.
- [x] Include the separately confirmed late W3-5 prose correction: qualify the DevOps brief
  dependency-pinning claim; preserve its no-new-unpinned-installs directive and change no tools/workflows.
- [x] Synchronize active handover/todo checkpoints with observed evidence; retain dated
  historical findings and original definition of done. Commit final results, stop before push.

Local source `25548116`: Python 3.11.16 / PyJWT 2.13.0, 102 exact runtime/dev pins,
retired jose/ecdsa/rsa/pyasn1 distributions and modules absent. Documented pip-compile command
retained every unrelated version; explicit greenlet 3.5.1 input preserves the prior Linux pin.
The first platform-dropping output is retained and excluded. The supported compiler header
override records actual arguments after a Click default-rendering artifact; no resolver flag
or compiled version was hand-edited.

Focused existing auth/refresh/Apple/leeway and the new gate: 44 passed, 17 warnings (28.74s).
The sole new actual-jose-import mutant failed its intended AST assertion (1 failed in 0.58s),
then exact restoration passed (1 passed in 0.51s). Full Ruff/Bandit exit 0;
2384 passed, 2 deselected, 23 warnings (67.59s), exit 0. The existing post-summary shutdown
logging error is retained. Actual runtime-lock pip-audit reports 99 dependencies, no known
vulnerabilities, exit 0; audit policy stays advisory and other ecosystems are not covered.
All 59 current archives (including the original 52), original handover/ledger, dated review
finding text, four locked contracts and sole baseline are byte-identical; 18 local owning-doc
links resolve. The private initial archive-count assumption (52 total versus actual 59) was
corrected to compare complete inventories and retained as excluded checker evidence.

- [ ] Root: final independent review, draft publication, actual required CI, merge and verified
  deployment. Local source/evidence completion does not claim a shipped W3-6 change.

### W3-5 preparation history — verified #715

W3-5 is complete with the deployment evidence above. Final CI 34006454576 passed backend
2383 tests, performance 2, frontend 487 and browser 21 (3 existing skips), plus PostgreSQL
triple application. Copilot run 34006471949 artifact 9981128325 contains 18 passing results,
zero errors/vetoes and verified six-source/database hashes. The checkboxes and draft-status
statements below preserve their pre-merge source checkpoints; they are not current holds.


Latest review confirmed two bounded gaps after independent refutation: companyfacts transport
made the EFTS-only exception wording incomplete, and case-insensitive Render phrases matched
benign rendering text. Earlier CI and mutation evidence remains scoped history.

- [x] Correct active SEC guidance and literal-gate descriptions without changing runtime or
  executable SEC checks; distinguish limiter-only paths, local parsing and the manual diagnostic.
- [x] Bound the three Render platform phrases and assert benign rendering text in the same gate.
- [x] Removed-boundary mutant failed the intended `section rendering` assertion: `1 failed
  in 0.03s`; exact restoration passed (`1 passed in 0.04s`).
- [x] Source `37b3e04e`: coherent Python 3.11.16, 105 exact pins, Ruff/Bandit exit 0;
  `2383 passed, 2 deselected, 23 warnings in 54.17s`, exit 0. SEC-gate executable AST is
  unchanged after excluding its description/error messages; application runtime is unchanged.
  Final prose preserves existing transport ownership even for paced requests.
  All 80 brief source paths and 152 local links resolve (31 brief links); original archives,
  §7/ledger, locked contracts and sole baseline remain exact.
- [x] Independent correctness and tests/rules reviews cleared the final delta and actual
  proof/full-gate evidence; root verified the documentation-only result checkpoint.
- [ ] Root: inspect corrected actual CI, merge and verify deployment.

The final table audit corrected app-chrome placement to files directly under `frontend/components/`
and distinguished seven configured job targets from verified provisioning. Root and two reviewers
checked the entire stack table against source. Conflicting CLAUDE/deployment prose now preserves
the required pregenerate update and conditional updates for the other six jobs.

Final prose review qualified existing stateful discovery GETs in the API brief after two
independent refutation attempts confirmed the contradiction. Runtime and gated source are unchanged.
The optional `frontend/src` matcher suggestion is outside the specified token set; current engineering
briefs contain no such path, and the frozen legacy set is preserved.

A further review confirmed lowercase obsolete recipes bypassed the case-sensitive pattern.
Two independent attempts to disprove the finding confirmed the gap. The full
case-insensitive scan requires no frozen-allowlist expansion. PR #715 remains draft.

- [x] Add `re.IGNORECASE` to the existing obsolete-stack pattern only.
- [x] Actual lowercase `alembic upgrade head` insertion failed the intended engineering
  assertion (`1 failed in 0.06s`); exact restoration passed (`1 passed in 0.04s`).
- [x] Source `98d0fb4d`: coherent Python 3.11.16, 105 exact pins, Ruff/Bandit exit 0;
  `2383 passed, 2 deselected, 23 warnings in 54.83s`, exit 0. Prior proofs and CI remain
  scoped historical evidence. All 148 local links resolve; original archives/§7/ledger,
  locked contracts and sole baseline are preserved.
- [x] Independent correctness and tests/rules reviews cleared the case delta and actual
  mutation/full-gate evidence; root verified the final documentation-only result update.
- [ ] Root: inspect corrected actual CI before merge and deployment verification.

PR #715 is draft during a bounded review correction. Two independent refutations confirmed
that the original obsolete-stack gate did not require the seven named engineering files,
and that the SEC prose overstated circuit-breaker coverage. Earlier CI evidence is retained.

- [x] Add explicit required-file presence to the existing gate (a review-added invariant),
  keeping its obsolete-stack and frozen legacy checks unchanged.
- [x] Correct the backend brief and conflicting active CLAUDE/architecture prose: existing
  EFTS uses the shared limiter/backoff without the breaker; new bypasses remain prohibited.
- [x] Actual backend-brief deletion failed the intended required-file assertion: `1 failed in
  0.03s`; exact restoration passed (`1 passed in 0.03s`). The initial old-runtime attempt
  timed out before pytest output, restored in `finally`, and is excluded from mutation credit.
- [x] Corrected source `609c84f9`: isolated Python 3.11.16, 105 exact runtime/dev pins;
  Ruff/Bandit exit 0; `2383 passed, 2 deselected, 23 warnings in 55.03s`, exit 0.
  Documentation checks: 79 brief source paths, 31 brief links, 148 expanded local links
  with none broken. Locked contracts, sole baseline, original §7/ledger and 52 archives preserved.
  Original obsolete-stack mutation evidence still applies to its unchanged assertion branch.
- [x] Independent correctness and tests/rules reviews cleared the corrected source and actual
  mutation/full-gate evidence; root verified the final documentation-only result update.

W3-2 (#709) is deployed and its effective pins are verified. This branch is based on
[#713](https://github.com/neilmac91/EarningsNerd/pull/713) merge `99b506d7`. W3-4 deployment and
corrected green/red acceptance are verified below. Root controls publication and serialized deployment.
At this W3-5 checkpoint, FMP HTTP 402 / issue #710 was treated as a founder entitlement
prerequisite and did not block the independent work. The later public-source replacement
supersedes that FMP prerequisite; other founder boundaries remain unchanged.

- [x] Refresh all seven engineering briefs and README status using actual source pointers.
- [x] Add one recursive obsolete-stack gate with a frozen, shrinking non-engineering allowlist.
- [x] Prove the gate with one intended Firebase assertion failure and exact restoration.
- [x] Three independent lenses cleared the W3-5 source; unchanged source bytes retain that evidence.
- [x] Prior #711 union gate at `3daf0c4c`: 105 exact runtime/dev pins, Ruff/Bandit exit 0;
  `2383 passed, 2 deselected, 72 warnings in 52.11s`.
- [x] Corrected timeout-safe #711 union at `d3986771`: 105 exact runtime/dev pins,
  Ruff/Bandit exit 0; `2383 passed, 2 deselected, 72 warnings in 48.26s`.
- [x] W3-4 verification is complete; root authorized W3-5 publication.
- [x] Root published draft #715; its prior CI evidence is retained.
- [ ] Root: inspect corrected actual CI, merge and verify W3-5 backend deployment.
  No corrected CI, merge or deployment is claimed at this source checkpoint.

Initial gate: `2355 passed, 2 deselected, 72 warnings in 52.52s`; the Firebase mutant failed its
intended assertion and restored with `1 passed in 0.03s`. Previous W3-2 union at `29f1dc61`:
105 exact pins, Ruff/Bandit clean; `2382 passed, 2 deselected, 72 warnings in 53.66s`.
These earlier gates are historical evidence. The review correction above adds required-file
presence and qualifies SEC prose; the original obsolete-stack assertion branch, all four locked
contracts and the sole baseline remain unchanged. Source checks resolve
79 paths and 31 Markdown links/anchors after the SEC source-pointer correction. The new base adds W3-4's scheduled workflow gate case.

The chief engineer reviewed #705 and the standalone writeup on 2026-09-05: sound, with eleven
discrepancies (none invalidating the handover). The ordered plan, founder prerequisites and the
per-item gates live in [`handover-wave3-2026-09.md`](handover-wave3-2026-09.md); non-Claude
operating directives live in the root `AGENTS.md`. Work items (engineering unless marked founder):

- [x] W3-0 Additional #705 tail verification: 13 task docs, 43 links valid, 52 earlier archives and original §7/ledger preserved. Final manual-reviewed `34350292` tree equals `eddcfbb7`; only the GitHub bot stopped at `c660e9a1`.
- [x] W3-0 documentation correction: #707 merged `a7ad8f85` after three reviews and link/preservation checks; #706 history, agent count, refresh cause, environment assumptions and dependency evidence corrected.
- [x] W3-1 `ops.yml` exposes revision and pregenerate flags; #708 merged `6414e5bd`, actual run 33996220468 verified revision 00270-4k6 at 100% and matched #704 image/config. Service calendar=true differs from its false default; founder approved preserving this override.
- [x] W3-2 Pin every prod guard flag explicitly in `ci.yml` (service + pregenerate job) with a bidirectional gate; pin `AI_FALLBACK_*` empty in all eval workflows with gates and pin-tool refusal; structural fail-loud gate for scheduled workflows
- [ ] W3-3 Public universe refresh: #718 source/data and deployment are verified; the public
  lists match current SPY/QQQ equity subsets. Automatic draft-PR publication remains held on
  founder-owned Actions policy and actual publication evidence; see the top checkpoint.
  Original FMP HTTP 402 run 34000192154 / issue #710 retained; no credential or age-limit change.
- [x] W3-4 Daily production smoke: #711 deployed; #713 corrected launcher targeting; actual green 34002892976 and deliberate red 34003003306 verified with separate failure reporter and resolved issues (details below).
- [x] W3-5 Rewrite the seven engineering agent files to the real stack; gate and #715 deployment verified above
- [x] W3-6 PyJWT #716 merged with verified source/CI, unchanged locked auth contract and verified production deployment (current checkpoint above).
- [ ] W3-7 **(founder)** first strong-judge readout → engineering reports the wrong-snap rate, pauses for the arm decision → arm `AI_EVIDENCE_SNAP` + listed re-pin → **(founder)** drain
- [ ] W3-8 Golden breadth (REIT/utility/insurer/small-cap, BRK.B) with its own re-pin; then the 6-K pre-classifier + 6-K scorer + goldens
- [ ] W3-9 Historical reconciliation-flag audit/repair script (dry-run default) → **(founder)** executes
- [ ] W3-10 **(founder)** Notable job + seed + one full week → flag PR; **(founder)** Analysis Vercel value + warm-up → `vercel.json` PR
- [ ] D8 **(founder OK)** delete the two stale remote branches with no PR

## W3-2 implementation — production parity (verified #709)

Owner: AI engineer (plan_gates). Root owns GitHub publication, actual CI, merge and deployment.
Entry evidence: W3-1 run 33996220468/job 101387131600; source image #704/123f99e.
Founder correction: preserve service `CALENDAR_INDEX_FILTER_ENABLED=true` as an intentional
production override, pregenerate=false, Settings default=false. Both fallback fields must be
empty for new pins. Founder provided `FMP_API_KEY` in the GitHub `Production` environment;
bind the existing refresh job to that environment without reading or changing the secret.
Routine required CI evaluations are authorized; extra sweeps and strong-judge dispatch remain held.

- [x] Implement explicit service/job pins and three gate families: visibility/defaults/parity,
  measured fallback provenance and pin refusal, scheduled failure notification structure.
- [x] Preserve serving-revision/traffic and distinct job observation through executable offline
  ops renderer tests; extend existing eval tests without adding duplicate rules.
- [x] Wire refresh to `Production`; correct owning RUNBOOK/config/deployment/dark-surface/handover
  docs, including the founder-approved calendar exception and current entry evidence.
  Documentation source, local verification and production deployment are complete.
- [x] Commit source; run one intended mutation proof per rule, restore exactly, run focused
  workflow gates and exact-runtime full backend gate. Locked tests and sole baseline stay unchanged.
  Local gate at `6a0e7174`: 105 exact pins, Ruff/Bandit clean, 2381 passed, 2 deselected,
  72 warnings (52.19s); 11 intended mutation proofs restored. Initial cache-path collection
  failures are retained and excluded; their four corrected reruns fail the intended assertions.
- [x] Root: independent reviews, publish draft, inspect actual serialized CI evaluations, merge,
  verify deployment and effective pins. #709 merged `ff8fe0f5`; [production run 33999866705](https://github.com/neilmac91/EarningsNerd/actions/runs/33999866705),
  deploy job 101396935030, succeeded with `applied=0 skipped=34`, revision `00271-8nk` at 100%.
  Image digest `c1d3789aa8fd0186c31d56971510037ccc71b1863946bffdfba679989402a4d2`;
  public detailed health healthy (DB 6.09 ms, SEC circuit closed).
  [Ops run 34000144716](https://github.com/neilmac91/EarningsNerd/actions/runs/34000144716) verified all seven service/job pins,
  calendar service=true/job=false, both fallback fields absent with verified empty defaults,
  and matching pregenerate image `ff8fe0f`. Refresh execution belongs to W3-3; judged readout remains held.

## W3-4 implementation — production smoke (verified #711 / #713)

Owner: plan_correctness; root owns publication, merge, deployment and live dispatch coordination.
W3-2 merged `ff8fe0f5` and its deployment/effective settings are verified above; the publication
prerequisite is satisfied. The scheduled
workflow reads a cached public filing as an unauthenticated visitor and never clicks generation
or Copilot. The existing health policy accepts degraded serving status and rejects unhealthy.

- [x] Add the daily/manual smoke workflow with safely bound filing input, bounded browser install,
  retained API/browser artifacts and final create-or-comment failure issue.
- [x] Extend the existing Node lockstep gate across all workflows while preserving its original
  nonempty `ci.yml` assertion; add prod-smoke to the existing scheduled-failure tuple.
  Review found the first extension lost CI-specific presence: both independent refuters confirmed;
  correction and one missing-CI-pins proof supplement the retained wrong-new-workflow-pin proof.
- [x] Restore exact mutation bytes; run full backend and frontend gates on combined `b636780a`:
  105 exact runtime/dev pins; Ruff/Bandit exit 0; 2382 passed, 2 deselected, 72 warnings (80.15s).
  Frontend lint/TypeScript exit 0, 95 files/487 tests passed (49.74s), production build passed.
  The CI-presence mutant failed its intended assertion; exact restoration passed all three Node checks.
- [x] Three independent reviews cleared the pre-timeout-correction source; its ancestry/docs
  updates preserved the then-tested workflow and test bytes. Fresh timeout-delta correctness,
  rules and tests/gates reviews also cleared the corrected source.
- [x] Correct confirmed #711 timeout reporting: move issue creation/comment to a bounded
  dependent job with `always()` and a non-success worker result; extend the existing parametrized
  gate, prove the condition with one intended mutation, restore and run the full backend gate.
  Artifact upload in the 15-minute worker remains best effort after timeout.
  Source `481dc168`: 105 exact pins; Ruff/Bandit exit 0; full backend 2382 passed,
  2 deselected, 72 warnings (52.01s), exit 0. Focused checks 52 passed (3.74s); Node gate
  3 passed (830ms). Exactly one result-condition mutant failed the intended assertion
  (1 failed, 1 passed in 0.06s); exact restoration passed both parametrized cases (0.04s).
  Existing shutdown logging warning is retained. Frontend source/full-gate proof unchanged.
- [x] #711 merged `9ab159b7`; [production run 34001741244](https://github.com/neilmac91/EarningsNerd/actions/runs/34001741244)
  succeeded, migrations `applied=0 skipped=34`, revision `00272-klf` serving 100%.
  Independent detailed health was healthy (DB 6.87 ms, SEC circuit closed).
- [x] Corrected the existing smoke locator in [#713](https://github.com/neilmac91/EarningsNerd/pull/713),
  merged `99b506d7`, after [initial run 34002187563](https://github.com/neilmac91/EarningsNerd/actions/runs/34002187563)
  passed the summary check but matched both the callout CTA and dialog launcher. The correction
  targets the exact accessible name plus dialog semantics and preserves both visibility assertions
  and timeouts. [Issue #712](https://github.com/neilmac91/EarningsNerd/issues/712) records the genuine
  failure and was resolved with the correction and passing evidence. This semantic smoke does not
  establish deployed commit identity.
  [#713 main CI 34002890791](https://github.com/neilmac91/EarningsNerd/actions/runs/34002890791)
  passed; actual backend scope reported `No backend changes - skipping deploy.`
- [x] Corrected default [green run 34002892976](https://github.com/neilmac91/EarningsNerd/actions/runs/34002892976)
  on `/filing/3`: `1 passed (5.1s)`, artifact `9980026833`, API healthy (DB 6.18 ms).
- [x] Deliberate [red run 34003003306](https://github.com/neilmac91/EarningsNerd/actions/runs/34003003306)
  on `/filing/does-not-exist` failed summary visibility; artifact `9980065113` was retained.
  Separate reporter job `101405277325` created [issue #714](https://github.com/neilmac91/EarningsNerd/issues/714),
  which root closed after inspecting the actual issue and artifacts. Both acceptance outcomes and
  failure reporting are verified; the genuine initial failure remains part of the evidence.

## WS-10 verified engineering handover — final synchronization

Documentation-stage checkboxes below record the 2026-09-05 pre-merge source checkpoint
`177f9ff4`. [PR #705](https://github.com/neilmac91/EarningsNerd/pull/705) is authoritative for
subsequent review, CI and merge outcomes; unchecked items do not assert those later results failed.

Verified backend checkpoint: #704 (`123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`).
Its deployment is healthy. Original handover §7 is not complete: the first actual strong-judge
readout, dependent activation and founder production operations still need evidence.

- [x] Knowledge Curator (plan_rules): synchronize the active handover, ledger, briefs, todo,
  dark-surface and launch checklists with observed merges, gates and deployments. Attribute
  independently merged #673 separately; preserve accepted D1–D8 and every outstanding boundary.
- [x] Knowledge Curator: archive finished implementation plans and the exact earlier ledger;
  preserve existing archives and the original definition of done verbatim. Keep mixed-stage
  readout, broader coverage and founder residuals active rather than marking them completed.
- [x] Chief engineer: verify archive bytes, local links/anchors, exact commit references and
  documentation-only scope. Root, plan_correctness and plan_gates independently review the
  final documentation; serious findings require two refuters before correction. *Done in #705 (`eddcfbb7`).*
- [x] Chief engineer: inspect required CI, merge with the freshly read head, and publish a
  standalone engineering handover with the evidence and a single founder action list. Pause
  the hourly check-in when no authorized work remains in flight. *Done in #705 (`eddcfbb7`); the
  handover was reviewed 2026-09-05 and its findings are tracked in wave 3 above.*

This stage changes only task documentation. The owning evaluation RUNBOOK was corrected in
#704. No backend path, feature flag, threshold, baseline, job, secret or production data changes.

## Prospective reporting-date wiring — archived

- [x] #704 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws7-period-wiring-2026-09.md).

## Filing-scoped Copilot — archived

- [x] #703 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-copilot-2026-09.md).

## Filing-only input and recovery hygiene — archived

- [x] #702 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-hygiene-2026-09.md).

Source: `docs/ENGINEERING_AUDIT_2026-09.md` (synthesis) + `docs/audit-2026-09/` (six workstream
appendices with file:line evidence). Lens: invite-only beta, product quality wins ties.
Each phase is one or a few reviewed PRs. Engineering merges are authorized for the chief
engineer; items marked **(founder)** still require the founder.

## Wave 2 execution — 2026-09-05

Owner: chief engineer (Codex); founder has authorized engineering merges and deployments.
Accepted D1–D8 remain in force. Existing unchecked decision rows below are historical tracking,
not requests to revisit accepted decisions. Founder-only actions remain founder-only.

Verified backend/code checkpoint #704: `123f99eac2b758f0dc7e2b9fcbc2a0a6bbf8146c`.
Deployment 33988401306: applied=0 skipped=34, revision `00270-4k6` at 100%, healthy.
The [ledger](wave2-ledger-2026-09.md) records all accepted code/actual gates; last verified frontend
remains #697. #673 was externally merged and preserved, not authored or merged by this task.
#684 closed as integrated by #701; #685 merged; #686 split/closed by #694/#695.
No usable strong-judge credential or actual first readout was available, so D5 remains held.
The unavailable Claude Workflow runtime was replaced by three independent Codex review lenses
and two refuters per serious finding; absent verifier output never counted as clearance.

- [x] Chief engineer: execution plan merged #689 (`47d65a2c`), reviewed and CI green.
- [x] Backend Developer + Database Specialist: WS-7 steps 1–2 merged #690 (`99e91ba7`); graduate statement
  financials default, prepare SIC backfill instructions, implement distinctive job heartbeat
  storage with a new lock-safe migration, instrument every job, report coverage/stubs/age/last success.
- [x] Chief engineer: backend deployments through #704 serialized and independently verified; retain this prerequisite for every future backend merge.
- [ ] Founder: trigger SIC backfill; supply observed completion before declaring SIC data backfilled.
- [x] Backend Developer: WS-7 remaining code steps merged #697 (`c925cfa8`): 10-Q periods/unit assertions and
  reconciliation labels; amendments/supersession/Change Report; persisted XBRL first and missing
  balance-sheet facts; FPI + 10-Q pregeneration and universe Company seeding preparation.
- [x] AI Engineer: parity and sole honest pin merged #698 (`d696f408`), deployed with healthy detailed health.
  Statement env, JPM G5 components, production streaming and safe baseline provenance are verified.
- [x] AI Engineer: measurement code merged #700 (`80314db6`): WARN figure-trace dimension,
  persisted audit counters and bounded weekly strong-judge workflow/readout handoff; deployed healthy.
- [ ] AI Engineer / founder credential boundary: obtain the first actual weekly strong-judge readout.
  An unavailable artifact and routine judge-off regression runs do not satisfy this prerequisite.
- [x] AI Engineer: resilience #701 integrated #684, optional real fallback, bounded retries, actual usage/model telemetry and missing-grounding protection; full backend and complete actual eval gates passed.
- [x] AI Engineer: #702 filing-only AST/context hygiene; #703 scoped/native-currency Copilot with six verified accessions/five issuers and three actual draws each. Latest #704 18/18 accepted; uncited-answer coverage remains advisory.
- [ ] Chief engineer: arm AI_EVIDENCE_SNAP in ci.yml only after first judged readout; founder triggers drain.
- [x] Frontend Developer: sitemap freshness + /terms + SEO correction merged #693 (`157e6a39`).
- [x] Frontend Developer: locate boundary and regression/mutation proof merged #691 (`a2c7fa70`).
- [x] Frontend Developer: #686 split/closed through #694 (`6e169de8`) and #695 (`919aa862`);
  full lint/typecheck/vitest/build and Playwright with no backend for each candidate.
- [x] Security/Backend Developer: #685 compatibility/backend gate and verified deployment (`5cb23b8a`).
- [x] Backend + Frontend Developers: WS-9 preparation merged #692 (`60d8015e`); activation remains held;
  Analysis requires confirmed Vercel value + warmed companyfacts; Notable requires founder-created
  job, seed and a week of review before repository flag flip. Calendar and Insiders stay off.
- [x] Owning PRs corrected migration/provider/report/eval/config docs and script placement; FPI plans archived with residuals. Final active-task synchronization and its review/CI/merge are tracked at the top.
- [ ] Founder: pregeneration off-peak only after WS-7 prerequisites; console/secrets/licence actions
  remain as listed in handover §6, with exact instructions in the relevant PR.
- [ ] Chief engineer: finish final docs review/CI/merge and standalone handover, then pause the hourly quiet check-in when no authorized work remains in flight. Report original §7 as incomplete; do not wait for founder-held operations to claim engineering handover.

Every implementation PR is draft immediately, uses a worktree under `.claude/worktrees/`,
and includes exact gate tails and mutation proofs. Locked contracts, migration allow-lists,
and AI baseline protections remain unchanged unless explicitly permitted by the mandate.

## Resilience and complete-report gate — archived

- [x] #701 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-resilience-2026-09.md).

## Phase 0 — this PR: make releases safe, land the audit

- [x] Explicit ruff rule set (`select = ["E4","E7","E9","F"]`) + pinned `requirements-dev.txt`; CI and the local gate install from it
- [x] `timeout-minutes: 30` on `deploy-backend`
- [x] Migration step: `lock_timeout=10s` / `statement_timeout=120s`, 5 bounded retries, `pg_stat_activity` dump on final failure
- [x] Gate test `backend/tests/unit/test_migration_lock_safety.py` (workflow knobs, toolchain pin, explicit select, filename convention, frozen shrink-only allow-list of 17 legacy unguarded ALTERs)
- [x] Lessons: `ops-migrations-need-lock-timeout.md`, `ops-pin-ci-toolchain.md` (+ index)
- [x] Doc sync: `DEPLOYMENT.md` (7 jobs, `/health/detailed`, `pdx1`, migrations automatic, only backend pushes deploy), `CLAUDE.md` (7 jobs, rule-3 lock note, gate install line)
- [x] `frontend/package.json`: `"postcss": "$postcss"` override (unblocks Dependabot; lockfile-neutral, `npm ci` verified)
- [x] Archive finished SEO plan → `tasks/archive/seo-audit-quick-wins-todo.md`
- [x] **(founder)** Pre-flight: run the `pg_stat_activity` query in `ENGINEERING_AUDIT_2026-09.md` §2; terminate any idle-in-transaction session — *skipped by decision 2026-09-04 (no Cloud SQL access from the merging session; the new `lock_timeout` bounded the worst case to a failed, diagnosable job). The migration step applied all 32 files on the first attempt, so no blocker was present.*
- [x] **(founder)** Merge this PR → watch `deploy-backend` complete → verify API `robots.txt` is `Disallow: /`, `/health/detailed` healthy, 31-burst to `/api/companies/AAPL/insiders` → 429 — *done 2026-09-04 22:36–22:42Z: merge `df9c893`, CI run 1840 success; robots `Disallow: /` live after 319 s; `/health/detailed` healthy (db 7.8 ms, circuit closed); burst → 30×200 then 429 with `Retry-After: 36`.*
- [ ] **(founder)** Check Cloud Run 5xx/latency + Sentry for 2026-07-16 18:40Z → 07-17 00:38Z; if degraded, add a lesson

## Phase 1 — Priority 1: reliability floor (≈4 engineer-days + founder console time)

- [x] **(founder decision)** Migration design: DO-block guard only (status quo, gated) vs `schema_migrations` ledger (recommended; ADR supersedes rule-3 wording) — *decided 2026-09-04: ledger (PR #658, ADR-0007)*
- [x] Implement the chosen migration design — *PR #658 merged 2026-09-05 (`c6eaddf`); its first deploy failed because prod already had a foreign `schema_migrations` table, fixed by hotfix PR #678 (`f8e7728`, ledger renamed `migration_ledger`, CI decoy gate, ADR-0007 amendment, lesson `ops-deploy-owned-state-needs-a-distinctive-name.md`); seed deploy verified `applied=32 skipped=0`, health green*; Cloud SQL flag `idle_in_transaction_session_timeout` as DB-side backstop **(founder: flag)**; **(founder)** inspect and drop the legacy prod `schema_migrations` table
- [x] Extend the lock gate: plain `CREATE INDEX IF NOT EXISTS` on pre-existing tables (second frozen legacy list; `CONCURRENTLY` for new files) — *PR #656 merged 2026-09-05 (`f340bb0`), deploy green*
- [x] Ledger-skip the re-run `UPDATE` in `20260706_demote_null_fiscal_period_duplicates.sql` — *ledger live since #678; the file ran once at seed and is now skipped*
- [ ] Alerting minimum: uptime check on `/health/detailed`; Cloud Run job-failure alert; log-based alerts (SEC circuit open, generation failures); Actions failure notifications for `refresh-index-membership` / `data-quality-weekly` **(founder: GCP console)**
- [x] Scheduled workflow running `tests/e2e/prod-smoke.spec.ts` against production (`SMOKE_BASE_URL`), daily — #711 plus #713 locator correction; green 34002892976 and deliberate red 34003003306 accepted, failure reporting and issue closure verified (W3-4 evidence above).
- [x] Frontend observability: `GlobalErrorBoundary` imports the Sentry SDK; delete the dead frontend `signup_completed` helper; pre-consent PostHog proposal — *PR #660 merged 2026-09-05 (`ffb0b61`)*; Sentry source-map env in Vercel **(founder)**
- [x] Dependabot triage: merge #635 #636 #639 #640 #641 #642 — *all merged 2026-09-04, deploys green*
- [x] Dependabot closes: #629 and #570 closed 2026-09-04; `typescript` major-ignore landed in #674; #662–#670 closed as superseded by #674 and #672 closed as superseded by #679 + #680; #659 closed so Dependabot re-creates the remaining 15 minors against Next 16.3.4 / Node 22 — *2026-09-05*; the fresh #686 group appeared and was resolved by #694/#695
- [x] #684 OpenAI 3.7 integrated and closed through #701 resilience/native SDK/full actual eval gates. #685/#683 merged; #686 superseded by #694/#695.
- [x] Split #672: non-edgartools bumps (pandas 3.0.5, fastapi, stripe, posthog, …) — *PR #679 merged 2026-09-05 (`fbbccc5`)*; edgartools 5.40.1→5.55.0 alone through the eval gate — *PR #680 merged (`083247d`, regression gate PASS, 0 warnings)*; #672 closed
- [x] Next.js 16.3.4 (+ transitive security patches, `npm audit --omit=dev` 10 → 0) — *PR #674 merged 2026-09-05 (`2f2e48d`); Vercel production deployment completed; `::highlight` lives in a constructed stylesheet; `next build` typechecks `tsconfig.ci.json`*
- [x] Dependency-audit gates in CI (advisory): `pip-audit -r backend/requirements.txt`, `npm audit --omit=dev --audit-level=high` — *PR #674*; cryptography 50 shipped #685. Audit posture remains advisory. W3-6 local runtime-lock `pip-audit` reports no known vulnerabilities after removing the jose/ecdsa chain; this does not claim every dev-tool, image or frontend dependency is clean or authorize a blocking-policy transition.
- [ ] Backups: PITR + deletion protection on `earningsnerd-db`; monthly export to lifecycle-managed GCS; one-page rehearsed restore runbook **(founder: console)**
- [x] Universe refresh: FMP stable API first, loud partial-list abort, 100-day age gate — *PR #655 merged 2026-09-05 (`49dd399`), deploy green*; founder supplied `FMP_API_KEY` in GitHub `Production`; W3-2 binding/deployment verified. W3-3 run 34000192154 reached FMP but returned HTTP 402. The subsequent founder-requested public-source replacement #718 supersedes that prerequisite; its release and remaining publication acceptance are recorded above
- [x] Pricing page SSR (`useSearchParams` → Suspense-scoped child) + Product/Offer JSON-LD; contact meta-description entity; noindex auth pages — *PR #660 merged 2026-09-05*
- [x] Node 20 → 22.23.2 (`.nvmrc`, `engines`, CI ×3, lockstep gate `nodeVersionLockstep.spec.ts`) — *PR #674*; **(founder)** set the Vercel project Node.js Version to 22 so the dashboard matches the `engines.node` override that already governs the build
- [x] Quick wins: `ops.yml` push trigger removed + `cloud-sql-proxy` sha256 pinned (*#656*); `hot_filings.py` and the trending refresh route deleted outright (*#657*, so the admin-token compare and rate limit are moot)
- [x] Drop `"log"` from client Sentry console levels — *PR #660 merged 2026-09-05*
- [x] Rule-8 gate: env-access allow-list test — *PR #661 merged 2026-09-05 (`41abb26`), deploy green*

## Phase 2 — Priority 2: summary fidelity measurement, then arm the guards (≈7 engineer-days)

- [x] Add `mean_untraceable_dollar_figures` as a measured absolute WARN dimension — #700. The parity pin has no reference for it; no invented zero baseline or new hard floor.
- [x] #700 implemented the fixed 8 × 3 weekly strong-judge workflow and report receiver; judge remains off in routine PR CI.
- [ ] First actual strong-judge readout: founder credential/execution required; workflow also sends the report email.
- [x] Roll the five audit counters into the weekly data-quality report from persisted `raw_summary` audits — #700, with separate valid/missing/malformed denominators.
- [ ] Arm `AI_EVIDENCE_SNAP` only after the first judged readout (D5 accepted); figure-trace and forward-quote remain advisory. Strong-judge credential/readout currently unavailable
- [x] #701 retry/fallback: delete the dead Gemini chain in `openai_service.py`; bounded backoff on the primary; env-configured `AI_FALLBACK_BASE_URL`/`AI_FALLBACK_MODEL`; fix the retry unit test to use real names
- [x] #701 per-summary telemetry: log `usage` and `response.model`; surface on `/metrics`
- [x] Eval ↔ prod parity, restored JPM G5 components, actual production streaming, routine two-run gate and sole three-run baseline pin — #698.
- [x] #703 Copilot on verified live-source FPI filings: currency directive (never bare `$` for CNY/TWD/EUR); scope `_query_fact` to the filing being viewed (period from the filing, not `is_latest` company-wide); six verified accessions/five issuers, three actual draws each; older unverified entries remain pending
- [ ] Golden-set breadth: 6-K entries, one REIT/utility/insurer, small caps **(D4 spend approved; execution pending)**
- [x] Reading surface on the filing page: distinct risk headings, mobile section jump-nav, skip-to-content + live region, company-name casing — *PRs #671 + #676 merged 2026-09-05, casing verified live*
- [x] #702 section-recovery grounding: build context from labelled excerpt sections (~30k cap) instead of raw HTML with a 6,000-char cap
- [x] #702 deleted the latent `previous_filings` prompt path + AST pin (rule 2 hygiene)
- [ ] **D4 spend approved; founder execution pending:** drain cached v1 summaries → v2 via admin `refresh-stale` (~$0.05/filing), after D5's judged-readout and evidence-snap prerequisites
- [x] Owning #698–#704 PRs corrected RUNBOOK status, quality-plan headers, façade/provider and DATA_COMPLIANCE processor descriptions; historical quality-plan bodies preserved.

## Phase 3 — Priority 3: coverage and data integrity for the beta universe (≈8 engineer-days)

- [ ] **D4 spend approved; founder execution pending (~$25–50 one-time):** universe-wide pregeneration, latest 10-K + 10-Q for the 515-name universe in batches via `precompute`; weekly 10-Q and Company seed tooling merged #697; founder seed/SIC enrichment and off-peak generation still pending (237 missing rows was the audit snapshot)
- [x] Weekly coverage/stub/universe-age/job-heartbeat report implementation — #690. Live report/backfill evidence remains required.
- [ ] **(founder)** Execute SIC backfill and retain completion/report evidence. Code default True shipped #690; pregenerate FPI env shipped #697; neither proves data was backfilled.
- [x] Amendments: list/ingest 10-K/A and 10-Q/A; supersession and Change Report — #697; existing rows link on refresh/backfill.
- [x] Fiscal periods, unit/decimals assertions and reconciliation UI/exports — #697.
- [x] #704 wires actual ORM reporting date into prospective reconciliation; existing-identity skips/cross-check policy preserved.
- [ ] Engineering: design an explicit historical flag audit/repair capability before founder production repair. Ordinary backfill or freshness `--force` does not re-reconcile existing identities.
- [x] Rule-5 gate: `_fetch_companyfacts_sync` through the SEC limiter via the app-loop bridge (`app/services/event_loop.py`); `sec.gov` allow-list test — *PRs #661 + #675 merged 2026-09-05*
- [x] Rule-10 gate: `app/utils/sec_urls.py::build_sec_archive_url` + listener tests — *PR #661 merged 2026-09-05*
- [x] Sitemap: hourly ISR with uncached upstream fetch, regression tests, `/terms` and SEO doc — #693.
- [ ] 6-K classifier (earnings vs governance vs press release): the 6-K summary path exists behind `ENABLE_FPI_FILINGS` (`prompts/6k-*.md`, `summary_pipeline.py:358-489`) but every 6-K gets one prompt; add 6-K golden-set entries
- [x] Dead-integration teardown: trending, hot_filings, fmp, finnhub, stocktwits and their consumers removed — *PR #657 merged 2026-09-05 (`9ff8da6`), deploy green, old routes 404*
- [ ] Clear the four standing weekly-report anomalies: `backfill-filing-history` for C, MS, WFC, GS; grant deployer SA access to `INTERNAL_JOB_TOKEN`
- [x] Liabilities/cash fallback and persisted accession-specific XBRL first — #697.
- [ ] **D3 accepted; execution pending:** founder creates/seeds the Notable job and reviews one week of output before `NOTABLE_FILINGS_ENABLED` activation per `DEPLOYMENT.md`; homepage findings archive completed #692
- [x] FPI roadmap archive and status block — #692. Residual 6-K classifier and founder backfill remain open.

## Accepted policies — execution and verification pending

- [x] Migration design (guard-only vs ledger) — *ledger, 2026-09-04*
- [ ] **D5 accepted:** obtain the first judged readout, then arm `AI_EVIDENCE_SNAP`; figure-trace and forward-quote remain advisory. The strong-judge credential/readout prerequisite is outstanding.
- [ ] **Execution pending; D4 spend approved:** universe pregeneration, v1→v2 drain and golden-set runs; FMP secret remains founder-owned
- [ ] **D3 accepted:** confirm the Analysis production flag and warm companyfacts before activation; complete Notable job/seed/one-week review prerequisites. Calendar remains off pending the licence decision; Insiders remains off.

## Remaining founder decisions and console actions

- [ ] Alpha Vantage: licence or EDGAR-only
- [ ] Legal: Terms §7e counsel pass; processor DPAs; legal entity / governing law
- [ ] `WAITLIST_MODE` intent; LAUNCH_CHECKLIST founder-only actions (GSC, Bing, apex 307→308, Vercel plan, `NEXT_PUBLIC_EXAMPLE_FILING_ID`)
- [ ] Pro trial timing; delete retired reverse-trial code?
- [ ] `USE_STRUCTURED_OUTPUT`: bake-off or delete
- [ ] GCP console: PITR + deletion protection; uptime/alert policies; Turnstile keys; confirm effective `REGISTRATION_MODE` in the console (`ops.yml describe-service` withholds its value); inspect other permitted flags

## Deferred (tracked in appendix 06, not scheduled)

SEO phases 2–3; dashboard "later" tier (8-K rows, weekly brief, sparklines, 13F); competitive roadmap
A4/A7/A8; cold-path Phase C; MFA/TOTP; retention purge jobs (policy promise — schedule before public
launch); Turnstile fail-closed; T5 depth ledger; cheaper-model routing flags; waitlist/contact route tests;
`SUMMARY_SELF_VERIFY`; prompt-prefix caching; off-peak cron windows.

## Parity and the sole measured baseline — archived

- [x] #698 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-parity-2026-09.md).

## WS-7 implementation — archived

Steps 1–6 are merged (#690/#697). [Completed steps 3–6 and proof](archive/ws7-completeness-2026-09.md).
Founder execution and live data evidence remain unchecked above and in the ledger; #697 deployment is verified.

## WS-10 — configuration and script placement hygiene

- [x] Implementation and current-main local gates complete in PR #696; [archived proof](archive/ws10-hygiene-2026-09.md).
- [x] WS-7 default/docs integrated; 1910-test gate, independent review and CI passed; #696 merged (`0e0e7762`), deployment verified.

## Measurement implementation — archived

- [x] #700 merged, actual gates and deployment verified; [plan and retained evidence](archive/ws6-measurement-implementation-2026-09.md).
