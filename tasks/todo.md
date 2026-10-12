# Open items — EarningsNerd

One line per open item, with owner, disposition and next step; full sweep evidence belongs in the
reconciliation PR. The [historical ledger](archive/todo-ledger-through-2026-10-07.md) is evidence,
not a queue. Format: `AGENTS.md` §7. Founder rows stay until the founder closes them.

## Where things stand — 2026-10-12, Codex

- Production read Oct12 01:28 UTC: `earningsnerd-backend-00502-vs7` serves 100%, release `86aafb7`; [Ops 38192011129](https://github.com/neilmac91/EarningsNerd/actions/runs/38192011129) passed with worker IAM enforced/private. Detailed health was healthy at 01:28. [Main CI 38176749830](https://github.com/neilmac91/EarningsNerd/actions/runs/38176749830) is the existing successful deploy (`applied=0 skipped=43`); no sweep deploy occurred.
- Provider balance and account-budget observations are retained in the private sweep ledger; no paid evaluation has run. Refresh the balance and reserve cost before paid work, retaining the wallet floor, programme ceiling and [refactor hold](refactor-closeout-2026-10.md#spend-ledger).
- Repository is intentionally public; standard Ubuntu read-only runs report zero billable milliseconds. Current account-wide billing and the protected-branch settings API remain UNVERIFIED; budgets/stop-usage are unchanged. Approved exact scan exceptions in [#1261](https://github.com/neilmac91/EarningsNerd/pull/1261) pass six application/security checks but await quota-blocked required review; no override.
- Sweep drafts [#1255–#1275](https://github.com/neilmac91/EarningsNerd/pull/1255) and per-row links below are locally prepared; none merged. Required review is quota-blocked except #1256–#1259; #1259/#1265 retain separate hosted timing failures. Founder owns #1243/#1248 merges; #1251 remains owner-held. #1197/#1226 are merged.
- Holds: [September 19 §5](handover-astra-2026-09-19.md#5-what-remains--reconciled-open-list) and September 28 checkpoint in `continuation-plan-2026-09-26.md`; E7/R1/H20 custody remains separate. The sweep adopts the Analysis recommendations for decisions 4 (amended), 6, 7, 8 and 9; that authorizes implementation, not a claim it is shipped.

## Open items

Founder:
- [ ] F1 — PREPARE: supply the founder sentence and name for the dormant `founderNote.ts` slot; brand handoff `docs/brand/README.md` (#1226).
- [ ] F2 — PREPARE: decide one bounded FY2025 landing-demo regeneration; its `data_notes` and narrative payload must match the filtered demo consumers before publication (#1226, #1225).
- [ ] F3 — PREPARE: choose the Notable filings curation rule before remounting the homepage section; compare the observed public feed with known-good, size-floor and 10-K/10-Q options (#1226).
- [ ] F4 — PREPARE: review the concrete Vercel Analytics policy/date draft [#1265](https://github.com/neilmac91/EarningsNerd/pull/1265), or choose shared consent gating; legal publication remains held and all hosted checks remain required.
- [ ] F5 — PREPARE: verify the founder's calendar sage-number decision through owner PR #1251, including its computed-JSX review finding; no competing branch (D-023/D-030).
- [ ] F6 — PREPARE: decide a separate landing-composition pass after reviewing the scope and 200%-text/mount risks in `docs/brand/09-stress-test.md` §2.
- [ ] F7 — PREPARE: confirm the intended PostHog project before closing this row for the absent `pricing-experiment` flag or retiring any remaining definition; tracked code has no reader after #1009; retain the test-account exclusion in `docs/OPERATIONS.md`.
- [ ] F8 — PREPARE: approve the prepared previous-Price renewal classifier branch and verify historical monthly/yearly IDs before configuration; no paid PR until that approval and a fresh reservation (`billing_revenue_service.py`, `docs/PRICING_OFFER.md`).
- [ ] F9 — PREPARE: decide provider-key rotation after record 23's in-session fragment exposure; founder performs provider, CI and Cloud Run secret actions, then verifies balance and health (`code-red-20261004/runtime/control/DECISIONS-23.md`).
- [ ] F10 — PREPARE: relay record 20's appendix custody step A once and decide record 16's outcome-B form (b); custody evidence and the R1 hold remain unchanged (`DECISIONS-16.md`, `DECISIONS-20.md`).
- [ ] F11 — PREPARE: change the squash default to Pull request title and description if desired; current API reports COMMIT_MESSAGES, so reviewed PR evidence is not the default message (`DECISIONS-18.md`, `DECISIONS-20.md`).
- [ ] F12 — PREPARE: choose an Artifact Registry Docker Hub remote repository or a Docker Hub CI credential; a workflow branch needs the real registry/auth contract first (#1169).
- [ ] F13 — POSTPONE: H20-only packing/closure refinement needs its registered planner, custody gates and explicit lift of the implementation hold (`DECISIONS-04.md`, `DECISIONS-05.md`).
- [ ] F14 — POSTPONE: confirm the private security plan's credential rotation, push protection, old revision-tag removal and WIF-to-main console actions; no security setting changes are authorized here (#1069).
- [ ] F15 — PREPARE: settle #1118 decisions 3 (visibility/public records), 4 (`tasks/` retention) and optional 8 (briefs as subagents); repository is now public and private deliberations stay outside it.
- [ ] F16 — POSTPONE: provide the missing `tasks/upstream-sync.md` §1–15 or its location and the external DS project; then regenerate `_ds_bundle.js`, complete P-01 in the Claude Design project, republish and link the package (DS-01).
- [ ] F17 — PREPARE: choose a release asset or archive repository for the removed landing export; commit `02628e5` contains 35 tree files, including the retained RATIONALE.md, and 34 removed payload files.
- [ ] F18 — PREPARE: decide orphan-subscription cleanup and deletion-failure policy; production user-deletion audit rows are not available through the current Ops allowlist, and Stripe cancellation stays founder-owned (#1176).
- [ ] F19 — PREPARE: approve the prepared atomic deletion-audit/UTC-export branch, including audit-failure blocking database deletion, before a paid PR; uniqueness needs a private duplicate count and note-preservation policy, and async DB work needs latency evidence (#1140/#1141).
- [ ] F20 — CANCEL-RECOMMENDED: the exact Copilot arm-B-plus-quotation candidate was measured and closed unqualified in #1074; a successor needs a new question and ceiling, not a repeat of that experiment.
- [ ] F21 — PREPARE: decide held native-evidence adapter draft #1035 after its current lifecycle/metadata findings; bind the release base and run the releasing-machine plan/probe only within an approved ceiling.

Engineering:
- [ ] E1 — IN-FLIGHT: truthful status [#1264](https://github.com/neilmac91/EarningsNerd/pull/1264), reading/print [#1272](https://github.com/neilmac91/EarningsNerd/pull/1272), table geometry [#1273](https://github.com/neilmac91/EarningsNerd/pull/1273), charts [#1274](https://github.com/neilmac91/EarningsNerd/pull/1274) and period controls [#1275](https://github.com/neilmac91/EarningsNerd/pull/1275) pass local acceptance. Canonical-copy/exports are prepared separately; paid PR waits for required review/dependencies and a fresh reservation. Reconcile shared components and final-base gates against `analysis-redesign-2026-10/review-2026-10-10.md`; adopted decisions 4 (amended), 6–9 stay in the design brief §9, and data repair stays held.
- [ ] E2 — IN-FLIGHT (founder/Claude): #1243 fixes the three original review findings; its newer aliased/dotted namespace-accessor boundary remains an owner-declined scope decision for the founder; verify each #1177 clause after the founder merges.
- [ ] E3 — IN-FLIGHT (founder/Claude): #1243 covers #1190 imports/CLI/layout/new members; verify the final self-tests after the founder merges and retain disclosed directory-only/cross-file-order limits unless a concrete consumer justifies more.
- [ ] E4 — IN-FLIGHT (Codex): [#1262](https://github.com/neilmac91/EarningsNerd/pull/1262) fixes the delete-account error field and removes its final pin with measured shared focus tokens; merge and verify both themes before closure.
- [ ] E5 — IN-FLIGHT (Codex): shared tokens/Switch/inset controls in [#1262](https://github.com/neilmac91/EarningsNerd/pull/1262) and named page controls in [#1263](https://github.com/neilmac91/EarningsNerd/pull/1263) pass local acceptance; owner #1251 retains MonthView; reconcile final integration and required checks.
- [ ] E6 — POSTPONE (CODE RED chief): read the 2026-10-12 06:00–08:00 UTC capacity window after 08:20; the accessible automation list cannot verify the recorded chief trigger, so coordinate it before any dispatch or duplicate schedule; absent SEC/breaker classes stay unknown (`DECISIONS-19.md`, `DECISIONS-23.md`).
- [ ] E8 — IN-FLIGHT (Codex, sufficient context): [#1258](https://github.com/neilmac91/EarningsNerd/pull/1258) captures proxy-secret stderr, preserves disclosed progress and documents redaction/interpreter limits; local high-tier gates and exact-head review pass; first affected read-only Ops readback waits for merge.
- [ ] E9 — POSTPONE (page owners): the company, filing and TickerFilingsView full-page spinners wait for their pages' next rework, as the design critique and owning spinner gate intended (#1146/#1147/#1148/#1150); external P-01 is with Founder F16.
- [ ] E10 — IN-FLIGHT: catalog [#1256](https://github.com/neilmac91/EarningsNerd/pull/1256) and zero ceilings [#1257](https://github.com/neilmac91/EarningsNerd/pull/1257) are reviewed drafts; founder-owned #1248 fixes its original four findings but retains the qualified-create_engine gap; further router moves wait for dependencies and reserved release capacity.
- [ ] E11 — IN-FLIGHT (Codex): [#1259](https://github.com/neilmac91/EarningsNerd/pull/1259) repairs the isolation owners with leaker/victim evidence and 7,076 local passes; an unchanged hosted provider-admission timing assertion is red, and native Windows remains unverified; preserve locked tests and obtain green final-base checks.
- [ ] E12 — POSTPONE (founder): supply the private WP-07+ list or confirm completion; the repository defines WP-01–WP-06 only (#1069 series).
- [ ] E13 — IN-FLIGHT: generation focus [#1260](https://github.com/neilmac91/EarningsNerd/pull/1260), desktop pane [#1269](https://github.com/neilmac91/EarningsNerd/pull/1269) and phone tables [#1270](https://github.com/neilmac91/EarningsNerd/pull/1270) pass local acceptance; preserve both SummaryBlocks changes on integration. Warning suppression is CANCEL-RECOMMENDED; old harnesses wait for reuse, memoization for measurements, and missing-prior server formatting for a compatible backend batch.
- [ ] E14 — IN-FLIGHT: disabled tint [#1262](https://github.com/neilmac91/EarningsNerd/pull/1262), verification [#1266](https://github.com/neilmac91/EarningsNerd/pull/1266), dashboard [#1267](https://github.com/neilmac91/EarningsNerd/pull/1267) and alert errors [#1268](https://github.com/neilmac91/EarningsNerd/pull/1268) are locally verified drafts; retain the inapplicable Modal-host Escape CANCEL-RECOMMENDED disposition and PREPARE the founder-only class-7 SQL read.
- [ ] E15 — IN-FLIGHT: Insider gain/loss ink [#1262](https://github.com/neilmac91/EarningsNerd/pull/1262) and filing Retry [#1271](https://github.com/neilmac91/EarningsNerd/pull/1271) pass local acceptance; preserve the shared inset ring on integration. Analysis Run’s locked native-disabled contract remains a separate founder decision.

## What to doubt first

- Re-read `main`, open heads and current reviews before each branch; #1243/#1248/#1251 are owned by other sessions, and a drafted fix is not a merged closure.
- The provider balance is time-stamped, not a spend receipt; refresh before paid work and retain unknown costs. Account billing and future capacity are not established by the successful reads above.
- Historical handovers and unchecked archive rows are evidence only; private decision packs and missing external plans are not repository authority.
