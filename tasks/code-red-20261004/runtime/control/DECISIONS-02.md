# Decision record 02 — post-Astra decision set (chief, 2026-10-04)

Recorded 2026-10-04T17:45Z, amended 2026-10-04T17:50Z (D3 and D9 after both refuters returned at 17:43Z and 17:47Z) and 2026-10-04T17:59Z (D3 execution note); corrected 2026-10-04T18:09Z after the independent PR review (ten processes/190, window label, burst semantics) by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`,
runtime-reported model `claude-fable-5-1`). Inputs: Astra's read-only report relayed by the founder on
2026-10-04 (ledger byte-identity confirmed; timebox balance unrecorded; backfill-facts Monday 07:00 UTC
confirmed; zero spend, zero writes), the COO disposition's eight items, the CTO handback revision 3, two
read-only Ops reads (`PRODUCTION-CONFIG-OBSERVATION-20261004.md`), SEC's published fair-access policy and
DeepSeek's published rate-limit page (both read 2026-10-04). Founder instruction: execute the open actions
and take the decisions with the owning officers' input. Nothing below admits capacity, releases a hold,
invites a user, changes a production flag, adds load or spends.

## D1 — Successor spend ledger designated (CEO, CFO evidence)

- Condition (b) of `LEDGER-ACCESS.md` is met: Astra confirmed the live
  `outputs/next-stage-20261003/spend-and-reservation.json` is byte-identical to snapshot
  `99c7259ff3e5f0f2c40b60e6b557bbc711222be0e261b9277f3105e9bca8fc7b` (18,351 bytes) and that no
  reservation, hold or event was added after 2026-10-04T09:35:21Z. The original writer is retired.
- Successor store: a **private claude.ai artifact titled "CODE RED Spend Ledger"** in the founder's
  account, published 2026-10-04T17:39Z. Its authoritative document `spend-and-reservation.json`
  (20,272 bytes, SHA-256 `53e8486800e193277c5be5c14a786cfeff90d3b4fa212be1c044c7343fea9f78`) is the
  snapshot plus a `successor_designation` block (predecessor hash, hash-chain rule, state at designation,
  empty `events`). Page SHA-256 `d38dc3e031b278a2dbabf57426159816650291e6bcb120290c5af2375daa17bb`.
  The URL is deliberately not recorded in this public repository (D5); it is in the founder's artifact
  gallery and was handed to the founder in the session.
- Writer: the chief only. Every later write appends an event carrying the previous document's SHA-256.
  Paid dispatch stays HELD until a reservation is written there. Active reservations: 0.
- State carried unchanged: 2,356 calls / USD 4.331765 cumulative telemetry estimate; USD 0.547516
  recorded against the founder's USD 15 shared authority; USD 1.881713 retained holds; USD 12.570771
  conditional unreserved. Unknown cost is never zero. Astra's local file is frozen reference; Astra is
  read-only on the ledger.

## D2 — R1 source-engineering refinement: one explicit bounded allowance (CEO with CTO)

- Fact (Astra): the timebox balance of the source-engineering H20 packing/closure refinement was never
  recorded. Declaring it exhausted would invent a fact; leaving it open-ended would be a new allowance by
  drift. `R1-STATUS.md` therefore stays `BLOCKED_SOURCE_OWNED_PACKING` until the work below returns.
- Decision: **one bounded allowance of 3 focused hours of local, founder-side work**, scoped to the
  packing/closure refinement of the 27 remaining H20 items, executed by a fresh eligible source-only
  planner that Astra bootstraps through the existing process (cloud-only custody bytes restored only
  through the existing custody process). Conditions: USD 0 DeepSeek and no paid dispatch (any paid step
  first needs a reservation in the successor ledger); engineering-safe return contract (counts, hashes,
  status — no source packets, candidate outputs, judge material or custodian mappings cross the
  boundary); the planner's context identity is reported before any executive context reads its output
  and is registered in the next exclusion closure; Astra authors no source material and remains
  read-only on the ledger. On return or expiry the chief sets `R1-STATUS.md` to
  `REFINEMENT_RETURNED` (with counts) or `TIMEBOX_EXHAUSTED`.

## D3 — SEC aggregate-rate hazard: per-process budgets as risk reduction (CTO draft; founder numbers)

- Evidence (Ops reads; the arithmetic refuter's finding, verified by the chief in the pinned library
  source):
  - No `SEC_RATE_LIMIT_PER_SECOND` override on the service or on any of the eight jobs → the app's
    singleton bucket runs at the code default 10 req/s per process with capacity equal to rate
    (`backend/app/config.py:33`, `backend/app/services/sec_rate_limiter.py:57`).
  - A **second, independent, process-global bucket** paces every edgartools call (submissions,
    filing objects, XBRL through `backend/app/services/edgar/client.py`): edgartools 5.58.0
    `edgar/httpclient.py:196-202` reads `int(os.environ.get("EDGAR_RATE_LIMIT_PER_SEC", "9"))` into a
    pyrate-limiter token bucket created once at import (`:433`, `HTTP_MGR`). The app documents this
    bucket (`backend/app/integrations/sec_api.py:9-11`) and never wraps it; no deploy sets
    `EDGAR_RATE_LIMIT_PER_SEC`. Source SHA-256 of the file read: `63675da6f438d5e06422882a07b20802eded59a944a8357242969b53d7876ecc`.
  - Per-process configured sustained ceiling is therefore 10 + 9 = 19 req/s. First second: the app
    bucket starts full (capacity equals rate, so 2× its rate), while edgartools' pyrate-limiter bucket is
    a sliding window that admits at most its rate per rolling second (verified in pyrate-limiter 4.3.0
    `InMemoryBucket.put`), so 20 + 9 = 29 per process. Fleet: all ten processes (two instances + eight
    jobs) 190 req/s; Monday 07:00 UTC scheduled overlap (two instances + pregenerate + filing-scan +
    backfill-facts) 95; the hourly
    filing-scan window 57 — against SEC's 10 req/s per user. Handback B36's 20/40/50 was a floor (D9).
  - The limiter waits rather than rejects (`_wait_for_token`), so exceeding the aggregate shows as
    `rate_limit_hits` climbing on the service while a job runs, or as SEC 403/429 and
    `circuit_breaker.sec_edgar.state`.
- Decision: the CTO prepares a **draft PR, held unready**, setting **both** per-process budgets on
  every process: service `SEC_RATE_LIMIT_PER_SECOND=1` and `EDGAR_RATE_LIMIT_PER_SEC=1` per instance
  (2 req/s per instance; 4 across the two instances); each of the eight jobs `1` and `1` (2 req/s per
  job). A rule-12 unit gate asserts those configured values and the arithmetic stated here. Claimed
  configured sustained sums: steady 4; hourly filing-scan window 6; Monday 06:00 UTC (pregenerate +
  scan) 8; Monday 07:00 UTC with backfill-facts and a still-running pregenerate 10; a daily EFTS job
  over a running scan 8 — every scheduled overlap in B23 ≤ 10. Honestly **not** claimed: all ten
  processes at once (20); first-second bursts (twice the app budget plus the edgartools budget: 3 per
  process, 15 at Monday 07:00); rollout-overlap
  instances; manual job executions and operator one-shots; any path outside both limiters; SEC's
  enforcement window. Why 1 rather than 2 on the service: with two buckets per process, 2 + 1 per
  instance already puts Monday 07:00 at 12 > 10; the latency cost (a generation's fetch phase queues at
  1 req/s per path per instance against the 120 s pipeline timeout) is the founder's to weigh. Both
  numbers are the founder's to change (COO item routed to the founder, Slice B).
- Hold reason: marking the PR ready triggers `copilot-eval` (about USD 0.01), which needs a reservation
  in the successor ledger; the draft itself costs USD 0. Env changes apply only at the next backend
  deploy. The same PR fixes the unreachable `database.checked_out > 8` warning threshold in
  `docs/OPERATIONS.md` (B33) and documents both budgets.

## D3 — execution note (2026-10-04T17:59Z)

The CTO change was prepared in an isolated local worktree from main `0ad56621`: `ci.yml` pins
`SEC_RATE_LIMIT_PER_SECOND=1,EDGAR_RATE_LIMIT_PER_SEC=1` in all four deploy env maps (service,
pregenerate, the six-job loop, backfill-facts); new gate `backend/tests/unit/test_sec_process_budgets.py`
(pinned values on every process, the stated sums against `docs/OPERATIONS.md`, dev default 10, and the
pinned edgartools release reading `EDGAR_RATE_LIMIT_PER_SEC`); `docs/CONFIGURATION.md` documents the
library-read budget; `docs/OPERATIONS.md` gains the per-process budget section and corrects the
`database.checked_out` warning threshold (B33). In the local virtualenv (edgartools 5.58.0 confirmed
reading default 9) the targeted tests pass; the full backend gate result is reported in the session.
**The `git commit` of that change was denied by the platform's auto-mode classifier (reason: Production
Deploy).** Per the standing rule the chief did not pursue the commit through another tool, worker or
turn. The founder decides: apply the patch handed over in the session (SHA-256 recorded there) on a
branch of their own, change the numbers first, or drop it. Nothing deploys until a backend push to
main; marking any such PR ready still needs a chief reservation for `copilot-eval`.

Post-gate addendum (2026-10-04T18:16Z): the first full backend gate on the patch returned ruff and
bandit clean and pytest 2305 passed / 1 failed — `tests/unit/test_data_completeness.py::
test_backfill_deploy_restores_only_its_scheduled_entrypoint` pins the backfill-facts env token, so the
revised patch updates that token and also carries the burst-semantics corrections from the PR review
(edgartools' bucket is a sliding window). Revised patch handed over in the session: 19,842 bytes,
SHA-256 `e1c097f915cc1566e2b65791bdaf9a27326ef87dd7a98bf2b20f944563553e71` (supersedes the first
hand-over). Targeted tests pass on the revised patch; the full re-run result is reported in the session.

## D4 — Monday capacity readout window widened to 06:00–08:00 UTC (COO/CEO)

backfill-facts is scheduled Monday 07:00 UTC (Astra), so the earlier 06:00–07:00 window would have
missed it. The reminder Routine now fires 2026-10-05T08:10Z and dispatches one read-only `ops.yml`
`capacity-readout` over 06:00–08:00 UTC (within the operation's 2-hour input bound). Receipt → COO
(item 2 / B32). No new load, no DeepSeek call.

## D5 — Records privacy, forward-only (CEO; Astra advice 4)

The repository is public. From this record on, runtime records that carry reservation state, cost
detail, context identities beyond labels or operator-only detail live in private stores (the ledger
artifact and its successors); the repository keeps sanitized summaries, decisions and SHA-256 hashes.
No history rewrite: PR #1086's records stay as published (no credentials, customer or source material;
the cost figures there were already public telemetry estimates).

## D6 — Provisional stop conditions for the beta window (COO/CTO; provisional until COO item 8 closes)

Any one of these, seen in `/health` detail, the Monday readout or logs, holds all optional load
(pregenerate executions, backfills, broad generation) until the chief records a disposition:

1. `sec_rate_limiter.rate_limit_hits` rising on the service while a job runs, any SEC 403/429, or
   `circuit_breaker.sec_edgar.state` other than `closed`.
2. `database.checked_out` equal to `pool_size` on the service (pool 4 / overflow 0) or any pool-wait
   failure.
3. Provider HTTP 429 or `provider_admission` `rejected` > 0.
4. Any paid trigger proposed without a reservation in the successor ledger.

Nothing here admits capacity.

## D7 — Provider account limits: published figures recorded (closes handback B46 as "published, dated")

DeepSeek's public rate-limit page, read 2026-10-04: no requests-per-minute limit; account-level
concurrency limits per model (as read that day: `deepseek-flash` 2,500 concurrent, `deepseek-v4-pro`
500), with HTTP 429 above them. The fleet's configured stream ceiling (B41: 34 / 43) is far below.
Account-specific overrides are not verified; treat the figures as dated.

## D8 — Egress identity is moot for the SEC cap (closes B37 for compliance)

SEC's fair-access policy limits requests per user, not per IP: "no more than 10 requests per second,
regardless of the number of machines used". The Ops read shows no VPC egress or NAT annotation
(dynamic egress IP), so instances and jobs may present different addresses; that does not make them
separate users. B36's "assumes one shared IP" caveat is unnecessary for compliance; egress identity
stays unknown only for how SEC attributes traffic, which the decision in D3 does not depend on.

## D9 — COO item 8 (derived-row arithmetic and assumptions): refuter results

Two isolated read-only refuter contexts (arithmetic lens, assumptions lens; registered in
`source-context-exclusion-139.json`) were launched 2026-10-04T17:33Z against handback rows B08, B19,
B36, B41, B54 and §5 and returned at 17:43Z and 17:47Z. Verdicts: Appendices A and B; closure
statement under "D9 — closure".

## Owners and next actions

| # | Owner | Next action | State |
|---|---|---|---|
| D1 | CEO | None; write events only with a reservation | done |
| D2 | Founder + Astra (local) | Run the 3-hour refinement; report counts and planner identity | authorized, not started |
| D3 | CTO (patch) → founder (apply or change numbers) → CEO (reservation before ready) | Change prepared and gated locally; **commit denied by the platform classifier ("Production Deploy")**, so no draft PR was opened; patch left for the founder (see "D3 — execution note") | blocked on founder |
| D4 | Routine → chief → COO | Fires 2026-10-05T08:10Z | armed |
| D5 | All executive contexts | Standing | in force |
| D6 | COO/CTO | Replace with admitted thresholds when item 8 closes | provisional |
| D7, D8 | CTO | None; dated evidence | closed as recorded |
| D9 | Chief → COO | Both refuters folded in (Appendices A, B); COO decides whether item 8 closes | answered |

## Spend

0 DeepSeek calls, USD 0.000000, 0 reservations, 0 ledger events beyond the designation block.

## Appendix A — arithmetic-lens refuter (returned 2026-10-04T17:43Z; isolated, read-only; USD 0)

Context `…:launched-2026-10-04T1733Z:envelope-derived-refuter-arith-01` (exclusion-139). Scope: rows
B08, B19, B36, B41, B54 and §5 of handback revision 3, recomputed from the repository at main
`0ad56621` (the 24 non-`tasks/` files changed since `100fb7d6` are frontend/lessons and touch no cited
anchor). No row is arithmetically wrong on its stated inputs; four rows and §5 are true-but-incomplete.

| Row | Verdict | Finding the chief accepts | Consequence |
|---|---|---|---|
| B08 | stands | 2 instances × 1 process; overlap extra still unknown | §5's "+4" resolves that unknown to exactly one extra instance; two (+8 → 26 > 22) is not excluded |
| B19 | qualified | 25 − 3 = 22 correct; PostgreSQL 15 has no `reserved_connections` GUC (16+), so the null is "not a parameter", not an unknown; 22 is the total non-reserved backend threshold that Cloud SQL agent and non-application sessions also consume | Treat 22 as a ceiling on everyone's backends, not an application-fillable figure (COO item on DB headroom) |
| B36 | qualified | 10×{2,4,5} = 20/40/50 correct **on its inputs**, but the input "one 10 req/s bucket per process" is a floor: edgartools' internal limiter is a second, unwrapped bucket in every process (`sec_api.py:9-11`); the app bucket starts full and refills to full after any ≥1 s gap, so the first-second ceiling is 2× sustained (app bucket only; edgartools' sliding window stays at rate — see D3) and Cloud Scheduler starts Monday jobs at the same second; the hourly filing-scan (every hour) and the daily EFTS jobs (notable-filings, earnings-calendar-refresh) are SEC callers missing from the row | **Chief verification:** edgartools 5.58.0 `edgar/httpclient.py:202` default 9 req/s, env `EDGAR_RATE_LIMIT_PER_SEC`, process-global (`:433`). Per-process ceiling 19 sustained; D3 rewritten to budget both buckets; "mostly the Monday window" withdrawn |
| B41 | qualified | 17 per process and 2×17 = 34 correct; the pregenerate process is sequential (B48) with recovery after the primary stream, so its tight bound is 3 and the fleet figure 37 (43 remains a valid loose bound); none of the other seven jobs reaches the provider | Close the row's "other jobs unverified" clause; use 37 as the configured fleet stream ceiling |
| B54 | qualified | 300/1000/100 × 20 correct and enforced per calendar month; it bounds metered user-originated demand, not provider requests (retries ×3, recovery, cross-instance duplicates, unmetered job generation sit outside) | Keep as a demand ceiling only |
| §5 | qualified | 18 = 8 + 3 + 7 and 18 + 4 = 22 exact; the "+4" is an assumption (see B08); the hazard-frequency claim understates (hourly 30 req/s configured window; daily EFTS jobs) | D3 covers every job; the frequency claim is withdrawn |

Missing SEC-calling processes the row should enumerate: earnings-calendar-refresh (EFTS 8-K sweep,
daily 05:30 America/New_York), notable-filings (EFTS, 08:30 and 18:30 America/New_York), the hourly
filing-scan window, operator one-shots run through job definitions (each with its own buckets), and
the edgartools bucket inside every process. Correctly excluded: filing-digest, earnings-day-alerts,
retention-purge. None of this requires an E09 code path; it sharpens the configuration-only gap and
adds one external input now verified: edgartools' 9 req/s default.

## Appendix B — assumptions-lens refuter (returned 2026-10-04T17:47Z; isolated, read-only; USD 0)

Context `…:launched-2026-10-04T1733Z:envelope-derived-refuter-assume-01` (exclusion-139). Same scope
as Appendix A; read at main `0ad56621` (the 24 non-`tasks/` files changed since `100fb7d6` are all
frontend/lessons and touch no cited anchor). No row refuted outright; B41 stands; five rows
qualified. Hidden assumptions the chief accepts, with their disposition:

| Row | Hidden assumption surfaced | Disposition (chief) |
|---|---|---|
| B08 (and B15/B36/B41 through it) | "One process per instance" assumed no `WEB_CONCURRENCY` on the live revision: uvicorn honours `$WEB_CONCURRENCY` when `--workers` is absent, and `--update-env-vars` retains env set by hand | **Resolved by today's Ops read**: `WEB_CONCURRENCY` and `UVICORN_WORKERS` both `not_set`, command is the image default, `Dockerfile:60` has no `--workers` → one process per instance is now observed, not assumed (B07/B08 reclassified in the observation record). Rollout overlap stays unknown; the configured overlap case is up to +2 instances (+8 connections), not +1 |
| B19 | `reserved_connections = null` is "GUC absent on PostgreSQL 15", which supports 22; 22 is the non-superuser threshold that platform superuser backends (Cloud SQL agents, the monthly export) and Ops proxy sessions also occupy; at the server limit new connects fail immediately (FATAL), not after the 10 s pool wait | Accepted; carried into COO item on DB headroom; no number changed |
| B36 | Same second-bucket, burst and job-enumeration findings as Appendix A, plus: SEC's keying (per IP vs per declared identity) is external and unknown; all processes share one declared identity string, so the shared-budget reading is the conservative branch either way | Accepted. D8 is applied exactly that way: resolving egress identity relaxes nothing; D3 budgets both buckets for every process |
| B41 | Every provider stream is inside one of the three bounds (verified from source); none of the six non-pregenerate jobs calls the provider; a Copilot question may issue up to 4 sequential streams and a summary up to 3 attempts plus recovery — call counts, not simultaneous streams | Stands; 37 adopted as the tight fleet ceiling (Appendix A) |
| B54 | Caps are enforced server-side on every user path; there is **no guest generation path** (`ENABLE_GUEST_DAILY_QUOTA`, removed at deploy, has no Settings field — dead config); system-initiated generation (pregenerate, `/internal/precompute`, admin regenerate) is uncapped by design; units are admitted uses, not provider calls; "20" assumes one account per participant | Accepted; B52 resolves "no guest generation" from source; dead env name noted for the owner of the next `ci.yml` deploy change |
| §5 | The configuration-only mitigation for gap (a) was conditional on a bounded process count, on the library throttle being bounded separately, on integer granularity (smallest fleet sum = 2 × process count once both buckets are set), and on "Retry-After backoff" being per call (it does not pause the bucket) | Process count now observed (1 per instance); library throttle verified configurable (D3); granularity makes the scheduled-overlap sum exactly 10 with no headroom and the all-active sum 20 — stated in D3; the "existing control" wording is withdrawn: backoff is per call. The negative determination ("no E09 code subset demonstrated necessary") survives; nothing here establishes that configuration suffices |

## D9 — closure

With both refuters returned, COO item 8 moves from "open" to **"answered: no arithmetic error; six
qualifications accepted; one external input verified (edgartools 9 req/s default, env-configurable);
one assumption resolved by observation (one process per instance)"**. The COO decides whether the
item closes; the handback's next revision (CTO) carries B07/B08/B36/B41/B52 updates and the withdrawn
frequency and existing-control wording. Capacity remains unadmitted.
