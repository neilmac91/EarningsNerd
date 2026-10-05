# Decision record 07 — afternoon execution with the founder away: B62 cause established, PostHog query route evidence, readout diagnostics, custody tooling (chief, 2026-10-05)

Recorded 2026-10-05T17:09:29Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Amended 2026-10-05T17:39:08Z after the three-lens review of head `de8a525d`: two addenda (both bounded workers
returned), the caps-source labelling, the custody-run timing, two provenance/location notes; nothing else in the record
changed. Amended again 2026-10-05T17:56:53Z after the delta review of `2c4e6926`: chief defect recorded (one paid CI run triggered without a
reservation; ledger event 3), classifier denial 5 (uploaded archives not opened), three delta-review nits. Context: the
founder was away from the MacBook from about 17:05Z and had regained access by 17:29Z, and asked the chief to execute
independently whatever the plan allows. Nothing below releases inputs, dispatches the planner, admits capacity, releases a
hold, invites a user, changes a production or cloud configuration, adds load or extends a timebox; the one spend is the
chief defect recorded below (USD 0.005575 by telemetry, unreserved), with one reservation (USD 0.010000) for its required
re-trigger.

## R1 — custody check cannot be executed by the chief; tooling delivered

The two private H20 planning folders live on the founder's MacBook and no local session is reachable from this container.
The chief delivered a read-only check script (`tools/h20-custody-check.sh`, SHA-256
`31046549905004e53ff035be5141cdfc159c85de06fc68752e1ab2a483d23b8b`, 2,134 bytes; also attached in the session) that
prints per file the iCloud materialisation status, byte length and SHA-256, and per folder a `TOTAL=` line; it never prints
contents and writes nothing inside the folders. Reading a file for its hash materialises an iCloud-evicted copy (the
script's `WAS_DATALESS` status and `MATERIALISED_BY_THIS_READ` count record exactly that, like Finder's Download Now), so
custody counts observed after the run differ from the 2026-10-04/05 cloud-only counts for that reason and the
materialised count is the record of it. The script lives with this record under `tools/` rather than in
`backend/scripts/` because it is a founder-side macOS tool, not a repository script run by the service or CI; it is not
executable in the tree (mode 100644) and is run with an explicit `bash`. Runs: one placeholder run (both folders
`MISSING_DIR`, on the MacBook, pasted to the chief at 16:54Z), one single-argument run (usage
message), then the real run started 2026-10-05T17:29:39Z on the MacBook with both folder paths (first line `.DS_Store
LOCAL`); its two `TOTAL=` lines had not reached the chief at the time of this amendment. Until the totals, Astra's
manifest comparison and the planner resumability check arrive, R1 stays exactly where record 06 left it: receipt
NOT_RELEASED, planner undispatched, 150 of 180 minutes remaining.

## R3 — B62 cause established by the existing read-only `logs-probe` (no code change)

| Item | Value |
|---|---|
| Dispatch | `ops.yml` `logs-probe` on main `f8091c53`; run **37345946128** (Ops #67), job 111884413046; 17:06:32–17:06:55Z; conclusion success (the probe itself reports the denial) |
| Result | `logs-probe: logging.read DENIED (rc=1)` — `PERMISSION_DENIED: Permission denied for all log views`, authenticated as `github-deployer@earnings-nerd.iam.gserviceaccount.com` (the identity as printed in the run's public Actions log by the probe step; recorded for that reason, consistent with record 02 D5) |
| Reading | The Ops Workload Identity Federation identity lacks a Logging read role (for example `roles/logging.viewer` or a log-view binding). The Monitoring 403s of the 2026-10-05 readout are the same class of failure on the Monitoring API (a missing `roles/monitoring.viewer`-equivalent) unless the receipt's error detail shows otherwise once the diagnostics change below is deployed. The 2026-10-04 receipt (COO first deliverable) carried Monitoring samples, so a role present on 2026-10-04 is absent now; the cause of the change is not established here. |
| Decision | **Founder's cloud-configuration decision** (the chief makes no IAM change). The smallest grant that unblocks the B32 observation route is two project-level read-only roles on that service account: `roles/logging.viewer` and `roles/monitoring.viewer`. Both are viewer roles; neither grants write or admin access. The founder may also check the IAM policy change history in Cloud Audit Logs before re-granting. |
| Effect when granted | One more bounded `capacity-readout` over a job-overlap window would then carry DB-connection, request and error-log samples (B32, B56, part of B39); until then the COO HOLD stands (disposition update 01). |

## R3 — G1/G2: a supported query route exists (PostHog MCP, invented literals only)

| Item | Value |
|---|---|
| Route | The official PostHog MCP connector attached to this session; `execute-sql` (HogQL) against the active project |
| Project identity | `project-get` returned project **117863** ("Default project", timezone UTC); the same project the G1 ticket 76581 concerns |
| Probe | one query of invented literals, no collected data: `SELECT 1 AS probe_a, 'alpha' AS probe_b, toDateTime('2026-10-05 00:00:00') AS probe_c` at 2026-10-05T17:07Z |
| Result | one row `1 | alpha | 2026-10-05T00:00:00Z`; response as returned (193 bytes) SHA-256 `c9c1961ec63b04f26842b9878fe18c77e7e36b397e420a26dc35c5df0cff9b0b` |
| What it shows | HogQL queries run and return rows through a supported, non-batch-export route; this is the "tiny invented-literal format probe" the COO's G2 definition names, on a query route rather than a file-export route |
| What it does not show | No customer or participant data was read and none may be read by an executive context; the route's completeness guarantees differ from the batch-export contract G2/G3 were written for (pagination; a 100-row default cap and a 500-row maximum as stated by the connector's `execute-sql` command description read in this session on 2026-10-05, not independently verified and not stated by the connector's tool schema; no file parts); G1's exit still requires an explicit access decision for whichever route the COO adopts |
| Decision | Evidence handed to the **COO** for the G1–G3 route decision: whether a query-based readout contract (bounded queries, explicit `LIMIT`/`OFFSET` pagination, retained query text and result hashes, denominators preserved) can replace the blocked batch-export contract. Not a G1 closure; no customer query; ticket 76581 retained and not resent. The `project-get` response also carries two public client tokens; they are not recorded anywhere. |

## R3 — readout diagnostics (engineering change, bounded)

`ops/capacity/readout.py` recorded only `http_403` for the failed channels. A bounded engineering worker (closure 148)
changes it to record a structured error reason — `status`, `code`, the `ErrorInfo` `reason`/`domain` and a message
truncated to 240 characters, parsed from at most 8 KiB of the error envelope, never the raw body or headers — and extends
`backend/tests/unit/test_capacity_readout.py` accordingly. Outcome, hashes and checks: see the addendum below. The change is not dispatched after merge; the next readout is the COO/CEO decision after the IAM grant.

## Chief defect — unreserved paid CI run on marking this PR ready (ledger event 3)

| Item | Value |
|---|---|
| What happened | The chief marked PR #1098 ready for review at 17:44:19Z. The path-filtered paid workflow `Copilot filing fidelity` (`.github/workflows/copilot-eval.yml`, `paths: backend/**`; this PR carries `backend/tests/unit/test_capacity_readout.py`) ran: run **37350658792**, job 111900387690, head `2c4e6926`. No reservation existed in the successor ledger — contrary to record 02 (marking such a PR ready needs a chief reservation for `copilot-eval`, about USD 0.01), a rule the chief had recorded and did not apply. |
| Response | Cancellation requested at about 17:45:50Z (accepted) and the PR returned to draft. The cancel did not interrupt the running step: `Run every verified question three times` ran 17:45:57–17:46:44Z to completion (expected 18, completed 18, scored 17, passed 17, errors 1; exit code 1), then the evidence upload; the job's conclusion reads `cancelled` although every step completed. A cancel request is not a control. |
| Calls and cost | 29 `deepseek-flash` calls (17:46:00–17:46:43Z, all `success`; 901,169 prompt tokens of which 895,734 cache hits; 3,461 completion tokens); telemetry `estimated_cost_usd` sum **USD 0.005575**, computed twice from the public job log: by the chief and by a read-only helper subagent (requested model `claude-haiku-4-5`, launched 17:50Z; registered as an actual context in closure 150, `control/source-context-exclusion-150.json`, after the delta reviewer found it unregistered). A telemetry estimate, not an invoice. |
| Result of the run | `accepted: false` on the known pre-existing withholding `Unsupported prose quotation: quotation_not_in_source` (one of 18), disposed on earlier runs as not caused by the PR under the RUNBOOK red-copilot rule; this PR touches no Copilot code. Recorded, not retried. The check is not one of the six required checks. Evidence: GitHub artifact `copilot-fidelity-37350658792` (id 11362123334, 76 files, 78,712,337 bytes, digest `68edeb78…`, expires 2027-01-03). |
| Ledger | **Event 3** written 2026-10-05T17:54:35Z by the chief (sole writer; recorded in the repository 17:56:53Z) under the hash chain (`previous_sha256` `f4dd36fb…`): the run recorded as use against the shared authority (known use 0.547516 → **0.553091**, calls 297 → 326; cumulative recorded usage 2,385 calls / USD 4.337340), holds unchanged (1.881713), and one **reservation of USD 0.010000** for the single required `ready_for_review` re-trigger of this PR (the PR must leave draft to merge; the trigger cannot be avoided for a PR touching `backend/**`); conditional unreserved headroom 22.570771 → **22.555196**. Document SHA-256 `6c2dc45f76b5405730c6079d2a08dee2507125a64b0afa1f759c533ac71449c5`, 29,012 bytes. Event 4 will record the re-trigger's actual telemetry cost and release the unused part of the reservation. |
| Rule | Before marking any PR that touches `backend/**` or `copilot-eval.yml` ready, the chief writes the reservation first; a cancel request is never relied on to stop a paid job. Recorded here and in the CHECKPOINT as a chief defect. |

## R1 — archives uploaded to the session were not opened (classifier denial 5)

At about 17:52Z the founder uploaded two archives, named for the two H20 planning folders, into this session's upload
area and asked the chief to proceed. The chief's one attempt to unpack them and compute per-member byte lengths and SHA-256s
for the custody check (hash and length only, no content read) was denied by the platform's auto-mode classifier
(PII Data Handling). Under the denial's terms the chief does not pursue that outcome through another tool, sub-agent or
turn, so no custody verification, planner dispatch or input release from this session uses the uploads; the archives were
not opened and nothing from them is recorded. The founder-side route stands unchanged: the two `TOTAL=` lines from the
custody script, Astra's manifest comparison, the planner-resumability check in the Codex app, then the release receipt.
Whether the uploads remain in the session is the founder's decision; the chief recommends removing them, since no step the
chief may take needs them here.

## Registration (closure 148)

`control/source-context-exclusion-148.json` registers the readout worker (actual), resolves the record-06 PR reviewer's
identity, and pre-registers the record-07 review workflow's lenses and refuters as provisional labels. The chief context
itself ran the PostHog probe and dispatched the logs probe; no new context was created for either. One omission, stated
here rather than hidden: the COO report-route proposal worker (dispatch `COO-REPORT-ROUTE-03`, 17:11Z) was dispatched
after closure 148 was recorded (17:09:29Z) and was not pre-registered; closure 149 (`control/source-context-exclusion-149.json`,
appended at this PR's final head) registers it as an actual context, resolves the review workflow's lenses and refuters
to their agent ids, and pre-registers the delta reviewer of this PR's final head as a provisional label. Closure 150
registers the read-only log-cost helper subagent of 17:50Z (actual) that the first delta check found unregistered; the
delta reviewer's own label stays provisional until the next closure, as usual.

## Readout diagnostics — delivered (addendum)

The bounded worker (closure 148, `cto-readout-error-detail-01`; dispatched 17:07Z, returned 17:15Z) delivered commit
`de8a525d`: `ops/capacity/readout.py` reads at most 8 KiB of a failed call's error envelope and keeps only
`error.status`, `error.code`, the first `ErrorInfo` `reason`/`domain` and a message truncated to 240 characters as
`error_detail` beside the existing `error` string; the `(data, error)` return shape is unchanged; non-JSON bodies record
a sentinel; valid JSON without a Google error envelope records nothing; the detail is reset on every request so a later
transport failure never carries a stale reason. One disclosed harness fix during authoring (a closed-stream `tell()`
replaced by counting consumed bytes). Checks by the worker and re-run by the chief at `de8a525d`: 4 passed; `ruff check .`
clean; `py_compile` clean; CI green.

The three-lens review of head `de8a525d` (CHECKPOINT review record) found no blocker, one should-fix and three nits on the
code, all applied by the chief in this PR's final head (the worker had returned; one writer per component): `error_detail`
can no longer abort a receipt (any exception while reading or parsing the body, including a parser `RecursionError` on a
deeply nested body or a missing stream, becomes the sentinel and `request()` still returns `http_NNN`); `status`, `reason`
and `domain` are capped at 64 characters each (`MAX_ERROR_FIELD`); a valid envelope cut at the 8 KiB cap records
`truncated_or_non_json` instead of the plain `non_json_or_unreadable`; a message cut at 240 characters carries
`message_truncated: true`; the receipt's `limits` block names `max_error_body_bytes` and `max_error_message_chars`
(additive keys, `schema_version` unchanged). Tests: the two vacuous bound assertions were removed, two tests added (field bounds and the
limits keys; never-aborts, including `fp=None`) and one renamed and extended (truncation naming) — 6 passed; `ruff check` clean on
both files; `py_compile` clean; `bandit -ll` on the module: no findings. SHA-256 at the final head:
`ops/capacity/readout.py` `d76591d52f67301d4003dc7fadb9740ad9803401e5f87759162c10a455df1a92` (15,225 bytes);
`backend/tests/unit/test_capacity_readout.py` `0319df33830e5747c799e7318c53c2c7f31766c6cd83a5b4507906fba21cca65`
(14,170 bytes). Not dispatched after merge; the next readout is the COO/CEO decision after the founder's IAM grant.

## Beta reporting route — COO proposal delivered (addendum)

The bounded COO worker (`coo-report-route-proposal-01`, dispatch `COO-REPORT-ROUTE-03`, seven inputs hash-verified;
dispatched 17:11Z, returned 17:20Z) delivered `handbacks/coo/REPORT-ROUTE-PROPOSAL-01.md` (33,854 bytes, SHA-256
`0916b5f27190cb7805b561d82498552697375071f14121b5a91901ce24017810`): the blocked batch-export contract side by side with
a query-based readout contract over the official PostHog MCP route, in the G2/G3 shape (retained query text and UTC
half-open window, a count-bracketed pagination-completeness rule, private retention with hashes, an operator-identity rule
under which no executive context runs a customer query, a review checklist), what the route settles and does not settle
for G1–G5, ten risks with owners, and a three-option decision table for the CEO/founder with no recommendation and no
spend. Two evidence-derived cautions carried forward: the probe response's `results` field is pipe-delimited text with no
row count, limit, offset or run id (so completeness must be constructed by a separate count query, and compatibility
with the released consumer is not established), and the connector was attached to the chief's interactive session, so
whether a non-executive operator context can hold it is not yet established. **CEO disposition:** the decision is the
founder's with the CEO (a substitute reporting contract is never silently approved); the chief's assessment for that
decision is option C (keep ticket 76581 open and prepare the query route) because it adds no cost and loses nothing,
subject to the operator-identity question being answered first. G1–G3 stay BLOCKED; nothing is adopted here.

Binding note: dispatch manifest `COO-REPORT-ROUTE-03.json` binds this record at its pre-amendment hash
(`d4468a18e04f9f9ff6c4939cef526e33ea40f78e0feca5786346531ad7147bd0`, 6,247 bytes), which is the version the worker read;
the manifest is a record of what was dispatched and is not edited. This amendment postdates the worker's return (17:20Z)
and changes none of the facts the worker was given except the labelling of the 100/500-row caps as connector-stated and
not independently verified, so the proposal's pagination-completeness rule inherits that caveat; confirming the caps
against the connector's own `execute-sql` description is part of the route decision, not a correction to the proposal.

## Spend

29 DeepSeek calls — all by the unreserved `copilot-eval` run recorded above as a chief defect (telemetry USD 0.005575);
no other provider call; 1 reservation (USD 0.010000, for the one required re-trigger); 1 ledger event (3). The PostHog MCP
calls are covered by the existing PostHog plan; the Ops dispatch costs no provider call.
