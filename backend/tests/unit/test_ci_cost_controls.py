"""Execute the browser scope on real Git histories; cost controls must fail closed.

Markdown records under tasks/, lessons/ and docs/, plus the two named CODE RED
JSON families, omit browser builds. So does a change confined to backend/ and ops/
files that neither the frontend build nor a browser spec reads: the browser jobs run
the built frontend with no backend. A run that tests nothing skips the test jobs: a
draft pull request's push (the ready mark starts the run that tests the head), a push
to main that deploys nothing (its pull request tested it; a nightly run tests such
merges together) and a nightly run with no new commit. Wherever a run tests a change,
the application, contract, record-validation, policy and migration suites keep their
coverage, and a draft's required checks are never all green.
A computed scope also says whether the change touches the offer (``prices_changed``,
read by the price-agreement job); a scope that falls back to the full suite says
nothing about it, so an unknown scope can never skip that job.
"""

import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
PRICES = "frontend/app/pricing/prices.ts"
CONTROL = "tasks/code-red-20261004/runtime/control"
APPOINTMENTS = f"{CONTROL}/APPOINTMENTS.json"
EXCLUSION = f"{CONTROL}/source-context-exclusion-203.json"
RECORD_PATHS = ("tasks/todo.md", APPOINTMENTS, EXCLUSION)


BROWSER_INPUTS_OUTSIDE_FRONTEND = (
    "backend/tests/fixtures/analysis_later_filings.json",
    "backend/tests/fixtures/analysis_first_reports_produced.json",
    "docs/brand/templates/email-header.html",
)
FULL_SUITE = "records_only=false\nbrowser=true\ntests=true\ndraft=false"  # an unknown scope: nothing about the offer
IDLE_NIGHT = "records_only=false\nbrowser=false\ntests=false\ndraft=false"
# The job conditions: a job skips only where ci-scope succeeded AND wrote the exact value. A scope that failed, was
# skipped, or wrote nothing or anything else runs the job (GitHub's `==` on a missing output is false).
TESTS_IF = "${{ always() && !cancelled() && !(needs.ci-scope.result == 'success' && needs.ci-scope.outputs.tests == 'false') }}"
SHARD_IF = "${{ always() && !cancelled() && !(needs.ci-scope.result == 'success' && needs.ci-scope.outputs.draft == 'true') }}"
BROWSER_RUNNER = "${{ needs.ci-scope.outputs.browser == 'false' && 'ubuntu-slim' || 'ubuntu-latest' }}"


def NOTHING_SKIPPED(output):
    """A scope that failed must write no value a job skips work on."""
    return not {"records_only=true", "prices_changed=false", "browser=false", "tests=false", "draft=true"} & set(output.splitlines())


def scoped(records, prices=False, browser=None, tests=True, draft=False):
    """What a computed scope writes, one line per output. Records never run the browser jobs; any other change
    runs them unless the case says it is confined to backend/ and ops/ files they do not read. `tests` is false where
    the run tests nothing, and `draft` true on a draft pull request alone."""
    browser = (not records) if browser is None else browser
    return "\n".join(f"{name}={str(value).lower()}" for name, value in (
        ("records_only", records), ("prices_changed", prices), ("browser", browser), ("tests", tests), ("draft", draft)))


def workflow():
    return yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)


@pytest.fixture
def history(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    # An empty global config of its own, never /dev/null: a config write would rename git's lock file over it.
    global_config = tmp_path / "gitconfig"
    global_config.write_text("", encoding="utf-8")
    env = {
        **os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": str(global_config),
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


# The stub `gh` the scope step meets: it records each call, then answers the three reads the step makes. The runs on
# main's tip (the nightly run) come from RUNS_ANSWER, a run's backend-tests conclusions from JOBS_ANSWER_<run id> or
# JOBS_ANSWER, and anything else, the pull request's draft flag, from DRAFT_ANSWER.
GH_STUB = r"""#!/bin/sh
printf '%s\n' "$*" >> "$GH_CALLS"
case "$2" in
  */actions/workflows/ci.yml/runs*) printf '%s\n' "$RUNS_ANSWER"; exit "$RUNS_EXIT" ;;
  */actions/runs/*/jobs*)
    run=${2#*/actions/runs/}
    printenv "JOBS_ANSWER_${run%%/*}" || printf '%s\n' "$JOBS_ANSWER"
    exit "$JOBS_EXIT" ;;
esac
printf '%s\n' "$DRAFT_ANSWER"
exit "$GH_EXIT"
"""


def classify(history, tmp_path, event="push", **overrides):
    """Run ci-scope's step. On a pull request it reads the live draft flag through `gh`; a stub answers with
    DRAFT_ANSWER (a ready pull request unless the case says otherwise) and exits with GH_EXIT, and records its
    arguments so a case can check which pull request was read."""
    repo, env, git, _ = history
    output = tmp_path / "output"
    output.unlink(missing_ok=True)
    stub = tmp_path / "stub-bin"
    stub.mkdir(exist_ok=True)
    (stub / "gh").write_text(GH_STUB, encoding="utf-8")
    (stub / "gh").chmod(0o755)
    (tmp_path / "gh-calls").write_text("", encoding="utf-8")
    env = {
        **env, "EVENT_NAME": event, "GITHUB_SHA": git("rev-parse", "HEAD"),
        "BEFORE_SHA": git("rev-parse", "HEAD^"), "PR_HEAD_SHA": "", "PR_NUMBER": "7",
        "GITHUB_REPOSITORY": "owner/repo", "GH_TOKEN": "stub", "DRAFT_ANSWER": "false", "GH_EXIT": "0",
        "RUNS_ANSWER": "", "RUNS_EXIT": "0", "JOBS_ANSWER": "", "JOBS_EXIT": "0",
        "GH_CALLS": str(tmp_path / "gh-calls"), "PATH": f"{stub}{os.pathsep}{env['PATH']}",
        "RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(output), **overrides,
    }
    scope = workflow()["jobs"]["ci-scope"]["steps"][-1]
    result = subprocess.run(
        ["bash", "-e", "-c", scope["run"]], cwd=repo, env=env,
        capture_output=True, text=True, timeout=20, check=False,
    )
    return result, output.read_text().strip() if output.exists() else ""


def merge_as_pull_request(history, *paths, content="record\n"):
    """Commit the paths on a branch off main and merge it as GitHub's test merge does; returns the branch's head."""
    _, _, git, write = history
    branch = f"feature-{git('rev-list', '--count', 'HEAD')}"
    git("switch", "-qc", branch)
    for path in paths:
        write(path, content)
    git("add", ".")
    git("commit", "-qm", "change")
    head = git("rev-parse", "HEAD")
    git("switch", "-q", "main")
    git("merge", "--no-ff", "-qm", "checked merge", branch)
    return head


@pytest.mark.parametrize("path,records,browser", [
    ("tasks/todo.md", True, False),
    ("tasks/archive/a record.md", True, False),
    ("lessons/ops-new.md", True, False),
    ("docs/nested/guide.md", True, False),
    (APPOINTMENTS, True, False),
    (EXCLUSION, True, False),
    (f"{CONTROL}/source-context-exclusion-0.json", True, False),
    (f"{CONTROL}/source-context-exclusion-00203.json", True, False),
    (f"{CONTROL}/appointments.json", False, True),
    (f"{CONTROL}/APPOINTMENTS.json.bak", False, True),
    (f"{CONTROL}/other.json", False, True),
    (f"{CONTROL}/nested/APPOINTMENTS.json", False, True),
    (f"{CONTROL}-other/APPOINTMENTS.json", False, True),
    (f"{CONTROL}/source-context-exclusion-.json", False, True),
    (f"{CONTROL}/source-context-exclusion-1evil.json", False, True),
    (f"{CONTROL}/source-context-exclusion-1evil2.json", False, True),
    (f"{CONTROL}/source-context-exclusion--1.json", False, True),
    (f"{CONTROL}/source-context-exclusion-+1.json", False, True),
    (f"{CONTROL}/source-context-exclusion-1.0.json", False, True),
    (f"{CONTROL}/source-context-exclusion-١.json", False, True),
    (f"{CONTROL}/source-context-exclusion-１.json", False, True),
    (f"{CONTROL}/source-context-exclusion-1١.json", False, True),
    (f"{CONTROL}/source-context-exclusion-1.JSON", False, True),
    (f"{CONTROL}/source-context-exclusion-1.json.bak", False, True),
    (f"{CONTROL}/source-context-exclusion-1/2.json", False, True),
    (f"{CONTROL}/nested/source-context-exclusion-1.json", False, True),
    (f"{CONTROL}-other/source-context-exclusion-1.json", False, True),
    ("other/" + EXCLUSION, False, True),
    ("\n" + EXCLUSION, False, True),
    (EXCLUSION + "\n", False, True),
    (f"{CONTROL}/source-context-exclusion-1\n2.json", False, True),
    ("backend/prompts/summary.md", False, False),
    ("backend/app/config.py", False, False),
    ("backend/migrations/new.sql", False, False),
    ("backend/requirements.txt", False, False),
    ("backend/requirements-dev.txt", False, False),
    ("backend/tests/unit/test_contract.py", False, False),
    ("backend/evals/fixtures/README.md", False, False),
    ("frontend/package-lock.json", False, True),
    ("frontend/app/page.tsx", False, True),
    ("frontend/DESIGN_SYSTEM.md", False, True),
    ("DESIGN.md", False, True),
    ("CLAUDE.md", False, True),
    ("AGENTS.md", False, True),
    (".impeccable/design.json", False, True),
    (".github/workflows/ci.yml", False, True),
    (".github/ai-model.env", False, True),
    (".gitleaksignore", False, True),
    (".claude/workflows/review.ts", False, True),
    ("docs/example.sh", False, True),
    ("tasks/prototype.html", False, True),
    ("lessons/data.json", False, True),
    ("docs-lookalike/guide.md", False, True),
    ("new-shared-config", False, True),
    ("backend/app/new\nfile.md", False, False),
    (PRICES, False, True),
    ("frontend/app/pricing/prices.tsx", False, True),
    ("frontend/app/pricing/prices.ts.bak", False, True),
    # Backend and ops files run no browser job, except the ones a browser check reads.
    ("backend/app/services/summary_pipeline.py", False, False),
    ("backend/tests/fixtures/other.json", False, False),
    ("ops/detection/financial_revenue_state.sql", False, False),
    ("ops/dev/verify.py", False, False),
    *((path, False, True) for path in BROWSER_INPUTS_OUTSIDE_FRONTEND),
    ("backend", False, True),
    ("ops", False, True),
    ("backend-lookalike/app/config.py", False, True),
    ("ops-lookalike/dev/verify.py", False, True),
    ("other/backend/app/config.py", False, True),
    ("\nbackend/app/config.py", False, True),
    ("frontend/backend/app/config.py", False, True),
    ("frontend/package.json", False, True),
    (".github/workflows/eval-baseline-ready.yml", False, True),
    (".github/dependabot.yml", False, True),
    ("README.md", False, True),
])
def test_scope_classifies_real_changes(history, tmp_path, path, records, browser):
    # As a ready pull request, where every job that applies runs: a push to main runs the browser jobs for no
    # change that deploys nothing, so it cannot show which paths they read.
    head = merge_as_pull_request(history, path)
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head)
    assert result.returncode == 0, result.stderr
    assert output == scoped(records, prices=path == PRICES, browser=browser)


@pytest.mark.parametrize("extra_path", [
    None, "backend/app/config.py", "ops/dev/verify.py", "frontend/app/page.tsx", PRICES,
    *BROWSER_INPUTS_OUTSIDE_FRONTEND[:3],
])
def test_scope_classifies_record_bundles_and_mixed_changes(history, tmp_path, extra_path):
    head = merge_as_pull_request(history, *RECORD_PATHS, *([extra_path] if extra_path else []))
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head)
    assert result.returncode == 0, result.stderr
    # One path the browser jobs read runs them, whatever else the change holds.
    browser = extra_path not in (None, "backend/app/config.py", "ops/dev/verify.py")
    assert output == scoped(extra_path is None, prices=extra_path == PRICES, browser=browser)


@pytest.mark.parametrize("record_path,renamed_record_path", [
    ("tasks/todo.md", "tasks/runtime.md"),
    (APPOINTMENTS, EXCLUSION),
    (EXCLUSION, APPOINTMENTS),
])
def test_scope_uses_whole_push_and_preserves_both_rename_sides(
    history, tmp_path, record_path, renamed_record_path,
):
    # The runtime file deploys, so each push that touches it runs the test jobs, and a push that touches it by a
    # rename alone must too: `tests=false` here would mean the rename hid the backend side.
    repo, _, git, write = history
    before = git("rev-parse", "HEAD")
    write("backend/app/runtime.md")
    git("add", ".")
    git("commit", "-qm", "runtime")
    write(record_path)
    git("add", ".")
    git("commit", "-qm", "records tail")
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and output == scoped(False, browser=False)

    # Moving an identical runtime file into records must not hide its deletion.
    git("mv", "backend/app/runtime.md", renamed_record_path)
    git("commit", "-qm", "rename into records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=False)

    git("mv", renamed_record_path, "backend/app/runtime.md")
    git("commit", "-qm", "rename out of records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=False)

    (repo / "backend/app/runtime.md").unlink()
    git("commit", "-qam", "delete runtime")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=False)

    (repo / record_path).unlink()
    git("commit", "-qam", "delete record")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(True, tests=False)


@pytest.mark.parametrize("record_path", RECORD_PATHS)
def test_scope_finds_an_offer_change_anywhere_in_the_change(history, tmp_path, record_path):
    repo, _, git, write = history
    before = git("rev-parse", "HEAD")
    write(PRICES, "export const PRO_PRICING = proPricing(30, 300)\n")
    git("add", ".")
    git("commit", "-qm", "offer")
    write(record_path)
    git("add", ".")
    git("commit", "-qm", "records tail")
    # A push of the offer deploys nothing, so it tests nothing; the scope still reports the offer's change.
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and output == scoped(False, prices=True, browser=False, tests=False)

    # Deleting or renaming the module changes the offer too.
    git("mv", PRICES, "frontend/app/pricing/offer.ts")
    git("commit", "-qm", "rename the offer")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, prices=True, browser=False, tests=False)


@pytest.mark.parametrize("record_path", RECORD_PATHS)
def test_pr_scope_compares_checked_merge_to_its_base_parent(history, tmp_path, record_path):
    _, _, git, write = history
    git("switch", "-qc", "feature")
    write(record_path)
    git("add", ".")
    git("commit", "-qm", "records")
    head = git("rev-parse", "HEAD")
    git("switch", "-q", "main")
    # An unrelated base change must not be mistaken for a change in this PR.
    write("frontend/app/page.tsx", "base-only\n")
    git("add", ".")
    git("commit", "-qm", "base advanced")
    write(PRICES, "base-only offer\n")
    git("add", ".")
    git("commit", "-qm", "base offer advanced")
    git("merge", "--no-ff", "-qm", "checked merge", "feature")
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head)
    assert result.returncode == 0 and output == scoped(True, prices=False)
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA="a" * 40)
    assert result.returncode != 0 and NOTHING_SKIPPED(output)


def test_pr_scope_reports_the_pull_requests_own_offer_change(history, tmp_path):
    _, _, git, write = history
    git("switch", "-qc", "feature")
    write(PRICES, "export const PRO_PRICING = proPricing(20, 200)\n")
    git("add", ".")
    git("commit", "-qm", "offer")
    head = git("rev-parse", "HEAD")
    git("switch", "-q", "main")
    write("tasks/todo.md", "base-only\n")
    git("add", ".")
    git("commit", "-qm", "base advanced")
    git("merge", "--no-ff", "-qm", "checked merge", "feature")
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head)
    assert result.returncode == 0 and output == scoped(False, prices=True)


@pytest.mark.parametrize("record_path", RECORD_PATHS)
def test_unknown_empty_manual_and_mismatched_inputs_never_skip(history, tmp_path, record_path):
    _, _, git, write = history
    write(record_path)
    git("add", ".")
    git("commit", "-qm", "records")
    # An unusable push base falls back to the full suite and says nothing about the offer.
    for overrides in ({"BEFORE_SHA": "0" * 40}, {"BEFORE_SHA": "HEAD^"}, {"BEFORE_SHA": ""}):
        result, output = classify(history, tmp_path, **overrides)
        assert result.returncode == 0 and output == FULL_SUITE
    result, output = classify(history, tmp_path, BEFORE_SHA=git("rev-parse", "HEAD"))
    assert result.returncode == 0 and output == scoped(False)  # an empty change runs everything
    for event in ("workflow_dispatch", "unexpected"):
        result, output = classify(history, tmp_path, event)
        assert result.returncode == 0 and output == FULL_SUITE
    for event, overrides in (("push", {"GITHUB_SHA": "a" * 40}), ("pull_request", {})):
        result, output = classify(history, tmp_path, event, **overrides)
        assert result.returncode != 0 and NOTHING_SKIPPED(output)


@pytest.mark.parametrize("path,deploys", [("backend/app/config.py", True), ("ops/dev/verify.py", False)])
def test_a_backend_or_ops_change_with_an_unknown_scope_runs_every_job(history, tmp_path, path, deploys):
    _, _, git, write = history
    write(path)
    git("add", ".")
    git("commit", "-qm", "backend")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=False, tests=deploys)
    for overrides in ({"BEFORE_SHA": "0" * 40}, {"BEFORE_SHA": ""}):
        result, output = classify(history, tmp_path, **overrides)
        assert result.returncode == 0 and output == FULL_SUITE
    for event in ("workflow_dispatch", "unexpected"):
        result, output = classify(history, tmp_path, event)
        assert result.returncode == 0 and output == FULL_SUITE
    result, output = classify(history, tmp_path, GITHUB_SHA="a" * 40)
    assert result.returncode != 0 and NOTHING_SKIPPED(output)


@pytest.mark.parametrize("paths,records,browser", [
    (("frontend/app/page.tsx",), False, True),
    (("backend/app/config.py",), False, False),
    (("backend/app/config.py", "frontend/app/page.tsx", "tasks/todo.md"), False, True),
    (("tasks/todo.md",), True, False),
    ((PRICES,), False, True),
])
def test_a_draft_runs_no_test_job_and_the_ready_pull_request_runs_them(history, tmp_path, paths, records, browser):
    # The draft flag is the one `gh` reads now, never the event's: a payload can still say draft after the ready
    # mark (#1315). Only its exact "true" skips the test jobs.
    head = merge_as_pull_request(history, *paths)
    prices = PRICES in paths
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head, DRAFT_ANSWER="true")
    assert result.returncode == 0, result.stderr
    assert output == scoped(records, prices=prices, browser=browser, tests=False, draft=True)
    assert "::notice title=Draft: the test jobs did not run::" in result.stdout
    assert (tmp_path / "gh-calls").read_text() == "api repos/owner/repo/pulls/7 --jq .draft\n"
    result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head, DRAFT_ANSWER="false")
    assert result.returncode == 0 and output == scoped(records, prices=prices, browser=browser)
    assert "::" not in result.stdout
    # A read that fails, or answers anything else, runs every job the change calls for, and says so.
    for unreadable in ({"DRAFT_ANSWER": ""}, {"DRAFT_ANSWER": "null"}, {"DRAFT_ANSWER": "True"}, {"DRAFT_ANSWER": "true\ntrue"},
                       {"DRAFT_ANSWER": "true", "GH_EXIT": "1"}, {"DRAFT_ANSWER": "true", "PR_NUMBER": ""},
                       {"DRAFT_ANSWER": "true", "PR_NUMBER": "7/../8"}, {"DRAFT_ANSWER": "true", "PR_NUMBER": "0"}):
        result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head, **unreadable)
        assert result.returncode == 0 and output == scoped(records, prices=prices, browser=browser), unreadable
        assert "::warning::Cannot read whether this pull request is a draft; running every job." in result.stdout


def deploy_detector():
    """deploy-backend's own rule for a path that deploys, as its "Detect backend changes" step defines it."""
    step = next(each for each in workflow()["jobs"]["deploy-backend"]["steps"] if each.get("id") == "changes")
    (rule,) = [line.strip() for line in step["run"].splitlines() if line.strip().startswith("deployable() {")]
    return rule


@pytest.mark.parametrize("path,deploys", [
    ("backend/app/config.py", True),
    ("backend/migrations/new.sql", True),
    ("backend/requirements.txt", True),
    ("backend/Dockerfile", True),
    ("backend/scripts/apply_migrations.sh", True),
    ("backend/prompts/summary.md", True),
    ("backend/testsuite/x.py", True),
    ("backend/tests", True),
    ("backend/tests/unit/test_contract.py", False),
    ("backend/tests/fixtures/analysis_later_filings.json", False),
    ("backendish/app/config.py", False),
    ("other/backend/app/config.py", False),
    ("frontend/app/page.tsx", False),
    ("frontend/package-lock.json", False),
    (".github/workflows/ci.yml", False),
    ("ops/dev/verify.py", False),
    ("tasks/todo.md", False),
    ("CLAUDE.md", False),
])
def test_a_push_to_main_runs_the_test_jobs_exactly_when_it_deploys(history, tmp_path, path, deploys):
    # deploy-backend needs the test jobs, so a push it would deploy must run them: a skipped job skips the deploy.
    # The scope's rule is held to the deploy job's own, run here on the same path.
    _, _, git, write = history
    write(path)
    git("add", ".")
    git("commit", "-qm", "merge")
    detector = subprocess.run(
        ["bash", "-c", f"{deploy_detector()}; printf '%s\\n' \"$1\" | deployable", "detector", path],
        capture_output=True, text=True, timeout=10, check=False)
    assert (detector.returncode == 0) == deploys, "this case's `deploys` disagrees with deploy-backend's rule"
    result, output = classify(history, tmp_path)
    assert result.returncode == 0, result.stderr
    assert f"tests={str(deploys).lower()}" in output.splitlines()
    if not deploys:
        # It tests nothing, so the browser legs run with their steps skipped and e2e-tests passes: main stays green.
        assert {"browser=false", "draft=false"} <= set(output.splitlines())
        assert "This push deploys nothing" in result.stdout


def test_a_push_runs_the_test_jobs_when_any_commit_range_deploys(history, tmp_path):
    # deploy-backend reads HEAD^..HEAD; the scope reads the whole push. A push whose last commit deploys must run
    # the test jobs even where the push's net change does not (a file added, then removed).
    repo, _, git, write = history
    before = git("rev-parse", "HEAD")
    write("backend/app/added.py")
    git("add", ".")
    git("commit", "-qm", "add")
    (repo / "backend/app/added.py").unlink()
    write("tasks/todo.md")
    git("add", "-A")
    git("commit", "-qm", "remove, and a record")
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and "tests=true" in output.splitlines()
    # The reverse: the last commit is a record, the push's first deploys.
    before = git("rev-parse", "HEAD")
    write("backend/app/kept.py")
    git("add", ".")
    git("commit", "-qm", "deploys")
    write("lessons/ops-new.md")
    git("add", ".")
    git("commit", "-qm", "record")
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and "tests=true" in output.splitlines()
    result, output = classify(history, tmp_path)  # that record alone, as its own push
    assert result.returncode == 0 and output == scoped(True, tests=False)


def test_the_nightly_run_tests_main_unless_a_run_already_tested_its_tip(history, tmp_path):
    # Whether main's tip is tested is read from the runs made on it, never from its age or its paths: GitHub can drop
    # a scheduled run, and a push can get no run at all (#2005). Only a completed push or nightly run whose
    # backend-tests ran, passed or failed, makes this run idle; an idle run's own backend-tests is skipped.
    _, _, git, write = history
    write("frontend/app/page.tsx")
    git("add", ".")
    git("commit", "-qm", "a merge")
    tip = git("rev-parse", "HEAD")
    result, output = classify(history, tmp_path, "schedule")
    assert result.returncode == 0 and output == FULL_SUITE and "::" not in result.stdout  # no run on the tip yet
    assert (tmp_path / "gh-calls").read_text().startswith(
        f"api repos/owner/repo/actions/workflows/ci.yml/runs?head_sha={tip}&status=completed&per_page=50 --jq ")
    for conclusions, expected in (("success", IDLE_NIGHT), ("failure", IDLE_NIGHT), ("skipped", FULL_SUITE),
                                  ("cancelled", FULL_SUITE), ("", FULL_SUITE), ("skipped success", IDLE_NIGHT),
                                  ("successful", FULL_SUITE)):
        result, output = classify(history, tmp_path, "schedule", RUNS_ANSWER="101", JOBS_ANSWER=conclusions)
        assert result.returncode == 0 and output == expected, (conclusions, output)
        assert ("already tested main's tip" in result.stdout) == (expected == IDLE_NIGHT)
    # Several runs on the tip: last night's idle one, and the one before it that ran the suites.
    result, output = classify(history, tmp_path, "schedule", RUNS_ANSWER="101\n102",
                              JOBS_ANSWER_101="skipped", JOBS_ANSWER_102="success")
    assert result.returncode == 0 and output == IDLE_NIGHT
    assert [call.split(" --jq ")[0] for call in (tmp_path / "gh-calls").read_text().splitlines()[1:]] == [
        "api repos/owner/repo/actions/runs/101/jobs?per_page=100", "api repos/owner/repo/actions/runs/102/jobs?per_page=100"]
    result, output = classify(history, tmp_path, "schedule", RUNS_ANSWER="101\n102",
                              JOBS_ANSWER_101="skipped", JOBS_ANSWER_102="cancelled")
    assert result.returncode == 0 and output == FULL_SUITE
    # A read that fails, or answers something that is not a run, runs every job and says so.
    for unreadable in ({"RUNS_EXIT": "1"}, {"RUNS_ANSWER": "101", "JOBS_EXIT": "1", "JOBS_ANSWER": "success"},
                       {"RUNS_ANSWER": "not-a-run", "JOBS_ANSWER": "success"},
                       {"RUNS_ANSWER": "101/../102", "JOBS_ANSWER": "success"}):
        result, output = classify(history, tmp_path, "schedule", **unreadable)
        assert result.returncode == 0 and output == FULL_SUITE, unreadable
        assert "::warning::Cannot read whether main's tip is already tested; running every job." in result.stdout


SCANNED_SUFFIXES = {".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs", ".cjs", ".css"}


def outside_frontend_references(frontend=None, specs=True):
    """Files outside frontend/ that the frontend's build or browser specs name in a path literal.

    The browser jobs build frontend/ and run tests/e2e against it. A spec can read any file; a shipped file may
    read none outside frontend/ (test_frontend_build_filter.py), and the scan reads both. Each quoted literal
    that holds ``../`` is resolved two ways: against its file's directory, as an import or a ``__dirname`` join
    reads it, and against frontend/, the directory the jobs run in, as a bare ``readFileSync('../backend/x')`` reads
    it (kept only when the file exists, since most literals are meant the first way). A literal under the ``@/``
    alias is resolved against frontend/ alone. tests/unit runs in frontend-tests, which no scope skips, so it is
    read only where a scanned file imports from it; scripts/ holds tools no CI browser job runs, and .open-next/
    and .wrangler/ are the untracked output of a local Workers build (`npm run cf:build`). A path built from
    separate segments (``path.join(dir, '..', 'backend')``) is outside this check: write such a path as one literal.

    ``specs=False`` reads the build alone, as Vercel runs it (test_frontend_build_filter.py): no file under tests/
    starts the scan, and one is read only where a shipped file imports it.
    """
    frontend = frontend or ROOT / "frontend"
    root = frontend.parent
    literal = re.compile(r"""['"`]([^'"`\n]*\.\./[^'"`\n]*)['"`]""")
    found = {}

    def scanned(path):
        relative = path.relative_to(frontend)
        return (path.is_file() and path.suffix in SCANNED_SUFFIXES
                and relative.parts[0] not in {"node_modules", ".next", ".open-next", ".wrangler", "scripts"})

    def starts_the_scan(path):
        parts = path.relative_to(frontend).parts
        return parts[:2] != ("tests", "unit") if specs else parts[0] != "tests"

    queue = [path for path in sorted(frontend.rglob("*")) if scanned(path) and starts_the_scan(path)]
    seen = set(queue)
    while queue:
        source = queue.pop()
        relative = source.relative_to(frontend).as_posix()
        for match in literal.finditer(source.read_text(encoding="utf-8")):
            text = match.group(1).removeprefix("${__dirname}/")
            aliased = text.startswith("@/")
            for base in ([frontend] if aliased else [source.parent, frontend]):
                target = Path(os.path.normpath(base / text.removeprefix("@/")))
                if target == frontend or frontend in target.parents:
                    # A test module or fixture that a scanned file imports is read with it. With the specs, that
                    # is a tests/unit one, since everything else under tests/ already started the scan.
                    for module in (target, *(target.with_name(target.name + suffix) for suffix in SCANNED_SUFFIXES)):
                        if module not in seen and frontend / "tests" in module.parents and scanned(module):
                            seen.add(module)
                            queue.append(module)
                elif base == source.parent and not aliased or root in target.parents and target.exists():
                    found.setdefault(target, relative)
    return found


def test_the_scan_reads_each_way_a_frontend_file_names_a_file_outside_frontend(tmp_path):
    frontend = tmp_path / "frontend"
    planted = {
        "tests/e2e/dirname.spec.ts": "readFileSync(path.join(__dirname, '../../../backend/a.json'))",
        "tests/e2e/cwd.spec.ts": "readFileSync('../backend/b.json')",
        "tests/e2e/template.spec.ts": "readFileSync(`${__dirname}/../../../backend/c.json`)",
        "lib/alias.ts": "import x from '@/../backend/d.json'",
        "tests/e2e/through-unit.spec.ts": "import { helper } from '../unit/helper'",
        "tests/unit/helper.ts": "export const helper = readFileSync('../backend/e.json')",
        "app/page.css": "@import '../../backend/f.css';",
        # Not references: a unit spec nothing scanned imports, a tool under scripts/, and paths that stay inside.
        "tests/unit/alone.spec.ts": "readFileSync('../backend/unit-only.json')",
        "scripts/tool.mjs": "readFileSync('../backend/tool-only.json')",
        "tests/e2e/inside.spec.ts": "import y from '../../lib/alias'; import z from '../unit/missing'",
    }
    for name, text in planted.items():
        (frontend / name).parent.mkdir(parents=True, exist_ok=True)
        (frontend / name).write_text(text + "\n", encoding="utf-8")
    backend = tmp_path / "backend"
    backend.mkdir()
    for name in ("a.json", "b.json", "c.json", "d.json", "e.json", "f.css", "unit-only.json", "tool-only.json"):
        (backend / name).write_text("{}\n", encoding="utf-8")
    found = outside_frontend_references(frontend)
    assert {path.relative_to(tmp_path).as_posix() for path in found} == {
        "backend/a.json", "backend/b.json", "backend/c.json", "backend/d.json", "backend/e.json", "backend/f.css"}
    # The build alone: what the specs read is left out, until a shipped file imports the module that reads it.
    build_alone = outside_frontend_references(frontend, specs=False)
    assert {path.relative_to(tmp_path).as_posix() for path in build_alone} == {"backend/d.json", "backend/f.css"}
    (frontend / "lib/through-a-spec.ts").write_text("import { helper } from '../tests/unit/helper'\n", encoding="utf-8")
    assert tmp_path / "backend/e.json" in outside_frontend_references(frontend, specs=False)
    (frontend / "lib/through-a-spec.ts").unlink()
    # A literal that leaves frontend/ for a file that is not there is kept, so the gate below fails on it.
    (frontend / "tests/e2e/gone.spec.ts").write_text("readFileSync(path.join(__dirname, '../../../backend/gone.json'))\n")
    assert tmp_path / "backend/gone.json" in outside_frontend_references(frontend)


def test_every_file_a_browser_check_reads_outside_frontend_runs_the_browser_jobs(history, tmp_path):
    # ci-scope skips the browser jobs for a change confined to backend/ and ops/ files, and for records. That holds
    # only while no browser check reads such a file, so each file one does read must be a path the scope runs them
    # for (BROWSER_INPUTS_OUTSIDE_FRONTEND mirrors the scope's list for the planted cases above).
    references = outside_frontend_references()
    assert references, "the scan found no reference at all: its pattern or its file walk is broken"
    targets = set()
    for target, source in references.items():
        assert ROOT in target.parents and target.is_file(), (
            f"frontend/{source} names {target}, which is not a file in the repository: write the whole path as one "
            "literal, so this gate can read which file a browser check depends on")
        targets.add(target.relative_to(ROOT).as_posix())
    assert targets == set(BROWSER_INPUTS_OUTSIDE_FRONTEND), (
        "the files browser checks read outside frontend/ changed: update BROWSER_INPUTS_OUTSIDE_FRONTEND, and name "
        "each new backend/ or ops/ file in ci-scope's browser case in .github/workflows/ci.yml")
    for path in sorted(targets):
        head = merge_as_pull_request(history, path, content=f"changed {path}\n")
        result, output = classify(history, tmp_path, "pull_request", PR_HEAD_SHA=head)
        assert result.returncode == 0 and "browser=true" in output.splitlines(), (path, output)


def test_browser_checks_report_records_and_reject_failed_or_missing_scope(tmp_path):
    jobs = workflow()["jobs"]
    for name in ("e2e-shard", "lighthouse"):  # each browser shard carries the scope guard, not the job summing them
        job = jobs[name]
        assert job["needs"] == ["ci-scope"]
        # Either condition runs the job whenever the scope failed, so the guard below then fails it.
        assert job["if"] == (SHARD_IF if name == "e2e-shard" else TESTS_IF)
        # A leg with no browser input runs the guard and the notice alone, on the 1-core runner; a scope that
        # wrote nothing takes the standard one, where the guard fails.
        assert job["runs-on"] == BROWSER_RUNNER
        guard, records, *steps = job["steps"]
        # The guard alone fails a leg whose scope failed or is missing. With an `if:` of its own it would skip, every
        # step after it would skip too, and the leg would pass; so would a `continue-on-error:` or a `shell:` that runs
        # nothing (E312). The shard job's own keys are pinned in the shards test; lighthouse is advisory by design.
        assert set(guard) == {"name", "env", "run"} and guard["name"] == "Require a valid browser scope"
        assert guard["env"] == {
            "SCOPE_RESULT": "${{ needs.ci-scope.result }}",
            "BROWSER": "${{ needs.ci-scope.outputs.browser }}",
        }
        for state, value in (("success", "true"), ("success", "false"),
                             ("failure", ""), ("cancelled", "true"),
                             ("skipped", ""), ("success", ""), ("success", "bogus")):
            result = subprocess.run(
                ["bash", "-e", "-c", guard["run"]], capture_output=True, text=True,
                env={**os.environ, "SCOPE_RESULT": state, "BROWSER": value},
                timeout=10, check=False,
            )
            assert (result.returncode == 0) == (state == "success" and value in ("true", "false"))
        assert records["if"] == "needs.ci-scope.outputs.browser == 'false'"
        assert "GITHUB_STEP_SUMMARY" in records["run"] and "not applicable" in records["run"]
        assert steps
        for step in steps:
            if step.get("uses", "").startswith("actions/upload-artifact@"):
                assert step["if"] == "failure()"
            else:
                assert step["if"] == "needs.ci-scope.outputs.browser == 'true'"
    assert jobs["ci-scope"]["outputs"]["browser"] == "${{ steps.scope.outputs.browser }}"

    # Keep actual suites and secret scanning on records; don't skip required workflows. The suites skip as whole
    # jobs, and only where the scope says the run tests nothing; no step of theirs skips, and nothing skips the scan.
    assert "if" not in jobs["secret-scan"] and "needs" not in jobs["secret-scan"]
    for name in ("backend-tests", "frontend-tests", "migrations-postgres"):
        assert jobs[name]["needs"] == ["ci-scope"] and jobs[name]["if"] == TESTS_IF
        assert jobs[name]["runs-on"] == "ubuntu-latest"
    for name in ("backend-tests", "frontend-tests", "migrations-postgres", "secret-scan"):
        assert all("if" not in step for step in jobs[name]["steps"])
        assert not {"continue-on-error", "defaults"} & jobs[name].keys()
    assert not {"continue-on-error"} & (jobs["e2e-shard"].keys() | jobs["e2e-tests"].keys())
    for event in ("push", "pull_request"):
        assert not {"paths", "paths-ignore"} & (workflow()["on"][event] or {}).keys()


def test_e2e_tests_keeps_the_founders_35_minute_limit():
    # F59, the founder's decision (2026-10-23): deploy-backend needs e2e-tests, so a run cancelled at the limit skips
    # its deploy, and a slow npm registry or apt mirror adds minutes to the installs. Since the founder chose shards
    # (2026-11-04, #1990), each shard keeps the 35 minutes; the job summing them only reads their result.
    jobs = workflow()["jobs"]
    assert jobs["e2e-shard"]["timeout-minutes"] == "35"
    assert jobs["e2e-tests"]["timeout-minutes"] == "5"


def test_e2e_tests_passes_only_when_every_browser_shard_passed():
    # e2e-tests is the required check and deploy-backend's need, so it must report on every run: GitHub counts a
    # skipped job as passing a required check, and `!cancelled()` would skip it on a cancelled run
    # (lessons/ops-a-required-check-that-sums-other-jobs-never-skips.md).
    ci = workflow()
    jobs = ci["jobs"]
    summary = jobs["e2e-tests"]
    assert summary["needs"] == ["e2e-shard"]
    assert summary["if"] == "${{ always() }}"
    # Every key is pinned: a step `if:` on the result, `continue-on-error:`, a `shell:` or a `defaults:` (the job's or
    # the workflow's) would each pass the job with a shard red while its script still reads right.
    assert set(summary) == {"needs", "if", "runs-on", "timeout-minutes", "steps"}
    assert "defaults" not in ci
    (step,) = summary["steps"]
    assert set(step) == {"name", "env", "run"}
    assert step["env"] == {"SHARDS": "${{ needs.e2e-shard.result }}"}
    for result in ("success", "failure", "cancelled", "skipped", "", "successful"):
        ran = subprocess.run(
            ["bash", "-e", "-c", step["run"]], capture_output=True, text=True,
            env={**os.environ, "SHARDS": result}, timeout=10, check=False,
        )
        assert (ran.returncode == 0) == (result == "success"), (result, ran.returncode)
    # No other job reads a shard directly, so the shards reach the gate and the deploy only through this job.
    assert [name for name, job in jobs.items() if "e2e-shard" in (job.get("needs") or [])] == ["e2e-tests"]


def test_the_browser_shards_cover_the_suite_and_keep_their_evidence_apart():
    # Playwright splits by test count and keeps a file whole unless it runs in parallel mode. At the pace measured on
    # 2026-11-04 (one worker on a 2-vCPU runner), five shards need about 21 minutes each with the installs; two or
    # three would need 28 to 29, too close to the 35-minute limit when a slow mirror adds minutes (#1990).
    shard = workflow()["jobs"]["e2e-shard"]
    assert shard["strategy"] == {"fail-fast": "false", "matrix": {"shard": ["1", "2", "3", "4", "5"]}}
    # A leg must fail when its tests fail: no job `defaults:` and no step's `continue-on-error:` or `shell:`.
    assert set(shard) == {"needs", "if", "runs-on", "timeout-minutes", "strategy", "steps"}
    softened = [step.get("name") for step in shard["steps"] if {"continue-on-error", "shell"} & step.keys()]
    assert softened == [], softened
    run = next(each for each in shard["steps"] if each.get("name") == "Run E2E tests")
    assert set(run) == {"name", "if", "run", "working-directory", "env"}
    # The matrix numbers its shards 1 to N on its only axis, so job-total is N and every test runs in one shard.
    assert run["env"]["SHARD"] == "${{ matrix.shard }}/${{ strategy.job-total }}"
    uploads = [step for step in shard["steps"] if step.get("uses", "").startswith("actions/upload-artifact@")]
    names = [step["with"]["name"] for step in uploads]
    # A run holds one artifact per name, so a shard's failure evidence carries its number.
    assert names == ["playwright-report-${{ matrix.shard }}", "playwright-videos-${{ matrix.shard }}"]


def test_charts_run_in_the_standard_e2e_job_without_a_flag():
    # E195 retires the separate chart build once F67 removes its required check. The standard job already collects
    # every browser spec, including the gallery and D13; neither spec may retain the flag that used to skip it here.
    jobs = workflow()["jobs"]
    assert "e2e-charts-v2" not in jobs
    run = next(each for each in jobs["e2e-shard"]["steps"] if each.get("name") == "Run E2E tests")
    assert run["run"] == 'npx playwright test --shard="$SHARD"'
    assert run["working-directory"] == "frontend"
    assert run["env"] == {
        "PLAYWRIGHT_BASE_URL": "http://localhost:3000", "SHARD": "${{ matrix.shard }}/${{ strategy.job-total }}",
    }
    assert "NEXT_PUBLIC_CHARTS_V2" not in (ROOT / ".github/workflows/ci.yml").read_text()
    flagged = sorted(path.name for path in (ROOT / "frontend/tests/e2e").glob("*.spec.ts") if "CHARTS_V2" in path.read_text())
    assert flagged == [], f"browser specs still read the retired chart flag: {flagged}"


def test_documented_required_checks_are_jobs_a_workflow_runs():
    # docs/OPERATIONS.md names the checks main's ruleset (23561253) requires. Each must be a job some workflow runs: a
    # required check no job reports blocks every pull request. So a job deleted from its workflow (E195's e2e-charts-v2)
    # fails here until the list drops it, and with it the founder's ruleset entry. CONTRIBUTING.md names them too.
    text = (ROOT / "docs/OPERATIONS.md").read_text()
    start = text.index("required status checks")
    listed = re.findall(r"`([a-z0-9-]+)`", text[start:text.index("each pinned to the GitHub Actions app", start)])
    jobs = set()
    for path in (ROOT / ".github/workflows").glob("*.yml"):
        jobs |= set((yaml.load(path.read_text(), Loader=yaml.BaseLoader) or {}).get("jobs", {}))
    assert len(listed) == len(set(listed)) == 7
    assert set(listed) <= jobs, set(listed) - jobs
    contributing = (ROOT / "CONTRIBUTING.md").read_text()
    ci = contributing[contributing.index("## CI"):]
    assert all(f"`{name}`" in ci for name in listed), [name for name in listed if f"`{name}`" not in ci]


def test_cancellation_is_pr_scoped_and_never_groups_main_or_manual_runs():
    ci = workflow()
    # Unique run_id fallbacks prevent queued main/manual runs replacing each other,
    # which cancel-in-progress:false alone would NOT prevent. Neither this group nor eval-baseline's reads the
    # event's action or draft state, so a pull request's ready-mark run and its draft runs supersede one another (F55).
    assert ci["concurrency"] == {
        "group": "ci-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}",
        "cancel-in-progress": "${{ github.event_name == 'pull_request' }}",
    }
    assert ci["on"]["push"]["branches"] == ["main"]
    # Every main push enters this group before its backend-change detector runs.
    # Retain pending jobs so a later nondeploying run cannot replace a waiting release.
    assert ci["jobs"]["deploy-backend"]["concurrency"] == {
        "group": "deploy-backend", "cancel-in-progress": "false", "queue": "max",
    }
    assert set(ci["jobs"]["deploy-backend"]["needs"]) == {
        "backend-tests", "frontend-tests", "migrations-postgres", "e2e-tests", "secret-scan",
    }


def test_the_workers_build_checks_staging_and_never_holds_a_backend_release():
    # Staging's two Workers are built, sized and requested by worker-build (docs/DEPLOYMENT.md, "Frontend on
    # Cloudflare Workers (staging)"). It runs when the test jobs run, and deploy-backend does not wait for it: a
    # fault in the Workers toolchain must not stop a backend release, which is not retried.
    jobs = workflow()["jobs"]
    job = jobs["worker-build"]
    assert job["needs"] == ["ci-scope"] and job["if"] == TESTS_IF and "continue-on-error" not in job
    assert "worker-build" not in jobs["deploy-backend"]["needs"]
    runs = [step.get("run", "") for step in job["steps"]]
    assert "npm run cf:build" in runs
    check = runs[-1]
    # Each size is refused from its limit, and a size the step cannot read is refused too. The front Worker's limit
    # is what keeps the Next server out of it (512 KiB; the server alone is over 3 MiB); the server's is 8 MiB, under
    # Cloudflare's 10.
    assert 'npx wrangler deploy --dry-run -c "$1" > "dry-run-$1.log"' in check
    assert "sed -n 's/.*gzip: \\([0-9]*\\)\\.[0-9]* KiB.*/\\1/p' \"dry-run-$1.log\"" in check
    assert "front_kib=$(gzip_kib wrangler.jsonc)" in check and "server_kib=$(gzip_kib wrangler.server.jsonc)" in check
    assert 'if ! [[ "$front_kib" =~ ^[0-9]+$ ]] || [ "$front_kib" -ge 512 ]; then' in check
    assert 'if ! [[ "$server_kib" =~ ^[0-9]+$ ]] || [ "$server_kib" -ge 8192 ]; then' in check
    # One page through both Workers, rendered by the server Worker, with the copy's headers, and with Sentry's
    # instrumentation loaded: Next words a failed load and a throwing register() differently, and both are refused.
    assert "npx wrangler dev -c wrangler.jsonc -c wrangler.server.jsonc" in check
    assert "grep -qi '^x-nextjs-cache: MISS' headers.txt" in check
    assert "grep -qi '^x-robots-tag: noindex, nofollow' headers.txt" in check
    assert "if grep -qE 'An error occurred while loading (the )?instrumentation hook' wrangler-dev.log; then" in check
    # The front Worker's schedule is run, a reader's request then finds one of its pages in the front Worker's cache,
    # and the schedule is run again: a run that does not pass that cache to the server Worker answers 500. The build
    # names no backend, so none of this calls production.
    assert "wrangler.server.jsonc --test-scheduled --port 8788" in check
    assert "curl -fsS -o /dev/null 'http://127.0.0.1:8788/__scheduled?cron=*+*+*+*+*' || { cat wrangler-dev.log; exit 1; }" in check
    first_run, cached, second_run = (check.index(line) for line in (
        "}\nrun_schedule\nsleep 2\n",
        "grep -qi '^x-opennext-cache: HIT' cached.txt\n",
        "itself throws, and this answers 500.\nrun_schedule\n",
    ))
    assert first_run < cached < second_run
    build = next(step for step in job["steps"] if step.get("run") == "npm run cf:build")
    assert build["env"] == {"NEXT_PUBLIC_API_BASE_URL": "http://localhost:8000"}
    assert all("if" not in step and "continue-on-error" not in step for step in job["steps"])
    # No step may reach a Cloudflare account: the job holds no credential.
    assert "CLOUDFLARE" not in str(job) and "secrets." not in str(job)


def test_the_ready_mark_starts_the_run_that_tests_the_head_and_the_paid_eval():
    # A draft's pushes run no test job, and drafts draw no eval-baseline (F55; test_eval_parity.py runs its scope
    # shell against the live draft flag), so the ready mark must start a run of its own: the first to test the head.
    # The three default types still start a run on each head, which scans it for secrets and, when the pull request
    # is ready, tests it. The eval job runs on a pull request or a dispatch, never on a push or the nightly run.
    ci = workflow()
    assert ci["on"]["pull_request"]["types"] == ["opened", "synchronize", "reopened", "ready_for_review"]
    assert ci["jobs"]["eval-baseline"]["if"] == (
        "github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'")
    assert not {"env", "defaults"} & ci.keys()


def test_a_draft_never_shows_every_required_check_green():
    # GitHub counts a skipped job as passing a required check, and a draft's push skips the test jobs. A ready mark
    # whose run GitHub never starts (2026-11-04: lessons/ops-a-ready-mark-runs-ci-on-the-merge-commit-of-the-last-push.md)
    # would then leave a ready pull request with every check green and nothing tested. So on a draft e2e-shard skips
    # as a whole job, and e2e-tests, a required check that always runs, fails on any shard result but success.
    jobs = workflow()["jobs"]
    scope = jobs["ci-scope"]
    assert scope["outputs"]["tests"] == "${{ steps.scope.outputs.tests }}"
    assert scope["outputs"]["draft"] == "${{ steps.scope.outputs.draft }}"
    assert scope["permissions"] == {"contents": "read", "pull-requests": "read", "actions": "read"}
    # The scope reads history (HEAD^ and a pull request's merge parents) and GitHub (the draft flag, the tip's
    # runs). Without either it fails, or reads every draft as unreadable and tests it: safe, and the whole saving gone.
    checkout, step = scope["steps"]
    assert checkout["with"] == {"fetch-depth": "2", "persist-credentials": "false"}
    assert step["env"] == {
        "EVENT_NAME": "${{ github.event_name }}", "PR_HEAD_SHA": "${{ github.event.pull_request.head.sha }}",
        "PR_NUMBER": "${{ github.event.pull_request.number }}", "BEFORE_SHA": "${{ github.event.before }}",
        "GH_TOKEN": "${{ github.token }}",
    }
    assert jobs["e2e-shard"]["if"] == SHARD_IF
    summary = jobs["e2e-tests"]
    assert summary["needs"] == ["e2e-shard"] and summary["if"] == "${{ always() }}"
    ran = subprocess.run(["bash", "-e", "-c", summary["steps"][0]["run"]], capture_output=True, text=True,
                         env={**os.environ, "SHARDS": "skipped"}, timeout=10, check=False)
    assert ran.returncode != 0
    # The draft output is true only with tests=false, so no run skips the shards while it runs the suites.
    text = scope["steps"][-1]["run"]
    assert text.count("DRAFT=true") == 1 and re.search(r"TESTS=false\n\s*DRAFT=true\n", text)
    # deploy-backend needs every test job and e2e-tests, so a push that skipped them skips the deploy too; the
    # scope never skips them on a push that deploys (test_a_push_to_main_runs_the_test_jobs_exactly_when_it_deploys).
    # Its condition names no status function (always, cancelled, failure, success), so a skipped need skips it.
    assert jobs["deploy-backend"]["if"] == (
        "github.event_name == 'push' && github.ref == 'refs/heads/main' && vars.GCP_WIF_PROVIDER != ''")


def test_the_nightly_run_reports_a_failed_job_in_an_issue():
    # A merge that deploys nothing runs no test job on main; the nightly run tests those merges together, and
    # nobody watches a scheduled run, so its failure must leave an issue (test_scheduled_workflows_fail_loud.py
    # holds the other scheduled workflows to the same).
    ci = workflow()
    assert [entry["cron"] for entry in ci["on"]["schedule"]] == ["17 4 * * *"]
    reporter = ci["jobs"]["report-failure"]
    assert set(reporter) == {"needs", "if", "runs-on", "timeout-minutes", "permissions", "steps"}
    assert set(reporter["needs"]) == set(ci["jobs"]["deploy-backend"]["needs"])
    assert reporter["if"] == ("${{ always() && github.event_name == 'schedule' && "
                              "(contains(needs.*.result, 'failure') || contains(needs.*.result, 'cancelled')) }}")
    assert reporter["permissions"] == {"issues": "write"}
    (step,) = reporter["steps"]
    assert "if" not in step and step["env"]["GH_TOKEN"] and step["env"]["GH_REPO"] == "${{ github.repository }}"
    executable = "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))
    assert "gh issue create " in executable and "gh issue comment " in executable
    # Run the step with a stub `gh`: no open issue creates one, an open one takes a comment, and both carry the
    # run's link and each job's result.
    for existing, expected in (("", "issue create"), ("41", "issue comment 41")):
        import tempfile
        with tempfile.TemporaryDirectory() as scratch:
            stub = Path(scratch) / "gh"
            stub.write_text(
                '#!/bin/sh\ncase "$2" in list) printf \'%s\' "$EXISTING" ;; *) printf \'%s\\n\' "$*" >> "$CALLS"; '
                'for a in "$@"; do p="$n"; n="$a"; [ "$p" = --body-file ] && cat "$a" >> "$CALLS"; done ;; esac\n')
            stub.chmod(0o755)
            calls = Path(scratch) / "calls"
            ran = subprocess.run(
                ["bash", "-e", "-c", step["run"]], capture_output=True, text=True, timeout=20, check=False,
                env={**os.environ, "PATH": f"{scratch}{os.pathsep}{os.environ['PATH']}", "EXISTING": existing,
                     "CALLS": str(calls), "RUN_URL": "https://example.invalid/run/1", "TIP": "0123456789abcdef",
                     "RESULTS": '{"backend-tests": {"result": "failure"}, "e2e-tests": {"result": "success"}}'})
            assert ran.returncode == 0, ran.stderr
            said = calls.read_text()
            assert expected in said and "https://example.invalid/run/1" in said and "(0123456)" in said
            assert "- backend-tests: failure" in said and "- e2e-tests: success" in said


def test_no_ci_job_can_run_for_the_six_hour_default_and_one_core_jobs_fit_their_runner():
    # A job with no limit runs until GitHub's 6-hour default when it hangs: 360 billed minutes for one push.
    jobs = workflow()["jobs"]
    for job_name, job in jobs.items():
        assert job.get("timeout-minutes", "").isdigit() and 1 <= int(job["timeout-minutes"]) <= 60, job_name
    # GitHub bills the 1-core runner at a third of the standard rate, stops its jobs at 15 minutes, and runs it in
    # an unprivileged container: no service containers and no Docker. Only jobs that run seconds of shell use it.
    slim = {job_name: job for job_name, job in jobs.items() if job["runs-on"] == "ubuntu-slim"}
    assert set(slim) == {"ci-scope", "secret-scan", "e2e-tests", "report-failure"}
    for job_name, job in slim.items():
        assert int(job["timeout-minutes"]) <= 15, job_name
        assert not {"services", "container"} & job.keys(), job_name
        assert not [step for step in job["steps"] if step.get("uses", "").startswith("docker/")], job_name
    # The browser jobs take it only for a leg with no browser input, whose steps past the guard and the notice all
    # skip (test_browser_checks_report_records_and_reject_failed_or_missing_scope pins each step's condition).
    assert {job_name for job_name, job in jobs.items() if "ubuntu-slim" in job["runs-on"]} - set(slim) == {"e2e-shard", "lighthouse"}
    assert jobs["e2e-shard"]["runs-on"] == jobs["lighthouse"]["runs-on"] == BROWSER_RUNNER


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
