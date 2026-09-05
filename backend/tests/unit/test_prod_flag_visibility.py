"""Observed production pins and read-only configuration evidence; no cloud/model calls."""
import ast
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from app.config import Settings
from scripts import pin_baseline

ROOT = Path(__file__).resolve().parents[3]
PROD_ENV_PINS = {
    "NOTABLE_FILINGS_ENABLED": "false", "AI_EVIDENCE_SNAP": "false",
    "AI_FIGURE_TRACE_GATE": "false", "AI_FORWARD_QUOTE_GATE": "false",
    "USE_STRUCTURED_OUTPUT": "false", "USE_STATEMENT_FINANCIALS": "true",
    # Founder-approved W3-1 observation: keep the live service filter, not the old plan's false.
    "CALENDAR_INDEX_FILTER_ENABLED": "true", "ENABLE_FPI_FILINGS": "true",
    "STREAM_SECTION_REVEAL": "true", "REGISTRATION_MODE": "invite_only",
}
INTENTIONAL_PROD_OVERRIDES = {
    "ENABLE_FPI_FILINGS", "STREAM_SECTION_REVEAL", "REGISTRATION_MODE",
    "CALENDAR_INDEX_FILTER_ENABLED",
}


def _workflow(name):
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def _step(job, name):
    return next(step for step in job["steps"] if step.get("name") == name)


def _env_map(run):
    executable = "\n".join(line for line in run.splitlines() if not line.lstrip().startswith("#"))
    values = re.findall(r"--update-env-vars=(\S+)", executable)
    assert len(values) == 1
    entries = [item.split("=", 1) for item in values[0].split(",")]
    assert all(len(entry) == 2 for entry in entries)
    assert len({key for key, _ in entries}) == len(entries), "Duplicate deployment env key"
    return dict(entries)


def _ops_code():
    step = _step(_workflow("ops.yml")["jobs"]["ops"],
                 "Describe service env (values only for known feature flags)")
    return step["run"].split("python3 - <<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]


def test_production_pins_match_defaults_pregenerate_and_ops_visibility(tmp_path):
    job = _workflow("ci.yml")["jobs"]["deploy-backend"]
    service = _env_map(_step(job, "Deploy Cloud Run service")["run"])
    assert pin_baseline.production_env() == service  # independent YAML selection vs stdlib parser
    script = ROOT / "backend/scripts/pin_baseline.py"
    probe = subprocess.run([sys.executable, "-S", "-c",
                            "import runpy,sys; m=runpy.run_path(sys.argv[1]); m['production_env']()", str(script)],
                           cwd=tmp_path, capture_output=True, text=True)
    assert probe.returncode == 0, probe.stderr  # no site packages, app imports or cwd dependency
    for key, value in PROD_ENV_PINS.items():
        assert service.get(key) == value, f"Unexpected service pin: {key}"
        if key not in INTENTIONAL_PROD_OVERRIDES:
            default = Settings.model_fields[key].default
            assert type(default) is bool and str(default).lower() == value, key
    pregenerate = _env_map(_step(job, "Update pregenerate job image")["run"])
    for key in (*pin_baseline.AI_GUARD_ENV, "NOTABLE_FILINGS_ENABLED"):
        assert pregenerate.get(key) == service[key], key
    assert pregenerate["CALENDAR_INDEX_FILTER_ENABLED"] == "false"
    assert Settings.model_fields["CALENDAR_INDEX_FILTER_ENABLED"].default is False
    assignments = {node.targets[0].id: ast.literal_eval(node.value)
                   for node in ast.parse(_ops_code()).body
                   if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
                   and node.targets[0].id in {"allow", "flag_defaults"}}
    assert set(pin_baseline.AI_GUARD_ENV) == {
        "AI_EVIDENCE_SNAP", "AI_FIGURE_TRACE_GATE", "AI_FORWARD_QUOTE_GATE",
        "USE_STRUCTURED_OUTPUT", "USE_STATEMENT_FINANCIALS",
    }
    assert assignments["allow"] >= PROD_ENV_PINS.keys()
    assert assignments["flag_defaults"].keys() >= PROD_ENV_PINS.keys()
    for key, value in assignments["flag_defaults"].items():
        default = Settings.model_fields[key].default
        assert type(value) is type(default) and value == default, key


@pytest.mark.parametrize("defect", ["missing", "comment", "duplicate-key", "duplicate-step", "wrong-command", "guard-value"])
def test_pin_parser_rejects_unusable_service_evidence(monkeypatch, tmp_path, defect):
    source = pin_baseline.CI_PATH.read_text()
    if defect == "missing":
        source = source.replace("- name: Deploy Cloud Run service", "- name: Retired service step")
    elif defect == "comment":
        source = source.replace("            --update-env-vars=ENVIRONMENT", "            # --update-env-vars=ENVIRONMENT")
    elif defect == "duplicate-key":
        source = source.replace("ENVIRONMENT=production,", "ENVIRONMENT=production,ENVIRONMENT=staging,", 1)
    elif defect == "duplicate-step":
        source += "\n      - name: Deploy Cloud Run service\n"
    elif defect == "wrong-command":
        source = source.replace("gcloud run deploy earningsnerd-backend", "echo gcloud run deploy earningsnerd-backend")
    elif defect == "guard-value":
        source = source.replace("AI_EVIDENCE_SNAP=false", "AI_EVIDENCE_SNAP=0", 1)
    path = tmp_path / "ci.yml"
    path.write_text(source)
    monkeypatch.setattr(pin_baseline, "CI_PATH", path)
    with pytest.raises(ValueError, match="Cannot pin"):
        pin_baseline.production_env()


def _render(service, revision, job):
    output = io.StringIO()
    with patch("builtins.open", return_value=io.StringIO(json.dumps(service))), \
            patch.dict("os.environ", {"REGION": "fixture-region"}), \
            patch("subprocess.check_output", side_effect=[json.dumps(revision), json.dumps(job)]) as describe, \
            redirect_stdout(output):
        exec(compile(_ops_code(), "ops-describe", "exec"), {})
    assert describe.call_count == 2
    assert describe.call_args_list[0].args[0] == [
        "gcloud", "run", "revisions", "describe", "serving", "--region=fixture-region", "--format=json"]
    assert describe.call_args_list[1].args[0] == [
        "gcloud", "run", "jobs", "describe", "earningsnerd-pregenerate", "--region=fixture-region", "--format=json"]
    return output.getvalue()


@pytest.fixture
def resources():
    def container(image, value):
        return {"image": image, "env": [
            {"name": "CALENDAR_INDEX_FILTER_ENABLED", "value": value},
            {"name": "AI_EVIDENCE_SNAP", "valueFrom": {"secretKeyRef": {"name": "hidden-reference"}}},
            {"name": "AI_FIGURE_TRACE_GATE", "valueSource": {"secretKeyRef": {"name": "hidden-reference"}}},
            {"name": "AI_FALLBACK_API_KEY", "value": "hidden-credential"},
        ]}
    return (
        {"status": {"latestReadyRevisionName": "serving", "latestCreatedRevisionName": "serving",
                    "traffic": [{"revisionName": "serving", "percent": 100}]}},
        {"spec": {"containers": [container("service-image", "true")]}},
        {"spec": {"template": {"spec": {"template": {"spec": {
            "containers": [container("job-image", "false")]}}}}}},
    )


def test_ops_renderer_binds_masked_values_to_distinct_resources(resources):
    service, revision, job = resources
    # A stale service template is deliberately different from the immutable serving revision.
    service["spec"] = {"template": {"spec": {"containers": [{"image": "stale-template"}]}}}
    output = _render(service, revision, job)
    left, right = output.split("Job: earningsnerd-pregenerate")
    assert "Serving revision: serving" in left and "service-image" in left
    assert "CALENDAR_INDEX_FILTER_ENABLED = 'true'" in left
    assert "job-image" in right and "CALENDAR_INDEX_FILTER_ENABLED = 'false'" in right
    for rendered in (left, right):
        assert "AI_EVIDENCE_SNAP = <secret-ref>" in rendered
        assert "AI_FIGURE_TRACE_GATE = <secret-ref>" in rendered
        assert "AI_FALLBACK_API_KEY = <set; value withheld>" in rendered
        assert "USE_STATEMENT_FINANCIALS = <NOT SET -> Settings default applies (True)>" in rendered
        assert "verify these against the reported image before pinning" in rendered
    assert "hidden-credential" not in output and "hidden-reference" not in output
    assert "stale-template" not in output


@pytest.mark.parametrize("defect", ["missing", "rollback", "split", "unready"])
def test_ops_renderer_rejects_unresolved_traffic_before_describing(resources, defect):
    service, revision, job = resources
    if defect == "missing":
        service["status"].pop("traffic")
    elif defect == "rollback":
        service["status"]["traffic"][0]["revisionName"] = "older"
    elif defect == "split":
        service["status"]["traffic"] = [{"revisionName": "serving", "percent": 50},
                                         {"revisionName": "older", "percent": 50}]
    else:
        service["status"]["latestCreatedRevisionName"] = "unready"
    with patch("subprocess.check_output", side_effect=[json.dumps(revision), json.dumps(job)]) as describe, \
            patch.dict("os.environ", {"REGION": "fixture-region"}), \
            pytest.raises(SystemExit, match="100% traffic"):
        # _render would install a second patch, so execute directly for the no-cloud-call assertion.
        with patch("builtins.open", return_value=io.StringIO(json.dumps(service))):
            exec(compile(_ops_code(), "ops-describe", "exec"), {})
    describe.assert_not_called()


@pytest.mark.parametrize("resource,count", [("revision", 0), ("revision", 2), ("job", 0), ("job", 2)])
def test_ops_renderer_requires_single_application_container(resources, resource, count):
    service, revision, job = resources
    spec = revision["spec"] if resource == "revision" else job["spec"]["template"]["spec"]["template"]["spec"]
    spec["containers"] *= count
    with pytest.raises(SystemExit, match="one application container"):
        _render(service, revision, job)
