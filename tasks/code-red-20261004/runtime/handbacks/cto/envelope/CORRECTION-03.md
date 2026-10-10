# Correction 03 — CTO operating-envelope handback, revision 3 → revision 4 (2026-10-05T08:41:15Z)

**Source of the changes:** dispatch `CTO-ENVELOPE-HANDBACK-02` (manifest SHA-256
`260a706a37cd448b075cedbb96246101a6f41895ba16c70195e0463ed4f30fd5`, 8,584 bytes; all 16 allowed inputs verified by
SHA-256 and byte length before use), issued by the chief after the 2026-10-05 Monday capacity-readout receipt
(record 06: "CTO handback rev 4 … B07/B08/B36/B41/B52 updates, B32 observation, C5 re-determination"; COO disposition
§4 item 7 names the CTO re-determination as the next owner action). Inputs folded in: decision records 02–06 (D3
two-bucket SEC model and the founder-held patch; D4 window; D6 provisional stop conditions; D7 provider limits; D8
egress; D9 and Appendices A/B — refuter qualifications of B08/B19/B36/B41/B54/§5; records 03/05 `rate_limit_hits`
semantics; record 06 ledger event 2 and C1 closures), the 2026-10-04 production-configuration observation (two
read-only Ops describes), the 2026-10-05 readout receipt note and its two files (`cloud.json`, `database.jsonl`),
and bounded read-only code reads at the current checkout (`backend/app/services/sec_rate_limiter.py`,
`routers/summaries.py`, `services/rate_limiter.py`, `config.py`, `dependencies.py`, `routers/auth.py`,
`routers/internal.py`, `routers/admin.py`, `integrations/sec_api.py`, `requirements.txt`, `Dockerfile`,
`.github/workflows/ci.yml`, `docs/OPERATIONS.md`). Author: role label `cto-envelope-handback-rev4-author-01`
(isolated Claude Code subagent dispatched by the chief; requested model inherited `claude-fable-5-1`; it cannot
observe its served model or runtime id). Revision 4 was authored directly rather than by the revisions 1–3
generator; every new `file:line` anchor was read at this checkout and every retained anchor is unchanged (the
non-`tasks/` tree differs from `100fb7d6` only in `frontend/`, `lessons/`, `.impeccable/` and `.gitleaksignore`).
No adversarial lens ran on revision 4 itself. No production, cloud, network, provider, test, server or git-write
action; the only files written are the three outputs.

**Branch movement during authoring (disclosed):** the manifest named branch HEAD `0aebe6d9`; at start the branch
was at `9146b91a` (readout receipt + this manifest) and during authoring it advanced through `6ad94ded`
(checkpoint, `tasks/` only) to `4fbaf15d` (`.gitleaksignore` only). The revision-3 files committed at HEAD still
hash to the manifest values (`58ef902d…`, `5ee84009…`); all other inputs re-verified unchanged; no cited anchor is
affected. The revision-4 files record HEAD `4fbaf15d` and code anchors at main `0b8d39eb`.

## Changed bounds (ids B01–B58 stable; B59–B62 new)

| ID | What changed | Why | Evidence |
|---|---|---|---|
| B04 | evidence, uncertainty: service and revision maxScale 2 confirmed live; configured overlap case +2 noted | live configuration read | `PRODUCTION-CONFIG-OBSERVATION-20261004.md` §Service |
| B05 | evidence: `containerConcurrency` 40 confirmed live | same | same |
| B06 | evidence: request timeout 600 s confirmed live | same | same |
| B07 | **classification `configured-code-default` → `observed`**; evidence, uncertainty | required change: one serving process per instance is observed (command = image default; `WEB_CONCURRENCY`/`UVICORN_WORKERS` not set) | PCO §Service; `backend/Dockerfile:60`; record 02 Appendix B (B08 row) |
| B08 | **classification `assumed` → `observed`**; value adds `configured_overlap_case_max_extra_instances=2` (rollout extra stays `null`); evidence, uncertainty | required change; refuters: overlap case up to +2 instances (+8 connections), not +1 | PCO §Service; record 02 Appendices A/B |
| B10 | evidence: `DB_POOL_SIZE=4`, `DB_MAX_OVERFLOW=0` confirmed live | live configuration read | PCO §Service |
| B14 | evidence: eight jobs observed with pools 3+0 / 1+0, `taskCount` 1 | same | PCO §Jobs |
| B15 | uncertainty: +8 overlap case (26 > 22 usable not excluded); platform agents added to non-application clients | refuter qualification | record 02 Appendix B |
| B18 | uncertainty: PostgreSQL 15 has no `reserved_connections` GUC (null = parameter absent, still not zero); re-observed null 2026-10-05 | refuter qualification; readout | record 02 Appendices A/B; `database.jsonl` |
| B19 | uncertainty: 22 is the threshold on everyone's backends (agents, export, Ops sessions); FATAL at the server limit, not the 10 s pool wait | refuter qualification | record 02 Appendices A/B |
| B20 | uncertainty: cross-reference to the 2026-10-05 instant (B61) | readout | `database.jsonl` |
| B21 | value: timeouts (1800 s / 3600 s) and `parallelism=1` observed for the three jobs that executed 2026-10-05; `taskCount` 1 re-observed on all eight; other five jobs' parallelism stays `null`; evidence, uncertainty | readout + Ops read | `cloud.json` executions; PCO §Jobs; 2026-09-19 inventory retained |
| B22 | value: 2026-10-05 lifetime overlaps 24.94 s / 24.97 s and business-phase overlaps 9.15 s / 6.57 s added beside the 2026-10-04 figures; same-job concurrency stays `null`; evidence, uncertainty (filing-scan listing `partial`) | readout | receipt note §"Concurrency observed"; `database.jsonl`; `cloud.json` |
| B23 | value: backfill-facts = Mon 07:00 UTC (Astra confirmation; execution `nf566` observed 07:00:04Z); uncertainty adds the SEC-calling job set | record 02 D4 / Appendix A; readout | record 02; `cloud.json` |
| B32 | evidence: 2026-10-05 readout returned HTTP 403 on Monitoring (`num_backends`, `request_count`, `request_latencies`) and Logging → no window sample; SQL snapshot outside the window; overlaps with near-empty work; uncertainty: resolving observation now has prerequisite B62; value stays `null`/`unknown` | required change | receipt note; `cloud.json`; `database.jsonl` |
| B33 | uncertainty: the founder-held D3 patch would fix the doc threshold; not applied | record 02 D3 execution note; record 03 | record 02, 03 |
| B34 | evidence: no `SEC_RATE_LIMIT_PER_SECOND` override on the service or any job observed; uncertainty: bucket starts full (2× first second), waits rather than rejects, patch would set 1 (not applied) | PCO; record 02 D3; code read | PCO §Service/§Jobs; `sec_rate_limiter.py:57`, `:80`–83, `:85`–94 |
| B35 | unit "req/s per IP" → "req/s per user (SEC wording: regardless of the number of machines)"; evidence, uncertainty | record 02 D8 | SEC fair-access policy as read 2026-10-04 (D8); `config.py:32`; Appendix B |
| B36 | bound retitled; **value 20/40/50 → two-bucket model**: per process 19 sustained / 29 first second; 38 steady, 57 hourly filing-scan, 76 Monday 06:00, 95 Monday 07:00, 190 all ten; founder-held D3 patch figures (1 + 1: 4/6/8/10/20; first second 3 per process, 15 at Monday 07:00) recorded as NOT applied; "assumes one shared IP" caveat removed; evidence, uncertainty; classification stays `assumed` | required change (record 02 D3/D9: 20/40/50 was a floor) | record 02 D3, Appendix A; PCO; `config.py:33`; `sec_rate_limiter.py:57`, `:80`–83; `sec_api.py:9`–11; `requirements.txt:52`, `:172`; `docs/OPERATIONS.md:96` |
| B37 | bound retitled; **classification `unknown` → `observed`**; value: dynamic egress IP observed; compliance consequence none (closed by D8); evidence, uncertainty | required change | PCO §Service; record 02 D8; 2026-09-19 proposal `:29` |
| B38 | value adds the edgartools internal limiter and the backoff-path vs single-token call sites; evidence, uncertainty | supports B36/B39 | `facts_service.py:1922`; `sec_api.py:218`; `edgar/compat.py:149`, `:423`, `:509`; `edgar/xbrl_service.py:882`; `edgar/company_sic.py:19` |
| B39 | bound retitled; evidence: `rate_limit_hits` semantics verified with line cites (`_wait_for_token` `:72`–98 increments `_total_requests` only; `_rate_limit_hits` only at `:153` in `execute_with_backoff` `:119`–181; `_is_rate_limit_error` `:184`–196: `HTTPStatusError` → 429 only, message fallback only for other exceptions; `execute()` `:100`–117 never increments); uncertainty: flat counter closes nothing; log search needs B62; value stays `null`/`unknown` | required change (records 03/05) | `sec_rate_limiter.py`; records 03, 05; receipt note (readout lacks the counter) |
| B40 | uncertainty: live env confirmed 2026-10-04 | PCO | PCO §Service |
| B41 | value: `plus_pregenerate_tight=37` added, 43 retained as loose; evidence (none of the other seven jobs reaches the provider); uncertainty (B46 published headroom) | required change (Appendix A/B qualifications) | record 02 Appendices A/B |
| B46 | bound retitled; **classification `unknown` → `observed`**; value: no RPM limit published; 2,500 concurrent `deepseek-flash`, 500 `deepseek-v4-pro`; HTTP 429 above; read 2026-10-04; unit; evidence, uncertainty (published/dated, not account-verified) | required change (record 02 D7; record 06 item 4 closed) | record 02 D7; record 06 |
| B48 | uncertainty: tight simultaneous-stream bound 3 for the pregenerate process | refuter qualification | record 02 Appendix A |
| B49 | evidence: `REGISTRATION_MODE=invite_only` confirmed live | live configuration read | PCO §Service |
| B51 | bound retitled; **classification `unknown` → `configured-code-default`**; value: 5 per 60 s (summaries) and 10 per 60 s (questions) per account, account-only key, per-process sliding window, 10,000 keys per limiter per process, fail closed when full; unit; evidence, uncertainty | required change (bounded code read) | `summaries.py:60`–65, `:217`–223, `:456`–462; `services/rate_limiter.py:13`–14, `:40`–41; `config.py:170`–171 |
| B52 | **classification `unknown` → `configured-code-default`**; value: no guest generation path (`generate-stream` → `get_current_user`, 401 without a JWT; `ask-stream` → `require_copilot_or_taste`; other triggers internal-token precompute and admin refresh, system-initiated); `ENABLE_GUEST_DAILY_QUOTA` is dead deploy config; evidence, uncertainty | required change (bounded code read) | `summaries.py:175`–186, `:436`–441, `:146`–173, `:610`–611, `:656`–657; `auth.py:379`–391; `dependencies.py:51`; `internal.py:27`–36, `:305`; `admin.py:34`, `:913`, `:946`; grep: `ci.yml:619` only; record 02 Appendix B |
| B54 | uncertainty: ceiling of metered admitted uses per calendar month; retries, recovery, duplicates and system generation sit outside; "20" assumes one account per participant | refuter qualification | record 02 Appendices A/B |
| B56 | evidence: the readout adds no useful-work evidence (`already_cached=15`, no `generated` counter; 403s); uncertainty (after B62); value stays `null`/`unknown` | readout | receipt note; `database.jsonl` |
| B57 | value adds `provisional_stop_conditions` (record 02 D6 as corrected by record 03); evidence; uncertainty (readout lacks `rate_limit_hits`; log routes 403; provisional until items 1 and 2 supply baselines) | records 02 D6, 03, 06 item 5; readout | records 02, 03, 06; receipt note |
| B58 | bound retitled; value: successor ledger (document SHA-256 `f4dd36fb…`, 25,307 bytes, version 3); ceiling USD 25 after event 2 (2026-10-05T00:10:56Z; was 15); known future cost 0.547516; holds 1.881713; conditional unreserved 22.570771; 0 reservations; cumulative 2,356 calls / USD 4.331765; paid dispatch HELD; evidence, uncertainty (provenance only; Monday pregenerate spend unknown) | required change | record 06 §"Ledger event 2"; record 02 D1; record 03 §D1; `LEDGER-ACCESS.md` named by record 06, not opened |
| B59 (new) | `observed`, component 2: 2026-10-05 readout observation-channel availability — Cloud Run executions and SQL read; Monitoring `num_backends`/`request_count`/`request_latencies` and Logging HTTP 403 | required change (B32 observation) | receipt note §"What the receipt does NOT contain"; `cloud.json` |
| B60 (new) | `observed`, component 1: four executions in 06:00–08:00 UTC; business-phase overlaps 9.15 s (pregenerate × filing-scan) and 6.57 s (backfill-facts × filing-scan); counters `already_cached=15`, `companies_scanned=7`/0, `filings_upserted=0`, `filings_processed=0`; `generated` absent → unknown | required change (job-ledger facts) | `database.jsonl`; `cloud.json`; receipt note |
| B61 (new) | `observed`, component 1: SQL snapshot 08:13:07Z (outside the window): `max_connections` 25, `superuser_reserved_connections` 3, `reserved_connections` null, 7 client backends (1 active = observer, 6 idle, 5 under the application role), 14 backends in total | required change (point-in-time read, not a window sample) | `database.jsonl`; receipt note |
| B62 (new) | `unknown`, component 2: Monitoring/Logging read access for the Ops WIF identity — new sub-dependency for B32, B56 and the log-based stop signals; owner CTO/CEO (read-only IAM check), founder (any grant) | required change | receipt note; record 06 item 1 |

Unchanged bounds (25): B01, B02, B03, B09, B11, B12, B13, B16, B17, B24, B25, B26, B27, B28, B29, B30, B31, B42,
B43, B44, B45, B47, B50, B53, B55.

## Field-by-field diff of the JSON, revision 3 → revision 4

- **Top level:** `revision` 3 → 4; `dispatch_id` `CTO-ENVELOPE-HANDBACK-01` → `CTO-ENVELOPE-HANDBACK-02`; new
  `original_dispatch_id` (`CTO-ENVELOPE-HANDBACK-01`), `repository_note` and `dispatch_manifest` (path, SHA-256,
  bytes, 16 inputs verified); `observed_at` 2026-10-04T15:20:16Z → 2026-10-05T08:36:50Z; `repository_commit`
  `100fb7d6…` → `0b8d39eb…`; `author` and `next_owner` rewritten. Unchanged: `schema_version`, `counts_unchanged`,
  `spend` (0 calls, USD 0.000000, 0 reservations), `external_mutations` (0).
- **Bounds:** 58 → 62 (B59–B62 added). 33 existing bounds changed in 81 fields: `classification` on 6 (B07, B08,
  B37, B46, B51, B52); `value` on 13 (B08, B21, B22, B23, B36, B37, B38, B41, B46, B51, B52, B57, B58); `unit` on 3
  (B35, B46, B51); `bound` on 6 (B36, B37, B39, B46, B51, B58); `evidence` and/or `uncertainty` on all 33. No `id`,
  `component` or `enforcement_scope` changed. Every `null` value is classified `unknown` (B32, B39, B62) or is a
  sub-field marked unknown (B08, B21, B22, B60, B61); `null` is never zero.
- **`determination` block: changed** (revisions 2 and 3 had left it byte-identical). `existing_controls_suffice`
  stays `"undetermined"` and `necessary_e09_subset` stays `null`; `missing_decision` now names the founder's D3
  patch decision (apply / change / drop) as the Slice B allocation with the 19/38/95/190 ceiling; `missing_observations`
  rewritten (B32 with prerequisite B62; B39 with the counter semantics; B56); `evidence_ids` 26 → 39 (added B07,
  B08, B21, B22, B38, B46, B51, B52, B57, B59, B60, B61, B62; none removed); `hazard_ranking_for_current_beta` 4 → 5
  entries (SEC figures corrected to the two-bucket model and the "existing control" wording corrected per Appendix
  B; DB overlap case +8; provider quota re-evaluated on the published figures; new observation-blindness hazard);
  new `closed_since_revision_3` and `what_each_missing_item_resolves`.

## Effect on the COO disposition

`handbacks/coo/CURRENT-BETA-OPERATING-ENVELOPE-DISPOSITION.md` (SHA-256 `d30bdd50…`) evaluated revision 1 and reached
HOLD. Revision 4 changes load-bearing rows for the first time: B37 and B46 leave `unknown` (closed by records 02 D8
and D7), B51/B52 leave `unknown` (source read), B07/B08 become `observed`; B32, B39 and B56 remain `unknown`, and B62
is added as a prerequisite to the B32 route. The §5 determination remains `undetermined` with no E09 subset named as
necessary. The HOLD is not weakened by this revision; the COO disposition-update worker (provisional label
`coo-envelope-disposition-update-01`) is the next owner and states each of the eight C1 items' state.

## Hash chain

| File | Revision 3 SHA-256 (manifest `CTO-ENVELOPE-HANDBACK-02.json`) | Bytes | Revision 4 SHA-256 | Bytes |
|---|---|---:|---|---:|
| `CURRENT-BETA-OPERATING-ENVELOPE-HANDBACK.md` | `58ef902d0339ba812e859a764575f53828f60588b8104bf9318d79c69b0a967e` | 36,686 | `94c155c7c517b36b73d751a1935fa78060747907dd810fcbf84685ac19ee3d41` | 72,085 |
| `CURRENT-BETA-OPERATING-ENVELOPE-BOUNDS.json` | `5ee84009c08f8ecf107174376f67c34084f9461b162fdbc5864e718f4ce3c8fd` | 38,003 | `d675516eea6b401780e6dbe29061388573b5c736f4447b979bb86536a2577505` | 68,998 |

Revision 4 hashes were computed after the final write of both files (one wording correction to the §0
branch-advance note and the JSON `repository_note` followed the first write; both files were re-verified for
id/classification agreement afterwards). Revisions 1 and 2 remain in `CORRECTION-01.md`; revision 2 → 3 in
`CORRECTION-02.md`. This file cannot contain its own digest; the author reports it to the chief.

## Spend

0 DeepSeek calls; USD 0.000000; 0 reservations; 0 ledger events; 0 external mutations; files written: the three
outputs only.
