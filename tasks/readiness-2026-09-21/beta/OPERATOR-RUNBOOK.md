# Operator runbook — founder-operated PostHog file-download export (D1 option O2) and the private store (D3)

**Status: authored by a bounded COO worker (`coo-operator-script-writer-01`, dispatch `COO-OPERATOR-SCRIPT-08`),
placed by the chief, revised once for the PR #1100 independent review findings; run only by the founder.** It
implements readout contract revision 3 §2.0 (lifecycle steps 1–8), §3 (the two legs) and the founder's decisions D1
(O2: founder-operated, with a founder-side verification script) and D3 (founder-side private directory; the repository
receives hashes and counts only). Nothing in this runbook authorises a customer-data export, a new export of any kind,
a PostHog charge, a production or CI change, or any statement that cohort reporting, beta admission or capacity is
complete or admitted. A customer export still needs every entry gate of the contract (§2.0 "Operator", §5): the
recorded G1 access decision (D2 text), the operator label registered in the exclusion closure, the private store in
place, and the G4 roster/exclusions/parameters by hash.

The script is `tasks/readiness-2026-09-21/beta/export_operator.py`, beside the released consumer `readout_v1.py` and
the D5 adapter `file_export_to_v1.py` (it imports `COLUMNS` from the former and the completeness rule from the latter
when they sit beside it). Standard library only, Python 3.11+, no package install. It performs HTTP only when the
founder runs it in export or resume mode.

## 1. Standing rules the script enforces

| Rule | How |
|---|---|
| The personal API key is never an argument, never printed, never written | Read once from the environment variable `POSTHOG_PERSONAL_API_KEY` inside `run_export`; passed as a parameter to the two HTTP functions; no logging module is imported; the only stdout site is `_say()` |
| The signed URL is never logged, stored or printed | Redirects are never followed automatically (`_NoRedirect`); in `_download_part` the `Location` value is read into the local variable `target`, fetched exactly once (without the bearer header unless its host is the API host), then deleted; it is not returned and not recorded |
| Redaction before any print or receipt | `_say()` and every error summary pass through `_redact()`: any `hogql_query` value and any occurrence of the bound query text (raw or JSON-escaped) become `<bound query; sha256 …>`; the raw response stays in `responses/` in the private store |
| No row is printed | Stdout carries counts, hashes, ids, statuses, UTC times and the verdict; a failed connector-leg or download-leg response prints only the HTTP status and the redacted `type`/`code`/`detail`/`attr` fields of a JSON error body (or a byte count) |
| Pricing stop | `FailedBilling`, or connector-leg response text containing payment, billing, trial or quota (substrings) or plan/plans (whole word), stops the run; the HTTP status, the matched word and the redacted structured fields are printed; no PostHog charge is authorised (exit 4) |
| One create per invocation | A single `create` POST sits in the lifecycle; `--resume RUN_ID` re-enters at step 4 with zero creates; any new create is a new invocation under a new authorisation |
| `n_before < 10000` | Otherwise the script stops before `create` with verdict `incomplete (cap)` (exit 4) |
| Poll robustness | A 5xx or a transport error on a retrieve poll is recorded in `calls` and retried at the poll interval until the deadline; only the deadline raises `source-unavailable` |
| Single completeness rule owner | When `file_export_to_v1.py` sits beside the script, its `file_export_completeness(run_record, parts, n_before, n_after, source_availability_recorded=…)` record IS the verdict; otherwise a byte-equivalent inline fallback runs; the receipt's `completeness_rule_source` names which rule ran |
| Private directory outside any repository | `--private-dir` is refused when any ancestor (or the directory itself) contains `.git` (exit 5); outputs are 0600 files in 0700 directories, created exclusively, never overwritten |
| Project identity | Recorded as given (`--project`, default 117863); no `project-get` call |
| Request shapes | Mirror `export-capability-run.json`: count-rows `{model: hogql, hogql_query, hogql_modifiers: {convertToProjectTimezone: false}}`; create adds `file: {format: JSONLines, compression: null, max_size_mb: null}`; the same `hogql_query` string object is serialised into both bodies; no `data_interval_*` bounds |

Hygiene proof (run by the chief on every revision; expected matches follow from the source):

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
   downloaded from (the operator record beside the part records `host: https://eu.posthog.com`, 302 then 200). Confirm
   against the production env (`POSTHOG_HOST` override) and the organisation's app URL before the first customer run;
   pass `--host` only if production differs.
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
5. **First-run path confirmation on the capability project (zero creates).** The three connector-leg REST paths the
   script uses were inferred from the MCP tool names (`file-download-batch-exports-count-rows-create`, `-create`,
   `-retrieve`); only the download path is recorded from an actual HTTP exchange (the capability part's operator
   record). Before any customer run, confirm the two read-only paths with the capability run, printing HTTP codes only:
   ```
   H=https://eu.posthog.com; P=117863; CAP_RUN=01a10d89-1ee8-0000-3e2c-9000712c9502
   curl -sS -o /dev/null -w 'retrieve %{http_code}\n' -H "Authorization: Bearer $POSTHOG_PERSONAL_API_KEY" \
     "$H/api/projects/$P/file_download_batch_exports/$CAP_RUN/"
   python3 -c 'import json,sys; print(json.dumps({"model":"hogql","hogql_query":open(sys.argv[1]).read(),
     "hogql_modifiers":{"convertToProjectTimezone":False}}))' \
     tasks/review-evidence/beta-readout-2026-09-30/literal-projection.hogql > "$PRIVATE/probe-count-rows.json"
   curl -sS -o "$PRIVATE/probe-count-rows-response.json" -w 'count_rows %{http_code}\n' \
     -H "Authorization: Bearer $POSTHOG_PERSONAL_API_KEY" -H 'Content-Type: application/json' \
     --data-binary @"$PRIVATE/probe-count-rows.json" "$H/api/projects/$P/file_download_batch_exports/count_rows/"
   ```
   Expected: `retrieve 200` (a 404 means the capability run record has expired — record it; still no create) and
   `count_rows 200` with `{"count": 3}` in the saved response (the literal projection is invented data; the body may
   be read). The create path is the same collection URL without `count_rows/`; it cannot be probed without creating,
   so it is confirmed by the first authorised run's `create` response — a 404 or 405 there stops the run before any
   export exists (`source-unavailable`, exit 3). Record the two codes in the first customer run's receipt notes.

## 3. D3 layout of the private store

```
<private-dir>/                                   # outside any repository; 0700
  <label>-bound.hogql                            # the bound query the founder prepares (roster literals; private)
  <label>-parameters.json                        # the consumer parameters file (eligible/excluded ids; private)
  <label>-<run_id>/                              # written by the script; named after the create response
    bound-query.hogql                            # byte copy of --query
    responses/01-count-rows-before-<UTC>.json    # every response exactly as returned, UTC-stamped
    responses/02-create-<UTC>.json
    responses/03-retrieve-<UTC>.json ...         # one file per poll (5xx polls included)
    responses/NN-count-rows-after-<UTC>.json
    parts/posthog-hogql-<run_id>-<file_id>.jsonl # raw bytes, one per id in files[] (rows: private)
    VERIFICATION.json                            # full operator record (steps 1-8, per-part checks, completeness, verdict text)
    v1-events.json                               # only when file_export_to_v1.py sits beside the script (rows: private)
    RECEIPT-PUBLIC.json                          # hashes, counts, ids, statuses, verdict class, window, N, labels, UTC only
    CUSTODY.txt                                  # "sha256  bytes  relative-path" per file + TOTAL=<files> <bytes>
  <label>-<run_id>-resume-<UTC>/                 # a --resume invocation: the same layout, steps 4-8 only
```

Until `create` answers, the run directory is `<label>-pending-<UTC>`; it is renamed to `<label>-<run_id>` on the create
response. A run that stops before `create` (cap, connector failure, pricing signal on count-rows) keeps the pending
name with its `VERIFICATION.json`, `RECEIPT-PUBLIC.json` and `CUSTODY.txt`.

**What leaves the private store.** To the chief, per run: `RECEIPT-PUBLIC.json` and `CUSTODY.txt` only. Never a part of a
customer run, never `bound-query.hogql`, never `responses/`, never `v1-events.json`, never `VERIFICATION.json` (it holds
the verdict text with any remote error text), never the private path. **What enters the repository:** hashes and counts
(the receipt's content: query SHA-256, part SHA-256 and byte lengths, run id, file ids, status, `n_before`, `n_after`,
`records_completed`, `rows_parsed`, verdict class with the SHA-256 and length of the verdict text, public failing-rule
statements, window, `N`, exclusion count, labels, UTC times). **Retention exception, stated once (contract §2.0):** parts
of invented-literal exports (the capability run, whose `FROM` is a literal subquery) are the only part bytes that may
enter the repository; every part of a run whose query names `events` is private, hash only.

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
   python3 tasks/readiness-2026-09-21/beta/export_operator.py --label W1 \
     --query "$PRIVATE/W1-bound.hogql" --private-dir "$PRIVATE" \
     --window-start 2026-MM-DDT00:00:00Z --window-end 2026-MM-DDT00:00:00Z \
     --n <N> --excluded-count <E>
   ```
   W2: `--label W2` with the week-2 bound query and window. Combined: `--label C` with the union window
   `[W1_start, W2_end)` and the same roster — a separate export, never a concatenation of the W1 and W2 parts.
   Defaults: `--host https://eu.posthog.com`, `--project 117863`, `--poll-seconds 15` (bounded 5–300),
   `--timeout-minutes 30` (bounded 1–240).
3. **Resume after a transient failure (same authorisation, zero creates).** If an invocation printed `run_id=…` (the
   create succeeded; `responses/02-create-*.json` exists) and then ended `source-unavailable` (poll deadline, transport
   failure, download failure), re-enter at step 4 for that run:
   ```
   python3 tasks/readiness-2026-09-21/beta/export_operator.py --label W1 --resume <run_id> \
     --n-before <count from responses/01-count-rows-before-*.json> \
     --query "$PRIVATE/W1-bound.hogql" --private-dir "$PRIVATE" \
     --window-start ... --window-end ... --n <N> --excluded-count <E>
   ```
   The resume writes `<label>-<run_id>-resume-<UTC>/`, performs retrieve, count-after, download, verify and
   completeness, and its receipt states `resumed_run: true` and `n_before_carried: true`. A run that never printed
   `run_id=` has nothing to resume; a new create is a new authorisation.
4. **Read the output.** Lines: identity (label, project, host, query hash and bytes); `columns: 21 (source: ...)`;
   `n_before=` (or `resume run_id=… n_before=… (carried)`); `run_id=`; one `poll k: status=` per retrieve (a 5xx or
   transport error prints `poll k: … retrying until the deadline`); `terminal status=Completed records_completed=
   files=`; `n_after=`; one `download i/n <file_id>: sha256= bytes= first_http=302 body_http=200` per part; one `part i
   <file_id>: ...` verification line per part; `completeness rule: ...`; the count line; `verdict: ...`; then the custody
   block (`custody <dir>:`, one line per file, `TOTAL=<files> <bytes>`).
5. **Exit codes.** 0 `complete` / `complete (zero rows)`; 2 `incomplete (...)` naming the failing rule(s); 3
   `source-unavailable (...)` (non-Completed terminal status, error field, 4xx or non-JSON connector response, poll
   deadline, download failure); 4 stop (`incomplete (cap)` or a pricing signal); 5 refused before any network call
   (missing key, private dir inside a git tree, unbound placeholders, bad arguments).
6. **Hand to the chief:** `RECEIPT-PUBLIC.json` and `CUSTODY.txt` from the run directory. Unset the key.

## 5. Stop conditions and what to do

| Signal | Script behaviour | Founder action |
|---|---|---|
| `n_before >= 10000` | `incomplete (cap)`, no create, exit 4 | Narrow the window under a new receipt; never truncate |
| `FailedBilling`, or payment/billing/trial/quota (substring) or plan/plans (whole word) in any connector-leg response | Stops at once; prints the HTTP status, the matched word and the redacted structured fields; exit 4 | Report the status, the matched word and the redacted structured fields; the raw response stays in the private store; **no charge, no plan change, no retry** |
| Terminal status other than `Completed`, or an `error` field | `source-unavailable (terminal status ...)`, exit 3 | Report; a second create needs new authorisation |
| 5xx or transport error on a retrieve poll | Recorded in `calls`; retried at the poll interval until the deadline | None while retrying |
| Poll deadline reached | `source-unavailable (poll timeout ...; resume with --resume ...)`, exit 3 | Do not cancel or re-create; `--resume <run_id> --n-before <carried>` under the same authorisation (section 4.3) |
| Download first/body HTTP not 302/200 (401, 403, 404, 410, a second redirect) | `source-unavailable (download of file i/n ...)`, exit 3; the redacted structured error fields only are printed | Report; the file availability window is unknown (contract K3), so run promptly after `Completed`; `--resume` re-downloads under the same authorisation while the files remain available |
| `n_after` not observed | Download continues; verdict `incomplete (n_after not observed)`, exit 2 | Report; the week stays unknown, not zero |
| Counts differ (`n_before`, `n_after`, `records_completed`, `rows_parsed`) | `incomplete (counts differ: ...)` | Honest incomplete (contract K9); re-run only under the settle rule and a new authorisation |
| Key set, BOM, CR, duplicate lines, key order, row order, `timestamp_s` type | Recorded per part in `VERIFICATION.json` (`deviations`, counts); key-set deviation is a finding for G3, not something the script coerces | Hand the receipt to G3; a projection change is a reviewed change, never an adapter coercion |

A `source-unavailable` or `incomplete` run leaves that week **unknown, not zero**; no partial window is reported as a
week; parts are never concatenated across runs or windows; `hasMore=false` is never manufactured.

## 6. Offline verification of the capability part (steps 7–8, no network)

Purpose: exercise the custody path and the verification code on the invented-literal part at zero risk (decision D3
"trial first"). The run record is derived from `export-capability-run.json` (call 9: `Completed`, `records_completed` 3,
one file id); `n_before` 3 from call 7; `n_after` was not taken in that run (contract §2.2 records this as a limitation
of the capability receipt). The verdict `incomplete (n_after not observed)` is therefore a **true statement about that
run, not a defect** of the part or the script.

```
PRIVATE=<a directory outside any git work tree>
mkdir -p "$PRIVATE"
cat > "$PRIVATE/capability-run-record.json" <<'EOF'
{"status": "Completed", "files": ["01a10d89-3a26-0000-56f3-e1f6c4004610"], "records_completed": 3}
EOF
python3 tasks/readiness-2026-09-21/beta/export_operator.py --label CAP \
  --offline-verify tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/parts/posthog-hogql-01a10d89-1ee8-0000-3e2c-9000712c9502-01a10d89-3a26-0000-56f3-e1f6c4004610.jsonl \
  --run-record "$PRIVATE/capability-run-record.json" --n-before 3 \
  --private-dir "$PRIVATE"
echo "exit=$?"
```

**Observed output — by the PR #1100 independent reviewer, from a copy of the head (7ee540aa), with `readout_v1.py` and
`file_export_to_v1.py` beside the script** (the two timestamped JSON outputs' byte counts and hashes vary from run to
run; the identity line shows the label used):

```
export_operator offline-verify label=<label> run_id=01a10d89-1ee8-0000-3e2c-9000712c9502 parts=1
columns: 21 (source: readout_v1.COLUMNS)
part 1 01a10d89-3a26-0000-56f3-e1f6c4004610: sha256=67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5 bytes=2092 rows=3 key_set_equal_rows=3 key_order_equals_projection_rows=0 bom=None cr_bytes=0 ends_with_newline=True duplicate_lines=0 duplicate_uuids=0 deviations=2
completeness rule: file_export_to_v1.file_export_completeness
n_before=3 n_after=None records_completed=3 rows_parsed=3 status=Completed
verdict: incomplete (n_after not observed)
custody <label>-01a10d89-1ee8-0000-3e2c-9000712c9502:
<sha256 varies>  <bytes vary>  RECEIPT-PUBLIC.json
<sha256 varies>  <bytes vary>  VERIFICATION.json
e37fed76…  1839  v1-events.json
TOTAL=3 9066
exit=2
```

`v1-events.json` (1,839 bytes, SHA-256 `e37fed76…`) equals the committed `d4-events.json`, the D4 dry-run input. The
two `deviations` on the part are the ones G3 review 01 recorded: key order differs from the projection on 3 of 3
rows, and rows are not ordered by `(timestamp_s, uuid)`; both are recorded, neither is a key-set or rendering failure.
Without `readout_v1.py` beside the script the columns line reads `columns: 21 (source: embedded (readout_v1.py not
present beside the script))`; without `file_export_to_v1.py` the rule line reads `completeness rule: inline fallback
(…)` and no `v1-events.json` is written (`TOTAL=2`). The D4 offline consumer dry run (`readout_v1.py --events
v1-events.json --parameters ... --query ... --output ...`) runs under its own authorisation, not this runbook.

## 7. What the chief records

From each run: the receipt's hashes and counts (query SHA-256, part SHA-256/bytes/rows, run id, file ids, status,
`n_before`, `n_after`, `records_completed`, `rows_parsed`, verdict class plus `verdict_text_sha256`/`verdict_text_bytes`,
public failing-rule statements, `completeness_rule_source`, `resumed_run`/`n_before_carried`, window, `N`, exclusion
count, labels, UTC times) and the `CUSTODY.txt` lines. Executive contexts (chief, officers, management workers) receive
these only — never a part, the bound query, a response body, the verdict text with remote error text, the key or a
signed URL (contract §3). The G3 reviewer is a separate non-executive context that reads hashed artefacts and the run
record.

## 8. Authoring record and deviations (worker `coo-operator-script-writer-01`)

- Written with no network, connector, PostHog or HTTP call; no package install; nothing opened under
  `tasks/readiness-2026-09-21/acceptance/` or `/root/.claude/uploads/`. The first revision was staged outside the
  repository and placed by the chief; this revision (review findings applied) was written in place at the chief's
  instruction, without commit or `git add`.
- **Deviation — the worker's session cannot execute commands.** Bash and Monitor were blocked for the whole
  conversation by the auto-mode safety classifier, which reacts to the dispatch prompt's content (API key, bearer
  header, signed URL wording), not to any command. Consequently, in the authoring session: (a) the manifest and input
  SHA-256/byte checks could not be computed — inputs were read by path after the manifest, their hashes unverified by
  the worker; (b) `python3 -m py_compile`, (c) `ruff check` and (d) the `--offline-verify` run were not executed by the
  worker — **(b)–(d) were executed on the first revision by the chief (py_compile ok, ruff clean, hygiene greps as
  expected) and by the PR #1100 independent reviewer (section 6 output, exit 2, `TOTAL=3 9066`)**; (e) the staged files'
  SHA-256 and byte counts were not computed by the worker. For this revision the chief re-runs py_compile, ruff and
  the hygiene greps, and the delta reviewer executes `--offline-verify` and exercises the `--resume` and redaction paths
  offline before anything is placed or merged.
- Review findings applied in this revision (PR #1100, head 7ee540aa): single completeness rule owner (adapter record
  is the verdict; inline rule kept only as a byte-equivalent fallback with the adapter's `error`, whole-word `plan` and
  explicit zero-row semantics; receipt names the rule that ran); redaction of `hogql_query` values and bound-query
  bytes before any print or receipt, pricing stop printing status + matched word + redacted structured fields only;
  5xx/transport-error polls retried until the deadline; `--resume RUN_ID --n-before N` for steps 4–8 under the same
  authorisation; receipt verdict as class plus SHA-256/length of the verdict text with public failing-rule statements
  only; runbook §2.5 first-run path confirmation; §6 observed output; repository paths throughout.
- Inputs read for the first revision (by path): the manifest; the contract revision 3; `FOUNDER-DECISIONS-FILE-ROUTE.md`;
  `tasks/readiness-2026-09-21/beta/readout_v1.py`; `tasks/readiness-2026-09-21/beta/posthog-v1-export.hogql`; the
  capability part and its operator `VERIFICATION.json`; `G3-FILE-INPUT-CONTRACT-REVIEW-01.md`;
  `tasks/code-red-20261004/runtime/handbacks/coo/export-validation-01/export-capability-run.json`;
  `tasks/review-evidence/beta-readout-2026-09-30/{literal-projection.hogql, parameters.json}`. For this revision:
  the placed `export_operator.py`, this runbook and `tasks/readiness-2026-09-21/beta/file_export_to_v1.py` (to mirror
  its completeness semantics). Not opened: `fixture_check.py`, `readout.json`, `d4-events.json`.
- The founder-side script reads one environment variable directly; it is a standalone operator tool outside
  `backend/app`, so CLAUDE.md rule 8 (Settings-only env access for app code) does not apply to it.
- Nothing here marks cohort reporting, beta admission or capacity complete or admitted; G1–G5 states are unchanged by
  this runbook.
