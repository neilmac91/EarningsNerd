# ADAPTER-NOTES — D5 Option A: file-download export parts → released v1 consumer (CTO-FILE-EXPORT-ADAPTER-07)

**Status: staged outside the repository for the chief to place. Nothing here was placed in `/home/user/EarningsNerd`;
`git status` stayed clean (branch `claude/vigilant-goodall-633yx3` at `ad915c44`). No network, connector, PostHog or HTTP
call; no package install; stdlib only; nothing opened under `tasks/readiness-2026-09-21/acceptance/` or
`/root/.claude/uploads/`. The released consumer `readout_v1.py` is byte-unchanged (sha `a9e089cd…`, 15,092 B). The
capability part holds invented literals only. Nothing in this file states or implies that cohort reporting, beta
admission or capacity is complete or admitted; G1–G5 are not settled by an adapter.**

| Item | Value |
|---|---|
| Role label | `cto-file-export-adapter-writer-01` (minimal implementation writer; not a reviewer, not an operator) |
| Manifest | `<scratchpad>/adapter/CTO-FILE-EXPORT-ADAPTER-07.json` — sha256 `6a2115cab899119b32caa1be24b93c00e0a55fca13ac339630bbded46a5efb40`, 8,264 B, verified before reading |
| Authority | Founder 2026-10-05 ~21:15Z: D5 Option A (thin adapter; released consumer byte-unchanged); D4 (one offline consumer dry run on the three-row part once D5 is authored). G3 review 01: rendering ACCEPT, consumer-as-is REJECT — the condition for authoring |
| Recorded | 2026-10-05 ~21:36Z (hash checks) to ~21:48Z (this file) |
| Served model | not observable by the worker; the environment states `claude-fable-5-1` |
| Python / ruff | Python 3.11.15; ruff 0.15.20 (already on PATH; nothing installed) |

## 1. Inputs verified (12/12 sha256 + byte count matched BEFORE any input was read)

| # | Path | SHA-256 | Bytes |
|---|---|---|---|
| 1 | `<scratchpad>/coo-file-route-rev3/staging/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md` (contract rev 3; §2.0, §2.3, §3 read) | `ad599074e6f27149b6bfb736fccdb45014d1bdc411a2b087165a23d09e9b16dd` | 47,321 |
| 2 | `<scratchpad>/coo-file-route-rev3/staging/FOUNDER-DECISIONS-FILE-ROUTE.md` | `7bfe1e63c0b56ffac9bced4161df747ed711e162274e1788571980f854fa906c` | 14,894 |
| 3 | `tasks/readiness-2026-09-21/beta/readout_v1.py` | `a9e089cd1d45672833c49cb222c6cdaab52fe9bafbb2a3dddb5c82ae9b82272e` | 15,092 |
| 4 | `tasks/readiness-2026-09-21/beta/fixture_check.py` | `a8aa46d1829f5720dbb29e63ada8d85fb4a1011af989c306cf380d73bfc1add8` | 28,307 |
| 5 | `tasks/readiness-2026-09-21/beta/posthog-v1-export.hogql` | `fa060fe65a078f90d4836d2f60361ff36def4fdf0da34f0eb24b3dbdf0bf47ef` | 2,612 |
| 6 | `<scratchpad>/g3/parts/posthog-hogql-01a10d89-1ee8-0000-3e2c-9000712c9502-01a10d89-3a26-0000-56f3-e1f6c4004610.jsonl` | `67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5` | 2,092 |
| 7 | `<scratchpad>/g3/parts/VERIFICATION.json` | `e5f5c2db2ce12fe7a2a44fcbe899874b8b8088171bc279034dd24364de4ae664` | 16,233 |
| 8 | `<scratchpad>/g3/G3-FILE-INPUT-CONTRACT-REVIEW-01.md` | `eb21a01378e3364ac8bb7012a14ef4a914bf215085fa65a5bff4f1ea375570e6` | 18,313 |
| 9 | `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/export-capability-run.json` | `328dbd442a7d562ee9cf139a9b03716b6aed1065a4d211c04bcf5050b19a403e` | 31,051 |
| 10 | `tasks/review-evidence/beta-readout-2026-09-30/parameters.json` | `6a64e5f39d9bee9fd211e276a437274cd4a041df2531a10e1478d4f152d8eca8` | 159 |
| 11 | `tasks/review-evidence/beta-readout-2026-09-30/readout.json` | `086be5e51d29646a92eae14dab628c057a8f665c1fa0154adc4643a299cdfb7e` | 2,430 |
| 12 | `tasks/review-evidence/beta-readout-2026-09-30/literal-projection.hogql` | `87c47aa644ef127eb8189db6e56cf0755d3158be59dcdadb74cecb33c253b3e4` | 2,923 |

The staged copies of inputs 3, 4 and 5 were `cmp`-identical to the repository files before work began.

## 2. What was built

| File (all under `<scratchpad>/adapter/staging/`) | What it is |
|---|---|
| `file_export_to_v1.py` (new, 8,822 B) | The adapter: `parse_record`, `v1_response_from_parts`, `file_export_completeness`, and a CLI. Stdlib only (`argparse`, `hashlib`, `json`, `os`, `re`, `collections.abc`, `pathlib`); imports `COLUMNS` and `MAX_ROWS` from `readout_v1` in the same directory; `from __future__ import annotations`; type hints; module docstring states no network/database access |
| `fixture_check.py` (released file + insertion, 40,109 B) | The released file with `check_file_export_adapter()` inserted before `main()` and an `--adapter-only` flag. `diff` against the released file shows **0 deleted or changed lines** (insertion only); `--v1-only` output is **byte-identical** to the released file's own run (sha `cf6ebba0…`, 741 B, both) |
| `ADAPTER-NOTES.md` | This file |
| `d4-run-record.json` (163 B) | The D4 run record, derived from input 9: `run.polls[0].response` (`{"status":"Completed","files":["01a10d89-3a26-0000-56f3-e1f6c4004610"],"records_completed":3}`) plus `run.id`; proven equal to that response + id by a Python equality check before use |
| `d4-events.json`, `d4-completeness.json`, `d4-readout.json` (mode 0600) | D4 offline dry-run outputs (§7) |
| `adapter-only.out`, `v1-only.out` | The exact stdout of the two fixture runs (§5) |
| `readout_v1.py`, `posthog-v1-export.hogql` | Unmodified copies (hashes equal to inputs 3 and 5) |

### 2.1 Public functions (exactly as the manifest names them)

- `parse_record(parts: list[bytes]) -> dict` → `{"parts": [{bytes, bom, cr_bytes, trailing_newline, lines, rows, key_order_matched_rows} …], "totals": {parts, bytes, cr_bytes, lines, rows, key_order_matched_rows}}`. Raises `ValueError` naming the part index (0-based, list position) and the line (1-based) on a BOM (`part 0: byte-order mark present`), a key-set mismatch (`part 1 line 1: key set mismatch (missing=['uuid'], extra=['id'])`), a non-object line, invalid JSON / UTF-8, or a part over 16 MiB. `bom` is always `False` in a returned record (a BOM raises); `lines == rows` by construction (every surviving line must be an object). CR bytes are counted and left in place (JSON tolerates a trailing `\r`).
- `v1_response_from_parts(parts: list[bytes]) -> dict` → exactly `{"columns": COLUMNS, "results": [[obj[c] for c in COLUMNS] …]}`, parts order then line order, values as decoded (no coercion), nothing else (no `hasMore`, `offset`, `warnings`, `error`).
- `file_export_completeness(run_record: dict, parts: list[dict], n_before: int | None, n_after: int | None) -> dict` → `{status, error, records_completed, n_before, n_after, rows_parsed, files, file_export_complete_observed, failing_rules}`; `files` is the parts inventory passed in (`[{id, sha256, bytes, rows} …]`); `file_export_complete_observed` is `True` iff `failing_rules` is empty (§4).
- CLI: `python3 file_export_to_v1.py --parts <file> [<file> …] --run-record <json> --n-before N [--n-after N] --output <v1 events json> --completeness-output <json>`. Each part is read to at most 16 MiB + 1 byte and the bound raises; the run record is bounded the same way; each part's `id` is the trailing UUID of its file name (the download leg's `posthog-hogql-<run>-<file>.jsonl` naming; the stem otherwise) and its `sha256` is computed from the bytes read; both outputs are written with `os.O_EXCL`, mode `0o600`, `json.dumps(sort_keys=True, indent=2, allow_nan=False) + "\n"`, never overwriting.

## 3. Mapping to contract §2.3 "Option A — adapter", line by line

| Contract §2.3 Option A text | Implementation (file_export_to_v1.py) |
|---|---|
| "A new, separately reviewed module (suggested home `tasks/readiness-2026-09-21/beta/file_export_to_v1.py`) with two pure functions and no network" | New module staged as `file_export_to_v1.py`; placement is the chief's. Module docstring: "No network/database access." Imports are stdlib plus `readout_v1` constants only. Two pure functions as named, plus the manifest's companion `parse_record` (same parser, facts only) |
| "(1) `v1_response_from_parts(parts: list[bytes]) -> dict`" | Defined with that exact signature |
| "rejects a BOM" | `part.startswith((b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff"))` → `ValueError("part {i}: byte-order mark present")` (fixture `rejections.bom`) |
| "splits each part on `\n`" | `part.split(b"\n")` — no universal-newline handling, so `\r` is never stripped (counted in `cr_bytes`) |
| "ignores only a single trailing empty line" | `if lines[-1] == b"": lines.pop()` once; any other empty line fails `json.loads` → `ValueError("part 0 line 3: invalid JSON …")` (fixture `rejections.second_trailing_empty_line`) |
| "`json.loads` each line into an object" | `json.loads(line.decode("utf-8"))`; a non-dict → `ValueError("… not a JSON object")` (fixture `rejections.non_object_line`) |
| "requires the object's key **set** to equal `COLUMNS` (records whether the key order matched)" | `set(obj) != set(COLUMNS)` → `ValueError` listing `missing`/`extra`; `key_order_matched_rows += list(obj) == COLUMNS` per part and in totals. On the actual part: key set equal on all 3 rows, `key_order_matched_rows` 0 (the G3 finding: fields are mapped by name, never by position) |
| "emits `{"columns": COLUMNS, "results": [[obj[c] for c in COLUMNS] for each object, parts in `files[]` order, lines in file order]}`" | Exactly that expression; the operator passes `--parts` in `files[]` order; row order is file order (the G3 finding: `readout_v1` is order-independent, confirmed by the fixture's end-to-end equality and by D4) |
| "**sets no `hasMore`, `offset` or `warnings`**" | The response dict has exactly two keys; fixture asserts `set(response) == {"columns", "results"}`; the CLI writes that dict unchanged |
| "performs **no type coercion** (a string `timestamp_s` stays a string and is diagnosed by the consumer as `malformed_event_identity`; the remedy is a reviewed projection change, not adapter coercion)" | Values are the decoded JSON values verbatim. Observed (not assumed) on the actual part with one `timestamp_s` rewritten to a string: the adapter passes `'1790553600'` through and `build_readout` reports `{"row": 0, "uuid": "…0010", "reason": "malformed_event_identity"}`; the fixture asserts the same reason on its own rows |
| "(2) `file_export_completeness(run_record, parts: list[{id, sha256, bytes, rows}], n_before, n_after) -> dict` — emits `{status, error, records_completed, n_before, n_after, rows_parsed, files, file_export_complete_observed}` where `file_export_complete_observed` is true iff the §2.0 step-8 rule holds" | Defined with that signature and those keys, plus `failing_rules` (manifest). `status`/`error`/`records_completed` are the run record's; `rows_parsed = Σ rows` over the inventory; `files` = the inventory; the verdict is `not failing_rules` (§4) |
| "The consumer's own `export_complete_observed` stays `false` and its `limits` list unchanged" | `readout_v1.py` is byte-unchanged; D4 output has `export_complete_observed: false` and the identical five `limits` strings; the fixture asserts `False` from both the adapter output and the equivalent direct response |
| "the readout receipt carries `file_export_complete_observed` from the adapter record and states that the consumer field is query-route-only" | The adapter writes the record (`--completeness-output`); the receipt is the operator's document. `d4-completeness.json` is the record for the capability run (§7) |
| "`fixture_check.py` gains fixtures for the adapter only" | `check_file_export_adapter()` + `--adapter-only`; `check_v1_readout()` and `--v1-only` untouched (insertion-only diff; byte-identical output) |
| Rule row: "No `hasMore=false` is manufactured; no parts are concatenated into a 'completed' response" | No completeness fact ever enters the response object; a part whose id is not in the run's `files[]` is a failing rule (`part … is not in this run's files inventory`), so parts of two runs cannot be presented as one complete export |

## 4. Contract §2.0 step 8 as implemented (`file_export_completeness`)

`complete` iff **all** hold; each violation appends one entry to `failing_rules`, and the verdict is `True` only when the list is empty:

| Step-8 clause | Rule text appended when violated |
|---|---|
| terminal status `Completed` | `status {status!r} is not Completed` |
| no `error` | `error field present: {value!r}` — the key's presence fails, even when its value is `null` |
| `n_before = n_after = records_completed = rows_parsed` | `{name} not observed` for each `None` (in particular **`n_after not observed`** when `n_after` is `None`); `{name} is not an integer: …` for a non-`int` (bool excluded); `counts differ: n_before=…, n_after=…, records_completed=…, rows_parsed=…` when the observed integers are not all equal |
| `n_before < 10000` | `n_before {n} is not below the LIMIT cap 10000` (cap = `readout_v1.MAX_ROWS`) |
| every id in `files[]` downloaded and hashed | `files inventory absent from the run record` if `files` is not a list of strings; `file {id} not downloaded and hashed` for each declared id missing from the inventory; `part inventory entry lacks id/sha256/bytes/rows: …` for a malformed entry; and `part {id} is not in this run's files inventory` for an inventory part the run did not declare (never concatenate across runs) |
| no pricing signal | `status FailedBilling (pricing signal)`; and, for every string value anywhere in the run record (recursively through dicts and lists) containing `payment`, `plan`, `billing`, `trial` or `quota` case-insensitively as a substring: `pricing signal [terms] in run record text: {text!r}` (reported verbatim; a false positive fails closed) |
| a zero-row export is `complete (zero rows)` only with the source-availability record | `zero rows without a source-availability record` unless `run_record["source_availability_recorded"] is True` |

`source-unavailable` (connector/HTTP failure) is not a state the adapter can know; the operator records it in the receipt before any part exists. The adapter never re-runs, re-counts, truncates or widens anything.

## 5. Fixture outputs (exact stdout, run from the staging directory)

`PYTHONDONTWRITEBYTECODE=1 python3 fixture_check.py --adapter-only` → exit 0, stderr empty:

```
{"actual_cli_roundtrip": "passed", "adapter_fixture_parts": 2, "adapter_fixture_rows": 4, "completeness_false_cases": {"error_field": ["error field present: None"], "failed_billing": ["status 'FailedBilling' is not Completed", "status FailedBilling (pricing signal)", "pricing signal ['billing'] in run record text: 'FailedBilling'"], "limit_cap": ["n_before 10000 is not below the LIMIT cap 10000"], "missing_file_id": ["file 00000000-0000-4000-8000-000000000999 not downloaded and hashed"], "n_after_mismatch": ["counts differ: n_before=4, n_after=5, records_completed=4, rows_parsed=4"], "n_after_none": ["n_after not observed"], "part_from_another_run": ["counts differ: n_before=4, n_after=4, records_completed=4, rows_parsed=6", "part 00000000-0000-4000-8000-000000000998 is not in this run's files inventory"], "pricing_text": ["pricing signal ['plan'] in run record text: 'Upgrade your plan'"]}, "completeness_true_case": true, "download_or_hogql_live_execution": "not performed", "end_to_end_readout_equal": true, "export_complete_observed": {"from_direct": false, "from_parts": false}, "key_order_matched_rows": 1, "rejections": {"bom": "part 0: byte-order mark present", "key_set_mismatch": "part 1 line 1: key set mismatch (missing=['uuid'], extra=['id'])", "non_object_line": "part 1 line 1: not a JSON object", "second_trailing_empty_line": "part 0 line 3: invalid JSON (Expecting value: line 1 column 1 (char 0))"}, "string_timestamp_s_consumer_reasons": ["malformed_event_identity"], "zero_rows": {"with_source_availability_record": true, "without_source_availability_record": ["zero rows without a source-availability record"]}}
```

What the adapter fixture covers: two synthetic parts (4 rows: one view, one started/finished pair split across the two parts with the finish in part one before the start in part two, one view by a second account) with rotated/reversed key order on three rows and projection order on one, part one with a trailing LF, part two with one CR before an LF and no trailing LF; `v1_response_from_parts(parts) == expected` (file order); `parse_record` facts; BOM, key-set mismatch, second trailing empty line and non-object line each raise `ValueError` naming part and line; a string-typed `timestamp_s` passes through uncoerced and the consumer's diagnostics give `malformed_event_identity`; completeness true case equals the full expected record; false cases (`n_after` mismatch, missing file id, `FailedBilling`, `n_after` `None`, error field, pricing text, part from another run, LIMIT cap); zero-row part with and without `source_availability_recorded`; CLI round trip by subprocess (both outputs mode `0600`, contents equal to the in-process results, second run exits non-zero — no overwrite), then the released `readout_v1.py` CLI consumes the adapter's `events.json` and equals `build_readout` in-process; end to end `build_readout(v1_response_from_parts(parts), parameters) == build_readout(direct_response_in_ORDER_BY_order, parameters)` with `export_complete_observed` `False` in both by construction (the direct response carries no `hasMore`).

`PYTHONDONTWRITEBYTECODE=1 python3 fixture_check.py --v1-only` → exit 0, stderr empty:

```
{"actual_cli_roundtrip": "passed", "eligible_denominator": 5, "hogql_live_execution": "not performed", "missing_success_summary_id_statuses": {"complete_missing": "ambiguous", "complete_null": "ambiguous", "partial_missing": "ambiguous", "partial_null": "ambiguous"}, "paired_outcomes": {"cancelled": 1, "complete": 3, "error": 2, "incomplete": 1, "partial": 1, "rejected": 2, "timed_out": 1}, "poisoned_request_reasons": {"00000000-0000-0000-0000-000000001009": ["conflicting_event_uuid"], "00000000-0000-0000-0000-000000001010": ["malformed_event_identity"], "00000000-0000-0000-0000-000000001011": ["excluded_account"]}, "request_statuses": {"ambiguous": 13, "missing_finish": 1, "missing_start": 1, "paired": 11}, "v1_fixture_rows": 67}
```

The same command on the **released** `fixture_check.py` (copied with `readout_v1.py` and `posthog-v1-export.hogql` into a temporary directory, then deleted) produced byte-identical stdout: sha256 `cf6ebba0cebf8288ee288ab0378c4262104b6ebfface304e74d8297b1c129c47`, 741 B, for both.

## 6. Compile and lint

- `python3 -m py_compile file_export_to_v1.py fixture_check.py` → ok (both). The `__pycache__/` it wrote in staging was removed afterwards.
- `ruff check --isolated file_export_to_v1.py fixture_check.py` (ruff defaults) → `All checks passed!` (exit 0).
- `ruff check --config /home/user/EarningsNerd/backend/ruff.toml file_export_to_v1.py fixture_check.py` (the repository gate's rule set: `E4`, `E7`, `E9`, `F`; E501 ignored; py311) → `All checks passed!` (exit 0).
- Baseline: `ruff check --isolated` on the released `fixture_check.py` → `All checks passed!`.

## 7. D4 offline dry run (no connector call, no customer data; the three-row invented-literal part)

Commands, run from the staging directory (`<part>` = input 6; `<R>` = `/home/user/EarningsNerd/tasks/review-evidence/beta-readout-2026-09-30`):

```
PYTHONDONTWRITEBYTECODE=1 python3 file_export_to_v1.py --parts <part> --run-record d4-run-record.json --n-before 3 \
  --output d4-events.json --completeness-output d4-completeness.json          # exit 0 (n_after not passed: not observed in the capability run)
PYTHONDONTWRITEBYTECODE=1 python3 readout_v1.py --events d4-events.json --parameters <R>/parameters.json \
  --query <R>/literal-projection.hogql --output d4-readout.json               # exit 0
```

All three outputs have mode `0600`. `d4-run-record.json` (derived from input 9; `n_before` 3 from `count_rows_result`; no `n_after` was taken in that run — contract §2.2 records this as a limitation of the capability receipt):

```
{
  "files": [
    "01a10d89-3a26-0000-56f3-e1f6c4004610"
  ],
  "id": "01a10d89-1ee8-0000-3e2c-9000712c9502",
  "records_completed": 3,
  "status": "Completed"
}
```

Completeness record `d4-completeness.json`, verbatim (**incomplete, as expected: `n_after` not observed**):

```
{
  "error": null,
  "failing_rules": [
    "n_after not observed"
  ],
  "file_export_complete_observed": false,
  "files": [
    {
      "bytes": 2092,
      "id": "01a10d89-3a26-0000-56f3-e1f6c4004610",
      "rows": 3,
      "sha256": "67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5"
    }
  ],
  "n_after": null,
  "n_before": 3,
  "records_completed": 3,
  "rows_parsed": 3,
  "status": "Completed"
}
```

`parse_record` on the part: `{"parts": [{"bytes": 2092, "bom": false, "cr_bytes": 0, "trailing_newline": true, "lines": 3, "rows": 3, "key_order_matched_rows": 0}], "totals": {"parts": 1, "bytes": 2092, "cr_bytes": 0, "lines": 3, "rows": 3, "key_order_matched_rows": 0}}` — agrees with VERIFICATION.json and the G3 review (no BOM, 0 CR, one terminal LF, 3 rows, key set equal, key order never the projection's).

`d4-events.json` (sha256 `e37fed76e32e7252bdcdc4791e4b797b2df7347cd870685e9d9718b17c8971b0`, 1,839 B): `columns` = the 21 names in projection order; `results` = the three rows in **file order** (uuid …0010, …0012, …0011; timestamps 1790553600, 1790553602, 1790553601), each value exactly as the part renders it (`timestamp_s` integers; `*_json` raw-JSON strings, `""` where absent); no other key.

Field-by-field comparison of `d4-readout.json` with `<R>/readout.json` (input 11), 20 top-level fields:

```
fields compared: 20
fields equal: 19
DIFF ('input_sha256.events', '975d48819b360e4da249d1bb6b90d9ddefbc79b168c731a25f64f8d6563f9ac3', 'e37fed76e32e7252bdcdc4791e4b797b2df7347cd870685e9d9718b17c8971b0')
export_complete_observed baseline/d4: False False
```

Identical: `conflicting_event_uuids` `[]`, `diagnostics` `[]`, `duplicate_uuid_deliveries` 0, `eligible_denominator` 1, `export_complete_observed` `false`, `export_row_count` 3, `input_sha256.parameters` `6a64e5f3…`, `input_sha256.query` `87c47aa6…`, `limits` (five strings), `observed_view_accounts` 1, `paired_outcome_counts` `{"complete": 1}`, `poisoned_request_ids` `[]`, `poisoned_request_reasons` `{}`, `project_unattributable_event_count` `null`, `readout_version` 1, `request_status_counts` `{"paired": 1}`, `requests` (one paired request `…0001`, account `1001`, filing 11, `event_uuids` [`…0011`, `…0012`], terminal complete/generation/summary 22/invoked true/reason `synthetic_fixture`, `paired_duration_ms` 1000), `unobserved_view_accounts_unknown` 0, `users` (account `1001`, one view `…0010` at 1790553600, `observed_later_week_new_filing_return` `null`), `window_start`/`window_end`. **Only `input_sha256.events` differs**, because the events input is now the adapter's file-ordered response rather than the September 30 provider response (`975d4881…`); `export_complete_observed` is `false` in both, by construction. This is the expected D4 result: the JSONLines → consumer path yields the retained September 30 readout (one view, one paired complete request, 1,000 ms) from the actual part.

## 8. Staged files (sha256, bytes) — `<scratchpad>/adapter/staging/`

| File | SHA-256 | Bytes |
|---|---|---|
| `file_export_to_v1.py` | `94f433cefcb0cacf6208d659f3f166cc528b7d543fc11f4b5f7a2b46a4b8b337` | 8,822 |
| `fixture_check.py` | `efe09f076abd82c81e1a11f45af5078505d7a1fd93e4fec57456ced01f5d1353` | 40,109 |
| `readout_v1.py` (unchanged copy) | `a9e089cd1d45672833c49cb222c6cdaab52fe9bafbb2a3dddb5c82ae9b82272e` | 15,092 |
| `posthog-v1-export.hogql` (unchanged copy) | `fa060fe65a078f90d4836d2f60361ff36def4fdf0da34f0eb24b3dbdf0bf47ef` | 2,612 |
| `d4-run-record.json` | `361421f4b4c112d282c1b42ee4bd139481981dbaa1ee1a8c7d3720129b95c58e` | 163 |
| `d4-events.json` | `e37fed76e32e7252bdcdc4791e4b797b2df7347cd870685e9d9718b17c8971b0` | 1,839 |
| `d4-completeness.json` | `b2f7c87147e725dc96bd73497164b68c721c226a9c505d6f1e934851c0789f7a` | 425 |
| `d4-readout.json` | `1c64010f9e9296ffeaaf72fd284e2ae58a8100c1b70459b764065cb200589840` | 2,430 |
| `adapter-only.out` | `3aa6b21635a71dca72a19a44c2e3505dd9f456ce7fbd330ccd48aa9932930d72` | 1,646 |
| `v1-only.out` | `cf6ebba0cebf8288ee288ab0378c4262104b6ebfface304e74d8297b1c129c47` | 741 |
| `ADAPTER-NOTES.md` | (this file — hash and byte count in the handback summary) | — |

## 9. Files read (all read-only)

The manifest and the twelve inputs in §1 (each after its hash check). Additionally, outside the allowed-inputs list: `/home/user/EarningsNerd/backend/ruff.toml` (lint configuration only, to run ruff under the repository gate's rule set; hash in the handback) and `ls` of `backend/` for config file names. Nothing under `tasks/readiness-2026-09-21/acceptance/` or `/root/.claude/uploads/`; no other repository file; no `summary-v1-readout.md`, `README.md`, `provider-response.json` or receipt was opened.

## 10. Deviations and side effects

1. `file_export_to_v1.py` imports `MAX_ROWS` as well as `COLUMNS` from `readout_v1`, so the 10,000 cap is the consumer's own constant rather than a duplicated literal.
2. `file_export_completeness` adds one rule beyond the literal step-8 wording: an inventory part whose id is not in the run's `files[]` fails (`part … is not in this run's files inventory`). It enforces the step-8 "never concatenate parts across runs" sentence; without it two runs' parts could pass the count equalities.
3. Parse rejections beyond the two the manifest names (BOM, key-set mismatch): a non-object line, invalid JSON or non-UTF-8 bytes on a line (which is how any empty line other than the single trailing one is rejected), and a part over 16 MiB — all `ValueError` naming part and line. No input is ever repaired or skipped.
4. Rows per part are reported as both `lines` and `rows`; they are equal by construction once parsing succeeds, and are kept because the manifest names both.
5. The pricing scan is a case-insensitive substring match over every string value in the run record; a word such as "explanation" would fail the verdict (fail-closed, reported verbatim). The `error` rule fails on the key's presence even when it is `null`.
6. `files` in the completeness output is the inventory passed in (the downloaded-and-hashed evidence), not a copy of the run's declared ids; a mismatch in either direction appears in `failing_rules`.
7. Fixture additions beyond the enumerated list: one CR-before-LF line and a part without a trailing LF (to prove CR is recorded, not stripped, and both trailing-newline branches), four more false completeness cases (error field, pricing text, part from another run, LIMIT cap), a `parse_record` assertion on an empty part, and a subprocess run of the released `readout_v1.py` CLI on the adapter's `events.json`. `check_v1_readout()` was not touched; adding `--adapter-only` changes `fixture_check.py --help` text only.
8. The first `--adapter-only` run failed on a bug of this worker's (the fixture's `row()` helper passed `account_id_at_event` both as a default and via `**props`: `TypeError: dict.update() got multiple values for keyword argument`). The helper was corrected to apply defaults then overrides; the run recorded in §5 is the corrected one. The adapter module itself was not changed by this fix.
9. Side effects outside staging, all under `<scratchpad>/adapter/`: a one-off `extend_fixture.py` that performed the insertion into the staged `fixture_check.py` (kept for reproducibility; not a deliverable), and a temporary `released-v1only-*` directory holding copies of the three released files for the byte-identity check (deleted). Inside staging: `__pycache__/` (from `py_compile`) and `.ruff_cache/` (from ruff) were removed; two empty `*.err` capture files were removed; `adapter-only.out` and `v1-only.out` were kept as the recorded outputs.
10. The D4 run record is a derived file (retrieve response + run id from input 9), not a connector response as returned — the capability run's response is retained in input 9 and the derivation was asserted equal before use. `n_after` was deliberately not passed: it was not observed in that run.
11. The repository was not modified: `git status --porcelain` was empty before and after; no file under `/home/user/EarningsNerd` was written.

**Closing statement.** This adapter and its fixtures demonstrate that a completed file-download export's parts can reach the released consumer unchanged, and that the capability run's part reproduces the retained September 30 readout. They do not make any export complete (the capability run's own record is `incomplete: n_after not observed`), do not settle G1–G5, and do not mark cohort reporting, beta admission or capacity complete or admitted.

## Revision 2 (review findings) — 2026-10-05 ~22:44Z (files written 22:44:16Z and 22:44:59Z), same worker, PR #1100 head `7ee540aa` review: NO BLOCKER, should-fix + nits applied

Edited in place in the repository (not committed; the chief commits): `tasks/readiness-2026-09-21/beta/file_export_to_v1.py` and `tasks/readiness-2026-09-21/beta/fixture_check.py`. `readout_v1.py` byte-unchanged (sha `a9e089cd…`). No network, connector, HTTP call or install; nothing under `acceptance/` or `/root/.claude/uploads/`. Where this revision changes a rule, it supersedes the matching revision-1 text (§4 rows "no `error`", "no pricing signal" and "zero rows"; §10 items 2 and 5).

**Changes — `file_export_to_v1.py` (the single rule owner for step 8). Correction: the operator script does carry an inline fallback of step 8, and that fallback is NOT byte-equivalent to this module's rule — the duplicate-part, files-order and hex-digest checks exist only in the adapter — so a verdict is authoritative only when it comes from `file_export_completeness`.**

1. (1a) `error` fails only when the key is present with a value not in `(None, "")`: a retrieve response carrying `"error": null` or `""` is not a failure. Rule text unchanged: `error field present: {value!r}`.
2. (1b) Pricing scan: `payment`/`billing`/`trial`/`quota` as case-insensitive substrings, `plan`/`plans` only as whole words (`re.compile(r"payment|billing|trial|quota|\bplans?\b", re.IGNORECASE)`), so "explanation" is not a signal; the rule names the matched terms and the text verbatim.
3. (1c) Zero rows are complete only when the caller passes the explicit keyword argument `source_availability_recorded=True` (new keyword-only parameter, default `False`); a key spliced into the run record is **not** read. Rule text kept: `zero rows without a source-availability record`. The CLI exposes it as `--source-availability-recorded`.
4. (2) `rows_parsed` is summed over the parts **as supplied** (a list, no longer an id-keyed dict); a repeated id adds `part <id> supplied more than once`; the CLI refuses duplicate `--parts` paths (`refusing duplicate --parts paths`, compared after `resolve()`) and duplicate part ids (`refusing duplicate part ids: …`) before reading or writing anything.
5. (nit) Lines are parsed with an `object_pairs_hook` that raises on a repeated key → `ValueError("part i line n: duplicate key 'k'")`.
6. (nit) The CLI checks that `--output` and `--completeness-output` differ and that neither exists before writing either, and exits with a one-line message (`refusing to overwrite <path>`, exit 1) instead of a traceback; `os.O_EXCL` remains the atomic guard underneath.
7. (nit) New failing rules: `supplied part ids [...] do not equal the run's files inventory [...]` whenever `[p["id"] for p in parts] != run_record["files"]` (order or multiplicity; it fires alongside the specific missing/extra/duplicate rules, which are kept for precision), and `part <id> sha256 is not 64 hex characters: …`.

**Changes — `fixture_check.py` (insertion/edits inside `check_file_export_adapter()` only; `check_v1_readout()` untouched — diff against the released file `a8aa46d1…` still shows 0 deleted or changed released lines):** new rejection `duplicate_key`; passing cases `error_null`, `error_empty`, `explanation_text`; false cases `error_text` (`"error": "boom"`, replacing the revision-1 `error_field: null` case, which now passes), `pricing_plural` ("see Plans"), `duplicate_part_id` (asserts `rows_parsed == 6` over the parts as supplied), `out_of_order_files`, `bad_sha256`; zero-row case asserts the spliced run-record key does **not** complete the export while the explicit keyword argument does; CLI checks assert the one-line refusals (`refusing to overwrite`, `refusing duplicate`) with no traceback and that a refused run writes nothing; and a D4-parity pin: the adapter on the committed capability part (`REPO / tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/parts/posthog-hogql-…4610.jsonl`) with `tasks/review-evidence/beta-readout-2026-09-30/parameters.json` must `build_readout` to `tasks/review-evidence/beta-readout-2026-09-30/readout.json` minus `input_sha256`, with `export_complete_observed` false.

**Verification (from a mirror copy at depth ≥ 3 — `<scratchpad>/adapter/rev2/tasks/readiness-2026-09-21/beta/` with the evidence files mirrored at their repository-relative paths so `REPO = HERE.parents[2]` resolves — and once more in place from the repository directory with `PYTHONDONTWRITEBYTECODE=1`; outputs identical):**

- `python3 fixture_check.py --adapter-only` → exit 0, stderr empty:

```
{"actual_cli_roundtrip": "passed", "adapter_fixture_parts": 2, "adapter_fixture_rows": 4, "completeness_false_cases": {"bad_sha256": ["part 00000000-0000-4000-8000-0000000000a1 sha256 is not 64 hex characters: 'abc'"], "duplicate_part_id": ["part 00000000-0000-4000-8000-0000000000a1 supplied more than once", "counts differ: n_before=4, n_after=4, records_completed=4, rows_parsed=6", "supplied part ids ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2'] do not equal the run's files inventory ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2']"], "error_text": ["error field present: 'boom'"], "failed_billing": ["status 'FailedBilling' is not Completed", "status FailedBilling (pricing signal)", "pricing signal ['billing'] in run record text: 'FailedBilling'"], "limit_cap": ["n_before 10000 is not below the LIMIT cap 10000"], "missing_file_id": ["file 00000000-0000-4000-8000-000000000999 not downloaded and hashed", "supplied part ids ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2'] do not equal the run's files inventory ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2', '00000000-0000-4000-8000-000000000999']"], "n_after_mismatch": ["counts differ: n_before=4, n_after=5, records_completed=4, rows_parsed=4"], "n_after_none": ["n_after not observed"], "out_of_order_files": ["supplied part ids ['00000000-0000-4000-8000-0000000000a2', '00000000-0000-4000-8000-0000000000a1'] do not equal the run's files inventory ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2']"], "part_from_another_run": ["counts differ: n_before=4, n_after=4, records_completed=4, rows_parsed=6", "part 00000000-0000-4000-8000-000000000998 is not in this run's files inventory", "supplied part ids ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2', '00000000-0000-4000-8000-000000000998'] do not equal the run's files inventory ['00000000-0000-4000-8000-0000000000a1', '00000000-0000-4000-8000-0000000000a2']"], "pricing_plural": ["pricing signal ['plans'] in run record text: 'see Plans'"], "pricing_text": ["pricing signal ['plan'] in run record text: 'Upgrade your plan'"]}, "completeness_passing_cases": ["error_empty", "error_null", "explanation_text"], "completeness_true_case": true, "d4_parity_with_retained_readout": "passed", "d4_part_sha256": "67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5", "download_or_hogql_live_execution": "not performed", "end_to_end_readout_equal": true, "export_complete_observed": {"from_direct": false, "from_parts": false}, "key_order_matched_rows": 1, "rejections": {"bom": "part 0: byte-order mark present", "duplicate_key": "part 0 line 1: duplicate key 'uuid'", "key_set_mismatch": "part 1 line 1: key set mismatch (missing=['uuid'], extra=['id'])", "non_object_line": "part 1 line 1: not a JSON object", "second_trailing_empty_line": "part 0 line 3: invalid JSON (Expecting value: line 1 column 1 (char 0))"}, "string_timestamp_s_consumer_reasons": ["malformed_event_identity"], "zero_rows": {"with_explicit_keyword_argument": true, "with_run_record_key_only": false, "without_source_availability_record": ["zero rows without a source-availability record"]}}
```

- `python3 fixture_check.py --v1-only` → exit 0; stdout byte-identical to revision 1 and to the released file's run: sha256 `cf6ebba0cebf8288ee288ab0378c4262104b6ebfface304e74d8297b1c129c47`, 741 B.
- `python3 -m py_compile` (on the mirror copies, `cmp`-identical to the repository files) → ok. `ruff check --isolated --no-cache` and `ruff check --no-cache --config backend/ruff.toml` on the repository files → `All checks passed!` (exit 0, both).
- **D4 re-run** with the revised module against the committed part and committed `d4-run-record.json` (`--n-before 3`, no `--n-after`), then `readout_v1.py` with the September 30 parameters and query, into the mirror: all three outputs **byte-identical** to the committed `d4-dry-run/` files — `d4-events.json` `e37fed76…` 1,839 B; `d4-completeness.json` `b2f7c871…` 425 B (`failing_rules: ["n_after not observed"]`, `file_export_complete_observed: false`); `d4-readout.json` `1c64010f…` 2,430 B. **Nothing regenerated.** A second invocation against the existing outputs printed `refusing to overwrite d4-events.json` and exited 1 with no traceback.

**Revised file hashes:** `tasks/readiness-2026-09-21/beta/file_export_to_v1.py` sha256 `95287af3df81fec54bc22224120b7a0047ab20c6cfc107b27460f217ff50369e`, 11,248 B; `tasks/readiness-2026-09-21/beta/fixture_check.py` sha256 `3559e4283c8c07fcbd1390819ddfc9a206b5b99ae6308d4142eb8a3d4436e58a`, 44,510 B (`git diff --stat HEAD`: 115 insertions, 26 deletions across the two files).

**Deviations, revision 2:** (i) A `--source-availability-recorded` CLI flag was added — the only way the CLI can pass the now-explicit keyword argument; without it no zero-row export could ever be recorded complete from the command line. (ii) The literal `supplied != declared` rule also fires in the missing/extra/duplicate cases, so those `failing_rules` lists carry one explanatory extra line; the specific rules are kept so the operator sees the cause. (iii) The first attempt to rewrite the repository module through a shell heredoc was denied by the session's permission classifier; the files were then written with the session's dedicated file-editing tools (same content, inspectable diff). (iv) `git status` shows other modified files in the working tree (`export_operator.py`, `runtime/CHECKPOINT.md`, `control/DECISIONS-09.md`, `control/APPOINTMENTS.json`, `control/LEDGER-ACCESS.md`, untracked `control/source-context-exclusion-157.json`) that belong to other writers; none was opened, read or touched here. (v) `py_compile` was run on the mirror copies, not in the repository directory, so no `__pycache__` was created there; the mirror's bytecode was removed. The scratchpad `staging/` copies from revision 1 were left as the revision-1 record. Nothing here changes the closing statement above: cohort reporting, beta admission and capacity remain not complete and not admitted.
