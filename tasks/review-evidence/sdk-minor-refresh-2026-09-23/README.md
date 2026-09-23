# SDK minor refresh (replaces Dependabot #950) — offline evidence, 2026-09-23

Replacement draft [#953](https://github.com/neilmac91/EarningsNerd/pull/953) for
[#950](https://github.com/neilmac91/EarningsNerd/pull/950) (source head
`8ae3ddda1eefadc2272b6b3ad5818856e5515f12`, base `ab7364dabf625b196f08ac608fefafe07d1515fc`).
Base main `ebdc4c44c5c6aa01c94587646a4c365f84fe26ec`; dependency commit
`31b88458ec19a2ff28f17a4c15a6c88868d8f403`. The dependency diff is byte-identical to #950's
three-file diff; the requirement files at #950's base and at this main are identical.

| Package | From | To | Where |
| --- | --- | --- | --- |
| `openai` | 3.15.0 | 3.16.2 | `backend/requirements.in` floor, `backend/requirements.txt` |
| `posthog` | 7.56.0 | 7.58.0 | `backend/requirements.in`, `backend/requirements.txt` |
| `anthropic` | 1.6.0 | 1.7.0 | `backend/requirements-eval.txt` (optional; never in the image) |

This is offline compatibility evidence. It is not live provider evidence, not E7/E8 or Fable
semantic acceptance, and not a quality claim.

## Lock and installs (Python 3.11.15)

- [lock-reproduction.diff.txt](lock-reproduction.diff.txt): isolated pip-tools 7.5.3 / pip 25.3.
  Seeded with main's lock and the exact new direct pins, the resolver changes only the `openai` and
  `posthog` lines. Every transitive pin (including `httpx2`/`httpcore2` 2.13.0) is unchanged.
  Recompiling from the committed lock reproduces it. Both diffs also show the environment's
  `--no-index` header annotation, which is not committed.
- [pip-check.txt](pip-check.txt): fresh runtime-only, runtime+dev (the CI gate set) and
  runtime+dev+eval venvs all report `No broken requirements found`.
- [freeze-runtime.txt](freeze-runtime.txt) equals the lock exactly; Anthropic is absent from it and
  from [freeze-gate.txt](freeze-gate.txt).
  [freeze-runtime-dev-eval.txt](freeze-runtime-dev-eval.txt) adds exactly `anthropic==1.7.0` and
  `docstring_parser==0.18.0`. The shared transport stays at the runtime pins because
  `requirements-eval.txt` keeps #949's `-c requirements.txt`. `backend/Dockerfile` installs only
  `requirements.txt`.
- [pip-audit.txt](pip-audit.txt): `pip-audit -r requirements.txt` (pinned dev tool) reports no known
  vulnerabilities.

## Backend gate on committed `31b8845`

[full-gate-tails.txt](full-gate-tails.txt), separate worktree, PostgreSQL 15.19 disposable cluster
with one database per concurrency lane and all four lane variables set:
`ruff check .` clean; `bandit -r app -ll` no medium/high; `python -m pytest`
**3497 passed, 2 deselected (performance marker), 0 skipped**; CI performance step 2 passed. The
existing post-pytest `_close_yahoo_client_sync` atexit logging noise follows the summary and does
not change the exit status.

## SDK call shapes (no network, no real events, no account deletion)

- OpenAI: existing tests drive the real SDK over `httpx2`/`httpx` `MockTransport`
  (`test_provider_resilience.py`, `test_attribution_verify.py`, `test_recovery_context.py`,
  `test_eval_measurement.py`). They cover streaming and non-streaming `chat.completions.create`,
  `response_format`, thinking `extra_body`, `stream_options` usage, status/transport error
  classification, partial-stream drops, owned stream close on cancel, tool-call fragment
  assembly and fallback. Results are in [focused-tests.txt](focused-tests.txt).
- PostHog: [posthog_shapes.py.txt](posthog_shapes.py.txt) replaces the consumer transports with
  recorders and makes `requests.Session.send` raise. It runs the app's exact shapes: both
  constructor forms, event-first `capture`, and the account-deletion all-keyword
  `capture(distinct_id=, event='$delete', properties=)` followed by `flush()`. The outputs under
  [7.58.0](posthog-shapes-7.58.0.txt) and [7.56.0](posthog-shapes-7.56.0.txt) deliver the same
  events, lane and consumer threads. 7.58.0's new `traces` option defaults to `None`.
- Anthropic: [anthropic_shapes.py.txt](anthropic_shapes.py.txt) drives the real
  `evals.judge._judge_via_anthropic` and `evals.models._call_anthropic` through `httpx2.MockTransport`,
  plus the real SDK error classes through `evals.runner._is_transient`
  ([1.7.0 app](anthropic-shapes-1.7.0-app.txt)). SDK-only reports for
  [1.7.0](anthropic-shapes-1.7.0-sdk.txt) and [1.6.0](anthropic-shapes-1.6.0-sdk.txt) are identical
  apart from the version. **Live Anthropic compatibility is unmeasured**; no Anthropic call or
  CLI judging was made.

## Independent review

Three lenses (correctness, rules-and-brief, tests-and-gates) with two refutation attempts per
candidate finding: no finding survived. The reviewer byte-compared installed SDK sources between the
old and new versions:
- OpenAI chat-completions, streaming, exceptions, models and types are identical. The changes are
  lazy `__getattr__` resource loading and a new `webhooks` property.
- PostHog adds only opt-in tracing, which stays off without a `traces` config.
- Anthropic's non-beta resources, exceptions and client are identical.

The reviewer found no concrete uncovered compatibility defect, so no regression test was added.

The review also reproduced a test-order leak that predates this change and does not depend on the
SDK versions: `test_ai_metrics.py` fails when it runs after `test_eval_attempt_diagnostics.py`,
whose `runpy` run of `evals.runner` sets `ai_metrics.set_trigger("eval")` and never resets it.
CI's file order hides it. This is out of scope here and has been queued as a separate task.

## Not measured here

The paid compatibility measurements did not run. A fresh balance readout through `deepseek-balance.yml`
and the manual `ci.yml` `workflow_dispatch` both require workflow dispatch, and this session's
GitHub integration was refused (`403 Resource not accessible by integration`). The latest existing
readout is run `35839909018` at 08:55Z (USD 66.21); it predates this work by over ten hours and is
not treated as the pre-spend balance. The PR's own `eval-baseline` skipped generation by its scope
filter (requirements-only), which is not compatibility evidence. The Copilot fidelity run (on ready)
is also outstanding. Live DeepSeek streaming/tool calls on 3.16.2 and real PostHog ingestion of
`$delete` remain unverified.
