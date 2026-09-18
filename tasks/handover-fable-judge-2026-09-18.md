# Handover: judge two retained artifacts on Fable — 2026-09-18

You have something this session does not: **Fable capacity**. The strong judge that gates AI quality
here runs on the founder's Claude subscription as `cli:claude-fable-5-1`, and that quota has been
exhausted since 2026-09-17. Two measurements are blocked on it and on nothing else. Everything you
need is already generated and retained; you are not generating anything, changing any code, or
touching production.

Read this whole file before running anything. It is short on purpose.

## Why these two measurements matter

The product's quality problem is summaries that state a *cause* the filing never gives ("revenue rose,
driven by strong demand"). Two things were built against it: a prompt condition released as
`summary-2026-09-o`, and a code gate that finds such clauses and asks a model whether the filing
states them. Both were measured with the strong judge, and both measurements are currently missing a
piece that only Fable can supply.

1. **The `o` release was credited with an improvement that one run cannot support.** Two `o` runs and
   one control run were judged on Fable: negatives 54% and 66% of attempts for `o`, 81% for the
   control. The candidate's own spread is nearly as wide as its gap to the control, so a second
   control was generated on 2026-09-17 and has **never been judged** — the quota died first. Judging
   it closes the comparison.
2. **The verifier's first measurement sits in the wrong judge frame.** It was judged on Opus 5
   because Fable was unavailable, and its numbers are therefore deliberately not compared with the
   Fable-judged runs. Re-judging it on Fable puts it in the contract frame and, as a by-product,
   gives the first Fable-versus-Opus agreement check this project has ever had.

## The rule that matters most

**Never substitute a different judge model to get past a limit.** Verdicts from two judges are not
comparable, and every cross-run number in this repository assumes one judge. If Fable is unavailable
to you too, stop and say so — a missing measurement is fine, a measurement in the wrong frame is not.
(`lessons/ops-the-subscription-judge-has-a-usage-limit.md`.)

## Before you start: probe the quota

An exhausted subscription looks like exit code 1 with an empty stderr; the reason is only in the JSON
body. Check `is_error` is false, not the exit code:

```bash
claude -p --model claude-fable-5-1 --output-format json --tools "" --strict-mcp-config --no-session-persistence --system-prompt "Answer in one word." "Reply with exactly: OK"
```

If the result says "You've reached your Fable limit", stop here and report that. Do not switch models.

## Setup

```bash
git clone https://github.com/neilmac91/EarningsNerd.git earningsnerd-judge && cd earningsnerd-judge
python3 -m venv .venv && ./.venv/bin/pip install -q -r backend/requirements.txt -r backend/requirements-eval.txt
```

Keep the checkout **outside** any iCloud-synced folder such as `~/Documents`; file-provider stalls
there make every command take minutes (`lessons/ops-keep-worktrees-out-of-icloud-documents.md`).

## Task A (required): judge the second control run

```bash
gh run download 35240242526 --repo neilmac91/EarningsNerd -n eval-report-35240242526 -D /tmp/n2
cd backend && SKIP_REDIS_INIT=true SECRET_KEY=offline-judge-run-not-a-real-secret-key \
  ../.venv/bin/python -m evals.judge_report /tmp/n2/eval_*.json --output-dir /tmp/judged-n2 --concurrency 2
```

Roughly 25 minutes for 70 attempts. `--judge` defaults to the contract judge; do not pass it.

## Task B (only if Task A finished and the quota holds): re-judge the verification run

```bash
gh run download 35280067189 --repo neilmac91/EarningsNerd -n eval-report-35280067189 -D /tmp/verify
cd backend && SKIP_REDIS_INIT=true SECRET_KEY=offline-judge-run-not-a-real-secret-key \
  ../.venv/bin/python -m evals.judge_report /tmp/verify/eval_*.json --output-dir /tmp/judged-verify-fable --concurrency 2
```

## What the output means

`judged.md` is the human-readable table; `judged.json` holds every verdict. Quote denominators from
`judged_summary.judged` — the count of **complete** verdicts — never from the attempt count. An
attempt whose verdict carries `claude CLI exit 1` is an exhausted subscription, not a content result;
if several appear, the quota died mid-run and the numbers are partial. Say so plainly.

Gate codes under judge contract version 2: G2 fabricated comparatives, G3 hallucinated facts,
**G4 unsupported cause**, **G5 basis mismatch**. G4 is the one this whole line of work is about.

## Report back on the pull request

Post one comment per task on the pull request named in your prompt. Keep it plain text and factual:

```
Task A — second n control, judged cli:claude-fable-5-1, contract v2
judged/judgeable: __ / 70   (complete verdicts only)
negative judgments: __
G2 __ | G3 __ | G4 __ | G5 __
mean faithfulness / insight / clarity / specificity: __ / __ / __ / __
errors and their reason (verbatim), or "none": __
```

Attach nothing and paste no excerpts of filing text. If you also ran Task B, use the same shape with
its own heading. If either task could not run, post a comment saying which and why — a clear negative
result is a complete answer.

## Boundaries — do not cross these

- **Do not** merge, close or approve any pull request, and do not push to `main`.
- **Do not** change any code, prompt, flag or workflow. You are judging retained artifacts only.
- **Do not** turn on `AI_ATTRIBUTION_GATE` or `AI_ATTRIBUTION_VERIFY`, and do not run the pregenerate
  job, the drain, or any generation. Nothing you do should reach production.
- **Do not** run an eval that generates summaries — that spends the provider key and is not your task.
- **Do not** read, print, copy or extract any API key or secret. The `SECRET_KEY` above is a throwaway
  string for offline settings validation, not a credential.
- **Do not** re-judge with a different model to work around a limit, for the reason given above.

## If something does not fit this description

The repository moves. If a command fails because the code has changed, read the failure, say what you
found, and stop rather than adapting the measurement to make it pass. The value of these numbers is
entirely in their being produced the same way as the ones they will be compared with.

## Background, if you want it

- `tasks/review-evidence/pr805-path/variance-correction-2026-09-17.md` — why the second control exists.
- `tasks/review-evidence/pr805-path/verifier-first-measurement-2026-09-18.md` — what the verifier did
  and why its frame is wrong.
- `backend/evals/RUNBOOK.md`, section "Judging a pull request's eval artifact" — the judge tooling.
- `lessons/evals-accept-a-prompt-change-on-two-runs-not-one.md` — why one run is never an effect size.
