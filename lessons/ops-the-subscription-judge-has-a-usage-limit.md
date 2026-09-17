# The subscription judge has a usage limit; a 70-verdict measurement can exhaust it mid-run

Date: 2026-09-17   Area: ops

**Context**: The strong judge runs on the founder's Claude subscription (`cli:claude-fable-5-1`,
`evals.judge_report` / `evals.judge_readout`). On 2026-09-17, after three 70-attempt judge runs in
one day, the CLI began returning exit 1 with an empty stderr on every call. The JSON body carried
the reason: "You've reached your Fable limit." The failure first appeared as the last two attempts
of one run (MELI, the largest excerpt) and then as all seventy attempts of the next, which produced
a judged artifact with zero usable verdicts.

**Rule**: Probe the judge before starting a run that needs dozens of verdicts
(`claude -p --model <judge> --output-format json …` and check `is_error` is false, not just the exit
code), and read the `result` field on failure — the limit message lives there, not in stderr. Treat a
run whose attempts all carry `claude CLI exit 1` as an exhausted subscription, not a code fault; the
retained artifact is fine and can be judged again after the limit resets. Never substitute a
different judge model to get past it: verdicts from two judges are not comparable, and the readout
contract pins the judge identity for exactly this reason. Quote denominators from complete verdicts
only (`judged_summary.judged`), never from the attempt count.

**Evidence**: the 2026-09-17 probe (`is_error: true`, Fable limit message) after the `o` run-2 and
control run-2 judge attempts; `backend/evals/judge.py::_judge_via_cli`;
`backend/evals/judge_report.py` (errors are counted, never silently dropped).
