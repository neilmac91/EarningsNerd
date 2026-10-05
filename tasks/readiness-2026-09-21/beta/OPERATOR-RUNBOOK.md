# Operator runbook — founder-operated PostHog file-download export (D1 option O2) and the private store (D3)

**Status: staged by a bounded COO worker (`coo-operator-script-writer-01`, dispatch `COO-OPERATOR-SCRIPT-08`); placed
by the chief; run only by the founder.** It implements readout contract revision 3 §2.0 (lifecycle steps 1–8), §3 (the
two legs) and the founder's decisions D1 (O2: founder-operated, with a founder-side verification script) and D3
(founder-side private directory; the repository receives hashes and counts only). Nothing in this runbook authorises a
customer-data export, a new export of any kind, a PostHog charge, a production or CI change, or any statement that
cohort reporting, beta admission or capacity is complete or admitted. A customer export still needs every entry gate of
the contract (§2.0 "Operator", §5): the recorded G1 access decision (D2 text), the operator label registered in the
exclusion closure, the private store in place, and the G4 roster/exclusions/parameters by hash.

The script is `export_operator.py` (same directory as this file when staged; placed beside
`tasks/readiness-2026-09-21/beta/readout_v1.py` by the chief if it enters the repository). Standard library only,
Python 3.11+, no package install. It performs HTTP only when the founder runs it in export mode.

## 1. Standing rules the script enforces

| Rule | How |
|---|---|
| The personal API key is never an argument, never printed, never written | Read once from the environment variable `POSTHOG_PERSONAL_API_KEY` inside `run_export`; passed as a parameter to the two HTTP functions; no logging module is imported; the only stdout site is `_say()` |
| The signed URL is never logged, stored or printed | Redirects are never followed automatically (`_NoRedirect`); in `_download_part` the `Location` value is read into the local variable `target`, fetched exactly once (without the bearer header unless its host is the API host), then deleted; it is not returned and not recorded |
| No row is printed | Stdout carries counts, hashes, ids, statuses, UTC times, the verdict and (on a pricing stop) the connector-leg response text verbatim; connector-leg responses (count-rows, create, retrieve) never contain rows; download-leg failures print only `type`/`code`/`detail`/`attr` fields of a JSON error body, or a byte count |
| One create per invocation | A single `create` POST sits in the lifecycle; the only re-run is a new invocation, which the contract treats as a new authorisation |
| `n_before < 10000` | Otherwise the script stops before `create` with verdict `incomplete (cap)` (exit 4) |
| Pricing stop | `FailedBilling`, or any connector-leg response text containing payment, billing, trial, quota or the word plan(s), stops the run; status and text are printed verbatim; no PostHog charge is authorised (exit 4) |
| Private directory outside any repository | `--private-dir` is refused when any ancestor (or the directory itself) contains `.git` (exit 5); outputs are 0600 files in 0700 directories, created exclusively, never overwritten |
| Project identity | Recorded as given (`--project`, default 117863); no `project-get` call |
| Request shapes | Mirror `export-capability-run.json`: count-rows `{model: hogql, hogql_query, hogql_modifiers: {convertToProjectTimezone: false}}`; create adds `file: {format: JSONLines, compression: null, max_size_mb: null}`; the same `hogql_query` string object is serialised into both bodies; no `data_interval_*` bounds |

Hygiene proof (run by the founder or the chief; expected matches are derived from the staged source):

```
grep -n "print("          export_operator.py   # expected: no match (stdout is sys.stdout.write inside _say only)
grep -n "sys.stdout"      export_operator.py   # expected: exactly the two lines inside _say
grep -n "import logging"  export_operator.py   # expected: no match
grep -n "os.environ"      export_operator.py   # expected: one read site, os.environ.get(KEY_ENV, "") in run_export
grep -n 'get("Location")' export_operator.py   # expected: one line in _download_part (value bound to the local `target`)
grep -n "Authorization"   export_operator.py   # expected: three header-construction lines (one in _api_call, two in _download_part)
```

## 2. One-time setup by the founder

1. **Confirm the host once (contract K4, decisions "Open founder confirmation").** The script's default is the EU-cloud
   API host `https://eu.posthog.com`, matching the founder's statement and the host the capability part was actually
   downloaded from (`g3/parts/VERIFICATION.json` records `host: https://eu.posthog.com`, 302 then 200). Confirm against
   the production env (`POSTHOG_HOST` override) and the organisation's app URL before the first customer run; pass
   `--host` only if production differs.
2. **Create the personal API key at the EU settings page** (`https://eu.posthog.com/settings/user-api-keys`), scoped
   to the Default project 117863, with exactly the two scopes PostHog requires for this lifecycle: `batch_export:read`
   (retrieve, count-rows, download) and `batch_export:write` (create). These are the scopes the readout runbook records
   as already connected on 2026-09-30; no new plan, scope class or charge. Keep the key in the password manager only.
3. **Export the key into the shell for the run only, without echo and without a history line:**
   ```
   read -rs POSTHOG_PERSONAL_API_KEY && export POSTHOG_PERSONAL_API_KEY   # paste, Enter; nothing is echoed
   # ... run the script ...
   unset POSTHOG_PERSONAL_API_KEY
   ```
   Never put the key in a file, an argument, a ticket, a chat or a receipt.
4. **Create the private store (D3).** A founder-side directory outside every git work tree, under the custody
   convention already used for the private planning folders (per-file SHA-256 and byte length, a `TOTAL=` line per
   folder). Example: `~/private/earningsnerd-readouts/` with mode 0700. The CEO records its existence and custody rule
   by label, never its path; this runbook does not name the real path either.

## 3. D3 layout of the private store

```
<private-dir>/                                   # outside any repository; 0700
  <label>-bound.hogql                            # the bound query the founder prepares (roster literals; private)
  <label>-parameters.json                        # the consumer parameters file (eligible/excluded ids; private)
  <label>-<run_id>/                              # written by the script; named after the create response
    bound-query.hogql                            # byte copy of --query
    responses/01-count-rows-before-<UTC>.json    # every response exactly as returned, UTC-stamped
    responses/02-create-<UTC>.json
    responses/03-retrieve-<UTC>.json ...         # one file per poll
    responses/NN-count-rows-after-<UTC>.json
    parts/posthog-hogql-<run_id>-<file_id>.jsonl # raw bytes, one per id in files[] (rows: private)
    VERIFICATION.json                            # full operator record (steps 1-8, per-part checks, completeness)
    v1-events.json                               # only when file_export_to_v1.py sits beside the script (rows: private)
    RECEIPT-PUBLIC.json                          # hashes, counts, ids, statuses, verdict, window, N, labels, UTC only
    CUSTODY.txt                                  # "sha256  bytes  relative-path" per file + TOTAL=<files> <bytes>
```

Until `create` answers, the run directory is `<label>-pending-<UTC>`; it is renamed to `<label>-<run_id>` on the create
response. A run that stops before `create` (cap, connector failure, pricing signal on count-rows) keeps the pending
name with its `VERIFICATION.json`, `RECEIPT-PUBLIC.json` and `CUSTODY.txt`.

**What leaves the private store.** To the chief, per run: `RECEIPT-PUBLIC.json` and `CUSTODY.txt` only. Never a part of a
customer run, never `bound-query.hogql`, never `responses/`, never `v1-events.json`, never the private path. **What
enters the repository:** hashes and counts (the receipt's content: query SHA-256, part SHA-256 and byte lengths, run id,
file ids, status, `n_before`, `n_after`, `records_completed`, `rows_parsed`, verdict, window, `N`, exclusion count,
labels, UTC times). **Retention exception, stated once (contract §2.0):** parts of invented-literal exports (the
capability run, whose `FROM` is a literal subquery) are the only part bytes that may enter the repository; every part of
a run whose query names `events` is private, hash only.

## 4. Per-readout procedure (three runs per cohort cycle: W1, W2, combined)

Preconditions for any run on a query naming `events` (contract §2.0 "Operator"): G1 access decision recorded (D2
text); operator label registered in the exclusion closure; private store present; G4 roster, exclusions and parameters
frozen by hash; the window has elapsed plus the settle delay the COO/CEO record when the first window is authorised.

1. **Bind the query.** Start from the released projection `tasks/readiness-2026-09-21/beta/posthog-v1-export.hogql`
   with exactly two substitutions (contract §2.0): the eligible roster after exclusions as sorted, single-quoted,
   comma-separated canonical decimal strings in the `IN (...)` list, and the UTC half-open window in the two
   `toDateTime('YYYY-MM-DD HH:MM:SS', 'UTC')` literals. Save as `<private-dir>/<label>-bound.hogql`. The script refuses a
   text that still contains `{{`/`}}`. Record the file's SHA-256 (the receipt carries it).
2. **Run.** From a shell with the key exported (section 2.3):
   ```
   python3 export_operator.py --label W1 \
     --query "$PRIVATE/W1-bound.hogql" --private-dir "$PRIVATE" \
     --window-start 2026-MM-DDT00:00:00Z --window-end 2026-MM-DDT00:00:00Z \
     --n <N> --excluded-count <E>
   ```
   W2: `--label W2` with the week-2 bound query and window. Combined: `--label C` with the union window
   `[W1_start, W2_end)` and the same roster — a separate export, never a concatenation of the W1 and W2 parts.
   Defaults: `--host https://eu.posthog.com`, `--project 117863`, `--poll-seconds 15` (bounded 5–300),
   `--timeout-minutes 30` (bounded 1–240).
3. **Read the output.** Lines: identity (label, project, host, query hash and bytes); `columns: 21 (source: ...)`;
   `n_before=`; `run_id=`; one `poll k: status=` per retrieve; `terminal status=Completed records_completed= files=`;
   `n_after=`; one `download i/n <file_id>: sha256= bytes= first_http=302 body_http=200` per part; one `part i <file_id>:
   ...` verification line per part; `completeness rule: ...`; the count line; `verdict: ...`; then the custody block
   (`custody <dir>:`, one line per file, `TOTAL=<files> <bytes>`).
4. **Exit codes.** 0 `complete` / `complete (zero rows)`; 2 `incomplete (...)` naming the failing rule(s); 3
   `source-unavailable (...)` (non-Completed terminal status, error field, HTTP or connector failure, poll timeout,
   download failure); 4 stop (`incomplete (cap)` or a pricing signal); 5 refused before any network call (missing key,
   private dir inside a git tree, unbound placeholders, bad arguments).
5. **Hand to the chief:** `RECEIPT-PUBLIC.json` and `CUSTODY.txt` from the run directory. Unset the key.

## 5. Stop conditions and what to do

| Signal | Script behaviour | Founder action |
|---|---|---|
| `n_before >= 10000` | `incomplete (cap)`, no create, exit 4 | Narrow the window under a new receipt; never truncate |
| `FailedBilling`, or payment/plan/billing/trial/quota text in any connector-leg response | Stops at once; prints status and text verbatim; exit 4 | Report verbatim to the chief/CEO; **no charge, no plan change, no retry** |
| Terminal status other than `Completed`, or an `error` field | `source-unavailable (terminal status ...)`, exit 3 | Report; a second create needs new authorisation |
| Poll timeout | `source-unavailable (poll timeout ...)`, exit 3 | Do not cancel or re-create from the script; report |
| Download first/body HTTP not 302/200 (401, 403, 404, 410, a second redirect) | `source-unavailable (download of file i/n ...)`, exit 3; the structured error fields only are printed | Report; the file availability window is unknown (contract K3), so run promptly after `Completed` |
| `n_after` not observed | Download continues; verdict `incomplete (n_after not observed)`, exit 2 | Report; the week stays unknown, not zero |
| `n_before != n_after`, or either differs from `records_completed`/`rows_parsed` | `incomplete (n_before = n_after = records_completed = rows_parsed does not hold)` | Honest incomplete (contract K9); re-run only under the settle rule and a new authorisation |
| Key set, BOM, CR, duplicate lines, key order, row order, `timestamp_s` type | Recorded per part in `VERIFICATION.json` (`deviations`, counts); key-set deviation is a finding for G3, not something the script coerces | Hand the receipt to G3; a projection change is a reviewed change, never an adapter coercion |

A `source-unavailable` or `incomplete` run leaves that week **unknown, not zero**; no partial window is reported as a
week; parts are never concatenated across runs or windows; `hasMore=false` is never manufactured.

## 6. Offline verification of the staged capability part (steps 7–8, no network)

Purpose: exercise the custody path and the verification code on the invented-literal part at zero risk (decision D3
"trial first"). The run record is derived from `export-capability-run.json` (call 9: `Completed`, `records_completed` 3,
one file id); `n_before` 3 from call 7; `n_after` was not taken in that run (contract §2.2 records this as a limitation
of the capability receipt). The expected verdict `incomplete (n_after not observed)` is therefore a **true statement
about that run, not a defect** of the part or the script.

```
PRIVATE=<a directory outside any git work tree>      # e.g. the session scratchpad's operator/offline-verify
mkdir -p "$PRIVATE"
cat > "$PRIVATE/capability-run-record.json" <<'EOF'
{"status": "Completed", "files": ["01a10d89-3a26-0000-56f3-e1f6c4004610"], "records_completed": 3}
EOF
python3 export_operator.py --label CAP \
  --offline-verify <scratchpad>/g3/parts/posthog-hogql-01a10d89-1ee8-0000-3e2c-9000712c9502-01a10d89-3a26-0000-56f3-e1f6c4004610.jsonl \
  --run-record "$PRIVATE/capability-run-record.json" --n-before 3 \
  --private-dir "$PRIVATE"
echo "exit=$?"
```

**Expected output (derived from the staged source and the G3-verified facts of the part; NOT observed in the authoring
session — see section 8; replace this block with the observed output when the chief or founder runs it):**

```
export_operator offline-verify label=CAP run_id=01a10d89-1ee8-0000-3e2c-9000712c9502 parts=1
columns: 21 (source: embedded (readout_v1.py not present beside the script))
part 1 01a10d89-3a26-0000-56f3-e1f6c4004610: sha256=67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5 bytes=2092 rows=3 key_set_equal_rows=3 key_order_equals_projection_rows=0 bom=None cr_bytes=0 ends_with_newline=True duplicate_lines=0 duplicate_uuids=0 deviations=2
completeness rule: inline (file_export_to_v1.py not present beside the script; identical to section 2.0 step 8)
n_before=3 n_after=None records_completed=3 rows_parsed=3 status=Completed
verdict: incomplete (n_after not observed)
custody CAP-01a10d89-1ee8-0000-3e2c-9000712c9502:
<sha256>  <bytes>  RECEIPT-PUBLIC.json
<sha256>  <bytes>  VERIFICATION.json
TOTAL=2 <bytes>
exit=2
```

The two `deviations` on the part are the ones G3 review 01 recorded: key order differs from the projection on 3 of 3
rows, and rows are not ordered by `(timestamp_s, uuid)`; both are recorded, neither is a key-set or rendering failure.
The `<sha256>`/`<bytes>` of the two JSON outputs depend on the run's UTC timestamps and are not predictable. When the
script runs beside `readout_v1.py`, the columns line reads `columns: 21 (source: readout_v1.COLUMNS)`; when
`file_export_to_v1.py` (decision D5, Option A) sits beside it, the rule line names
`file_export_to_v1.file_export_completeness (agrees with inline; both recorded)` and `v1-events.json` is written — the
input for the D4 offline consumer dry run (`readout_v1.py --events v1-events.json --parameters ... --query ... --output
...`), which runs under its own authorisation, not this runbook.

## 7. What the chief records

From each run: the receipt's hashes and counts (query SHA-256, part SHA-256/bytes/rows, run id, file ids, status,
`n_before`, `n_after`, `records_completed`, `rows_parsed`, verdict, window, `N`, exclusion count, labels, UTC times) and
the `CUSTODY.txt` lines. Executive contexts (chief, officers, management workers) receive these only — never a part,
the bound query, a response body, the key or a signed URL (contract §3). The G3 reviewer is a separate non-executive
context that reads hashed artefacts and the run record.

## 8. Authoring record and deviations (worker `coo-operator-script-writer-01`)

- Written with no network, connector, PostHog or HTTP call; no package install; no repository file edited; nothing
  opened under `tasks/readiness-2026-09-21/acceptance/` or `/root/.claude/uploads/`.
- **Deviation — verification not executed in the authoring session.** The session's command-execution tool (Bash, and
  the Monitor tool) was blocked for the whole conversation by the auto-mode safety classifier, which reacts to the
  dispatch prompt's content (API key, bearer header, signed URL wording), not to any command. Consequently, in the
  authoring session: (a) the manifest and input SHA-256/byte checks could not be computed — inputs were read by path
  after the manifest was read, their hashes **unverified**; (b) `python3 -m py_compile export_operator.py` was not run;
  (c) `ruff check` was not run; (d) the `--offline-verify` run above was **not executed** — the output block in section 6
  is the expected output derived from the source, not an observation; (e) the SHA-256 and byte counts of the two staged
  files were not computed. The chief runs these five checks before placing the files; any failure returns to the worker
  lane as a fix, not a founder action.
- Inputs read (by path; hashes not verified here): the manifest; the contract revision 3; `FOUNDER-DECISIONS-FILE-ROUTE.md`;
  `tasks/readiness-2026-09-21/beta/readout_v1.py`; `tasks/readiness-2026-09-21/beta/posthog-v1-export.hogql`; the
  capability part and `g3/parts/VERIFICATION.json`; `G3-FILE-INPUT-CONTRACT-REVIEW-01.md`;
  `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/export-capability-run.json`;
  `tasks/review-evidence/beta-readout-2026-09-30/{literal-projection.hogql, parameters.json}`. Not opened:
  `fixture_check.py`, `readout.json` (not needed for the operator script).
- The founder-side script reads one environment variable directly; it is a standalone operator tool outside
  `backend/app`, so CLAUDE.md rule 8 (Settings-only env access for app code) does not apply to it.
- Nothing here marks cohort reporting, beta admission or capacity complete or admitted; G1–G5 states are unchanged by
  this runbook.
