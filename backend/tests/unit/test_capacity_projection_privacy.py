"""The complete Ops Python readback withholds private command/environment values."""
import json
from pathlib import Path
import subprocess
from unittest.mock import mock_open

import pytest
import yaml


@pytest.mark.parametrize("command,args", [
    ([], []),
    (["python", "123"], []),
    (["uvicorn", "main:app"], ["--workers", "4"]),
    (["PRIVATE_COMMAND_SENTINEL"], ["PRIVATE_ARGUMENT_SENTINEL"]),
])
@pytest.mark.parametrize("concurrency,timeout,expected", [
    (80, 300, (80, 300)),
    (1000, 3600, (1000, 3600)),
    ("PRIVATE_CONCURRENCY_SENTINEL", {"private": "PRIVATE_TIMEOUT_SENTINEL"}, (None, None)),
    (True, False, (None, None)),
    (0, 3601, (None, None)),
])
def test_capacity_projection_withholds_commands_and_private_values(capsys, monkeypatch, command, args,
                                                                  concurrency, timeout, expected):
    workflow = yaml.safe_load((Path(__file__).parents[3] / ".github/workflows/ops.yml").read_text())
    step = next(s for s in workflow["jobs"]["ops"]["steps"]
                if s.get("name") == "Describe service env (values only for known feature flags)")
    # Execute the entire Python readback, including show(), not a comment-delimited suffix.
    # The fixed shell wrapper redirects its only external read; added shell output must fail too.
    shell, projection = step["run"].split("python3 - <<'PY'\n", 1)
    projection, suffix = projection.split("\nPY", 1)
    assert shell == ('set -euo pipefail\n'
                     'gcloud run services describe "$SERVICE" --region="$REGION" --format=json > /tmp/svc.json\n')
    assert not suffix.strip()
    container = {"image": "allowed-api-image", "command": command, "args": args, "env": [
        {"name": "AI_DEFAULT_MODEL", "value": "deepseek-flash"},
        {"name": "WEB_CONCURRENCY", "value": "4"},
        {"name": "UVICORN_WORKERS", "valueFrom": {"secretKeyRef": {"name": "PRIVATE_SECRET_SENTINEL"}}},
        {"name": "GUNICORN_CMD_ARGS", "value": "PRIVATE_GUNICORN_SENTINEL"},
        {"name": "UNRELATED", "value": "PRIVATE_ENV_SENTINEL"},
    ]}
    revision = {"spec": {"containers": [container], "containerConcurrency": concurrency,
                         "timeoutSeconds": timeout}, "metadata": {"annotations": {
        "run.googleapis.com/vpc-access-egress": "PRIVATE_EGRESS_SENTINEL",
        "run.googleapis.com/vpc-access-connector": "PRIVATE_CONNECTOR_SENTINEL",
        "run.googleapis.com/network-interfaces": "PRIVATE_NETWORK_SENTINEL",
    }}}
    svc = {
        "status": {"latestReadyRevisionName": "revision-1", "latestCreatedRevisionName": "revision-1",
                   "traffic": [{"revisionName": "revision-1", "percent": 100}]},
        "metadata": {"annotations": {"run.googleapis.com/ingress": "PRIVATE_INGRESS_SENTINEL"}},
    }
    job_container = {"image": "allowed-job-image", "command": ["PRIVATE_JOB_COMMAND_SENTINEL"],
                     "args": ["PRIVATE_JOB_ARGUMENT_SENTINEL"], "env": [
        {"name": "UNRELATED", "value": "PRIVATE_JOB_ENV_SENTINEL"},
        {"name": "AI_DEFAULT_MODEL", "value": "deepseek-flash"},
        {"name": "AI_FALLBACK_MODEL", "valueSource": {"secretKeyRef": {"name": "PRIVATE_JOB_SECRET_SENTINEL"}}},
    ]}
    pregenerate = {"spec": {"template": {"spec": {"template": {"spec": {"containers": [job_container]}}}}}}
    readbacks = {("revisions", "revision-1"): revision, ("jobs", "earningsnerd-pregenerate"): pregenerate}
    calls = []

    def describe(argv: list[str], *, text: bool) -> str:
        assert argv[:2] == ["gcloud", "run"] and argv[3] == "describe"
        assert argv[5:] == ["--region=offline-region", "--format=json"] and text is True
        key = (argv[2], argv[4])
        calls.append(key)
        return json.dumps(readbacks[key])

    monkeypatch.setenv("REGION", "offline-region")
    monkeypatch.setattr(subprocess, "check_output", describe)
    service_json = mock_open(read_data=json.dumps(svc))
    exec(projection, {"open": service_json})
    output = capsys.readouterr().out
    service_json.assert_called_once_with("/tmp/svc.json")
    assert calls == list(readbacks)
    assert "PRIVATE_" not in output
    assert "Serving revision: revision-1\nimage: allowed-api-image" in output
    assert "Job: earningsnerd-pregenerate\nimage: allowed-job-image" in output
    assert output.count("AI_DEFAULT_MODEL = 'deepseek-flash'") == 2
    assert "UNRELATED = <set; value withheld>" in output and "AI_FALLBACK_MODEL = <secret-ref>" in output
    capacity_lines = [line.removeprefix("Capacity configuration: ") for line in output.splitlines()
                      if line.startswith("Capacity configuration: ")]
    assert len(capacity_lines) == 1
    value = json.loads(capacity_lines[0])
    assert value["container_command"] == {"state": (
        "override_present_values_withheld" if command or args else "image_default_unresolved")}
    assert (value["container_concurrency"], value["request_timeout_seconds"]) == expected
    assert value["worker_environment"] == {
        "WEB_CONCURRENCY": {"state": "literal", "value": 4},
        "UVICORN_WORKERS": {"state": "secret_ref_unresolved"},
    }
    assert value["effective_worker_count"] is None and value["egress_ip_identity"] is None
    assert value["vpc_egress"] == value["ingress"] == "unset_or_unresolved"
    assert value["vpc_connector_annotation_present"] and value["direct_vpc_annotation_present"]
