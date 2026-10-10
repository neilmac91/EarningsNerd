#!/usr/bin/env bash
# records-gate.sh — the supported way to verify a CODE RED records commit before it is made.
#
# Every verification step runs unpiped and its exit status is captured explicitly (`|| status=$?`):
# the gate does not rely on `set -e`, which the chief's tool shell suppresses (chief defects 10 and
# 11, tasks/code-red-20261004/runtime/control/DECISIONS-21.md). One line per step is printed and
# the exit status is 0 only when every step passed. Lesson: lessons/ops-a-piped-gate-does-not-gate.md.
# Gate: backend/tests/unit/test_records_gate_wrapper.py pins this form and proves by mutation that a
# failing step of any kind fails the wrapper.
#
# Scope (RECORDS_GATE_SCOPE=auto|records|backend, default auto):
#   records  the runtime-records gate, then ruff check and ruff format --check on the two backend
#            test files the records tree owns;
#   backend  the records steps plus the repository's full backend gate, required before every push
#            that changes backend/ (AGENTS.md): ruff check ., bandit -r app -ll, python -m pytest;
#   auto     in a git repository: backend when the working tree has a staged or unstaged change under
#            backend/ or when the commits since the merge-base with origin/main (fallback main) change
#            backend/; fails closed (exit 2) when neither base exists; records otherwise. Outside a
#            repository: records (nothing is being committed or pushed there).
#
# Usage: tools/records-gate.sh [repo-root]
# Environment overrides for the test: RECORDS_GATE_PYTHON, RECORDS_GATE_TEST, RECORDS_GATE_LINT_PATHS, RECORDS_GATE_SCOPE.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${1:-$(cd "$here/../../../.." && pwd)}"
python_bin="${RECORDS_GATE_PYTHON:-python3}"
test_path="${RECORDS_GATE_TEST:-tests/unit/test_code_red_runtime_records.py}"
lint_paths="${RECORDS_GATE_LINT_PATHS:-tests/unit/test_code_red_runtime_records.py tests/unit/test_records_gate_wrapper.py}"
scope="${RECORDS_GATE_SCOPE:-auto}"
if [ "$scope" = "auto" ]; then
  if git -C "$repo" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    changed="$(git -C "$repo" status --porcelain -- backend 2>/dev/null || true)"
    if [ -z "$changed" ]; then
      base=""
      for ref in origin/main main; do
        if base="$(git -C "$repo" merge-base HEAD "$ref" 2>/dev/null)"; then break; fi
        base=""
      done
      if [ -z "$base" ]; then
        echo "records-gate: cannot determine the scope: no working-tree change under backend/ and no origin/main or main to compare the commits with; set RECORDS_GATE_SCOPE=records or backend" >&2
        exit 2
      fi
      changed="$(git -C "$repo" diff --name-only "$base" HEAD -- backend 2>/dev/null || true)"
    fi
    if [ -n "$changed" ]; then scope=backend; else scope=records; fi
  else
    scope=records
  fi
fi
case "$scope" in
  records | backend) ;;
  *) echo "records-gate: unknown scope '$scope' (records, backend or auto)" >&2; exit 2 ;;
esac
echo "records-gate: scope $scope"
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
if [ "$scope" = "backend" ]; then
  run_step "ruff check (backend)" "$python_bin" -m ruff check .
  run_step "bandit" "$python_bin" -m bandit -r app -ll
  run_step "pytest (backend)" "$python_bin" -m pytest -q -p no:cacheprovider
fi

if [ "$failed" -eq 0 ]; then
  echo "records-gate: PASSED"
else
  echo "records-gate: FAILED" >&2
fi
exit "$failed"
