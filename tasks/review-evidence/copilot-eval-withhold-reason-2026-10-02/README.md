# copilot-eval names the publication-withhold reason: offline evidence

This is R1 option (b) plus the triage rule, approved by the founder on 2026-10-02 at 13:10Z ("Go with your recommendation on all open points"; recorded in `tasks/pr-disposition-2026-09-30.md`, log entry 13:10Z). It is diagnostic only. Acceptance, error counting, thresholds and the exit code are unchanged. Everything here is offline: no provider calls and no spend.

Branch `claude/copilot-eval-withhold-reason`, on main `06ad809a` (main `a541c3c8` is merged in after these commits):

| Commit | Content |
| --- | --- |
| `cf2dedad` | runner capture, label and markdown verdict; the job-summary step; tests |
| `f311c87a` | RUNBOOK: the reason field and the triage rule |
| `49677945` | evidence (first version, capture as a handler) |
| `ee5cedb4` | the capture becomes a logger filter, so `runner.log` keeps the service's lines (review blocker); regression test |
| (after `ee5cedb4`) | RUNBOOK wording (logger filter; per-row verdict column; approval ledger path), then this evidence regenerated on `ee5cedb4` |

## Before and after

When the service withholds a candidate at the publication boundary, it logs the application-owned reason and yields only `_PUBLICATION_ERROR` (`copilot_service.py:1830-1833`).

| | Before | After |
| --- | --- | --- |
| Row error | `{'type': 'ValueError', 'stage': 'answer_or_score'}` | the same, plus `withheld_reason` (also kept in `tool_trace.withheld_reasons`) |
| `validate_report` | `operationally incomplete attempt` | `publication withheld: <reason>`. A row with no captured reason keeps the generic label. |
| `copilot-eval.md` verdict | the raw dict | the same label |
| Run page | nothing | `copilot-eval.md` in the job summary, written by an `always()` step that skips cleanly when no report exists |
| `summary.errors`, `failures` non-empty, `accepted`, exit code | | unchanged |

## Design choice

- **Capture: a filter on the `copilot_service` logger, scoped to one attempt.**
  - It keeps only records whose argument is an `_UnpublishableAnswer`. It matches on that type, not on the message text.
  - It returns `True` for every record, so the service's log output is unchanged.
  - Why not a handler (the first version, `49677945`): the copilot-eval job sets no root handler, so the service's warnings and `logger.exception` tracebacks reach stderr, which the job tees into `runner.log`, only through `logging.lastResort`. That fallback runs only when no handler is on the logger's path, so an added handler silenced the withhold line, the uncited-figure and misplaced-marker telemetry, and the stream-failure traceback for the whole attempt. Both independent reviews found this; pytest attaches root handlers, so the suite could not see it until the regression test below emptied them.
  - That catches every publication-boundary reason: decision F (`Unsupported prose quotation: …`) and all the others (`Invalid citation declaration`, `Missing citation envelope`, `Unverified or ambiguous referenced citation` from the whole-excerpt and section-label checks, the not-disclosed envelope).
  - The alternative was to wrap `_withhold_unsupported_quotations`. It was rejected because it sees F only.
- **Product code is unchanged.** `git diff 06ad809a..HEAD -- backend/app` is empty. The replay below reports the service's sha256 as `008ca638…`, which is main's. SSE events and the rule-6 locked contract tests are untouched.
- **Attempt scope.**
  - `run()` awaits one attempt at a time. The existing observer patches a module attribute, so attempts cannot overlap.
  - The filter is attached for the attempt and removed afterwards.
  - A `ContextVar` check also ignores any record logged under another task's context, or from a thread the attempt did not start. `asyncio.to_thread` carries the attempt's context, so the attempt's own thread work still counts.
  - A reason that is not captured leaves the generic label. It never produces a pass.
- **Workflow.** The triggers, `if` condition, secrets and cost are unchanged. The shape test now locks the triggers to `pull_request` only.

## Tests (`backend/tests/unit/test_copilot_gate.py`)

| Test | What it proves |
| --- | --- |
| `test_withheld_rows_name_their_own_reason_and_still_fail_the_run` | End to end through `main()`, the real `run()`, `_answer` and service, with a scripted provider and a passing scorer: row 0 (F) and row 1 (`Invalid citation declaration`) carry their own reasons, rows 2–17 carry none, `errors` is 2, `accepted` is False, the **exit code is 1**, and the markdown verdicts show the labels |
| `test_withheld_capture_keeps_other_attempts_records_off_the_row` | Two overlapping captures: another task's record and a foreign thread's record are ignored, a `to_thread` record is kept, and no filter is left behind |
| `test_withheld_capture_keeps_service_lines_in_runner_log` | With the root logger's handlers emptied (the job's setup), two attempts through `_answer` and the real service: an F withhold and a provider exception. The F reason is captured, and the withhold line and the `Copilot answer_filing_question failed` traceback still reach stderr. It fails on `49677945` (stderr empty) and passes with the filter |
| `test_withheld_attempt_is_named_and_remains_a_failure` | The label for F, for a non-F reason, and for an uncaptured or malformed reason (the generic label); always exactly one failure |
| `test_attempt_trace_retains_candidate_and_closes_provider` (extended) | The real service's non-F withholds (`Incomplete citation array`, `Missing citation envelope`) are captured; a provider error and a cancellation are not |
| `test_human_readable_report_preserves_failures_counts_and_json` (extended) | The markdown verdict shows the label |
| `test_workflow_is_explicit_same_repo_ready_full_cohort_and_always_artifacts` (extended) | The summary step is `always()`, comes after the run and has no `env`; the triggers are `pull_request` only; the exact step, run under bash `-eo pipefail`, appends the report and exits 0 when the report is missing |

## Offline demonstration on retained red runs (`replay_withheld_reasons.py`)

The script replays every errored row's retained candidate deltas and recorded tool results through the patched runner's own `_answer` and the real service. It then compares the captured reasons, in row order, with the run's `runner.log` withhold lines; attempts are sequential, so the k-th line belongs to the k-th withheld row. Finally it relabels the retained report.

It ran on tree `ee5cedb4`, clean. The output is `replay-withheld-reasons.json` (`"result": "PASS"`). The first three runs give byte-identical `labelled-<run>.md` files to the earlier run on `f311c87a`. The script puts a `NullHandler` on the root logger, so it prints nothing; the `runner.log` output is covered by the regression test and the probe below.

| Run | Row | Captured reason (= `runner.log` line) | F? |
| --- | --- | --- | --- |
| 37003942265 (A1) | ASML sales-net-income d0 | `Unsupported prose quotation: quotation_not_in_source` | yes |
| 37004589548 (C1) | BABA native-revenue-2026 d2 | `Invalid citation declaration` | **no** |
| 37004589548 (C1) | ASML d0 | `Unsupported prose quotation: quotation_not_in_source` | yes |
| 37004589548 (C1) | ASML d1, d2 | `Unsupported prose quotation: elided_quotation` | yes |
| 37005546506 (C2) | BABA viewed-native-revenue-2025 d1 | `Unsupported prose quotation: elided_quotation` | yes |
| 37005546506 (C2) | ASML d0, d2 | `Unsupported prose quotation: quotation_not_in_source` | yes |
| 37029156902 (G stage 2 B1) | ASML d1, d2 | `Unsupported prose quotation: quotation_not_in_source` | yes |
| 37029964566 (G stage 2 B2) | BABA viewed-native-revenue-2025 d1 | `Unsupported prose quotation: elided_quotation` | yes |
| 37029964566 (G stage 2 B2) | ASML d2 | `Unsupported prose quotation: quotation_not_in_source` | yes |

- Across all 12 rows:
  - every replay ends in the same retained service event;
  - no lookup went unserved;
  - the captured sequence equals the log sequence in all 5 runs.
- Each run keeps its retained error count (1, 4, 3, 2, 2), `accepted` False and exit code 1.
- `labelled-<run>.md` holds the relabelled report. `labelled-vs-retained.diff.txt` shows that only the `Failures:` line and the errored rows' verdicts change.
- Under the triage rule, A1, C2, B1 and B2 would pass condition (1), every errored row being F. C1 fails it because of BABA d2. Arms B and C ran different prompts (G's experiment arms, never merged), so they show the labels, not a triage outcome.

**`runner.log` output (reviewer probe, not committed).** A plain-Python run of the real `main()` (no pytest, so no root handler, as in the job) with an F withhold, a non-F withhold and a provider crash prints the same 11 stderr lines on main `06ad809a` and on `ee5cedb4`, apart from one runner line number in a traceback frame; on `49677945` it printed none. Exit code, errors and `accepted` are the same on all three.

## Mutations (`mutate.py`, output in `mutations.txt` and `mutations.json`)

These ran on tree `ee5cedb4`. The unmutated baseline is 76 passed. Each mutation turns `test_copilot_gate.py` red, and the tree is restored clean after each one.

| Mutation | Failing tests |
| --- | --- |
| M1: the capture records nothing | 5 |
| M2: the reason is not copied to the row error | 1 |
| M3: a named withhold counts as success | 3 (including the exit-1 end-to-end test) |
| M4: no attempt-context check | 1 |
| M5: the filter is left on the service logger | 1 |
| M6: the generic label is kept | 4 |
| M7: the markdown verdict shows the raw error | 2 |
| M8: the summary step is not `always()` | 1 |
| M9: the summary step fails when the report is missing | 1 |
| M10: a `workflow_dispatch` trigger is added | 1 |
| M11: the filter drops the record | 1 (only `test_withheld_capture_keeps_service_lines_in_runner_log`) |
| M12: the capture is a handler again (the `49677945` code) | 1 (the same test) |

## Gate

The full backend gate, from `backend/` with provider keys unset: `ruff check . && bandit -q -r app -ll && python -m pytest -q -p no:cacheprovider`.

- On `f311c87a` (handler version): ruff and bandit clean, **5546 passed**, 39 skipped, 2 deselected, exit 0. `test_copilot_gate.py` grew from 67 to 75 collected items (67 on main `06ad809a`), so main's count is 5538, which matches the 5538 an earlier gate log recorded.
- The filter fix adds one test: `test_copilot_gate.py` collects 76. The full gate on the final head, after merging main, is reported with the branch.
- After the run, the interpreter prints a "Logging error" from the existing `companies._close_yahoo_client_sync` atexit hook. That hook predates this change and appears in earlier gate logs too.
- The evidence commit adds only files under this folder. Its gate result is reported with the branch, not here.

The logs are kept in the session scratch and are not committed.

## Not done

- **No live run.** The first live exercise will be the next copilot-eval run on a ready PR. A PR carrying this change matches `backend/evals/*`, so it pays one `eval-baseline` run per push as well as `copilot-eval`.
