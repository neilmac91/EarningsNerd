# E7 judge call reservation and capture

`backend/evals/acceptance_ai_judge_runner.py` is an explicit, one-call-at-a-time
runner for the retained Fable ledger. It does not start a queue or call a model
on import. An operator first calls `initialize(programme, cli, contract,
system_prompt, input_paths, probe_input=None)` with a new private directory,
the exact `evals.judge._JUDGE_SYSTEM` prompt, and files containing all 120
independently reconstructed judge inputs plus `development-smoke`. The contract
and all 121 input byte hashes are frozen before dispatch. `initialize` runs the
pinned executable's `--version` locally, requires `2.1.278 (Claude Code)`, and
retains raw version output and a hash-bound receipt. This is a local version
observation, not remote model authentication.

`run_one(programme, slot, cli, timeout_seconds=300)` invokes only the named
slot after a durable SQLite reservation. It requires the same binary, contract,
prompt, inputs, settings and version evidence. Its child uses the exact
`--model claude-fable-5-1` judge argv expected by
`evals.acceptance_ai_judge_evidence`. The environment retains only local CLI
runtime basics and excludes the five billing variables in `evals.judge`, model
and endpoint overrides, proxies, and `NODE_OPTIONS`. Known Claude settings
files are frozen and rejected if they contain model, endpoint, proxy, hook,
MCP or environment overrides. The programme must be outside the repository;
before version observation and every call, the runner refuses a CLI working
directory beneath any ancestor `CLAUDE.md`, `CLAUDE.local.md`, `.claude`
directory (including settings and rules), or `.git`. It checks
again inside the guardian immediately before CLI launch. The guardian writes
raw stdout and stderr to
exclusive files, watches the controller, and kills the CLI process group if
the controller dies. If the guardian dies, the controller stops the programme
and kills its recorded CLI process group.

There are at most 243 calls including one optional quota probe. A substantive
slot permits at most one retry, and only after a retained CLI error on the
identical input. A `FAIL` is a completed verdict and cannot be redrawn. An
uncertain reserved attempt, invalid result, or any non-`OK` quota probe stops
later calls, including a generic CLI error from the probe.
There is no reset or automatic recovery. `inspect(programme)` reports progress;
`export_ledger(programme)` creates a snapshot for the offline
`validate_judge_ledger` check. Seal the version files, programme binding,
SQLite state, raw attempts, receipts and exported ledger together in the E7
evidence inventory.

A local receipt cannot prove which remote model or account answered. A machine
crash, or a simultaneous guardian failure in the gap between CLI spawn and PID
recording, leaves an uncertain reservation for external investigation. The
runner never treats that uncertainty as permission to retry.
