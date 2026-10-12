# Replay tool for the copilot-eval triage rule, generation-aware (2026-10-09)

`f_attribution.py` here (sha256 `22dd3061ece406135db34176e87ada12ace8907b1a4613ca22bf7753ff43a9fb`) is
the replay tool that `backend/evals/RUNBOOK.md` names for condition (3) of the triage rule for a red
copilot-eval run. It succeeds `../f-quote-containment-2026-10-01/f1-attribution-2026-10-02/f_attribution.py`
(sha256 `a88162d7…`). That copy is unchanged, because preregistrations and scope hashes pin it. Like its
predecessor, it is offline only: no provider call, no network, no database. Run it from `backend/` with the
provider keys unset (see its docstring).

## Why a successor

Since #1111 a question may run two generations: one private regeneration after an excerpt-only citation
mismatch or a retryable quotation. The runner retains each generation in
`tool_trace.generation_attempts`. The predecessor streamed the aggregate candidate into every generation,
which caused two problems:

- **A recovered row did not replay.** For a row whose first generation was withheld and whose second
  published, the replay withheld both and reported an UNEXPLAINED mismatch. The tool then exits 3, and
  condition (3) ("exit 0, 0 UNEXPLAINED") cannot be met for any report that holds such a row. The F-only
  rule has been in that state since #1111 merged.
- **An F-withheld first generation never triggered its retry**, because the predecessor let the
  decision F check through. It did that because the runs it was written for could predate F.

## What changed (the docstring lists it; nothing else changed)

1. Each replayed generation is served its own recorded tool results, deltas and provider controls. A
   report without `generation_attempts` (before #1111) replays the aggregate trace, as before. A replay
   that asks for more generations than the run recorded fails that generation.
2. The decision F check is observed, then enforced as in production, so the replay takes the run's
   generation path. When F withholds, the error event names no path, so the checked surfaces take their
   path from the checked call.
3. If a row's replayed withhold reasons (`replay_logged`) differ from the run's
   `tool_trace.withheld_reasons`, the row is not reproduced:
   - a published row counts as an UNEXPLAINED replay mismatch;
   - a withheld row is classified UNEXPLAINED.
   Exit 0 therefore means every recorded reason reproduced.
4. Self-test (`selftest.txt`, exit 0): the predecessor's cases still pass, with two adaptations. The enforced F check
   adds the production retry, so case 7's repair lookup is made once per generation. Four
   two-generation cases are added:
   - both generations withheld;
   - an unverified citation, then a quotation;
   - a record the replay does not reproduce;
   - a row that recovers on its second generation (the aggregate trace still cannot recover).
5. A run without a report is refused (exit 2). An empty list wrote a zero-row report and exited 0, which
   met condition (3) without replaying a row (Codex review on #1166). Added after the validation below,
   which ran the earlier revision (sha256 `43a7e863…`); it changes nothing for one or more reports.

## Validation on real reports (`replay-red-runs.txt`)

Both tools ran over the 13 retained reports of red runs on PRs that change no Copilot code, from 3 to 9
October. They ran on this branch, whose `copilot_service`, `copilot_tools` and `provenance_service` are
byte-identical to main's.

- **The 7 reports with `generation_attempts`.** The successor exits 0 on all 7. Every withheld row is
  "other reason", and its replayed reasons equal the recorded ones. The predecessor exits 3 on 3 of them,
  37700200842 (first attempt), 37943905552 and 37958886664 (first attempt), each because of a row that
  recovered on its second generation.
- **The 6 earlier reports.** The successor exits 3 on 5 of them, by design. These runs predate #1111's
  retry: main's code now regenerates where they did not, so the replay does not reproduce them. Condition
  (3) is about runs on current code, and every new report carries `generation_attempts`. The sixth
  (37102020155) reproduces: its only withheld excerpt was too short to earn a retry.

## Use in the triage rule

For each errored row in a red run, run the successor on the run's `copilot-eval.json`. The row is
reproduced when the tool exits 0 with 0 UNEXPLAINED and the row is classified with its recorded reason:
"other reason" whose `other_reason` equals `tool_trace.withheld_reasons`, or "F-withheld" with the row's
decision-F code. The remaining conditions are in the RUNBOOK.
