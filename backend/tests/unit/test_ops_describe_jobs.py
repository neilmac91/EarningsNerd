"""The Ops describe-jobs readback prints both SEC pins per job, withholds command values, lists every
value defect before one exit, and keeps its literals equal to ci.yml and the other job gates."""
import ast
import importlib.util
import json
import re
from pathlib import Path

import pytest
import yaml

from tests.unit.test_sec_process_budgets import EXPECTED_JOBS

ROOT = Path(__file__).resolve().parents[3]
STEP = "Describe expected job release configuration"
BACKFILL = "earningsnerd-backfill-facts"
# Fixture command/argument tokens; the readback prints verdicts, never these.
WITHHELD_TOKENS = ("python", "scripts/backfill_facts.py", "--only-new", "41")
PIN_DEFECTS = ("missing", "secret-ref", "10", "1 ", 1, "PRIVATE_PIN_VALUE_SENTINEL")


def _step():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ops.yml").read_text())
    return next(step for step in workflow["jobs"]["ops"]["steps"] if step.get("name") == STEP)


def _split(step):
    shell, code = step["run"].split("python3 - <<'PY'\n", 1)
    code, suffix = code.split("\nPY", 1)
    assert not suffix.strip()
    return shell, code


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
    container = {"image": "release-image", "env": env}
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


def _run(tmp_path, monkeypatch, capfd, fixtures, *, files=None):
    """Write each fixture to <JOB_DIR>/<name>.json, execute the heredoc body, return (output, SystemExit or None)."""
    for name, job in fixtures.items():
        (tmp_path / f"{name}.json").write_text(json.dumps(job))
    for name, text in (files or {}).items():
        (tmp_path / f"{name}.json").write_text(text)
    monkeypatch.setenv("JOB_DIR", str(tmp_path))
    code = compile(_split(_step())[1], "ops-describe-jobs", "exec")
    exit_ = None
    try:
        exec(code, {})
    except SystemExit as exc:
        exit_ = exc
    captured = capfd.readouterr()
    output = captured.out + captured.err
    # No allow-list echo exists here: a sentinel anywhere in the output or the exit is a leak.
    assert "PRIVATE_" not in output and "PRIVATE_" not in str(exit_ or "")
    for token in WITHHELD_TOKENS:
        assert token not in output
    return output, exit_


def test_describe_jobs_shell_reads_each_job_into_job_dir():
    step = _step()
    shell, code = _split(step)
    assert step["timeout-minutes"] == 10
    assert "set -euo pipefail" in shell and "export JOB_DIR" in shell
    assert 'if ! gcloud run jobs describe "$job" --region="$REGION" --format=json > "$JOB_DIR/$job.json" 2>/dev/null; then' in shell
    assert "::error::expected Cloud Run job '$job' is missing or unreadable" in shell and "exit 1" in shell
    array = re.search(r"jobs=\(\n((?:\s+earningsnerd-[a-z-]+\n)+)\s*\)", shell)
    assert array is not None and array.group(1).split() == list(_literals(code)["expected_pools"])


def test_describe_jobs_prints_both_pins_and_withholds_command_values(tmp_path, monkeypatch, capfd, fixtures):
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is None
    assert output.count("== earningsnerd-") == 8
    assert output.count("  SEC_RATE_LIMIT_PER_SECOND: '1'") == 8 and output.count("  EDGAR_RATE_LIMIT_PER_SEC: '1'") == 8
    assert ("== earningsnerd-backfill-facts\n  image: release-image\n  taskCount: 1\n  DB_POOL_SIZE: 1\n"
            "  DB_MAX_OVERFLOW: 0\n  SEC_RATE_LIMIT_PER_SECOND: '1'\n  EDGAR_RATE_LIMIT_PER_SEC: '1'\n"
            "  command/args: matches the committed entrypoint\n") in output
    assert "== earningsnerd-pregenerate\n  image: release-image\n  taskCount: 1\n  DB_POOL_SIZE: 3\n" in output
    assert output.count("  command/args: image default") == 6
    assert output.count("  command/args: override present (values withheld)") == 1
    assert ("  env: DB_POOL_SIZE(plain), DB_MAX_OVERFLOW(plain), SEC_RATE_LIMIT_PER_SECOND(plain), "
            "EDGAR_RATE_LIMIT_PER_SEC(plain), UNRELATED(plain), OPENAI_API_KEY(secret-ref)") in output
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
    assert f"earningsnerd-filing-digest must pin {pin}=1 as a plain value, got " in str(exit_)
    assert output.count("== earningsnerd-") == 8  # every later block still prints
    assert "describe-jobs: FAIL (1 invariant failure(s))" in output and "describe-jobs: PASS" not in output


def test_describe_jobs_lists_every_value_defect_once(tmp_path, monkeypatch, capfd, fixtures):
    _container(fixtures["earningsnerd-filing-scan"])["env"][0]["value"] = "2"
    fixtures["earningsnerd-retention-purge"]["spec"]["template"]["spec"]["taskCount"] = 2
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None
    assert "earningsnerd-filing-scan pool must be 1+0, got 2+0." in str(exit_)
    assert "earningsnerd-retention-purge taskCount must be 1." in str(exit_)
    assert output.count("::error::") == 2 and "describe-jobs: FAIL (2 invariant failure(s))" in output
    assert output.count("== earningsnerd-") == 8


@pytest.mark.parametrize("defect,expected", [
    ("missing-file", "cannot read earningsnerd-notable-filings"),
    ("empty-file", "cannot read earningsnerd-notable-filings"),  # a failed redirect leaves an empty file
    ("two-containers", "one application container"),
    ("name-mismatch", "response name does not match"),
    ("duplicate-env", "missing or duplicate env name"),
    ("secret-pool", "needs plain DB_POOL_SIZE"),
    ("no-image", "image is missing"),
])
def test_describe_jobs_keeps_shape_invariants_immediate(tmp_path, monkeypatch, capfd, fixtures, defect, expected):
    target = fixtures["earningsnerd-notable-filings"]  # the seventh job: six blocks print before it
    spec = target["spec"]["template"]["spec"]["template"]["spec"]
    files = None
    if defect == "missing-file":
        del fixtures["earningsnerd-notable-filings"]
    elif defect == "empty-file":
        del fixtures["earningsnerd-notable-filings"]
        files = {"earningsnerd-notable-filings": ""}
    elif defect == "two-containers":
        spec["containers"] *= 2
    elif defect == "name-mismatch":
        target["metadata"]["name"] = "other"
    elif defect == "duplicate-env":
        spec["containers"][0]["env"].append({"name": "DB_POOL_SIZE", "value": "1"})
    elif defect == "secret-pool":
        spec["containers"][0]["env"][0] = {"name": "DB_POOL_SIZE",
                                           "valueFrom": {"secretKeyRef": {"name": "PRIVATE_POOL_SENTINEL"}}}
    else:
        spec["containers"][0].pop("image")
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures, files=files)
    assert exit_ is not None and expected in str(exit_)
    assert output.count("== earningsnerd-") == 6 and "::error::" not in output and "describe-jobs:" not in output


def test_describe_jobs_reports_backfill_entrypoint_drift_without_values(tmp_path, monkeypatch, capfd, fixtures):
    _container(fixtures[BACKFILL])["args"] = ["scripts/backfill_facts.py"]
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is None and "== earningsnerd-backfill-facts" in output
    assert "  command/args: DOES NOT MATCH the committed entrypoint (values withheld; compare ci.yml)" in output
    assert "backfill_facts" not in output


def test_describe_jobs_fails_on_image_parity_after_printing_all_blocks(tmp_path, monkeypatch, capfd, fixtures):
    _container(fixtures["earningsnerd-filing-scan"])["image"] = "other-image"
    output, exit_ = _run(tmp_path, monkeypatch, capfd, fixtures)
    assert exit_ is not None and "do not share one release image" in str(exit_)
    assert output.count("== earningsnerd-") == 8 and "describe-jobs: FAIL (1 invariant failure(s))" in output


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
