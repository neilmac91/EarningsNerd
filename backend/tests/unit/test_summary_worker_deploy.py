"""Execute the optional image-only CI step with cloud commands replaced at the CLI boundary."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


ROOT = Path(__file__).resolve().parents[3]
STEP_NAME = "Update configured summary task worker image"
WORKER_URL = "https://summary-worker-uw.a.run.app"
IMAGE = "us-west1-docker.pkg.dev/test-project/backend/image"
SHA = "1234567890abcdef1234567890abcdef12345678ab"


def _step() -> dict:
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["deploy-backend"]["steps"]
    selected = [step for step in steps if step.get("name") == STEP_NAME]
    assert len(selected) == 1
    step = selected[0]
    assert step["if"] == "steps.changes.outputs.backend == 'true'"
    assert step["env"] == {"SUMMARY_WORKER_URL": "${{ vars.GCP_SUMMARY_WORKER_URL || '' }}"}
    names = [item.get("name") for item in steps]
    assert names.index("Apply database migrations") < names.index(STEP_NAME) < names.index("Deploy Cloud Run service")
    return step


def _run(tmp_path: Path, *, configured: str = WORKER_URL, observed: str = WORKER_URL,
         describe_exit: int = 0, update_exit: int = 0, traffic_exit: int = 0) -> tuple[subprocess.CompletedProcess, list]:
    fake = tmp_path / "gcloud"
    log = tmp_path / "calls.jsonl"
    fake.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CALLS"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:3] == ["run", "services", "describe"]:
    print(os.environ["FAKE_WORKER_URL"])
    raise SystemExit(int(os.environ["FAKE_DESCRIBE_EXIT"]))
if args[:3] == ["run", "services", "update"]:
    raise SystemExit(int(os.environ["FAKE_UPDATE_EXIT"]))
if args[:3] == ["run", "services", "update-traffic"]:
    raise SystemExit(int(os.environ["FAKE_TRAFFIC_EXIT"]))
raise SystemExit(99)
''')
    fake.chmod(0o700)
    result = subprocess.run(
        ["bash", "--noprofile", "--norc", "-c", _step()["run"]], cwd=tmp_path,
        env={
            "PATH": str(tmp_path) + os.pathsep + os.defpath,
            "SUMMARY_WORKER_URL": configured, "IMAGE": IMAGE, "GITHUB_SHA": SHA,
            "FAKE_CALLS": str(log), "FAKE_WORKER_URL": observed,
            "FAKE_DESCRIBE_EXIT": str(describe_exit), "FAKE_UPDATE_EXIT": str(update_exit),
            "FAKE_TRAFFIC_EXIT": str(traffic_exit),
        },
        capture_output=True, text=True, timeout=10,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    return result, calls


def test_unconfigured_summary_worker_step_performs_no_cloud_operation(tmp_path):
    result, calls = _run(tmp_path, configured="")
    assert result.returncode == 0
    assert calls == []


@pytest.mark.parametrize("observed,describe_exit", [(WORKER_URL, 1), ("", 0), ("https://different-uw.a.run.app", 0)])
def test_summary_worker_lookup_or_identity_failure_makes_no_changes(tmp_path, observed, describe_exit):
    result, calls = _run(tmp_path, observed=observed, describe_exit=describe_exit)
    assert result.returncode != 0
    assert calls == [["run", "services", "describe", "earningsnerd-summary-worker", "--region=us-west1",
                      "--format=value(status.url)"]]


def test_summary_worker_image_failure_does_not_advance_traffic(tmp_path):
    result, calls = _run(tmp_path, update_exit=1)
    assert result.returncode != 0
    assert [call[2] for call in calls] == ["describe", "update"]


@pytest.mark.parametrize("traffic_exit", [0, 1])
def test_configured_summary_worker_changes_only_image_release_and_traffic(tmp_path, traffic_exit):
    result, calls = _run(tmp_path, traffic_exit=traffic_exit)
    assert result.returncode == traffic_exit
    assert calls == [
        ["run", "services", "describe", "earningsnerd-summary-worker", "--region=us-west1",
         "--format=value(status.url)"],
        ["run", "services", "update", "earningsnerd-summary-worker", "--region=us-west1",
         f"--image={IMAGE}:{SHA[:7]}", f"--update-env-vars=SENTRY_RELEASE={SHA}", "--quiet"],
        ["run", "services", "update-traffic", "earningsnerd-summary-worker", "--region=us-west1",
         "--to-latest", "--clear-tags", "--quiet"],
    ]
    assert WORKER_URL not in result.stdout + result.stderr
