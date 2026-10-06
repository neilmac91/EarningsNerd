"""Test-only backend edits stay in CI and cannot trigger a Cloud Run deployment."""
import os
from pathlib import Path
import subprocess

import yaml

ROOT = Path(__file__).resolve().parents[3]


def test_backend_test_only_changes_do_not_deploy(tmp_path):
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    for event in ("push", "pull_request"):
        trigger = workflow["on"][event] or {}
        assert "paths" not in trigger and "paths-ignore" not in trigger
    tests = workflow["jobs"]["backend-tests"]
    assert "if" not in tests, "Test-only changes must still run the backend CI job"
    pytest_step = next(step for step in tests["steps"] if step.get("name") == "Run pytest")
    assert "if" not in pytest_step
    assert pytest_step["run"] == "cd backend && python -m pytest"
    assert "tests/" in (ROOT / "backend/.dockerignore").read_text().splitlines()

    tracked_tests = subprocess.check_output(
        ["git", "ls-files", "backend/tests/"], cwd=ROOT, text=True
    ).splitlines()
    assert len(tracked_tests) > 100, "The test-only case must cover real tracked test paths"
    detect = next(
        step for step in workflow["jobs"]["deploy-backend"]["steps"]
        if step.get("id") == "changes"
    )["run"]
    # Execute the workflow's actual shell, replacing only git's changed-path input.
    # Include future nested files and near-prefix boundaries, not just current .py tests.
    shell = '''git() {
      [ "$*" = "diff --name-only HEAD^ HEAD" ] || return 2
      printf '%s\\n' "$TEST_CHANGED_PATHS"
    }
''' + detect
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
    for index, (paths, expected) in enumerate(cases):
        output = tmp_path / f"github-output-{index}"
        result = subprocess.run(
            ["bash", "-e", "-c", shell], capture_output=True, text=True,
            env={**os.environ, "TEST_CHANGED_PATHS": "\n".join(paths), "GITHUB_OUTPUT": str(output)},
            timeout=10, check=False,
        )
        assert result.returncode == 0, result.stderr
        assert output.read_text().strip() == f"backend={str(expected).lower()}", (
            f"Incorrect deployment decision for {paths[:3]}: "
            "exclude backend/tests/ only; keep runtime and mixed changes deployable"
        )
