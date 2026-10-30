"""The Ops describe-jobs readback prints both SEC pins per job, withholds command values, lists every
resource and value defect before one exit, and keeps its literals equal to ci.yml and the other job gates."""
import ast
import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

from tests.unit.test_sec_process_budgets import EXPECTED_JOBS

ROOT = Path(__file__).resolve().parents[3]
STEP = "Describe expected job release configuration"
MODULE = ROOT / "ops/describe/jobs.py"
RUN = "python3 ops/describe/jobs.py"
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend:aaaaaaa"
BACKFILL = "earningsnerd-backfill-facts"
# Fixture command/argument tokens; the readback prints verdicts, never these.
WITHHELD_TOKENS = ("python", "scripts/backfill_facts.py", "--only-new", "41")
PIN_DEFECTS = ("missing", "secret-ref", "10", "1 ", 1, "PRIVATE_PIN_VALUE_SENTINEL")


def _step():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ops.yml").read_text())
    return next(step for step in workflow["jobs"]["ops"]["steps"] if step.get("name") == STEP)


def _split(step):
    return "", MODULE.read_text()


def _literals(code):
    return {node.targets[0].id: ast.literal_eval(node.value) for node in ast.parse(code).body
            if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id in {"expected_pools", "expected_entrypoints"}}


def _ci_step(name):
    workflow = yaml.load((ROOT / ".github/workflows/ci.yml").read_text(), Loader=yaml.BaseLoader)
    step = next(step for step in workflow["jobs"]["deploy-backend"]["steps"] if step.get("name") == name)
    return "\n".join(line for line in step["run"].splitlines() if not line.lstrip().startswith("#"))


def _readout():
    spec = importlib.util.spec_from_file_location("capacity_readout", ROOT / "ops/capacity/readout.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _job(name, pool):
    env = [{"name": "DB_POOL_SIZE", "value": pool}, {"name": "DB_MAX_OVERFLOW", "value": "0"},
           {"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"}, {"name": "EDGAR_RATE_LIMIT_PER_SEC", "value": "1"},
           {"name": "UNRELATED", "value": "PRIVATE_JOB_ENV_SENTINEL"},
           {"name": "OPENAI_API_KEY", "valueFrom": {"secretKeyRef": {"name": "PRIVATE_JOB_SECRET_SENTINEL"}}}]
    container = {"image": IMAGE, "env": env}
    if name == BACKFILL:
        container.update({"command": ["python"], "args": ["scripts/backfill_facts.py", "--only-new"]})
    elif name == "earningsnerd-filing-digest":
        container.update({"command": ["PRIVATE_COMMAND_SENTINEL"], "args": ["PRIVATE_ARGUMENT_SENTINEL", "41"]})
    return {"metadata": {"name": name},
            "spec": {"template": {"spec": {"taskCount": 1, "template": {"spec": {"containers": [container]}}}}}}


def _container(job):
    return job["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]


@pytest.fixture
def fixtures():
    """One passing describe fixture per expected job, keyed by name (fresh dicts; mutate freely)."""
    return {name: _job(name, pool) for name, pool in _literals(_split(_step())[1])["expected_pools"].items()}


def _run(tmp_path, monkeypatch, capfd, fixtures, *, files=None, errors=None):
    """Run the entire committed projector, stubbing only fixed external gcloud reads."""
    monkeypatch.setenv("REGION", "us-west1")
    spec = importlib.util.spec_from_file_location("ops_describe_jobs", MODULE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    calls = []

    def read(argv, *, text, stderr, timeout):
        assert argv[:3] == ["gcloud", "run", "jobs"] and argv[3] == "describe"
        assert argv[5:] == ["--region=us-west1", "--format=json"]
        assert text and stderr == subprocess.PIPE and timeout == 40
        name = argv[4]
        calls.append(name)
        if name in (errors or {}):
            raise errors[name]
        if name in (files or {}):
            return files[name]
        if name not in fixtures:
            raise subprocess.CalledProcessError(1, argv, stderr="NOT_FOUND PRIVATE_MISSING_SENTINEL")
        return json.dumps(fixtures[name])

    monkeypatch.setattr(module.subprocess, "check_output", read)
    code = module.main()
    captured = capfd.readouterr()
    output = captured.out + captured.err
    assert "PRIVATE_" not in output and "example.invalid" not in output
    for token in WITHHELD_TOKENS:
        assert token not in output
    assert calls == list(module.expected_pools)
    return output, None if code == 0 else SystemExit(code)


def test_describe_jobs_step_uses_the_bounded_complete_collector():
    step = _step()
    assert step["timeout-minutes"] == 10
    assert step["run"].strip() == RUN
    tree = ast.parse(MODULE.read_text())
    timeout = next(ast.literal_eval(node.value) for node in tree.body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id == "GCLOUD_TIMEOUT")
    assert timeout * len(_literals(MODULE.read_text())["expected_pools"]) <= 360


def test_describe_jobs_prints_both_pins_and_withholds_command_values(tmp_path, monkeypatch, capfd, fixtures):
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is None
    assert output.count("== earningsnerd-") == 9
    assert output.count("  SEC_RATE_LIMIT_PER_SECOND: '1'") == 9 and output.count("  EDGAR_RATE_LIMIT_PER_SEC: '1'") == 9
    assert (f"== earningsnerd-backfill-facts\n  image: {IMAGE}\n  taskCount: 1\n  DB_POOL_SIZE: 1\n"
            "  DB_MAX_OVERFLOW: 0\n  SEC_RATE_LIMIT_PER_SECOND: '1'\n  EDGAR_RATE_LIMIT_PER_SEC: '1'\n"
            "  command/args: matches the committed entrypoint\n") in output
    assert f"== earningsnerd-pregenerate\n  image: {IMAGE}\n  taskCount: 1\n  DB_POOL_SIZE: 3\n" in output
    assert output.count("  command/args: image default") == 7
    assert output.count("  command/args: override present (values withheld)") == 1
    assert output.count("  env: 5 plain, 1 secret-ref; names and other values withheld") == 9
    assert output.rstrip().endswith("All expected jobs use one release image with the production pool budget, "
                                    "both SEC pins at 1 and taskCount=1.\ndescribe-jobs: PASS")


@pytest.mark.parametrize("defect", PIN_DEFECTS)
@pytest.mark.parametrize("pin", ["SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC"])
def test_describe_jobs_collects_pin_defects_across_all_jobs(tmp_path, monkeypatch, capfd, fixtures, pin, defect):
    container = _container(fixtures["earningsnerd-filing-digest"])
    container["env"] = [entry for entry in container["env"] if entry["name"] != pin]
    if defect == "secret-ref":
        container["env"].append({"name": pin, "valueFrom": {"secretKeyRef": {"name": "PRIVATE_PIN_SECRET_SENTINEL"}}})
    elif defect != "missing":
        container["env"].append({"name": pin, "value": defect})
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None
    assert f"earningsnerd-filing-digest must pin {pin}=1 as a plain value, got " in output
    assert output.count("== earningsnerd-") == 9  # every later block still prints
    assert "describe-jobs: FAIL (1 invariant failure(s); 0 unverified job(s))" in output and "describe-jobs: PASS" not in output


def test_describe_jobs_lists_every_value_defect_once(tmp_path, monkeypatch, capfd, fixtures):
    _container(fixtures["earningsnerd-filing-scan"])["env"][0]["value"] = "2"
    fixtures["earningsnerd-retention-purge"]["spec"]["template"]["spec"]["taskCount"] = 2
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None
    assert "earningsnerd-filing-scan must set plain DB_POOL_SIZE=1; observed 2." in output
    assert "earningsnerd-retention-purge taskCount must be 1." in output
    assert output.count("::error::") == 2 and "describe-jobs: FAIL (2 invariant failure(s); 0 unverified job(s))" in output
    assert output.count("== earningsnerd-") == 9


@pytest.mark.parametrize("defect,expected", [
    ("missing", "not_found"), ("invalid-json", "unreadable_response"),
    ("two-containers", "application_container_unresolved"), ("name-mismatch", "response_name_mismatch"),
    ("duplicate-env", "environment_names_unresolved"), ("no-image", "image_identity_unresolved"),
    ("private-image", "image_identity_unresolved"), ("wrong-shape", "unreadable_response"),
    ("too-many-env", "environment_shape_unresolved"),
])
def test_describe_jobs_retains_later_evidence_after_unreadable_job(tmp_path, monkeypatch, capfd, fixtures, defect, expected):
    name = "earningsnerd-notable-filings"
    target = fixtures[name]
    container = _container(target)
    files = None
    if defect == "missing":
        del fixtures[name]
    elif defect == "invalid-json":
        files = {name: "PRIVATE_JSON_SENTINEL"}
    elif defect == "two-containers":
        target["spec"]["template"]["spec"]["template"]["spec"]["containers"] *= 2
    elif defect == "name-mismatch":
        target["metadata"]["name"] = "PRIVATE_NAME_SENTINEL"
    elif defect == "duplicate-env":
        container["env"].append({"name": "DB_POOL_SIZE", "value": "PRIVATE_VALUE_SENTINEL"})
    elif defect == "no-image":
        container.pop("image")
    elif defect == "private-image":
        container["image"] = "https://PRIVATE_IMAGE_SENTINEL.example.invalid/token"
    elif defect == "wrong-shape":
        target["spec"] = ["PRIVATE_SHAPE_SENTINEL"]
    else:
        container["env"] = [{"name": "PRIVATE_ENV_NAME_SENTINEL", "value": "value"}] * 257
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures, files=files)
    assert exit_ is not None and f"  read: UNVERIFIED ({expected})" in output
    assert output.count("== earningsnerd-") == 9
    assert output.count("  Summary/SEC runtime configuration:") == 8
    assert "== earningsnerd-feedback-media-cleanup\n  image: " in output
    assert "Job inventory: expected=9 projected=8 unverified=1" in output
    assert "describe-jobs: INCOMPLETE (0 invariant failure(s); 1 unverified job(s))" in output
    assert "describe-jobs: PASS" not in output


@pytest.mark.parametrize("error,expected", [
    (subprocess.CalledProcessError(1, [], stderr="PERMISSION_DENIED PRIVATE_ERROR_SENTINEL"), "permission_denied"),
    (subprocess.CalledProcessError(1, [], stderr="NOT_FOUND PRIVATE_ERROR_SENTINEL"), "not_found"),
    (subprocess.CalledProcessError(1, [], stderr="UNAVAILABLE PRIVATE_ERROR_SENTINEL"), "unavailable"),
    (subprocess.CalledProcessError(1, [], stderr="DEADLINE_EXCEEDED PRIVATE_ERROR_SENTINEL"), "unavailable"),
    (subprocess.CalledProcessError(2, [], stderr="PRIVATE_ERROR_SENTINEL"), "error (gcloud exit 2)"),
    (subprocess.TimeoutExpired([], 40, stderr="PRIVATE_ERROR_SENTINEL"), "timeout"),
    (FileNotFoundError("PRIVATE_ERROR_SENTINEL"), "error (gcloud not executable)"),
])
def test_describe_jobs_collects_closed_failure_classes(tmp_path, monkeypatch, capfd, fixtures, error, expected):
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures,
                         errors={"earningsnerd-pregenerate": error, "earningsnerd-feedback-media-cleanup": error})
    assert exit_ is not None and output.count(f"  read: UNVERIFIED ({expected})") == 2
    assert output.count("  Summary/SEC runtime configuration:") == 7
    assert "Job inventory: expected=9 projected=7 unverified=2" in output
    assert "describe-jobs: PASS" not in output


def test_unreadable_job_never_masks_readable_drift(tmp_path, monkeypatch, capfd, fixtures):
    del fixtures["earningsnerd-pregenerate"]
    _container(fixtures["earningsnerd-filing-scan"])["env"][0]["value"] = "2"
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None
    assert "describe-jobs: FAIL (1 invariant failure(s); 1 unverified job(s))" in output


def test_unexpected_env_names_pool_values_and_task_count_never_print(tmp_path, monkeypatch, capfd, fixtures):
    container = _container(fixtures[BACKFILL])
    container["env"].append({"name": "PRIVATE_ENV_NAME_SENTINEL", "value": "PRIVATE_VALUE_SENTINEL"})
    container["env"][0]["value"] = "PRIVATE_POOL_SENTINEL"
    fixtures[BACKFILL]["spec"]["template"]["spec"]["taskCount"] = "PRIVATE_TASK_COUNT_SENTINEL"
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None and "  DB_POOL_SIZE: <unresolved withheld>" in output
    assert "  taskCount: <invalid withheld>" in output


def test_oversized_response_and_total_absence_remain_incomplete(tmp_path, monkeypatch, capfd, fixtures):
    output, exit_ = _run(tmp_path, monkeypatch, capfd, {},
                         files={"earningsnerd-pregenerate": " " * 1_048_577})
    assert exit_ is not None and "UNVERIFIED (response_too_large)" in output
    assert "Job inventory: expected=9 projected=0 unverified=9" in output
    assert "describe-jobs: INCOMPLETE" in output and "do not share one release image" not in output


def test_describe_jobs_reports_backfill_entrypoint_drift_without_values(tmp_path, monkeypatch, capfd, fixtures):
    _container(fixtures[BACKFILL])["args"] = ["scripts/backfill_facts.py"]
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None and "== earningsnerd-backfill-facts" in output
    assert "  command/args: DOES NOT MATCH the committed entrypoint (values withheld; compare ci.yml)" in output
    assert "backfill_facts" not in output


def test_describe_jobs_fails_on_image_parity_after_printing_all_blocks(tmp_path, monkeypatch, capfd, fixtures):
    _container(fixtures["earningsnerd-filing-scan"])["image"] = IMAGE.replace("aaaaaaa", "bbbbbbb")
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None and "do not share one release image" in output
    assert output.count("== earningsnerd-") == 9 and "describe-jobs: FAIL (1 invariant failure(s); 0 unverified job(s))" in output


def test_describe_jobs_literals_match_ci_and_the_other_gates():
    literals = _literals(_split(_step())[1])
    pools, entrypoints = literals["expected_pools"], literals["expected_entrypoints"]
    backfill = _ci_step("Update backfill-facts job image and scheduled entrypoint")
    assert entrypoints == {BACKFILL: (["python"], ["scripts/backfill_facts.py", "--only-new"])}
    assert entrypoints[BACKFILL] == ([re.search(r"--command=(\S+)", backfill).group(1)],
                                     re.search(r"--args=(\S+)", backfill).group(1).split(","))
    assert set(pools) == EXPECTED_JOBS == {"earningsnerd-" + job for job in _readout().JOBS}
    assert pools["earningsnerd-pregenerate"] == "3"
    assert all(pool == "1" for name, pool in pools.items() if name != "earningsnerd-pregenerate")
    pool_pattern = r"--update-env-vars=\S*?DB_POOL_SIZE=(\d)"
    assert re.search(pool_pattern, _ci_step("Update pregenerate job image")).group(1) == pools["earningsnerd-pregenerate"]
    loop = _ci_step("Update filing-scan + digest + calendar + alert + notable + retention job images")
    assert re.search(pool_pattern, loop).group(1) == "1" and re.search(pool_pattern, backfill).group(1) == "1"
