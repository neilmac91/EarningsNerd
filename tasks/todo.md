# Open items — EarningsNerd

One line per open item, with owner, disposition and next step; full sweep evidence belongs in the
reconciliation PR. The [historical ledger](archive/todo-ledger-through-2026-10-07.md) is evidence,
not a queue. Format: `AGENTS.md` §7. Founder rows stay until the founder closes them.

## Where things stand — 2026-10-11, Codex

- Production read 22:43 UTC: `earningsnerd-backend-00502-vs7` serves 100%, image `86aafb7`; [Ops 38181518055](https://github.com/neilmac91/EarningsNerd/actions/runs/38181518055) passed. [Main CI 38176749830](https://github.com/neilmac91/EarningsNerd/actions/runs/38176749830) deployed with `applied=0 skipped=43`; detailed health was healthy at 22:41 UTC.
- Provider balance: USD 13.60 at 22:42:03 UTC ([38181452020](https://github.com/neilmac91/EarningsNerd/actions/runs/38181452020)); sweep cost/reservations USD 0; USD 8.046150 available under the USD 10 ceiling after the USD 5 floor and [USD 0.553850 retained hold](refactor-closeout-2026-10.md#spend-ledger).
- Repository API reports public; current workflows use standard Ubuntu runners (free public runner minutes). Account-wide Actions usage is UNVERIFIED (billing API 403); the 18:34 UTC USD 30.06/40 alert is historical. Budgets and stop-usage are unchanged.
- Open PRs at this reconciliation: #1252, #1251, #1250, #1249, #1248, #1243, #1223, #1121, #1035. Founder owns the merges of #1243/#1248; their latest review findings remain with their authors. #1197/#1226 are merged.
- Holds: [September 19 §5](handover-astra-2026-09-19.md#5-what-remains--reconciled-open-list) and September 28 checkpoint in `continuation-plan-2026-09-26.md`; E7/R1/H20 custody remains separate. The sweep adopts the Analysis recommendations for decisions 4 (amended), 6, 7, 8 and 9; that authorizes implementation, not a claim it is shipped.

## Open items

Founder:
- [ ] F1 — PREPARE: supply the founder sentence and name for the dormant `founderNote.ts` slot; brand handoff `docs/brand/README.md` (#1226).
- [ ] F2 — PREPARE: decide one bounded FY2025 landing-demo regeneration; its `data_notes` and narrative payload must match the filtered demo consumers before publication (#1226, #1225).
- [ ] F3 — PREPARE: choose the Notable filings curation rule before remounting the homepage section; compare the observed public feed with known-good, size-floor and 10-K/10-Q options (#1226).
- [ ] F4 — PREPARE: approve a Vercel Web Analytics privacy-policy/date addition or analytics-consent gating; prepare a frontend draft, preserving the legal decision (#1226 review).
- [ ] F5 — PREPARE: verify the founder's calendar sage-number decision through owner PR #1251, including its computed-JSX review finding; no competing branch (D-023/D-030).
- [ ] F6 — PREPARE: decide a separate landing-composition pass after reviewing the scope and 200%-text/mount risks in `docs/brand/09-stress-test.md` §2.
- [ ] F7 — PREPARE: end the unused PostHog `pricing-experiment` flag in the console; tracked frontend/backend code has no reader, and `docs/OPERATIONS.md` retains the test-account exclusion (#1009).
- [ ] F8 — PREPARE: decide whether legacy Price renewals need cycle labels; prepare previous-Price Settings/classifier tests on a branch, with no paid PR opened until approval (`billing_revenue_service.py`, `docs/PRICING_OFFER.md`).
- [ ] F9 — PREPARE: decide provider-key rotation after record 23's in-session fragment exposure; founder performs provider, CI and Cloud Run secret actions, then verifies balance and health (`code-red-20261004/runtime/control/DECISIONS-23.md`).
- [ ] F10 — PREPARE: relay record 20's appendix custody step A once and decide record 16's outcome-B form (b); custody evidence and the R1 hold remain unchanged (`DECISIONS-16.md`, `DECISIONS-20.md`).
- [ ] F11 — PREPARE: change the squash default to Pull request title and description if desired; current API reports COMMIT_MESSAGES, so reviewed PR evidence is not the default message (`DECISIONS-18.md`, `DECISIONS-20.md`).
- [ ] F12 — PREPARE: choose an Artifact Registry Docker Hub remote repository or a Docker Hub CI credential; a workflow branch needs the real registry/auth contract first (#1169).
- [ ] F13 — POSTPONE: H20-only packing/closure refinement needs its registered planner, custody gates and explicit lift of the implementation hold (`DECISIONS-04.md`, `DECISIONS-05.md`).
- [ ] F14 — POSTPONE: confirm the private security plan's credential rotation, push protection, old revision-tag removal and WIF-to-main console actions; no security setting changes are authorized here (#1069).
- [ ] F15 — PREPARE: settle #1118 decisions 3 (visibility/public records), 4 (`tasks/` retention) and optional 8 (briefs as subagents); repository is now public and private deliberations stay outside it.
- [ ] F16 — POSTPONE: provide the missing `tasks/upstream-sync.md` §1–15 or its location and the external DS project; then regenerate `_ds_bundle.js`, republish and link the package (DS-01).
- [ ] F17 — PREPARE: choose a release asset or archive repository for the removed landing export; commit `02628e5` contains 35 tree files, including the retained RATIONALE.md, and 34 removed payload files.
- [ ] F18 — PREPARE: decide orphan-subscription cleanup and deletion-failure policy; production user-deletion audit rows are not available through the current Ops allowlist, and Stripe cancellation stays founder-owned (#1176).
- [ ] F19 — PREPARE: decide Lane B's audit ordering/UTC export fixes, duplicate-summary uniqueness after a production count, and async DB work after latency evidence; branches require separate approval before paid PRs (#1140/#1141).
- [ ] F20 — CANCEL-RECOMMENDED: the exact Copilot arm-B-plus-quotation candidate was measured and closed unqualified in #1074; a successor needs a new question and ceiling, not a repeat of that experiment.
- [ ] F21 — PREPARE: decide held native-evidence adapter draft #1035 after its current lifecycle/metadata findings; bind the release base and run the releasing-machine plan/probe only within an approved ceiling.

Engineering:
- [ ] E1 — DO (Astra): finish the verified open Analysis review items in frontend-first groups, then exports/backend; decisions 4 (amended), 6–9 are adopted in `docs/design/analysis-data-notes-redesign-2026-10.md` §9; brief `analysis-redesign-2026-10/astra-prompt.md`, subitem record `analysis-redesign-2026-10/review-2026-10-10.md`; data repair remains held.
- [ ] E2 — IN-FLIGHT (founder/Claude): #1243 covers #1177's move-proof false OKs and missing self-tests; resolve the current class-namespace mutation finding, then verify each clause after the founder merges.
- [ ] E3 — IN-FLIGHT (founder/Claude): #1243 covers #1190's import/CLI/layout/new-member follow-ups; after merge, verify the self-tests and recommend retaining the directory-only and cross-file-order limits without speculative machinery.
- [ ] E4 — DO (Engineering): fix the delete-account error field with E5's measured ring tokens, then remove its last pin in `inputClassesNoOverrides.spec.tsx` (#1180/#1188).
- [ ] E5 — DO (Engineering): raise enabled light/dark focus-ring contrast to 3:1, apply the DS recipe to the named page controls/inset results, replace the notification switch and extend the owning gate; verify both themes and coordinate MonthView with #1251 (#1178).
- [ ] E6 — POSTPONE (CODE RED chief): read the 2026-10-12 06:00–08:00 UTC capacity window after it elapses and log ingestion settles; verify the existing chief trigger before any duplicate scheduling, and report unsupported SEC/breaker classes as unknown (`DECISIONS-19.md`, `DECISIONS-23.md`).
- [ ] E8 — DO (Codex, sufficient context established): withhold the proxy-secret read stderr, retain disclosed job/rollback progress, and document redaction/interpreter limits using the fake-gcloud gate and high-tier review; no security-policy or production-setting change (`DECISIONS-23.md`, #1195).
- [ ] E9 — POSTPONE (founder/page owners): P-01 needs the external Claude Design package; the three full-page spinners wait for their pages' next rework, as the design critique intended (#1146/#1147/#1148/#1150).
- [ ] E10 — DO (Engineering): add the eight Lane B service-catalog rows and prune proven zero ceilings; read-only GET work is IN-FLIGHT in founder-owned #1248; postpone further router moves until #1243's proof findings are settled and release capacity is reserved.
- [ ] E11 — DO (Engineering): reproduce and repair #1135's isolation leaks 1–6 and 8 with leaker-then-victim evidence, including limiter reset outside locked tests and Windows cleanup; no speculative second gates.
- [ ] E12 — POSTPONE (founder): supply the private WP-07+ list or confirm completion; the repository defines WP-01–WP-06 only (#1069 series).
- [ ] E13 — DO (Engineering): fix successful-generation focus, the chip-opened desktop pane overhang and phone GenericTable; named detector/doc defects are already closed, warning-only suppression is CANCEL-RECOMMENDED, and old harness repairs wait for reuse; postpone Copilot memoization without a measurement and bundle missing-prior server formatting with a backend change (EN-01/02/03).
- [ ] E14 — DO (Engineering): fix disabled Button tint, verification refresh/429 handling, subscription-error plan labels, saved-summary Retry and async alert anchoring/ticker context; ring tokens belong to E4/E5; CANCEL-RECOMMENDED for the currently inapplicable Modal portal-host Escape change, and PREPARE the founder-only class-7 SQL read.
- [ ] E15 — DO (Engineering): fix InsiderActivityPanel's 600-level gain/loss labels and assess FilingViewer Retry with E13; Analysis Run's locked native-disabled contract remains a founder decision; the resend-success focus clause is already fixed by #1082.

## What to doubt first

- Re-read `main`, open heads and current reviews before each branch; #1243/#1248/#1251 are owned by other sessions, and a drafted fix is not a merged closure.
- The provider balance is time-stamped, not a spend receipt; refresh before paid work and retain unknown costs. Account billing and future capacity are not established by the successful reads above.
- Historical handovers and unchecked archive rows are evidence only; private decision packs and missing external plans are not repository authority.
