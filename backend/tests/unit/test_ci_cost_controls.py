"""Execute the browser scope on real Git histories; cost controls must fail closed.

Markdown records under tasks/, lessons/ and docs/, plus the two named CODE RED
JSON families, omit browser builds. All application, contract, record-validation,
policy and migration suites retain their existing coverage.
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


def scoped(records, prices=False):
    """What a computed scope writes, one line per output."""
    return f"records_only={str(records).lower()}\nprices_changed={str(prices).lower()}"


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
    (APPOINTMENTS, True),
    (EXCLUSION, True),
    (f"{CONTROL}/source-context-exclusion-0.json", True),
    (f"{CONTROL}/source-context-exclusion-00203.json", True),
    (f"{CONTROL}/appointments.json", False),
    (f"{CONTROL}/APPOINTMENTS.json.bak", False),
    (f"{CONTROL}/other.json", False),
    (f"{CONTROL}/nested/APPOINTMENTS.json", False),
    (f"{CONTROL}-other/APPOINTMENTS.json", False),
    (f"{CONTROL}/source-context-exclusion-.json", False),
    (f"{CONTROL}/source-context-exclusion-1evil.json", False),
    (f"{CONTROL}/source-context-exclusion-1evil2.json", False),
    (f"{CONTROL}/source-context-exclusion--1.json", False),
    (f"{CONTROL}/source-context-exclusion-+1.json", False),
    (f"{CONTROL}/source-context-exclusion-1.0.json", False),
    (f"{CONTROL}/source-context-exclusion-١.json", False),
    (f"{CONTROL}/source-context-exclusion-１.json", False),
    (f"{CONTROL}/source-context-exclusion-1١.json", False),
    (f"{CONTROL}/source-context-exclusion-1.JSON", False),
    (f"{CONTROL}/source-context-exclusion-1.json.bak", False),
    (f"{CONTROL}/source-context-exclusion-1/2.json", False),
    (f"{CONTROL}/nested/source-context-exclusion-1.json", False),
    (f"{CONTROL}-other/source-context-exclusion-1.json", False),
    ("other/" + EXCLUSION, False),
    ("\n" + EXCLUSION, False),
    (EXCLUSION + "\n", False),
    (f"{CONTROL}/source-context-exclusion-1\n2.json", False),
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
    (PRICES, False),
    ("frontend/app/pricing/prices.tsx", False),
    ("frontend/app/pricing/prices.ts.bak", False),
])
def test_scope_classifies_real_changes(history, tmp_path, path, records):
    _, _, git, write = history
    write(path)
    git("add", ".")
    git("commit", "-qm", "change")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0, result.stderr
    assert output == scoped(records, prices=path == PRICES)


@pytest.mark.parametrize("extra_path", [None, "backend/app/config.py", "frontend/app/page.tsx", PRICES])
def test_scope_classifies_record_bundles_and_mixed_changes(history, tmp_path, extra_path):
    _, _, git, write = history
    for path in RECORD_PATHS:
        write(path)
    if extra_path:
        write(extra_path)
    git("add", ".")
    git("commit", "-qm", "record bundle with optional application change")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0, result.stderr
    assert output == scoped(extra_path is None, prices=extra_path == PRICES)


@pytest.mark.parametrize("record_path,renamed_record_path", [
    ("tasks/todo.md", "tasks/runtime.md"),
    (APPOINTMENTS, EXCLUSION),
    (EXCLUSION, APPOINTMENTS),
])
def test_scope_uses_whole_push_and_preserves_both_rename_sides(
    history, tmp_path, record_path, renamed_record_path,
):
    repo, _, git, write = history
    before = git("rev-parse", "HEAD")
    write("backend/app/runtime.md")
    git("add", ".")
    git("commit", "-qm", "runtime")
    write(record_path)
    git("add", ".")
    git("commit", "-qm", "records tail")
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and output == scoped(False)

    # Moving an identical runtime file into records must not hide its deletion.
    git("mv", "backend/app/runtime.md", renamed_record_path)
    git("commit", "-qm", "rename into records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False)

    git("mv", renamed_record_path, "backend/app/runtime.md")
    git("commit", "-qm", "rename out of records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False)

    (repo / "backend/app/runtime.md").unlink()
    git("commit", "-qam", "delete runtime")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False)

    (repo / record_path).unlink()
    git("commit", "-qam", "delete record")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(True)


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
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and output == scoped(False, prices=True)

    # Deleting or renaming the module changes the offer too.
    git("mv", PRICES, "frontend/app/pricing/offer.ts")
    git("commit", "-qm", "rename the offer")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, prices=True)


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
    assert result.returncode != 0 and "records_only=true" not in output and "prices_changed=false" not in output


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
        assert result.returncode == 0 and output == "records_only=false"
    result, output = classify(history, tmp_path, BEFORE_SHA=git("rev-parse", "HEAD"))
    assert result.returncode == 0 and output == scoped(False)  # an empty change runs everything
    for event in ("workflow_dispatch", "unexpected"):
        result, output = classify(history, tmp_path, event)
        assert result.returncode == 0 and output == "records_only=false"
    for event, overrides in (("push", {"GITHUB_SHA": "a" * 40}), ("pull_request", {})):
        result, output = classify(history, tmp_path, event, **overrides)
        assert result.returncode != 0 and "records_only=true" not in output and "prices_changed=false" not in output


def test_browser_checks_report_records_and_reject_failed_or_missing_scope(tmp_path):
    jobs = workflow()["jobs"]
    for name in ("e2e-tests", "e2e-charts-v2", "lighthouse"):
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


def test_e2e_tests_keeps_the_founders_35_minute_limit():
    # F59, the founder's decision (2026-10-23): deploy-backend needs e2e-tests, so a run cancelled at the limit skips
    # its deploy. The suite takes about 20 minutes, and a slow npm registry or apt mirror adds minutes to the installs.
    assert workflow()["jobs"]["e2e-tests"]["timeout-minutes"] == "35"


def test_e2e_charts_v2_keeps_room_for_the_layout_spec():
    # Since E194 the job runs analysis-layout.spec.ts on the renderer: about 14 minutes on CI (2026-10-25), from about
    # 3. It is a required check on main, so a run cancelled at its limit blocks merging until it is re-run.
    assert workflow()["jobs"]["e2e-charts-v2"]["timeout-minutes"] == "30"


def test_charts_v2_job_is_the_e2e_build_with_its_flag_set():
    # NEXT_PUBLIC_ values are inlined at build time (E192): the charts-v2 job builds, serves and tests with the flag, on
    # e2e-tests' own build settings, so the two builds differ in that flag alone.
    jobs = workflow()["jobs"]

    def step(job, name):
        return next(each for each in jobs[job]["steps"] if each.get("name", "").startswith(name))

    flag = {"NEXT_PUBLIC_CHARTS_V2": "true"}
    for name in ("Build frontend", "Start frontend server"):
        assert step("e2e-charts-v2", name)["env"] == {**step("e2e-tests", name)["env"], **flag}
        assert "NEXT_PUBLIC_CHARTS_V2" not in step("e2e-tests", name)["env"]
    run = step("e2e-charts-v2", "Run the charts")
    assert run["env"]["NEXT_PUBLIC_CHARTS_V2"] == "true"
    for spec in ("charts-v2", "charts-v2-gallery", "analysis-layout", "chart-export-fidelity", "analysis-teaser-window"):
        assert f"tests/e2e/{spec}.spec.ts" in run["run"], spec
    assert "tests/e2e/text-floors.spec.ts -g 'analysis: muted ink'" in run["run"]
    # Every spec that reads the flag runs here: one that skips without it (the gallery) runs nowhere else, and one that
    # reads either renderer (analysis-layout) runs on the flag-off build in e2e-tests too.
    flagged = sorted(path.name for path in (ROOT / "frontend/tests/e2e").glob("*.spec.ts") if "CHARTS_V2" in path.read_text())
    assert flagged, "no spec reads the flag"
    assert [name for name in flagged if f"tests/e2e/{name}" not in run["run"]] == []
    # A failing first run never hides the second: each records its status, and the step exits with either's failure.
    lines = [line.strip() for line in run["run"].strip().splitlines()]
    assert lines[0] == "status=0" and lines[-1] == "exit $status"
    assert all(line.endswith("|| status=1") for line in lines[1:-1]) and len(lines) == 4
    assert "continue-on-error" not in jobs["e2e-charts-v2"]


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
    assert len(listed) == len(set(listed)) == 8
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


def test_each_head_reports_required_checks_and_the_ready_mark_starts_the_paid_eval():
    # F55: drafts draw no eval-baseline (test_eval_parity.py runs its scope shell against the live draft flag), so the
    # ready mark must start a run of its own; the three default types keep every required check reporting on each
    # head, drafts included. The job still runs on a pull request or a dispatch, never on a push.
    ci = workflow()
    assert ci["on"]["pull_request"]["types"] == ["opened", "synchronize", "reopened", "ready_for_review"]
    assert ci["jobs"]["eval-baseline"]["if"] == (
        "github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'")


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
