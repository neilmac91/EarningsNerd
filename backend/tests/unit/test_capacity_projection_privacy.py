"""The complete Ops Python readback withholds private command/environment values."""
import json
from pathlib import Path
import subprocess
from unittest.mock import mock_open

import pytest
import yaml

MODEL = "allowed-model-value"  # an allow-listed name's value is echoed by design
# The task worker entrypoint ci.yml pins; the heredoc prints a match/mismatch verdict, never these tokens.
WORKER_COMMAND = ["uvicorn"]
WORKER_ARGS = ["task_worker_main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers",
               "--forwarded-allow-ips=*"]
WORKER_HOST = "https://PRIVATE_WORKER_HOST_SENTINEL.example.invalid"
# Annotation maps carry identities and URLs on live resources; every map in the fixtures plants them.
PRIVATE_NOTES = {
    "serving.knative.dev/creator": "PRIVATE_CREATOR_SENTINEL",
    "serving.knative.dev/lastModifier": "PRIVATE_MODIFIER_SENTINEL",
    "run.googleapis.com/urls": '["https://PRIVATE_URLS_SENTINEL.example.invalid"]',
}


@pytest.mark.parametrize("command,args", [
    ([], []),
    (["python", "123"], []),
    (["uvicorn", "main:app"], ["--workers", "17"]),
    (["PRIVATE_COMMAND_SENTINEL"], ["PRIVATE_ARGUMENT_SENTINEL"]),
])
@pytest.mark.parametrize("concurrency,timeout,expected", [
    (80, 300, (80, 300)),
    (1000, 3600, (1000, 3600)),
    ("PRIVATE_CONCURRENCY_SENTINEL", {"private": "PRIVATE_TIMEOUT_SENTINEL"}, (None, None)),
    (True, False, (None, None)),
    (0, 3601, (None, None)),
])
def test_capacity_projection_withholds_commands_and_private_values(capfd, monkeypatch, command, args,
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
    svc, revision, pregenerate, job_container = _service_fixtures(command, args, concurrency, timeout)
    worker, worker_revision, policy = _worker_fixtures()
    readbacks = _readbacks(revision, pregenerate, worker, worker_revision, policy)
    service_json, calls = _run(projection, svc, readbacks, monkeypatch)
    # Descriptor capture includes inherited child stdout/stderr as well as Python writes.
    captured = capfd.readouterr()
    output = captured.out + captured.err
    service_json.assert_called_once_with("/tmp/svc.json")
    assert calls == list(readbacks)
    assert "PRIVATE_" not in output
    assert "example.invalid" not in output  # no fixture host: service, worker, traffic or policy
    # Every fixture token is distinct from allowed output (worker env stays 4, args use 17/29).
    # Token absence covers individual/joined values as well as Python/JSON command arrays.
    for token in command + args + job_container["command"] + job_container["args"] + WORKER_COMMAND + WORKER_ARGS:
        assert token not in output
    assert 'Serving traffic: [{"percent": 100, "revisionName": "revision-1"}]' in output
    assert 'Worker serving traffic: [{"percent": 100, "revisionName": "worker-revision-1"}]' in output
    assert "Serving revision: revision-1\nimage: allowed-api-image" in output
    assert "Job: earningsnerd-pregenerate\nimage: allowed-job-image" in output
    assert "Worker revision: worker-revision-1\nimage: allowed-worker-image" in output
    assert output.count(f"AI_DEFAULT_MODEL = '{MODEL}'") == 3
    assert "UNRELATED = <set; value withheld>" in output and "AI_FALLBACK_MODEL = <secret-ref>" in output
    assert "TASKS_WORKER_URL = <set; value withheld>" in output
    assert "TASKS_INVOKER_EMAIL = <set; value withheld>" in output
    assert "DATABASE_URL = <secret-ref>" in output
    left, right = output.split("Worker revision: worker-revision-1")
    assert "TASKS_WORKER_PROCESS = 'false'" in left and "TASKS_WORKER_PROCESS = 'true'" in right
    # Sizing: closed-grammar values print, sentinel-valued annotations are withheld.
    assert "Service minScale: unset_or_unresolved" in output
    assert "Service maxScale: 2\nRevision minScale: 1\nRevision maxScale: 2\nRevision cpu: 1\nRevision memory: 1Gi\n" in output
    assert "Revision CPU allocation: unset_or_unresolved -> UNRESOLVED (expected request-based)" in output
    assert "Revision startup CPU boost: unset_or_unresolved" in output
    assert ("Worker service minScale: 0\nWorker service maxScale: 1\nWorker revision minScale: 0\n"
            "Worker revision maxScale: 1\nWorker revision cpu: 1\nWorker revision memory: 2Gi\n") in output
    assert "Worker revision CPU allocation: request-based (cpu-throttling=true) -> MATCH (expected request-based)" in output
    assert ("Worker revision startup CPU boost: true\nWorker revision containerConcurrency: 1\n"
            "Worker revision timeoutSeconds: 600") in output
    assert "Worker ingress: all" in output
    assert "Worker command/args: matches the committed worker entrypoint (values withheld)" in output
    assert "Worker invoker IAM check: enforced" in output
    assert "Worker invoker policy: PRIVATE (1 roles/run.invoker member(s); 1 binding(s))" in output
    assert "::warning::" not in output and "::error::" not in output
    assert output.rstrip().endswith("describe-service: PASS")
    # The service's capacity evidence is printed before the worker is read, so a worker defect never costs it.
    assert output.index("Capacity configuration: ") < output.index("Worker serving traffic:")
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


@pytest.mark.parametrize("command,args,verdict", [
    (WORKER_COMMAND, WORKER_ARGS, "matches the committed worker entrypoint (values withheld)"),
    (["uvicorn", "main:app"], ["--workers", "17"],
     "DOES NOT MATCH the committed worker entrypoint (values withheld; compare ci.yml's --command/--args)"),
    (["PRIVATE_COMMAND_SENTINEL"], ["PRIVATE_ARGUMENT_SENTINEL"],
     "DOES NOT MATCH the committed worker entrypoint (values withheld; compare ci.yml's --command/--args)"),
    ([], [], "DOES NOT MATCH the committed worker entrypoint (values withheld; compare ci.yml's --command/--args)"),
])
def test_worker_command_verdict_withholds_values(capfd, monkeypatch, command, args, verdict):
    svc, revision, pregenerate, job_container = _service_fixtures([], [], 80, 300)
    worker, worker_revision, policy = _worker_fixtures(command, args)
    _run(_projection(), svc, _readbacks(revision, pregenerate, worker, worker_revision, policy), monkeypatch)
    captured = capfd.readouterr()
    output = captured.out + captured.err
    assert f"Worker command/args: {verdict}" in output
    assert "PRIVATE_" not in output and "example.invalid" not in output
    for token in command + args + WORKER_COMMAND + WORKER_ARGS + job_container["command"] + job_container["args"]:
        assert token not in output
    assert output.rstrip().endswith("describe-service: PASS")


def _projection():
    workflow = yaml.safe_load((Path(__file__).parents[3] / ".github/workflows/ops.yml").read_text())
    step = next(s for s in workflow["jobs"]["ops"]["steps"]
                if s.get("name") == "Describe service env (values only for known feature flags)")
    return step["run"].split("python3 - <<'PY'\n", 1)[1].split("\nPY", 1)[0]


def _service_fixtures(command, args, concurrency, timeout):
    """API service, its serving revision and the pregenerate job; every private field carries a sentinel."""
    container = {"image": "allowed-api-image", "command": command, "args": args,
                 "resources": {"limits": {"cpu": "1", "memory": "1Gi"}}, "env": [
        {"name": "AI_DEFAULT_MODEL", "value": MODEL},
        {"name": "WEB_CONCURRENCY", "value": "4"},
        {"name": "UVICORN_WORKERS", "valueFrom": {"secretKeyRef": {"name": "PRIVATE_SECRET_SENTINEL"}}},
        {"name": "GUNICORN_CMD_ARGS", "value": "PRIVATE_GUNICORN_SENTINEL"},
        {"name": "UNRELATED", "value": "PRIVATE_ENV_SENTINEL"},
        {"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"},
        {"name": "EDGAR_RATE_LIMIT_PER_SEC", "value": "1"},
        {"name": "DURABLE_TASKS_ENABLED", "value": "true"},
        {"name": "TASKS_WORKER_PROCESS", "value": "false"},
    ]}
    revision = {"spec": {"containers": [container], "containerConcurrency": concurrency,
                         "timeoutSeconds": timeout}, "metadata": {"annotations": {
        "run.googleapis.com/vpc-access-egress": "PRIVATE_EGRESS_SENTINEL",
        "run.googleapis.com/vpc-access-connector": "PRIVATE_CONNECTOR_SENTINEL",
        "run.googleapis.com/network-interfaces": "PRIVATE_NETWORK_SENTINEL",
        "autoscaling.knative.dev/minScale": "1", "autoscaling.knative.dev/maxScale": "2",
        "run.googleapis.com/cpu-throttling": "PRIVATE_THROTTLING_SENTINEL",
        "run.googleapis.com/startup-cpu-boost": "PRIVATE_BOOST_SENTINEL",
        **PRIVATE_NOTES,
    }}}
    svc = {
        "status": {"latestReadyRevisionName": "revision-1", "latestCreatedRevisionName": "revision-1",
                   "traffic": [{"revisionName": "revision-1", "percent": 100,
                                "url": "https://PRIVATE_TRAFFIC_URL_SENTINEL.example.invalid",
                                "PRIVATE_TRAFFIC_SENTINEL": "x"}],
                   "url": "https://PRIVATE_API_HOST_SENTINEL.example.invalid"},
        "metadata": {"annotations": {"run.googleapis.com/ingress": "PRIVATE_INGRESS_SENTINEL",
                                     "run.googleapis.com/maxScale": "2",
                                     "run.googleapis.com/minScale": "PRIVATE_SCALE_SENTINEL",
                                     **PRIVATE_NOTES}},
    }
    job_container = {"image": "allowed-job-image", "command": ["python", "job_task.py"],
                     "args": ["--workers", "29"], "env": [
        {"name": "UNRELATED", "value": "PRIVATE_JOB_ENV_SENTINEL"},
        {"name": "AI_DEFAULT_MODEL", "value": MODEL},
        {"name": "AI_FALLBACK_MODEL", "valueSource": {"secretKeyRef": {"name": "PRIVATE_JOB_SECRET_SENTINEL"}}},
    ]}
    pregenerate = {"spec": {"template": {"spec": {"template": {"spec": {"containers": [job_container]}}}}}}
    return svc, revision, pregenerate, job_container


def _worker_fixtures(command=None, args=None):
    """Private task worker, its serving revision and its invoker policy; hosts, identities and labels are sentinels."""
    worker = {
        "metadata": {"annotations": {"run.googleapis.com/ingress": "all", "run.googleapis.com/minScale": "0",
                                     "run.googleapis.com/maxScale": "1", **PRIVATE_NOTES},
                     "labels": {"PRIVATE_LABEL_SENTINEL": "PRIVATE_LABEL_SENTINEL"}},
        "status": {"latestReadyRevisionName": "worker-revision-1", "latestCreatedRevisionName": "worker-revision-1",
                   "traffic": [{"revisionName": "worker-revision-1", "percent": 100, "latestRevision": True,
                                "url": WORKER_HOST, "PRIVATE_TRAFFIC_SENTINEL": "x"}],
                   "url": WORKER_HOST, "address": {"url": WORKER_HOST}},
    }
    worker_revision = {
        "metadata": {"annotations": {"autoscaling.knative.dev/minScale": "0", "autoscaling.knative.dev/maxScale": "1",
                                     "run.googleapis.com/cpu-throttling": "true",
                                     "run.googleapis.com/startup-cpu-boost": "true", **PRIVATE_NOTES}},
        "spec": {"containerConcurrency": 1, "timeoutSeconds": 600, "containers": [{
            "image": "allowed-worker-image",
            "command": WORKER_COMMAND if command is None else command,
            "args": WORKER_ARGS if args is None else args,
            "resources": {"limits": {"cpu": "1", "memory": "2Gi"}},
            "env": [
                {"name": "AI_DEFAULT_MODEL", "value": MODEL},
                {"name": "TASKS_WORKER_URL", "value": WORKER_HOST},
                {"name": "TASKS_INVOKER_EMAIL", "value": "PRIVATE_INVOKER_EMAIL_SENTINEL"},
                {"name": "TASKS_WORKER_PROCESS", "value": "true"},
                {"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"},
                {"name": "EDGAR_RATE_LIMIT_PER_SEC", "value": "1"},
                {"name": "DURABLE_TASKS_ENABLED", "value": "true"},
                {"name": "DATABASE_URL", "valueFrom": {"secretKeyRef": {"name": "PRIVATE_WORKER_SECRET_SENTINEL"}}},
            ]}]},
    }
    policy = {"bindings": [{"role": "roles/run.invoker",
                            "members": ["serviceAccount:PRIVATE_INVOKER_SENTINEL@example.invalid"]}],
              "etag": "PRIVATE_ETAG_SENTINEL"}
    return worker, worker_revision, policy


def _readbacks(revision, pregenerate, worker, worker_revision, policy):
    """The five gcloud reads the heredoc makes, in order, keyed by (kind, verb, name)."""
    return {("revisions", "describe", "revision-1"): revision,
            ("jobs", "describe", "earningsnerd-pregenerate"): pregenerate,
            ("services", "describe", "earningsnerd-task-worker"): worker,
            ("revisions", "describe", "worker-revision-1"): worker_revision,
            ("services", "get-iam-policy", "earningsnerd-task-worker"): policy}


def _run(projection, svc, readbacks, monkeypatch):
    """Execute the heredoc against a dict-keyed gcloud fake; returns (the open mock, the ordered read keys)."""
    calls = []

    def describe(argv: list[str], *, text: bool, stderr, timeout) -> str:
        assert argv[:2] == ["gcloud", "run"] and argv[3] in ("describe", "get-iam-policy")
        assert argv[5:] == ["--region=offline-region", "--format=json"] and text is True
        assert stderr is subprocess.PIPE and timeout == 120  # stderr is classified, never inherited by the log
        key = (argv[2], argv[3], argv[4])
        calls.append(key)
        return json.dumps(readbacks[key])

    monkeypatch.setenv("REGION", "offline-region")
    monkeypatch.setattr(subprocess, "check_output", describe)
    service_json = mock_open(read_data=json.dumps(svc))
    exec(projection, {"open": service_json})
    return service_json, calls
