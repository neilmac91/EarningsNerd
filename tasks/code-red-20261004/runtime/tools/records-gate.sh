#!/usr/bin/env bash
# Run the CODE RED runtime-records gate so that its exit status is the chain's exit status.
#
# lessons/ops-a-piped-gate-does-not-gate.md (chief defect 10, DECISIONS-21): a commit chain once ran
# `pytest … | tail -1 && git commit …`, the pipe hid the gate's failure and a red head was pushed. This
# wrapper is the supported way to run the gate before a records commit: the test runs unpiped, its
# summary line is printed afterwards, and the wrapper exits with pytest's own status, so `./records-gate.sh
# && git commit …` cannot commit over a red gate. Gate: backend/tests/unit/test_records_gate_wrapper.py
# (the form of this file, and a mutation proof that a failing test yields a non-zero exit).
#
# Usage: tasks/code-red-20261004/runtime/tools/records-gate.sh [REPO_ROOT]
#   REPO_ROOT defaults to the repository that contains this script.
# Environment:
#   RECORDS_GATE_PYTHON  interpreter to run pytest with (default: python3)
#   RECORDS_GATE_TEST    test path relative to <repo>/backend (default: the runtime-records gate)
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${1:-$(cd "$here/../../../.." && pwd)}"
python_bin="${RECORDS_GATE_PYTHON:-python3}"
test_path="${RECORDS_GATE_TEST:-tests/unit/test_code_red_runtime_records.py}"

log="$(mktemp)"
trap 'rm -f "$log"' EXIT

status=0
(cd "$repo/backend" && "$python_bin" -m pytest "$test_path" -q -p no:cacheprovider) >"$log" 2>&1 || status=$?

tail -n 1 "$log"
if [ "$status" -ne 0 ]; then
  echo "records-gate: FAILED (pytest exit $status); last 40 lines:" >&2
  tail -n 40 "$log" >&2
fi
exit "$status"
