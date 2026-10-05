# Readout contract — DRAFT 01, revision 3: the supported file-download batch-export route (COO worker `coo-query-route-contract-draft-01`)

**Status: DRAFT, revision 3, for acceptance by the founder with the CEO. Nothing in this file is adopted, authorised,
dispatched, exported, downloaded or run.** On 2026-10-05 (~20:17Z) the founder selected the **supported PostHog
file-download batch-export route** for the beta readout and asked for the existing draft to be revised for that route,
with only the still-necessary founder decisions presented (with recommended answers) and no competing route maintained
unnecessarily. Revisions 1–2 of this file wrote the contract for the MCP `execute-sql` query route under option C; that
route is now a one-paragraph fallback (§6.1). The three-row invented-literal export already **completed** (run
`01a10d89-1ee8-0000-3e2c-9000712c9502`, status Completed, `records_completed` 3, one part) and is **not repeated**; the
founder is downloading its part with their own authenticated context; the G3 independent review of that part is a
separate context, not this one. No customer or participant data was read; no connector or HTTP call was made; no
PostHog charge is authorised; the USD 25 authorisation is DeepSeek-only and untouched. **Nothing here marks cohort
reporting, beta admission or capacity complete or admitted.** G1–G5 settle only after the founder's explicit access
decision for this route and the G3 review of the actual downloaded part (§5).

## 1. Identity, inputs, observation date, authority and limits

| Item | Value |
|---|---|
| Worker role label | `coo-query-route-contract-draft-01` — the same registered context (closure 152), resumed for revision 3 |
| Dispatch | `…/scratchpad/coo-file-route-rev3/COO-FILE-ROUTE-REVISION-06.json`, SHA-256 `a73d0066cb9d84d48bb23c06c4a82f364e416024ce9f0c4004934b24e09efa5d`, 7,123 bytes (hash verified before reading; the dispatch message said 7,112 bytes — hash is the controlling check, discrepancy recorded in §7); recorded 2026-10-05T20:20:57.243659+00:00 by the chief (session `01GWYV7WXWstgVGQG43YcSM8`); requested model inherited `claude-fable-5-1`; one writer for the output paths |
| Runtime limitation | This worker **cannot observe its own served model or session id**; the chief resolves the label. |
| Observation date | Manifest and all nine inputs verified 2026-10-05T20:21Z; written 2026-10-05T20:22Z–20:31Z (UTC), including the chief's host addendum (same manifest, no new inputs). |
| Repository state | Branch `claude/vigilant-goodall-633yx3` at `ad915c44` (main `c780228a`; PR #1099 pending merge), working tree clean (passive reads only). **No write inside the repository tree**; both outputs are staged under `…/scratchpad/coo-file-route-rev3/staging/` and placed by the chief. |
| Authority | **COO drafts; the founder with the CEO accepts.** Founder instruction 2026-10-05 ~20:17Z (route selected). COO owns closure of G1–G5 (FIRST-DELIVERABLE). MASTERPLAN-REVIEW §3B still governs the substance: a reporting contract is accepted explicitly, never silently. Ticket 76581 is resolved and the HogQL file-download batch-export flag is enabled for the organisation (receipt 01) — decided facts, not re-asked. |
| Available authority of this worker | Administrative/management only; excluded from source A/B authorship, reconciliation, semantic financial review and blind judging. Read-only repository; no git write, connector, HTTP, customer query, test, cloud or production read. Zero provider calls, reservations and spend. |
| Not read, by rule | Customer or participant data, credentials, signed URLs, anything under `tasks/readiness-2026-09-21/acceptance/`, the session's upload area, any file outside the manifest's inputs except the one permitted sibling README (§1.1). |

### 1.1 Inputs verified (sha256 and byte length compared to the manifest BEFORE any input was read)

| Label | Path | SHA-256 | Bytes | Match |
|---|---|---|---|---|
| Existing draft, revision 2 (query route) — revised here | `tasks/code-red-20261004/runtime/handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md` | `448f4f12bee69a4c543cb14b22a785a9a5754af0d87acd6de834135ff180253d` | 49767 | match |
| COO report-route proposal 01 | `tasks/code-red-20261004/runtime/handbacks/coo/REPORT-ROUTE-PROPOSAL-01.md` | `0916b5f27190cb7805b561d82498552697375071f14121b5a91901ce24017810` | 33854 | match (read in full earlier in this session at the same hash) |
| Export capability receipt 01 | `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/EXPORT-CAPABILITY-RECEIPT-01.md` | `beb2fff840a74e7cfc278f257046c68904a275dcf9a6a80ea6e882ba711f4b40` | 13031 | match |
| Export capability run record | `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/export-capability-run.json` | `328dbd442a7d562ee9cf139a9b03716b6aed1065a4d211c04bcf5050b19a403e` | 31051 | match |
| Released consumer | `tasks/readiness-2026-09-21/beta/readout_v1.py` | `a9e089cd1d45672833c49cb222c6cdaab52fe9bafbb2a3dddb5c82ae9b82272e` | 15092 | match |
| Released readout runbook (G3 file-input checklist) | `tasks/readiness-2026-09-21/beta/summary-v1-readout.md` | `ffab744abf89efecaa574f057d217738057aeb00ac0cd3b6661f1ca9961b82be` | 14372 | match |
| Released v1 export HogQL | `tasks/readiness-2026-09-21/beta/posthog-v1-export.hogql` | `fa060fe65a078f90d4836d2f60361ff36def4fdf0da34f0eb24b3dbdf0bf47ef` | 2612 | match |
| Literal-only capability HogQL (21 columns, 3 rows) | `tasks/review-evidence/beta-readout-2026-09-30/literal-projection.hogql` | `87c47aa644ef127eb8189db6e56cf0755d3158be59dcdadb74cecb33c253b3e4` | 2923 | match |
| September 30 export-capability receipt (the 403) | `tasks/review-evidence/beta-readout-2026-09-30/export-capability.json` | `b1bb12abac4c865aac33670a83a4116378778025b11e2f1ebb87caa469f93387` | 1166 | match |
| Permitted sibling README (context only) | `tasks/review-evidence/beta-readout-2026-09-30/README.md` | `17996acc339478fa710142586285ede4345c21c53135e7d3210c3f153c7f4466` (as recorded by receipt 01; not in the manifest) | 2932 | read |

**9/9 matched.** The `…/scratchpad` prefix is the chief session's scratchpad directory (a session-local path, not recorded).

### 1.2 Facts this contract relies on

| # | Fact | Source |
|---|---|---|
| F1 | Ticket 76581 resolved; PostHog support enabled the HogQL file-download batch-export flag for the organisation (founder-relayed, recorded as reported); validated: the `hogql` model was accepted by `count-rows-create` and `create` on 2026-10-05 and the 2026-09-30 HTTP 403 (`HogQL batch exports are not enabled for this team.`) did not recur | receipt 01 §Enablement; export-capability.json (2026-09-30) |
| F2 | Capability run: count-rows `{"count":3}` at 19:27:03Z; create → run id `01a10d89-1ee8-0000-3e2c-9000712c9502` at 19:27:31Z; retrieve at 19:27:46Z → `{"status":"Completed","files":["01a10d89-3a26-0000-56f3-e1f6c4004610"],"records_completed":3}`; no `error` field; cancel not called; expected 3 = count 3 = records_completed 3 | run.json `calls` 7–9, `run.reconciliation` |
| F3 | Request shapes: create `{"model":"hogql","file":{"format":"JSONLines","compression":null,"max_size_mb":null},"hogql_query":<exact bytes>,"hogql_modifiers":{"convertToProjectTimezone":false}}`; count-rows the same without `file`; no `data_interval_*` bounds passed; the query round-trips byte-for-byte (2,923 bytes, SHA-256 `87c47aa6…`) | receipt 01 §Run facts; run.json `request_shapes`, `query` |
| F4 | Connector tool surface (from `info`): `file-download-batch-exports-count-rows-create` (readOnlyHint), `-create` (file format Parquet or JSONLines; compression null/zstd/gzip/brotli/lz4/snappy; `max_size_mb` number or null), `-retrieve` (by run id; readOnlyHint), `-cancel-create` (only while Starting/Running). Statuses per the skill: Starting, Running, Completed, Cancelled, Failed, FailedRetryable, FailedBilling, Terminated, TimedOut | run.json `calls` 2–6 |
| F5 | Download: `GET https://<posthog-api-host>/api/projects/117863/file_download_batch_exports/{run_id}/download/{file_uuid}/` (single-file alias `…/download/`), `Authorization: Bearer <personal API key>` with `batch_export:read`, one 302 to a temporary signed URL that is never stored or forwarded; file availability window not stated by tools or skill. **Host — founder-stated assumption (addendum 2026-10-05):** the organisation uses **PostHog EU cloud** — private API host `https://eu.posthog.com`, ingestion origin `https://eu.i.posthog.com`, personal API keys issued at the EU settings page. **Open founder confirmation (not a decision to re-ask):** the repository defaults (`backend/app/config.py` `POSTHOG_HOST` and the frontend provider) point at `https://us.i.posthog.com` unless overridden by env — receipt 01 and run.json record the US ingestion origin from `docs/CONFIGURATION.md` line 77 / `config.py` line 107 (this worker did not open those files); **the contract names the host production actually uses**, confirmed by the founder from the production environment and the organisation's app URL — never checked by a connector or HTTP call from any management context | receipt 01 §Run facts "Download endpoint"; run.json `download`, `handoff_codex_worker`; chief's addendum relaying the founder, 2026-10-05 |
| F6 | The download of the capability part was **not** attempted by the worker (no authenticated HTTP context); the founder is now downloading it; expected content: 3 JSONLines rows, the 21 aliases, the three literal UUIDs, `timestamp_s` 1790553600/1/2; rendering to be recorded, not assumed | receipt 01 §Run facts, §Next executable dependency |
| F7 | Released v1 query shape: the 21-column projection (`toString(uuid)`, `event`, `toUnixTimestamp(timestamp)`, 18 `JSONExtractRaw(properties, …)` columns) `FROM events WHERE event IN ('summary_viewed','summary_request_started','summary_request_finished') AND toString(properties.account_id_at_event) IN (<roster>) AND timestamp >= toDateTime('<start>','UTC') AND timestamp < toDateTime('<end>','UTC') ORDER BY timestamp, uuid LIMIT 10000`; LIMIT is a safety cap, not pagination; never widen to all customers; never `SELECT *` | posthog-v1-export.hogql |
| F8 | Released consumer `readout_v1.build_readout(response, parameters)`: requires `response["columns"] == COLUMNS` (the 21 names), `response["results"]` a list of at most 10,000 lists of 21 values (uuid, event, `timestamp_s` as `int`, then 18 raw-JSON strings, `""` → None), no `error`/`exception`; `export_complete_observed` is true only if `hasMore is False`, rows < 10,000, no `warnings`, and `offset` absent or integer 0; parameters: `window_start`/`window_end` whole-second UTC ISO (`Z`), `eligible_account_ids`, `excluded_account_ids` (distinct canonical positive decimal strings); denominator = eligible − excluded; every remaining account stays in the output; inputs bounded to 16 MiB; output exclusive-create mode 0600 with the three input hashes | readout_v1.py lines 19–31, 131–248, 251–269 |
| F9 | Runbook rule: "JSONLines rows and a completed file-export run are a different evidence contract from this consumer's query-response JSON. Do not manufacture `hasMore=false` or concatenate file parts into a v1 response and call it a completed export. Review and validate an explicit input format before any customer readout; keep the current consumer and its unknowns unchanged meanwhile." G3 checklist: format, fields/types, part inventory, completion evidence, bounds, duplicate/conflict handling, provenance; independent review before any customer readout | summary-v1-readout.md §"Supported export route…", checklist item 3 |
| F10 | Runbook cadence: two actual weekly readouts; each retains source availability, exact query/parameters and consumer version, original inputs, hashes, completeness/diagnostics, denominator and unknowns; the fixed-roster combined two-week window for observed ISO-week new-filing returns, **not** a concatenation of weekly exports; a prepared worksheet, synthetic receipt or completed export is not a weekly cohort result | summary-v1-readout.md checklist items 4–5 |
| F11 | Privacy: the repository is public; rows, parts, roster membership, executed queries with roster literals, keys and signed URLs live in private stores; the repository keeps sanitized receipts and SHA-256 hashes (record 02 D5, carried from revision 2). The last attempt to copy readout files to a private artifact store was classifier-denied (revision 2 F9) | revision 2 §1.2 F6, F9 |
| F12 | Operator: FIRST-DELIVERABLE G2 names "one separately named export operator"; the capability run was produced by a chief-dispatched bounded worker — a child context of the chief's session — which **did** call the connector's export tools successfully (function now evidenced for a child worker; transcript isolation from the executive session still not established); permissible because no collected data was touched; the first customer-data export still needs the named operator | receipt 01 §Identity, §Risks "Operator identity"; revision 2 §3 |

## 2. The readout contract for the file-download route — executable shape for G1–G5

### 2.0 Conventions and the export lifecycle (apply to every export run)

- **Placeholders.** `{{…}}` is bound to a literal in the retained receipt **before** the query is sent; the text sent
  contains no braces and no HogQL `{variable}`; the retained text is the exact bytes passed as `hogql_query` to both
  `count-rows-create` and `create` (F3 proves byte round-trip). `{{window_start}}`/`{{window_end}}` are
  `YYYY-MM-DD HH:MM:SS` UTC inside `toDateTime('…', 'UTC')` (F7); the window is half-open (`>=` start, `<` end) and
  `{{window_end}}` precedes the first call. `hogql_modifiers.convertToProjectTimezone` is `false`; **no
  `data_interval_start`/`data_interval_end` is passed** — the window lives in the query text, as validated (F3).
  `{{roster_account_id_literals}}` is the comma-separated list of single-quoted canonical positive decimal account-id
  strings of the **eligible roster after exclusions**, sorted ascending so the query text is deterministic (G4, §2.4).
  **No literal customer identifier appears in this file**; any bound query text is private, its SHA-256 public (F11).
- **The one query shape.** Every customer export uses the released v1 projection (F7) with exactly two substitutions:

```
SELECT toString(uuid) AS uuid, event, toUnixTimestamp(timestamp) AS timestamp_s,
       JSONExtractRaw(properties, 'evidence_version') AS evidence_version_json,
       JSONExtractRaw(properties, 'auth_state_at_event') AS auth_state_at_event_json,
       JSONExtractRaw(properties, 'account_id_at_event') AS account_id_at_event_json,
       JSONExtractRaw(properties, 'analytics_consent_at_event') AS analytics_consent_at_event_json,
       JSONExtractRaw(properties, 'filing_id') AS filing_id_json,
       JSONExtractRaw(properties, 'summary_id') AS summary_id_json,
       JSONExtractRaw(properties, 'request_id') AS request_id_json,
       JSONExtractRaw(properties, 'logical_request_id') AS logical_request_id_json,
       JSONExtractRaw(properties, 'client_attempt') AS client_attempt_json,
       JSONExtractRaw(properties, 'transport_attempt') AS transport_attempt_json,
       JSONExtractRaw(properties, 'identity_evidence') AS identity_evidence_json,
       JSONExtractRaw(properties, 'consent_evidence') AS consent_evidence_json,
       JSONExtractRaw(properties, 'outcome') AS outcome_json,
       JSONExtractRaw(properties, 'delivery_path') AS delivery_path_json,
       JSONExtractRaw(properties, 'summary_service_invoked') AS summary_service_invoked_json,
       JSONExtractRaw(properties, 'duration_ms') AS duration_ms_json,
       JSONExtractRaw(properties, 'reason') AS reason_json,
       JSONExtractRaw(properties, 'entry_point') AS entry_point_json
FROM events
WHERE event IN ('summary_viewed', 'summary_request_started', 'summary_request_finished')
  AND toString(properties.account_id_at_event) IN ({{roster_account_id_literals}})
  AND timestamp >= toDateTime('{{window_start}}', 'UTC')
  AND timestamp <  toDateTime('{{window_end}}', 'UTC')
ORDER BY timestamp, uuid
LIMIT 10000
```

  The event vocabulary, columns and consumer semantics are the released ones (F7, F8); nothing is invented or
  re-bound. The projection is never replaced by `SELECT *`/`properties`; the predicate is never widened; the LIMIT is a
  cap, not pagination (F7). This template is **not executed by this file**.
- **Lifecycle of one export run (steps in order; every response retained as returned).**
  1. *Identity.* Project identity for the run recorded (expected 117863); if `project-get` is used, its two public
     client tokens are redacted and never recorded (revision 2 F5).
  2. *Count before.* `count-rows-create` with the bound query → `n_before`. Rule: `n_before < 10000` (the LIMIT cap);
     otherwise the window is `incomplete (cap)` and is narrowed under a new receipt — never truncated.
  3. *Create (once).* `create` with the identical `hogql_query` bytes, `file {format: JSONLines, compression: null,
     max_size_mb: null}`, modifiers as above → `run_id`. One create per window per receipt; a second create needs a new
     authorisation.
  4. *Poll.* `retrieve` at a bounded interval until a terminal status. `Completed` → continue, recording
     `records_completed` and the ordered `files[]` inventory. Any other terminal status (Cancelled, Failed,
     FailedRetryable, FailedBilling, Terminated, TimedOut) or an `error` field → `source-unavailable`; stop.
     **`FailedBilling`, or any response text naming payment, plan, billing, trial or quota, is a stop signal to report
     verbatim: no PostHog charge is authorised.**
  5. *Count after.* `count-rows-create` again with the identical query → `n_after` (the bracket; revision 2's
     `n_before = n_after` rule, carried).
  6. *Download.* For each `file_uuid` in `files[]`, in order: one authenticated GET (F5) by the **operator identity**
     (§3) against the API host production actually uses — assumed `https://eu.posthog.com` on the founder's EU-cloud
     statement, confirmed before the first download (K4) — following the single 302; the signed URL is never logged,
     stored or forwarded; the body is saved as raw bytes; SHA-256 and byte length recorded per part. Download promptly
     (availability window unknown, F5).
  7. *Parse and verify.* Each part is JSONLines: one JSON object per non-empty line; BOM, CR bytes, duplicate lines and
     key-set deviations are recorded; `rows_parsed` = Σ objects over all parts; every object's key set equals the 21
     aliases (order recorded; set equality required).
  8. *Completeness verdict.* `complete` iff **all** hold: terminal status `Completed`; no `error`;
     `n_before = n_after = records_completed = rows_parsed`; `n_before < 10000`; every id in `files[]` downloaded and
     hashed; no pricing signal; a zero-row export is `complete (zero rows)` only with the source-availability record.
     Otherwise `incomplete` with the failing rule; connector/HTTP failure → `source-unavailable` (an unknown, not zero).
     **Never** manufacture `hasMore=false`, concatenate parts across runs or windows, re-run partially, or present a
     partial window as a full one (F9).
  9. *Consume.* The parts feed the released consumer only through the input contract decided after G3 (§2.3, decision
     D5 in `FOUNDER-DECISIONS-FILE-ROUTE.md`); until then no readout is produced from them.
- **Retention.** *Private store* (decision D3): the bound query text (it carries roster literals), the parameters file,
  every part's bytes, every connector response as returned, `VERIFICATION.json`, the consumer output, the operator
  context id. *Repository:* SHA-256 of the query text and of each part, `run_id`, `files[]` ids, status, `n_before`,
  `n_after`, `records_completed`, `rows_parsed`, verdict, window, `N`, exclusion count, role labels, UTC timestamps —
  hashes and counts only; never a row, a roster literal, a key or a signed URL. **Retention exception, stated once:**
  parts of invented-literal exports (the capability run, whose `FROM` is a literal subquery) are the only part bytes
  that may enter the repository; every part of a run whose query names `events` is private, hash only.
- **Denominators.** `N` = size of the eligible roster after exclusions from the frozen G4 packet, by reference and hash;
  the consumer keeps every remaining account in its output (`eligible_denominator`, `unobserved_view_accounts_unknown`,
  F8); exclusions by count and hash; an unobserved account is unknown, never zero, never success; `N` is never reduced.
- **Operator.** No step 2–9 runs on a query naming `events` before the founder's access decision (§5.2) is recorded, the
  operator identity (§3, D1) is registered in the exclusion closure, the private store exists (D3) and the entry gates
  hold (§5). The capability run (literal subquery, done) is the only run that has occurred.

### 2.1 G1 — supported export access

| Field | Content |
|---|---|
| Purpose | Dated enablement evidence for the selected route and the **explicit access decision** G1's exit requires (FIRST-DELIVERABLE G1; receipt 01 "G1 — OPEN"). |
| HogQL | None against collected data. The capability query is `literal-projection.hogql` (F3; invented rows; done, not repeated). |
| Evidence retained | Ticket 76581 resolved; flag enabled (F1); run `01a10d89-1ee8-0000-3e2c-9000712c9502` Completed with `records_completed` 3 = count 3 (F2); request shapes (F3); the 2026-09-30 403 preserved as the before-state. |
| Completeness / denominators | Not applicable (no roster, no customer data). |
| Retention | Receipt 01 and run.json are public (no customer data, no credential); the part, once downloaded, is public under the retention exception. |
| G3 checklist items that apply | Provenance (project identity; route named; no token, key or signed URL recorded). |
| State | Enablement **evidenced**; **decision absent** — OPEN until the founder records §5.2 (recommended text: `FOUNDER-DECISIONS-FILE-ROUTE.md` D2). |

### 2.2 G2 — complete literal file receipt

| Field | Content |
|---|---|
| Purpose | One tiny invented-literal export with exact query, actual run id/status, reported completed row count, all parts and hashes; part inventory, count and completion must agree (FIRST-DELIVERABLE G2). |
| HogQL | `literal-projection.hogql`, 2,923 bytes, SHA-256 `87c47aa6…` (done). |
| Run evidence (done) | count-rows 3 → create → run id → Completed, `records_completed` 3, `files` = [`01a10d89-3a26-0000-56f3-e1f6c4004610`] (F2). Poll ran once (already Completed). No `n_after` count was taken in that run — recorded as a limitation of the capability receipt, not a failure; the lifecycle rule (step 5) applies from the first customer export. |
| Pending (in flight, founder's authenticated context) | The part's bytes, SHA-256 and length; `rows_parsed` = 3; key set = the 21 aliases; the three literal UUIDs; `timestamp_s` 1790553600/1/2 with rendering recorded (integer vs string); `*_json` renderings recorded (`"1"`, `"\"authenticated\""`, `"true"`, `""` for absent); row order by timestamp, uuid; `VERIFICATION.json` beside the part (receipt 01 handoff steps 1–4). |
| Completeness verdict for G2 | `complete` iff `count 3 = records_completed 3 = rows_parsed 3`, one part present and hashed, status Completed, no pricing signal. Any mismatch → `incomplete`, recorded; a 401/403/404/410 on download → `source-unavailable` for the part (a new export would need new authorisation; none is given here). |
| Retention | Under the retention exception: the part (invented rows) and `VERIFICATION.json` may be public; hashes recorded in the repository. |
| G3 checklist items that apply | Format; fields/types; part inventory; completion evidence; bounds; duplicate/conflict; provenance — all exercised on this part first. |
| State | **Run completed; file verification pending the download.** Not credited as the complete G2 receipt until `VERIFICATION.json` exists and G3 has reviewed it. |

### 2.3 G3 — independent review of the actual file-input contract, and the consumer gap

| Field | Content |
|---|---|
| Purpose | A named independent read-only reviewer — **a separate context, not this one** — records `accept` / `reject` / `incomplete` on the actual downloaded part(s) and the run record, re-deriving every count and hash from bytes (runbook checklist item 3). |
| HogQL | None. The reviewer runs no query and no download. |
| Review checklist (F9) | **Format** — JSONLines, one object per line, no BOM/CR, trailing-newline behaviour recorded. **Fields/types** — key set = the 21 aliases; `uuid` string; `event` string; `timestamp_s` JSON integer (the consumer requires `int`); 18 `*_json` values are raw-JSON strings with `""` for absent (the consumer `json.loads` non-empty strings) — any string-typed `timestamp_s` or non-string `*_json` is a projection/rendering finding, **not** something an adapter may coerce. **Part inventory** — every id in `files[]` present, hashed, sizes recorded. **Completion evidence** — status Completed, `records_completed`, `n_before`, `n_after`, `rows_parsed` re-derived and equal. **Bounds** — `rows_parsed < 10000`; part bytes within the consumer's 16 MiB input bound or the gap recorded. **Duplicate/conflict** — duplicate lines, duplicate `uuid`s, conflicting rows recorded, not resolved. **Provenance** — project, run id, file ids, operator label registered before the run, UTC timestamps, no key/URL/token in any receipt. |
| **The consumer contract gap, stated exactly** | The released consumer expects a **query-response JSON object**: `{"columns": [<21 names>], "results": [[<21 values>], …], "hasMore": false, …}` (F8). A file-download run yields **JSONLines parts**: one JSON object per row keyed by the 21 aliases, with no `columns`, `results`, `hasMore`, `warnings` or `offset`. Feeding parts to `readout_v1.py` today is impossible without a transformation; and `export_complete_observed` would be `false` by construction because it tests query-route fields. **Exactly one of two changes is needed, after G3 reviews the actual part (decision D5):** |
| Option A — adapter (released consumer byte-unchanged) | A new, separately reviewed module (suggested home `tasks/readiness-2026-09-21/beta/file_export_to_v1.py`) with two pure functions and no network: (1) `v1_response_from_parts(parts: list[bytes]) -> dict` — rejects a BOM; splits each part on `\n`; ignores only a single trailing empty line; `json.loads` each line into an object; requires the object's key **set** to equal `COLUMNS` (records whether the key order matched); emits `{"columns": COLUMNS, "results": [[obj[c] for c in COLUMNS] for each object, parts in `files[]` order, lines in file order]}`; **sets no `hasMore`, `offset` or `warnings`**; performs **no type coercion** (a string `timestamp_s` stays a string and is diagnosed by the consumer as `malformed_event_identity`; the remedy is a reviewed projection change, not adapter coercion). (2) `file_export_completeness(run_record, parts: list[{id, sha256, bytes, rows}], n_before, n_after) -> dict` — emits `{status, error, records_completed, n_before, n_after, rows_parsed, files, file_export_complete_observed}` where `file_export_complete_observed` is true iff the §2.0 step-8 rule holds. The consumer's own `export_complete_observed` stays `false` and its `limits` list unchanged; the readout receipt carries `file_export_complete_observed` from the adapter record and states that the consumer field is query-route-only. `fixture_check.py` gains fixtures for the adapter only. |
| Option B — consumer change (alternative) | `readout_v1.build_readout` accepts an optional `response["file_export"]` object `{status, error, records_completed, count_rows_before, count_rows_after, rows_parsed, files: [{id, sha256, bytes}]}` and, when present, computes `export_complete_observed` from the §2.0 step-8 rule instead of the `hasMore`/`offset`/`warnings` test; `readout_version` is bumped; `fixture_check.py --v1-only` gains the file-route cases. This changes the released consumer, its fixtures and their recorded hashes. |
| Rule | Neither is implemented here or before G3's `accept` on the actual part; the released consumer stays unchanged meanwhile (F9; FIRST-DELIVERABLE G3: the CTO supplies a minimal implementation writer only if the reviewed real contract demonstrates the need). No `hasMore=false` is manufactured; no parts are concatenated into a "completed" response. |
| Retention | Review record public (verdict, failing items, hashes compared); reviewer context id private, label registered before it reads any part. |
| State | **OPEN** — needs the downloaded part, the named reviewer, then D5. |

### 2.4 G4 — private cohort, offered-scope and support control packet (what this route needs from it)

| Field | Content |
|---|---|
| Purpose | The route needs, by hash, before any customer export: the frozen eligible account-id roster, the explicit founder/staff/test exclusions, and the parameters file (F8). Everything else in G4 (consent, offered scope, legal, support owner/backup/address, calendar, entry/start authority) is unchanged and outside this contract. |
| Binding | `{{roster_account_id_literals}}` := the eligible roster **after** exclusions, canonical positive decimal strings, sorted ascending, single-quoted, comma-separated — so excluded accounts' events are not exported at all; the consumer's parameters file carries both `eligible_account_ids` and `excluded_account_ids` so its denominator is eligible − excluded and every remaining account stays in the output. The bound predicate text is private; its SHA-256 and the packet hash are public. |
| HogQL | None run by G4; it only produces the binding. |
| Denominators | `N` = eligible − excluded, from the packet; constant across the two weekly windows and the combined window (same frozen roster). |
| Completeness | Not applicable; the IN-list length bound is checked once on the capability part's successor run — if the route rejects a long literal list, that is a finding for a projection decision, not a reason to widen the predicate. |
| Retention | Packet private (no names in any shared bundle); repository holds the packet hash, `N`, exclusion count, predicate hash. |
| G3 checklist items that apply | Provenance (roster hash in the receipt equals the packet hash); bounds (`N` unchanged across the three runs). |
| State | **INCOMPLETE**; owners unchanged (founder consent/recruitment and offered scope; CPO; CTO; CFO; CEO integrates). No invitation, data collection, inferred consent, start date, flag, registration or pricing change. |

### 2.5 G5 — actual cohort observation: two weekly readouts and the combined-window receipt

| Field | Content |
|---|---|
| Purpose | Two dated actual weekly readouts and one fixed-roster combined-window receipt (F10), each from **one** export run under §2.0 and consumed under the D5 contract. A synthetic export is not a readout; **0/2 today**. |
| Runs | **R-W1**: template with `{{window_start}}`/`{{window_end}}` = week-1 window. **R-W2**: week-2 window. **R-C**: combined window `[W1_start, W2_end)` — a separate export over the union window with the same roster, from which the consumer derives `observed_later_week_new_filing_return` natively (F8); never a concatenation of R-W1 and R-W2 parts (F10). Three runs, three receipts, three private parts sets. |
| Cadence rule | Windows are UTC half-open with whole-second boundaries (F8); recommended alignment to ISO weeks (Monday 00:00:00Z) because the consumer's return logic is ISO-week based — a recommendation, not a date. Each run starts only after its `{{window_end}}` plus a settle delay the COO with the CEO record when the first window is authorised (no number here). Start date, windows and roster observation time come from the separately authorised G4/R4 gates; none is set here. |
| What the route carries | Observed view/request outcomes, pairing, outcomes, durations, first observed view, later-week different-filing return — exactly the released consumer's outputs. **What it cannot carry** (joined by account and window from their own evidence routes, never queried here): support responses (support route), cost per successful analysis (provider telemetry and the spend ledger), reviewed participant usefulness (session review). The readout names the evidence route per field. |
| Completeness | §2.0 step 8 per run; a `source-unavailable` or `incomplete` run leaves that week unknown, not zero; no partial week is reported as a week. |
| Denominators | `N` from G4 in every run; `unobserved_view_accounts_unknown` reported as unknown. |
| Retention | §2.0; parts private; hashes, counts, run ids and verdicts public. |
| G3 checklist items that apply | All seven, per run. |
| State | **QUEUED, 0/2** — nothing here changes the count; two elapsed windows cannot be parallelised away; entry gates: R2 quality decision, R3 operating readiness (C1 HOLD stands), G1–G4, invitation/consent/start authority. |

## 3. Operator identity on this route — standing rule and the two legs

Standing rule (carried): **an executive context never runs a customer export or reads a part.** Chief/CEO, COO, CTO,
CFO, CPO sessions and every management worker — this one included — receive only counts, hashes, status and verdicts.
The operator is a separately named, non-executive context (or a named human role), registered by label in
`control/source-context-exclusion-<n>.json` **before** the first customer-data run (label public, identity private).

This route has **two legs with different exposure**: the *connector leg* (count-rows, create, retrieve) returns no event
rows but **sends the roster-bearing query text** (account ids are participant data); the *download leg* (one GET per part
with a personal API key) returns rows and requires an authenticated PostHog HTTP context that today only the founder
holds (F5, F6). New evidence since revision 2: a bounded child worker of the chief's session **did** call the connector's
export tools (F12), so function is established for the connector leg; transcript isolation from the executive session
is not. **The decision, with a recommended answer, is D1 in `FOUNDER-DECISIONS-FILE-ROUTE.md`;** it is not made here.
Whichever option is recorded, the G3 reviewer is a different, non-executive context from the operator.

## 4. Dry run — what is already done, what remains, nothing executed here

On this route the three-row literal export **is** the dry run of the export mechanics: syntax acceptance, count-rows,
create, poll to Completed, `records_completed`, part inventory (F2). Its download and `VERIFICATION.json` are in flight
in the founder's authenticated context (F6). What no literal run has exercised: the window literals and the
`events`-table predicate (only exercisable on the first authorised customer run), multi-part output (`max_size_mb` null
produced one part; behaviour at larger sizes is unknown), the `n_after` bracket, and the consumer path from JSONLines
to `readout_v1.py`. The one remaining **no-cost, no-connector** dry run is offline: once D5 is decided and authored, run
the adapter (or changed consumer) on the downloaded three-row part with the September 30 synthetic parameters and
compare with the retained September 30 consumer output (one view, one paired complete request, 1,000 ms) — same rows,
different input contract. Whether that is wanted before the first real readout is **D4**. **Execution: none by this
worker; none authorised by this file.**

## 5. What this revision settles and does not settle — exactly as before: nothing settles until the founder's access decision and the G3 review of the actual part

### 5.1 Per group

| Group | State | Settled by this draft once accepted | Still required |
|---|---|---|---|
| G1 | **OPEN** (enablement evidenced; decision absent) | The route, its lifecycle and the contents of the access decision (§5.2) | **The founder's explicit, dated access decision** (recommended text: D2); operator identity (D1); private store (D3) |
| G2 | **Run completed; file verification pending** | The receipt fields and the completeness rule for the capability part (§2.2) | The downloaded part, its hashes and `VERIFICATION.json`; G3's acceptance of it |
| G3 | **OPEN** | The review checklist and the exact statement of the consumer gap with the two admissible changes (§2.3) | The named independent reviewer; the actual part; the D5 decision; then (only if accepted) a CTO-named minimal writer |
| G4 | **INCOMPLETE** | The binding rule for roster, exclusions and parameters (§2.4) | Everything else in G4; owners unchanged |
| G5 | **QUEUED, 0/2** | The three-run cadence and what the route can and cannot carry (§2.5) | Entry gates; settle rule; two elapsed windows; actual evidence |

### 5.2 What G1's explicit access decision must say for this route

Recorded by the founder with the CEO, dated, with provenance, before any customer export: (1) the route — PostHog
HogQL **file-download batch export** (JSONLines) on project 117863 **at the API host production actually uses**
(founder-stated EU cloud, `https://eu.posthog.com`, confirmed per K4), enablement per ticket 76581 and the completed
capability run (F1, F2); (2) the authorisation relied on — the founder's existing account authorisation and the
`batch_export:read`/`batch_export:write` scopes already connected on 2026-09-30 (runbook), with **no new scope, plan
purchase or plan change and no PostHog charge** authorised; (3) the data scope — the released v1 projection over the
three named events, the frozen roster and an elapsed UTC window only, for the beta readout only (F7); (4) the operator
option (D1) and the standing rule of §3; (5) the private store and custody rule (D3); (6) that the capability part is
verified and G3-reviewed before the first customer export; (7) that the consumer input contract is fixed by D5 after
G3, with the released consumer unchanged meanwhile; (8) that the first customer export runs on this route only; (9)
that acceptance of this contract is recorded separately from the access decision, so neither is inferred from the other
(MASTERPLAN-REVIEW §3B). The recommended decision text is `FOUNDER-DECISIONS-FILE-ROUTE.md` D2.

## 6. Risks with owners

| # | Risk | Why it matters | Owner | Permitted next step (none dispatched here) |
|---|---|---|---|---|
| K1 | Two-leg operator exposure (§3): roster literals in the connector leg; rows and a personal API key in the download leg | A wrong operator choice puts participant data or a credential in an executive or shared context | **Founder with the CEO** (D1) | Record D1 in the G1 decision; register the label before any customer run |
| K2 | Private store for parts, bound queries, parameters, outputs (F11) | The first customer part would have nowhere compliant to land | **Founder** (D3) with the CEO | Decide D3; exercise the custody path on the capability part first |
| K3 | File availability window unknown (F5) | A part may expire before download; a second create needs new authorisation | Operator; **CEO** (authorisation rule) | Download promptly after `Completed`; one create per window per receipt |
| K4 | API host: the founder states EU cloud (`https://eu.posthog.com` / `https://eu.i.posthog.com`), while the repository defaults recorded by receipt 01 point at the US ingestion origin unless overridden by env (F5); project identity not re-confirmed in-session | A host other than the one production actually uses yields a 404 on the download leg or an export from the wrong place; an ingestion-origin/region mismatch would mean events are not where the export reads — a possibility to confirm, not a finding asserted here | **Founder** (open confirmation, not a decision: the host production actually uses, from the production env and the app URL); operator records | Confirm the host once and name it in the G1 decision text (§5.2); record project identity per run (tokens redacted); no connector or HTTP check by any management context |
| K5 | Rendering unverified (`timestamp_s` type; `*_json` strings; key order; row order) | The consumer rejects or mis-diagnoses rows; an adapter must not coerce | **G3 reviewer**; projection owner if a change is needed | Review the actual part; any fix is a reviewed projection change |
| K6 | Consumer input-contract gap (§2.3) | No readout can be produced from parts until D5 is decided and authored | **Founder** (D5) with the CEO; CTO names the minimal writer only after G3 `accept` | Decide D5 after G3; no implementation before |
| K7 | LIMIT 10,000 cap or multi-part output | `n_before = 10000` means a capped, incomplete window; multi-part behaviour untested | **COO** (contract) | Narrow the window under a new receipt; download and hash every part |
| K8 | Pricing signal (`FailedBilling`, payment/plan text) | No PostHog charge is authorised | Operator stops and reports verbatim; **CEO/founder** decide | Stop rule in §2.0 step 4 |
| K9 | Late-arriving events between `n_before` and `n_after` | Honest `incomplete`; may force a re-run after the settle delay | **COO with the CEO** (settle rule) | Record the settle rule when the first window is authorised; no number here |
| K10 | Fields the route cannot carry presented as covered | Over-claiming the readout | **COO** | §2.5: evidence route named per field |
| K11 | Key, signed URL or roster literal reaching a receipt or the repository | Credential or participant exposure in a public repository | Operator; G3 reviewer (provenance) | Redaction rule in §2.0; hashes only in the repository |

### 6.1 Fallback — the MCP `execute-sql` query route (one paragraph, not maintained further)

If the file-download route becomes unavailable — the flag withdrawn, a `FailedBilling`/pricing signal, parts not
retrievable, or runs not completing within a readout's settle window — the query route written in revisions 1–2 of this
file (SHA-256 `448f4f12bee69a4c543cb14b22a785a9a5754af0d87acd6de834135ff180253d`, 49,767 bytes) is the fallback. Before
it could be used the founder would have to record a separate G1 access decision for that route, settle its operator
identity and private store, confirm the connector-reported 100-row default and 500-row maximum, accept client-side-only
completeness (count bracket plus LIMIT/OFFSET pages, no server-side run record) and have Q-G3 review its pipe-delimited
format against the consumer. Its three-option decision table is withdrawn: the route decision is made.

## 7. Return contract and closing record

- **Counts unchanged:** 3/30 dossiers; 0/2 actual weekly readouts; 5 reporting groups + 1 capacity decision (C1);
  candidate HOLD; E7 90+30 not admitted; counters overlap and are not summed. **G1 OPEN (decision absent); G2 run
  completed, file verification pending; G3 OPEN; G4 INCOMPLETE; G5 QUEUED. Nothing is adopted, authorised or run by
  this file; cohort reporting, beta admission and capacity are not complete and not admitted.**
- **Status:** `pass` for the administrative deliverable — the manifest's procedure items map to §2 (contract, lifecycle,
  retention, completeness, G4, G5 cadence, consumer gap), §6.1 (query route collapsed; decision table removed),
  `FOUNDER-DECISIONS-FILE-ROUTE.md` (decisions with recommendations), §5 (settle/not-settle), this §7.
- **Files written:** exactly two, both staged outside the repository under `…/scratchpad/coo-file-route-rev3/staging/`:
  this file and `FOUNDER-DECISIONS-FILE-ROUTE.md`. Hashes and byte counts are reported in the return message; the chief
  places the files and records the hash chain. **No write inside the repository working tree.**
- **Files read:** the nine manifest inputs (§1.1), the permitted sibling README, and the manifest itself; nothing else.
- **Actual new calls / spend / changes by this worker:** connector calls **0** (no PostHog MCP, no HTTP); network **0**;
  customer or participant data **0**; production reads **0**; provider calls **0**; DeepSeek spend **USD 0.000000**;
  reservations **0**; ledger writes **0**; git mutations **0** (passive reads: `rev-parse`, `log`, `status`,
  directory listings by name); agents spawned **0**; invitations, flags, pricing, registration, load, exports,
  downloads **0**. Observed for this worker's own actions; session/platform overhead is unmeasured.
- **Deviations:** (1) the dispatch message stated the manifest at 7,112 bytes; the file is 7,123 bytes and its SHA-256
  matches exactly — hash controlling, recorded. (2) The export-capability run was produced by a child worker of the
  chief's session (F12); this file records that as evidence about connector function, not as a precedent for a
  customer-data run. (3) The chief's addendum (same manifest; no new inputs) relaying the founder's statement that the
  organisation uses PostHog EU cloud was applied as a founder-stated assumption plus an open founder confirmation (F5,
  K4, §5.2); no repository file beyond the inputs was opened to check the defaults, and no connector or HTTP check was
  made. No stop condition was met.
- **Served model:** not observable to this worker; the manifest records inherited `claude-fable-5-1`.
- **No further writes; no background work is claimed after this handback.**

### 7.1 Revision history and corrections

| Revision | SHA-256 | Bytes | Where | What changed |
|---|---|---|---|---|
| 1 | `401b82ed08f2b23147cb1582075c149bf79f4c056368990c030e35593ecff3a8` | 45,384 | committed at `39c74850` | Query-route contract under option C (eight inputs; G1–G5; operator options O1–O4; dry-run P1–P6) |
| 2 | `448f4f12bee69a4c543cb14b22a785a9a5754af0d87acd6de834135ff180253d` | 49,767 | repository head `ad915c44` (committed with record 08's review application) | Chief's read-only review of revision 1 applied: one should-fix (grouped-query row bracket = distinct group-key tuples; `n_before = n_after = Σ rows` for every shape) and five nits (retention exception; `event` column; plan-coverage wording; length-guidance source; terminal page `< L`) |
| 3 | reported in the return message | — | staged at `…/scratchpad/coo-file-route-rev3/staging/`, placed by the chief | **Rewritten for the founder-selected file-download batch-export route** (2026-10-05 ~20:17Z): one query shape (released v1 projection with roster and window placeholders), export lifecycle (count → create → poll → count → download → verify), file-route completeness rule, retention with the parts exception, G4 binding, G5 three-run cadence, the consumer gap stated exactly with the two admissible changes (not implemented), operator two-leg analysis pointing to D1, the dry run restated as done/remaining, the query route collapsed to §6.1 and the three-option table removed, risks re-owned, founder decisions moved to `FOUNDER-DECISIONS-FILE-ROUTE.md` with recommended answers; the founder's EU-cloud host statement carried as an explicit assumption with an open confirmation against the repository's US defaults (addendum, same manifest) |
