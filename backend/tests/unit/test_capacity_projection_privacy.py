"""The actual Ops projection exposes capacity inputs without arbitrary command values."""
import json
from pathlib import Path
import re

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
def test_capacity_projection_withholds_commands_and_private_values(capsys, command, args,
                                                                  concurrency, timeout, expected):
    workflow = yaml.safe_load((Path(__file__).parents[3] / ".github/workflows/ops.yml").read_text())
    step = next(s for s in workflow["jobs"]["ops"]["steps"]
                if s.get("name") == "Describe service env (values only for known feature flags)")
    # Execute the exact committed projection, with only the preceding API readback replaced.
    projection = step["run"].split("# Capacity inputs only:", 1)[1].split("\nPY", 1)[0]
    projection = "\n".join(projection.splitlines()[1:])
    container = {"command": command, "args": args, "env": [
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
    exec(projection, {"json": json, "re": re, "revision": revision, "latest": "revision-1",
                      "svc": {"metadata": {"annotations": {"run.googleapis.com/ingress": "PRIVATE_INGRESS_SENTINEL"}}}})
    output = capsys.readouterr().out
    assert "PRIVATE_" not in output
    value = json.loads(output.removeprefix("Capacity configuration: "))
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
