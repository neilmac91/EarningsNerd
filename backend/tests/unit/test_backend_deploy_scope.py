"""Changes confined to backend/tests/ stay in CI and cannot trigger a Cloud Run deployment.

backend/.dockerignore excludes tests/ from the image, so the deploy-backend change detector drops
backend/tests/ before testing for ^backend/, and every deploy step is gated on that decision
(lessons/ops-deploy-detector-mirrors-the-image-context.md).

A deploy ships its own commit's image, and the deploy group runs waiting deploys in the order their
runs reach it, not in merge order. So the detector also skips a commit that main has moved past with
deployable backend changes, which that newer commit's own run deploys; a failed read of main fails
the step rather than deploying (lessons/ops-a-superseded-commit-never-deploys.md).
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
GIT_CALL = "diff --name-only --no-renames HEAD^ HEAD"
DEPLOY_GATE = "steps.changes.outputs.backend == 'true'"
# The detector's read of main, run only after it finds a deployable change of its own.
MAIN_TIP = "f" * 40
FETCH_CALL = "fetch --no-tags --quiet --depth=1 origin main"
TIP_CALL = "rev-parse --verify FETCH_HEAD"
NEWER_CALL = f"diff --name-only --no-renames HEAD {MAIN_TIP}"
# git as the detector calls it, answered from files: the merge's changed paths, and the paths main has
# changed since this commit. Any other invocation fails the run, and each fetch is logged.
GIT_STUB = (
    'git() {\n'
    '  case "$*" in\n'
    '    "' + GIT_CALL + '") cat "$TEST_CHANGED_PATHS_FILE" ;;\n'
    '    "' + FETCH_CALL + '") echo fetch >> "$TEST_FETCH_LOG" ;;\n'
    '    "' + TIP_CALL + '") echo "' + MAIN_TIP + '" ;;\n'
    '    "' + NEWER_CALL + '") cat "$TEST_NEWER_PATHS_FILE" ;;\n'
    '    *) echo "unexpected git invocation: $*" >&2; return 2 ;;\n'
    '  esac\n'
    '}\n'
)


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
    # Execute the workflow's actual shell, replacing only git's path inputs. Main has changed nothing
    # since this commit here, so the decision rests on the merge's own paths.
    # Include future nested files and near-prefix boundaries, not just current .py tests.
    changed = tmp_path / "changed-paths"
    newer = tmp_path / "newer-paths"
    newer.write_text("")
    fetches = tmp_path / "fetches"
    shell = GIT_STUB + detect["run"]
    cases = (
        ([], False),
        (["docs/DEPLOYMENT.md", ".github/workflows/ci.yml"], False),
        (tracked_tests, False),
        (["backend/tests/new.fixture", "backend/tests/future/deep/unknown.ext"], False),
        # Local verification tooling and its gates/guidance stay outside the backend image.
        (["ops/dev/verify.py", "ops/dev/README.md", "AGENTS.md", "CLAUDE.md", "CONTRIBUTING.md",
          ".claude/agents/engineering/backend-developer.md", ".claude/agents/engineering/frontend-developer.md",
          "lessons/ops-run-the-frontend-unit-suite-before-a-backend-push.md",
          "backend/tests/unit/test_local_verification.py", "backend/tests/unit/test_backend_deploy_scope.py",
          "backend/tests/unit/test_ops_stderr_withheld.py"], False),
        # An Ops read-back change: workflow, repository-root ops/ script, docs and a backend unit test.
        (["ops/capacity/readout.py", ".github/workflows/ops.yml", "docs/OPERATIONS.md",
          "backend/tests/unit/test_ops_describe_jobs.py"], False),
        # The read-back follow-ups: new ops/describe/ modules, the workflow, docs, two lessons, todo and backend tests.
        ([".github/workflows/ops.yml", "backend/tests/unit/test_backend_deploy_scope.py",
          "backend/tests/unit/test_capacity_projection_privacy.py", "backend/tests/unit/test_capacity_readout.py",
          "backend/tests/unit/test_job_reporting.py", "backend/tests/unit/test_ops_describe_jobs.py",
          "backend/tests/unit/test_ops_stderr_withheld.py", "backend/tests/unit/test_prod_flag_visibility.py",
          "docs/DEPLOYMENT.md", "lessons/ops-capacity-projection-withholds-command-values.md",
          "lessons/ops-denied-reads-report-unverified.md",
          "ops/capacity/readout.py", "ops/describe/jobs.py", "ops/describe/service.py", "tasks/todo.md"], False),
        (["backend/app/config.py"], True),
        (["backend/migrations/new.sql", "backend/scripts/apply_migrations.sh"], True),
        (["backend/Dockerfile", "backend/.dockerignore", "backend/requirements.txt"], True),
        (["backend/tests_support/helper.py", "backend/testsuite.py"], True),
        (["backend/tests/unit/test_example.py", "backend/app/config.py"], True),
    )
    env = {**os.environ, "TEST_CHANGED_PATHS_FILE": str(changed), "TEST_NEWER_PATHS_FILE": str(newer),
           "TEST_FETCH_LOG": str(fetches)}
    for index, (paths, expected) in enumerate(cases):
        changed.write_text("".join(f"{path}\n" for path in paths))
        fetches.write_text("")
        decision = _run_detector(shell, ROOT, env, tmp_path / f"github-output-{index}")
        assert decision == f"backend={str(expected).lower()}", (
            f"Incorrect deployment decision for {paths[:3]}: "
            "exclude backend/tests/ only; keep runtime and mixed changes deployable"
        )
        # Main is read only for a commit with a deployable change of its own.
        assert fetches.read_text() == ("fetch\n" if expected else ""), paths[:3]


def test_a_commit_main_superseded_with_deployable_changes_does_not_deploy(tmp_path):
    """A deployable merge deploys only if main has changed no deployable backend file since it.

    Main's newer paths get the same exclusion as the merge's own: backend/tests/ alone supersedes
    nothing, and a near-prefix path such as backend/tests_support/ does."""
    shell = GIT_STUB + _detect_step(_workflow())["run"]
    changed, newer, fetches = tmp_path / "changed-paths", tmp_path / "newer-paths", tmp_path / "fetches"
    changed.write_text("backend/app/config.py\n")
    env = {**os.environ, "TEST_CHANGED_PATHS_FILE": str(changed), "TEST_NEWER_PATHS_FILE": str(newer),
           "TEST_FETCH_LOG": str(fetches)}
    cases = (
        ([], True),
        (["frontend/app/page.tsx", "tasks/todo.md", "docs/DEPLOYMENT.md", ".github/workflows/ci.yml"], True),
        (["backend/tests/unit/test_example.py", "backend/tests/future/deep/unknown.ext"], True),
        (["backend/app/services/summary_pipeline.py"], False),
        (["backend/requirements.txt"], False),
        (["backend/migrations/new.sql"], False),
        (["backend/tests_support/helper.py"], False),
        (["frontend/app/page.tsx", "backend/app/config.py"], False),
    )
    for index, (paths, expected) in enumerate(cases):
        newer.write_text("".join(f"{path}\n" for path in paths))
        fetches.write_text("")
        output = tmp_path / f"github-output-superseded-{index}"
        result = subprocess.run(["bash", "-e", "-c", shell], capture_output=True, text=True, cwd=ROOT,
                                env={**env, "GITHUB_OUTPUT": str(output)}, timeout=30, check=False)
        assert (result.returncode, result.stderr) == (0, ""), result.stderr
        assert output.read_text().strip() == f"backend={str(expected).lower()}", paths
        assert fetches.read_text() == "fetch\n"
        assert ("superseded deploy" in result.stdout) is (not expected), result.stdout


def _scratch_repo(tmp_path):
    """A scratch repository whose origin is a bare repository, reached over file:// as Actions reaches
    GitHub, and a git runner for it that returns stdout."""
    repo, origin = tmp_path / "repo", tmp_path / "origin.git"
    repo.mkdir()
    env = {
        **os.environ, "HOME": str(tmp_path), "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(tmp_path / "gitconfig"),
        "GIT_AUTHOR_NAME": "gate", "GIT_AUTHOR_EMAIL": "gate@example.invalid",
        "GIT_COMMITTER_NAME": "gate", "GIT_COMMITTER_EMAIL": "gate@example.invalid",
    }

    def git(*args):
        return subprocess.run(
            ["git", "-c", "commit.gpgsign=false", *args], cwd=repo, env=env,
            check=True, capture_output=True, text=True, timeout=30,
        ).stdout.strip()

    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origin)], env=env, check=True,
                   capture_output=True, timeout=30)
    git("init", "-q", "-b", "main")
    git("remote", "add", "origin", origin.as_uri())
    return repo, env, git


def _commit(repo, git, message, files):
    for path, text in files.items():
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
    git("add", "-A")
    git("commit", "-q", "-m", message)
    return git("rev-parse", "HEAD")


def test_detector_sees_both_sides_of_a_rename(tmp_path):
    """A runtime file moved under backend/tests/ still deploys: --no-renames lists its old path."""
    repo, env, git = _scratch_repo(tmp_path)
    _commit(repo, git, "runtime file and test", {
        "backend/app/helper.py": "VALUE = 1\n" * 20,
        "backend/tests/test_helper.py": "def test_value():\n    assert True\n",
    })
    git("mv", "backend/app/helper.py", "backend/tests/helper.py")
    git("commit", "-q", "-m", "move the runtime file under tests")
    git("push", "-q", "origin", "HEAD:main")  # main is this commit, so nothing newer supersedes it
    detect = _detect_step(_workflow())["run"]
    assert _run_detector(detect, repo, env, tmp_path / "github-output-rename") == "backend=true"

    _commit(repo, git, "change confined to tests",
            {"backend/tests/test_helper.py": "def test_value():\n    assert 1 == 1\n"})
    git("push", "-q", "origin", "HEAD:main")
    assert _run_detector(detect, repo, env, tmp_path / "github-output-tests") == "backend=false"


def test_an_older_deploy_after_a_newer_backend_merge_is_skipped_in_real_git(tmp_path):
    """The 2026-10-31 order: three backend merges, the newest deploying first. Each older commit's
    deploy, run once main has moved past it, is skipped; the newest deploys, and so does a commit
    main has moved past only with changes outside the image (frontend, records, backend/tests/)."""
    repo, env, git = _scratch_repo(tmp_path)
    detect = _detect_step(_workflow())["run"]
    _commit(repo, git, "base", {"backend/app/a.py": "A = 0\n", "backend/app/b.py": "B = 0\n"})
    first = _commit(repo, git, "first backend merge", {"backend/app/a.py": "A = 1\n"})
    second = _commit(repo, git, "second backend merge", {"backend/app/b.py": "B = 1\n"})
    third = _commit(repo, git, "third backend merge", {"backend/app/a.py": "A = 2\n"})
    git("push", "-q", "origin", "HEAD:main")

    def decide(commit, label):
        # Each deploy job has a fresh checkout; the detector's shallow fetch of main must not leak
        # into the next decision, so each one runs in its own copy of the repository.
        workspace = tmp_path / f"workspace-{label}"
        shutil.copytree(repo, workspace, symlinks=True)
        subprocess.run(["git", "checkout", "-q", "--detach", commit], cwd=workspace, env=env, check=True,
                       capture_output=True, timeout=30)
        output = tmp_path / f"github-output-{label}"
        result = subprocess.run(["bash", "-e", "-c", detect], capture_output=True, text=True, cwd=workspace,
                                env={**env, "GITHUB_OUTPUT": str(output)}, timeout=30, check=False)
        assert (result.returncode, result.stderr) == (0, ""), result.stderr
        return output.read_text().strip(), result.stdout

    assert decide(third, "newest")[0] == "backend=true"
    for commit, label in ((first, "first"), (second, "second")):
        decision, stdout = decide(commit, label)
        assert decision == "backend=false" and f"Main is at {third[:7]}" in stdout, (label, stdout)

    # Main moves on with changes the image does not hold: the newest backend merge still deploys.
    git("checkout", "-q", "main")
    _commit(repo, git, "records, frontend and tests", {
        "tasks/todo.md": "row\n", "frontend/app/page.tsx": "export {}\n",
        "backend/tests/unit/test_a.py": "def test_a():\n    assert True\n",
    })
    git("push", "-q", "origin", "HEAD:main")
    assert decide(third, "newest-after-records")[0] == "backend=true"
    assert decide(second, "second-after-records")[0] == "backend=false"


def test_a_failed_read_of_main_fails_the_detector_and_deploys_nothing(tmp_path):
    """Without main's tip, the detector cannot tell a current commit from a superseded one: the step
    fails, and nothing deploys, rather than shipping a possibly older image."""
    repo, env, git = _scratch_repo(tmp_path)
    _commit(repo, git, "base", {"backend/app/a.py": "A = 0\n"})
    _commit(repo, git, "backend merge", {"backend/app/a.py": "A = 1\n"})
    git("remote", "set-url", "origin", (tmp_path / "unreachable.git").as_uri())
    output = tmp_path / "github-output-unreachable"
    result = subprocess.run(["bash", "-e", "-c", _detect_step(_workflow())["run"]], capture_output=True,
                            text=True, cwd=repo, env={**env, "GITHUB_OUTPUT": str(output)}, timeout=30,
                            check=False)
    assert result.returncode != 0
    assert "backend=true" not in (output.read_text() if output.exists() else "")


REPORT_STEP = "Report variable-driven rollout switches"
# `vars.NAME` and the index form `vars['NAME']` / `vars["NAME"]`.
VAR_REF = re.compile(r"\bvars(?:\.([A-Za-z_]\w*)|\[\s*['\"]([A-Za-z_]\w*)['\"]\s*\])")
AUTH_IDENTITY = {"GCP_WIF_PROVIDER", "GCP_DEPLOYER_SA"}  # who deploys, not what the deploy applies


def _var_names(node):
    """Every repository variable a parsed workflow fragment reads, from its raw keys and values."""
    if isinstance(node, dict):
        return set().union(*(_var_names(key) | _var_names(value) for key, value in node.items()))
    if isinstance(node, list):
        return set().union(*(_var_names(item) for item in node))
    return {name for match in VAR_REF.findall(str(node)) for name in match if name}


def test_deploy_reports_every_variable_driven_switch(tmp_path):
    """Repository variables change without a commit, so a deploy can roll out more than its diff: PR
    #1131's merge rolled out durable tasks switched on hours earlier (CODE RED decision record 17).
    Every deploy-backend env entry set from a repository variable is printed by an ungated step that
    runs before the detector, so every main push, deploying or not, shows what a deploy would apply.
    A variable read anywhere else in the job (a step's env, `with` or `run`, the job `if`) or in the
    workflow-level env fails, apart from the deploy identity, so every switch goes through the reported
    job env. The gate makes the values readable; reading them before a merge stays a review rule."""
    workflow = _workflow()
    deploy = workflow["jobs"]["deploy-backend"]
    names = [step.get("name") for step in deploy["steps"]]
    report = next(step for step in deploy["steps"] if step.get("name") == REPORT_STEP)
    assert "if" not in report and names.index(REPORT_STEP) < names.index("Detect backend changes")
    switches = [key for key, value in deploy["env"].items() if VAR_REF.search(value)]
    assert switches, "deploy-backend reads no repository variable: update this gate"
    outside = {**deploy, "env": {key: value for key, value in deploy["env"].items() if key not in switches},
               "workflow-level env": workflow.get("env", {})}
    stray = _var_names(outside) - AUTH_IDENTITY
    assert not stray, f"repository variables read outside the reported job env: {sorted(stray)}"
    sentinels = {key: f"sentinel-{index}" for index, key in enumerate(switches)}
    probe = subprocess.run(["bash", "-e", "-c", report["run"]], capture_output=True, text=True, timeout=30,
                           env={**os.environ, **sentinels, "GITHUB_STEP_SUMMARY": str(tmp_path / "probe")})
    assert probe.returncode == 0, probe.stderr
    printed = probe.stdout.split()
    for key, sentinel in sentinels.items():  # what the step prints, not what its source mentions
        assert f"{key}={sentinel}" in printed or f"{key}=set" in printed, f"the deploy does not report {key}"
    summary = tmp_path / "summary"
    env = {**os.environ, "DURABLE_TASKS_ENABLED": "true", "TASKS_WORKER_URL": "https://worker.example",
           "GITHUB_STEP_SUMMARY": str(summary)}
    result = subprocess.run(["bash", "-e", "-c", report["run"]], capture_output=True, text=True, env=env,
                            timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    line = "Variable-driven rollout switches: DURABLE_TASKS_ENABLED=true TASKS_WORKER_URL=set"
    assert result.stdout.strip() == line and summary.read_text().strip() == line
