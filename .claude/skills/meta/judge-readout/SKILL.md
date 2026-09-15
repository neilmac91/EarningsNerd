---
name: judge-readout
description: Produce the weekly strong-judge readout (W3-7) on this Mac from a Monday generation artifact, judging through the founder's Claude subscription; never generates, never emails without asking
version: 1.0.0
author: EarningsNerd
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /judge-readout — weekly strong-judge readout through the subscription

Run this in a fresh Claude Code chat opened on the EarningsNerd checkout. It turns the Monday
generation artifact (`data-quality-weekly.yml`, phase `generation`) into the judged weekly readout
by replaying each retained attempt through `evals.judge_readout`, which spawns `claude -p` with
the subscription login (no API key, no API credit). Nothing is generated here: the generator
credential is CI-only and this command never reads it.

Read `backend/evals/RUNBOOK.md` ("Weekly strong-judge measurement") before the first run.

## 1. Preconditions (check, do not assume)

```bash
claude -p --model claude-fable-5-1 --output-format json --tools "" "Reply with exactly: OK" | head -c 400
```
The reply must contain `"is_error":false`. If it says not logged in or invalid API key, the
standalone CLI needs its one-time `/login` in the app's Terminal pane (interactive `claude`,
`/login`, subscription option, then `/exit`). Do not use `--bare`: it disables subscription auth.

```bash
gh auth status && git -c core.fsmonitor=false status --short && git -c core.fsmonitor=false log --oneline -1
```
Use a backend virtual environment that matches `backend/requirements.txt`, and unset
`ANTHROPIC_API_KEY` in the shell so nothing can bill API credits.

## 2. Find and download the generation run

```bash
gh run list --workflow data-quality-weekly.yml --limit 6 --json databaseId,event,conclusion,createdAt,headSha
```
Pick the most recent scheduled run (or a `workflow_dispatch` run without a delivered readout).
Then:

```bash
gh run download <run_id> -n weekly-judged-readout-<run_id> -D /tmp/weekly-<run_id>
```
Confirm `report.json` has `"phase": "generation"`, 24 results and no `error` rows, and note its
`harness.source_sha` and `harness.golden_set_sha256`. The local checkout must carry the same
`backend/evals/golden_set.json` and `weekly_cohort.json` (the builder refuses otherwise); check out
`harness.source_sha` when in doubt. If generation was incomplete, record it in the ledger and stop:
a partial generation cannot become a complete readout.

## 3. Judge

From `backend/`, with the CI-parity environment (no real secret is needed for judging):

```bash
export SKIP_REDIS_INIT=true SECRET_KEY=local-judge-only-nonproduction-0123456789 \
  STRIPE_SECRET_KEY=sk_test_local_judge STRIPE_WEBHOOK_SECRET=whsec_local_judge \
  PWNED_PASSWORD_CHECK_ENABLED=false AI_FALLBACK_MODEL= AI_FALLBACK_BASE_URL= \
  OPENAI_API_KEY=local-judge-never-generates
unset ANTHROPIC_API_KEY
PYTHONPYCACHEPREFIX=$(mktemp -d) python -m evals.judge_readout /tmp/weekly-<run_id>/report.json --concurrency 2
```
Expect about 24 subscription calls, each carrying up to roughly 340,000 characters of retained
source, XBRL and summary; the run takes some minutes. Keep the terminal output. Do not raise the
judge input bounds or edit the golden set to make a verdict fit.

## 4. Report the result to the founder

Read `readout.md` and `readout.json` in the printed output directory and report: status, judged
count of 24, negative judgments, deterministic vetoes, the four dimension means, every error row
(for example an excerpt over the full-coverage bound), and the generation run, source SHA and
generator model. A partial readout is reported as partial. The readout never arms a flag; the
evidence-snap arm decision is the founder's and follows the wrong-snap rate engineering reports.

## 5. Record

Copy `readout.json` and `readout.md` into `tasks/review-evidence/w3-7/<YYYY-MM-DD>-run-<run_id>/`
and append the dated ledger entry in `tasks/todo.md` through an ordinary docs PR. Do not commit
`report.json` (it carries full excerpts) and do not change `baseline_scores.json` or the golden set.

## 6. Deliver (ask first)

Delivery re-sends the founder's data-quality email with the judged readout and retains it as an
artifact; it generates nothing. It is a live email action: ask the founder before dispatching.

```bash
gh workflow run data-quality-weekly.yml -f readout_b64="$(cat <output-dir>/readout.b64)"
```

## Boundaries

`--judge <other id>` exists only for an explicitly approved agreement check; its verdicts are
retained but produce no readout. No generation, no golden or baseline change, no flag change, no
email without a yes.
