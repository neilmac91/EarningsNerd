# Decision record 07 — afternoon execution with the founder away: B62 cause established, PostHog query route evidence, readout diagnostics, custody tooling (chief, 2026-10-05)

Recorded 2026-10-05T17:09:29Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Context: the founder is away from the MacBook until later today and asked the chief to execute
independently whatever the plan allows. Nothing below releases inputs, dispatches the planner, admits capacity, releases
a hold, invites a user, changes a production or cloud configuration, adds load, extends a timebox or spends.

## R1 — custody check cannot be executed by the chief; tooling delivered

The two private H20 planning folders live on the founder's MacBook and no local session is reachable from this container.
The chief delivered a read-only check script (`tools/h20-custody-check.sh`, SHA-256
`31046549905004e53ff035be5141cdfc159c85de06fc68752e1ab2a483d23b8b`, 2,134 bytes; also attached in the session) that
prints per file the iCloud materialisation status, byte length and SHA-256, and per folder a `TOTAL=` line; it never prints
contents and writes nothing inside the folders. The founder ran it once with placeholder arguments (both folders
`MISSING_DIR`) and will re-run it with the real folder paths. Until the totals, Astra's manifest comparison and the planner
resumability check arrive, R1 stays exactly where record 06 left it: receipt NOT_RELEASED, planner undispatched,
150 of 180 minutes remaining.

## R3 — B62 cause established by the existing read-only `logs-probe` (no code change)

| Item | Value |
|---|---|
| Dispatch | `ops.yml` `logs-probe` on main `f8091c53`; run **37345946128** (Ops #67), job 111884413046; 17:06:32–17:06:55Z; conclusion success (the probe itself reports the denial) |
| Result | `logs-probe: logging.read DENIED (rc=1)` — `PERMISSION_DENIED: Permission denied for all log views`, authenticated as `github-deployer@earnings-nerd.iam.gserviceaccount.com` |
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
| What it does not show | No customer or participant data was read and none may be read by an executive context; the route's completeness guarantees (pagination, 100-row default cap, 500-row maximum, no file parts) differ from the batch-export contract G2/G3 were written for; G1's exit still requires an explicit access decision for whichever route the COO adopts |
| Decision | Evidence handed to the **COO** for the G1–G3 route decision: whether a query-based readout contract (bounded queries, explicit `LIMIT`/`OFFSET` pagination, retained query text and result hashes, denominators preserved) can replace the blocked batch-export contract. Not a G1 closure; no customer query; ticket 76581 retained and not resent. The `project-get` response also carries two public client tokens; they are not recorded anywhere. |

## R3 — readout diagnostics (engineering change, bounded)

`ops/capacity/readout.py` recorded only `http_403` for the failed channels. A bounded engineering worker (closure 148)
changes it to record a structured error reason — `status`, `code`, the `ErrorInfo` `reason`/`domain` and a message
truncated to 240 characters, parsed from at most 8 KiB of the error envelope, never the raw body or headers — and extends
`backend/tests/unit/test_capacity_readout.py` accordingly. Outcome, hashes and checks: see the addendum below once the
worker returns. The change is not dispatched after merge; the next readout is the COO/CEO decision after the IAM grant.

## Registration (closure 148)

`control/source-context-exclusion-148.json` registers the readout worker (actual), resolves the record-06 PR reviewer's
identity, and pre-registers the record-07 review workflow's lenses and refuters as provisional labels. The chief context
itself ran the PostHog probe and dispatched the logs probe; no new context was created for either.

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 0 ledger events. The PostHog MCP calls are covered by the existing
PostHog plan; the Ops dispatch costs no provider call.
