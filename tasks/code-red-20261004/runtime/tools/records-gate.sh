#!/usr/bin/env bash
# records-gate.sh — the supported way to verify a CODE RED records commit before it is made.
#
# Every verification step runs unpiped and its exit status is captured explicitly (`|| status=$?`):
# the gate does not rely on `set -e`, which the chief's tool shell suppresses (chief defects 10 and
# 11, tasks/code-red-20261004/runtime/control/DECISIONS-21.md). One line per step is printed and
# the exit status is 0 only when every step passed. Lesson: lessons/ops-a-piped-gate-does-not-gate.md.
# Gate: backend/tests/unit/test_records_gate_wrapper.py pins this form and proves by mutation that a
# failing pytest step and a failing non-pytest step each fail the wrapper.
#
# Usage: tools/records-gate.sh [repo-root]
# Environment overrides exist for the test only: RECORDS_GATE_PYTHON, RECORDS_GATE_TEST, RECORDS_GATE_LINT_PATHS.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${1:-$(cd "$here/../../../.." && pwd)}"
python_bin="${RECORDS_GATE_PYTHON:-python3}"
test_path="${RECORDS_GATE_TEST:-tests/unit/test_code_red_runtime_records.py}"
lint_paths="${RECORDS_GATE_LINT_PATHS:-tests/unit/test_code_red_runtime_records.py tests/unit/test_records_gate_wrapper.py}"
log="$(mktemp)"
trap 'rm -f "$log"' EXIT
failed=0

run_step() {
  local name="$1"
  shift
  local status=0
  (cd "$repo/backend" && "$@") >"$log" 2>&1 || status=$?
  if [ "$status" -eq 0 ]; then
    printf 'records-gate: ok    %s: %s\n' "$name" "$(tail -n 1 "$log")"
  else
    printf 'records-gate: FAIL  %s (exit %s); last 40 lines:\n' "$name" "$status" >&2
    sed 's/^/    /' <<<"$(tail -n 40 "$log")" >&2
    failed=1
  fi
}

# shellcheck disable=SC2086  # lint_paths is a space-separated list by design
run_step "records gate" "$python_bin" -m pytest "$test_path" -q -p no:cacheprovider
run_step "ruff check" "$python_bin" -m ruff check $lint_paths
run_step "ruff format" "$python_bin" -m ruff format --check $lint_paths

if [ "$failed" -eq 0 ]; then
  echo "records-gate: PASSED"
else
  echo "records-gate: FAILED" >&2
fi
exit "$failed"
