# Decision record 08 — PR #1098 merged; ledger event 4 (reserved copilot-eval run settled, reservation undersized); deploy verified; founder instructions (custody, Ops access, option C, D3 patch); closure 151 (chief, 2026-10-05)

Recorded 2026-10-05T18:35:26Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Amended 2026-10-05T18:52:54Z: addendum (COO contract draft delivered; closure 152); dispatch manifest
`COO-QUERY-ROUTE-04` binds this record at its pre-addendum hash `9a19701d…` (13,211 bytes). Amended 2026-10-05T19:03:55Z after the
three-lens review of `39c74850`: this header, the merge-time source, the manifest-binding clause in the addendum. Amended
2026-10-05T19:07:44Z (COO draft revision 2); amended by 19:31:58Z (founder instruction ~19:12Z: ticket 76581 resolved, manifest
`COO-EXPORT-VALIDATION-05`, closure 153); amended 19:35:53Z (export capability outcome); amended 2026-10-05T22:00:25Z in record 09
(seven nits from the delta review of `ad915c44`: this header, the outcome's return time and tool list).
Context: record 07 and the readout diagnostics change merged to main as `c780228a` (GitHub `merged_at` 18:17:54Z; the
squash commit's own timestamp 18:17:51Z; PR #1098). This record closes the loop on that merge: the reserved paid re-trigger and its settlement, the
backend deploy that every `backend/`-touching merge runs, the review-chain identities, the two cosmetic nits carried
from the last delta review, the founder's five instructions received after the afternoon report, and the sixth (PostHog ticket
76581 resolved; export capability test dispatched). Nothing below releases inputs, dispatches the planner, admits capacity, releases a hold,
invites a user, adds load or extends a timebox; the one spend is the reserved run recorded below, whose cost exceeded
its reservation (chief defect, second instance).

## PR #1098 — merged

| Item | Value |
|---|---|
| Final head / merge | `56167e72` → main `c780228a` (squash; GitHub `merged_at` 2026-10-05T18:17:54Z, commit timestamp 18:17:51Z); branch restarted from that main |
| Review chain | three-lens workflow on `de8a525d` (21 contexts; NO BLOCKER ×3; 18 findings, 18 refuters / 0 refuted); delta checks on `2c4e6926`, `c6f3b993` and `56167e72` by the pre-registered delta reviewer (NO BLOCKER each; 48 / 48 / 49 hash rows, 0 mismatched); two nits carried into this record and applied (record-07 header amendment times; "second" delta check) |
| Required checks on `56167e72` | backend-tests, frontend-tests, e2e-tests, migrations-postgres, lighthouse, review-gate (run 37354665438, on the `Review override:` line) — all success; secret-scan and eval-baseline success |
| Codex / Copilot | Codex did not review (connector quota comments 5999886282 and 6000402651); Copilot did not review; the `copilot-eval` workflow is an evaluation job, not a review |

## Ledger event 4 — the reserved re-trigger settled; reservation undersized (chief defect, second instance)

| Item | Value |
|---|---|
| Run | `Copilot filing fidelity` run **37354664320**, job 111913901715, head `56167e72`, 18:16:07–18:18:30Z, triggered by marking the PR ready under the event-3 reservation (USD 0.010000); conclusion failure (not a required check) |
| Calls and cost | 34 `deepseek-flash` calls (18:17:29–18:18:21Z, all `success`); 977,448 prompt tokens of which only 840,448 cache hits (137,000 cache-miss tokens against 5,435 in the first run: a cold prompt cache); 4,155 completion tokens; telemetry `estimated_cost_usd` sum **USD 0.025568**, computed twice from the public job log (chief; the registered read-only helper subagent of closure 150, re-used) |
| Reservation | USD 0.010000 reserved; actual 0.025568; **excess USD 0.015568 unreserved** — recorded as use (chief defect: the reservation was sized to record 02's "about USD 0.01", not to a measured run; the first run's 0.005575 made the estimate look safe) |
| Result | `accepted: false`; expected 18, completed 18, scored 14, passed 14, errors 4 — three `Unverified or ambiguous referenced citation` withholdings and one `quotation_not_in_source`. The earlier run on `2c4e6926` (same code; heads differ only in `tasks/` files) passed 17 / 18 with one error, so the error set is eval non-determinism (same pre-existing withholding classes), not an effect of the PR; disposed not caused by the PR under the RUNBOOK red-copilot rule; recorded, not retried. Handed to the CPO/CTO as an observation for R2 quality work: two runs of the same code, same day, 17 and 14 passes. |
| Evidence | artifact `copilot-fidelity-37354664320` (id 11363019585, 52 files, 75,525,466 bytes, digest `24da8e1c…`, expires 2027-01-03); public job log |
| Ledger | **Event 4** written 2026-10-05T18:21:22Z by the chief (sole writer) under the hash chain (`previous_sha256` `6c2dc45f…`): reservation settled at actual cost; known use 0.553091 → **0.578659** (calls 326 → 360); holds unchanged 1.881713; active reservations 0; conditional unreserved headroom 22.555196 → **22.539628**; cumulative recorded usage 2,419 calls / USD 4.362908. Document SHA-256 `b4ce7016ed1996c345dfc40fc3565cfc1e964963bfc866af1df79f49660f9c36`, 31,690 bytes; republished (artifact version 5) and read back with the same hash. |
| Rule refinement | Reservations for `copilot-eval` are sized from the dearest measured run (≥ USD 0.03 until a cheaper run is measured) and the whole workflow run is the unit; a reservation under the measured cost is a defect, not a rounding. |

## Deploy triggered by the merge — verified

| Item | Value |
|---|---|
| Trigger | CI run **37354885121** on main `c780228a` (push); `deploy-backend` runs on every `backend/`-touching push to main — this PR touched `backend/tests/unit/test_capacity_readout.py` (a test) and `ops/capacity/readout.py` (operator tooling); application code unchanged |
| Detect backend changes | step succeeded and the job proceeded to build and deploy (the PR changed backend/tests/unit/test_capacity_readout.py); its printed output is not in the retained log tail |
| Conclusion | success (job completed 18:28:39Z; every step success, including Verify health) (job 111917875491); revision `earningsnerd-backend-00444-bxs` (image digest `b35a9b5b…`; traffic 100% LATEST; migrations applied 0 / skipped 41) |
| Note | Health step body: status healthy; database healthy (6.85 ms); redis disabled; SEC EDGAR circuit closed. The pregenerate job image and the seven other job images (eight jobs) were updated to the same digest. Application code unchanged from revision 00443; the rollout is a rebuild of identical service code plus the changed test and ops files. Facts read from the public job log by the chief and the registered helper subagent. |
| Chief omission | The PR body and record 07 said "no production change". A `backend/`-touching merge rebuilds the image and rolls a new revision even when application code is unchanged; that consequence was not stated before merging and is recorded here. Serial deployment verification: the job's own health step is the gate; no manual change by the chief. |

## Founder instructions received 2026-10-05T18:29Z — recorded and executed within authority

| # | Instruction (founder, verbatim intent) | Chief action | State |
|---|---|---|---|
| 1 | **R1 custody.** Remove the uploaded source archives from the chief chat where supported; no retry of unpacking, no workaround of the classifier denial; keep the approved local source-only custody route. Astra confirms all 21 bootstrap and 48 predecessor files recovered with zero cloud-only files at packaging, every ZIP member matching its local original, two retained control anchors and 15 predecessor hash/length pairs verified — recovery and packaging evidence only. | The two archives were removed from the session's upload area at 2026-10-05T18:30:57Z without being opened (one `rm`; the four chief-package uploads remain). Astra's statement is recorded here as evidence relayed by the founder, not verified by the chief. | Outstanding, exactly as the founder states: the complete original input-manifest comparison, the custody script's two `TOTAL=` lines, registered-planner resumability. No release or dispatch permission inferred. Receipt NOT_RELEASED; planner undispatched; 150 of 180 minutes remaining. |
| 2 | **Ops access.** `roles/logging.viewer` and `roles/monitoring.viewer` authorized for the existing designated Ops identity, scoped to the required EarningsNerd project; record the exact principal and project; use the normal supported approval process; nothing broader. | Recorded: principal `serviceAccount:github-deployer@earnings-nerd.iam.gserviceaccount.com`, project `earnings-nerd`, roles exactly the two named, project-level. The repository's supported process is the documented `gcloud projects add-iam-policy-binding` form of `tasks/gcp-deploy-runbook.md` (Phase 5) run by the founder; no Ops workflow operation grants IAM and the chief makes no IAM change. Exact commands handed to the founder in the session. | Grant pending the founder's run. After it: one read-only `logs-probe` dispatch verifies the read, then one bounded `capacity-readout` over a job-overlap window by COO/CEO decision (B32/B56). |
| 3 | **Reporting.** Option C: keep the existing PostHog ticket open and prepare the query route without spending or accessing customer data beyond existing authorization. | Adopted. Ticket 76581 retained and not resent. A bounded COO worker (label pre-registered in closure 151; dispatch manifest `COO-QUERY-ROUTE-04`) drafts the query-route readout contract from `REPORT-ROUTE-PROPOSAL-01` and the G2/G3 definitions: no connector call, no customer data, no spend. The operator-identity question (which non-executive context holds the connector) is answered in the draft as a decision for the founder, not assumed. | In progress; G1–G3 stay BLOCKED until the contract is accepted and the access decision for the chosen route is explicit. |
| 4 | **SEC budget patch.** Keep deployment held pending the specific D3 decision; present the exact existing patch, its configured fleet assumptions and the decision needed; do not reopen the broad assessment or circumvent any platform denial. | Presented in the session (file attached) and summarised below. Deployment held. The chief's own commit of the patch was classifier-denied on 2026-10-04 and is not re-attempted; application is the founder's (`git apply` of the attached file, commit, PR). | Decision pending: confirm `1 + 1` per process or change the numbers. |
| 5 | **Overall execution.** Complete the deployment verification in flight; progress other executable dependencies in parallel under existing owners and gates; batch records; reuse valid evidence for unchanged bytes. | Deploy verified (section above). This record batches the merge, the ledger settlement, the deploy, the five instructions and closure 151 into one PR; the COO draft runs in parallel. | — |

### The D3 patch as it stands (presented, not applied)

| Item | Value |
|---|---|
| File | `sec-process-budgets.patch`, SHA-256 `21322a0546542156a5c9d21fc3de9cb9ad0e4b93b320d9a4da6d3987eb8c3969`, 20,062 bytes; unchanged since 2026-10-04 (CHECKPOINT founder item 3); applies cleanly to main `c780228a` (`git apply --check`) |
| Changes | `.github/workflows/ci.yml` (+15/−): adds `SEC_RATE_LIMIT_PER_SECOND=1,EDGAR_RATE_LIMIT_PER_SEC=1` to the deploy env maps of the service, the pregenerate job, the six-job loop and backfill-facts; `backend/tests/unit/test_sec_process_budgets.py` (new, 132 lines): rule-12 gate asserting the pinned value on every process, the stated sums against `docs/OPERATIONS.md`, the dev default 10 unchanged, and the pinned edgartools release reading `EDGAR_RATE_LIMIT_PER_SEC`; `backend/tests/unit/test_data_completeness.py` (2 lines, the env-map assertion); `docs/CONFIGURATION.md` (+9/−) and `docs/OPERATIONS.md` (+36/−, per-process budget section; corrects the `database.checked_out` threshold, B33) |
| Configured fleet assumption | Two independent SEC buckets per process (the app's `SEC_RATE_LIMIT_PER_SECOND`, code default 10; edgartools' `EDGAR_RATE_LIMIT_PER_SEC`, library default 9, read once at import). Today: 19 req/s sustained per process, 29 in its first second, 190 across ten processes (two service instances + eight jobs) against SEC's 10 req/s per user "regardless of the number of machines" (record 02 D3). With the patch: 1 + 1 = 2 req/s sustained per process, 3 in its first second; ten processes 20 sustained / 30 first second; the Monday 07:00 UTC overlap (two instances + two jobs) 8 sustained. The gate's docstring states what is NOT bounded by configuration: rollout-overlap instances, manual job executions and operator one-shots, first-second bursts, any request outside both limiters. |
| Local gates | targeted tests pass (`sec-gate-2.log`: ruff all checks passed; pytest exit 0); first run (`sec-gate.log`) exit 1 was the harness environment, re-run clean |
| Decision needed from the founder | (a) apply with `1 + 1` on every process as written, or (b) change the numbers (for example a larger app budget on the service than on the jobs), or (c) keep holding. Then: the founder applies and commits the patch (the chief's commit was classifier-denied), opens the PR; marking it ready runs `copilot-eval`, so the chief reserves from the dearest measured run (≥ USD 0.03) before it leaves draft; merge deploys the new env to the service and all eight jobs through the normal `deploy-backend` job. |

## Option C — query-route readout contract draft delivered (addendum)

The bounded COO worker (`coo-query-route-contract-draft-01`, dispatch `COO-QUERY-ROUTE-04`, eight inputs hash-verified;
dispatched 18:37Z, returned 18:52Z; pass) delivered
`handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md` (45,384 bytes, SHA-256 `401b82ed08f2b23147cb1582075c149bf79f4c056368990c030e35593ecff3a8`): the
query-route readout contract in G2/G3 shape with placeholder-only HogQL per reporting group, the count-bracketed
pagination rule (caps labelled connector-reported, to be confirmed on first use), the private retention rule (hashes and
counts only in the repository), the operator-identity rule written as a decision for the founder with the CEO, a no-cost
dry-run plan that is explicitly not executed, what the contract settles and does not settle for G1–G5, risks with owners.
No connector call, no customer data, no spend; ticket 76581 open and not resent. This addendum post-dates the worker's read:
the manifest's record-08 input hash `9a19701d…` (13,211 bytes) names the pre-addendum version at `1b5e0a47`, where all eight
inputs matched. Worker deviations: (1) the manifest's read-scope commit e1b00514 precedes the worker's HEAD 1b5e0a47 by the manifest's own commit only, all eight input hashes matching at HEAD; (2) the file is 45,384 bytes after one in-place trim from 47,976 (about 384 bytes over the guidance; no required item removed); (3) one file created and then edited in place in the same run; (4) an observation, not a deviation: a PostHog exec tool appeared in the worker's deferred tool roster (never loaded or called), which the draft records as evidence of presentation only, not of function or transcript isolation, and which does not make such a worker an eligible operator. Open questions
for the founder: Q1 which operator-identity option is recorded with the CEO in the G1 access decision (O1 a dedicated non-executive remote session with the connector attached by the founder; O2 a founder-operated run with a hashing script; O3 a child worker of the executive session, weakest isolation; O4 no operator until the G4 frozen roster exists); Q2 whether a schema read of project 117863 (table, column and event names, no rows) is within existing authorization, and whether PostHog's terms support the MCP execute-sql route as a reporting route; Q3 which private store holds readout responses and under what custody rule, given the classifier-denied receipt copy; Q4 whether the six invented-literal dry-run probes are authorised and by which context. **Disposition:** a draft; nothing adopted; G1–G3 stay BLOCKED until the founder with the CEO
accepts the contract, decides the operator identity and makes the explicit access decision for the route.

**Revision 2** (2026-10-05T19:07:44Z): the three-lens review of `39c74850` found one should-fix and five nits in the draft (the grouped-query
count bracket was incoherent for a composite GROUP BY; the retention exception for invented-literal probe responses was
unscoped; the event-name column was an unplaceholdered schema assumption; the plan-coverage sentence over-generalised record
07; the length guidance was unsourced; the terminal-page rule was off by one row). The same registered worker (closure 152)
applied them, staged outside the repository while the reviewers were reading, and the chief moved the file into place: revision
2 as placed is 49,767 bytes, SHA-256 `448f4f12bee69a4c543cb14b22a785a9a5754af0d87acd6de834135ff180253d` (the worker's staged revision 2 was 49,766 bytes,
`9daf5f58…`; one chief edit before placement replaced the literal session upload-directory path in its "Not read, by rule" row
with "the session's upload area", a policy-lens finding; no other byte changed); its §7.1 lists the six changes against the revision-1 hash `401b82ed…`
(45,384 bytes, committed at `39c74850`). The worker's disclosed deviations: the file grew above the dispatch message's length
guidance because unrelated text was kept byte-identical; "six dry-run calls" was written as "the dry-run calls (six probe
shapes; several calls each)" for accuracy; the count-bracket correction was carried into §2.4 and §4 P4 for consistency.

## Founder instruction received ~19:12Z — PostHog ticket 76581 resolved; COO export capability test dispatched

| Item | Value |
|---|---|
| Event | The founder relayed (screenshots) that PostHog support (Luke) resolved ticket **76581**: "I've gone ahead and enabled the flag for your organization" (HogQL file-download batch exports, closed beta, enabled per team), with the docs link for file-download exports. **Support-confirmed enablement is recorded; actual export validation is pending** — nothing is credited until a run completes and its files are verified. |
| Instruction (verbatim intent) | Assign the existing COO to the next bounded reporting dependency: (1) record support-confirmed enablement; (2) run the previously agreed capability test for project 117863 — exactly three invented literal rows, no events, persons or customer-table access; (3) retain the exact query, run identity, terminal status, completed row count, every returned file part and file hashes, and verify the downloaded contents contain exactly the three expected rows; (4) complete the existing independent file-input contract review against those actual artifacts, reusing the released report consumer where compatible; (5) report which reporting prerequisites this closes and the next executable dependency; do not mark cohort reporting or beta admission complete from a synthetic test. No customer-data export, no inferred consent, no subscription change, no expansion of spending permissions; the USD 25 authorization is DeepSeek, not a PostHog charge. If the environment lacks the required PostHog tools, report the exact missing access and provide a narrowly scoped Codex-worker handoff. |
| Tooling check (chief, read-only) | The connector in this session exposes `file-download-batch-exports-create / -retrieve / -count-rows-create / -cancel-create` (plus the generic batch-export tools); the `hogql` model takes the query verbatim, `JSONLines`, no bounds when the query has no placeholders. The connector's own skill states that the final file download uses the REST endpoint `GET /api/projects/{project_id}/file_download_batch_exports/{run_id}/download/{part}/` "with the same PostHog authentication context as other API calls" — an authentication context this container does not hold (no environment variable name contains POSTHOG; connector credentials are never extracted). So steps 1–3 run here up to run completion, record count and file identities; the file download and the byte-level three-row verification need the founder's authenticated context or a Codex worker with it (handoff prepared by the worker). |
| Exact agreed query | `tasks/review-evidence/beta-readout-2026-09-30/literal-projection.hogql`, SHA-256 `87c47aa644ef127eb8189db6e56cf0755d3158be59dcdadb74cecb33c253b3e4` — the same query bytes the September 30 export attempt sent (its receipt's `query_sha256`); three invented rows from literal `UNION ALL` SELECTs, 21 aliased columns, no events/persons/sessions table |
| Dispatch | Manifest `dispatch/COO-EXPORT-VALIDATION-05.json` (SHA-256 `f7f0abfad0accb8d10c6dfd9881c7e2015089b51c05897adb3f51cc45fa201cf`, 9,414 bytes; ten input hashes; procedure: count-rows first, expected 3; one create; poll to a terminal status; no download without an existing authentication context; stop on any pricing, plan or billing signal). Bounded COO worker `coo-export-capability-test-01` dispatched 19:22Z (registered as actual in closure 153). The independent file-input contract review (G3) is a separate context, dispatched when the artifacts exist. |
| Boundaries | No customer or participant data; no events/persons/sessions export; no `execute-sql`; one export run; no subscription or plan change; no PostHog charge authorized (a pricing signal is a stop condition); USD 0 DeepSeek. Ticket 76581 is resolved by support; nothing is resent. |
| State | Support-confirmed enablement: RECORDED. G2 complete literal file receipt: PENDING the run and the file verification. G3: PENDING. G1 explicit access decision for the route: still the founder's with the CEO (the enabled flag is capability, not the programme's access decision). Cohort reporting and beta admission: NOT complete; a synthetic test cannot complete them. |

**Outcome (addendum, 2026-10-05T19:35:53Z).** The worker returned 19:32Z (run file recorded 19:32:44Z) with `pass`: all ten inputs verified before any connector call;
`count-rows` → 3 (= expected); one `create` → run **`01a10d89-1ee8-0000-3e2c-9000712c9502`**; first `retrieve` → **Completed**,
`records_completed` **3**, one file part **`01a10d89-3a26-0000-56f3-e1f6c4004610`** (JSONLines, uncompressed, single file); no pricing, plan or
billing signal; no cancel; no other export tool called (`learn` ×2, `info` ×4 only). Download not attempted: no authenticated PostHog HTTP context exists here and
none was sought; the endpoint and a narrow Codex-worker handoff (one authenticated GET following the single redirect, save
raw bytes, never store the signed URL, verify exactly three rows with the 21 aliases) are recorded in the run file. Outputs:
`handbacks/coo/export-validation-01/EXPORT-CAPABILITY-RECEIPT-01.md` (13,031 bytes, `beb2fff8…`) and
`export-capability-run.json` (31,051 bytes, `328dbd44…`); both scanned by the chief for credentials, signed URLs and local
paths (none). **Closes:** support-confirmed enablement, validated (the 403 did not recur; the `hogql` model was accepted).
**G2:** run completed, file verification pending the download access. **Open:** G1 explicit access decision for the route, G3
(independent file-input contract review against the actual part, dispatched when the part is available), G4, G5. Cohort
reporting and beta admission are NOT complete. Next executable dependency: the founder downloads the part (PostHog UI run
page, or the handoff with their personal API key) and provides it; then the G3 reviewer. 0 DeepSeek calls; USD 0.

## Registration (closure 151)

`control/source-context-exclusion-151.json` resolves the PR #1098 delta reviewer's label to its launch-time identity
(17:44Z) and pre-registers the record-08 PR reviewer and the COO query-route contract worker as provisional labels; closure 152
resolves the latter after its return. Closure 153 registers this PR's review-workflow contexts, the export capability
test worker (actual) and the delta reviewer (provisional). The log-cost helper (closure 150) was re-used
once as the same context; no other context was created.

## Spend

34 DeepSeek calls (the reserved run; telemetry USD 0.025568, of which USD 0.015568 unreserved); 0 active reservations;
1 ledger event (4). Afternoon total across records 07 and 08: 63 calls, USD 0.031143, of which USD 0.021143 unreserved.
