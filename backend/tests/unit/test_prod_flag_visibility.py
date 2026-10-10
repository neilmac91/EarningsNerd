"""Observed production pins and read-only configuration evidence; no cloud/model calls."""
import ast
import importlib.util
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from app.config import Settings
from scripts import pin_baseline

ROOT = Path(__file__).resolve().parents[3]
MODULE = ROOT / "ops/describe/service.py"  # the readback the describe-service step runs
PROD_ENV_PINS = {
    "NOTABLE_FILINGS_ENABLED": "true", "AI_EVIDENCE_SNAP": "true",
    "AI_FIGURE_TRACE_GATE": "false", "AI_FORWARD_QUOTE_GATE": "false", "AI_ATTRIBUTION_GATE": "false",
    "AI_ATTRIBUTION_VERIFY": "false",
    "USE_STRUCTURED_OUTPUT": "false", "USE_STATEMENT_FINANCIALS": "true",
    # Founder-approved W3-1 observation: keep the live service filter, not the old plan's false.
    "CALENDAR_INDEX_FILTER_ENABLED": "true", "ENABLE_FPI_FILINGS": "true",
    "STREAM_SECTION_REVEAL": "true", "REGISTRATION_MODE": "invite_only",
    # CODE RED D3 stage 2: the pinned service cannot carry the insider endpoint's cold fetch.
    "ENABLE_INSIDER_ACTIVITY": "false",
}
INTENTIONAL_PROD_OVERRIDES = {
    # Delegated Sep28 rollout: source-faithful labels and seven observed scheduled days.
    # This serving-only feature stays off by default in local/dev.
    "NOTABLE_FILINGS_ENABLED",
    "ENABLE_FPI_FILINGS", "STREAM_SECTION_REVEAL", "REGISTRATION_MODE",
    "CALENDAR_INDEX_FILTER_ENABLED",
    # Founder armed evidence auto-snap on 2026-09-15 after the first complete strong-judge readout
    # (W3-7, D5); the code default stays off so local/dev keeps the advisory audit.
    "AI_EVIDENCE_SNAP",
}


def _workflow(name):
    return yaml.load((ROOT / ".github/workflows" / name).read_text(), Loader=yaml.BaseLoader)


def _step(job, name):
    return next(step for step in job["steps"] if step.get("name") == name)


def _executable(run):
    return "\n".join(line for line in run.splitlines() if not line.lstrip().startswith("#"))


def _env_map(run):
    executable = _executable(run)
    values = re.findall(r"--update-env-vars=(\S+)", executable)
    assert len(values) == 1
    entries = [item.split("=", 1) for item in values[0].split(",")]
    assert all(len(entry) == 2 for entry in entries)
    assert len({key for key, _ in entries}) == len(entries), "Duplicate deployment env key"
    return dict(entries)


def _ops_code():
    step = _step(_workflow("ops.yml")["jobs"]["ops"],
                 "Describe service env (values only for known feature flags)")
    assert step["run"] == "python3 ops/describe/service.py"  # the literals read below are the code the step runs
    return MODULE.read_text()


def _load():
    """Execute the committed describe-service module by path; its top level is the readback."""
    spec = importlib.util.spec_from_file_location("ops_describe_service", MODULE)
    module = importlib.util.module_from_spec(spec)
    module.open = Mock(side_effect=AssertionError("the readback reads no file"))  # every read is a gcloud read
    spec.loader.exec_module(module)


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
                   and node.targets[0].id in {"allow", "flag_defaults", "expected_worker_command",
                                              "expected_worker_args"}}
    assert set(pin_baseline.AI_GUARD_ENV) == {
        "AI_EVIDENCE_SNAP", "AI_FIGURE_TRACE_GATE", "AI_FORWARD_QUOTE_GATE", "AI_ATTRIBUTION_GATE",
        "AI_ATTRIBUTION_VERIFY", "USE_STRUCTURED_OUTPUT", "USE_STATEMENT_FINANCIALS",
    }
    assert assignments["allow"] >= PROD_ENV_PINS.keys()
    # The allow-list is the only gate deciding which env values print to the public log: pin it exactly.
    assert assignments["allow"] == {
        "USE_STATEMENT_FINANCIALS", "ENABLE_FPI_FILINGS", "STREAM_SECTION_REVEAL", "AI_DEFAULT_MODEL",
        "OPENAI_BASE_URL", "ENVIRONMENT", "TRUSTED_PROXY_HOPS", "COOKIE_DOMAIN", "NOTABLE_FILINGS_ENABLED",
        "AI_EVIDENCE_SNAP", "AI_FIGURE_TRACE_GATE", "AI_FORWARD_QUOTE_GATE", "AI_ATTRIBUTION_GATE",
        "AI_ATTRIBUTION_VERIFY", "USE_STRUCTURED_OUTPUT", "CALENDAR_INDEX_FILTER_ENABLED", "REGISTRATION_MODE",
        "AI_FALLBACK_MODEL", "AI_FALLBACK_BASE_URL", "SENTRY_RELEASE", "DB_POOL_SIZE", "DB_MAX_OVERFLOW",
        "SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC", "DURABLE_TASKS_ENABLED", "ENABLE_INSIDER_ACTIVITY",
        "TASKS_WORKER_PROCESS",
    }
    assert assignments["flag_defaults"].keys() >= PROD_ENV_PINS.keys()
    for key, value in assignments["flag_defaults"].items():
        default = Settings.model_fields[key].default
        assert type(value) is type(default) and value == default, key
    # The worker entrypoint verdict compares against the entrypoint the deploy pins, so it cannot drift from it.
    worker = _executable(_step(job, "Update configured private task worker")["run"])
    assert assignments["expected_worker_command"] == [re.search(r"--command=(\S+)", worker).group(1)] == ["uvicorn"]
    assert assignments["expected_worker_args"] == re.search(r"--args='([^']*)'", worker).group(1).split(",")


@pytest.mark.parametrize("defect", ["missing", "comment", "duplicate-key", "duplicate-step", "wrong-command", "guard-value"])
def test_pin_parser_rejects_unusable_service_evidence(monkeypatch, tmp_path, defect):
    source = pin_baseline.CI_PATH.read_text()
    # Mutate the selected public API step even when a private worker appears earlier in CI.
    prefix, source = source.split("- name: Deploy Cloud Run service", 1)
    source = "- name: Deploy Cloud Run service" + source
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
        source = source.replace("AI_EVIDENCE_SNAP=true", "AI_EVIDENCE_SNAP=1", 1)
    path = tmp_path / "ci.yml"
    path.write_text(prefix + source)
    monkeypatch.setattr(pin_baseline, "CI_PATH", path)
    with pytest.raises(ValueError, match="Cannot pin"):
        pin_baseline.production_env()


# The five gcloud reads of describe-service after the API service describe, in order, keyed by (kind, verb, name).
FIVE = [("revisions", "describe", "serving"), ("jobs", "describe", "earningsnerd-pregenerate"),
        ("services", "describe", "earningsnerd-task-worker"), ("revisions", "describe", "worker-serving"),
        ("services", "get-iam-policy", "earningsnerd-task-worker")]
# The API service describe comes first (it was the step's shell read, outside the classified seam).
SERVICE = "earningsnerd-backend"
SERVICE_READ = ("services", "describe", SERVICE)
SERVICE_ARGV = ["gcloud", "run", "services", "describe", SERVICE, "--region=fixture-region", "--format=json"]
# gcloud's error text can name the acting principal; the readback reduces it to a class and never echoes it.
STDERR = "PRIVATE_STDERR_SENTINEL principal@example.invalid"
PIN_DEFECTS = {"missing": "<missing>", "secret-ref": "<secret-ref>", "10": "'10'",
               "1 ": "<value withheld: not a plain numeric string>", 1: "<value withheld: not a plain numeric string>",
               "PRIVATE_PIN_VALUE_SENTINEL": "<value withheld: not a plain numeric string>"}
MISMATCH = "Worker command/args: DOES NOT MATCH the committed worker entrypoint (values withheld; compare ci.yml's --command/--args)"


def _readbacks(revision, job, worker, worker_revision, policy):
    return dict(zip(FIVE, (revision, job, worker, worker_revision, policy)))


def _execute(service, readbacks, *, denied=None, raw=None):
    """Run the module with a dict-keyed gcloud fake; returns (output, SystemExit or None, the ordered read keys
    after the API service describe, which must come first).

    `denied` maps a read key to the stderr text of a failing gcloud (CalledProcessError), to "timeout" or to
    "missing" (no gcloud executable); `raw` maps a read key to non-JSON stdout."""
    denied = denied or {}
    raw = raw or {}
    reads = {SERVICE_READ: service, **readbacks}
    calls = []

    def fake(argv, *, text, stderr, timeout):
        assert argv[:2] == ["gcloud", "run"] and argv[3] in ("describe", "get-iam-policy")
        assert argv[5:] == ["--region=fixture-region", "--format=json"] and text is True
        assert stderr is subprocess.PIPE and timeout == 100
        key = (argv[2], argv[3], argv[4])
        calls.append(key)
        if key in denied:
            if denied[key] == "timeout":
                raise subprocess.TimeoutExpired(argv, timeout)
            if denied[key] == "missing":
                raise FileNotFoundError(2, "No such file or directory", "gcloud")
            raise subprocess.CalledProcessError(1, argv, output="", stderr=denied[key])
        if key in raw:
            return raw[key]
        return json.dumps(reads[key])

    output = io.StringIO()
    exit_ = None
    with patch.dict("os.environ", {"REGION": "fixture-region", "SERVICE": SERVICE}), \
            patch("subprocess.check_output", new=fake), \
            redirect_stdout(output):
        try:
            _load()
        except SystemExit as exc:
            exit_ = exc
    assert calls[:1] == [SERVICE_READ], calls  # the API service describe is always the first read
    return output.getvalue(), exit_, calls[1:]


def _service_then(service, later):
    """A gcloud fake serving the API service describe (exact argv) and handing every later read to `later`."""
    def fake(argv, *, text, stderr, timeout):
        if argv == SERVICE_ARGV:
            assert text is True and stderr is subprocess.PIPE and timeout == 100
            return json.dumps(service)
        return later(argv, text=text, stderr=stderr, timeout=timeout)
    return fake


def _render(service, revision, job, worker, worker_revision, policy):
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    if exit_ is not None:
        raise exit_
    assert calls == FIVE
    return output


def _plant_pin(container, pin, defect):
    container["env"] = [entry for entry in container["env"] if entry["name"] != pin]
    if defect == "secret-ref":
        container["env"].append({"name": pin, "valueFrom": {"secretKeyRef": {"name": "hidden-reference"}}})
    elif defect != "missing":
        container["env"].append({"name": pin, "value": defect})


@pytest.fixture
def resources():
    def container(image, value):
        return {"image": image, "env": [
            {"name": "CALENDAR_INDEX_FILTER_ENABLED", "value": value},
            {"name": "AI_EVIDENCE_SNAP", "valueFrom": {"secretKeyRef": {"name": "hidden-reference"}}},
            {"name": "AI_FIGURE_TRACE_GATE", "valueSource": {"secretKeyRef": {"name": "hidden-reference"}}},
            {"name": "AI_FALLBACK_API_KEY", "value": "hidden-credential"},
            {"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"},
            {"name": "EDGAR_RATE_LIMIT_PER_SEC", "value": "1"},
        ]}
    worker_container = container("worker-image", "true")
    worker_container["env"] += [{"name": "TASKS_WORKER_URL", "value": "hidden-host"},
                                {"name": "TASKS_WORKER_PROCESS", "value": "true"}]
    return (
        {"status": {"latestReadyRevisionName": "serving", "latestCreatedRevisionName": "serving", "url": "hidden-host",
                    "traffic": [{"revisionName": "serving", "percent": 100, "url": "hidden-host"}]}},
        {"spec": {"containers": [container("service-image", "true")]}},
        {"spec": {"template": {"spec": {"template": {"spec": {
            "containers": [container("job-image", "false")]}}}}}},
        {"metadata": {"annotations": {"run.googleapis.com/ingress": "all"}},
         "status": {"latestReadyRevisionName": "worker-serving", "latestCreatedRevisionName": "worker-serving",
                    "url": "hidden-host",
                    "traffic": [{"revisionName": "worker-serving", "percent": 100, "url": "hidden-host"}]}},
        {"spec": {"containers": [worker_container]}},  # no command/args: the entrypoint verdict reads MISMATCH
        {"bindings": [{"role": "roles/run.invoker", "members": ["serviceAccount:hidden-invoker"]}]},
    )


def test_ops_renderer_binds_masked_values_to_distinct_resources(resources):
    service, revision, job, worker, worker_revision, policy = resources
    # A stale service template is deliberately different from the immutable serving revision.
    service["spec"] = {"template": {"spec": {"containers": [{"image": "stale-template"}]}}}
    output = _render(service, revision, job, worker, worker_revision, policy)
    left, right = output.split("Job: earningsnerd-pregenerate")
    assert "Serving revision: serving" in left and "service-image" in left
    assert "CALENDAR_INDEX_FILTER_ENABLED = 'true'" in left
    assert "job-image" in right and "CALENDAR_INDEX_FILTER_ENABLED = 'false'" in right
    assert "Worker revision: worker-serving" in right and "worker-image" in right
    assert "TASKS_WORKER_PROCESS = 'true'" in right
    for rendered in (left, right):
        assert "AI_EVIDENCE_SNAP = <secret-ref>" in rendered
        assert "AI_FIGURE_TRACE_GATE = <secret-ref>" in rendered
        assert "AI_FALLBACK_API_KEY = <set; value withheld>" in rendered
        assert "USE_STATEMENT_FINANCIALS = <NOT SET -> Settings default applies (True)>" in rendered
        assert "EDGAR_RATE_LIMIT_PER_SEC = '1'" in rendered
        assert "verify these against the reported image before pinning" in rendered
    assert "hidden-credential" not in output and "hidden-reference" not in output
    assert "stale-template" not in output
    assert "hidden-host" not in output and "hidden-invoker" not in output
    # No DURABLE_TASKS_ENABLED pin expects always-allocated CPU; an absent annotation reads request-based.
    assert "Revision CPU allocation: request-based (cpu-throttling annotation absent) -> MISMATCH (expected always-allocated)" in output
    assert "Revision cpu: unset_or_unresolved" in output
    assert "Service minScale: absent (service-level minimum off, 0 per Cloud Run docs)" in output
    assert MISMATCH in output
    assert output.rstrip().endswith("describe-service: PASS")


@pytest.mark.parametrize("defect", ["missing", "rollback", "split", "unready"])
def test_ops_renderer_rejects_unresolved_traffic_before_describing(resources, defect):
    service, revision, job, *_ = resources
    match = "100% traffic"
    if defect == "missing":
        service["status"].pop("traffic")
    elif defect == "rollback":
        service["status"]["traffic"][0]["revisionName"] = "older"
    elif defect == "split":
        service["status"]["traffic"] = [{"revisionName": "serving", "percent": 50},
                                         {"revisionName": "older", "percent": 50}]
    else:
        service["status"]["latestCreatedRevisionName"] = "unready"
        match = r"100% traffic.*latest created revision unready is not ready \(latest ready serving\)"
    describe = Mock(side_effect=[json.dumps(revision), json.dumps(job)])  # every read after the service describe
    with patch("subprocess.check_output", new=_service_then(service, describe)), \
            patch.dict("os.environ", {"REGION": "fixture-region", "SERVICE": SERVICE}), \
            pytest.raises(SystemExit, match=match):
        # _render would install a second patch, so execute directly for the no-later-read assertion.
        _load()
    describe.assert_not_called()


@pytest.mark.parametrize("step", ["Deploy Cloud Run service", "Update configured private task worker"])
def test_deploy_routes_traffic_to_latest_and_clears_revision_tags(step):
    """A tagged revision stays addressable at its own URL at 0% traffic, so a leftover tag keeps a
    retired image serving beside the release; every deploy must clear tags when it routes traffic."""
    job = _workflow("ci.yml")["jobs"]["deploy-backend"]
    run = _step(job, step)["run"]
    executable = [line.strip() for line in run.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    traffic = [line for line in executable if "update-traffic" in line]
    assert len(traffic) == 1, f"expected exactly one update-traffic command, found {traffic}"
    assert "--to-latest" in traffic[0] and "--clear-tags" in traffic[0], traffic[0]


def test_ops_renderer_rejects_tagged_traffic_targets(resources):
    service, revision, job, *_ = resources
    service["status"]["traffic"].append({"revisionName": "retired", "percent": 0, "tag": "old", "url": "hidden-host"})
    describe = Mock(side_effect=[json.dumps(revision), json.dumps(job)])  # every read after the service describe
    with patch("subprocess.check_output", new=_service_then(service, describe)), \
            patch.dict("os.environ", {"REGION": "fixture-region", "SERVICE": SERVICE}), \
            pytest.raises(SystemExit, match="tagged traffic targets") as excinfo:
        _load()
    describe.assert_not_called()
    assert "hidden-host" not in str(excinfo.value)


@pytest.mark.parametrize("resource,count", [("revision", 0), ("revision", 2), ("job", 0), ("job", 2),
                                            ("worker", 0), ("worker", 2)])
def test_ops_renderer_requires_single_application_container(resources, resource, count):
    service, revision, job, worker, worker_revision, policy = resources
    spec = {"revision": revision["spec"], "job": job["spec"]["template"]["spec"]["template"]["spec"],
            "worker": worker_revision["spec"]}[resource]
    spec["containers"] *= count
    with pytest.raises(SystemExit, match="one application container"):
        _render(service, revision, job, worker, worker_revision, policy)


@pytest.mark.parametrize("defect", list(PIN_DEFECTS))
@pytest.mark.parametrize("pin", ["SEC_RATE_LIMIT_PER_SECOND", "EDGAR_RATE_LIMIT_PER_SEC"])
@pytest.mark.parametrize("target", ["service", "worker"])
def test_ops_renderer_collects_sec_pin_defects_and_prints_every_block(resources, target, pin, defect):
    """A pin defect is announced where it is found, every later block still prints, and the step exits once."""
    service, revision, job, worker, worker_revision, policy = resources
    _plant_pin((revision if target == "service" else worker_revision)["spec"]["containers"][0], pin, defect)
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    label = "Serving revision serving" if target == "service" else "Worker revision worker-serving"
    assert exit_ is not None and calls == FIVE
    assert f"{label} must pin {pin}=1 as a plain value, got {PIN_DEFECTS[defect]}" in str(exit_)
    errors = [line for line in output.splitlines() if line.startswith("::error::")]
    assert len(errors) == 1 and f"must pin {pin}=1" in errors[0]
    assert "Worker invoker policy: PRIVATE" in output
    assert "describe-service: FAIL (1 invariant failure(s))" in output and "describe-service: PASS" not in output
    # An echoed pin value is bounded to a short digit string; a sentinel never reaches the env block, the exit or the error line.
    assert "PRIVATE_" not in output + str(exit_)


def test_ops_renderer_lists_every_pin_defect_once(resources):
    service, revision, job, worker, worker_revision, policy = resources
    _plant_pin(revision["spec"]["containers"][0], "EDGAR_RATE_LIMIT_PER_SEC", "10")
    _plant_pin(worker_revision["spec"]["containers"][0], "SEC_RATE_LIMIT_PER_SECOND", "PRIVATE_PIN_VALUE_SENTINEL")
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    assert exit_ is not None and calls == FIVE
    assert "Serving revision serving must pin EDGAR_RATE_LIMIT_PER_SEC=1 as a plain value, got '10'" in str(exit_)
    assert ("Worker revision worker-serving must pin SEC_RATE_LIMIT_PER_SECOND=1 as a plain value, "
            "got <value withheld: not a plain numeric string>") in str(exit_)
    errors = [line for line in output.splitlines() if line.startswith("::error::")]
    assert len(errors) == 2 and "describe-service: FAIL (2 invariant failure(s))" in output
    # The env block prints the nonnumeric pin through the same bounded formatter as the verdict, so the whole output is clean.
    assert "SEC_RATE_LIMIT_PER_SECOND = <value withheld: not a plain numeric string>" in output
    assert "PRIVATE_" not in output + str(exit_)


def test_ops_renderer_collects_duplicate_env_names(resources):
    """Container env resolution is last-wins, so a duplicate name could mask a pin: it is a collected defect."""
    service, revision, job, worker, worker_revision, policy = resources
    revision["spec"]["containers"][0]["env"].append({"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"})
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    assert exit_ is not None and calls == FIVE
    assert "Serving revision serving has a duplicate or nameless env entry" in str(exit_)
    errors = [line for line in output.splitlines() if line.startswith("::error::")]
    assert len(errors) == 1 and "duplicate or nameless env entry" in errors[0]
    assert "describe-service: FAIL (1 invariant failure(s))" in output


def test_ops_renderer_immediate_exit_names_collected_defects(resources):
    """A service pin defect is collected; an undescribable worker then exits at once, naming both."""
    service, revision, job, worker, worker_revision, policy = resources
    _plant_pin(revision["spec"]["containers"][0], "EDGAR_RATE_LIMIT_PER_SEC", "10")
    readbacks = _readbacks(revision, job, worker, worker_revision, policy)
    output, exit_, calls = _execute(service, readbacks, denied={FIVE[2]: "ERROR: NOT_FOUND " + STDERR})
    assert exit_ is not None and calls == FIVE[:3]
    assert "Serving revision serving must pin EDGAR_RATE_LIMIT_PER_SEC=1 as a plain value, got '10'" in str(exit_)
    assert "cannot describe services earningsnerd-task-worker (not_found)" in str(exit_)
    assert "describe-service:" not in output and "PRIVATE_" not in output + str(exit_)


@pytest.mark.parametrize("defect", ["rollback", "split", "unready", "tagged"])
def test_ops_renderer_rejects_worker_traffic_defects(resources, defect):
    """A worker traffic defect exits after the worker describe; the service's evidence has already printed."""
    service, revision, job, worker, worker_revision, policy = resources
    status = worker["status"]
    if defect == "rollback":
        status["traffic"][0]["revisionName"] = "older"
    elif defect == "split":
        status["traffic"] = [{"revisionName": "worker-serving", "percent": 50, "url": "hidden-host"},
                             {"revisionName": "older", "percent": 50, "url": "hidden-host"}]
    elif defect == "unready":
        status["latestCreatedRevisionName"] = "unready"
    else:
        status["traffic"].append({"revisionName": "retired", "percent": 0, "tag": "old", "url": "hidden-host"})
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    assert exit_ is not None and calls == FIVE[:3]
    expected = "tagged traffic targets" if defect == "tagged" else "100% traffic on the latest ready revision of the Worker"
    assert expected in str(exit_)
    assert "Capacity configuration: " in output
    assert "hidden-host" not in output and "hidden-host" not in str(exit_)


@pytest.mark.parametrize("principal", ["allUsers", "allAuthenticatedUsers"])
@pytest.mark.parametrize("role", ["roles/run.invoker", "roles/run.servicesInvoker", "roles/run.viewer"])
def test_ops_renderer_fails_closed_on_public_invoker(resources, role, principal):
    """Several predefined roles carry run.routes.invoke, so a public principal on ANY binding is public."""
    service, revision, job, worker, worker_revision, policy = resources
    policy["bindings"].append({"role": role, "members": [principal]})
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    assert exit_ is not None and calls == FIVE
    assert f"admits a public principal: {principal} on {role}" in str(exit_)
    assert f"Worker invoker policy: PUBLIC ({principal} on {role})" in output
    assert "Worker invoker policy: PRIVATE" not in output and "hidden-invoker" not in output


@pytest.mark.parametrize("value", ["true", "True "])
def test_ops_renderer_fails_closed_on_disabled_invoker_iam_check(resources, value):
    service, revision, job, worker, worker_revision, policy = resources
    worker["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = value
    output, exit_, calls = _execute(service, _readbacks(revision, job, worker, worker_revision, policy))
    assert exit_ is not None and calls == FIVE  # the policy is still read and reported
    assert "invoker IAM check is disabled" in str(exit_)
    assert "Worker invoker IAM check: DISABLED" in output


@pytest.mark.parametrize("failure,klass,remedy", [
    ("ERROR: (gcloud.run.services.get-iam-policy) PERMISSION_DENIED: " + STDERR, "permission_denied",
     "run.services.getIamPolicy"),
    ("ERROR: NOT_FOUND: " + STDERR, "not_found", "did not resolve"),
    ("ERROR: UNAVAILABLE: " + STDERR, "unavailable", "re-dispatch"),
    ("ERROR: odd " + STDERR, "error (gcloud exit 1)", "re-dispatch"),
    ("timeout", "timeout", "re-dispatch"),
])
def test_ops_renderer_reports_denied_invoker_policy_as_unverified(resources, failure, klass, remedy):
    """A denied or failed policy read is UNVERIFIED with a closed failure class: never PRIVATE, never a crash,
    never gcloud's stderr; the step passes with a qualified verdict when nothing else failed."""
    service, revision, job, worker, worker_revision, policy = resources
    readbacks = _readbacks(revision, job, worker, worker_revision, policy)
    output, exit_, calls = _execute(service, readbacks, denied={FIVE[4]: failure})
    assert exit_ is None and calls == FIVE
    assert f"Worker invoker policy: UNVERIFIED ({klass})" in output
    assert "Worker invoker policy: PRIVATE" not in output
    warnings = [line for line in output.splitlines() if line.startswith("::warning::")]
    assert len(warnings) == 1 and f"UNVERIFIED ({klass})" in warnings[0] and remedy in warnings[0]
    assert output.rstrip().splitlines()[-1] == f"describe-service: PASS; UNVERIFIED: worker invoker policy ({klass})"
    assert "PRIVATE_STDERR_SENTINEL" not in output and "principal@" not in output


@pytest.mark.parametrize("policy,raw", [
    ({"bindings": [{"role": "roles/run.invoker", "members": "allUsers"}]}, False),
    ({"bindings": "x"}, False),
    (["list"], False),
    ({"bindings": [{"role": 7, "members": []}]}, False),
    ({"bindings": [{"role": "roles/run.invoker", "members": [1]}]}, False),
    ("<html>not a policy</html>", True),
])
def test_ops_renderer_treats_malformed_policy_as_unverified(resources, policy, raw):
    service, revision, job, worker, worker_revision, _ = resources
    readbacks = _readbacks(revision, job, worker, worker_revision, policy)
    output, exit_, calls = _execute(service, readbacks, raw={FIVE[4]: policy} if raw else None)
    assert exit_ is None and calls == FIVE
    assert "Worker invoker policy: UNVERIFIED (unreadable_response)" in output
    assert "Worker invoker policy: PRIVATE" not in output and "PUBLIC" not in output


@pytest.mark.parametrize("defect", ["pin", "iam-check"])
def test_ops_renderer_unverified_never_masks_a_fail(resources, defect):
    service, revision, job, worker, worker_revision, policy = resources
    if defect == "pin":
        _plant_pin(worker_revision["spec"]["containers"][0], "EDGAR_RATE_LIMIT_PER_SEC", "10")
        expected = "must pin EDGAR_RATE_LIMIT_PER_SEC"
    else:
        worker["metadata"]["annotations"]["run.googleapis.com/invoker-iam-disabled"] = "true"
        expected = "invoker IAM check is disabled"
    readbacks = _readbacks(revision, job, worker, worker_revision, policy)
    output, exit_, calls = _execute(service, readbacks, denied={FIVE[4]: "ERROR: PERMISSION_DENIED: " + STDERR})
    assert exit_ is not None and calls == FIVE and expected in str(exit_)
    assert "Worker invoker policy: UNVERIFIED (permission_denied)" in output
    assert "describe-service: FAIL (1 invariant failure(s))" in output


@pytest.mark.parametrize("failure,klass", [("ERROR: NOT_FOUND " + STDERR, "not_found"), ("timeout", "timeout"),
                                           ("ERROR: DEADLINE_EXCEEDED " + STDERR, "unavailable"),
                                           ("<html>", "unreadable_response")])
@pytest.mark.parametrize("index", [0, 1, 2, 3])
def test_ops_renderer_fails_closed_on_failed_describe(resources, index, failure, klass):
    """Every describe read the readback depends on fails closed with its class; stderr never reaches the log."""
    service, revision, job, worker, worker_revision, policy = resources
    kind, _, name = key = FIVE[index]
    readbacks = _readbacks(revision, job, worker, worker_revision, policy)
    if klass == "unreadable_response":
        output, exit_, calls = _execute(service, readbacks, raw={key: failure})
    else:
        output, exit_, calls = _execute(service, readbacks, denied={key: failure})
    assert exit_ is not None and calls == FIVE[:index + 1]
    assert f"cannot describe {kind} {name} ({klass})" in str(exit_)
    assert "PRIVATE_STDERR_SENTINEL" not in output + str(exit_)


@pytest.mark.parametrize("failure,klass", [
    ("ERROR: (gcloud.run.services.describe) PERMISSION_DENIED: " + STDERR, "permission_denied"),
    ("ERROR: NOT_FOUND " + STDERR, "not_found"), ("ERROR: UNAVAILABLE " + STDERR, "unavailable"),
    ("ERROR: DEADLINE_EXCEEDED " + STDERR, "unavailable"), ("ERROR: odd " + STDERR, "error (gcloud exit 1)"),
    ("timeout", "timeout"), ("missing", "error (gcloud not executable)"), ("<html>", "unreadable_response"),
])
def test_ops_renderer_fails_closed_on_failed_service_describe(resources, failure, klass):
    """The API service describe, once the step's shell read that printed gcloud's own error text, fails closed with
    its class before any other read and prints nothing else (no traffic line, no verdict)."""
    service, revision, job, worker, worker_revision, policy = resources
    readbacks = _readbacks(revision, job, worker, worker_revision, policy)
    if klass == "unreadable_response":
        output, exit_, calls = _execute(service, readbacks, raw={SERVICE_READ: failure})
    else:
        output, exit_, calls = _execute(service, readbacks, denied={SERVICE_READ: failure})
    assert exit_ is not None and calls == []
    assert str(exit_) == f"Unresolved production configuration: cannot describe services {SERVICE} ({klass})."
    assert output == "" and "PRIVATE_STDERR_SENTINEL" not in str(exit_) and "principal@" not in str(exit_)


@pytest.mark.parametrize("throttling,durable,expected", [
    ("false", "true", "always-allocated (cpu-throttling=false) -> MISMATCH (expected request-based)"),
    ("false", "false", "always-allocated (cpu-throttling=false) -> MATCH (expected always-allocated)"),
    ("true", "true", "request-based (cpu-throttling=true) -> MATCH (expected request-based)"),
    (None, "false", "request-based (cpu-throttling annotation absent) -> MISMATCH (expected always-allocated)"),
    ("PRIVATE_X", "true", "unset_or_unresolved -> UNRESOLVED (expected request-based)"),
])
def test_ops_renderer_sizing_vocabulary(resources, throttling, durable, expected):
    """CPU allocation is derived from DURABLE_TASKS_ENABLED as ci.yml derives it; absent annotations print their
    documented meaning; values outside the closed grammar are withheld."""
    service, revision, job, worker, worker_revision, policy = resources
    notes = {} if throttling is None else {"run.googleapis.com/cpu-throttling": throttling}
    revision["metadata"] = {"annotations": notes}
    revision["spec"]["containers"][0]["env"].append({"name": "DURABLE_TASKS_ENABLED", "value": durable})
    revision["spec"]["containers"][0]["resources"] = {"limits": {"cpu": "1", "memory": "1.5Gi"}}
    worker["metadata"]["annotations"].pop("run.googleapis.com/ingress")
    output = _render(service, revision, job, worker, worker_revision, policy)
    assert f"Revision CPU allocation: {expected}" in output
    assert "Revision cpu: 1\nRevision memory: 1.5Gi\n" in output
    assert "Service minScale: absent (service-level minimum off, 0 per Cloud Run docs)" in output
    assert "Worker ingress: absent (annotation not set; gcloud deploy default is all)" in output
    assert "PRIVATE_X" not in output


def test_ops_renderer_notes_missing_invoker_binding(resources):
    service, revision, job, worker, worker_revision, _ = resources
    output = _render(service, revision, job, worker, worker_revision, {"etag": "x"})
    assert ("Worker invoker policy: PRIVATE (0 roles/run.invoker member(s); 0 binding(s); "
            "no invoker binding: Cloud Tasks cannot invoke the worker (founder IAM item))") in output
    assert output.rstrip().endswith("describe-service: PASS")


def test_ops_renderer_parses_minimal_shapes_without_raising():
    """Describe JSON without metadata, resources, traffic URLs or a policy body renders with documented defaults."""
    def pins():
        return [{"name": "SEC_RATE_LIMIT_PER_SECOND", "value": "1"}, {"name": "EDGAR_RATE_LIMIT_PER_SEC", "value": "1"}]
    service = {"status": {"latestReadyRevisionName": "serving", "latestCreatedRevisionName": "serving",
                          "traffic": [{"revisionName": "serving", "percent": 100}]}}
    revision = {"spec": {"containers": [{"image": "i", "env": pins()}]}}
    job = {"spec": {"template": {"spec": {"template": {"spec": {"containers": [{"image": "j"}]}}}}}}
    worker = {"status": {"latestReadyRevisionName": "worker-serving", "latestCreatedRevisionName": "worker-serving",
                         "traffic": [{"revisionName": "worker-serving", "percent": 100}]}}
    worker_revision = {"spec": {"containers": [{"image": "k", "env": pins()}]}}
    output = _render(service, revision, job, worker, worker_revision, {})
    assert "Revision cpu: unset_or_unresolved" in output and "Revision containerConcurrency: None" in output
    assert "Revision CPU allocation: request-based (cpu-throttling annotation absent) -> MISMATCH (expected always-allocated)" in output
    assert MISMATCH in output
    # A container without the edgartools pin reports the library default, not a Settings default.
    assert "EDGAR_RATE_LIMIT_PER_SEC = <NOT SET -> edgartools default 9>" in output.split("Job: earningsnerd-pregenerate")[1]
