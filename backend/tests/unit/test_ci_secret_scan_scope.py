"""CI's secret-scan reads every branch and every tag, with the repository's own rules (rule 12 gate).

A tag publishes the commit it names as a branch does. On 2026-01-22 a cleanup script archived a closed
pull request's branch (#17) as `archive/2025-11-18-supabase-rag` and deleted the branch, and the
commit's `backend/env.example.txt` held a real OpenRouter key and a Supabase secret key. The scan
walked `--branches --remotes` only, so it never read that commit, while `actions/checkout` with
`fetch-depth: 0` fetched the tag on every run; GitHub's secret scanning raised alerts 1 and 2 on it
(lessons/ops-a-tag-publishes-the-commit-it-names.md). The walk must name every branch and every
tag, and the step must leave gitleaks to read `.gitleaks.toml` from the checkout.
"""
import re
import shlex
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CI = ROOT / ".github" / "workflows" / "ci.yml"
EVERY_REF = ({"--all"}, {"--branches", "--remotes", "--tags"})


def _workflow() -> dict:
    return yaml.safe_load(CI.read_text(encoding="utf-8"))


def _job() -> dict:
    return _workflow()["jobs"]["secret-scan"]


def _scan_step() -> dict:
    return next(step for step in _job()["steps"] if "gitleaks git" in step.get("run", ""))


def _scan_command() -> list[str]:
    commands = [line.strip() for line in _scan_step()["run"].splitlines() if "gitleaks git" in line]
    assert len(commands) == 1, f"one gitleaks scan expected, found {commands}"
    return shlex.split(commands[0])


def _log_opts(words: list[str]) -> set[str]:
    values = [word.split("=", 1)[1] for word in words if word.startswith("--log-opts=")]
    assert len(values) == 1, f"one --log-opts expected, found {values}"
    return set(values[0].split())


def test_the_checkout_fetches_every_branch_and_tag():
    checkout = next(step for step in _job()["steps"] if step.get("uses", "").startswith("actions/checkout@"))
    assert checkout["with"]["fetch-depth"] == 0
    assert "fetch-tags" not in checkout["with"]  # fetch-depth: 0 fetches every tag; nothing turns it off


def test_the_scan_walks_every_branch_and_every_tag():
    assert _log_opts(_scan_command()) in EVERY_REF


def test_the_scan_reads_the_repository_rules_from_the_checkout():
    words = _scan_command()
    assert words[words.index("git") + 1] == ".", "gitleaks reads ./.gitleaks.toml only when it scans the checkout"
    # --config replaces the rules and --enable-rule narrows them to the ids it names.
    assert not any(word.startswith(("--config", "-c", "--enable-rule")) for word in words)
    # GITLEAKS_CONFIG and GITLEAKS_CONFIG_TOML outrank ./.gitleaks.toml (gitleaks 8.24.3 cmd/root.go), wherever
    # the step's environment gets them: the workflow's env, the job's, the step's, or the run script itself.
    for env in (_workflow().get("env") or {}, _job().get("env") or {}, _scan_step().get("env") or {}):
        assert not [name for name in env if name.upper().startswith("GITLEAKS_CONFIG")]
    assert "GITLEAKS_CONFIG" not in _scan_step()["run"].upper()
    assert (ROOT / ".gitleaks.toml").is_file()


def test_the_selector_refuses_a_walk_that_skips_tags():
    # The bad case this gate exists for: the walk the job ran from #1069 until this gate.
    assert _log_opts(shlex.split('./gitleaks git . --log-opts="--branches --remotes" --redact=100')) not in EVERY_REF
    assert re.search(r"--tags\b", CI.read_text(encoding="utf-8"))
