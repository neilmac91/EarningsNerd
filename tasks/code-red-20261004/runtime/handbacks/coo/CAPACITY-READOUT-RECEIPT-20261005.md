# Capacity-readout receipt — Monday 2026-10-05 06:00–08:00 UTC job-overlap window (chief → COO, item 1 / B32)

Recorded 2026-10-05T08:17:17Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). Authority: record 02 D4
(COO/CEO decision; Routine `trig_01QEr6wQnjqtMG4FdqLce2qT` fired 2026-10-05T08:11:12Z). Pre-checks before dispatch: no
`deploy-backend` or other CI run in flight on main (latest main CI run 37153230036, completed); main unchanged at
`0b8d39eb`; no founder instruction superseding the readout. One dispatch; no retry; no widening. This is a dated evidence
receipt for the COO's C1 disposition. It admits no capacity, sets no threshold and names no participant count.

## Run identity

| Item | Value |
|---|---|
| Workflow / operation | `ops.yml` `capacity-readout` on `main` `0b8d39ebad065a8ab5f3ab4b6213892f2e7544a2` |
| Inputs | `capacity_start=2026-10-05T06:00:00Z`, `capacity_end=2026-10-05T08:00:00Z` (two-hour maximum) |
| Run / job | run 37282199614 (Ops #66), job 111672636113; queued 08:12:30Z, completed 08:13:10Z; conclusion **success** |
| Steps | pre-flight (no main push in flight) ✓; window validation ✓; cloud read ✓ (08:12:46–08:12:54Z); Cloud SQL proxy ✓; SQL snapshot ✓ (08:13:06–08:13:07Z); artifact retained ✓ |
| Retained artifact | `capacity-readout-37282199614` (id 11332748217), zip 2,477 bytes, GitHub digest `sha256:4f7af7b4d0cc081b570a4c9d3f68f3352651f743092d46955d07f0c598a505ff`, expires 2026-10-19T08:13:07Z |
| `cloud.json` | 9,841 bytes, SHA-256 `2a177f6df5c13b4859bf02da80f53676e745791f8d6fe96cdb267c7230d1337d` (observed_at 2026-10-05T08:12:47.354838Z) |
| `database.jsonl` | 2,755 bytes, SHA-256 `37094bf81b34a1a4e44afeae1bf29fe2ec4353bf278ee7dd9e207ea35a0c4768` (snapshot 08:13:07.513Z; ledger read 08:13:07.591Z) |
| Private copy | **not made**: the chief's attempt to publish the two receipt files beside the private ledger artifact was denied by the platform's auto-mode classifier (Data Exfiltration) and is not pursued by another route. The retained store is the GitHub Actions artifact above (expires 2026-10-19T08:13:07Z); the founder may download it before then if a longer-lived copy is wanted. The repository keeps this note and the hashes only (record 02 D5) |
| Cost | 0 DeepSeek calls; USD 0; no reservation needed; no production change |

## What the receipt contains (counts and timings; see the files for the full records)

**Job executions in the window (Cloud Run API):** 4 executions, all `succeededCount=1`, `taskCount=1`, `parallelism=1`,
all on image digest `444f06cf…` (the serving revision's image).

| Execution | Start → completion (UTC) | Lifetime | SQL ledger business phase | Numeric counters reported |
|---|---|---|---|---|
| pregenerate `f7lv2` | 06:00:04.287 → 06:00:37.377 | 33.09 s | 06:00:16.926 → 06:00:31.936 (15.01 s), succeeded | `already_cached=15`; no `generated` counter (unknown, not zero) |
| filing-scan `fgrcd` | 06:00:06.283 → 06:00:31.222 | 24.94 s | 06:00:18.789 → 06:00:27.942 (9.15 s), succeeded | `companies_scanned=7`, `filings_upserted=0`, `source_errors=0`, `alerts_sent=0`, `alerts_failed=0` |
| filing-scan `gk9p6` | 07:00:04.311 → 07:00:29.283 | 24.97 s | 07:00:16.833 → 07:00:23.404 (6.57 s), succeeded | `companies_scanned=0`, `filings_upserted=0`, `source_errors=0`, `alerts_sent=0`, `alerts_failed=0` |
| backfill-facts `nf566` | 07:00:04.311 → 07:00:33.381 | 29.07 s | 07:00:16.235 → 07:00:24.577 (8.34 s), succeeded | `filings_processed=0`, `facts_inserted=0`, `facts_skipped=0`, `facts_rejected=0`, `extract_errors=0` |

filing-digest, earnings-calendar-refresh, earnings-day-alerts, notable-filings, retention-purge: 0 executions in the
window (consistent with their schedules). Listing completeness: `complete` for 7 jobs; **`partial` for filing-scan**
(page limit reached after 500 retained executions; the two in-window executions were found, but completeness of the
in-window set for that job is not guaranteed by the receipt).

**Concurrency observed (first retained window in which business phases overlap):**

| Pair | Execution-lifetime overlap | Business-phase overlap (SQL ledger) |
|---|---|---|
| pregenerate × filing-scan, 06:00 | 06:00:06.283 → 06:00:31.222 = 24.94 s | 06:00:18.789 → 06:00:27.942 = **9.15 s** |
| backfill-facts × filing-scan, 07:00 | 07:00:04.311 → 07:00:29.283 = 24.97 s | 07:00:16.833 → 07:00:23.404 = **6.57 s** |

The 2026-10-04 02:30–04:30 window (COO first deliverable) recorded business phases that did *not* overlap; this
window records two that did. The overlapping work was near-empty (7 companies scanned, 0 filings processed or
upserted, 15 examples already cached), so it is evidence that Monday job overlap happens, not evidence of load.

**Current SQL snapshot (08:13:07.513Z, at dispatch time, outside the window):** `max_connections=25`,
`superuser_reserved_connections=3`, `reserved_connections=null` (unknown, not zero); 14 backends in total: 7 client
backends (1 active = the observer's own query, 6 idle; 5 under the application role) and 7 server processes
(archiver, autovacuum launcher, background writer, checkpointer, dataplex worker, logical replication launcher, walwriter).

## What the receipt does NOT contain (material limitation)

| Channel | State | Consequence |
|---|---|---|
| Cloud Monitoring `cloudsql.googleapis.com/database/postgresql/num_backends` | `unavailable`, **HTTP 403**, 0 pages | no DB-connection samples inside the window |
| Cloud Monitoring `run.googleapis.com/request_count` | `unavailable`, HTTP 403 | no request counts for the window |
| Cloud Monitoring `run.googleapis.com/request_latencies` | `unavailable`, HTTP 403 | no latency series |
| Cloud Logging entries (severity ≥ ERROR, pool-timeout signatures) | `unavailable`, HTTP 403 | no error-log or pool-timeout evidence either way |

The Ops workflow's Workload Identity Federation identity could read Cloud Run executions and Cloud SQL but was refused
by the Monitoring and Logging APIs in this run. The retained 2026-10-04 receipt (Ops run 37184184008, attempt 2) did
carry Monitoring samples, so the refusal is new or intermittent; its cause was not investigated here (a read-only IAM
check is the resolving step, owner CTO/CEO; any grant is a cloud-configuration change for the founder to decide — not
made). Therefore **B32 (DB operating reserve under concurrent generation) and B56 (useful-work evidence under
concurrency) remain unobserved by this run**, and B39 (`rate_limit_hits`) was never in the readout's scope.

## Disposition inputs for the COO (item 1) — no admission

- Item 1's smallest permitted handback was "one dated read-only readout receipt". It exists (this note + the two files).
  Its DB-reserve content is empty because of the 403s; its job-ledger content is new evidence of Monday overlap with
  near-empty work.
- New sub-dependency for items 1 and 5: Monitoring/Logging read access for the Ops identity, or an alternative
  retained-sample route, before any B32 observation can exist. Owner: CTO/CEO (read-only check), founder (any grant).
- Provider spend inside the window: pregenerate reported `already_cached=15` and no generation counter; the receipt
  cannot show whether any DeepSeek call occurred (counter absent = unknown, not zero). The ledger records no
  estimate for it.
- Nothing here changes the COO's HOLD, D6's provisional stop conditions, or the E09 hold.
