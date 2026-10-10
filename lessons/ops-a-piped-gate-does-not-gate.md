# A verification command in a commit chain is never piped away; its exit status gates the commit

Date: 2026-10-10 · Area: ops / verification

**Context.** The CODE RED chief ran the runtime-records gate inside a commit-and-push chain as
`pytest … | tail -1 && git commit … && git push`. The gate failed (closure 172 resolved a label inside
the closure that registered it), but `tail` returned 0, so the chain committed and pushed head
`7d65c89` of PR neilmac91/EarningsNerd#1172 with the gate red. The "1 failed" line was printed and
read seconds later; the correction landed one minute after (chief defect 10,
`tasks/code-red-20261004/runtime/control/DECISIONS-21.md`). CI caught it too, but a push that
reaches CI red costs a cycle and the reviewers' trust.

**Rule.** When a verification step decides whether a commit or push happens, its exit status must be
the thing that decides: run it unpiped, or set `pipefail` for the chain, and grep the summary only
after the status has been checked. Prefer `set -euo pipefail` at the top of any chain that ends in a
commit or push, and never follow a test run with `| tail`, `| grep` or `| head` on the same line as
the `&&` that commits. For the CODE RED records, run every verification step of a records commit only through
`tasks/code-red-20261004/runtime/tools/records-gate.sh`, which runs the records gate, `ruff check` and
`ruff format --check` unpiped and, when the working tree or the commits since main change anything under `backend/`, the repository's
full backend gate (`ruff check .`, `bandit -r app -ll`, `python -m pytest`; chief defect 12), captures each exit
status explicitly and exits 0 only when every step passed; `backend/tests/unit/test_records_gate_wrapper.py` pins that form and proves by mutation that a
failing pytest step and a failing non-pytest step each fail the wrapper (rule 12: the gate behind
this rule). Run it with CI's interpreter version (`RECORDS_GATE_PYTHON`): under this container's default Python 3.13 eleven
pre-existing tests fail that pass on CI's 3.11, and in the gate's output an environment-only failure looks like a real one
(chief defect 12's first run). `set -e` is not that check in the Claude Code tool shell: a probe `(set -e; false; echo survived)` prints there, so
errexit is suppressed (chief defect 11, 2026-10-10T05:00Z: a failed `ruff format --check` did not stop a chain from committing and
pushing `577edeb`). Give every verification step of a chain that commits or pushes its own explicit exit, `cmd || exit 1`; the
wrapper is a separate script, where `set -e` does work.

**Evidence.** `tasks/code-red-20261004/runtime/control/DECISIONS-21.md` (disclosure 7);
`tasks/code-red-20261004/runtime/control/APPOINTMENTS.json` (`chief_defects`, 2026-10-10T04:05Z);
PR neilmac91/EarningsNerd#1172 heads `7d65c89` (gate red) and `351319f` (gate green); `577edeb` (unformatted) and `2dc7a3b` (formatted); chief defect 12: heads `0fc248f`, `577edeb`, `2dc7a3b` and `10df20f`
pushed without the full backend gate run locally (CI ran it green).
