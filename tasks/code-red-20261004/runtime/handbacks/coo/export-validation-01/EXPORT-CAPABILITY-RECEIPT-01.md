# Export-capability receipt 01 — HogQL file-download batch export, synthetic three-row literal test (COO worker → chief, dispatch COO-EXPORT-VALIDATION-05)

Recorded 2026-10-05 ~19:30Z by worker `coo-export-capability-test-01` (dispatched by the chief, session_01GWYV7WXWstgVGQG43YcSM8,
manifest `tasks/code-red-20261004/runtime/dispatch/COO-EXPORT-VALIDATION-05.json`, SHA-256 `f7f0abfad0accb8d10c6dfd9881c7e2015089b51c05897adb3f51cc45fa201cf`,
9,414 bytes). Authority: founder instruction 2026-10-05 ~19:12Z after PostHog support (ticket 76581, resolved) enabled the HogQL
file-download batch-export flag for the organisation. This is a dated capability receipt for the COO's G1–G3 route work. It
exports three invented literal rows and nothing else; it admits no cohort result, no participant, no beta entry. Companion
record with every request and response as returned: [`export-capability-run.json`](export-capability-run.json).

## Identity

| Item | Value |
|---|---|
| Repository | branch `claude/vigilant-goodall-633yx3` at `39c74850e1286a4469d705c96d1ffa7d07d80b20`; read-only; no git mutation; only this directory written |
| Worker / served model | `coo-export-capability-test-01`; the served model is **not observable** by the worker — the environment states `claude-fable-5-1`, and that string was passed as `llm_model` on every connector call |
| Connector | PostHog MCP (`mcp__PostHog__exec`), conversation `01a10d86-9b05-7402-93ab-5ac0211878dc`; no credential read, extracted or sought |
| Project | **117863** (EarningsNerd) — named by the manifest authority and confirmed by the 2026-09-30 receipt and decision record 07; **not re-confirmed in-session** (`project-get` is outside this dispatch's allowed tools) |
| Tools used | `learn` ×2 (required `learn -s`, optional skill load), `info` ×4, `file-download-batch-exports-count-rows-create` ×1, `-create` ×1, `-retrieve` ×1, `-cancel-create` ×0. No `execute-sql`, `project-get`, `query-*`, events/persons/sessions model or any other tool |
| Data touched | three invented literal rows generated inside the query (`UNION ALL` of constants); **no events, persons, sessions or customer table**; no customer or participant data |
| Cost | 0 DeepSeek calls; USD 0.000000; no reservation; no PostHog pricing signal in any response (see Deviations/Risks) |

## Inputs verified (10/10, before any connector call)

| # | Input | Path | SHA-256 | Bytes | Result |
|---|---|---|---|---|---|
| 1 | Exact literal-only HogQL (21 columns, 3 rows, `LIMIT 10`) | `tasks/review-evidence/beta-readout-2026-09-30/literal-projection.hogql` | `87c47aa644ef127eb8189db6e56cf0755d3158be59dcdadb74cecb33c253b3e4` | 2,923 | ok |
| 2 | September 30 export capability receipt (HTTP 403, no run) | `tasks/review-evidence/beta-readout-2026-09-30/export-capability.json` | `b1bb12abac4c865aac33670a83a4116378778025b11e2f1ebb87caa469f93387` | 1,166 | ok |
| 3 | September 30 literal projection + consumer receipt | `tasks/review-evidence/beta-readout-2026-09-30/receipt.json` | `5a5da5115de54f53c4ddaa454a88f493a76944598bffc46c581723631c996f21` | 2,223 | ok |
| 4 | September 30 evidence README | `tasks/review-evidence/beta-readout-2026-09-30/README.md` | `17996acc339478fa710142586285ede4345c21c53135e7d3210c3f153c7f4466` | 2,932 | ok |
| 5 | Summary v1 readout runbook | `tasks/readiness-2026-09-21/beta/summary-v1-readout.md` | `ffab744abf89efecaa574f057d217738057aeb00ac0cd3b6661f1ca9961b82be` | 14,372 | ok |
| 6 | Released consumer `readout_v1.py` (unchanged, not invoked) | `tasks/readiness-2026-09-21/beta/readout_v1.py` | `a9e089cd1d45672833c49cb222c6cdaab52fe9bafbb2a3dddb5c82ae9b82272e` | 15,092 | ok |
| 7 | Export projection `posthog-v1-export.hogql` (reference only; **not run**) | `tasks/readiness-2026-09-21/beta/posthog-v1-export.hogql` | `fa060fe65a078f90d4836d2f60361ff36def4fdf0da34f0eb24b3dbdf0bf47ef` | 2,612 | ok |
| 8 | COO first deliverable (G1–G5 definitions) | scratchpad handover copy `handover/officers/coo/references/FIRST-DELIVERABLE.md` (manifest `allowed_inputs[7]`; not a repository path) | `c82773953be1e85daa87525003d1ade26db4e8f8e9df428f97fff80d10ee3f7f` | 15,184 | ok |
| 9 | COO report-route proposal 01 | `tasks/code-red-20261004/runtime/handbacks/coo/REPORT-ROUTE-PROPOSAL-01.md` | `0916b5f27190cb7805b561d82498552697375071f14121b5a91901ce24017810` | 33,854 | ok |
| 10 | Decision record 07 | `tasks/code-red-20261004/runtime/control/DECISIONS-07.md` | `0f511f5a9f6eeb97cd59886b732cb96adc6828d16373d1fae57198b980897bf0` | 18,305 | ok |

The query file has no trailing newline, no CR and no non-ASCII byte; the `hogql_query` string sent round-trips byte-for-byte
to these 2,923 bytes (compact request JSON SHA-256: count-rows `86a3c33169e240643b84b8eae707f4f19761c70ee14a192b67285322ae4b573c`,
create `048ef4154b7e822918187f7be3d39b0c2b1ec2949c53ce9edc01b0c47580a8e9`).

## Enablement statement

**Support-confirmed enablement** (per the founder's relayed ticket-76581 message, PostHog support, resolved) — recorded as
reported, not independently observed by this worker. **Actual validation evidence:** in this run the `hogql` model was
accepted by both `count-rows-create` and `create` for the connector's active project, and the 2026-09-30 refusal
(HTTP 403, `HogQL batch exports are not enabled for this team.`) did not recur. The run below is the "one tiny
invented-literal-only export" the September 30 README and the October 2 operator checklist named as the first step
after confirmed access.

## Run facts

| Item | Value |
|---|---|
| Request shape (create) | `{"model":"hogql","file":{"format":"JSONLines","compression":null,"max_size_mb":null},"hogql_query":<exact 2,923 bytes>,"hogql_modifiers":{"convertToProjectTimezone":false}}`; no `data_interval_*` bounds (the query has no placeholders) |
| Request shape (count-rows) | same `model`, `hogql_query`, `hogql_modifiers`; no `file` (not in that tool's schema) |
| Count-rows | issued 2026-10-05T19:27:03Z → `{"count":3}` — **3 = expected 3**; export therefore started |
| Create (once) | issued 2026-10-05T19:27:31Z → `{"id":"01a10d89-1ee8-0000-3e2c-9000712c9502"}` |
| Poll 1 (retrieve) | issued 2026-10-05T19:27:46Z → `{"status":"Completed","files":["01a10d89-3a26-0000-56f3-e1f6c4004610"],"records_completed":3}` |
| Terminal status | **Completed** on poll 1 (≤ 15 s after the create clock read; the run may have finished earlier); no `error` field; no further poll; **cancel not called** |
| `records_completed` | **3** — agrees with count-rows 3 and the expected 3 |
| Files | **1** part, UUID `01a10d89-3a26-0000-56f3-e1f6c4004610` (single file, `max_size_mb: null`) |
| Download | **not attempted — no authenticated PostHog HTTP context in this environment** (no environment-variable name contains `POSTHOG`, checked by name only; connector credentials not read). No signed URL requested, received or recorded. `parts/` not created |
| Download endpoint (needs auth) | `GET https://<posthog-api-host>/api/projects/117863/file_download_batch_exports/01a10d89-1ee8-0000-3e2c-9000712c9502/download/01a10d89-3a26-0000-56f3-e1f6c4004610/` (or `…/download/` for the single file). Host: not reported by the tools or the skill; the repository's configured ingestion origin is `https://us.i.posthog.com` (US cloud; `docs/CONFIGURATION.md` line 77), whose API host by PostHog's URL pattern is `https://us.posthog.com` — operator confirms from the organisation's app URL. Auth: `Authorization: Bearer <personal API key>` for a user with access to project 117863, read scope `batch_export:read` (the scope the runbook records for the export tools); the endpoint 302-redirects to a temporary signed URL that must never be stored or forwarded |
| Timestamps | `date -u` clock reads issued in the same tool batch as each call (the calls run concurrently), not server times; the connector responses carry none |
| Expected content (for the pending verification) | 3 JSONLines rows; key set exactly the 21 aliases `uuid, event, timestamp_s, evidence_version_json, auth_state_at_event_json, account_id_at_event_json, analytics_consent_at_event_json, filing_id_json, summary_id_json, request_id_json, logical_request_id_json, client_attempt_json, transport_attempt_json, identity_evidence_json, consent_evidence_json, outcome_json, delivery_path_json, summary_service_invoked_json, duration_ms_json, reason_json, entry_point_json`; `uuid` ∈ {`00000000-0000-4000-8000-000000000010`, `…11`, `…12`}; `timestamp_s` 1790553600/1/2 (derived from the query's `toDateTime(…,'UTC')` literals); `*_json` values are `JSONExtractRaw` strings, empty where the property is absent — rendering to be recorded, not assumed |

## What this evidence closes and does not close

| Prerequisite | State after this receipt | Basis |
|---|---|---|
| Support-confirmed enablement | **CLOSED** | ticket 76581 resolved (founder-relayed) and validated: `hogql` model accepted; run Completed with 3 records |
| G2 — complete literal file receipt | **run completed, file verification pending the download access** | exact query, run id, terminal status, `records_completed` 3 (= count = expected) and the one file UUID are retained; file bytes, SHA-256 and the three-row/21-key/three-UUID content check await the authenticated download. Not credited as the complete G2 receipt until then |
| G1 — explicit access decision for the adopted route | **OPEN** | enablement is now evidenced for the file route; the dated access/route decision (FIRST-DELIVERABLE G1; REPORT-ROUTE-PROPOSAL-01 §6 options A/B/C) remains the CEO/founder's and is not made here |
| G3 — independent actual-file contract review | **OPEN** | needs the downloaded actual part; the released consumer stays unchanged; no adapter, no coerced response |
| G4 — control packet | **OPEN** | unchanged |
| G5 — cohort observation (0/2) | **OPEN** | unchanged; a synthetic export is not a readout |

## Next executable dependency

An operator-held **authenticated PostHog HTTP context** (personal API key, `batch_export:read`, project 117863) executing the
narrow Codex-worker handoff retained in `export-capability-run.json` (`handoff_codex_worker`): one GET of the single part via the
endpoint above, SHA-256 and byte length, verification of exactly three JSONLines rows with the 21 expected keys and the three
literal UUIDs, retention under `parts/` with a `VERIFICATION.json`, and **no other API call** (no second create, retrieve,
cancel, project-get or query). Then the existing independent file-input contract review (G3) runs against that actual artifact
in a separate context, reusing the released consumer where compatible. Download promptly: the tools and skill do not state how
long the exported file remains available.

## Risks

- **File availability window unknown** — not stated by the tools or the skill. If the part has expired before the download, a
  new export would need a new authorization (this dispatch permitted one create; none remains).
- **Host not confirmed in-session** — the API host must be taken from the organisation's PostHog app URL, not assumed from the
  repository's ingestion origin.
- **Project identity not re-confirmed in-session** — rests on the manifest, the 2026-09-30 receipt and record 07.
- **Rendering unverified** — `JSONExtractRaw` string values, empty-string for absent properties, `timestamp_s` integer vs
  string, row order: all to be recorded from the actual file, not assumed.
- **Timestamps are client clock reads**, not run metadata; the retrieve response carries no `created_at`/`finished_at`.
- **Operator identity** — FIRST-DELIVERABLE G2 names "one separately named export operator"; this synthetic run was produced by
  the chief-dispatched worker under founder instruction, which is permissible because no collected data was touched; the
  first customer-data export still needs the named operator and CEO dispatch.

## Deviations from the manifest procedure

- Two `learn` calls (the required `learn -s` and the optional skill load the manifest allows). `info` ×4 and the skill load were
  not individually clock-stamped (bounded between 19:24:46Z and 19:27:03Z); every `call` and the one poll were.
- The ~20 s poll loop ran once: the run was already `Completed` at the first retrieve. No cancel.
- Download not attempted and `parts/` not created, exactly as the manifest directs when no authentication context exists.
- Nothing else: one create, no disallowed tool, no other query, no customer data, no pricing signal, no git mutation.

## Statement

A completed three-row synthetic literal export validates the export capability and nothing more. **Nothing in this receipt marks
cohort reporting or beta admission complete**, closes G1's access decision, G3, G4 or G5, authorises customer-data export, infers
participant consent, changes any subscription, or expands any spending permission. The USD 25 authorization referenced by the
manifest is for DeepSeek and was not touched; no PostHog charge was observed or authorised.
