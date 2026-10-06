# Decision record 09 — PR #1099 merged after GitHub's Actions incident; founder instruction 20:17Z (IAM verified DENIED; export part; G3 review 01; contract revision 3; R1 reconciliation; review and reservation rules; deploy-scoping explanation); founder adopts D1–D5 (G1 text; D5 adapter; D4 dry run; D1/D3 operator script); closures 154–157 (chief, 2026-10-05)

Recorded 2026-10-05T22:05:00Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Context: record 08 merged to main as `eccf45a31a45b1b69d20a1a37111f4131b3f4b93` (PR #1099; GitHub `merged_at` 2026-10-05T21:59:56Z; squash commit timestamp 21:59:55Z); this
branch was restarted from that main. Records plus the file-route implementation under `tasks/readiness-2026-09-21/beta/` (adapter,
fixture extension, operator script, runbook — tasks-side Python added): no runtime or service code, workflow, migration, cloud, IAM or
production change; a tasks-only merge leaves `deploy-backend`'s deploy steps skipped (the merge's CI on main is recorded below).
Amended 2026-10-05T22:49Z after the three-lens review of `7ee540aa` (findings applied; review section below).
Amended 2026-10-05T23:05Z with the delta review's wording corrections (commit `4907e6a3`; this amendment line added in record 10 per the carried nit).

## PR #1099 — merged

| Item | Value |
|---|---|
| Final head | `ad915c441f5ec6e52152da8f7de2df385081827e` (five commits on top of main `c780228a`) |
| Delta review | pre-registered delta reviewer (closure 153 provisional label; launched 19:32:45Z; resolved in closure 154): **NO BLOCKER bound to `ad915c44`**; 58 checkpoint hash rows / 0 mismatched (56 / 0 at `6f5d07a2`); closure 153 against 152 10 / 10 checks; the 30 workflow contexts matched to closure 153; 27 / 27 prior findings addressed; manifest `COO-EXPORT-VALIDATION-05` 10 / 10 inputs; export receipt and run JSON consistent across five files; seven nits (below) |
| Reviewer deviation (disclosed) | one classifier denial (PII Data Handling) on a Bash read of the harness's persisted tool-results file holding an oversized diff; not pursued; per-file `git diff` re-run against the repository with bounded output. Read-only throughout; nothing under `acceptance/`, no upload opened |
| Marked ready | 19:45:20Z (the chief); the Codex connector posted its usage-limit comment 6001767728 at 19:45:21Z; no `@codex review` re-request |
| Review override | bound to `ad915c44` in the PR body at 19:46Z, citing comment 6001767728; `review-gate` success on the `edited` run (the `ready_for_review` run was cancelled by the edit) |
| Required checks on `ad915c44` | `backend-tests` success 19:43:47Z and `eval-baseline` success 19:41:22Z (attempt 1; no AI-relevant change, so no paid job), `review-gate` success 19:47:10Z (run 37365546132, the `edited` event); `frontend-tests`, `e2e-tests`, `migrations-postgres`, `lighthouse` and `secret-scan` cancelled by the platform at 19:51:03Z after 15 minutes queued with no runner during GitHub's "Incident with Actions" (runner-assignment delays, then major outage; status page updates 19:50Z–21:32Z), then **re-run once** (`rerun_failed_jobs` on run 37364453310 at 21:55:36Z, after the status page showed Actions operational) and all five success by 21:59:18Z (attempt 2). Six required checks green on the unchanged head; the earlier evidence reused |
| Paid jobs | none (tasks-only: `copilot-eval` not triggered; `eval-baseline` passed without an AI-relevant change) |
| Merge | squash `eccf45a31a45b1b69d20a1a37111f4131b3f4b93`, GitHub `merged_at` 2026-10-05T21:59:56Z; main CI: run 37379578901 on `eccf45a3` (tasks-only: the `deploy-backend` job succeeded with its deploy steps skipped — no `backend/` change) |

## Seven nits from the delta review — applied here

1. Stamp order at `6f5d07a2` (checkpoint header 19:31:58Z before closure 153's 19:31:59Z): moot at `ad915c44`; rule for the chief: take the header stamp after the last bound file is written, and stamp no bound file after the header (its converse, breached by the 22:08Z stamps of the first commit and corrected in the second).
2. Record 08 header: amendment lines added for 19:07:44Z (revision 2), by 19:31:58Z (founder instruction, ticket 76581, manifest 05, closure 153), 19:35:53Z (export outcome) and this record's edit.
3. Checkpoint hash-row description for record 08 extended to its later sections.
4. The x-masked return time replaced by "19:32Z (run file recorded 19:32:44Z)" in record 08 and checkpoint decision 29; "nothing else called" replaced by "no other export tool called (`learn` ×2, `info` ×4 only)".
5. "Third delta" lowercased in the PR #1098 review record.
6. `APPOINTMENTS.json` `query_route_contract_draft_01` parentheses flattened (facts unchanged).
7. PR #1099 applied-findings list: "event-3 write time" dropped (no such finding; the text was unchanged); the dry-run item now states the clause was removed and the CEO's decision recorded in Next (4).

## Founder status update and masterplan next steps — delivered 19:58Z

Delivered in the session as requested ("after this work is done"): delivered outcomes, a refreshed wave table (R1–R5 and shared spend; counts, blockers recorded once, next deliverable with acceptance), actual spend, five masterplan steps in priority order with finite exits, and the five founder-only items. Nothing in it admits capacity, releases inputs, infers consent or marks cohort reporting complete; holds unchanged.

## Review of this PR's head `7ee540aa` and its CI (added 22:49Z)

**Review (proportionate, per the record-09 rule for a PR that adds code):** a three-lens read-only workflow (anchors, code, policy)
with one refuter per blocker/should-fix finding only — 13 contexts (3 lenses + 10 refuters), registered in closure 157 by
resolving closure 156's provisional label. **NO BLOCKER ×3 on `7ee540aa`.** Anchors: 78 checkpoint hash rows / 0 mismatched;
closure chain 153 → 156 66 / 66 checks; manifests 06/07/08 inputs matching at head except the three inputs bound at the
pre-revision bytes (each explained); every locally checkable hash, byte count, commit and time in this record verified; the
seven carried nits 7 / 7 applied. Code: `py_compile` and `ruff` clean; `fixture_check.py --adapter-only` exit 0 and `--v1-only`
byte-identical to the base; the D4 reproduction byte-identical to the committed `d4-*.json` and equal to the September 30 readout
except `input_sha256.events`; **`export_operator.py --offline-verify` executed by the reviewer on the invented-literal part**:
verdict `incomplete (n_after not observed)`, exit 2, `TOTAL=3 9066`, `v1-events.json` byte-identical to the committed
`d4-events.json`, the git-tree private-dir refusal exercised, the recorded request-body hashes reproduced — the execution check
the author could not run (classifier denial 6) is therefore done. Policy: no private URL, token, signed URL, customer data or
MacBook path; the only part bytes are the invented literals; decision fidelity to D1–D5 confirmed; IAM three states, D3 held,
reservation rule and R1 table as stated. Findings: 0 blocker, **10 should-fix** (code 4; anchors 2; policy 4, two overlapping
the others), 24 nits; 10 refuters / 0 refuted.

**Applied in the following commit (re-checked by the pre-registered single delta reviewer before the override is bound):**

| # | Finding (should-fix) | Fix |
|---|---|---|
| S1 | Two step-8 rules shipped (adapter and the operator's inline copy) with different `error`, zero-row and `plan` semantics; a disagreement produced an empty-reason `incomplete` | Single rule owner: the adapter's `file_export_completeness` (fails on `error` only when present and non-null; `plan`/`plans` whole-word; zero rows complete only with an explicit `source_availability_recorded=True` argument); the operator calls it when present and names the rule that ran in the receipt. Its inline fallback (used only when the adapter file is absent beside the script) is equivalent on the error / whole-word plan / zero-row semantics but **not byte-equivalent**: the adapter's duplicate-part, files-order and hex-digest rules are adapter-only (delta review of `ec58eeb4`, 12-case probe: 8 equal, 4 divergent); the receipt, docstring and runbook say so |
| S2 | A part supplied twice collapsed in the adapter's id-keyed inventory (6 rows fed, `rows_parsed` 3, verdict complete) | `rows_parsed` over the parts as supplied; failing rule for a repeated id; the CLI refuses duplicate `--parts` |
| S3 | On a pricing stop the operator printed up to 4,000 characters of the connector response verbatim; a REST response echoing `hogql_query` would carry roster literals to stdout and to an executive context | Redaction of any `hogql_query` value and of the bound query bytes before any print or public receipt; status, matched word and structured fields only; raw response stays in the private store; runbook §5 reworded |
| S4 | One transient 5xx on a retrieve poll ended the invocation and would waste an authorised customer export (a second `create` needs new authorisation) | Retry 5xx/URLError within the poll deadline; `--resume RUN_ID --n-before N` runs steps 4–8 with zero creates |
| S5 | `APPOINTMENTS.json` `updated_at` and the `LEDGER-ACCESS.md` heading were stamped 22:08Z, after the 22:07:07Z commit that contained them | Stamps corrected to their actual write times (22:06Z); the rule "take the header stamp after the last bound file is written" restated with its converse |
| S6 | This record's title and scope sentence read as a records-only record with closure 154, while the PR carries code and closures 154–157 | Title and scope sentence rewritten (this header) |
| S7 | The checkpoint row for the contract draft carried an editing remnant and revision 2's description beside revision 3's hash | Row rewritten for revision 3 with revision 2 and 1 as predecessors |
| S8 | Row 1a's state cell was stale ("awaiting the founder's file") and the operator's disclosed credential-setup caveat appeared only in closure 155 and APPOINTMENTS | Cell rewritten with the receipt facts and the caveat |

**Nits applied in the same commit** (same files, no extra cycle): manifest 06 byte count (7,123) at its first mention; the x-masked time quotation reworded; the squash commit timestamp added beside `merged_at`; the `deploy-backend` wording; the `LEDGER-ACCESS.md` and `APPOINTMENTS.json` row descriptions extended; separators in two appended APPOINTMENTS values; the PR #1099 review record's "Next (4)" pointer annotated; the key-status attribution in founder item 5(b) corrected to the operator's hand-over; adapter: duplicate-key rejection, both-outputs-exist check, `files[]` order and hex-digest rules, a parity fixture pinning the D4 result on the committed part; operator/runbook: receipt verdict class plus hash of any error summary, a first-run connector-leg path confirmation step, §6 replaced by the reviewer-observed output, §8 marked executed, staging references pointed at repository paths.

**File identities after the applied findings (second and third commits; the third carries wording corrections only):**

| File | SHA-256 | Bytes | Writer |
|---|---|---|---|
| `tasks/readiness-2026-09-21/beta/file_export_to_v1.py` | `95287af3df81fec54bc22224120b7a0047ab20c6cfc107b27460f217ff50369e` | 11,248 | CTO adapter writer (revision 2) |
| `tasks/readiness-2026-09-21/beta/fixture_check.py` | `3559e4283c8c07fcbd1390819ddfc9a206b5b99ae6308d4142eb8a3d4436e58a` | 44,510 | CTO adapter writer (insertion-only vs the release; `--v1-only` output still `cf6ebba0…`) |
| `tasks/readiness-2026-09-21/beta/export_operator.py` | `2668223cceb0db9ccf1c44d7f4b41ccf876b529c1e4f69eee8f2f927368ac14d` | 57,402 | COO operator-script writer (revision 2; edits only — execution still denied in its context) |
| `tasks/readiness-2026-09-21/beta/OPERATOR-RUNBOOK.md` | `9018e7ab214d51f7443b400b23473f30e74d6f2a19195bec791455bc3d4d335c` | 26,372 | COO operator-script writer (revision 2) |
| `handbacks/cto/ADAPTER-NOTES-01.md` | `fabe9323e3fb25505a386dea87998eeb10850f8fb334d0b29816a7843e8c0dc9` | 39,606 | CTO adapter writer ("Revision 2 (review findings)" section) |

Chief verification after the writers returned (22:48–22:49Z): `py_compile` ok and `ruff` clean on the three `.py` files; `fixture_check.py --adapter-only` exit 0 with the new D4-parity fixture passing and the `error_null` / `error_empty` / `explanation_text` cases passing; `--v1-only` output byte-identical (`cf6ebba0…`); the committed `d4-*.json` unchanged by the adapter revision (writer re-ran and compared); `readout_v1.py` byte-identical to the release; hygiene greps on the operator unchanged (no `print(`, key from the environment only, `Location` local-only). The operator's `--offline-verify`, `--resume` refusal and redaction paths are executed by the delta reviewer.

**Delta review of `ec58eeb4` (single pre-registered reviewer, closure 157; resolved in record 10): NO BLOCKER bound to `ec58eeb4`.** 79 hash rows / 0 mismatched; closure 157 against 156 fully verified (274 → 288; 13 actual + 1 provisional; 13 agent ids equal the workflow's meta files); S1–S8 8 / 8 present (S1's equivalence claim corrected below), the 15 applied nits 15 / 15 present; from a depth-3 mirror: `py_compile`/`ruff` clean, `--adapter-only` exit 0 (D4 parity passed), `--v1-only` `cf6ebba0…`, `export_operator.py --offline-verify` on the committed part → `incomplete (n_after not observed)`, exit 2, rule named as the adapter's, `v1-events.json` byte-identical to the committed `d4-events.json`, `TOTAL=3 8722` (1,828 / 5,055 / 1,839 bytes; stable across two runs); `--resume` refusals (no `--n-before`, bad run id, with `--offline-verify`, no key) and the git-tree private-dir refusal exercised with no HTTP; the redaction helper replaced a `hogql_query` value and bound-query bytes; D4 files byte-identical to a fresh run; `readout_v1.py` unchanged; policy greps clean. Findings: 0 blocker, 4 should-fix (all factual-accuracy items in hash-bound files, none on the exercised path), 8 nits. **Applied in the third commit:** (1) the fallback described as equivalent on semantics, not byte-equivalent (receipt string, docstring, runbook §1, adapter notes, S1 row above); (2) the chief-verification range corrected to 22:48–22:49Z (the 22:52Z end post-dated the commit); (3) runbook §6 replaced with the `ec58eeb4` output the delta reviewer observed (`TOTAL=3 8722`; byte counts stable, hashes vary), the `7ee540aa` figures kept only as the first reviewer's observation; (4) the adapter notes' revision-2 stamp corrected from ~22:05Z to the actual ~22:44Z. Nits applied: the record-09 and operator checkpoint-row descriptions; the exact re-run second; the capitalisation; closure 157's labelling convention stated in its scope; the runbook documents pricing-before-retry as intended. **Carried to record 10:** the operator's offline mode reads `source_availability_recorded` from the operator-authored run record rather than an explicit flag (align with the adapter CLI); the 7ee540aa review's remaining carried items.

**Nits carried to record 10 (hash-bound files or not worth a cycle):** the session upload-directory literal in manifests 07/08, the G3 review, the adapter notes and the runbook ("the session's upload area" wording in future); `FOUNDER-DECISIONS-FILE-ROUTE.md`'s "first download" reads as "first customer download"; manifests 07 and 08 share one clock read (generated together); the fixture's end-to-end equality proves order-invariance and consumability, with parity pinned separately by the new D4 fixture.

**CI on `7ee540aa`:** `backend-tests` failed once on `tests/unit/test_inflight_dedup.py::test_waiter_serves_leader_result_without_regenerating` (`assert False` over heartbeats; a coroutine-never-awaited warning) with 5,715 passing. Not this PR's: the PR changes nothing under `backend/`; the identical backend code passed on `main` `eccf45a3` eleven minutes earlier (run 37379578901) and on `ad915c44`; the test is timing-dependent (`asyncio.sleep(0.2)`). One standing-down comment posted on the PR (comment 6004234330) and the single re-run requested at 22:15:44Z (attempt 2 started 22:15:44Z): `backend-tests` success 22:23:50Z; all eight jobs green. A robustness fix would be a `backend/tests/` change outside this tasks-only PR and would trigger the paid `copilot-eval` workflow; recorded for the CTO as a candidate, not carried here.

## Classifier denial 6 — the operator-script worker's command execution (worker context)

The bounded COO worker authoring `export_operator.py` reported that every command-execution attempt in its context (Bash twice, a
Monitor once, including read-only `sha256sum` and `wc -c`) was refused by the platform's auto-mode classifier, which stated it
reacted to the dispatch prompt's wording (API key, bearer header, signed URL) rather than to the commands. Consequences,
recorded as the worker reported them: input hashes were not verified before reading (a procedure violation, disclosed); the
script was neither compiled, linted nor run by its author. The denial is not worked around: the worker was not re-dispatched
with altered wording; the chief performed only its standing hand-back verification (hashes, `py_compile`, `ruff`, leakage greps);
the execution check (`--offline-verify` on the invented-literal part) is assigned to the independent code-lens reviewer of this
PR, whose brief already includes running the kit's offline checks. Lesson for dispatch wording: a worker that must execute
commands cannot carry credential-handling vocabulary in its brief; the next operator-tool dispatch separates the two.

## Registration (closures 154–157)

`control/source-context-exclusion-154.json` (268 entries) resolves the record-08 delta reviewer's provisional label to its
launch-time identity (19:32Z). `-155.json` (270) registers the founder-operated Codex download worker (external, actual; request
20:52:57Z) and the single G3 reviewer (actual; launched 21:04Z). `-156.json` (274) registers the CTO adapter writer and the COO
operator-script writer (both launched 21:34Z; actual), the human operator role `founder-operator:readout-export-legs-01` (D1
option O2; registered before any customer run) and pre-registers this PR's proportionate review (`adapter-review-01`,
provisional). `-157.json` (288) resolves that label to the 13 contexts of review workflow `wf_955b20cc-eb7` (3 lenses, 10 refuters) and pre-registers the single delta reviewer of this PR's final head (`record-09-delta-reviewer-01`, provisional; resolved in record 10). The COO revision-3 author is the already-registered context of closure 152.

## Spend

0 DeepSeek calls; 0 active reservations; 0 ledger events. Headroom unchanged at USD 22.539628 conditional unreserved under the USD 25 authority.

## Founder instruction received 2026-10-05 ~20:17Z — recorded and executed within authority

| # | Instruction (intent) | Action by the chief | State |
|---|---|---|---|
| 0 | IAM bindings run (both commands clean); verify with the `logs-probe` | Read-only `ops.yml` `logs-probe` dispatched on `main` `c780228a` at 20:21:06Z (Ops run 37369180920) during GitHub's Actions runner incident | First dispatch (run 37369180920, job 111962125429) was cancelled by the platform after 15 minutes queued with no runner (20:22:12Z → 20:37:15Z; no step ran; no evidence). Second dispatch at 21:55:36Z after GitHub reported Actions operational: run 37379102331, job 111996067424, conclusion success; the probe step printed **`logs-probe: logging.read DENIED (rc=1)`** — `PERMISSION_DENIED: Permission denied for all log views. This command is authenticated as github-deployer@earnings-nerd.iam.gserviceaccount.com` (21:55:53Z). **Access is therefore NOT verified**: the bindings the founder reports as applied at ~20:17Z are not effective for this principal 98 minutes later (propagation is normally minutes). IAM state: authorized (record 08) → applied per the founder's statement → **verified DENIED**. The chief makes no IAM change; the founder is asked to run the read-only policy check in the morning report |
| 1a | Give the exact authenticated download link or navigation for the existing export part; do not repeat the export | PostHog documentation (two read-only `docs-search` calls): file-download exports are API-only; the run's part is fetched by an authenticated GET on the private API host with a `batch_export:read` personal API key; both URL forms (part path from the connector's command description; run-level `download/` from the API reference) given to the founder at ~20:24Z, re-issued for EU cloud at ~20:26Z when the founder stated the organisation uses PostHog EU; the key and redirect URL are never written anywhere | **Received 20:52:57Z** — downloaded by the founder's own Codex operator (GPT 6.1, operator-side) on EU cloud with the part-path URL form (one GET, HTTP 302 → 200; part `67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5`, 2,092 bytes; `VERIFICATION.json` `e5f5c2db…`, 16,233 bytes); chief hash-verified (3 rows, 21-key sets, fixed uuids); the operator disclosed its credential setup (browser key creation, scope reduced to `batch_export:read` on project 117863, transient clipboard transfer, cleared) as outside the bounded download phase, its `api_call_statement` scoped to that phase, and that the key remained active — revocation recommended to the founder; G3 review 01 followed (closure 155) |
| 1b | File-download route selected; revise the draft for that route; present only the necessary founder decisions with recommended answers; no competing routes | Same registered COO context (closure 152) resumed on manifest `COO-FILE-ROUTE-REVISION-06` (`a73d0066…`, 7,123 bytes; nine input hashes; no connector call; staged outside the repository) | **Delivered** ~20:32Z: revision 3 of `handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md` (as placed `ad599074e6f27149b6bfb736fccdb45014d1bdc411a2b087165a23d09e9b16dd`, 47,321 bytes, after one chief sanitisation of a session-local path; worker's staged `afe6b59a…`, 47,331 bytes) and `handbacks/coo/FOUNDER-DECISIONS-FILE-ROUTE.md` (`7bfe1e63c0b56ffac9bced4161df747ed711e162274e1788571980f854fa906c`, 14,894 bytes); 9 / 9 inputs hash-verified; EU host carried as the founder's stated assumption; manifest 7,123 bytes (the dispatch message said 7,112 characters; hash controlling) |
| 2 | Distinguish "roles recorded" from "bindings applied and access verified"; keep unresolved until evidence; then perform the existing bounded readout | Recorded as three states: authorized (record 08) → applied (founder statement 20:17Z, commands ran clean; not evidence of access) → verified (only by the probe's `logging.read PERMITTED` line). The bounded readout is the same `capacity-readout` over the Monday 06:00–08:00 UTC window (record 02 D4), dispatched only after the probe shows PERMITTED and no main CI is in flight | **Not dispatched**: the gate (probe PERMITTED) did not hold. B32/B56 remain unobserved; C1 items 1 and 5 keep the B62 sub-dependency |
| 3 | R1: recovery and archive integrity confirmed; complete-manifest verification and planner resumability unconfirmed; preserve gates; reconcile the allowance without resetting it | Custody state updated: recovery and archive integrity CONFIRMED by the founder (20:17Z); outstanding: complete original input-manifest comparison, the two `TOTAL=` lines, registered-planner resumability; release receipt NOT_RELEASED; gates unchanged. Allowance reconciled below | Recorded |
| 4 | Stop optional review chains and cosmetic iterations; batch records around substantive deliverables; explain the PR #1098 deploy; propose one bounded correction under the existing owner | Review rule and the deploy explanation below | Recorded; correction proposed, not applied |
| 5 | Keep the reservation overrun visible; reservations carry justified headroom; USD 0.03 is a measured minimum; re-run only the necessary cancelled jobs; reuse unchanged-head evidence | Reservation rule below; `rerun_failed_jobs` (five cancelled jobs only; `backend-tests`, `eval-baseline`, `review-gate` results on `ad915c44` retained) once GitHub's runner incident clears | Re-run once at 21:55:36Z when GitHub reported Actions operational (not during the outage); five jobs success by 21:59:18Z; merged 21:59:56Z |

### R1 allowance — reconciled, not reset

| Item | Minutes |
|---|---|
| Allowance (record 02 D2; three focused hours of source-only planner refinement) | 180 |
| Charged before record 03 | 10 |
| Charged after record 03 (inside `minutes_used`) | 20 |
| Total charged | 30 |
| Remaining | 150 |

Not charged: the founder's and Astra's recovery, packaging and archive-integrity work and the read-only custody check (none is planner refinement); the chief's and reviewers' time (not part of the allowance). The balance is unchanged by this record; the founder's confirmation of recovery and archive integrity adds no minutes and resets nothing.

### Why PR #1098 deployed unchanged application code

`deploy-backend` decides to deploy with `git diff --name-only HEAD^ HEAD | grep -qE '^backend/'`. PR #1098 changed `backend/tests/unit/test_capacity_readout.py` (and `ops/capacity/readout.py`, outside the filter). `backend/.dockerignore` excludes `tests/` from the build context, so the image's application content was unchanged while the filter still fired; Docker produced a new digest (`b35a9b5b…`) because image builds are not reproducible, and Cloud Run rolled revision 00444. This is a workflow-scoping defect: the deploy trigger is wider than the build inputs.

**Proposed bounded correction (owner: CTO; one line in `.github/workflows/ci.yml`; its own PR; the founder's release boundary applies because it changes the deploy pipeline):** make the filter mirror the build context by excluding the paths `.dockerignore` excludes, i.e. `git diff --name-only HEAD^ HEAD | grep -E '^backend/' | grep -vqE '^backend/tests/'`. Everything that reaches the image (`backend/app`, `backend/main.py`, `backend/requirements*.txt`, `backend/Dockerfile`, `backend/migrations/`, `backend/prompts/`) still deploys. Rule 12: the same PR adds a unit test asserting the filter's exclusion list equals `.dockerignore`'s directory excludes under `backend/`. Not applied here.

### Review rule for records-only PRs (efficiency)

From this record: a records-only PR gets one independent read-only reviewer context (hash table, closure chain, anchors, policy greps) bound to the final head; the three-lens-plus-refuters workflow is reserved for PRs that change code, workflows or a contract; nits are carried into the next substantive record, never a cosmetic commit; records are batched around substantive deliverables (a hand-back, a run receipt, a founder decision). Required gates and the `Review override:` mechanism are unchanged.

### Reservation rule (refined)

A reservation is written before any paid action at `max(measured cost of the dearest comparable run) × a stated headroom factor`, with the factor justified in the ledger event. For `copilot-eval`: two measured runs on identical code cost USD 0.005575 and 0.025568 (4.6×); the next reservation is USD 0.06 (0.025568 × 2, rounded up) unless a dearer run is measured first. USD 0.03 is the measured minimum, not a ceiling. The event-3/event-4 overrun (USD 0.015568 unreserved) stays visible in every ledger view and in `LEDGER-ACCESS.md`.

## Founder decisions adopted 2026-10-05 ~21:15Z — "go with COO recommendations"; next stage of implementation authorised

The founder adopted D1–D5 as recommended in `handbacks/coo/FOUNDER-DECISIONS-FILE-ROUTE.md` and asked the chief to progress
execution overnight. Recorded dispositions and the executable work each one releases:

| Decision | Adopted answer | Executable consequence (owner) | State at this record |
|---|---|---|---|
| D1 operator identity | **O2 — founder-operated** for both legs with a founder-side verification script; the G3 reviewer a separate non-executive context | Founder-side `export_operator.py` and runbook authored by a bounded COO worker (manifest `COO-OPERATOR-SCRIPT-08`); operator label `founder-operator:readout-export-legs-01` registered in closure 156 before any customer run; no customer run occurs before §5 gates | **Authored and staged** (writer returned ~22:02Z): `tasks/readiness-2026-09-21/beta/export_operator.py` (SHA-256 `0ec82832ed363c376d0e52b274fedf3d2e04002d0c3cf9634f3135037e5816d6`, 47,977 bytes) and `OPERATOR-RUNBOOK.md` (`d7fb545664d8a68e0ce1098b1987ef3f8ee0e61bd91c000ecca771357f6c5822`, 19,060 bytes). **Worker verification blocked (classifier denial 6, below)**: the worker could not execute any command, so it did not hash its inputs, compile, lint or run `--offline-verify`; it reported this rather than conceal it. Chief static verification: `py_compile` ok, `ruff` clean, no `print(` call (two `sys.stdout` writes in one helper), the key read only from the environment variable, the redirect `Location` held in a local variable and deleted after one fetch, three bearer-header construction lines. Execution of `--offline-verify` on the capability part is left to the independent code-lens reviewer of this PR; the runbook's §6 expected output is labelled as expected, not observed |
| D2 G1 access decision | Record the drafted text, dated, once the part is verified and G3-reviewed | Recorded below with the production-host confirmation explicitly outstanding; G1 closes on that confirmation | Recorded; host confirmation outstanding |
| D3 private store | Founder-side private directory under the custody convention; repository hashes and counts only | The operator script writes parts, responses and the bound query only to `--private-dir` (outside any git work tree) and prints custody lines; `RECEIPT-PUBLIC.json` and `CUSTODY.txt` are the only repository-bound outputs; trialled on the capability part by `--offline-verify` | **Implemented in the operator script and runbook** (private-dir refusal inside a git work tree; `CUSTODY.txt` with per-file sha256/bytes and a `TOTAL=` line; `RECEIPT-PUBLIC.json` hashes and counts only); the trial on the capability part is the `--offline-verify` run assigned to the PR's code-lens reviewer (classifier denial 6); the invented-literal capability part is the only part bytes placed in the repository (retention exception, contract §2.0) |
| D4 dry run | No second export; one offline consumer dry run on the three-row part once D5 exists | Run by the adapter writer in staging on the actual capability part with the September 30 parameters and query; compared field by field with the September 30 consumer output | **Run** (adapter writer, staging, ~21:45Z): adapter CLI on the actual part with `--n-before 3` and no `--n-after` (not observed in the capability run) → `d4-events.json` (`e37fed76…`, 1,839 bytes) and `d4-completeness.json` (`b2f7c871…`, 425 bytes: status Completed, records_completed 3, n_before 3, n_after null, rows_parsed 3, one file hashed, `file_export_complete_observed` **false**, failing rule `n_after not observed`); released consumer on that output with the September 30 parameters and query → `d4-readout.json` (`1c64010f…`, 2,430 bytes): 20 top-level fields compared with the September 30 readout, 19 equal, the only difference `input_sha256.events` (file order 10, 12, 11); one view, one paired complete request, 1,000 ms, no diagnostics; `export_complete_observed` false in both by construction. The September 30 readout is reproduced from the actual part through the adapter |
| D5 consumer gap | **Option A — thin adapter**, authored after G3's accept on the actual part; released consumer byte-unchanged | `file_export_to_v1.py` (+ `fixture_check.py` `--adapter-only`) authored by a CTO-named minimal implementation writer (manifest `CTO-FILE-EXPORT-ADAPTER-07`); proportionate independent review before its PR | **Authored and staged** (writer returned ~21:48Z): `tasks/readiness-2026-09-21/beta/file_export_to_v1.py` (SHA-256 `94f433cefcb0cacf6208d659f3f166cc528b7d543fc11f4b5f7a2b46a4b8b337`, 8,822 bytes; `parse_record`, `v1_response_from_parts`, `file_export_completeness`, CLI with `O_EXCL` 0o600 and a 16 MiB part bound; imports `COLUMNS`/`MAX_ROWS` from the consumer); `fixture_check.py` extended by insertion only (0 lines changed or deleted, 165 added; `--adapter-only`; SHA-256 `efe09f076abd82c81e1a11f45af5078505d7a1fd93e4fec57456ced01f5d1353`, 40,109 bytes); `--adapter-only` and `--v1-only` both exit 0, the latter byte-identical to the released file's own output; `ruff` and `py_compile` clean; `readout_v1.py` byte-identical to the release. Notes: `handbacks/cto/ADAPTER-NOTES-01.md` (`23cc69e5…`, 28,731 bytes). Review and PR follow in this record's PR |

### G1 access decision (file-download route) — recorded 2026-10-05 on the founder's adoption of D2

> **G1 access decision (file-download route), 2026-10-05.** The beta readout uses PostHog's supported HogQL file-download batch
> export (JSONLines) on project 117863 at the API host production actually uses — founder-stated **EU cloud**,
> `https://eu.posthog.com` (ingestion origin `https://eu.i.posthog.com`); **confirmation against the production environment
> values (`POSTHOG_HOST`, the frontend provider host) and the organisation's app URL is outstanding** and is the one condition
> on which this decision's G1 closure waits. Enablement: ticket 76581 resolved by PostHog support; validated by the completed
> three-row literal run `01a10d89-1ee8-0000-3e2c-9000712c9502` (count 3 = records_completed 3; one part, SHA-256
> `67bc4e91db4f1bdc31dd4ffc290efd1864d4babdd6c33bd1e45bfb3fa413c6a5`, 2,092 bytes, downloaded 20:52:57Z by the founder's
> operator on EU cloud, HTTP 302 → 200). Authorisation relied on: the founder's existing account authorisation and the
> `batch_export:read`/`write` scopes connected on 2026-09-30; **no new scope, plan purchase, plan change or PostHog charge is
> authorised**; any billing or pricing signal stops the run. Data scope: the released v1 projection over the three named
> events, the frozen eligible roster after exclusions, and an elapsed UTC half-open window — for the beta readout only.
> Operator: **O2, founder-operated** (D1), label registered in the exclusion closure before the first customer run; executive
> contexts receive counts, hashes, status and verdicts only. Private store: founder-side private directory under the custody
> convention (D3); repository hashes and counts only. The consumer input contract is fixed by **Option A** (D5) after the G3
> review (review 01: rendering accept; consumer-as-is reject; adapter authored); the released consumer is byte-unchanged. The
> first customer export runs on this route only; the `execute-sql` query route is a fallback requiring its own decision.
> Acceptance of the readout contract (revision 3) is recorded separately from this decision. Nothing in this decision admits
> capacity, invites a participant, infers consent or marks cohort reporting or beta admission complete.

### Reporting groups after this record

| Group | State | What settles it |
|---|---|---|
| G1 | **Decision recorded; closure pending the production-host confirmation** | Founder confirms the deployed `POSTHOG_HOST` / frontend host values and the app URL region |
| G2 | **Evidenced** for the synthetic literal route (Completed run; count 3 = records 3 = parsed 3; one part hash-verified; G3 review 01 rendering accept) | A customer-run receipt on the same rule, later |
| G3 | **Reviewed with a stated gap**; adapter authored under D5 | Independent review of the adapter and the D4 dry run; contract acceptance recorded |
| G4 | INCOMPLETE | Frozen roster, exclusions and control packet (founder, later gate) |
| G5 | 0/2 | Two actual weekly readouts after R4 entry |

Nothing here marks cohort reporting, beta admission or capacity complete or admitted.
