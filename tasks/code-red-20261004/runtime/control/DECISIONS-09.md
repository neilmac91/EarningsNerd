# Decision record 09 — PR #1099 merged; delta review of `ad915c44` and its seven nits applied; closure 154; founder status update and masterplan next steps delivered (chief, 2026-10-05)

Recorded 2026-10-05T22:05:00Z by the chief (`https://claude.ai/code/session_01GWYV7WXWstgVGQG43YcSM8`, runtime-reported model
`claude-fable-5-1`). Context: record 08 merged to main as `eccf45a31a45b1b69d20a1a37111f4131b3f4b93` (PR #1099; GitHub `merged_at` 2026-10-05T21:59:56Z); this
branch was restarted from that main. Records only: no code, workflow, migration, cloud, IAM or production change; a
tasks-only merge runs no `deploy-backend` step that changes the service (the merge's CI on main is recorded below for completeness).

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
| Merge | squash `eccf45a31a45b1b69d20a1a37111f4131b3f4b93`, GitHub `merged_at` 2026-10-05T21:59:56Z; main CI: run 37379578901 on `eccf45a3` (tasks-only: `deploy-backend` detects no `backend/` change and skips) |

## Seven nits from the delta review — applied here

1. Stamp order at `6f5d07a2` (checkpoint header 19:31:58Z before closure 153's 19:31:59Z): moot at `ad915c44`; rule for the chief: take the header stamp after the last bound file is written.
2. Record 08 header: amendment lines added for 19:07:44Z (revision 2), by 19:31:58Z (founder instruction, ticket 76581, manifest 05, closure 153), 19:35:53Z (export outcome) and this record's edit.
3. Checkpoint hash-row description for record 08 extended to its later sections.
4. "19:3xZ" replaced by "19:32Z (run file recorded 19:32:44Z)" in record 08 and checkpoint decision 29; "nothing else called" replaced by "no other export tool called (`learn` ×2, `info` ×4 only)".
5. "Third delta" lowercased in the PR #1098 review record.
6. `APPOINTMENTS.json` `query_route_contract_draft_01` parentheses flattened (facts unchanged).
7. PR #1099 applied-findings list: "event-3 write time" dropped (no such finding; the text was unchanged); the dry-run item now states the clause was removed and the CEO's decision recorded in Next (4).

## Founder status update and masterplan next steps — delivered 19:58Z

Delivered in the session as requested ("after this work is done"): delivered outcomes, a refreshed wave table (R1–R5 and shared spend; counts, blockers recorded once, next deliverable with acceptance), actual spend, five masterplan steps in priority order with finite exits, and the five founder-only items. Nothing in it admits capacity, releases inputs, infers consent or marks cohort reporting complete; holds unchanged.

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

## Registration (closures 154–156)

`control/source-context-exclusion-154.json` (268 entries) resolves the record-08 delta reviewer's provisional label to its
launch-time identity (19:32Z). `-155.json` (270) registers the founder-operated Codex download worker (external, actual; request
20:52:57Z) and the single G3 reviewer (actual; launched 21:04Z). `-156.json` (274) registers the CTO adapter writer and the COO
operator-script writer (both launched 21:34Z; actual), the human operator role `founder-operator:readout-export-legs-01` (D1
option O2; registered before any customer run) and pre-registers this PR's proportionate review (`adapter-review-01`,
provisional; resolved in the next closure). The COO revision-3 author is the already-registered context of closure 152.

## Spend

0 DeepSeek calls; 0 active reservations; 0 ledger events. Headroom unchanged at USD 22.539628 conditional unreserved under the USD 25 authority.

## Founder instruction received 2026-10-05 ~20:17Z — recorded and executed within authority

| # | Instruction (intent) | Action by the chief | State |
|---|---|---|---|
| 0 | IAM bindings run (both commands clean); verify with the `logs-probe` | Read-only `ops.yml` `logs-probe` dispatched on `main` `c780228a` at 20:21:06Z (Ops run 37369180920) during GitHub's Actions runner incident | First dispatch (run 37369180920, job 111962125429) was cancelled by the platform after 15 minutes queued with no runner (20:22:12Z → 20:37:15Z; no step ran; no evidence). Second dispatch at 21:55:36Z after GitHub reported Actions operational: run 37379102331, job 111996067424, conclusion success; the probe step printed **`logs-probe: logging.read DENIED (rc=1)`** — `PERMISSION_DENIED: Permission denied for all log views. This command is authenticated as github-deployer@earnings-nerd.iam.gserviceaccount.com` (21:55:53Z). **Access is therefore NOT verified**: the bindings the founder reports as applied at ~20:17Z are not effective for this principal 98 minutes later (propagation is normally minutes). IAM state: authorized (record 08) → applied per the founder's statement → **verified DENIED**. The chief makes no IAM change; the founder is asked to run the read-only policy check in the morning report |
| 1a | Give the exact authenticated download link or navigation for the existing export part; do not repeat the export | PostHog documentation (two read-only `docs-search` calls): file-download exports are API-only; the run's part is fetched by an authenticated GET on the US-cloud private host with a `batch_export:read` personal API key; both URL forms (part path from the connector's command description; run-level `download/` from the API reference) given to the founder at ~20:24Z; the key and redirect URL are never written anywhere | Awaiting the founder's file |
| 1b | File-download route selected; revise the draft for that route; present only the necessary founder decisions with recommended answers; no competing routes | Same registered COO context (closure 152) resumed on manifest `COO-FILE-ROUTE-REVISION-06` (`a73d0066…`, 7,112 bytes; nine input hashes; no connector call; staged outside the repository) | **Delivered** ~20:32Z: revision 3 of `handbacks/coo/QUERY-ROUTE-READOUT-CONTRACT-DRAFT-01.md` (as placed `ad599074e6f27149b6bfb736fccdb45014d1bdc411a2b087165a23d09e9b16dd`, 47,321 bytes, after one chief sanitisation of a session-local path; worker's staged `afe6b59a…`, 47,331 bytes) and `handbacks/coo/FOUNDER-DECISIONS-FILE-ROUTE.md` (`7bfe1e63c0b56ffac9bced4161df747ed711e162274e1788571980f854fa906c`, 14,894 bytes); 9 / 9 inputs hash-verified; EU host carried as the founder's stated assumption; manifest 7,123 bytes (the dispatch message said 7,112 characters; hash controlling) |
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
