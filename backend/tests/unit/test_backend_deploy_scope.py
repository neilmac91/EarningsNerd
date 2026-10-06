"""Changes confined to backend/tests/ stay in CI and cannot trigger a Cloud Run deployment.

backend/.dockerignore excludes tests/ from the image, so the deploy-backend change detector drops
backend/tests/ before testing for ^backend/, and every deploy step is gated on that decision
(lessons/ops-deploy-detector-mirrors-the-image-context.md).
"""
import os
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
GIT_CALL = "diff --name-only --no-renames HEAD^ HEAD"
DEPLOY_GATE = "steps.changes.outputs.backend == 'true'"


def _workflow():
    return yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)


def _detect_step(workflow):
    return next(
        step for step in workflow["jobs"]["deploy-backend"]["steps"] if step.get("id") == "changes"
    )


def _run_detector(shell, cwd, env, output):
    # GitHub runs an unspecified `shell:` as `bash -e {0}` (no pipefail); mirror that exactly.
    result = subprocess.run(
        ["bash", "-e", "-c", shell], capture_output=True, text=True, cwd=cwd,
        env={**env, "GITHUB_OUTPUT": str(output)}, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == "", result.stderr
    return output.read_text().strip()


def test_backend_test_only_changes_do_not_deploy(tmp_path):
    workflow = _workflow()
    for event in ("push", "pull_request"):
        trigger = workflow["on"][event] or {}
        assert "paths" not in trigger and "paths-ignore" not in trigger
    tests = workflow["jobs"]["backend-tests"]
    assert "if" not in tests, "Changes confined to backend/tests/ must still run the backend CI job"
    pytest_step = next(step for step in tests["steps"] if step.get("name") == "Run pytest")
    assert "if" not in pytest_step
    assert "python -m pytest" in pytest_step["run"], "The backend CI job must run the whole suite"
    assert "tests/" in (ROOT / "backend/.dockerignore").read_text().splitlines()

    deploy = workflow["jobs"]["deploy-backend"]
    detect = _detect_step(workflow)
    # The detector's exit status relies on GitHub's default shell (bash -e, no pipefail).
    assert "shell" not in detect and "defaults" not in deploy and "defaults" not in workflow
    later = deploy["steps"][deploy["steps"].index(detect) + 1:]
    assert later, "deploy-backend has no steps after the detector"
    for step in later:
        assert step.get("if") == DEPLOY_GATE, f"Deploy step {step.get('name')!r} is not gated"

    tracked_tests = subprocess.check_output(
        ["git", "ls-files", "backend/tests/"], cwd=ROOT, text=True
    ).splitlines()
    assert len(tracked_tests) > 100, "The test-only case must cover real tracked test paths"
    # Execute the workflow's actual shell, replacing only git's changed-path input.
    # Include future nested files and near-prefix boundaries, not just current .py tests.
    changed = tmp_path / "changed-paths"
    shell = (
        'git() {\n'
        '  [ "$*" = "' + GIT_CALL + '" ] || { echo "unexpected git invocation: $*" >&2; return 2; }\n'
        '  cat "$TEST_CHANGED_PATHS_FILE"\n'
        '}\n'
    ) + detect["run"]
    cases = (
        ([], False),
        (["docs/DEPLOYMENT.md", ".github/workflows/ci.yml"], False),
        (tracked_tests, False),
        (["backend/tests/new.fixture", "backend/tests/future/deep/unknown.ext"], False),
        (["backend/app/config.py"], True),
        (["backend/migrations/new.sql", "backend/scripts/apply_migrations.sh"], True),
        (["backend/Dockerfile", "backend/.dockerignore", "backend/requirements.txt"], True),
        (["backend/tests_support/helper.py", "backend/testsuite.py"], True),
        (["backend/tests/unit/test_example.py", "backend/app/config.py"], True),
    )
    env = {**os.environ, "TEST_CHANGED_PATHS_FILE": str(changed)}
    for index, (paths, expected) in enumerate(cases):
        changed.write_text("".join(f"{path}\n" for path in paths))
        decision = _run_detector(shell, ROOT, env, tmp_path / f"github-output-{index}")
        assert decision == f"backend={str(expected).lower()}", (
            f"Incorrect deployment decision for {paths[:3]}: "
            "exclude backend/tests/ only; keep runtime and mixed changes deployable"
        )


def test_detector_sees_both_sides_of_a_rename(tmp_path):
    """A runtime file moved under backend/tests/ still deploys: --no-renames lists its old path."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env = {
        **os.environ, "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "GIT_AUTHOR_NAME": "gate", "GIT_AUTHOR_EMAIL": "gate@example.invalid",
        "GIT_COMMITTER_NAME": "gate", "GIT_COMMITTER_EMAIL": "gate@example.invalid",
    }

    def git(*args):
        subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
            check=True, capture_output=True, text=True, timeout=30,
        )

    git("init", "-q", "-b", "main")
    (repo / "backend/app").mkdir(parents=True)
    (repo / "backend/tests").mkdir(parents=True)
    (repo / "backend/app/helper.py").write_text("VALUE = 1\n" * 20)
    (repo / "backend/tests/test_helper.py").write_text("def test_value():\n    assert True\n")
    git("add", ".")
    git("commit", "-q", "-m", "runtime file and test")
    git("mv", "backend/app/helper.py", "backend/tests/helper.py")
    git("commit", "-q", "-m", "move the runtime file under tests")
    detect = _detect_step(_workflow())["run"]
    assert _run_detector(detect, repo, env, tmp_path / "github-output-rename") == "backend=true"

    (repo / "backend/tests/test_helper.py").write_text("def test_value():\n    assert 1 == 1\n")
    git("commit", "-q", "-am", "change confined to tests")
    assert _run_detector(detect, repo, env, tmp_path / "github-output-tests") == "backend=false"
