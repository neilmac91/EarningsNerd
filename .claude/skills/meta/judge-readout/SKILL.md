---
name: judge-readout
description: Produce the weekly strong-judge readout (W3-7) on this Mac from a Monday generation artifact, judging through the founder's Claude subscription; never generates, never emails without asking
version: 1.0.0
author: EarningsNerd
disable-model-invocation: true
allowed-tools: Bash, Read
---

# /judge-readout — weekly strong-judge readout through the subscription

Run this in a fresh Claude Code chat opened on an EarningsNerd checkout that sits outside any
iCloud-synced folder (`lessons/ops-keep-worktrees-out-of-icloud-documents.md`; the current
handover names the clone and virtual environment to use). It turns the Monday
generation artifact (`data-quality-weekly.yml`, phase `generation`) into the judged weekly readout
by replaying each retained attempt through `evals.judge_readout`, which spawns `claude -p` with
the subscription login (no API key, no API credit). Nothing is generated here: the generator
credential is CI-only and this command never reads it.

Read `backend/evals/RUNBOOK.md` ("Weekly strong-judge measurement") before the first run.

## 1. Preconditions (check, do not assume)

First remove every credential through which `claude -p` could bill something other than the
subscription, then probe the subscription login itself (the JSON is about 1.8 KB and `is_error`
sits near its end, so extract it rather than truncating the output):

```bash
unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX CLAUDE_CODE_USE_FOUNDRY
claude -p --model claude-fable-5-1 --output-format json --tools "" "Reply with exactly: OK" < /dev/null | grep -oE '"(is_error|result)":[^,]*'
```
Expect `"is_error":false` and `"result":"OK"`. If the reply says not logged in or invalid API key,
the standalone CLI needs its one-time `/login` in the app's Terminal pane (interactive `claude`,
`/login`, subscription option, then `/exit`). Do not use `--bare`: it disables subscription auth.
`evals.judge_readout` strips the same variables from every judge subprocess, so the probe and the
run authenticate the same way.

```bash
gh auth status && git -c core.fsmonitor=false status --short && git -c core.fsmonitor=false log --oneline -1
```
Use a backend virtual environment that matches `backend/requirements.txt`.

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
OUT=/tmp/weekly-<run_id>/judged
PYTHONPYCACHEPREFIX=$(mktemp -d) nohup python -m evals.judge_readout /tmp/weekly-<run_id>/report.json \
  --output-dir "$OUT" --concurrency 2 > /tmp/weekly-<run_id>/judge.log 2>&1 &
```
Expect about 24 subscription calls, each carrying up to roughly 340,000 characters of retained
source, XBRL and summary, with a 300-second bound per call; the run takes minutes and writes its
outputs only at the end, which is why it runs detached from the tool's own timeout. Wait for
`Outputs:` in `judge.log` (poll the file; do not re-run while `pgrep -f evals.judge_readout`
still finds it), then keep that log. A partial readout exits 1 by design (for example MELI's
attempts over the excerpt bound); do not re-run for that reason. Do not raise the judge input
bounds or edit the golden set to make a verdict fit.

## 4. Report the result to the founder

Read `readout.md` and `readout.json` in the printed output directory and report: status, judged
count of 24, negative judgments, deterministic vetoes, the four dimension means, every error row
(for example an excerpt over the full-coverage bound), and the generation run, source SHA and
generator model. A partial readout is reported as partial. The readout never arms a flag; the
evidence-snap arm decision is the founder's and follows the wrong-snap rate engineering reports.

## 5. Record

Copy `readout.json` and `readout.md` into `tasks/review-evidence/w3-7/<YYYY-MM-DD>-run-<run_id>/`
and append the dated ledger entry in `tasks/todo.md` through an ordinary docs PR. This copy is the
only durable record of the per-attempt verdicts: the readout links the generation run, whose
artifact holds unjudged attempts, and a delivery dispatch retains only the bounded readout. Do not
commit `report.json` (it carries full excerpts) and do not change `baseline_scores.json` or the
golden set.

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
