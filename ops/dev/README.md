# Local verification

Run full suites and builds through `verify.py` so cooperating sessions on the same machine
do not compete for CPU and memory. Use Python 3.11 or later on Linux or macOS, with the
system `/bin/ps` available. No Python packages are required by the launcher.

From the command's normal working directory, prepend the launcher to **each** heavy stage:

```bash
# backend/ — retain Ruff and Bandit, then run the full suite
ruff check . && bandit -r app -ll && python3 ../ops/dev/verify.py -- python -m pytest

# frontend/ — also required before any backend-path push, including backend tests
python3 ../ops/dev/verify.py -- npm run test -- --run

# frontend/ — full gate for frontend changes
npm run lint && python3 ../ops/dev/verify.py -- npx tsc -p tsconfig.ci.json && \
  python3 ../ops/dev/verify.py -- npm run test -- --run && \
  python3 ../ops/dev/verify.py -- npm run build

# frontend/ — full browser suite, when needed
python3 ../ops/dev/verify.py -- npm run test:e2e
```

The launcher executes an argument vector, without a shell. A prefix before `a && b`
protects only `a`; wrap both heavy commands as above. Focused checks remain concurrent.
The canonical gate requirements are in [CLAUDE.md](../../CLAUDE.md#commands) and
[AGENTS.md §8](../../AGENTS.md#8-commit-hygiene). CI commands, worker counts, suite
timeouts, and Git hooks are unchanged. Never edit a worktree while a suite reads it.

## Lock and cancellation contract

- Every checkout for the same OS account uses the persistent file
  `<account-home>/.cache/earningsnerd/verification.lock`. The account home comes from
  the OS account database, so different `HOME`, `XDG_CACHE_HOME`, `TMPDIR` or working
  directories do not split the queue. Use a local filesystem with working `flock`
  semantics, shared by all participating processes. Different machines, containers
  with separate filesystem namespaces and different users have separate slots.
- The OS owns the lock, not a PID file. **Never delete or replace the lock file**, even
  when it looks idle: waiters may still have the old inode open. A normal exit releases
  the lock without deleting it. No stale-PID recovery, daemon or FIFO ordering is promised.
- Commands retain their working directory, arguments and stdin/stdout/stderr. Normal
  exit codes and signal termination propagate. Diagnostics use stderr and report
  `queue_seconds` separately from `run_seconds`; execution time includes child cleanup.
  Command arguments and environment values are not logged.
- This is for foreground, noninteractive commands running as the same user. The command
  starts in its own process group. INT, TERM, HUP and QUIT cancel a waiter without starting
  its command or signaling the owner. For an active command, the first signal is forwarded
  to its group. Cleanup allows five seconds, then uses KILL; a second cancellation escalates
  at the next supervision check (process inspection can take up to five seconds). The slot
  stays held until no live member of that group remains, including
  descendants left after the direct child exits. A normal leader exit also cleans up any
  remaining group members. The leader is reaped last, preserving the group's ID throughout.
- Unreadable cleanup state or an unsignalable child keeps the slot held and prints a
  diagnostic. Restore process visibility or terminate the remaining owned processes;
  do not delete the lock to admit more work. Linux snapshots include threads so a dead
  main thread cannot hide a live worker. macOS uses process-state snapshots because
  Python does not expose `waitid` there.
- Nested launcher use fails clearly. The inherited `EARNINGSNERD_VERIFY_ACTIVE` marker
  only refuses nesting; it never grants a lock bypass. Wrap each stage once. Commands
  that deliberately clear the marker, detach into another process group/session, change
  user, or run without the launcher are outside this cooperative contract.
- SIGKILL of the launcher, a launcher crash, host loss, and terminal job-control/suspension
  are outside the cleanup guarantee. The parent-only lock then closes, while a child may
  remain alive. Check for and stop surviving work before starting another heavy command.
  The launcher is not a general process supervisor or a fix for test isolation bugs.

## Verification and measurement

The behavioral gate is `backend/tests/unit/test_local_verification.py`. It exercises
real processes and isolated lock files; `--lock-file /absolute/path` exists for such
isolated namespaces. Use the default shared lock for normal development. Never point
a test at the developer's live lock. When the suite itself runs under the launcher,
these fixtures remove its nesting marker only for their separate test namespace.

Compare first-attempt outcomes and queue/run times across subsequent full checks. A wait
is visible scheduling time, not a slower test. Serialization can reduce resource contention;
it does not fix locale differences, flaky assertions, shared state or application defects.
Linux process behavior is verified by the suite and ordinary Linux CI; native macOS
execution needs a macOS host and should be recorded separately from fallback-branch tests.
