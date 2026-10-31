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
#   records  the runtime-records gate, the agent-workflow rules gate (tests/unit/test_agent_workflow_rules.py:
#            the one-page todo and the lessons index, which records commits change), then ruff check and
#            ruff format --check on the two backend test files the records tree owns;
#   backend  the records steps plus the repository's full backend gate, required before every push
#            that changes backend/ (AGENTS.md): ruff check ., bandit -r app -ll, python -m pytest;
#   auto     in a git repository: backend when the working tree has a staged, unstaged or untracked change
#            (read with --untracked-files=all, so no git configuration can hide a new file) under
#            backend/, or when the commits since the merge-base with origin/main change backend/;
#            fails closed (exit 2) when origin/main does not exist (a local main is never a base: its
#            publication state is unknown); records otherwise. HEAD at origin/main means nothing beyond
#            the remote, so records stands. Outside a repository: records scope (nothing is being committed
#            or pushed there), but main's agent-workflow rules gate needs `git ls-files`, so that step fails
#            there and the wrapper reports it; a plain export of the tree is not a place to prove the gate.
#            A git inspection error (a failed status, diff, merge-base or rev-parse) fails closed (exit 2):
#            an error is never read as "no backend change". "not a git repository" counts as a genuine
#            non-repository only when no .git entry exists at the root (checked without following symlinks, so a
#            dangling .git link counts as present); a damaged .git is an inspection error.
#
# Usage: tools/records-gate.sh [repo-root]
# Environment overrides for the test: RECORDS_GATE_PYTHON, RECORDS_GATE_TEST, RECORDS_GATE_RULES_TEST, RECORDS_GATE_LINT_PATHS,
# RECORDS_GATE_SCOPE.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="${1:-$(cd "$here/../../../.." && pwd)}"
python_bin="${RECORDS_GATE_PYTHON:-python3}"
test_path="${RECORDS_GATE_TEST:-tests/unit/test_code_red_runtime_records.py}"
rules_test="${RECORDS_GATE_RULES_TEST:-tests/unit/test_agent_workflow_rules.py}"
lint_paths="${RECORDS_GATE_LINT_PATHS:-tests/unit/test_code_red_runtime_records.py tests/unit/test_records_gate_wrapper.py}"
scope="${RECORDS_GATE_SCOPE:-auto}"
log="$(mktemp)"
trap 'rm -f "$log"' EXIT

inspection_failed() {
  echo "records-gate: cannot determine the scope: git failed to inspect the repository ($1: $(tail -n 1 "$log")); set RECORDS_GATE_SCOPE=records or backend" >&2
  exit 2
}

if [ "$scope" = "auto" ]; then
  inside=""
  if ! inside="$(LC_ALL=C git -C "$repo" rev-parse --is-inside-work-tree 2>"$log")"; then
    grep -q "not a git repository" "$log" || inspection_failed "rev-parse"
    if [ -e "$repo/.git" ] || [ -L "$repo/.git" ]; then inspection_failed "rev-parse"; fi
    inside="false"
  fi
  if [ "$inside" = "true" ]; then
    changed=""
    changed="$(git -C "$repo" status --porcelain --untracked-files=all -- backend 2>"$log")" || inspection_failed "status"
    if [ -z "$changed" ]; then
      base=""
      if ! git -C "$repo" rev-parse --verify --quiet origin/main >/dev/null 2>&1; then
        echo "records-gate: cannot determine the scope: no working-tree change under backend/ and no origin/main to compare the commits with (a local main is not a base; fetch origin or set RECORDS_GATE_SCOPE=records or backend)" >&2
        exit 2
      fi
      base="$(git -C "$repo" merge-base HEAD origin/main 2>"$log")" || inspection_failed "merge-base"
      [ -n "$base" ] || inspection_failed "merge-base"
      changed="$(git -C "$repo" diff --name-only "$base" HEAD -- backend 2>"$log")" || inspection_failed "diff"
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
run_step "workflow rules" "$python_bin" -m pytest "$rules_test" -q -p no:cacheprovider
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
