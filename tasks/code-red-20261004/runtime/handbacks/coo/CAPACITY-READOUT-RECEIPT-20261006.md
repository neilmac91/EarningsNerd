# Capacity-readout receipt — Monday 2026-10-05 06:00–08:00 UTC window, re-read with Monitoring and Logging access (chief → COO, item 1 / B32; B59 and B62 evidence)

Recorded 2026-10-06T05:44:29Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`). Authority: record 02 D4 (the
same bounded readout, same two-hour window) and the founder's instruction of 2026-10-05 ~20:17Z, item 2 ("after access is
available, perform the existing bounded probe/readout"; record 09). Gate: the read-only `logs-probe` re-run on `main`
`caa6defe` (Ops run 37418676235, job 112122928339, 2026-10-06T05:28:21Z) printed `logs-probe: logging.read PERMITTED (3 recent
entries visible)` — the first PERMITTED result; the 2026-10-05 21:55Z re-run was DENIED. The access change behind it is the
founder's: the Astra morning handover (2026-10-06, metadata only) states that `roles/logging.viewer` and `roles/monitoring.viewer`
were applied to the Ops deployer service account after explicit founder confirmation, with an authenticated policy readback;
no cloud, IAM or production change was made by the chief or any delegate. Pre-checks before dispatch: no `deploy-backend` or
other CI run in flight on `main` (the workflow's own pre-flight step passed); `main` unchanged at `caa6defe` since PR #1100's
merge; no founder instruction superseding the readout. One dispatch; no retry; no widening. This is a dated evidence receipt
for the COO's C1 disposition. It admits no capacity, sets no threshold and names no participant count. The 2026-10-05 receipt
(`CAPACITY-READOUT-RECEIPT-20261005.md`) stands as the record of that run; this receipt re-reads the identical window with the
four channels that were HTTP 403 there.

## Run identity

| Item | Value |
|---|---|
| Workflow / operation | `ops.yml` `capacity-readout` on `main` `caa6defef2ac9b32cddf8bd7cad164230c132266` |
| Inputs | `capacity_start=2026-10-05T06:00:00Z`, `capacity_end=2026-10-05T08:00:00Z` (two-hour maximum; identical to the 2026-10-05 run) |
| Run / job | run 37418876945, job 112123543299; created 05:30:31Z, started 05:30:33Z, completed 05:31:11Z (2026-10-06); conclusion **success**, attempt 1 |
| Steps | pre-flight (no main push in flight) ✓ 05:30:37–38Z; window validation ✓; WIF auth ✓; cloud read ✓ 05:30:44–05:30:54Z; Cloud SQL proxy ✓ 05:30:54–05:31:06Z; SQL snapshot and job ledger ✓ 05:31:06–07Z; artifact retained ✓ 05:31:07–08Z; every other step skipped by operation |
| Retained artifact | `capacity-readout-37418876945` (id 11392520407), zip 18,589 bytes, GitHub digest `sha256:29f36229f7c601ff1e8737e149ae00396fab1f0635e7b62540ac3b72071e8b6c`, expires 2026-10-20T05:31:08Z; downloaded by the chief 2026-10-06T05:37:00Z into an empty directory, zip SHA-256 equal to the GitHub digest |
| `cloud.json` | 683,233 bytes, SHA-256 `3bf59560658467cfd03839d9a9c16e3fa1971209b8cc7373932dc473b8c6cbe5` (`observed_at` 2026-10-06T05:30:46.038854Z; schema 1; limits: 5 pages per query, 8 MiB per response) |
| `database.jsonl` | 2,755 bytes, SHA-256 `3d30c4a5bdc20a3cff31ce61981ff4d6973e7a2bd8c02671ce06308277b51d78` (snapshot 05:31:07.607Z; ledger read 05:31:07.705Z) |
| Private copy | **not made** (the 2026-10-05 classifier denial on publishing receipt files beside the private ledger is not pursued by another route). The retained store is the GitHub Actions artifact above (expires 2026-10-20T05:31:08Z); the founder may download it before then if a longer-lived copy is wanted. The repository keeps this note and the hashes only (record 02 D5) |
| Cost | 0 DeepSeek calls; USD 0; no reservation needed; no production change |

## Channel availability — B59 for this run, B62 evidence

| Channel | 2026-10-05 run (37282199614) | This run (37418876945) |
|---|---|---|
| Cloud Run job executions (API) | `complete` for 7 jobs; `partial` for filing-scan (page limit at 500 retained executions) | same: `complete` ×7; `partial` for filing-scan (5 pages, 500 retained executions inspected; the two in-window executions found; in-window completeness for that job not guaranteed) |
| Cloud SQL snapshot + bounded job ledger (proxy) | read | read |
| Cloud Monitoring `cloudsql.googleapis.com/database/postgresql/num_backends` | `unavailable`, HTTP 403, 0 pages | **`complete`**, 1 page, 4 series × 120 one-minute samples (06:01–08:00Z) |
| Cloud Monitoring `run.googleapis.com/request_count` | `unavailable`, HTTP 403 | **`complete`**, 1 page, 6 series × 120 samples |
| Cloud Monitoring `run.googleapis.com/request_latencies` | `unavailable`, HTTP 403 | **`complete`**, 1 page, 6 series × 120 samples |
| Cloud Logging entries (the readout's committed filter: severity ≥ ERROR and pool-timeout signatures) | `unavailable`, HTTP 403 | **`complete`**, 1 page, **0 entries**, `outside_scope_count` 0 |

The Ops Workload Identity Federation identity read every channel in this run. B62 (Monitoring/Logging read access for the
Ops identity) is therefore evidenced as **available on 2026-10-06** after the founder's bindings; the 2026-10-05 HTTP 403s are
consistent with those two roles being absent then, but this receipt does not explain why the 2026-10-04 run (37184184008,
attempt 2) carried Monitoring samples — that history stays unexplained and the access should be treated as verified per run,
not assumed permanent.

## What the receipt contains (counts and timings; see the files for the full records)

**Database connections in the window (Cloud SQL `num_backends`, gauge, one sample per minute, 120 samples per database,
06:01:00Z–08:00:00Z):**

| Database | Min | Max | Pattern |
|---|---|---|---|
| `earningsnerd` (application) | 3 | 4 | 3 in 105 sampled minutes; 4 in 15 consecutive sampled minutes, 07:46:00Z–08:00:00Z |
| `cloudsqladmin` (platform agent) | 2 | 2 | constant |
| `postgres` | 0 | 0 | — |
| `template1` | 0 | 0 | — |

Across databases the sampled total never exceeded **6 backends** against `max_connections=25` with 3 superuser-reserved
(22 usable, B19). At the sampled minutes nearest the two job overlaps (06:01–06:03Z and 07:01–07:03Z) the application
database showed 3 backends; the overlaps themselves lasted 9.15 s and 6.57 s between samples, so a one-minute gauge does not
resolve them (the readout's own interpretation line: "Samples are not instantaneous peaks"). The rise to 4 from 07:46Z
coincides with the window's busiest request decile (07:40–07:49Z, 29 requests); the receipt records the coincidence, not a
cause.

**HTTP requests to the service in the window (Cloud Run `request_count`, revision `earningsnerd-backend-00443-n58` — the only
revision with traffic in the window; the current revision `00444-bxs` was deployed later on 2026-10-05):**

| Response code | Requests | Note |
|---|---|---|
| 200 | 95 | 28 non-zero minutes; maximum 9 in one minute |
| 401 | 1 | 06:49Z |
| 302, 404, 405, 502 | 0 each | series present with zero deltas |

By ten-minute bucket (200s): 06:00 0 · 06:10 7 · 06:20 4 · 06:30 11 · 06:40 18 · 06:50 3 · 07:00 2 · 07:10 9 · 07:20 2 ·
07:30 4 · 07:40 29 · 07:50 6. Light traffic throughout (≈ 0.8 requests per minute on average), consistent with the earlier
COO windows.

**Latency (Cloud Run `request_latencies`, 200 responses, 95 requests; distribution with exponential buckets, scale 10 ms,
growth 1.1):** approximate upper bounds from the cumulative bucket counts — p50 ≤ 61 ms, p90 ≤ 309 ms, p95 ≤ 548 ms, p99 and
maximum ≤ 1,563 ms; per-minute means ranged 28–628 ms. The single 401 took about 5.7 ms. Bucket upper bounds, not exact
percentiles.

**Error logs in the window:** 0 entries matched the readout's committed filter (severity ≥ ERROR and pool-timeout signatures);
0 outside-scope entries. Absence within that filter in this window; not proof that no error occurred elsewhere.

**Job executions and business phases (Cloud Run API and the SQL job ledger):** identical to the 2026-10-05 receipt — 4
executions (`pregenerate f7lv2` 06:00:04–06:00:37Z; `filing-scan fgrcd` 06:00:06–06:00:31Z; `filing-scan gk9p6`
07:00:04–07:00:29Z; `backfill-facts nf566` 07:00:04–07:00:33Z), all `succeededCount=1`, `taskCount=1`, `parallelism=1`;
ledger phases 15.01 s / 9.15 s / 6.57 s / 8.34 s, all `succeeded`; counters `already_cached=15` (no `generated` counter —
unknown, not zero), `companies_scanned=7` then `0`, `filings_upserted=0`, `source_errors=0`, `filings_processed=0`,
`facts_inserted=0`, `extract_errors=0`; business-phase overlaps **9.15 s** (06:00, pregenerate × filing-scan) and **6.57 s**
(07:00, backfill-facts × filing-scan); the other five jobs 0 executions. Ledger read `row_limit` 1000, `truncated` false.

**Current SQL snapshot (2026-10-06T05:31:07.607Z, at dispatch time, about 21.5 hours after the window closed):**
`max_connections=25`, `superuser_reserved_connections=3`, `reserved_connections=null` (unknown, not zero); 13 backends in
total: 6 client backends (1 active = the observer's own query, 5 idle; 4 under the application role) and 7 server processes
(archiver, autovacuum launcher, background writer, checkpointer, dataplex worker, logical replication launcher, walwriter). The
2026-10-05 snapshot had 14 (7 client backends).

## What the receipt does NOT contain (limitations)

- No sample inside either job overlap: the gauge is one per minute and the overlaps were 9.15 s and 6.57 s.
- No concurrent **generation** in the window: pregenerate reported `already_cached=15` and no `generated` counter, so the
  connection samples are samples under light HTTP traffic and near-empty single-task jobs, not under concurrent useful
  generation. **B32 remains unobserved under its own definition**; what now exists is a quiet-Monday baseline for the same
  window (3–4 application backends, 6 total, 95 requests in two hours, p50 ≤ 61 ms, 0 error-filter entries).
- No `/metrics` read (pool `checked_out`, `provider_admission`, `sec_rate_limiter`), so B39 (`rate_limit_hits`, aggregate SEC
  rate) and B56 (useful-work evidence under concurrency) are not advanced by this run. The Logging channel is now readable,
  so the Logging half of the B39 route (SEC 403/429 search) is feasible for the Ops identity; it was not run here.
- Monitoring series are per database (connections) and per revision/response code (requests); no per-instance series was
  requested, so the realised rollout-overlap instance count (B08) is not observed.
- The provider-spend question for the window is unchanged: the receipt cannot show whether any DeepSeek call occurred
  (counter absent = unknown, not zero).

## Disposition inputs for the COO (items 1, 2, 5, 7) — no admission

- Item 1 (B32): the readout route now returns connection, request, latency and error-log samples. The sub-dependency B62 is
  evidenced for this run. B32 itself still needs one bounded read-only readout over a window **with concurrent generation**
  (the readout's existing scope; no widening), which no retained window has yet shown.
- Item 2 (B39): the Logging half of the route is feasible for the Ops identity (this run read Cloud Logging); the
  per-process `/metrics` half is unchanged and not performed.
- Item 5 (stop thresholds): the log-based stop signals' observation channel is evidenced (0 matching entries in this window);
  the baselines above are from a quiet window and are inputs for the COO, not thresholds.
- Item 7 (C5): no new evidence that an E09 subset is necessary or that existing controls demonstrably suffice; the CTO's
  revision-5 re-determination is the named next owner action (dispatch manifest `CTO-ENVELOPE-HANDBACK-03`).
- Nothing here changes the COO's HOLD, D6's provisional stop conditions, or the E09 hold.
