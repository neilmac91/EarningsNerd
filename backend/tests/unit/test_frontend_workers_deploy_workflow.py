"""The workflow that deploys the frontend's Cloudflare Workers copy holds a Cloudflare token and can move a
hostname, so what may start it, what it deploys and what it prints are pinned here
(.github/workflows/deploy-frontend-workers.yml; docs/DEPLOYMENT.md, "Frontend on Cloudflare Workers (staging)" and
"Moving production to Cloudflare Workers")."""
import os
import re
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[3]
PATH = ROOT / ".github/workflows/deploy-frontend-workers.yml"
TEXT = PATH.read_text()
WORKFLOW = yaml.load(TEXT, Loader=yaml.BaseLoader)
JOB = WORKFLOW["jobs"]["deploy-frontend-workers"]
STEPS = {step.get("name", step.get("uses")): step for step in JOB["steps"]}
DEPLOYS = "steps.decide.outputs.deploy == 'true'"


def test_only_a_push_to_main_that_changes_the_build_or_a_dispatch_starts_it():
    # No pull_request trigger of either kind: a pull request's code must never run beside the token.
    assert set(WORKFLOW["on"]) == {"push", "workflow_dispatch"}
    assert WORKFLOW["on"]["push"] == {"branches": ["main"], "paths": ["frontend/**"]}
    # frontend/ is everything the build reads; Vercel's build filter says so and a test holds it to that.
    assert "BUILD_INPUTS=(\n  ':(top)frontend'\n)" in (ROOT / "frontend/scripts/vercel-ignore-build.sh").read_text()
    target = WORKFLOW["on"]["workflow_dispatch"]["inputs"]["target"]
    assert (target["type"], target["options"], target["default"]) == ("choice", ["staging", "production"], "staging")
    assert WORKFLOW["permissions"] == {"contents": "read"}
    assert len(WORKFLOW["jobs"]) == 1
    # A dispatch runs the dispatched branch's copy of this file, and a repository-level secret is readable by any
    # branch's workflow. So the token is held by an environment, which the job names; its setting that admits main
    # only is GitHub's and cannot be read here (docs/DEPLOYMENT.md states it as a founder step).
    assert JOB["environment"] == "frontend-workers"
    deployment = (ROOT / "docs/DEPLOYMENT.md").read_text()
    assert "environment `frontend-workers`" in deployment and "Deployment branches" in deployment


def test_a_push_deploys_staging_and_production_is_deployed_by_dispatch_only():
    # A push carries no inputs, so its target is staging. Production joins the push at the cutover, by a change to
    # this workflow and this test.
    assert JOB["env"] == {"TARGET": "${{ inputs.target || 'staging' }}"}
    run = STEPS["Build and deploy both Workers"]["run"]
    assert 'if [ "$TARGET" = production ]; then\n  npm run cf:deploy:production\nelse\n  npm run cf:deploy\nfi' in run
    scripts = yaml.safe_load((ROOT / "frontend/package.json").read_text())["scripts"]
    assert scripts["cf:deploy"] == "node scripts/cf-deploy.mjs"
    assert scripts["cf:deploy:production"].endswith("wrangler.production.jsonc wrangler.production.server.jsonc")
    # One deploy of a target at a time: a cancelled deploy can stop between its steps. And every waiting run is
    # kept, which takes `queue: max`: the default single pending slot lets a later run replace a waiting one, and
    # the later run may be one that deploys nothing.
    assert WORKFLOW["concurrency"] == {
        "group": "deploy-frontend-workers-${{ inputs.target || 'staging' }}", "cancel-in-progress": "false",
        "queue": "max",
    }
    assert JOB["timeout-minutes"] == "20" and "continue-on-error" not in TEXT


def test_it_deploys_nothing_until_it_is_configured_and_nothing_main_has_moved_past():
    decide = STEPS["Decide whether this run deploys"]
    run = decide["run"]
    # Without the token, the account or the target's values the run says so and stops, so the workflow can be
    # merged before the founder adds them.
    assert 'if [ -z "$CLOUDFLARE_API_TOKEN" ] || [ -z "$CLOUDFLARE_ACCOUNT_ID" ] || [ -z "$BUILD_VALUES" ]; then\n  echo "deploy=false" >> "$GITHUB_OUTPUT"' in run
    # A commit whose frontend/ main no longer holds is not deployed: a newer commit's run deploys main's, and this
    # one after it would put the older build back. Main is read by its full ref, three times at most.
    assert "git fetch --no-tags --quiet --depth=1 origin refs/heads/main" in run
    assert 'if [ "$(git rev-parse HEAD:frontend)" != "$(git rev-parse FETCH_HEAD:frontend)" ]; then\n  echo "deploy=false" >> "$GITHUB_OUTPUT"' in run
    assert run.rstrip().endswith('echo "deploy=true" >> "$GITHUB_OUTPUT"')
    assert run.count('echo "deploy=true"') == 1
    # A failed read of main deploys nothing and fails the run.
    assert 'if [ "$fetched" != true ]; then' in run and "exit 1" in run
    # Every later step waits for that decision.
    later = [step for name, step in STEPS.items() if name not in ("actions/checkout@v7", "Decide whether this run deploys")]
    assert len(later) == 4 and all(DEPLOYS in step["if"] for step in later)
    # And the script it runs makes the same comparison itself, so a dispatch on a branch deploys nothing either.
    deploy = (ROOT / "frontend/scripts/cf-deploy.mjs").read_text()
    assert "if (git('rev-parse', 'HEAD:frontend') !== git('rev-parse', 'FETCH_HEAD:frontend')) {" in deploy


def test_each_target_is_built_with_its_own_values_and_no_value_is_printed():
    for name in ("Decide whether this run deploys", "Build and deploy both Workers"):
        env = STEPS[name]["env"]
        assert env["CLOUDFLARE_API_TOKEN"] == "${{ secrets.CLOUDFLARE_API_TOKEN }}"
        assert env["CLOUDFLARE_ACCOUNT_ID"] == "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}"
        assert env["STAGING_VALUES"] == "${{ vars.FRONTEND_WORKERS_ENV_STAGING }}"
        assert env["PRODUCTION_VALUES"] == "${{ vars.FRONTEND_WORKERS_ENV_PRODUCTION }}"
        # The shell picks one. An expression such as `a && production || staging` would hand production staging's
        # values whenever its own were empty.
        assert 'if [ "$TARGET" = production ]; then BUILD_VALUES=$PRODUCTION_VALUES; else BUILD_VALUES=$STAGING_VALUES; fi' in STEPS[name]["run"]
    assert "|| vars." not in TEXT and "&& vars." not in TEXT
    # The secrets reach those two steps and no other, by any spelling of the context.
    uncommented = "\n".join(line for line in TEXT.splitlines() if not line.lstrip().startswith("#"))
    assert len(re.findall(r"\bsecrets\b", uncommented)) == 4 and uncommented.count("secrets.CLOUDFLARE_") == 4
    build = STEPS["Build and deploy both Workers"]
    # Vercel's own variables are what the Sentry release and environment fall back to; here they are stated.
    assert build["env"]["NEXT_PUBLIC_SENTRY_RELEASE"] == "${{ github.sha }}"
    assert build["env"]["NEXT_PUBLIC_SENTRY_ENVIRONMENT"] == "${{ inputs.target || 'staging' }}"
    # The values go into a file Next reads and git ignores, so the deploy script still sees an unchanged checkout;
    # only their names are printed.
    assert "printf '%s\\n' \"$BUILD_VALUES\" > .env.production.local" in build["run"]
    assert "grep -oE '^[A-Za-z0-9_]+=' .env.production.local | tr -d '=' | sort" in build["run"]
    assert build["run"].count(".env.production.local") == 2 and "cat .env" not in TEXT and "set -x" not in TEXT
    # Main is read again after the install, so a commit that changed frontend/ meanwhile ends this run as a skip.
    recheck = build["run"].index('if [ "$(git rev-parse HEAD:frontend)" != "$(git rev-parse FETCH_HEAD:frontend)" ]; then')
    assert recheck < build["run"].index("npm run cf:deploy:production") and "exit 0" in build["run"][recheck:]
    ignored = (ROOT / ".gitignore").read_text().splitlines()
    assert ".env.*" in ignored


def test_it_uses_the_runtime_ci_uses_and_checks_staging_afterwards():
    ci = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    node = next(step for step in ci["jobs"]["worker-build"]["steps"] if step.get("name") == "Set up Node.js")
    assert STEPS["Set up Node.js"]["uses"] == node["uses"] and STEPS["Set up Node.js"]["with"] == node["with"]
    assert STEPS["Install dependencies"]["run"] == "npm ci"
    check = STEPS["Staging answers"]
    assert check["if"] == f"{DEPLOYS} && env.TARGET == 'staging'"
    assert "https://staging.earningsnerd.io/pricing" in check["run"]
    assert "grep -qi '^x-robots-tag: noindex, nofollow' headers.txt" in check["run"]


def _git(cwd, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.test", *args], cwd=cwd, check=True, capture_output=True)


def _decide(tmp_path, *, main_moves=(), origin_gone=False, target="staging", staging="A=1", production="", token="t"):
    """Runs the decide step as GitHub would, in a depth-1 checkout of a commit of a real repository whose main then
    moves on by `main_moves`, and returns (exit code, what it wrote to GITHUB_OUTPUT)."""
    origin = tmp_path / "origin"
    for path in ("frontend/app.txt", "backend/app.txt"):
        (origin / path).parent.mkdir(parents=True, exist_ok=True)
        (origin / path).write_text("first\n")
    _git(origin, "init", "--quiet", "--initial-branch=main")
    _git(origin, "add", "-A")
    _git(origin, "commit", "--quiet", "-m", "first")
    checkout = tmp_path / "checkout"
    _git(tmp_path, "clone", "--quiet", "--depth=1", f"file://{origin}", str(checkout))
    for path in main_moves:
        (origin / path).write_text("moved\n")
        _git(origin, "commit", "--quiet", "-am", f"moves {path}")
    if origin_gone:
        _git(checkout, "remote", "set-url", "origin", f"file://{tmp_path}/nowhere")
    output = tmp_path / "output"
    output.write_text("")
    # GitHub runs `shell: bash` as `bash --noprofile --norc -eo pipefail {0}`. The fetch retry's waits are not slept.
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-eo", "pipefail", "-c", "sleep() { :; }\n" + STEPS["Decide whether this run deploys"]["run"]],
        cwd=checkout, capture_output=True, text=True, timeout=60, check=False,
        env={"PATH": os.environ["PATH"], "HOME": str(tmp_path), "GITHUB_OUTPUT": str(output), "TARGET": target,
             "CLOUDFLARE_API_TOKEN": token, "CLOUDFLARE_ACCOUNT_ID": "a", "STAGING_VALUES": staging, "PRODUCTION_VALUES": production},
    )
    return result.returncode, output.read_text().strip()


@pytest.mark.parametrize("case, expected", [
    ({}, (0, "deploy=true")),
    # A commit elsewhere leaves frontend/ as this commit has it: this run still deploys what main holds.
    ({"main_moves": ("backend/app.txt",)}, (0, "deploy=true")),
    # A commit to frontend/ supersedes this run, whose own commit must not be deployed after it.
    ({"main_moves": ("frontend/app.txt",)}, (0, "deploy=false")),
    ({"main_moves": ("backend/app.txt", "frontend/app.txt")}, (0, "deploy=false")),
    # Unconfigured: no token, or no values for the target asked for. Production never borrows staging's.
    ({"token": ""}, (0, "deploy=false")),
    ({"staging": ""}, (0, "deploy=false")),
    ({"target": "production"}, (0, "deploy=false")),
    ({"target": "production", "production": "A=1"}, (0, "deploy=true")),
    # Main cannot be read: the run fails, and nothing says to deploy.
    ({"origin_gone": True}, (1, "")),
])
def test_the_decide_step_run_in_real_git(tmp_path, case, expected):
    assert _decide(tmp_path, **case) == expected

