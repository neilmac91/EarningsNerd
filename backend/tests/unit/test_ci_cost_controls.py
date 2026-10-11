"""Execute the browser scope on real Git histories; cost controls must fail closed.

Only Markdown records under tasks/, lessons/ and docs/ omit browser builds. All
application, contract, policy and migration suites retain their existing coverage.
"""

import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]


def workflow():
    return yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "CI scope test", "GIT_AUTHOR_EMAIL": "ci@example.invalid",
        "GIT_COMMITTER_NAME": "CI scope test", "GIT_COMMITTER_EMAIL": "ci@example.invalid",
    }

    def git(*args):
        return subprocess.check_output(
            ["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
            text=True, stderr=subprocess.PIPE, timeout=20,
        ).strip()

    def write(path, content="record\n"):
        target = repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    git("init", "-q", "-b", "main")
    write("seed", "base\n")
    git("add", ".")
    git("commit", "-qm", "base")
    return repo, env, git, write


def classify(history, tmp_path, event="push", **overrides):
    repo, env, git, _ = history
    output = tmp_path / "output"
    output.unlink(missing_ok=True)
    env = {
        **env, "EVENT_NAME": event, "GITHUB_SHA": git("rev-parse", "HEAD"),
        "BEFORE_SHA": git("rev-parse", "HEAD^"), "PR_HEAD_SHA": "",
        "RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(output), **overrides,
    }
    scope = workflow()["jobs"]["ci-scope"]["steps"][-1]
    result = subprocess.run(
        ["bash", "-e", "-c", scope["run"]], cwd=repo, env=env,
        capture_output=True, text=True, timeout=20, check=False,
    )
    return result, output.read_text().strip() if output.exists() else ""


@pytest.mark.parametrize("path,records", [
    ("tasks/todo.md", True),
    ("tasks/archive/a record.md", True),
    ("lessons/ops-new.md", True),
    ("docs/nested/guide.md", True),
    ("backend/prompts/summary.md", False),
    ("backend/app/config.py", False),
    ("backend/migrations/new.sql", False),
    ("backend/requirements.txt", False),
    ("backend/requirements-dev.txt", False),
    ("backend/tests/unit/test_contract.py", False),
    ("backend/evals/fixtures/README.md", False),
    ("frontend/package-lock.json", False),
    ("frontend/app/page.tsx", False),
    ("frontend/DESIGN_SYSTEM.md", False),
    ("DESIGN.md", False),
    ("CLAUDE.md", False),
    ("AGENTS.md", False),
    (".impeccable/design.json", False),
    (".github/workflows/ci.yml", False),
    (".github/ai-model.env", False),
    (".gitleaksignore", False),
    (".claude/workflows/review.ts", False),
    ("docs/example.sh", False),
    ("tasks/prototype.html", False),
    ("lessons/data.json", False),
    ("docs-lookalike/guide.md", False),
    ("new-shared-config", False),
    ("backend/app/new\nfile.md", False),
])
def test_scope_classifies_real_changes(history, tmp_path, path, records):
    _, _, git, write = history
    write(path)
    git("add", ".")
    git("commit", "-qm", "change")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0, result.stderr
    assert output == f"records_only={str(records).lower()}"


def test_scope_uses_whole_push_and_preserves_both_rename_sides(history, tmp_path):
    repo, _, git, write = history
    before = git("rev-parse", "HEAD")
    write("backend/app/runtime.md")
    git("add", ".")
    git("commit", "-qm", "runtime")
    write("tasks/todo.md")
    git("add", ".")
    git("commit", "-qm", "records tail")
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and output == "records_only=false"

    # Moving an identical runtime file into records must not hide its deletion.
    git("mv", "backend/app/runtime.md", "tasks/runtime.md")
    git("commit", "-qm", "rename into records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == "records_only=false"

    git("mv", "tasks/runtime.md", "backend/app/runtime.md")
    git("commit", "-qm", "rename out of records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == "records_only=false"

    (repo / "backend/app/runtime.md").unlink()
    git("commit", "-qam", "delete runtime")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == "records_only=false"


def test_pr_scope_compares_checked_merge_to_its_base_parent(history, tmp_path):
    _, _, git, write = history
    git("switch", "-qc", "feature")
    write("tasks/todo.md")
    git("add", ".")
    git("commit", "-qm", "records")
    head = git("rev-parse", "HEAD")
    git("switch", "-q", "main")
    # An unrelated base change must not be mistaken for a change in this PR.
    write("frontend/app/page.tsx", "base-only\n")
    git("add", ".")
    git("commit", "-qm", "base advanced")
    git("merge", "--no-ff", "-qm", "checked merge", "feature")
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head)
    assert result.returncode == 0 and output == "records_only=true"
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA="a" * 40)
    assert result.returncode != 0 and output != "records_only=true"


def test_unknown_empty_manual_and_mismatched_inputs_never_skip(history, tmp_path):
    _, _, git, write = history
    write("tasks/todo.md")
    git("add", ".")
    git("commit", "-qm", "records")
    for overrides in ({"BEFORE_SHA": "0" * 40}, {"BEFORE_SHA": "HEAD^"},
                      {"BEFORE_SHA": git("rev-parse", "HEAD")}):
        result, output = classify(history, tmp_path, **overrides)
        assert result.returncode == 0 and output == "records_only=false"
    for event in ("workflow_dispatch", "unexpected"):
        result, output = classify(history, tmp_path, event)
        assert result.returncode == 0 and output == "records_only=false"
    for event, overrides in (("push", {"GITHUB_SHA": "a" * 40}), ("pull_request", {})):
        result, output = classify(history, tmp_path, event, **overrides)
        assert result.returncode != 0 and output != "records_only=true"


def test_browser_checks_report_records_and_reject_failed_or_missing_scope(tmp_path):
    jobs = workflow()["jobs"]
    for name in ("e2e-tests", "lighthouse"):
        job = jobs[name]
        assert job["needs"] == ["ci-scope"]
        assert job["if"] == "${{ always() && !cancelled() }}"
        guard, records, *steps = job["steps"]
        assert guard["env"] == {
            "SCOPE_RESULT": "${{ needs.ci-scope.result }}",
            "RECORDS_ONLY": "${{ needs.ci-scope.outputs.records_only }}",
        }
        for state, value in (("success", "true"), ("success", "false"),
                             ("failure", ""), ("cancelled", "true"),
                             ("skipped", ""), ("success", ""), ("success", "bogus")):
            result = subprocess.run(
                ["bash", "-e", "-c", guard["run"]], capture_output=True, text=True,
                env={**os.environ, "SCOPE_RESULT": state, "RECORDS_ONLY": value},
                timeout=10, check=False,
            )
            assert (result.returncode == 0) == (state == "success" and value in ("true", "false"))
        assert records["if"] == "needs.ci-scope.outputs.records_only == 'true'"
        assert "GITHUB_STEP_SUMMARY" in records["run"] and "not applicable" in records["run"]
        assert steps
        for step in steps:
            if step.get("uses", "").startswith("actions/upload-artifact@"):
                assert step["if"] == "failure()"
            else:
                assert step["if"] == "needs.ci-scope.outputs.records_only == 'false'"

    # Keep actual suites and secret scanning on records; don't skip required workflows.
    for name in ("backend-tests", "frontend-tests", "migrations-postgres", "secret-scan"):
        assert "if" not in jobs[name] and "needs" not in jobs[name]
        assert all("if" not in step for step in jobs[name]["steps"])
    assert "continue-on-error" not in jobs["e2e-tests"]
    for event in ("push", "pull_request"):
        assert not {"paths", "paths-ignore"} & (workflow()["on"][event] or {}).keys()


def test_cancellation_is_pr_scoped_and_never_groups_main_or_manual_runs():
    ci = workflow()
    # Unique run_id fallbacks prevent queued main/manual runs replacing each other,
    # which cancel-in-progress:false alone would NOT prevent.
    assert ci["concurrency"] == {
        "group": "ci-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }
    assert ci["on"]["push"]["branches"] == ["main"]
    assert ci["jobs"]["deploy-backend"]["concurrency"] == {
        "group": "deploy-backend", "cancel-in-progress": "false",
    }
    assert set(ci["jobs"]["deploy-backend"]["needs"]) == {
        "backend-tests", "frontend-tests", "migrations-postgres", "e2e-tests", "secret-scan",
    }


def test_pip_caches_downloads_keyed_by_the_installed_pins_not_environments():
    jobs = workflow()["jobs"]
    for name in ("backend-tests", "migrations-postgres", "eval-baseline"):
        steps = jobs[name]["steps"]
        setup = next(step for step in steps if step.get("uses", "").startswith("actions/setup-python@"))
        pins = ["backend/requirements.txt"]
        if name == "backend-tests":
            pins.append("backend/requirements-dev.txt")
        assert setup["with"]["cache"] == "pip"
        assert setup["with"]["cache-dependency-path"].splitlines() == pins
        install = next(step for step in steps if step.get("name") == "Install dependencies")
        assert "cache-hit" not in install.get("if", "")
        for pin in pins:
            assert f"pip install -r {pin}" in install["run"]
