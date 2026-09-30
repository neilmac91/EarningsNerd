# Native-evidence delivery adapter (route `claude_code_cli_print`)

**Status:** engineering candidate (`schema_version` 1; kinds `e7_native_delivery_request`,
`e7_native_delivery_receipt`, `e7_native_delivery_validation`). Non-admitting. It has no readiness,
protocol, executor or decision call site, dispatches nothing on import, and cannot admit evidence.
Its first live use is the bounded probe in `backend/scripts/native_delivery_probe.py`, which has not
been run.

`backend/evals/acceptance_source_review_delivery.py` fills the gap the
[execution-custody slice](source-review-execution.md) left at step 3: `reserve_attempt` retains the
exact prompt and `settle_attempt` accepts caller-supplied output, but nothing carried the prompt to a
consumer. This adapter carries **exactly the reserved `prompt.bin` bytes** to one route — the Claude
Code CLI in print mode (`claude -p`, prompt on standard input, `stream-json` output, no tools) —
retains everything it sent and received in an immutable delivery ledger, and proposes a settlement
for the existing journal. V1 prompt rendering, the eligible-receipt key set, journal retry/redraw
rules and the graph validator are unchanged; no owner module was edited.

## What stays separate

| | What it is | How the receipt records it |
| --- | --- | --- |
| **Custody** | Native evidence members the caller supplies (bytes, label, `required`) | Each member gets one disposition against the delivered bytes: `delivered_inline` only when its exact bytes occur contiguously inside the reserved prompt; `retained_not_delivered` otherwise; `indeterminate` below 64 bytes. Compared by bytes, never by hash, so compact text or a manifest pointer cannot stand in for another member. `complete_native_delivery` is `null` (no members), `true` (every required member inline) or `false`. |
| **Delivery** | The bytes written to the route process's standard input | `stdin.sha256` equals the journal row's `prompt_sha256`; `stdin.bin` is retained. This is process-level delivery only: `provider_delivery_verified` is always `false`, usage is `usage_is_route_reported_estimate`. |
| **Output** | The `result` text of the stream, strict UTF-8, non-empty | Retained by hash as `output`, proposed as the settlement artifact; the whole raw stream and stderr are retained as `stdout.raw`/`stderr.raw`. |

The route adds one fixed system prompt (`ROUTE_SYSTEM_PROMPT`, recorded by SHA-256 and length; the
V1 template is never passed twice) and whatever the CLI itself wraps around a request. Those
wrapper tokens are unknown and are not claimed.

## Pre-dispatch refusals (no process, no ledger entry)

All raise `ValueError` before anything is written (at most the pinned executable's `--version` has
run): prompt not strict UTF-8 or larger than the operator's `max_stdin_bytes` (itself capped at the
documented 10 MB stdin limit); the journal's pending row is not this reservation, has an uncommitted
settlement intent, or its prompt differs from the supplied bytes; the frozen role contract does not
name provider `anthropic-claude-code-cli` or has no declared `provider_version`; a `required` native
member is not inside the prompt, or a member differs from its `expected_members` identity;
`engineering_probe` against a non-synthetic accession; a passthrough variable outside the proxy/CA
set, a missing `HOME`, CLI settings files that declare model, routing, hook, env, statusline, MCP or
`enabledPlugins` overrides, or a HOME carrying user-level context the CLI injects regardless of cwd
(`~/.claude/CLAUDE.md`, `~/.claude/rules`, installed plugins); `delivery_root` inside the repository
or under any `CLAUDE.md`/`.claude`/`.git` ancestor, on a volume without hard links, or already holding
a ledger for this reservation; and a pinned executable whose `--version` does not fullmatch the
contract's `provider_version` (drift). The version pin lives in the journal contract, never in code.

## Dispatch and the ledger

The child environment is an allow-list (`SAFE_ENV` plus declared proxy/CA names); receipts record
variable **names** only, the executable home-relatively (`~/…`) and the working directory as `cwd`.
The ledger directory `<delivery_root>/<reservation_id>/` is created exclusively **before** the
child starts and is the redispatch lock: a second call for the same reservation into the same
delivery root, including after an `unknown` outcome, is refused. The journal keeps no dispatch
memory, so the lock's scope is the delivery root and **one delivery root per journal** is the
operator rule (the probe manifest pins one). `request.json` and `stdin.bin` are published
create-once before the spawn; `stdout.raw`/`stderr.raw` are file-backed so partial output survives a
timeout; the child runs in its own session in an empty `cwd` and its process group is terminated
(SIGTERM, then SIGKILL) on timeout. `receipt.json` is written after the process ends; if the
dispatch raises before that (a spawn error, for instance) the ledger stays **incomplete** with no
receipt, still blocks redispatch, and the operator settles or retires through the journal after
inspection. The raw streams are retained unredacted for local custody: before any ledger file leaves
the machine, scan it for absolute home paths, `sk-ant-`/bearer/OAuth token shapes, e-mail addresses
and proxy userinfo; the receipt hashes remain the custody proof. argv is fixed:

```
<cli> -p --output-format stream-json --verbose --model <contract model> --system-prompt <ROUTE_SYSTEM_PROMPT>
      --tools "" --strict-mcp-config --no-session-persistence --permission-prompts none [--max-budget-usd N]
```

## Outcome classification (pure, re-runnable on the retained stream)

Precedence: `unknown` > `compacted` > `truncated` > `failed` > `complete`.

- `unknown`: the process timed out or the stream has no `result` event. No settlement proposal;
  the reservation stays pending, `redispatch_permitted` is `false`, and the operator settles or
  retires it through the journal after inspecting the ledger.
- `compacted`: a `system`/`compact_boundary` event was observed.
- `truncated`: any assistant `stop_reason` is `max_tokens`.
- `failed`: any of — non-zero exit; `is_error` not `false`; result `subtype` not `success`;
  `num_turns` absent or not 1; more than one result event (`result_ambiguous`); unparseable lines
  (including NaN/Infinity constants and pathologically nested lines); init event absent, tools not
  `[]`, model absent or not the contract model, or a reported CLI version that differs; no assistant
  event; an assistant message without a string id (`stream_schema:message_id`) or more than one
  message id; any assistant `stop_reason` absent (`stop_reason_unobserved`) or not `end_turn`; a
  `tool_use` block; empty, non-text or non-encodable `result`; result text not equal to the
  assistant text blocks.
- `complete`: none of the above, which requires an **observed** `end_turn`.

Every reason is recorded verbatim, so a `failed:stream_schema/*` outcome on a real run is
diagnosable from `stdout.raw` without a second call; `classify_stream` can be re-applied to that
retained stream after a classifier revision (`classifier_version` is in the receipt).

## Settlement and validation

`settle_delivery` rebuilds the classification from the retained files (never from memory) and calls
`settle_attempt`: `complete` → `eligible` with the exact V1 eleven-key receipt derived from the
journal binding and pending row; `truncated`/`compacted`/`failed` → the same status with the delivery
receipt as the journal receipt and the output bytes (if any) as the artifact; `unknown` is refused.

Both `settle_delivery` and `validate_delivery_binding` bind the ledger to the journal first: the
receipt's `route`, `route_provider`, `model_requested` and `provider_version` must equal the frozen
contract, and the classification is re-derived with the **contract's** model and version, never the
ledger's own, so a rewritten ledger cannot re-label a model-mismatch stream. `validate_delivery_binding`
then checks ledger file hashes against the receipt and the row identity, and enforces the status
matrix: `eligible` only for `complete` with matching artifact and a receipt equal to the derived V1
receipt; `truncated`/`compacted` one-to-one with the delivered output and the retained delivery
receipt; `failed` one-to-one, or an operator `retired`; `unknown` admits a still-pending row or an
operator `retired`/`failed`, never `eligible`. An operator settlement (any `retired`, or anything
after `unknown`) is reported as `operator_settled_after_outcome` and is not required to carry the
output bytes. Supplying the member bytes re-derives dispositions from `stdin.bin`.

## Limits

The receipt and validation carry these strings with every attestation flag `false`:

1. Delivery is process-level: the bytes written to the route's standard input equal the reserved prompt; provider ingestion, model attention and the CLI's own wrapper tokens are not verified.
2. Stream finish metadata (stop_reason, usage, subtype, compaction) is recorded as the route reported it; a required field that is absent classifies the attempt as failed, never complete.
3. A native member counts as delivered only when its exact bytes occur inside the reserved prompt; attachments, tool-mediated file reads and binary modalities are unsupported by this route, so members above the operator stdin cap are retained_not_delivered.
4. Usage and cost are route-reported estimates, not billing; the journal context_id is operator-chosen and the CLI session_id is retained only as route evidence.
5. No source review, source-role readiness, E7 coverage_status or E7 admission is attested; an unknown outcome stays pending with no automatic retirement or redispatch.
6. The redispatch lock is the per-delivery-root ledger directory and the journal keeps no dispatch memory, so one delivery root per journal is an operator rule; user-level Claude memory, rules, plugins and hook settings are excluded only by the pre-dispatch home observation, and the raw streams are retained unredacted for local custody.

Consequences stated plainly: through this route the complete H20 native bundle cannot be
`complete_native_delivery: true` — `source-view.json` (26,445,997 bytes) exceeds the documented 10 MB
stdin cap and `reader.txt` (277,045 bytes) exceeds any conservative probe cap, so both are
`retained_not_delivered` by construction. The stream shapes the classifier expects (assistant
`stop_reason`, result `subtype` names, `compact_boundary`) are documentation- and precedent-derived
and unmeasured until the probe runs; the probe's retained `stdout.raw` is the first real fixture.
Full L004 controls remain absent; nothing here confers source-role readiness.

## API

```python
from evals.acceptance_source_review_delivery import (
    deliver_reserved_attempt, settle_delivery, validate_delivery_binding, native_member_dispositions,
)

outcome = deliver_reserved_attempt(
    journal_root, delivery_root, reservation_id=reservation["reservation_id"],
    prompt_bytes=reservation["prompt_bytes"], cli_path="/opt/homebrew/bin/claude", environment=dict(os.environ),
    limits={"max_stdin_bytes": 65536, "timeout_seconds": 300, "max_budget_usd": None},
    native_members=[{"label": "primary", "bytes": primary, "required": True}], engineering_probe=True,
)
if outcome["outcome"] != "unknown":
    settle_delivery(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
validate_delivery_binding(journal_root, delivery_root, reservation_id=reservation["reservation_id"])
```

Tests: `backend/tests/unit/test_acceptance_source_review_delivery.py` (offline; an injected fake
route for classification and the ledger, plus one run of the default subprocess runner against a
fake `claude` executable that echoes the stdin hash and, on a sleep trigger, proves partial-output
retention and process-group termination).
