"""Offline safety/ownership checks; these never claim actual Google delivery evidence."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import threading
import time
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.summary_delivery import instance, manage, runtime, spec  # noqa: E402

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64
ENV = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "456",
       "SUMMARY_DELIVERY_APPROVED": "true", "SUMMARY_DELIVERY_DEPLOYER": "github-actions@earnings-nerd.iam.gserviceaccount.com"}
EXPECTED_SQL_PERMISSIONS = ["cloudsql.instances.connect", "cloudsql.instances.create", "cloudsql.instances.delete",
                            "cloudsql.instances.get", "cloudsql.instances.list"]


def document():
    return spec.plan(ROOT, IMAGE, "123456789", "123", "b" * 32, now=NOW)


def approved(doc=None, **kwargs):
    doc = doc or document()
    return spec.approve(doc, doc["sha256"], doc["manifest"]["nonce"], ENV, now=NOW, **kwargs)


def test_plan_has_exact_private_bounded_resources_and_no_credentials():
    doc = document()
    m = approved(doc)
    assert (len(m["services"]), len(m["queues"]), len(m["identities"]), len(m["secrets"])) == (3, 2, 2, 2)
    assert len({s["name"] for s in m["services"]}) == 3
    assert "app/services/summary_recovery.py" in m["source_hashes"]
    assert "app/services/request_work.py" in m["source_hashes"]
    assert all(s["private"] and s["max_instances"] == s["concurrency"] == 1 for s in m["services"])
    assert m["schema"] == 2 and m["resource_expiry_is_enforced"] is False
    for role in spec.ROLES:
        service = spec.service_spec(m, {"DATABASE_URL": "1", "SECRET_KEY": "2"}, role,
                                    (ROOT / "ops/summary_delivery/runtime.py").read_text())
        refs = [v["valueSource"]["secretKeyRef"]["secret"] for v in service["template"]["containers"][0]["env"] if "valueSource" in v]
        assert refs == list(spec.SECRETS.values())
        assert service["invokerIamDisabled"] is False
        assert service["template"]["serviceAccount"] == spec.RUNTIME_IDENTITY
        assert service["template"]["volumes"] == [{"name": "sql", "cloudSqlInstance": {
            "instances": ["earnings-nerd:us-west1:earningsnerd-summary-verify-db-123"]}}]


@pytest.mark.parametrize("field", list(spec.sql_instance_contract("123", "b" * 32)))
def test_rehashed_plan_cannot_expand_temporary_instance_contract(field):
    doc = document()
    value = doc["manifest"]["sql_instance"][field]
    doc["manifest"]["sql_instance"][field] = not value if isinstance(value, bool) else "unapproved-value"
    doc["sha256"] = spec.digest(doc["manifest"])
    with pytest.raises(spec.Refused, match="fixed_instance_scope"):
        approved(doc, cleanup=True)


@pytest.mark.parametrize("operation", ["apply", "cleanup"])
def test_legacy_schema_cannot_expand_prior_approval_before_cloud_auth(tmp_path, monkeypatch, operation):
    doc = spec.plan(ROOT, IMAGE, "123456789", "123", "b" * 32)
    doc["manifest"]["schema"] = 1
    for key in ("sql_instance", "source_database_version", "resource_expiry_is_enforced", "sql_permissions"):
        doc["manifest"].pop(key)
    doc["sha256"] = spec.digest(doc["manifest"])
    monkeypatch.setattr(manage, "Cloud", lambda: pytest.fail("legacy approval must fail before cloud auth"))
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    plan_file = tmp_path / "plan.json"
    plan_file.write_text(json.dumps(doc))
    assert manage.main([operation, "--plan", str(plan_file), "--output", str(tmp_path / "receipt.json"),
                        "--expected-plan-sha256", doc["sha256"], "--approval-nonce", doc["manifest"]["nonce"]]) == 1


@pytest.mark.parametrize("key,value", [("GITHUB_ACTIONS", "false"), ("GITHUB_RUN_ATTEMPT", "2"),
                                       ("GITHUB_RUN_ID", ""), ("SUMMARY_DELIVERY_APPROVED", "false")])
def test_all_apply_approval_guards_are_required(key, value):
    doc = document()
    with pytest.raises(spec.Refused):
        spec.approve(doc, doc["sha256"], doc["manifest"]["nonce"], {**ENV, key: value}, now=NOW)


def test_cleanup_survives_expiry_and_code_changes_but_requires_exact_approval():
    doc = document()
    later = NOW + timedelta(days=10)
    with pytest.raises(spec.Refused):
        spec.approve(doc, doc["sha256"], doc["manifest"]["nonce"], ENV, now=later)
    assert spec.approve(doc, doc["sha256"], doc["manifest"]["nonce"], ENV, now=later, cleanup=True)
    with pytest.raises(spec.Refused):
        spec.approve(doc, "0" * 64, doc["manifest"]["nonce"], ENV, now=later, cleanup=True)


@pytest.mark.parametrize("mutation", [
    lambda m: m["services"][0].update(name=spec.PARENT + "/services/earningsnerd-backend"),
    lambda m: m["queues"][0].update(name=spec.PARENT + "/queues/production"),
    lambda m: m.update(identities=["production@earnings-nerd.iam.gserviceaccount.com"]),
    lambda m: m.update(secrets=["DATABASE_URL"]), lambda m: m.update(database="earningsnerd"),
    lambda m: m["services"][0].update(max_instances=100),
    lambda m: m.pop("sql_permissions"),
    lambda m: m["sql_permissions"]["required"].append("cloudsql.instances.update"),
    lambda m: m["sql_permissions"]["granted"].append("secretmanager.versions.access"),
    lambda m: m["sql_permissions"]["missing"].append("cloudsql.instances.get"),
])
def test_rehashed_manifest_cannot_choose_other_cleanup_targets(mutation):
    doc = document()
    mutation(doc["manifest"])
    doc["sha256"] = spec.digest(doc["manifest"])
    with pytest.raises(spec.Refused, match="fixed_resource_scope|sql_permissions_unverified"):
        approved(doc, cleanup=True)


class FakeCloud:
    def __init__(self, manifest, *, populated=True):
        self.calls, self.cleanup_calls, self.seen, self.rows = 0, 0, [], {}
        self.cleaning = False
        self.deadline = time.monotonic() + manage.APPLY_SECONDS
        self.manifest = manifest
        self.sql_operation = None
        self.permissions = list(spec.SQL_PERMISSIONS)
        self.project = {"etag": "retain-etag", "bindings": [
            {"role": "roles/cloudsql.client", "members": ["serviceAccount:" + spec.RUNTIME_IDENTITY, "serviceAccount:unrelated"]},
            {"role": "roles/viewer", "members": ["user:unrelated@example.test"]}]}
        if not populated:
            self.project["bindings"][0]["members"].remove("serviceAccount:" + spec.RUNTIME_IDENTITY)
        if populated:
            for api, path, kind in manage.resources(manifest):
                self.rows[(api, path)] = {"name": path.removeprefix("v2/"), "state": "RUNNING",
                    "labels": {"purpose": spec.PURPOSE, "run-id": manifest["run_id"]},
                    "description": spec.PURPOSE + ":" + manifest["run_id"]}
            row = instance._request(manifest, "a" * 64)
            row.pop("rootPassword")
            row.update(state="RUNNABLE", connectionName=spec.connection_name(manifest),
                       instanceType="CLOUD_SQL_INSTANCE", backendType="SECOND_GEN")
            self.rows[("sqladmin", instance.BASE + "/instances/" + row["name"])] = row

    def begin_cleanup(self):
        self.cleaning = True

    def call(self, api, path, *, method="GET", body=None, missing_ok=False, timeout=None):
        self.seen.append((api, path, method, deepcopy(body)))
        if self.cleaning:
            self.cleanup_calls += 1
        else:
            self.calls += 1
        if path.endswith(":testIamPermissions"):
            assert api == "cloudresourcemanager" and method == "POST"
            assert body == {"permissions": EXPECTED_SQL_PERMISSIONS}
            return {"permissions": self.permissions}
        if api == "sqladmin":
            name = self.manifest["sql_instance"]["name"]
            if path == instance.BASE + "/instances/earningsnerd-db":
                return {"name": "earningsnerd-db", "project": spec.PROJECT, "region": spec.REGION,
                        "databaseVersion": "POSTGRES_15"}
            if method == "POST":
                row = deepcopy(body)
                row.pop("rootPassword")
                row.update(state="RUNNABLE", connectionName=spec.connection_name(self.manifest),
                           instanceType="CLOUD_SQL_INSTANCE", backendType="SECOND_GEN")
                self.rows[(api, path + "/" + name)] = row
            if method in {"POST", "DELETE"}:
                if method == "DELETE":
                    self.rows.pop((api, path.split("?", 1)[0]), None)
                self.sql_operation = {"name": "operation", "status": "DONE", "targetProject": spec.PROJECT,
                                      "targetId": name, "insertTime": self.manifest["created_at"],
                                      "operationType": "CREATE" if method == "POST" else "DELETE"}
                return deepcopy(self.sql_operation)
            if "/operations?" in path:
                return {"items": [self.sql_operation] if self.sql_operation else []}
        if path.endswith(":getIamPolicy"):
            return deepcopy(self.project)
        if path.endswith(":setIamPolicy"):
            self.project = deepcopy(body["policy"])
            return {}
        if path.endswith(":pause"):
            return {}
        if method == "DELETE":
            self.rows.pop((api, path), None)
            return {"done": True}
        return deepcopy(self.rows.get((api, path)))


def test_cleanup_preserves_unrelated_policy_and_deletes_identity_after_grant():
    m = approved()
    cloud = FakeCloud(m)
    assert manage.cleanup(cloud, m)["state"] == "removed"
    project_write = next(i for i, r in enumerate(cloud.seen) if r[1].endswith(":setIamPolicy"))
    identity_deletes = [i for i, r in enumerate(cloud.seen) if r[0] == "iam" and r[2] == "DELETE"]
    assert all(i > project_write for i in identity_deletes)
    assert cloud.project["etag"] == "retain-etag"
    assert cloud.project["bindings"][0]["members"] == ["serviceAccount:unrelated"]
    assert cloud.project["bindings"][1]["members"] == ["user:unrelated@example.test"]
    assert not cloud.rows and cloud.cleanup_calls > 0


def test_cleanup_refuses_unowned_resources():
    m = approved()
    cloud = FakeCloud(m)
    cloud.rows[("run", "v2/" + m["services"][0]["name"])]["labels"]["run-id"] = "unowned"
    with pytest.raises(spec.Refused, match="ownership"):
        manage.cleanup(cloud, m)
    assert not any(r[2] == "DELETE" for r in cloud.seen)


def test_failed_service_delete_still_removes_independent_resources_and_retains_database():
    m = approved()
    cloud = FakeCloud(m)
    call = cloud.call
    failed_path = "v2/" + m["services"][0]["name"]

    def fail_one(api, path, **kwargs):
        if path == failed_path and kwargs.get("method") == "DELETE":
            raise RuntimeError("untrusted-provider-body-never-printed")
        return call(api, path, **kwargs)

    cloud.call = fail_one
    result = manage.cleanup(cloud, m)
    assert result["state"] == "UNVERIFIED" and result["requires_explicit_cleanup"]
    assert ("run", failed_path) in cloud.rows
    assert all((api, path) not in cloud.rows for api, path, kind in manage.resources(m) if kind in {"queue", "secret"})
    assert all((api, path) in cloud.rows for api, path, kind in manage.resources(m) if kind == "identity")
    assert "untrusted" not in str(result)
    assert not any(r[0] == "sqladmin" and r[2] == "DELETE" for r in cloud.seen)


@pytest.mark.parametrize("failure", ["first_pause", "instance_unavailable", "worker_unavailable"])
def test_standalone_cleanup_continues_cloud_teardown_without_database_credentials(
    tmp_path, monkeypatch, capsys, failure,
):
    from ops.summary_delivery import database

    doc = document()
    manifest = doc["manifest"]
    cloud = FakeCloud(manifest)
    original_call = cloud.call
    first_pause = "v2/" + manifest["queues"][0]["name"] + ":pause"
    first_worker = "v2/" + manifest["services"][0]["name"]

    def call(api, path, *, method="GET", body=None, **kwargs):
        if ((failure == "first_pause" and path == first_pause)
                or (failure == "worker_unavailable" and path == first_worker and method == "DELETE")
                or (failure == "instance_unavailable" and api == "sqladmin")):
            cloud.seen.append((api, path, method, deepcopy(body)))
            raise RuntimeError("private-provider-failure-must-not-be-emitted")
        if api == "sqladmin" and method == "DELETE":
            assert all((api, path) not in cloud.rows for api, path, kind in manage.resources(manifest)
                       if kind in {"service", "queue", "secret"})
        return original_call(api, path, method=method, body=body, **kwargs)

    cloud.call = call
    monkeypatch.setattr(manage, "Cloud", lambda: cloud)
    monkeypatch.setattr(database, "admin", lambda *a: pytest.fail("cleanup must not open SQL/proxy/credentials"))
    monkeypatch.setattr(database.subprocess, "run", lambda *a, **k: pytest.fail("cleanup must not launch psql"))
    monkeypatch.setattr(database.subprocess, "Popen", lambda *a, **k: pytest.fail("cleanup must not launch proxy"))
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    plan_file, receipt_file = tmp_path / "plan.json", tmp_path / "receipt.json"
    plan_file.write_text(json.dumps(doc))
    assert manage.main(["cleanup", "--plan", str(plan_file), "--output", str(receipt_file),
                        "--expected-plan-sha256", doc["sha256"], "--approval-nonce", manifest["nonce"]]) == 1
    receipt = json.loads(receipt_file.read_text())
    assert "private-" not in receipt_file.read_text() + capsys.readouterr().out
    assert {path for _, path, method, _ in cloud.seen if method == "POST" and path.endswith(":pause")} == {
        "v2/" + queue["name"] + ":pause" for queue in manifest["queues"]}
    for api, path, kind in manage.resources(manifest):
        if kind in {"service", "queue", "secret"} and not (failure == "worker_unavailable" and path == first_worker):
            assert (api, path) not in cloud.rows
            assert any(row[:3] == (api, path, "DELETE") for row in cloud.seen)
    assert receipt["state"] == "UNVERIFIED" and receipt["requires_explicit_cleanup"]
    assert not any(":access" in path for _, path, _, _ in cloud.seen)
    if failure == "first_pause":
        assert "queue_pause" in receipt["failed_stages"]
        assert not cloud.rows
    else:
        assert ("sqladmin", instance.BASE + "/instances/" + manifest["sql_instance"]["name"]) in cloud.rows
        assert all((api, path) in cloud.rows for api, path, kind in manage.resources(manifest) if kind == "identity")
        assert not any(method == "DELETE" and api == "iam" for api, _, method, _ in cloud.seen)
        assert not any(path.endswith(":setIamPolicy") for _, path, _, _ in cloud.seen)
        assert ("instance_cleanup" if failure == "instance_unavailable" else "worker_absence") in receipt["failed_stages"]


@pytest.mark.parametrize("public", [False, True, "authenticated"])
def test_effective_ingress_checks_detect_inherited_public_invocation(monkeypatch, public):
    m = approved()

    class Cloud:
        deadline = time.monotonic() + manage.APPLY_SECONDS
        def call(self, api, path, **kwargs):
            prefix = "runtime:" if spec.RUNTIME_IDENTITY in path else ""
            return {"token": prefix + kwargs["body"]["audience"]}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, count):
            return b'{"status":"healthy","synthetic":true}'

    class Opener:
        def open(self, request, timeout):
            token = request.headers.get("X-serverless-authorization")
            origin = request.full_url.removesuffix("/health")
            correct = token == "Bearer " + origin
            granted = (public is True or correct or public == "authenticated" and token == "Bearer runtime:" + origin)
            if not granted:
                raise HTTPError(request.full_url, 403, "denied", None, None)
            return Reply()

    monkeypatch.setattr(manage, "build_opener", lambda *args: Opener())
    if public:
        with pytest.raises(spec.Refused, match="effective_private_ingress"):
            manage.verify_private_surface(Cloud(), m)
    else:
        assert manage.verify_private_surface(Cloud(), m)["health_requests"] == 12


def test_cleanup_budget_is_independent_of_exhausted_apply(monkeypatch):
    monkeypatch.setattr(manage.auth.AccessToken, "get", lambda self, deadline: "private-test-token")
    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, count):
            return b'{}'
    monkeypatch.setattr(manage, "build_opener", lambda *a: type("Opener", (), {"open": lambda *a, **k: Reply()})())
    cloud = manage.Cloud()
    cloud.calls = 400
    with pytest.raises(spec.Refused):
        cloud.call("run", "example")
    cloud.begin_cleanup()
    assert cloud.call("run", "example") == {}
    assert cloud.cleanup_calls == 1


def test_cleanup_renews_expired_sdk_credentials_without_replaying_resource_mutations(monkeypatch, capsys):
    from types import SimpleNamespace

    now, issued, credentials, seen = [0.0], {}, [], []
    monkeypatch.setattr(manage.time, "monotonic", lambda: now[0])
    manifest = document()["manifest"]
    backend = FakeCloud(manifest)

    def refresh(argv, **kwargs):
        assert argv == ["gcloud", "config", "config-helper", "--force-auth-refresh",
                        "--format=json(credential.access_token,credential.token_expiry)", "--quiet"]
        assert kwargs["stderr"] == subprocess.DEVNULL and 0 < kwargs["timeout"] <= 15
        token = "private-synthetic-token-" + str(len(credentials))
        credentials.append(token)
        issued[token] = now[0] + 300  # Model a short-lived credential, not a promised GHA lifetime.
        expiry = (datetime.now(timezone.utc) + timedelta(seconds=300)).isoformat()
        kwargs["stdout"].write(json.dumps({"credential": {"access_token": token, "token_expiry": expiry}}).encode())
        return SimpleNamespace(returncode=0)

    class Reply:
        def __init__(self, body):
            self.body = body
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, count):
            return json.dumps(self.body).encode()

    class Opener:
        def open(self, request, timeout):
            parsed = urlsplit(request.full_url)
            token = request.headers["Authorization"].removeprefix("Bearer ")
            seen.append((parsed.hostname, parsed.path, request.method, token))
            assert token in issued and issued[token] > now[0], "expired credential reached resource API"
            path = parsed.path.removeprefix("/") + ("?" + parsed.query if parsed.query else "")
            result = backend.call(parsed.hostname.removesuffix(".googleapis.com"), path,
                                  method=request.method, body=json.loads(request.data) if request.data else None)
            if result is None:
                raise HTTPError(request.full_url, 404, "missing", None, None)
            return Reply(result)

    monkeypatch.setattr(manage.auth.subprocess, "run", refresh)
    monkeypatch.setattr(manage, "build_opener", lambda *a: Opener())
    cloud = manage.Cloud()
    cloud.call("cloudresourcemanager", "v1/projects/earnings-nerd:getIamPolicy", method="POST", body={})
    now[0] = 49 * 60
    original = cloud.call

    def lifecycle_elapsed(api, path, **kwargs):
        if api == "run" and kwargs.get("method") == "DELETE":
            now[0] += 3 * 60  # Elapsed work between requests, within each240s Run-operation allowance.
        return original(api, path, **kwargs)

    cloud.call = lifecycle_elapsed
    result = manage.cleanup(cloud, manifest)
    assert result["state"] == "removed" and not backend.rows
    assert len(credentials) >= 4 and cloud.cleanup_deadline > now[0]
    mutations = [(host, path, method) for host, path, method, _ in seen if method == "DELETE"]
    assert len(mutations) == len(set(mutations)) == 10  #9 original resources plus isolated SQL instance.
    assert all(value not in json.dumps(result) + capsys.readouterr().out for value in credentials)


def test_auth_time_consumes_request_budget_and_401_does_not_replay_mutation(monkeypatch):
    now, requested, cleared = [100.0], [], []
    monkeypatch.setattr(manage.time, "monotonic", lambda: now[0])

    def token(self, deadline):
        assert deadline == 105.0
        now[0] += 2
        return "private-fixture"

    class Opener:
        def open(self, request, timeout):
            requested.append((request.method, timeout))
            raise HTTPError(request.full_url, 401, "private-provider-error", None, None)

    monkeypatch.setattr(manage.auth.AccessToken, "get", token)
    monkeypatch.setattr(manage.auth.AccessToken, "clear", lambda self: cleared.append(True))
    monkeypatch.setattr(manage, "build_opener", lambda *a: Opener())
    cloud = manage.Cloud()
    cloud.deadline = 105.0
    with pytest.raises(spec.Refused, match="cloud_operation_refused"):
        cloud.call("sqladmin", instance.BASE + "/instances", method="POST", body={})
    assert requested == [("POST", 3)] and cleared == [True] and cloud.calls == 1


def test_cloud_deadlines_bound_requests_and_preserve_fresh_cleanup_margin(monkeypatch):
    import yaml

    clock, waits = [100.0], []
    monkeypatch.setattr(manage.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(manage.auth.AccessToken, "get", lambda self, deadline: "private-test-token")

    class Reply:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self, count):
            return b'{}'

    class Opener:
        def open(self, request, timeout):
            waits.append(timeout)
            return Reply()

    monkeypatch.setattr(manage, "build_opener", lambda *args: Opener())
    cloud = manage.Cloud()
    clock[0] = cloud.deadline - 2
    cloud.call("sqladmin", instance.BASE + "/instances/fixed", timeout=20)
    assert waits == [2]
    clock[0] = cloud.deadline
    with pytest.raises(spec.Refused, match="cloud_operation_deadline"):
        cloud.call("run", "v2/example")
    assert waits == [2]
    cloud.begin_cleanup()
    first_cleanup_deadline = cloud.cleanup_deadline
    cloud.call("run", "v2/example")
    assert waits[-1] == 30
    clock[0] += 20
    cloud.begin_cleanup()
    assert cloud.cleanup_deadline == first_cleanup_deadline
    clock[0] = cloud.cleanup_deadline - 1
    cloud.call("sqladmin", instance.BASE + "/instances/fixed", timeout=30)
    assert waits[-1] == 1
    steps = yaml.safe_load((ROOT / ".github/workflows/ops.yml").read_text())["jobs"]["ops"]["steps"]
    apply = next(s for s in steps if s.get("run", "").startswith("python3 ops/summary_delivery/manage.py apply"))
    cleanup = next(s for s in steps if s.get("run", "").startswith("python3 ops/summary_delivery/manage.py cleanup"))
    # Fixture HTTP/sleeps and bounded proxy/SQL work are outside cloud calls.
    # Six minutes covers their local bootstrap/shutdown margin; no OS-hard claim.
    assert manage.APPLY_SECONDS + 9 * 60 + manage.CLEANUP_SECONDS + 6 * 60 <= apply["timeout-minutes"] * 60
    assert manage.CLEANUP_SECONDS + 5 * 60 <= cleanup["timeout-minutes"] * 60
    tools_step = next(s for s in steps if s.get("name") == "Install isolated summary verification SQL tools")
    assert tools_step["if"] == "steps.request.outputs.operation == 'summary-delivery-apply'"


@pytest.mark.parametrize("consumer", ["cloud", "json", "sse", "ingress"])
@pytest.mark.parametrize("drip", ["headers", "body"])
def test_whole_http_deadline_interrupts_real_header_and_body_trickles(monkeypatch, consumer, drip):
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    stop = threading.Event()
    payload = b'{"status":"healthy","synthetic":true}'
    if consumer == "sse":
        payload = b"data: " + payload + b"\n\n"
    header = b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(payload)).encode() + b"\r\nConnection: close\r\n\r\n"

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            try:
                prefix, trickle, suffix = (b"", header, payload) if drip == "headers" else (header, payload, b"")
                self.connection.sendall(prefix)
                for byte in trickle:
                    if stop.is_set():
                        return
                    self.connection.sendall(bytes([byte]))
                    stop.wait(0.03)  # Every byte arrives inside the socket inactivity timeout.
                self.connection.sendall(suffix)
            except OSError:
                pass

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        target = f"http://127.0.0.1:{server.server_port}/"

        class Opener:
            def open(self, request, timeout):
                return urlopen(target, timeout=timeout)  # Real urllib transport; no external host.

        monkeypatch.setattr(manage, "build_opener", lambda *args: Opener())
        monkeypatch.setattr(manage.auth.AccessToken, "get", lambda self, deadline: "private-fixture")
        cloud = manage.Cloud()
        if consumer != "cloud":
            monkeypatch.setattr(cloud, "call", lambda *a, **k: {"token": "private-fixture"})
        client = manage.Client(cloud, document()["manifest"], "private-fixture") if consumer in {"json", "sse"} else None
        before_handler = signal.getsignal(signal.SIGALRM)
        start = time.monotonic()
        cloud.deadline = start + 0.15
        if client:
            client.deadline = cloud.deadline
        try:
            with pytest.raises(spec.Refused):
                if consumer == "cloud":
                    cloud.call("sqladmin", instance.BASE + "/instances/fixed")
                elif consumer == "ingress":
                    manage.verify_private_surface(cloud, document()["manifest"])
                else:
                    client.request("/__summary_verify__/receipt", first_frame=consumer == "sse")
            assert time.monotonic() - start < 0.75
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
            assert signal.getsignal(signal.SIGALRM) == before_handler
        finally:
            stop.set()
            server.shutdown()
            thread.join(timeout=1)
            assert not thread.is_alive()


def test_request_timer_refuses_takeover_and_restores_success_and_error_paths(monkeypatch):
    def unrelated_handler(signum, frame):
        raise AssertionError("unrelated timer must remain disarmed")

    ambient = signal.signal(signal.SIGALRM, unrelated_handler)
    previous = unrelated_handler
    try:
        for fail in (False, True):
            try:
                with manage.request_deadline(time.monotonic() + 1):
                    assert signal.getitimer(signal.ITIMER_REAL)[0] > 0
                    if fail:
                        raise ValueError("fixed-test-error")
            except ValueError:
                assert fail
            assert signal.getitimer(signal.ITIMER_REAL) == (0.0, 0.0)
            assert signal.getsignal(signal.SIGALRM) == previous
        with monkeypatch.context() as patch:
            patch.setattr(signal, "getitimer", lambda *a: (1.0, 0.0))
            with pytest.raises(spec.Refused, match="request_deadline_unavailable"), manage.request_deadline(time.monotonic() + 1):
                pytest.fail("must not take over existing timer")
        with monkeypatch.context() as patch:
            patch.setattr(threading, "current_thread", lambda: object())
            with pytest.raises(spec.Refused, match="request_deadline_unavailable"), manage.request_deadline(time.monotonic() + 1):
                pytest.fail("must not run timer outside main thread")
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, ambient)


def test_actual_queue_requests_cannot_extend_attempt_ceiling(monkeypatch):
    m = approved()
    sent = []

    class Cloud:
        def call(self, api, path, *, method="GET", body=None, **kwargs):
            sent.append((api, path, method, deepcopy(body)))
            if method == "GET":
                return {"state": "PAUSED"}
            if path.endswith(":getIamPolicy"):
                return {"etag": "retain", "bindings": []}
            return {}

    manage.create_queues(Cloud(), m)
    creates = [body for _, path, method, body in sent if method == "POST" and path.endswith("/queues")]
    assert len(creates) == 2
    assert {c["name"] for c in creates} == {q["name"] for q in m["queues"]}
    for body in creates:
        retry = body["retryConfig"]
        assert retry["maxAttempts"] == 3
        assert 0 < int(retry["maxRetryDuration"].removesuffix("s")) < int(retry["minBackoff"].removesuffix("s"))
        assert retry["minBackoff"] == retry["maxBackoff"] == "30s"
        assert body["rateLimits"] == {"maxConcurrentDispatches": 1, "maxDispatchesPerSecond": 0.2}
    assert sum(path.endswith(":pause") for _, path, _, _ in sent) == 2


def test_persisted_runtime_budget_and_expiry_never_admit_extra_work(tmp_path, monkeypatch):
    from sqlalchemy import create_engine, insert, select, update
    from app import database

    engine = create_engine("sqlite:///" + str(tmp_path / "budget.db"))
    monkeypatch.setattr(database, "engine", engine)
    metadata, state, _ = runtime.tables()
    metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(insert(state).values(id=1, run_id="123", created_at=datetime.now(timezone.utc),
                                                value={"worker_deliveries": 0, "cloud_create_tasks": 0}))
    try:
        for _ in range(12):
            runtime.consume("123", "worker_deliveries", 12)
        with pytest.raises(runtime.Refused, match="request_budget"):
            runtime.consume("123", "worker_deliveries", 12)
        with engine.begin() as connection:
            assert connection.execute(select(state.c.value)).scalar_one()["worker_deliveries"] == 12
            connection.execute(update(state).values(created_at=datetime.now(timezone.utc) - timedelta(seconds=601)))
        with pytest.raises(runtime.Refused, match="run_expired"):
            runtime.consume("123", "cloud_create_tasks", 32)
        with engine.begin() as connection:
            assert connection.execute(select(state.c.value)).scalar_one()["cloud_create_tasks"] == 0
            connection.execute(update(state).values(created_at=datetime.now(timezone.utc)))
        with pytest.raises(runtime.Refused, match="run_expired"):
            runtime.consume("different-run", "cloud_create_tasks", 32)
    finally:
        engine.dispose()


def test_network_guard_permits_real_event_loop_uvicorn_and_task_child_startup(tmp_path):
    # Only the cloud identity/source bootstrap is replaced. The installed audit
    # hook, event loop, uvicorn listener and native task child startup are real.
    # This loopback smoke is not cloud OIDC or database delivery acceptance.
    prefix = (f"import sys; sys.path.insert(0, {str(ROOT)!r}); "
              "from ops.summary_delivery import runtime; "
              "runtime.verify_runtime_permissions=lambda:None; "
              "runtime.validate_environment=lambda *a,**k:('background' if '--child' in sys.argv else 'api','123'); ")
    env = {**os.environ, "SUMMARY_VERIFY_RUN_ID": "123", "TASKS_WORKER_ROLE": "background"}
    child = subprocess.run([sys.executable, "-c", prefix + "sys.argv=['runtime','--child']; raise SystemExit(runtime.main())"],
                           input=b'{"kind":"probe","payload":{}}', stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, env=env, cwd=ROOT / "backend", timeout=20, check=False)
    assert child.returncode == 0
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    env["PORT"] = str(port)
    with (tmp_path / "server.log").open("wb+") as log:
        process = subprocess.Popen([sys.executable, "-c", prefix + "raise SystemExit(runtime.main())"],
                                   stdout=log, stderr=log, env=env, cwd=ROOT / "backend")
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline and process.poll() is None:
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        assert response.read(1024) == b'{"status":"healthy","synthetic":true}'
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                log.seek(0)
                pytest.fail("guarded runtime failed to start: " + log.read(4096).decode(errors="replace"))
        finally:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.mark.parametrize("failure", ["headroom", "admin_startup", "create_ambiguous"])
def test_apply_failure_removes_temporary_instance_without_production_credentials(monkeypatch, failure):
    from ops.summary_delivery import database
    doc = spec.plan(ROOT, IMAGE, "123456789", "123", "b" * 32)
    cloud = FakeCloud(doc["manifest"], populated=False)
    monkeypatch.setattr(manage, "production_snapshot", lambda cloud: (IMAGE, ("DATABASE_URL", "SECRET_KEY")))

    class SQL:
        headroom_snapshot = {"maximum": 25, "usable": 22, "active": 7, "admitted": False}

        def preflight(self):
            raise spec.Refused("database_headroom_insufficient")

        def provision(self, password):
            pytest.fail("must refuse before creating SQL resources")

    @contextmanager
    def admin(*args):
        assert failure != "create_ambiguous", "uncertain creation must not reach SQL"
        assert len(args) == 4 and len(args[3]) == 64
        assert any(api == "sqladmin" and method == "POST" for api, _, method, _ in cloud.seen)
        if failure == "admin_startup":
            raise RuntimeError("private-admin-failure")
        yield SQL()

    monkeypatch.setattr(database, "admin", admin)
    if failure == "create_ambiguous":
        def lost_create(cloud, manifest, password):
            cloud.call("sqladmin", instance.BASE + "/instances", method="POST", body=instance._request(manifest, password))
            raise spec.Refused("sql_cloud_operation_unverified")
        monkeypatch.setattr(instance, "create", lost_create)
    result = manage.apply(cloud, doc, doc["sha256"], doc["manifest"]["nonce"], ENV)
    assert result["state"] == "UNVERIFIED"
    assert result["failed_phase"] == ("database_preflight" if failure == "headroom" else "isolated_instance")
    if failure == "headroom":
        assert result["database_headroom"]["active"] == 7
    assert result["cleanup"]["state"] == "removed"
    assert not cloud.rows
    assert not any(":access" in path for _, path, _, _ in cloud.seen)


def valid_runtime_environment():
    m = document()["manifest"]
    env = {row["name"]: row["value"] for row in spec.runtime_env(m, {"DATABASE_URL": "1", "SECRET_KEY": "1"}, "summary",
        (ROOT / "ops/summary_delivery/runtime.py").read_text()) if "value" in row}
    env.update(K_SERVICE=spec.PREFIX + "-summary", SECRET_KEY="x" * 64,
               DATABASE_URL=f"postgresql://{spec.DATABASE}:password@/{spec.DATABASE}?host=/cloudsql/{spec.connection_name(m)}")
    return env


@pytest.mark.parametrize("key,value", [("K_SERVICE", "earningsnerd-backend"), ("RESEND_API_KEY", "forbidden"),
    ("OPENAI_API_KEY", "real-key-forbidden"), ("TASKS_WORKER_ROLE", "background"), ("DB_MAX_OVERFLOW", "1"),
    ("DATABASE_URL", "postgresql://user:password@localhost/earningsnerd"), ("SUMMARY_VERIFY_RUNTIME_SHA256", "0" * 64)])
def test_runtime_refuses_production_credentials_or_identity(monkeypatch, key, value):
    monkeypatch.chdir(ROOT / "backend")
    env = valid_runtime_environment()
    assert runtime.validate_environment(env, child=True) == ("summary", "123")
    env[key] = value
    with pytest.raises(runtime.Refused):
        runtime.validate_environment(env, child=True)


@pytest.mark.parametrize("target", ["earningsnerd-db", "earningsnerd-summary-verify-db-456"])
def test_runtime_cannot_redirect_both_environment_and_url_to_other_instance(monkeypatch, target):
    monkeypatch.chdir(ROOT / "backend")
    env = valid_runtime_environment()
    assert runtime.validate_environment(env, child=True) == ("summary", "123")
    old = env["SUMMARY_VERIFY_INSTANCE"]
    env["SUMMARY_VERIFY_INSTANCE"] = "earnings-nerd:us-west1:" + target
    env["DATABASE_URL"] = env["DATABASE_URL"].replace(old, env["SUMMARY_VERIFY_INSTANCE"])
    with pytest.raises(runtime.Refused, match="database_boundary"):
        runtime.validate_environment(env, child=True)


@pytest.mark.parametrize("missing", ["cloudsql.instances.create", "cloudsql.instances.delete", "cloudsql.instances.connect"])
def test_missing_sql_permissions_are_reviewable_and_apply_makes_no_mutation(monkeypatch, tmp_path, missing):
    cloud = FakeCloud(document()["manifest"], populated=False)
    cloud.permissions.remove(missing)
    assert instance.permission_snapshot(cloud)["missing"] == [missing]
    monkeypatch.setattr(manage, "Cloud", lambda: cloud)
    monkeypatch.setattr(manage, "production_snapshot", lambda cloud: (IMAGE, ("DATABASE_URL", "SECRET_KEY")))
    original = cloud.call

    def call(api, path, **kwargs):
        if path == "v1/projects/earnings-nerd":
            return {"projectNumber": "123456789"}
        return original(api, path, **kwargs)

    cloud.call = call
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    output = tmp_path / "plan.json"
    assert manage.main(["plan", "--output", str(output)]) == 0
    doc = json.loads(output.read_text())
    assert doc["manifest"]["sql_permissions"] == {"required": EXPECTED_SQL_PERMISSIONS,
                                                 "granted": cloud.permissions, "missing": [missing]}
    cloud.seen.clear()
    result = manage.apply(cloud, doc, doc["sha256"], doc["manifest"]["nonce"], ENV)
    assert result["state"] == "UNVERIFIED" and result["failed_phase"] == "sql_permission_preflight"
    assert result["sql_permissions"]["missing"] == [missing]
    assert result["cleanup"]["state"] == "not_needed"
    assert cloud.seen == [("cloudresourcemanager", "v1/projects/earnings-nerd:testIamPermissions", "POST",
                           {"permissions": EXPECTED_SQL_PERMISSIONS})]
    # Grant changes require a fresh reviewed plan; a missing-permission plan
    # cannot silently turn into an apply authorization after IAM is changed.
    cloud.permissions = list(spec.SQL_PERMISSIONS)
    result = manage.apply(cloud, doc, doc["sha256"], doc["manifest"]["nonce"], ENV)
    assert result["state"] == "UNVERIFIED" and not cloud.rows


@pytest.mark.asyncio
async def test_fixed_fixture_runs_real_pipeline_and_persists_one_charge_per_summary(tmp_path, monkeypatch):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app import database
    from app.config import settings
    from app.models import SummaryJob, User
    from app.services import summary_job_store as store, summary_jobs, summary_pipeline as pipeline
    from app.services.durable_tasks import TaskEnvelope
    from app.services import email_service

    engine = create_engine("sqlite:///" + str(tmp_path / "isolated.db"), connect_args={"check_same_thread": False})
    factory = sessionmaker(bind=engine)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", factory)
    monkeypatch.setattr(store, "SessionLocal", factory)
    monkeypatch.setattr(settings, "SUMMARY_DURABLE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "DURABLE_TASKS_ENABLED", True)
    # Fixtures below are restored by pytest; production code receives the real
    # sleep values. This unit proves pipeline compatibility, not wall-clock SLOs.
    original_sleep = asyncio.sleep

    async def quick_sleep(seconds):
        await original_sleep(min(seconds, 0.01))

    monkeypatch.setattr(runtime.asyncio, "sleep", quick_sleep)
    for target, name in [(pipeline.sec_edgar_service, "get_filing_document"),
                         (pipeline.xbrl_service, "get_xbrl_data"), (pipeline.xbrl_service, "get_filing_sections"),
                         (pipeline, "get_or_cache_excerpt"), (pipeline.openai_service, "summarize_filing"),
                         (email_service, "send_verification_email"), (email_service, "send_password_reset_email")]:
        monkeypatch.setattr(target, name, getattr(target, name))
    tokens = runtime.seed("123")["tokens"]
    assert len(tokens) == 2
    with factory() as db:
        users = [db.query(User).filter_by(email=e).one().id for e in runtime.EMAILS[:2]]
    try:
        for fid, user_id in zip((45003, 45004), users, strict=True):
            view = store.ensure_job(fid, user_id)
            if fid == 45004:
                with factory() as db:
                    db.get(SummaryJob, view.job_id).attempts = 1  # model the recovered delivery for this compatibility test
                    db.commit()
            envelope = TaskEnvelope(kind="summary", payload={"job_id": view.job_id, "generation": 1})
            runtime.install_fixtures(envelope)
            await summary_jobs.run_summary_task(envelope.payload)
        result = runtime.receipt("123")
        assert [job["status"] for job in result["jobs"]] == ["complete", "complete"]
        assert result["logical_charges"] == result["summaries"] == 2
        assert result["reservations"] == 0
        assert all(job["charge_state"] == "settled" for job in result["jobs"])
        assert result["source_semantics_verified"] is False
    finally:
        engine.dispose()
