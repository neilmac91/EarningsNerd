# Correction 04 — CTO operating-envelope handback, revision 4 → revision 5 (2026-10-06T06:19:30Z)

**Source of the changes:** dispatch `CTO-ENVELOPE-HANDBACK-03` (manifest SHA-256
`0513f43f3a6cbff203696a4d4d64e50abb39c6947e001434358a917f1b12c93c`, 13,649 bytes; all 25 allowed inputs verified by
SHA-256 and byte length before use; none mismatched, none missing), issued by the chief after the 2026-10-06
capacity-readout receipt (the 2026-10-05 06:00–08:00 UTC window re-read by Ops run 37418876945 with every Monitoring
and Logging channel `complete` where the 2026-10-05 run 37282199614 had HTTP 403; gate: `logs-probe` run 37418676235
PERMITTED). Inputs folded in: `handbacks/coo/CAPACITY-READOUT-RECEIPT-20261006.md` and its two files (`cloud.json`
683,233 bytes, `database.jsonl` 2,755 bytes), beside the retained 2026-10-05 receipt and files; decision record 07
(§R3: the B62 failure class — a missing Logging/Monitoring read role; probe 37345946128 DENIED), record 08 (ledger
event 4; founder instructions: the two viewer roles authorized for the Ops principal, the D3 patch presented and held),
record 09 (IAM three states authorized → applied → verified; probe 37379102331 DENIED at 21:55Z; the refined reservation
rule; the deploy-scoping explanation; "D3 held"); closure 158 (this writer's provisional label); the manifest's
event-5 ledger figures; and bounded read-only repository reads at `e3eac7a7` (`.github/workflows/ci.yml`,
`.github/workflows/ops.yml`, `docs/DEPLOYMENT.md`, `ops/capacity/readout.py`, `tasks/todo.md`,
`tasks/fleet-coordination-proposal-2026-09-19.md`, `CLAUDE.md` diff, `git diff --name-status`/`git log`/`git show`
over the anchor files). Author: role label `cto-envelope-handback-rev5-author-01` (isolated Claude Code subagent
dispatched by the chief; requested model inherited `claude-fable-5-1`; it cannot observe its served model or runtime
id; provisional label pre-registered in closure 158, resolved by the chief in the next closure). Authoring method: the
bounds JSON is the source of record; the Markdown tables are rendered from it by a renderer first shown to reproduce
revision 4's 62 rows byte-for-byte from revision 4's JSON; every figure in B63–B65 was recomputed from the `cloud.json`
points and equals the receipt's (B64 states the one labelling convention involved). No adversarial lens ran on
revision 5 itself. No production, cloud, network, provider, test, server, package-install or git-write action; the
only files written are the three outputs.

**Branch movement and working tree during authoring (disclosed):** the manifest named the branch at `e3eac7a7`
(PR #1101) on main `caa6defe`; every anchor was read there. At 2026-10-06T06:10:34Z another writer committed
`1d2bfae21c08b035773c6393a94e81e83e09fdf2` ("ci: review findings on the deploy-scope detector — `--no-renames`,
deploy-step gating asserted, rename case, stale wording, lesson"; 10 files, none under `tasks/`, `backend/app/`, `ops/`
or any other cited file). The revision-5 anchors stay pinned to `e3eac7a7` (`repository_commit`); each shifted cited
line was re-read at `1d2bfae2`: `.github/workflows/ci.yml` lines cited after `:533` are four higher there (`:499`–533
one higher; `:400` unchanged; the detector is `:539` and gains `--no-renames`), `docs/DEPLOYMENT.md` lines cited after
`:47` are one higher (`:160`, `:204`, `:225`, `:278`, `:283`, `:288`, `:347`, `:354`, `:384`, `:626`–627, `:667`, `:765`,
`:770`), `CLAUDE.md` changed in its Deploy wording only (rule 5 unchanged). The revision-4 files committed at both
commits still hash to the manifest values (`94c155c7…`, `d675516e…`). Separately, after the 25 inputs were verified
and record 09 had been read, another writer modified `control/DECISIONS-09.md` in the working tree (one insertion;
working-tree SHA-256 `be6fed3e…`, 36,020 bytes; 05:53:48Z) and `control/LEDGER-ACCESS.md`, and added
`control/DECISIONS-10.md`; none of the three was opened or used — the record-09 content relied on is the manifest-bound
version, byte-identical to the committed file at `e3eac7a7` and `1d2bfae2` (`bcc56ab2…`, 35,869 bytes), and every
record-09 fact cited was re-checked against that committed text.

**Superseded citation corrected:** revision 4 cited `control/DECISIONS-06.md` at `13f852f0…` (14,904 bytes), the
pre-commit state its manifest bound; the committed file (`f8091c53`, PR #1093) is `08f9c060…` (19,699 bytes) — the
same record with the "Morning execution" section appended. B46, B58 and B62 now cite the committed hash, as the
manifest does.

## Changed bounds (ids B01–B62 stable; B63–B66 new)

| ID | What changed | Why | Evidence |
|---|---|---|---|
| B01 | evidence: `docs/DEPLOYMENT.md:201` → `:203` at `e3eac7a7` (`:204` at `1d2bfae2`) | PR #1101 added two lines at `:46`–50 (one more in `1d2bfae2`); line re-read | `docs/DEPLOYMENT.md` diff hunks and lines |
| B08 | uncertainty: instance count still unobserved — the 2026-10-06 request series are per revision, not per instance | the 403 explanation is superseded by the re-read | receipt 2026-10-06 §"What the receipt does NOT contain"; `cloud.json` `request_count` resource labels |
| B15 | evidence: `:664` → `:666` (`:667` at `1d2bfae2`) | as B01 | same |
| B16 | evidence: `:157` → `:159` (`:160` at `1d2bfae2`) | as B01 | same |
| B18 | uncertainty: null re-observed 2026-10-06 (B66) | readout | `database.jsonl` 2026-10-06 |
| B20 | uncertainty: third instant (B66); the in-window gauge counts per database, not clients | readout | same; B63 |
| B21 | evidence: re-read identically on 2026-10-06 | readout | `cloud.json` 2026-10-06 executions |
| B22 | evidence: 2026-10-06 files; uncertainty: no sample inside either overlap on either run — nearest one-minute samples show 3 application backends; filing-scan `partial` on both runs | readout (B63) | receipt 2026-10-06; `cloud.json` `database_connections` points |
| B23 | value: notable-filings runbook lines read directly (`docs/DEPLOYMENT.md:625`–626 at `e3eac7a7`, `:626`–627 at `1d2bfae2`; previously reviewer-reported); evidence: seven runbook anchors renumbered (+2), 2026-10-06 `cloud.json`; uncertainty: attribution note replaced | anchor re-verification; bounded read | `docs/DEPLOYMENT.md` lines; `git show 0b8d39eb:docs/DEPLOYMENT.md` |
| B28 | evidence: `:762` → `:764` (`:765` at `1d2bfae2`) | as B01 | same |
| B32 | evidence: the 2026-10-06 run's samples (3–4 application backends, ≤ 6 total, 95 requests, 0 error-filter entries, no sample inside the overlaps, no concurrent generation); uncertainty: resolving observation named exactly — one bounded readout over a retained window with concurrent useful generation, when one exists; never new load; B62 no longer a standing prerequisite (verified per run); readout anchors `:38` → `:41`–42, `:128` → `:183`; classification stays `unknown` | required change | receipt 2026-10-06; `cloud.json`; `database.jsonl`; `ops/capacity/readout.py` at `e3eac7a7` |
| B39 | evidence: neither readout carries `rate_limit_hits`; the 2026-10-06 log query is the committed error/pool-timeout filter, not an SEC 403/429 search; counter-semantics file unchanged at `e3eac7a7`/`1d2bfae2`; uncertainty: Logging half feasible (PERMITTED) and not run — no existing Ops operation performs it; `/metrics` half unchanged; stays `unknown` | required change | receipt 2026-10-06; `ops/capacity/readout.py:240`–248; `.github/workflows/ops.yml:36`–49 |
| B43 | evidence: `:767` → `:769` (`:770` at `1d2bfae2`) | as B01 | same |
| B46 | evidence: record 06 cited at the committed hash `08f9c060…` | superseded citation | `git log` of `control/DECISIONS-06.md` |
| B47 | evidence: `tasks/todo.md:6147` → `:6180` (the PR #1069 backend bullet; drift since `100fb7d6` disclosed) | anchor re-verification | `tasks/todo.md:6177`–6182; heading line at `100fb7d6`/`0b8d39eb`/HEAD |
| B51 | evidence: same `tasks/todo.md` anchor | same | same |
| B56 | evidence: neither readout adds useful-work evidence (request samples are light HTTP traffic the readout cannot attribute to generation); uncertainty: route = B32's observation (B62 per run) plus `/metrics.provider_admission` peaks; stays `unknown` | required change | receipt 2026-10-06 |
| B57 | evidence: readout anchor `:128` → `:183`, log filter `:240`–248, B65; uncertainty: log-based signals' channel evidenced (0 entries, quiet window) — a channel check and no-load baseline, not a threshold; SEC 403/429 search not part of the filter; access verified per run | required change (§4) | receipt 2026-10-06 §"Error logs"; `ops/capacity/readout.py` |
| B58 | value: ledger after event 5 — ceiling 25.000000; recorded use 0.578659 (field `known_future_cost_usd` → `recorded_use_against_ceiling_usd`, record 08's wording); holds 1.881713; one active reservation 0.060000 (PR #1101 copilot-eval run); conditional unreserved 22.479628; event chain 3 → 4 → 5; document identity last known after event 4 (`b4ce7016…`, 31,690 bytes); evidence, uncertainty | required change (provenance only) | manifest 03 `required_changes`; records 06–09; commit `e3eac7a7` message |
| B59 | bound retitled; value: two dated observations — the 2026-10-05 run (retained) and the 2026-10-06 run (executions complete ×7 / filing-scan partial; SQL read; `num_backends` 4 × 120, `request_count` 6 × 120, `request_latencies` 6 × 120, logs 0 entries — all `complete`); evidence, uncertainty (per-run; 2026-10-04 → 05 change unexplained) | required change | both receipts; both `cloud.json` |
| B60 | evidence: re-read identically on 2026-10-06; uncertainty: `partial` on both runs | readout | `database.jsonl`, `cloud.json` 2026-10-06 |
| B61 | uncertainty: next instant B66 | readout | `database.jsonl` 2026-10-06 |
| B62 | **classification `unknown` → `observed`**; bound retitled "— observed per run"; value: state 2026-10-06 (probe PERMITTED; four channels complete), state history (2026-10-04 samples → 10-05 403 → 17:06Z DENIED → 18:29Z authorized → ~20:17Z applied → 21:55Z DENIED → 10-06 05:28Z PERMITTED), provenance of the change (the founder's binding of `roles/logging.viewer` and `roles/monitoring.viewer`, per the Astra handover as relayed in the receipt; metadata only; effective between 21:55:53Z and 05:28:21Z), verification rule (per run); evidence; uncertainty (2026-10-04 unexplained; binding not read here; any IAM action is the founder's) | required change | receipt 2026-10-06; records 07 §R3, 08 item 2, 09 items 0/2; `.github/workflows/ops.yml:410`–419 |
| B63 (new) | `observed`, component 2: the window's `num_backends` one-minute samples by database — application 3 (105 min) / 4 (15 consecutive min from 07:46Z), `cloudsqladmin` 2, `postgres`/`template1` 0, total 5–6; nearest samples to both overlaps 3; no sample inside the overlaps; the 07:46Z rise coincides with the busiest request decile (coincidence, not cause) | required change | `cloud.json` 2026-10-06 `database_connections` (recomputed); receipt |
| B64 (new) | `observed`, component 4: requests to revision 00443-n58 — 200 ×95 (28 non-zero minutes; max 9), 401 ×1 (interval ending 06:49Z), others 0; ten-minute buckets labelled by interval end time (the receipt's convention; start-time labelling moves boundary minutes, total 95 either way); latency upper bounds p50 ≤ 61 ms, p90 ≤ 309, p95 ≤ 548, p99/max ≤ 1,563 (bucket bounds, not exact percentiles); per-minute means 28–628 ms | required change | `cloud.json` 2026-10-06 `request_count`, `request_latencies` (recomputed); receipt; record 08 (00444-bxs later) |
| B65 (new) | `observed`, component 4: 0 entries under the readout's committed filter (`severity>=ERROR OR "QueuePool limit" OR "connection pool exhausted"`, service revisions or the eight jobs, us-west1, the window), 0 outside scope — absence within the filter, not proof of no error; not an SEC 403/429 search | required change | `cloud.json` 2026-10-06 `error_logs`; `ops/capacity/readout.py:178`–184, `:240`–248 |
| B66 (new) | `observed`, component 1: SQL snapshot 2026-10-06T05:31:07Z — `max_connections` 25, `superuser_reserved_connections` 3, `reserved_connections` null, 6 client backends (1 active = observer, 5 idle, 4 under the application role), 7 server processes, 13 in total — beside B61's 14 | required change | `database.jsonl` 2026-10-06; receipt |

Unchanged bounds (39): B02, B03, B04, B05, B06, B07, B09, B10, B11, B12, B13, B14, B17, B19, B24, B25, B26, B27, B29, B30, B31, B33, B34, B35, B36, B37, B38, B40, B41, B42, B44, B45, B48, B49, B50, B52, B53, B54, B55.

## Field-by-field diff of the JSON, revision 4 → revision 5

- **Top level:** `revision` 4 → 5; `dispatch_id` `CTO-ENVELOPE-HANDBACK-02` → `CTO-ENVELOPE-HANDBACK-03`; `observed_at`
  2026-10-05T08:36:50Z → 2026-10-06T06:17:07Z; `repository_commit` `0b8d39eb…` → `e3eac7a7…` (anchors pinned to the
  branch commit the manifest names; the branch movement to `1d2bfae2` and the line offsets are in `repository_note`);
  `repository_note`, `author` and `next_owner` rewritten; `dispatch_manifest` (path, SHA-256, 13,649 bytes, 25 inputs
  listed and verified). Unchanged: `schema_version`, `original_dispatch_id`, `counts_unchanged`, `spend` (0 calls,
  USD 0.000000, 0 reservations), `external_mutations` (0).
- **Bounds:** 62 → 66 (B63–B66 added). 23 existing bounds changed in 40 fields: `classification` on
  1 (B62); `bound` on 2 (B59, B62); `value` on 4 (B23, B58, B59, B62);
  `evidence` on 19; `uncertainty` on 14. No `id`, `component`, `unit` or
  `enforcement_scope` changed. Every `null` is classified `unknown` (B32, B39, B56) or is a sub-field marked unknown
  (B08 `rollout_overlap_extra`, B16 `current`, B18/B61/B66 `reserved_connections`, B21 `other_five_jobs` parallelism,
  B22 `same_job_concurrent_executions`, B60 `generated`); `null` is never zero, and a sample that does not exist (inside
  the 9.15 s / 6.57 s overlaps) is recorded as absent, not estimated. B58's sub-field `known_future_cost_usd` is
  replaced by `recorded_use_against_ceiling_usd` (the same ledger line in record 08's wording) and
  `active_reservation_usd`, `event_chain_after_event_2` are added; the B59 value nests the revision-4 object under
  `run_37282199614_20261005` unchanged.
- **`determination` block:** `existing_controls_suffice` stays `"undetermined"` and `necessary_e09_subset` stays `null`;
  `missing_decision` adds the records 08/09 provenance (patch presented and held; three options; "D3 held");
  `missing_observations` rewritten (B32 without a standing B62 prerequisite — the resolving observation named exactly,
  never new load; B39's Logging half feasible and not run; B56); `what_each_missing_item_resolves` key `B62_then_B32`
  → `B32` (text rewritten; the other two keys retained); `evidence_ids` 39 → 43 (B63–B66 added; none removed);
  `hazard_ranking_for_current_beta` 5 entries — entries 1 (SEC: B65 is not an SEC search), 2 (DB: three instants and
  the window's 3–4 / ≤ 6 as a quiet baseline; mitigation = the B32 observation) and 5 (observation blindness →
  per-run verification) changed, 3 and 4 unchanged; new `closed_since_revision_4` (4 entries); `closed_since_revision_3`
  retained unchanged.

## Effect on the COO disposition

`handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md` (SHA-256 `d30bdd50…`) reached HOLD on revision 1;
`…-DISPOSITION-UPDATE-01.md` (SHA-256 `07ebaaf3…`) kept it after revision 4 with items 1, 2 (B39 part), 3, 5 and 7
open and the B62 sub-dependency on items 1 and 5. Revision 5 moves B62 to `observed` under a per-run verification
rule, so item 1 now waits on a retained window with concurrent useful generation (not on access) and item 5's
log-based signal channel is evidenced with a quiet-window 0 (thresholds still not evidenced); B32, B39 and B56 remain
`unknown` with `null` values; item 3 (the founder's D3 decision) is still open; item 7 is answered "undetermined; no
E09 subset demonstrated necessary". The HOLD is not weakened by this revision; the COO disposition-update worker
(provisional label `coo-envelope-disposition-update-02`, closure 158) is the next owner and states each of the eight C1
items' state.

## Hash chain

| File | Revision 4 SHA-256 (manifest `CTO-ENVELOPE-HANDBACK-03.json`) | Bytes | Revision 5 SHA-256 | Bytes |
|---|---|---:|---|---:|
| `CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` | `94c155c7c517b36b73d751a1935fa78060747907dd810fcbf84685ac19ee3d41` | 72,085 | `b9fdccb3f368ed07f0f0b8bf148298cba1a61ab4ae75186c7c642f97e0140381` | 101,532 |
| `CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` | `d675516eea6b401780e6dbe29061388573b5c736f4447b979bb86536a2577505` | 68,998 | `6638a908cbff099ff49f38a5c707a814c0f277e17e47727de1964b19c2cf92f3` | 94,153 |

Revision 5 hashes were computed after the final write of both files (the first write at 06:08:11Z / 06:12:47Z
preceded the branch movement; both files were amended at 06:17:07Z to disclose it and pin the anchors, and the Markdown
once more for one wording alignment, with the 66 table rows re-verified against the JSON render after each write).
Revisions 1 → 2 → 3 → 4 remain in `CORRECTION-01.md`, `CORRECTION-02.md` and `CORRECTION-03.md`. This file cannot
contain its own digest; the author reports it to the chief.

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 0 ledger events; 0 external mutations; files written: the three
outputs only.
