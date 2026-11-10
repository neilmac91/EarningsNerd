"""Execute the browser scope on real Git histories; cost controls must fail closed.

Markdown records under tasks/, lessons/ and docs/, plus the two named CODE RED
JSON families, omit browser builds. So does a change confined to backend/ and ops/
files that neither the frontend build nor a browser spec reads: the browser jobs run
the built frontend with no backend. All application, contract, record-validation,
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


BROWSER_INPUTS_OUTSIDE_FRONTEND = (
    "backend/app/public_email_addresses.json",
    "backend/tests/fixtures/analysis_later_filings.json",
    "backend/tests/fixtures/analysis_first_reports_produced.json",
    "docs/brand/templates/email-header.html",
)
FULL_SUITE = "records_only=false\nbrowser=true"  # what an unknown scope writes: nothing about the offer


def NOTHING_SKIPPED(output):
    """A scope that failed must write no value a job skips work on."""
    return not {"records_only=true", "prices_changed=false", "browser=false"} & set(output.splitlines())


def scoped(records, prices=False, browser=None):
    """What a computed scope writes, one line per output. Records never run the browser jobs; any other change
    runs them unless the case says it is confined to backend/ and ops/ files they do not read."""
    browser = (not records) if browser is None else browser
    return (f"records_only={str(records).lower()}\nprices_changed={str(prices).lower()}"
            f"\nbrowser={str(browser).lower()}")


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
    _, _, git, write = history
    write(path)
    git("add", ".")
    git("commit", "-qm", "change")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0, result.stderr
    assert output == scoped(records, prices=path == PRICES, browser=browser)


@pytest.mark.parametrize("extra_path", [
    None, "backend/app/config.py", "ops/dev/verify.py", "frontend/app/page.tsx", PRICES,
    *BROWSER_INPUTS_OUTSIDE_FRONTEND[:3],
])
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
    # One path the browser jobs read runs them, whatever else the change holds.
    browser = extra_path not in (None, "backend/app/config.py", "ops/dev/verify.py")
    assert output == scoped(extra_path is None, prices=extra_path == PRICES, browser=browser)


@pytest.mark.parametrize("runtime_path,browser", [("backend/app/runtime.md", False), ("frontend/app/runtime.md", True)])
@pytest.mark.parametrize("record_path,renamed_record_path", [
    ("tasks/todo.md", "tasks/runtime.md"),
    (APPOINTMENTS, EXCLUSION),
    (EXCLUSION, APPOINTMENTS),
])
def test_scope_uses_whole_push_and_preserves_both_rename_sides(
    history, tmp_path, record_path, renamed_record_path, runtime_path, browser,
):
    repo, _, git, write = history
    before = git("rev-parse", "HEAD")
    write(runtime_path)
    git("add", ".")
    git("commit", "-qm", "runtime")
    write(record_path)
    git("add", ".")
    git("commit", "-qm", "records tail")
    result, output = classify(history, tmp_path, BEFORE_SHA=before)
    assert result.returncode == 0 and output == scoped(False, browser=browser)

    # Moving an identical runtime file into records must not hide its deletion.
    git("mv", runtime_path, renamed_record_path)
    git("commit", "-qm", "rename into records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=browser)

    git("mv", renamed_record_path, runtime_path)
    git("commit", "-qm", "rename out of records")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=browser)

    (repo / runtime_path).unlink()
    git("commit", "-qam", "delete runtime")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=browser)

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


@pytest.mark.parametrize("path", ["backend/app/config.py", "ops/dev/verify.py"])
def test_a_backend_or_ops_change_with_an_unknown_scope_runs_the_browser_jobs(history, tmp_path, path):
    _, _, git, write = history
    write(path)
    git("add", ".")
    git("commit", "-qm", "backend")
    result, output = classify(history, tmp_path)
    assert result.returncode == 0 and output == scoped(False, browser=False)
    for overrides in ({"BEFORE_SHA": "0" * 40}, {"BEFORE_SHA": ""}):
        result, output = classify(history, tmp_path, **overrides)
        assert result.returncode == 0 and output == FULL_SUITE
    for event in ("workflow_dispatch", "unexpected"):
        result, output = classify(history, tmp_path, event)
        assert result.returncode == 0 and output == FULL_SUITE
    result, output = classify(history, tmp_path, GITHUB_SHA="a" * 40)
    assert result.returncode != 0 and NOTHING_SKIPPED(output)


def outside_frontend_references():
    """Files outside frontend/ that the frontend's build or browser specs name by a relative path literal.

    The browser jobs build frontend/ and run tests/e2e against it. Turbopack's root is the repository
    (frontend/next.config.js), so an import can leave frontend/, and a spec can read any file. Each quoted literal
    that starts with ``../`` is resolved against its file. tests/unit runs in frontend-tests, which no scope skips,
    and scripts/ holds tools no CI browser job runs, so neither is read. A path built from separate segments
    (``path.join(dir, '..', 'backend')``) is outside this check: write such a path as one literal.
    """
    frontend = ROOT / "frontend"
    literal = re.compile(r"""['"`]((?:\.\./)+[^'"`\n]*)['"`]""")
    found = {}
    for source in sorted(frontend.rglob("*")):
        relative = source.relative_to(frontend)
        if source.suffix not in {".ts", ".tsx", ".mts", ".js", ".jsx", ".mjs", ".cjs"} or not source.is_file():
            continue
        if relative.parts[0] in {"node_modules", ".next", "scripts"} or relative.parts[:2] == ("tests", "unit"):
            continue
        for match in literal.finditer(source.read_text(encoding="utf-8")):
            target = Path(os.path.normpath(source.parent / match.group(1)))
            if target != frontend and frontend not in target.parents:
                found.setdefault(target, relative.as_posix())
    return found


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
    _, _, git, write = history
    for path in sorted(targets):
        write(path, f"changed {path}\n")
        git("add", ".")
        git("commit", "-qm", f"change {path}")
        result, output = classify(history, tmp_path)
        assert result.returncode == 0 and "browser=true" in output.splitlines(), (path, output)


def test_browser_checks_report_records_and_reject_failed_or_missing_scope(tmp_path):
    jobs = workflow()["jobs"]
    for name in ("e2e-shard", "lighthouse"):  # each browser shard carries the scope guard, not the job summing them
        job = jobs[name]
        assert job["needs"] == ["ci-scope"]
        assert job["if"] == "${{ always() && !cancelled() }}"
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

    # Keep actual suites and secret scanning on records; don't skip required workflows.
    for name in ("backend-tests", "frontend-tests", "migrations-postgres", "secret-scan"):
        assert "if" not in jobs[name] and "needs" not in jobs[name]
        assert all("if" not in step for step in jobs[name]["steps"])
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


def test_each_head_reports_required_checks_and_the_ready_mark_starts_only_the_paid_eval():
    # F55: drafts draw no eval-baseline (test_eval_parity.py runs its scope shell against the live draft flag), so the
    # ready mark must start that job on the head the pull request already has. It starts nothing else: a ready mark
    # changes no file, and a CI run on it repeated the head's last run job for job (127 runs on 1-10 November 2026,
    # docs/ops/actions-cost-plan-2026-11.md). So CI keeps the three default types, which report every required check
    # on each head, drafts included, and the ready mark runs a copy of the job from a workflow of its own.
    ci = workflow()
    assert ci["on"]["pull_request"]["types"] == ["opened", "synchronize", "reopened"]
    assert ci["jobs"]["eval-baseline"]["if"] == (
        "github.event_name == 'workflow_dispatch' || github.event_name == 'pull_request'")
    ready = yaml.load((ROOT / ".github/workflows/eval-baseline-ready.yml").read_text(), Loader=yaml.BaseLoader)
    # Nothing but the ready mark starts it, and it holds nothing but the job: a required check's name here would
    # report on the head beside CI's own, and a workflow-level concurrency, env or defaults would change the copy.
    assert set(ready) == {"name", "on", "jobs"}
    assert ready["on"] == {"pull_request": {"types": ["ready_for_review"]}}
    assert set(ready["jobs"]) == {"eval-baseline"}
    # The copy is the job itself, key for key, so the measurement a ready mark starts is the one a push starts.
    assert ready["jobs"]["eval-baseline"] == ci["jobs"]["eval-baseline"]
    assert not {"env", "defaults"} & ci.keys()


def test_no_ci_job_can_run_for_the_six_hour_default_and_one_core_jobs_fit_their_runner():
    # A job with no limit runs until GitHub's 6-hour default when it hangs: 360 billed minutes for one push.
    slim = {}
    for name in ("ci.yml", "eval-baseline-ready.yml"):
        for job_name, job in yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)["jobs"].items():
            assert job.get("timeout-minutes", "").isdigit() and 1 <= int(job["timeout-minutes"]) <= 60, (name, job_name)
            if job["runs-on"] == "ubuntu-slim":
                slim[job_name] = job
    # GitHub bills the 1-core runner at a third of the standard rate, stops its jobs at 15 minutes, and runs it in
    # an unprivileged container: no service containers and no Docker. Only jobs that run seconds of shell use it.
    assert set(slim) == {"ci-scope", "secret-scan", "e2e-tests"}
    for job_name, job in slim.items():
        assert int(job["timeout-minutes"]) <= 15, job_name
        assert not {"services", "container"} & job.keys(), job_name
        assert not [step for step in job["steps"] if step.get("uses", "").startswith("docker/")], job_name


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
