# Pin the lint/security toolchain and select lint rules explicitly — CI must not drift with the tool

**Date:** 2026-09-04 · **Area:** ops / CI

## Context

`ci.yml` installed the backend lint gate with a bare `pip install ruff bandit`. The tree was clean
on 2026-07-16 under ruff 0.15.x. Ruff 0.16 widened its *default* rule selection; with no code
change the same tree reported 2,767 findings (UP045, UP006, B008, I001, UP035, BLE001, UP017 …)
under 0.16.6 — i.e. the next backend push to `main` would have gone red at the lint step before
the deploy could even run. `backend/ruff.toml` relied on ruff's defaults instead of naming its
rule set, so the tool's opinion, not the repo's, decided what CI enforced.

## Rule

- Lint and security tools are installed from a pinned file (`backend/requirements-dev.txt`, exact
  `==` pins) by both CI and the local gate. Never `pip install <tool>` unpinned in a workflow.
- `ruff.toml` names its rule set with an explicit `select`. Widening the set is a deliberate PR
  that also runs the autofix — never a side effect of a tool upgrade.
- Before pushing, run the gate with the pinned versions (`pip install -r backend/requirements-dev.txt`).

Enforced by `backend/tests/unit/test_migration_lock_safety.py`
(`test_lint_toolchain_is_installed_from_pinned_dev_requirements`, `test_ruff_rule_set_is_selected_explicitly`).

## Evidence

- `.github/workflows/ci.yml` "Install dependencies" step; `backend/requirements-dev.txt`; `backend/ruff.toml [lint] select`.
- Local reproduction 2026-09-04: ruff 0.15.8 → "All checks passed!"; ruff 0.16.6 → 2,767 findings;
  ruff 0.16.6 with `--select E4,E7,E9,F` → "All checks passed!".
