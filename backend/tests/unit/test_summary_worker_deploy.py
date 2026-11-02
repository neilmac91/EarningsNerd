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
BUDGET_KEYS = ("SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC")


def _step() -> dict:
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["deploy-backend"]["steps"]
    selected = [step for step in steps if step.get("name") == STEP_NAME]
    assert len(selected) == 1
    step = selected[0]
    assert step["if"] == "steps.changes.outputs.backend == 'true'"
    assert workflow["jobs"]["deploy-backend"]["env"]["SUMMARY_WORKER_URL"] == "${{ vars.GCP_SUMMARY_WORKER_URL || '' }}"
    assert "env" not in step
    names = [item.get("name") for item in steps]
    assert names.index("Apply database migrations") < names.index(STEP_NAME) < names.index("Deploy Cloud Run service")
    return step


def _run(tmp_path: Path, *, configured: str = WORKER_URL, observed: str = WORKER_URL,
         describe_exit: int = 0, update_exit: int = 0, traffic_exit: int = 0,
         entries: list | None = None, containers: int = 1, raw: str | None = None) -> tuple[subprocess.CompletedProcess, list]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    fake = tmp_path / "gcloud"
    log = tmp_path / "calls.jsonl"
    if entries is None:
        entries = [{"name": key, "value": "1"} for key in BUDGET_KEYS]
    service = {"status": {"url": observed}, "spec": {"template": {"spec": {"containers": [{"env": entries}] * containers}}}}
    fake.write_text(f"#!{sys.executable}\n" + '''
import json, os, stat, sys
args = sys.argv[1:]
with open(os.environ["FAKE_CALLS"], "a") as log:
    log.write(json.dumps(args) + "\\n")
if args[:3] == ["run", "services", "describe"]:
    assert stat.S_IMODE(os.fstat(sys.stdout.fileno()).st_mode) == 0o600
    print(os.environ["FAKE_WORKER_SERVICE"])
    print("PRIVATE_PROVIDER_ERROR", file=sys.stderr)
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
            "TMPDIR": str(tmp_path),
            "SUMMARY_WORKER_URL": configured, "IMAGE": IMAGE, "GITHUB_SHA": SHA,
            "FAKE_CALLS": str(log), "FAKE_WORKER_SERVICE": json.dumps(service) if raw is None else raw,
            "FAKE_DESCRIBE_EXIT": str(describe_exit), "FAKE_UPDATE_EXIT": str(update_exit),
            "FAKE_TRAFFIC_EXIT": str(traffic_exit),
        },
        capture_output=True, text=True, timeout=10,
    )
    calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
    assert {item.name for item in tmp_path.iterdir()} <= {"gcloud", "calls.jsonl"}, "private snapshot must be removed"
    assert "PRIVATE_" not in result.stdout + result.stderr
    return result, calls


def assert_existing_sec_budget_preflight(tmp_path: Path) -> None:
    """The budget inventory's sole preservation exception executes this real-shell guard.

    A step name alone cannot exempt an unpinned process. Both limiter names must
    refuse missing, wrong, secret-backed and ambiguous values before any update.
    """
    for key in BUDGET_KEYS:
        other = [{"name": name, "value": "1"} for name in BUDGET_KEYS if name != key]
        invalid = [[], [{"name": key, "value": "2"}], [{"name": key, "value": 1}],
                   [{"name": key, "value": "PRIVATE_CONFIG"}],
                   [{"name": key, "value": "1", "valueFrom": {"secretKeyRef": {"name": "PRIVATE_SECRET"}}}],
                   [{"name": key, "value": "1", "valueSource": {"secretKeyRef": {"secret": "PRIVATE_SECRET"}}}],
                   [{"name": key, "value": "1"}, {"name": key, "value": "2"}]]
        for index, values in enumerate(invalid):
            result, calls = _run(tmp_path / f"{key}-{index}", entries=other + values)
            assert result.returncode != 0, f"{key} must be verified before the image update"
            assert len(calls) == 1 and calls[0][2] == "describe", f"{key} drift must not mutate the worker"


def test_unconfigured_summary_worker_step_performs_no_cloud_operation(tmp_path):
    result, calls = _run(tmp_path, configured="")
    assert result.returncode == 0
    assert calls == []


@pytest.mark.parametrize("observed,describe_exit", [(WORKER_URL, 1), ("", 0), ("https://different-uw.a.run.app", 0)])
def test_summary_worker_lookup_or_identity_failure_makes_no_changes(tmp_path, observed, describe_exit):
    result, calls = _run(tmp_path, observed=observed, describe_exit=describe_exit)
    assert result.returncode != 0
    assert calls == [["run", "services", "describe", "earningsnerd-summary-worker", "--region=us-west1",
                      "--format=json"]]


@pytest.mark.parametrize("containers,raw", [(0, None), (2, None), (1, "PRIVATE_BAD_JSON"), (1, "[]")])
def test_summary_worker_snapshot_must_resolve_one_container(tmp_path, containers, raw):
    result, calls = _run(tmp_path, containers=containers, raw=raw)
    assert result.returncode != 0
    assert len(calls) == 1 and calls[0][2] == "describe"


def test_summary_worker_image_failure_does_not_advance_traffic(tmp_path):
    result, calls = _run(tmp_path, update_exit=1)
    assert result.returncode != 0
    assert [call[2] for call in calls] == ["describe", "update"]


@pytest.mark.parametrize("traffic_exit", [0, 1])
def test_configured_summary_worker_changes_only_image_release_and_traffic(tmp_path, traffic_exit):
    entries = ([{"name": key, "value": "1"} for key in BUDGET_KEYS]
               + [{"name": "TASKS_WORKER_ROLE", "value": "summary"},
                  {"name": "SUMMARY_DURABLE_GENERATION_ENABLED", "value": "true"},
                  {"name": "SEC_DISTRIBUTED_LIMIT_ENABLED", "value": "true"},
                  {"name": "DATABASE_URL", "valueFrom": {"secretKeyRef": {"name": "PRIVATE_SECRET", "key": "1"}}}])
    result, calls = _run(tmp_path, traffic_exit=traffic_exit, entries=entries)
    assert result.returncode == traffic_exit
    assert calls == [
        ["run", "services", "describe", "earningsnerd-summary-worker", "--region=us-west1",
         "--format=json"],
        ["run", "services", "update", "earningsnerd-summary-worker", "--region=us-west1",
         f"--image={IMAGE}:{SHA[:7]}", f"--update-env-vars=SENTRY_RELEASE={SHA}", "--quiet"],
        ["run", "services", "update-traffic", "earningsnerd-summary-worker", "--region=us-west1",
         "--to-latest", "--clear-tags", "--quiet"],
    ]
    assert WORKER_URL not in result.stdout + result.stderr
