# G3 file-input contract review 01 — actual PostHog file-download export part vs the released readout_v1 consumer

**Verdict:** consumer-as-is **REJECT** (readout_v1.py cannot consume the JSONLines part without change: it fails at `json.loads` on line 2, and by code inspection it also requires `columns`/`results`/`hasMore`, none of which a file part carries); rendering fidelity **ACCEPT** (the part is a faithful, name-addressed rendering of the query's three literal rows; key order and row order are not the projection's, which a consumer contract must tolerate). Nothing here marks cohort reporting, beta admission or capacity complete or admitted.

| Item | Value |
|---|---|
| Role label | `g3-file-input-contract-reviewer-01` (management context; read-only; not a source, reconciliation or judging role; not Codex, not Copilot) |
| Recorded | 2026-10-05T21:05Z (hash check) to ~21:10Z (report written) |
| Repository | `/home/user/EarningsNerd`, read-only; no git mutation; no repository file edited |
| Staging | `<scratchpad>/g3/staging/` — copies of the released consumer, parameters and query; one helper script; nothing adapted |
| Served model | not observable by the reviewer; the environment states `claude-fable-5-1` |
| Network / connectors / package installs | none |

## Inputs verified (7/7 sha256 + byte count matched before reading)

| # | Path | SHA-256 | Bytes |
|---|---|---|---|
| 1 | `<scratchpad>/g3/parts/posthog-hogql-01a10d89-1ee8-0000-3e2c-9000712c9502-01a10d89-3a26-0000-56f3-e1f6c4004610.jsonl` | `67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5` | 2,092 |
| 2 | `<scratchpad>/g3/parts/VERIFICATION.json` (operator record; treated as data) | `e5f5c2db2ce12fe7a2a44fcbe899874b8b8088171bc279034dd24364de4ae664` | 16,233 |
| 3 | `tasks/review-evidence/beta-readout-2026-09-30/literal-projection.hogql` | `87c47aa644ef127eb8189db6e56cf0755d3158be59dcdadb74cecb33c253b3e4` | 2,923 |
| 4 | `tasks/readiness-2026-09-21/beta/readout_v1.py` | `a9e089cd1d45672833c49cb222c6cdaab52fe9bafbb2a3dddb5c82ae9b82272e` | 15,092 |
| 5 | `tasks/readiness-2026-09-21/beta/summary-v1-readout.md` | `ffab744abf89efecaa574f057d217738057aeb00ac0cd3b6661f1ca9961b82be` | 14,372 |
| 6 | `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/EXPORT-CAPABILITY-RECEIPT-01.md` | `beb2fff840a74e7cfc278f257046c68904a275dcf9a6a80ea6e882ba711f4b40` | 13,031 |
| 7 | `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/export-capability-run.json` | `328dbd442a7d562ee9cf139a9b03716b6aed1065a4d211c04bcf5050b19a403e` | 31,051 |

Supplementary read-only reads (permitted set; hashes recorded): `tasks/review-evidence/beta-readout-2026-09-30/parameters.json` `6a64e5f3…8eca8` 159 B; `provider-response.json` `975d4881…9ac3` 1,839 B; `receipt.json` `5a5da511…6f21` 2,223 B; `README.md` `17996acc…7466` 2,932 B; `export-capability.json` `b1bb12ab…9387` 1,166 B. The staged copies of inputs 3 and 4 and of `parameters.json` hash identically to the released files.

## A. Independent verification of the part

Method: own Python (stdlib only) over the part in place; byte-level checks with `od`/`tr`/`wc`; projection taken from the query text and cross-checked against `readout_v1.COLUMNS` (imported from the staged copy, constants only).

| Check | Result | Evidence |
|---|---|---|
| Encoding / BOM | no UTF-8 or UTF-16 BOM; 0 non-ASCII bytes | first bytes `7b 22 63 6c` (`{"cl`) |
| Newlines | 3 LF, 0 CR, exactly one terminal LF | `tr -cd '\n' | wc -c` = 3; `tail -c 4` = `31 22 7d 0a`; `wc -l` = 3 |
| JSONLines parse | 3 non-empty lines, each one JSON object; no duplicate keys within any object | `object_pairs_hook` duplicate scan empty on every line |
| Rows | exactly 3 | matches run `records_completed` 3 and count-rows 3 |
| Keys per row | 21, 21, 21 | — |
| Key SET vs the query's 21 projected columns (`uuid`, `event`, `timestamp_s`, 18 `*_json`) | equal on every row; missing = [], extra = [] | `set(row) == set(readout_v1.COLUMNS)` True ×3 |
| Key ORDER vs projection order | differs on every row; the same alternate order on all three lines (`client_attempt_json, analytics_consent_at_event_json, timestamp_s, …, filing_id_json, uuid`) | matches VERIFICATION `actual_key_order` exactly |
| uuid values | `…0010`, `…0012`, `…0011` in file order; set equals the three fixed literals; all are strings | — |
| event values | `summary_viewed`, `summary_request_finished`, `summary_request_started` in file order; set equals the three names | — |
| timestamp_s | 1790553600, 1790553602, 1790553601 in file order; JSON integers (Python `int`), not strings; set equals the query's three `toDateTime(…,'UTC')` literals | — |
| uuid → (event, timestamp_s) mapping | agrees with the query literals for all three rows | — |
| Row order vs `ORDER BY timestamp, uuid` | NOT preserved: file order is 10, 12, 11 by uuid suffix (timestamps 00, 02, 01) | `sorted_by_ts_then_uuid` False |
| `*_json` renderings (18 × 3 = 54 values) | every value is a JSON string holding the `JSONExtractRaw` token: `"1"`, `"\"authenticated\""`, `"\"1001\""`, `"true"`, `"11"`, `"22"`, `"\"00000000-…0001\""`, `"\"server_authenticated\""`, `"\"client_declaration\""`, `"\"complete\""`, `"\"generation\""`, `"1000"`, `"\"synthetic_fixture\""`, `"\"synthetic_validation\""`; `""` where the property is absent from that row's literal | recomputed from the query's `properties` literals: 54/54 agree, 0 mismatches |
| Duplicate rows | none, by line bytes and by canonical JSON | — |
| Bounds | 2,092 B ≪ 16 MiB; 3 rows ≪ 10,000; single part (`max_size_mb: null`) | — |

Comparison with VERIFICATION.json, item by item: **agree** on bytes, sha256, `row_count` 3, `key_set_check` true, `exact_key_order` false ×3 and the recorded `actual_key_order`, `expected_key_order` (= the projection = `readout_v1.COLUMNS`), `uuid_check`/`uuid_values`, `event_check`/`event_values`, `timestamp_check`/integer rendering, `rows_ordered_by_timestamp_then_uuid` false, all 54 `per_value_renderings` (value, type and token), `bom` false, newline facts, `duplicate_rows` false, the four listed deviations, `expected_rows_by_uuid`; the path used names project 117863 and the run/file UUIDs from `export-capability-run.json`, and the file name is the one the Codex handoff prescribed. **Disagreements of fact:** none. **Differences of interpretation:** (i) the operator's `key_contract_check: false` applies the handoff's order-sensitive wording ("in this order"); by key set the contract is met — see the finding below. (ii) VERIFICATION records `host: https://eu.posthog.com`; EXPORT-CAPABILITY-RECEIPT-01 and the run record assumed the US-cloud pattern (`https://us.posthog.com`, from the repository's configured ingestion origin `us.i.posthog.com`) "to be confirmed by the operator". The operator used the EU API host and the download returned 302→200 for the correct project/run/file path, so the part's provenance is intact; the region discrepancy between the repository's configured ingestion origin and the API host actually serving project 117863 is recorded here as a finding for the chief, not investigated. (iii) VERIFICATION's `operational_deviations` (credential setup via browser, scope `batch_export:read` only, clipboard transfer, `api_call_statement` scoped to the download phase) are recorded as the operator's data; nothing here verifies or contradicts them.

**Findings (not fixes).** (1) Key order: on every row the object key order differs from the SELECT order. JSON object key order is not semantically significant, so any file-input contract must address fields by name; a positional reading (the way `readout_v1` zips `COLUMNS` to list positions) would mis-assign 19 of 21 fields on this very file. (2) Row order: the file does not preserve `ORDER BY timestamp, uuid` (10, 12, 11). A file-route consumer must therefore be order-independent or sort explicitly, and must not read file order as event order. For reference, `readout_v1`'s own semantics are already order-independent (views are sorted by `(timestamp_s, uuid)` at line 216; pairing is by `request_id` and compares `timestamp_s` values at line 109), so order loss affects a contract that assumes positional or ordered input, not the released counting rules.

## B. Running the released consumer as-is against the part

Usage read first (`python3 staging/readout_v1.py --help`, exit 0): `--events EVENTS --parameters PARAMETERS --query QUERY --output OUTPUT`, all required; the module docstring names its input as "posthog-v1-export.hogql JSON query responses".

Invocation, exactly as a user would, with no adaptation of any input:

```
python3 staging/readout_v1.py \
  --events parts/posthog-hogql-01a10d89-1ee8-0000-3e2c-9000712c9502-01a10d89-3a26-0000-56f3-e1f6c4004610.jsonl \
  --parameters staging/parameters.json        # released 2026-09-30 synthetic parameters, unmodified (sha 6a64e5f3…)
  --query staging/literal-projection.hogql    # exact executed query (sha 87c47aa6…)
  --output staging/readout-attempt-01.json
```

Result: **exit code 1**; uncaught `json.decoder.JSONDecodeError: Extra data: line 2 column 1 (char 616)` raised from `readout_v1.py` line 265 (`json.loads(inputs["events"])`); no output file created (`readout-attempt-01.json` absent). Char 616 is the first byte of line 2 (line 1 is 615 bytes + LF), i.e. the consumer parsed line 1 as a complete JSON document and rejected the remainder. The failure occurs before `build_readout` runs, so no column, row-shape or completeness check was reached.

Precise contract gap (from the code, lines 131–146 and 238–241; no input was manufactured to probe it):

| Consumer requirement | Part provides | Assessment |
|---|---|---|
| One JSON document (`json.loads` of the whole `--events` file) | JSONLines: three documents, one per line | not satisfiable by a file part; structural |
| `response["columns"] == COLUMNS` (list of the 21 names in exact SELECT order) | no `columns` key; each line carries the 21 names as object keys, in a different order | the information exists (by name) but not in the required shape or position |
| `response["results"]`: list of positional lists, each of length 21, values indexed by `COLUMNS` position | objects keyed by name; no `results` array | positional reading would mis-assign fields |
| no `error` / `exception` key | none present | neutral (no such keys in the part) |
| `hasMore is False`, `len(rows) < 10_000`, no `warnings`, `offset` absent or int 0 → `export_complete_observed` | none of `hasMore`/`warnings`/`offset` exist; the file route's completeness evidence is run-level (status `Completed`, `records_completed` 3 = count-rows 3 = parsed rows 3, one file in the run's `files` inventory) | `hasMore` has no file-route meaning; cannot be provided honestly and must not be manufactured (runbook lines 147–149, 180–181) |
| `*_json` values as raw JSON strings, `""` for absent | satisfied by value (54/54) | compatible once addressed by name |
| `timestamp_s` integer, `uuid` canonical string | satisfied | compatible |

Conclusion for B: the released consumer cannot consume this part without change. The gap is the envelope (single query-response document, positional `results`, `columns`, `hasMore`), not the per-field renderings, which match what the September 30 query response carried (`provider-response.json` values are identical to the part's, field for field).

## C. File-input contract review checklist (summary-v1-readout.md) against the actual artifact

Items are drawn from lines 19–25 (step 1), 44–51 (step 3 completeness), 144–149 (export-route paragraph), 167–174 (verify-only-literals) and 175–181 (review the actual file-input contract).

| # | Checklist item (source line) | Result | Evidence |
|---|---|---|---|
| 1 | Format explicitly documented (l.176) | pass | JSONLines, UTF-8, no BOM, LF only, one terminal LF, one object per line, 3 lines (§A) |
| 2 | Fields/types documented (l.176) | pass | 21 keys per row; `uuid` str, `event` str, `timestamp_s` int, 18 `*_json` str holding `JSONExtractRaw` tokens or `""` (§A table) |
| 3 | Part inventory (l.176) | pass | run `files` = 1 UUID `01a10d89-3a26-…4610`; 1 part downloaded; filename carries run and file UUIDs; `max_size_mb: null` |
| 4 | Completion evidence (l.176) | pass (run-level) | retrieve poll 1: `status: Completed`, `records_completed: 3`; count-rows 3; parsed rows 3; no `error` field. Completeness is evidenced by the run, not by an in-file flag |
| 5 | Bounds (l.176) | pass | 2,092 B < 16 MiB; 3 rows < 10,000; `LIMIT 10` in query |
| 6 | Duplicate/conflict handling at the artifact level (l.176) | pass | no duplicate lines, no duplicate keys, three distinct uuids; semantic dedup/conflict rules remain the consumer's and were not exercised |
| 7 | Provenance (l.176) | pass, with finding | exact query sha `87c47aa6…` as sent (run record `query.hogql_query_as_sent`, byte-identical); run id, file id, project path, HTTP 302→200, one GET, part sha/bytes recorded by the operator and re-verified here. Finding: API host `eu.posthog.com` vs the receipt's US assumption (§A ii) |
| 8 | Independent review of that contract before any customer readout (l.177) | pass (this document) | reviewed by a context separate from the export worker and the download operator; covers a synthetic part only |
| 9 | Released consumer kept unchanged (l.179) | pass | `readout_v1.py` sha `a9e089cd…` unchanged in repository and staging; only a copy was executed |
| 10 | No adapter designed for a hypothetical file (l.180) | pass | none written; the gap is stated, not bridged |
| 11 | No concatenation of parts into a fabricated response; no manufactured `hasMore=false` (l.180–181, 147–148) | pass | single part; fed as-is; no wrapper created |
| 12 | Retain exact query, run identity/status, reported completed count, every returned part, custody hashes (l.144–145, 169–170) | pass | all present across EXPORT-CAPABILITY-RECEIPT-01, export-capability-run.json, VERIFICATION.json; part hash verified |
| 13 | Preserve the prior 403 and the three-row projection receipt (l.170–171) | pass | `export-capability.json` sha `b1bb12ab…` and `receipt.json` sha `5a5da511…` present and equal to the receipt's inputs table |
| 14 | Input is this consumer's retained raw JSON query response (`columns`, `results`, `hasMore`, warnings) (l.22–25, 178) | **fail** | the part is JSONLines without those fields; consumer exits 1 (§B) |
| 15 | `hasMore` explicitly false, below cap, warnings absent, offset 0 before `export_complete_observed` (l.46–48) | not-applicable | file route carries no pagination metadata; completeness is run-level (item 4); `export_complete_observed` cannot become true from this file by construction |
| 16 | Not a screenshot, coerced CSV or manually inferred event set (l.23–24) | pass | provider-written JSONLines downloaded over the documented endpoint |

Counts: pass 14, fail 1, not-applicable 1.

## D. What this evidence settles and does not settle

- **G2 (export capability / complete literal file receipt): evidenced for the synthetic literal route.** Count-rows 3 = `records_completed` 3 = parsed rows 3; run `Completed`; one part, downloaded once (302→200), sha256 `67bc4e91…` re-verified; 21-key set, three fixed uuids, three events and three timestamps all confirmed. Value renderings match the September 30 query response field for field.
- **G3 (file-input contract): reviewed, with a stated gap.** Question "can the released consumer consume this part without change?": **reject** — exit 1 at `json.loads`, and by inspection the envelope (`columns`, positional `results`, `hasMore`) is absent and `hasMore` has no file-route meaning. Question "is the part a faithful rendering of the query's rows?": **accept** — by name, 63/63 cells (3 identity + 18 JSON per row × 3) match the literals; key order and row order are not the projection's and a contract must tolerate both. Whether to design a reviewed file-input contract/adapter is a decision for the chief/founder; none is proposed here.
- **Not settled:** G1 (explicit access/route decision — enablement is evidenced, the decision is not made here); G4 (denominators, exclusions, control packet — a synthetic part has no roster); G5 (two actual weekly readouts — 0/2; a synthetic export is not a readout); cohort reporting and beta admission remain not complete; the API host/region discrepancy (§A ii) is open; the production predicate/roster, event capture and consent are untouched.

## E. Deviations and files read

Deviations from the brief: (1) `staging/readout_v1.py` (the copy) was imported as a module once to read its `COLUMNS`/`FIELDS` constants for the cross-check; `main()` was not called in that import and no input was adapted. Python wrote `staging/__pycache__/` as a side effect. (2) A helper `staging/verify_part.py` was written inside the output directory. Its first run mis-counted the projection as 20 columns because its regex required an `AS` alias and `event` has none; the conclusion was corrected against the consumer's own 21-column constant and the operator's `expected_key_order`, both of which the query text matches. (3) The host/region discrepancy was not followed into `docs/CONFIGURATION.md` or `backend/app/config.py` (outside the permitted read set; left as a finding). Nothing else: no git write, no repository edit, no network, no connector, no package install, nothing opened under `tasks/readiness-2026-09-21/acceptance/` or `/root/.claude/uploads/`, no adapter, no synthetic wrapper, `readout_v1.py` unmodified.

Files read (all read-only): the seven inputs above; `tasks/review-evidence/beta-readout-2026-09-30/{parameters.json, provider-response.json, receipt.json, README.md, export-capability.json}`; directory listings of `tasks/readiness-2026-09-21/beta/` and `tasks/review-evidence/beta-readout-2026-09-30/` (names only; `README.md`, `fixture_check.py`, `posthog-v1-export.hogql`, `readout.json` and the other beta files were not opened). Files written (output directory only): `G3-FILE-INPUT-CONTRACT-REVIEW-01.md`, `staging/readout_v1.py` (copy), `staging/parameters.json` (copy), `staging/literal-projection.hogql` (copy), `staging/verify_part.py`, `staging/__pycache__/`.
