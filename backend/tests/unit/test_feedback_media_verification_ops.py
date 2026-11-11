"""The isolated live-verification boundary and signed enablement evidence fail closed."""
from __future__ import annotations

import ast
import copy
import hashlib
import hmac
import http.client
import importlib.util
import inspect
import json
import base64
import re
import struct
import sys
import types
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ops/feedback_media"))
SPEC = importlib.util.spec_from_file_location("feedback_verify_ops", ROOT / "ops/feedback_media/verify_manage.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)

RUN_ID = "40210191699-1"
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64
KEY = "fixture-only-verifier-signing-key-for-unit-tests"
HASHES = {"runtime_source_sha256": hashlib.sha256((ROOT / "ops/feedback_media/verify_runtime.py").read_bytes()).hexdigest(),
          "verification_suite_sha256": "b" * 64, "frontend_tree": "c" * 40}
VERSIONS = {verify.KEY_SECRET: "1", verify.DB_SECRET: "1"}


def envelope(**changes):
    observed = {
        "database": {**dict.fromkeys(("feedback", "submitted", "attachments", "fixture_users", "available", "deleted", "pending",
                                       "published_attachments", "confirmed_generation_deletions"), 0), "normalized_metadata_valid": True},
        "notifications": {"accepted": 1, "rejected": 0, "attachment_counts": [3], "admin_link_valid": True, "no_image_payload": True},
        "resources": {**dict.fromkeys(("sample_count", "rss_peak_bytes", "cgroup_sample_peak_bytes", "cgroup_kernel_peak_bytes",
                                       "cgroup_memory_limit_bytes", "configured_memory_limit_bytes", "self_high_water_rss_bytes",
                                       "reaped_child_high_water_rss_bytes", "last_process_count", "conservative_process_bound_bytes"), 1),
                      "method": "kernel peak when exposed; otherwise conservative process bound plus sampled cgroup; representative workload only",
                      "worker_limits": {"feedback_image_service": 1, "feedback_storage_worker_service": 2},
                      "unexplained_children": False, "acceptance_passed": True, "sample_age_seconds": 0.01,
                      "evidence_basis": "kernel cgroup high-water peak"},
        "cleanup": {"dry_run": False, "eligible": 3, "deleted": 3, "errors": 0, "overdue": 0, "pending_verification": 0},
    }
    payload = {"schema": 1, "purpose": verify.PURPOSE, "run_id": RUN_ID, "image_digest": IMAGE.split("@", 1)[1],
               **HASHES, "browser_assertions": verify.ASSERTIONS.copy(), "observed": observed,
               "completed_at": datetime.now(timezone.utc).isoformat(), **changes}
    signature = hmac.new(KEY.encode(), verify.RECEIPT_DOMAIN + json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    return {"payload": payload, "signature": signature}


@pytest.mark.parametrize("defect", [None, "signature", "run", "image", "runtime", "suite", "frontend", "assertion", "numeric-true", "stale", "future"])
def test_signed_receipt_binds_current_code_image_frontend_and_complete_acceptance(defect):
    changes = {}
    if defect == "run":
        changes["run_id"] = "40210191698-1"
    elif defect == "image":
        changes["image_digest"] = "sha256:" + "d" * 64
    elif defect in {"runtime", "suite", "frontend"}:
        changes[{"runtime": "runtime_source_sha256", "suite": "verification_suite_sha256", "frontend": "frontend_tree"}[defect]] = "d" * (40 if defect == "frontend" else 64)
    elif defect in {"assertion", "numeric-true"}:
        changes["browser_assertions"] = {**verify.ASSERTIONS, "cleanup": False if defect == "assertion" else 1}
    elif defect in {"stale", "future"}:
        changes["completed_at"] = (datetime.now(timezone.utc) + timedelta(hours=-3 if defect == "stale" else 1)).isoformat()
    receipt = envelope(**changes)
    if defect == "signature":
        receipt["signature"] = "0" * 64
    if defect:
        with pytest.raises(verify.media.OperationError):
            verify.verify_receipt(receipt, KEY, RUN_ID, IMAGE, HASHES)
    else:
        verify.verify_receipt(receipt, KEY, RUN_ID, IMAGE, HASHES)


def test_enable_stops_before_any_flag_write_when_live_verification_is_unavailable(monkeypatch):
    calls = []
    service = {"etag": "version", "template": {"containers": [{"env": []}]}, "latestReadyRevision": "current",
               "trafficStatuses": [{"revision": "current", "percent": 100}]}
    class Cloud:
        def call(self, *_, method="GET", body=None):
            calls.append("write" if method != "GET" else "read")
            return service if method == "GET" else {"done": True, "response": service}
        def wait(self, operation):
            return operation["response"]
    monkeypatch.setattr(verify.media, "inspect", lambda *_: True)
    def refuse(*_):
        calls.append("receipt")
        raise verify.media.OperationError("live verification missing")
    monkeypatch.setattr(verify.media, "require_live_verification", refuse)
    with pytest.raises(verify.media.OperationError, match="live verification missing"):
        verify.media.set_enabled(Cloud(), service, True)
    assert calls == ["receipt"]


def test_a_script_run_enable_refused_for_its_receipt_exits_on_one_line(monkeypatch):
    """ops.yml runs manage.py by path, so it is __main__ while the verifier imports it as ops.feedback_media.manage:
    the receipt's refusal must still end in the one-line exit of its __main__ block, never a traceback."""
    path = ROOT / "ops/feedback_media/manage.py"
    *body, guard = ast.parse(path.read_text()).body
    assert isinstance(guard, ast.If) and ast.unparse(guard.test) == "__name__ == '__main__'"
    script = types.ModuleType("__main__")
    script.__file__ = str(path)
    monkeypatch.setitem(sys.modules, "__main__", script)
    monkeypatch.setattr(sys, "path", list(sys.path))
    monkeypatch.setattr(sys, "argv", [str(path), "feedback-media-enable-apply"])
    exec(compile(ast.Module(body, []), str(path), "exec"), script.__dict__)
    calls = []
    unstable = {"etag": "version", "template": {"containers": [{"env": []}]}, "trafficStatuses": []}

    class Cloud:
        def call(self, *_, method="GET", **__):
            calls.append(method)
            return unstable
    script.Cloud = Cloud
    script.inspect = lambda *_: True  # storage and scheduled cleanup verified; only the receipt is refused
    # A fresh package import each run: an earlier test's copy would hide (or fake) the script's own identity.
    package = {name: sys.modules.pop(name) for name in list(sys.modules) if name == "ops" or name.startswith("ops.")}
    try:
        with pytest.raises(SystemExit) as refused:
            exec(compile(ast.Module([guard], []), str(path), "exec"), script.__dict__)
    finally:
        for name in [name for name in sys.modules if name == "ops" or name.startswith("ops.")]:
            del sys.modules[name]
        sys.modules.update(package)
    assert refused.value.code == "Production must have one stable revision serving all traffic"
    assert calls == ["GET"]  # the production read only: no flag write


def test_runtime_spec_copies_no_production_secret_and_caps_every_process():
    production = {"template": {"containers": [{"env": [{"name": "DATABASE_URL", "value": "PRODUCTION_SECRET_SENTINEL"}]}]}}
    for job in (False, True):
        spec = verify.runtime_spec(production, RUN_ID, IMAGE, HASHES, VERSIONS, job=job)
        task = spec["template"]["template"] if job else spec["template"]
        env = {row["name"]: row for row in task["containers"][0]["env"]}
        assert "PRODUCTION_SECRET_SENTINEL" not in json.dumps(spec)
        assert task["serviceAccount"] == verify.IDENTITY
        assert task["containers"][0]["image"] == IMAGE
        assert task["containers"][0]["resources"]["limits"] == {"cpu": "1", "memory": "512Mi" if job else "1Gi"}
        assert env["DATABASE_URL"]["valueSource"]["secretKeyRef"]["secret"] == verify.DB_SECRET
        assert env["SECRET_KEY"]["valueSource"]["secretKeyRef"]["secret"] == verify.KEY_SECRET
        assert {name for name, row in env.items() if "valueSource" in row} == {"DATABASE_URL", "SECRET_KEY"}
        assert env["FEEDBACK_MEDIA_BUCKET"]["value"] == verify.BUCKET
        assert env["FEEDBACK_VERIFY_MODE"]["value"] == ("cleanup" if job else "api")
        assert env["DB_POOL_SIZE"]["value"] == ("1" if job else "2")
        assert env["DB_MAX_OVERFLOW"]["value"] == "0"
        assert task["timeout"] == ("600s" if job else "60s")
        assert task["volumes"] == [{"name": "sql", "cloudSqlInstance": {"instances": [verify.INSTANCE]}}]
        if job:
            assert spec["template"]["taskCount"] == spec["template"]["parallelism"] == 1
            assert task["maxRetries"] == 1
        else:
            assert task["maxInstanceRequestConcurrency"] == 4 and task["scaling"]["maxInstanceCount"] == 1
            assert spec["scaling"] == {"scalingMode": "AUTOMATIC", "minInstanceCount": 0, "maxInstanceCount": 1}
    # ProtoJSON may omit empty values, but a hidden secret reference is never equivalent to empty.
    assert verify.contains_spec({"name": "RESEND_API_KEY"}, {"name": "RESEND_API_KEY", "value": ""})
    assert not verify.contains_spec({"name": "RESEND_API_KEY", "valueSource": {"secretKeyRef": {"secret": "production-mail"}}},
                                    {"name": "RESEND_API_KEY", "value": ""})


@pytest.mark.parametrize("defect", [None, "wrong-db", "wrong-role", "network-host", "other-instance", "other-query"])
def test_sql_connection_is_fixed_to_isolated_role_database_and_proxy(defect):
    url = verify.database_url("a" * 64)
    if defect == "wrong-db":
        url = url.replace("@/" + verify.DATABASE, "@/production")
    elif defect == "wrong-role":
        url = url.replace(verify.DATABASE + ":", "postgres:", 1)
    elif defect == "network-host":
        url = url.replace("@/", "@unapproved.invalid/")
    elif defect == "other-instance":
        url = url.replace(verify.INSTANCE, "earnings-nerd:us-west1:other")
    elif defect == "other-query":
        url += "&options=-c%20role%3Dpostgres"
    if defect:
        with pytest.raises(verify.media.OperationError, match="boundary"):
            verify.connection_env(url, isolated=True)
    else:
        env = verify.connection_env(url, isolated=True)
        assert env["PGDATABASE"] == env["PGUSER"] == verify.DATABASE
        assert env["PGHOST"] == "127.0.0.1" and env["PGPORT"] == "15432"
        assert "DATABASE_URL" not in env


@pytest.mark.parametrize("defect", [None, "admin-capability", "broad-role", "foreign-database", "production-table", "production-definer"])
def test_sql_privilege_preflight_refuses_drift_and_production_access_without_writes(monkeypatch, defect):
    statements = []
    def query(self, statement, *, env=None):
        statements.append(statement)
        if "rolsuper OR" in statement:
            return "0" if defect == "admin-capability" else "1"
        if "count(*) FROM pg_roles" in statement:
            return "1"
        if "NOT rolsuper" in statement:
            return "0" if defect == "broad-role" else "1"
        if "pg_get_userbyid" in statement:
            return "foreign" if defect == "foreign-database" else "owned"
        if "FROM pg_class" in statement:
            return "1" if defect == "production-table" else "0"
        if "FROM pg_proc" in statement:
            return "1" if defect == "production-definer" else "0"
        raise AssertionError(statement)
    monkeypatch.setattr(verify.Sql, "query", query)
    sql = verify.Sql({})
    if defect:
        with pytest.raises(verify.media.OperationError):
            sql.preflight()
            sql.audit_production_access()
    else:
        sql.preflight()
        sql.audit_production_access()
    assert all(statement.lstrip().startswith("SELECT") for statement in statements)


@pytest.mark.parametrize("status", [200, 401, 403, 404, 503, "unavailable"])
def test_private_service_requires_effective_anonymous_gateway_denial(monkeypatch, status):
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *_):
            return None
    class Opener:
        def open(self, request, *, timeout):
            assert request.full_url == "https://earningsnerd-feedback-verify-123.us-west1.run.app/health"
            assert not request.headers and timeout == 20
            if status == "unavailable":
                raise URLError("PRIVATE_PROVIDER_ERROR_SENTINEL")
            if status != 200:
                raise HTTPError(request.full_url, status, "PRIVATE_PROVIDER_ERROR_SENTINEL", {}, None)
            return Response()
    monkeypatch.setattr(verify, "build_opener", lambda *_: Opener())
    if status == 403:
        verify.require_anonymous_denial("https://earningsnerd-feedback-verify-123.us-west1.run.app")
    else:
        with pytest.raises(verify.media.OperationError, match="must reject") as failure:
            verify.require_anonymous_denial("https://earningsnerd-feedback-verify-123.us-west1.run.app")
        assert "PRIVATE_PROVIDER" not in str(failure.value)


def png():
    def chunk(kind, payload):
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(b"\0\0\0\0")) + chunk(b"IEND", b"")


@pytest.mark.parametrize("defect", [None, "symlink", "unlisted", "oversized", "png-metadata", "receipt-content", "receipt-signature"])
def test_evidence_publisher_only_retains_bounded_synthetic_pngs_and_signed_counts(monkeypatch, tmp_path, defect):
    monkeypatch.setattr(verify, "ROOT", tmp_path)
    source = tmp_path / "private-output"
    source.mkdir()
    receipt = envelope()
    screenshot = source / "composer-light.png"
    screenshot.write_bytes(png())
    if defect == "symlink":
        screenshot.unlink()
        screenshot.symlink_to(tmp_path / "outside.png")
        (tmp_path / "outside.png").write_bytes(png())
    elif defect == "unlisted":
        (source / "storage-state.json").write_bytes(png())
    elif defect == "oversized":
        with screenshot.open("wb") as stream:
            stream.truncate(8 * 1024 * 1024 + 1)
    elif defect == "png-metadata":
        screenshot.write_bytes(png() + b"PRIVATE_CREDENTIAL_SENTINEL")
    elif defect == "receipt-content":
        receipt["payload"]["observed"]["notifications"]["recipient"] = "PRIVATE_RECIPIENT_SENTINEL"
        receipt = envelope(observed=receipt["payload"]["observed"])
    elif defect == "receipt-signature":
        receipt["signature"] = "0" * 64
    (source / "receipt.json").write_text(json.dumps(receipt))
    if defect:
        reason = {"symlink": "unapproved file", "unlisted": "unapproved file", "receipt-content": "unsupported data"}.get(defect)
        with pytest.raises(verify.media.OperationError, match=reason):
            verify.retain_artifacts(source, KEY, RUN_ID, IMAGE, HASHES)
        assert not (tmp_path / "verification-output").exists()
    else:
        verify.retain_artifacts(source, KEY, RUN_ID, IMAGE, HASHES)
        assert {path.name for path in (tmp_path / "verification-output").iterdir()} == {"receipt.json", "composer-light.png"}


def test_missing_cloud_permissions_stop_before_resource_creation():
    calls = []
    class Cloud:
        def call(self, api, path, **kwargs):
            calls.append((api, path, kwargs))
            return {"permissions": []}
    with pytest.raises(verify.media.OperationError, match="lacks required IAM"):
        verify.preflight_cloud(Cloud())
    assert len(calls) == 2 and all(call[1].endswith(":testIamPermissions") for call in calls)


@pytest.mark.parametrize("granted", [True, False, "string-answer", "unhashable-entries"])
def test_verification_preflight_tests_image_read_on_the_api_image_repository(granted):
    calls = []
    answers = {True: {"permissions": [verify.media.IMAGE_READ]}, False: {"permissions": []},
               # Malformed answers grant nothing: a bare string is never read as containing the name.
               "string-answer": {"permissions": verify.media.IMAGE_READ},
               "unhashable-entries": {"permissions": [{"name": verify.media.IMAGE_READ}]}}
    class Cloud:
        def call(self, api, path, **kwargs):
            calls.append((api, path, kwargs.get("method"), kwargs.get("body")))
            if api == "artifactregistry":
                return answers[granted]
            return {"permissions": sorted(verify.PROJECT_PERMISSIONS)}
    assert verify.IMAGE_PATTERN.pattern.startswith(r"us-west1-docker\.pkg\.dev/earnings-nerd/earningsnerd/")
    assert verify.media.IMAGE_REPOSITORY == "projects/earnings-nerd/locations/us-west1/repositories/earningsnerd"
    if granted is True:
        verify.preflight_cloud(Cloud())
    else:
        with pytest.raises(verify.media.OperationError) as refused:
            verify.preflight_cloud(Cloud())
        assert str(refused.value) == ("Verification provisioning lacks required IAM permissions: "
                                      "artifactregistry.repositories.downloadArtifacts on the API image repository")
    assert calls[1] == ("artifactregistry", f"v1/{verify.media.IMAGE_REPOSITORY}:testIamPermissions", "POST",
                        {"permissions": ["artifactregistry.repositories.downloadArtifacts"]})


@pytest.mark.parametrize("defect", [None, "private-policy", "identity", "bucket", "secret", "runtime-source", "pool", "image", "missing-receipt", "manual-scaling", "accelerator"])
def test_live_inspection_accepts_only_the_exact_private_runtime_and_never_repairs_drift(monkeypatch, defect):
    production = {"name": verify.media.SERVICE, "latestReadyRevision": "production-revision", "template": {"containers": [{"image": IMAGE}]},
                  "trafficStatuses": [{"revision": "production-revision", "percent": 100}]}
    service = verify.runtime_spec(production, RUN_ID, IMAGE, HASHES, VERSIONS, job=False)
    service.update({"uri": "https://earningsnerd-feedback-verify-123.us-west1.run.app", "latestReadyRevision": "verification-revision",
                    "trafficStatuses": [{"revision": "verification-revision", "percent": 100}]})
    env = {row["name"]: row for row in service["template"]["containers"][0]["env"]}
    if defect == "identity":
        service["template"]["serviceAccount"] = "production@earnings-nerd.iam.gserviceaccount.com"
    elif defect == "bucket":
        env["FEEDBACK_MEDIA_BUCKET"]["value"] = verify.media.BUCKETS["production"]
    elif defect == "secret":
        env["DATABASE_URL"]["valueSource"]["secretKeyRef"]["secret"] = "DATABASE_URL"
    elif defect == "runtime-source":
        service["template"]["containers"][0]["args"] = ["-c", "print('unapproved')"]
    elif defect == "pool":
        env["DB_MAX_OVERFLOW"]["value"] = "20"
    elif defect == "image":
        service["template"]["containers"][0]["image"] = IMAGE.replace("a" * 64, "d" * 64)
    elif defect == "manual-scaling":
        service["scaling"]["scalingMode"] = "MANUAL"
        service["scaling"]["manualInstanceCount"] = 10
    elif defect == "accelerator":
        service["template"]["containers"][0]["resources"]["limits"]["nvidia.com/gpu"] = "1"
    calls = []
    class Cloud:
        def call(self, api, path, *, method="GET", **_):
            calls.append((api, path, method))
            if api == f"{verify.REGION}-run":
                return {"status": {"imageDigest": IMAGE}}
            if api == "run" and path == "v2/" + verify.SERVICE:
                return service
            if api == "run" and ":getIamPolicy" in path:
                return {"bindings": [{"role": "roles/run.invoker", "members": ["allUsers" if defect == "private-policy" else "serviceAccount:" + verify.IDENTITY]}]}
            if api == "secretmanager":
                if path.endswith(":access"):
                    value = KEY if verify.KEY_SECRET in path else verify.database_url("a" * 64)
                    return {"name": path.removesuffix("latest:access") + "1", "payload": {"data": base64.b64encode(value.encode()).decode()}}
                return {"labels": {"purpose": verify.PURPOSE}}
            raise AssertionError((api, path, method))
    monkeypatch.setattr(verify, "fingerprints", lambda: HASHES)
    monkeypatch.setattr(verify, "require_anonymous_denial", lambda origin: None)
    monkeypatch.setattr(verify, "control", lambda *args: {"receipt": None if defect == "missing-receipt" else envelope()})
    if defect:
        with pytest.raises(verify.media.OperationError):
            verify.require_receipt(Cloud(), production)
    else:
        assert verify.require_receipt(Cloud(), production)["payload"]["run_id"] == RUN_ID
    assert calls and all(method == "GET" for _, _, method in calls)


def test_a_read_back_may_omit_the_default_automatic_scaling_mode():
    """ServiceScaling defaults to AUTOMATIC, so a read-back that leaves the mode out still matches; MANUAL never does."""
    expected = {"scaling": {"scalingMode": "AUTOMATIC", "minInstanceCount": 0, "maxInstanceCount": 1}}
    assert verify.contains_spec({"scaling": {"maxInstanceCount": 1}}, expected)
    assert not verify.contains_spec({"scaling": {"scalingMode": "MANUAL", "maxInstanceCount": 1}}, expected)


def fake_clock(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(verify, "time", types.SimpleNamespace(
        monotonic=lambda: clock[0], sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds)))
    return clock


def test_the_browser_waits_until_the_service_answers_the_verifier(monkeypatch):
    """ensure_service writes the verifier's invoker grant moments before the browser's first call, and an IAM change
    takes minutes to apply: refused reads are retried until the receipt read, which changes nothing, answers."""
    answers = [verify.media.OperationError("refused"), verify.media.OperationError("refused"), {"receipt": None}]

    def control(cloud, origin, key, run_id, path, payload=None):
        assert path == "receipt" and payload is None
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(verify, "control", control)
    clock = fake_clock(monkeypatch)
    verify.await_control(None, "https://verify.example", KEY, RUN_ID)
    assert answers == [] and clock[0] == 2 * verify.CONTROL_POLL_SECONDS


def test_the_browser_wait_gives_up_after_ten_minutes(monkeypatch):
    def control(*_args, **_kwargs):
        raise verify.media.OperationError("refused")
    monkeypatch.setattr(verify, "control", control)
    clock = fake_clock(monkeypatch)
    with pytest.raises(verify.media.OperationError, match="did not answer the verifier identity within ten minutes"):
        verify.await_control(None, "https://verify.example", KEY, RUN_ID)
    assert verify.CONTROL_WAIT_SECONDS <= clock[0] < verify.CONTROL_WAIT_SECONDS + verify.CONTROL_POLL_SECONDS


def test_the_receipt_read_outlasts_a_cold_verifier(monkeypatch):
    """The verifier scales to zero between verify-apply and enable-apply; a read that fails while it starts is retried,
    and the answer that arrives is returned as it is (one without a receipt is refused by require_receipt)."""
    answers = [verify.media.OperationError("timed out"), verify.media.OperationError("timed out"), {"receipt": None}]

    def control(cloud, origin, key, run_id, path, payload=None):
        assert path == "receipt" and payload is None
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(verify, "control", control)
    clock = fake_clock(monkeypatch)
    assert verify.read_receipt(None, "https://verify.example", KEY, RUN_ID) == {"receipt": None}
    assert answers == [] and clock[0] == 2 * verify.CONTROL_POLL_SECONDS


def test_the_receipt_read_gives_up_after_four_minutes(monkeypatch):
    def control(*_args, **_kwargs):
        raise verify.media.OperationError("Private verification control request failed; response withheld")
    monkeypatch.setattr(verify, "control", control)
    clock = fake_clock(monkeypatch)
    with pytest.raises(verify.media.OperationError, match="control request failed; response withheld"):
        verify.read_receipt(None, "https://verify.example", KEY, RUN_ID)
    # Four minutes, as DEPLOYMENT.md states; the Ops step's 15-minute timeout must also cover it.
    assert verify.RECEIPT_WAIT_SECONDS == 240
    assert verify.RECEIPT_WAIT_SECONDS <= clock[0] < verify.RECEIPT_WAIT_SECONDS + verify.CONTROL_POLL_SECONDS


@pytest.mark.parametrize("failure", ["dropped", "reset", "cut short", "HTTP 503", "unreachable", "timeout"])
def test_a_failed_control_request_is_a_closed_refusal_the_receipt_read_retries(monkeypatch, failure):
    """A connection dropped before a response, or a response cut short, raises outside urllib's URLError wrapper."""
    attempts = []

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self, _limit):
            if failure == "cut short" and len(attempts) < 3:
                raise http.client.IncompleteRead(b"PRIVATE_PROVIDER_ERROR_SENTINEL")
            return b'{"receipt": null}'

    class Opener:
        def open(self, request, *, timeout):
            attempts.append(timeout)
            if len(attempts) < 3:  # the direct call, then the receipt read's first attempt
                if failure == "dropped":
                    raise http.client.RemoteDisconnected("PRIVATE_PROVIDER_ERROR_SENTINEL")
                if failure == "reset":
                    raise ConnectionResetError("PRIVATE_PROVIDER_ERROR_SENTINEL")
                if failure == "HTTP 503":
                    raise HTTPError(request.full_url, 503, "PRIVATE_PROVIDER_ERROR_SENTINEL", {}, None)
                if failure == "unreachable":
                    raise URLError("PRIVATE_PROVIDER_ERROR_SENTINEL")
                if failure == "timeout":
                    raise TimeoutError("PRIVATE_PROVIDER_ERROR_SENTINEL")
            return Response()

    monkeypatch.setattr(verify, "build_opener", lambda *_: Opener())
    monkeypatch.setattr(verify, "token", lambda *_: "header.payload.signature")
    with pytest.raises(verify.media.OperationError) as refusal:
        verify.control(None, "https://verify.example", KEY, RUN_ID, "receipt")
    assert str(refusal.value) == "Private verification control request failed; response withheld"
    assert refusal.value.__cause__ is None  # raised from None: no provider detail is chained into a traceback
    clock = fake_clock(monkeypatch)
    assert verify.read_receipt(None, "https://verify.example", KEY, RUN_ID) == {"receipt": None}
    assert len(attempts) == 3 and clock[0] == verify.CONTROL_POLL_SECONDS


def test_the_enable_receipt_check_reads_through_the_retrying_read():
    assert "read_receipt(" in inspect.getsource(verify.require_receipt)
    assert "control(" not in inspect.getsource(verify.require_receipt).replace("read_receipt(", "")


def test_provision_waits_for_the_service_before_the_browser():
    """The wait sits between the service deploy and the browser, whose first refusal would fail the seeded run."""
    source = inspect.getsource(verify.provision)
    assert source.index("ensure_service(") < source.index("await_control(") < source.index("browser(")


def test_browser_suite_fingerprint_is_identical_in_python_and_the_actual_node_runner():
    output = verify.run(["node", "--input-type=module", "-e", "import {suiteDigest} from '" +
                         (ROOT / "ops/feedback_media/live_runner.mjs").as_uri() + "';process.stdout.write(suiteDigest());"])
    assert output == verify.fingerprints()["verification_suite_sha256"]


@pytest.mark.parametrize("state", ["new", "owned-empty", "owned-value", "foreign", "production-name"])
def test_secret_resume_reuses_an_owned_value_and_never_rotates_or_adopts_foreign_data(state):
    calls = []
    class Cloud:
        def call(self, api, path, *, method="GET", body=None, **_):
            calls.append((path, method))
            if method == "POST":
                return {"name": "projects/earnings-nerd/secrets/fixture/versions/1"}
            if path.endswith(":access"):
                return {"name": "projects/earnings-nerd/secrets/fixture/versions/1", "payload": {
                    "data": base64.b64encode(b"retained-value").decode()}} if state == "owned-value" else None
            return None if state == "new" else {"labels": {"purpose": "foreign" if state == "foreign" else verify.PURPOSE}}
    if state in {"foreign", "production-name"}:
        with pytest.raises(verify.media.OperationError):
            verify.secret(Cloud(), "DATABASE_URL" if state == "production-name" else verify.KEY_SECRET, create_value="new-value")
        assert not any(method != "GET" for _, method in calls)
    else:
        value, version = verify.secret(Cloud(), verify.KEY_SECRET, create_value="new-value")
        assert version == "1" and value == ("retained-value" if state == "owned-value" else "new-value")
        assert sum(path.endswith(":addVersion") for path, method in calls if method == "POST") == (0 if state == "owned-value" else 1)


def test_failed_cleanup_never_counts_as_a_completed_run():
    class Cloud:
        def call(self, *args, **kwargs):
            return {}
        def wait(self, operation):
            return {"taskCount": 1, "failedCount": 1, "succeededCount": 0}
    with pytest.raises(verify.media.OperationError, match="did not complete"):
        verify.execute_cleanup(Cloud())


@pytest.mark.parametrize("expired", ["0", "1", ""])
def test_a_new_apply_cannot_finalize_an_active_or_unknown_previous_lease(expired):
    calls = []
    previous = verify.runtime_spec({"template": {}}, RUN_ID, IMAGE, HASHES, VERSIONS, job=True)
    class Cloud:
        def call(self, api, path, *, method="GET", body=None, **_):
            calls.append((method, body))
            return previous if method == "GET" else {"done": True, "response": {"taskCount": 1, "succeededCount": 1}}
        def wait(self, operation):
            return operation["response"]
    class Sql:
        def query(self, statement, *, env):
            assert statement.startswith("SELECT (expires_at<=CURRENT_TIMESTAMP)") and RUN_ID in statement
            return expired
    if expired == "1":
        verify.settle_previous_run(Cloud(), Sql(), {}, {"template": {}})
        assert calls[-1] == ("POST", {"overrides": {"containerOverrides": [{"name": "verification", "env": [
            {"name": "FEEDBACK_VERIFY_MODE", "value": "cleanup_now"}]}]}})
    else:
        with pytest.raises(verify.media.OperationError, match="lease"):
            verify.settle_previous_run(Cloud(), Sql(), {}, {"template": {}})
        assert calls == [("GET", None)]


@pytest.mark.parametrize("answer, admitted", [
    ("25|3|0|6", True),    # 22 usable: (6 + 4 + 5) * 10 = 150 <= 154
    ("25|3|0|7", False),   # (7 + 4 + 5) * 10 = 160 > 154
    ("25|3|2|6", False),   # reserved_connections counts against usable: 20 usable, 150 > 140 (22 would admit)
    ("23|3|0|5", True),    # exactly at 70%: (5 + 4 + 5) * 10 = 140 <= 140
    ("8|3|0|0", False),
    ("0|3|0|0", False),
    ("25|3|0|PRINCIPAL", None),
])
def test_production_sql_admission_refuses_the_verifier_without_room(monkeypatch, capsys, answer, admitted):
    statements = []
    def query(self, statement, *, env=None):
        statements.append(statement)
        return answer
    monkeypatch.setattr(verify.Sql, "query", query)
    if admitted:
        verify.Sql({}).admit()
    else:
        with pytest.raises(verify.media.OperationError,
                           match="unreadable" if admitted is None else "insufficient for the isolated verifier; nothing was created"):
            verify.Sql({}).admit()
    assert len(statements) == 1 and statements[0].lstrip().startswith("SELECT")
    # A session another role owns shows backend_type NULL to a role without pg_read_all_stats; it still counts.
    assert "backend_type='client backend' OR (backend_type IS NULL AND datid IS NOT NULL)" in " ".join(statements[0].split())
    assert "PRINCIPAL" not in capsys.readouterr().out


def test_the_verifier_role_cap_covers_its_pools_and_one_serial_connection(monkeypatch):
    pools = {}
    for mode in ("api", "cleanup"):
        env = {row["name"]: row.get("value") for row in verify.runtime_env(RUN_ID, IMAGE, HASHES, VERSIONS, mode)}
        pools[mode] = int(env["DB_POOL_SIZE"]) + int(env["DB_MAX_OVERFLOW"])
    assert pools["api"] + pools["cleanup"] + 1 <= verify.CONNECTION_LIMIT == 4
    statements = []
    def query(self, statement, *, env=None):
        statements.append(statement)
        if "rolsuper OR" in statement:
            return "1"
        if "count(*) FROM pg_roles" in statement or "count(*) FROM pg_database" in statement or "FROM pg_class" in statement \
                or "FROM pg_proc" in statement:
            return "0"
        if "current_database()" in statement:
            return f"{verify.DATABASE}:{verify.DATABASE}"
        return ""
    monkeypatch.setattr(verify.Sql, "query", query)
    verify.Sql({}).provision("d" * 64, {})
    assert sum(f"CONNECTION LIMIT {verify.CONNECTION_LIMIT} PASSWORD" in statement for statement in statements) == 1


@pytest.mark.parametrize("state", [None, "role-absent", "role-deleted", "preview-absent", "preview-public"])
def test_live_verification_refuses_before_any_write_without_completed_media_provisioning(state):
    calls = []
    role = {"includedPermissions": verify.media.PERMISSIONS.copy(), "stage": "GA", "deleted": state == "role-deleted"}
    preview = {"name": verify.BUCKET, "location": "US-WEST1", "labels": {"purpose": "feedback-media", "environment": "preview"},
               "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True},
                                    "publicAccessPrevention": "inherited" if state == "preview-public" else "enforced"},
               "versioning": {"enabled": False}, "softDeletePolicy": {"retentionDurationSeconds": "0"}}
    class Cloud:
        def call(self, api, path, *, method="GET", missing_ok=False, step=None, **_):
            calls.append((api, method, step))
            if api == "iam":
                return None if state == "role-absent" else role
            return None if state == "preview-absent" else preview
    if state is None:
        verify.require_media_prerequisites(Cloud())
    else:
        with pytest.raises(verify.media.OperationError, match="refused before any write: media provisioning prerequisite not verified") as refused:
            verify.require_media_prerequisites(Cloud())
        assert {"role-absent": "role is absent", "role-deleted": "role is deleted", "preview-absent": "Preview bucket is absent",
                "preview-public": "preview bucket differs"}[state] in str(refused.value)
    assert all(method == "GET" and step for _api, method, step in calls)


@pytest.mark.parametrize("refusal", [None, "prerequisites", "bootstrap", "admission"])
def test_verify_apply_checks_media_prerequisites_and_sql_admission_before_its_first_write(monkeypatch, refusal):
    events = []
    monkeypatch.setenv("GITHUB_RUN_ID", RUN_ID.split("-")[0])
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "1")
    monkeypatch.setenv("FEEDBACK_VERIFY_DEPLOYER", "github-ops-fixture@earnings-nerd.iam.gserviceaccount.com")
    monkeypatch.setattr(verify, "current_image", lambda *_: IMAGE)
    monkeypatch.setattr(verify, "fingerprints", lambda: HASHES)
    monkeypatch.setattr(verify, "preflight_cloud", lambda _cloud: events.append("permissions"))
    def prerequisites(_cloud):
        events.append("media prerequisites")
        if refusal == "prerequisites":
            raise verify.media.OperationError("Live verification refused before any write")
    monkeypatch.setattr(verify, "require_media_prerequisites", prerequisites)
    monkeypatch.setattr(verify, "bootstrap_gaps", lambda _cloud, _deployer: events.append("bootstrap") or (
        ["resourcemanager.projects.setIamPolicy"] if refusal == "bootstrap" else []))
    class Sql:
        def preflight(self):
            events.append("sql preflight")
        def admit(self):
            events.append("sql admission")
            if refusal == "admission":
                raise verify.media.OperationError("Production SQL headroom is insufficient")
    class Admin:
        def __enter__(self):
            events.append("sql admin")
            return Sql()
        def __exit__(self, *_):
            return False
    monkeypatch.setattr(verify, "sql_admin", lambda _cloud: Admin())
    def first_write(*_args, **_kwargs):
        events.append("first write")
        raise verify.media.OperationError("stop after the first write")
    monkeypatch.setattr(verify, "secret", first_write)
    class Cloud:
        def call(self, api, path, *, method="GET", **_):
            assert method == "GET" and path == "v2/" + verify.media.SERVICE
            return {"template": {"containers": [{"image": IMAGE}]}}
    with pytest.raises(verify.media.OperationError) as refused:
        verify.provision(Cloud())
    expected = ["permissions", "media prerequisites", "bootstrap", "sql admin", "sql preflight", "sql admission", "first write"]
    stop = {None: len(expected), "prerequisites": 2, "bootstrap": 3, "admission": 6}[refusal]
    assert events == expected[:stop]
    if refusal == "bootstrap":
        assert str(refused.value) == ("Verification provisioning lacks required IAM permissions for this state; nothing "
                                      "was changed: resourcemanager.projects.setIamPolicy")


def test_the_verification_preflight_tests_every_permission_its_reads_before_writing_name():
    """The provision gate's rule, for the verifier's own pre-write reads: each permission they name is preflighted."""
    labels = []
    class Cloud:
        def call(self, api, path, *, method="GET", missing_ok=False, step=None, **_):
            labels.append(step)
            return {"includedPermissions": verify.media.PERMISSIONS.copy(), "stage": "GA"} if api == "iam" else {
                "name": verify.BUCKET, "location": "US-WEST1", "labels": {"purpose": "feedback-media", "environment": "preview"},
                "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}, "publicAccessPrevention": "enforced"},
                "versioning": {"enabled": False}, "softDeletePolicy": {"retentionDurationSeconds": "0"}}
    verify.require_media_prerequisites(Cloud())
    named = {name for label in labels for name in label.split(" [", 1)[1].rstrip("]").split(", ")}
    assert named == {"iam.roles.get", "storage.buckets.get"}
    # Every Cloud Run operation poll (media.Cloud.wait's label) and the serving revision's read (current_image, which
    # is unlabelled) also run before or between writes.
    polled = verify.media.OPERATION_READ.split(" [", 1)[1].rstrip("]").split(", ")
    assert named | set(polled) | {"run.revisions.get"} <= verify.PROJECT_PERMISSIONS


DEPLOYER = "github-ops-fixture@earnings-nerd.iam.gserviceaccount.com"


class BootstrapCloud:
    """The verifier's identity, grants and secrets as the founder's one-time owner commands leave them (or absent)."""

    def __init__(self, bootstrapped=True):
        runner, member = "serviceAccount:" + DEPLOYER, "serviceAccount:" + verify.IDENTITY
        self.calls, self.granted, self.denied, self.latest_version = [], None, set(), None
        self.denied_paths = set()  # exact paths answered 403
        self.project_granted = None  # the project's testIamPermissions answer; None answers as the resources do
        self.secret_policies, self.latest_versions = {}, {}  # per-secret answers in place of the shared ones
        self.run, self.run_policies, self.schedule = {}, {}, None  # the Cloud Run job and service, and the schedule
        self.identity = {"description": verify.PURPOSE} if bootstrapped else None
        # Google returns every IAM policy with an etag; its write-back is conditional on it.
        self.sa_policy = {"etag": "BwYsa", "bindings": [{"role": role, "members": [runner]} for role in verify.SA_ROLES]
                          if bootstrapped else []}
        self.project = {"etag": "BwYproject", "bindings": [{"role": "roles/cloudsql.client", "members": [member]}]
                        if bootstrapped else []}
        self.secrets = {name: {"labels": {"purpose": verify.PURPOSE}} for name in (verify.DB_SECRET, verify.KEY_SECRET)} if bootstrapped else {}
        self.secret_policy = {"etag": "BwYsecret", "bindings": [{"role": verify.ACCESSOR, "members": [runner, member]},
                                                               {"role": verify.VERSION_ADDER, "members": [runner]}]}
        self.bucket_policy = {"etag": "CAE=", "bindings": [{"role": verify.media.ROLE, "members": ["serviceAccount:runtime@example.invalid"]
                                                           + ([member] if bootstrapped else [])}]}

    def call(self, api, path, *, method="GET", body=None, missing_ok=False, step=None):
        self.calls.append((api, path, method, body))
        if path in self.denied_paths or any(part in path for part in self.denied):
            raise verify.media.ProviderError(f"{step or api + ' operation'} failed (HTTP 403)")
        if path.endswith(":testIamPermissions"):
            granted = self.project_granted if api == "cloudresourcemanager" and self.project_granted is not None else self.granted
            return {"permissions": [name for name in body["permissions"] if granted is None or name in granted]}
        assert method == "GET" or path.endswith(":getIamPolicy") or ":getIamPolicy?" in path, (api, path, method)
        answer = self.answer(api, path)
        if answer is None and not missing_ok:
            # Google answers an absent resource with 404, which Cloud.call returns as None only when the caller allows it.
            raise verify.media.ProviderError(f"{step or api + ' operation'} failed (HTTP 404; NOT_FOUND)")
        return answer

    def answer(self, api, path):
        if api == "iam":
            return self.sa_policy if ":getIamPolicy" in path else self.identity
        if api == "cloudresourcemanager":
            return self.project
        if api == "secretmanager":
            name = path.split("/secrets/", 1)[1].split("/", 1)[0].split(":", 1)[0]
            if ":getIamPolicy" in path:  # one policy per secret, each its own copy of the shared default
                return self.secret_policies.setdefault(name, copy.deepcopy(self.secret_policy))
            if path.endswith("/versions/latest"):
                # None: the founder adds no value, and the run adds the first version itself
                return self.latest_versions.get(name, self.latest_version)
            return self.secrets.get(name)
        if api == "storage":
            return self.bucket_policy
        if api == "run":
            if ":getIamPolicy" in path:
                return self.run_policies.get(path.split(":getIamPolicy", 1)[0])
            return self.run.get(path)
        if api == "cloudscheduler":
            return self.schedule
        raise AssertionError((api, path))


def test_a_founder_bootstrap_removes_every_owner_equivalent_and_identity_write_from_verify_apply():
    cloud = BootstrapCloud()
    assert verify.bootstrap_gaps(cloud, DEPLOYER) == []
    project = [set(body["permissions"]) for api, path, _method, body in cloud.calls
               if api == "cloudresourcemanager" and path.endswith(":testIamPermissions")]
    assert project == [{"run.jobs.create", "run.jobs.setIamPolicy", "run.services.create", "run.services.setIamPolicy",
                        "cloudscheduler.jobs.create"}]
    resource = {(api, path.rsplit("/", 1)[-1]) for api, path, _method, _body in cloud.calls
                if api != "cloudresourcemanager" and path.endswith(":testIamPermissions")}
    assert resource == {("iam", verify.IDENTITY + ":testIamPermissions"), ("secretmanager", verify.DB_SECRET + ":testIamPermissions"),
                        ("secretmanager", verify.KEY_SECRET + ":testIamPermissions")}
    assert not (verify.PROJECT_PERMISSIONS & {"resourcemanager.projects.setIamPolicy", "iam.serviceAccounts.setIamPolicy",
                                              "iam.serviceAccounts.create", "secretmanager.secrets.setIamPolicy"})
    assert verify.CONDITIONAL_PERMISSIONS.isdisjoint(verify.PROJECT_PERMISSIONS)


def test_without_a_bootstrap_verify_apply_still_names_every_grant_it_would_make():
    cloud = BootstrapCloud(bootstrapped=False)
    cloud.granted = set()
    assert verify.bootstrap_gaps(cloud, DEPLOYER) == sorted(verify.CONDITIONAL_PERMISSIONS - {
        "run.jobs.update", "run.services.update", "cloudscheduler.jobs.update"})


@pytest.mark.parametrize("defect, refusal", [
    ("identity-foreign", "not the active feature-owned identity"),
    ("identity-extra-member", "identity grants differ from the approved bootstrap"),
    ("identity-token-creator", "identity grants differ from the approved bootstrap"),
    ("identity-members-string", "Resource policy is malformed"),
    ("project-conditional", "unexpected direct project privileges"),
    ("project-editor", "unexpected direct project privileges"),
    ("project-bindings-object", "Resource policy is malformed"),
    ("secret-foreign", "secret is not feature-owned"),
    ("secret-labels-string", "secret is not feature-owned"),
    ("secret-admin", "secret grants differ from the approved bootstrap"),
    ("secret-public", "public principal"),
    ("bucket-admin", "Runtime bucket grants differ"),
    ("identity-policy-denied", "iam operation failed (HTTP 403)"),
    ("secret-denied", "secretmanager operation failed (HTTP 403)"),
    ("secret-policy-no-etag", "Resource policy has no etag"),
    ("project-policy-no-etag", "Resource policy has no etag"),
    ("secret-version-disabled", f"Verification secret {verify.DB_SECRET} has a latest version that is not enabled"),
])
def test_a_bootstrap_in_another_shape_or_unreadable_is_refused_before_any_write(defect, refusal):
    """A denied read is never planned as absent, and a malformed or differing one never as approved."""
    cloud = BootstrapCloud()
    member = "serviceAccount:" + verify.IDENTITY
    if defect == "identity-foreign":
        cloud.identity = {"description": "someone else's"}
    elif defect == "identity-extra-member":
        cloud.sa_policy["bindings"][0]["members"].append("user:someone@example.invalid")
    elif defect == "identity-token-creator":
        cloud.sa_policy["bindings"].append({"role": "roles/iam.serviceAccountTokenCreator", "members": ["serviceAccount:" + DEPLOYER]})
    elif defect == "identity-members-string":
        # A string would match the deployer by substring and plan no grant.
        cloud.sa_policy["bindings"] = [{"role": role, "members": "serviceAccount:" + DEPLOYER} for role in verify.SA_ROLES]
    elif defect == "project-conditional":
        cloud.project["bindings"][0]["condition"] = {"title": "fixture", "expression": "true"}
    elif defect == "project-editor":
        cloud.project["bindings"].append({"role": "roles/editor", "members": [member]})
    elif defect == "project-bindings-object":
        cloud.project["bindings"] = {"role": "roles/cloudsql.client", "members": [member]}
    elif defect == "secret-foreign":
        cloud.secrets[verify.KEY_SECRET] = {"labels": {}}
    elif defect == "secret-labels-string":
        cloud.secrets[verify.KEY_SECRET] = {"labels": "purpose=" + verify.PURPOSE}
    elif defect == "secret-admin":
        cloud.secret_policy["bindings"].append({"role": "roles/secretmanager.admin", "members": ["serviceAccount:" + DEPLOYER]})
    elif defect == "secret-public":
        cloud.secret_policy["bindings"][0]["members"].append("allUsers")
    elif defect == "identity-policy-denied":
        cloud.denied = {":getIamPolicy?options.requestedPolicyVersion=3"}
    elif defect == "secret-denied":
        cloud.denied = {"/secrets/" + verify.DB_SECRET}
    elif defect == "secret-policy-no-etag":
        del cloud.secret_policy["etag"]
    elif defect == "project-policy-no-etag":
        del cloud.project["etag"]
    elif defect == "secret-version-disabled":
        # The run reads the latest value and never rotates one: a disabled latest version would stop it mid-apply.
        cloud.latest_version = {"name": "projects/p/secrets/s/versions/3", "state": "DISABLED"}
    else:
        cloud.bucket_policy["bindings"].append({"role": "roles/storage.objectAdmin", "members": [member]})
    with pytest.raises(verify.media.OperationError, match=re.escape(refusal)):
        verify.bootstrap_gaps(cloud, DEPLOYER)
    assert all(method == "GET" or "IamPolicy" in path or path.endswith(":testIamPermissions") for _a, path, method, _b in cloud.calls)
    # Planning stopped at the read: no write permission was tested.
    assert not [call for call in cloud.calls if call[0] == "cloudresourcemanager" and call[1].endswith(":testIamPermissions")]


def test_a_bootstrapped_identity_the_deployer_cannot_yet_act_as_is_named_not_assumed():
    cloud = BootstrapCloud()
    # The founder's resource-scoped grants have not propagated yet: the run names them rather than failing mid-apply.
    cloud.granted = verify.PROJECT_PERMISSIONS | verify.CONDITIONAL_PERMISSIONS - {"secretmanager.versions.add"}
    assert verify.bootstrap_gaps(cloud, DEPLOYER) == [
        "actAs and getOpenIdToken on the verification identity",
        f"secretmanager.versions.add on {verify.DB_SECRET}", f"secretmanager.versions.add on {verify.KEY_SECRET}"]


@pytest.mark.parametrize("case", ["bootstrapped", "not-bootstrapped", "no-image-read", "no-deployer", "denied"])
def test_verify_inspect_reports_what_verify_apply_would_lack_without_writing(monkeypatch, capsys, case):
    cloud = BootstrapCloud(bootstrapped=case != "not-bootstrapped")
    if case == "not-bootstrapped":
        cloud.granted = verify.PROJECT_PERMISSIONS | {verify.media.IMAGE_READ}
    if case == "no-image-read":
        # Exactly the preflight verify-apply runs first, so the line never reads complete while the apply would refuse.
        cloud.granted = verify.PROJECT_PERMISSIONS | verify.CONDITIONAL_PERMISSIONS
    if case == "denied":
        cloud.denied = {"/secrets/" + verify.KEY_SECRET}
    if case != "no-deployer":
        monkeypatch.setenv("FEEDBACK_VERIFY_DEPLOYER", DEPLOYER)
    else:
        monkeypatch.delenv("FEEDBACK_VERIFY_DEPLOYER", raising=False)
    verify.report_capability(cloud)
    line = capsys.readouterr().out.strip()
    assert line == {
        "bootstrapped": "Capability for feedback-media-verify-apply: all required permissions present",
        "not-bootstrapped": "Capability for feedback-media-verify-apply: missing " + ", ".join(sorted(
            verify.CONDITIONAL_PERMISSIONS - {"run.jobs.update", "run.services.update", "cloudscheduler.jobs.update"})),
        "no-image-read": ("Capability for feedback-media-verify-apply: missing artifactregistry.repositories.downloadArtifacts"
                          " on the API image repository"),
        "no-deployer": "Capability for feedback-media-verify-apply: UNVERIFIED (the configured project deployer is unavailable)",
        "denied": "Capability for feedback-media-verify-apply: UNVERIFIED (secretmanager operation failed (HTTP 403))",
    }[case]
    assert all(method == "GET" or "IamPolicy" in path or path.endswith(":testIamPermissions") for _a, path, method, _b in cloud.calls)

class IdentityCloud(BootstrapCloud):
    """BootstrapCloud with the object role and preview bucket readable, recording writes, for ensure_identity."""

    def __init__(self):
        super().__init__()
        self.writes = []
        self.role = {"includedPermissions": verify.media.PERMISSIONS.copy(), "stage": "GA"}
        self.preview_bucket = {
            "name": verify.BUCKET, "location": "US-WEST1", "labels": {"purpose": "feedback-media", "environment": "preview"},
            "iamConfiguration": {"uniformBucketLevelAccess": {"enabled": True}, "publicAccessPrevention": "enforced"},
            "versioning": {"enabled": False}, "softDeletePolicy": {"retentionDurationSeconds": "0"}}

    def call(self, api, path, *, method="GET", body=None, missing_ok=False, step=None):
        if method != "GET" and not path.endswith(":getIamPolicy") and ":getIamPolicy?" not in path:
            # As Cloud Run v2 does: "job.name must be empty on CreateJobRequest" (provision run 42888895423).
            assert not (method == "POST" and ("?jobId=" in path or "?serviceId=" in path) and "name" in body), (
                "a Cloud Run v2 create leaves the resource's name to its jobId or serviceId")
            self.calls.append((api, path, method, body))
            self.writes.append((api, path, body))
            return {}
        if api == "iam" and path == "v1/" + verify.media.ROLE:
            self.calls.append((api, path, method, body))
            return self.role
        if api == "storage" and path == "storage/v1/b/" + verify.BUCKET:
            self.calls.append((api, path, method, body))
            return self.preview_bucket
        return super().call(api, path, method=method, body=body, missing_ok=missing_ok, step=step)

    def wait(self, operation, step=None):
        return {}


@pytest.mark.parametrize("case", ["second-binding", "missing-role"])
def test_ensure_identity_writes_the_identity_policy_exactly_when_bootstrap_planning_does(case):
    """The identity-policy write happens exactly when bootstrap_gaps planned its setIamPolicy, so it is never untested."""
    cloud = IdentityCloud()
    runner = "serviceAccount:" + DEPLOYER
    if case == "second-binding":
        # The deployer holds each role; the second through a later binding of the same role.
        cloud.sa_policy["bindings"] = [{"role": verify.SA_ROLES[0], "members": [runner]},
                                       {"role": verify.SA_ROLES[1], "members": []},
                                       {"role": verify.SA_ROLES[1], "members": [runner]}]
    else:
        cloud.sa_policy["bindings"] = [{"role": verify.SA_ROLES[0], "members": [runner]}]
    planned = "iam.serviceAccounts.setIamPolicy" in verify.bootstrap_gaps(cloud_copy(cloud), DEPLOYER)
    verify.ensure_identity(cloud, DEPLOYER)
    identity_writes = [body for api, path, body in cloud.writes if api == "iam" and path.endswith(":setIamPolicy")]
    assert planned is (case == "missing-role")
    assert len(identity_writes) == (1 if case == "missing-role" else 0)
    assert cloud.writes == [] if case == "second-binding" else all(api == "iam" for api, _path, _body in cloud.writes)
    if identity_writes:
        assert identity_writes[0]["policy"]["etag"] == "BwYsa"  # conditional on the read
        assert verify.media.bound(identity_writes[0]["policy"], verify.SA_ROLES[1], runner)


def cloud_copy(cloud):
    """A planning view of the same state that grants nothing, so every write the state needs is named."""
    planning = BootstrapCloud()
    planning.sa_policy = copy.deepcopy(cloud.sa_policy)
    planning.granted = set()
    return planning


def rerun_cloud():
    """A bootstrapped project on a later run: its job, service and schedule exist, and both secrets hold a value."""
    cloud = BootstrapCloud()
    member = "serviceAccount:" + verify.IDENTITY
    for path in ("v2/" + verify.JOB, "v2/" + verify.SERVICE):
        cloud.run[path] = {"labels": {"purpose": verify.PURPOSE}, "etag": "run-version"}
        cloud.run_policies[path] = {"etag": "BwYrun", "bindings": [{"role": "roles/run.invoker", "members": [member]}]}
    cloud.schedule = {"description": verify.PURPOSE}
    cloud.latest_version = {"name": "projects/p/secrets/s/versions/1", "state": "ENABLED"}
    return cloud


RERUN = ["cloudscheduler.jobs.update", "run.jobs.update", "run.services.update"]


@pytest.mark.parametrize("state, expected", [
    ("first-run", ["cloudscheduler.jobs.create", "run.jobs.create", "run.jobs.setIamPolicy", "run.services.create",
                   "run.services.setIamPolicy", f"secretmanager.versions.add on {verify.DB_SECRET}",
                   f"secretmanager.versions.add on {verify.KEY_SECRET}"]),
    ("rerun", RERUN),
    ("rerun-job-invoker-missing", sorted(RERUN + ["run.jobs.setIamPolicy"])),
    ("rerun-service-invoker-missing", sorted(RERUN + ["run.services.setIamPolicy"])),
    ("rerun-schedule-absent", ["cloudscheduler.jobs.create", "run.jobs.update", "run.services.update"]),
    ("rerun-identity-without-grants", sorted(RERUN + ["iam.serviceAccounts.setIamPolicy"])),
    ("rerun-project-grant-missing", sorted(RERUN + ["resourcemanager.projects.setIamPolicy"])),
    ("rerun-key-accessor-deployer-only", sorted(RERUN + ["secretmanager.secrets.setIamPolicy"])),
    ("rerun-key-accessor-identity-only", sorted(RERUN + ["secretmanager.secrets.setIamPolicy"])),
    ("rerun-bucket-grant-missing", sorted(RERUN + ["storage.buckets.setIamPolicy"])),
    ("rerun-job-foreign", "Existing verification cleanup job is not feature-owned"),
    ("rerun-service-public", "Resource policy includes a public principal"),
    ("rerun-schedule-foreign", "Existing verification cleanup schedule is not feature-owned"),
    ("rerun-identity-disabled", "Existing verification identity is not the active feature-owned identity"),
    ("rerun-secret-grant-conditional", "Existing verification secret grants differ from the approved bootstrap"),
    ("rerun-version-destroyed", f"Verification secret {verify.DB_SECRET} has a latest version that is not enabled"),
    ("rerun-version-no-state", f"Verification secret {verify.DB_SECRET} has a latest version that is not enabled"),
    ("rerun-version-state-list", f"Verification secret {verify.DB_SECRET} has a latest version that is not enabled"),
    ("rerun-bucket-policy-no-etag", "Resource policy has no etag"),
    ("rerun-job-policy-no-etag", "Resource policy has no etag"),
    ("rerun-service-policy-no-etag", "Resource policy has no etag"),
])
def test_verify_apply_plans_exactly_the_writes_each_state_needs(state, expected):
    """The verifier's planning table, read against secret(), ensure_identity, ensure_job and the service deploy: a
    state's every write is named and no other, and a re-run tests only the updates. The resource-held prerequisites are
    granted on the identity, and versions.add is not, since only a secret with no value needs it."""
    cloud = BootstrapCloud() if state == "first-run" else rerun_cloud()
    cloud.project_granted = set()  # every project write the state needs is named
    cloud.granted = {verify.media.ACT_AS, "iam.serviceAccounts.getOpenIdToken"}
    member, runner = "serviceAccount:" + verify.IDENTITY, "serviceAccount:" + DEPLOYER
    job, service = "v2/" + verify.JOB, "v2/" + verify.SERVICE
    if state == "rerun-job-invoker-missing":
        cloud.run_policies[job]["bindings"] = []
    elif state == "rerun-service-invoker-missing":
        cloud.run_policies[service]["bindings"] = []
    elif state == "rerun-schedule-absent":
        cloud.schedule = None
    elif state == "rerun-identity-without-grants":
        cloud.sa_policy["bindings"] = []
    elif state == "rerun-project-grant-missing":
        cloud.project["bindings"] = []
    elif state == "rerun-key-accessor-deployer-only":
        cloud.secret_policies[verify.KEY_SECRET] = {"etag": "BwYkey", "bindings": [{"role": verify.ACCESSOR, "members": [runner]}]}
    elif state == "rerun-key-accessor-identity-only":
        cloud.secret_policies[verify.KEY_SECRET] = {"etag": "BwYkey", "bindings": [{"role": verify.ACCESSOR, "members": [member]}]}
    elif state == "rerun-bucket-grant-missing":
        cloud.bucket_policy["bindings"][0]["members"].remove(member)
    elif state == "rerun-job-foreign":
        cloud.run[job]["labels"]["purpose"] = "sql-backups"
    elif state == "rerun-service-public":
        cloud.run_policies[service]["bindings"].append({"role": "roles/run.invoker", "members": ["allUsers"]})
    elif state == "rerun-schedule-foreign":
        cloud.schedule = {"description": "Another team's hourly job"}
    elif state == "rerun-identity-disabled":
        cloud.identity = {"description": verify.PURPOSE, "disabled": True}
    elif state == "rerun-secret-grant-conditional":
        cloud.secret_policy["bindings"][0]["condition"] = {"title": "fixture", "expression": "true"}
    elif state.startswith("rerun-version-"):
        # The run reads the latest value and never rotates one: only an ENABLED latest version is usable.
        cloud.latest_version = {"rerun-version-destroyed": {"name": "projects/p/secrets/s/versions/1", "state": "DESTROYED"},
                                "rerun-version-no-state": {"name": "projects/p/secrets/s/versions/1"},
                                "rerun-version-state-list": {"state": ["ENABLED"]}}[state]
    elif state == "rerun-bucket-policy-no-etag":
        del cloud.bucket_policy["etag"]
    elif state in ("rerun-job-policy-no-etag", "rerun-service-policy-no-etag"):
        del cloud.run_policies[job if "job" in state else service]["etag"]
    if isinstance(expected, str):
        with pytest.raises(verify.media.OperationError, match="^" + re.escape(expected)):
            verify.bootstrap_gaps(cloud, DEPLOYER)
    else:
        assert verify.bootstrap_gaps(cloud, DEPLOYER) == expected
    assert all(method == "GET" or "IamPolicy" in path or path.endswith(":testIamPermissions") for _a, path, method, _b in cloud.calls)


VERIFIER_READS = {
    "identity": "v1/" + verify.SA_PATH,
    "identity-policy": "v1/" + verify.SA_PATH + ":getIamPolicy?options.requestedPolicyVersion=3",
    "project-policy": f"v1/projects/{verify.PROJECT}:getIamPolicy",
    **{f"{label}-{kind}": path for label, name in (("db", verify.DB_SECRET), ("key", verify.KEY_SECRET))
       for kind, path in (("secret", f"v1/projects/{verify.PROJECT}/secrets/{name}"),
                          ("secret-policy", verify.media.policy_path(f"v1/projects/{verify.PROJECT}/secrets/{name}")),
                          ("latest-version", f"v1/projects/{verify.PROJECT}/secrets/{name}/versions/latest"))},
    "bucket-policy": verify.media.policy_path("storage/v1/b/" + verify.BUCKET, storage=True),
    "job": "v2/" + verify.JOB, "job-policy": verify.media.policy_path("v2/" + verify.JOB),
    "service": "v2/" + verify.SERVICE, "service-policy": verify.media.policy_path("v2/" + verify.SERVICE),
    "schedule": "v1/" + verify.SCHEDULE,
}


def unbootstrapped_cloud():
    """Nothing made yet, and no write permission held: the planner's first-run paths."""
    cloud = BootstrapCloud(bootstrapped=False)
    cloud.granted = set()
    return cloud


# The states the planner reads differently in: a later run, the founder's bootstrap alone, and nothing made yet.
PLANNING_STATES = (rerun_cloud, BootstrapCloud, unbootstrapped_cloud)


def planning_reads(cloud):
    """The paths bootstrap_gaps reads on this state, its capability tests left out."""
    verify.bootstrap_gaps(cloud, DEPLOYER)
    return {path for _api, path, _m, _b in cloud.calls if not path.endswith(":testIamPermissions")}


def test_the_denial_table_holds_every_read_bootstrap_gaps_makes():
    """The table is the planner's reads in each state it reads differently in: a read added to bootstrap_gaps on any of
    those paths fails here until it is denied below."""
    assert set().union(*(planning_reads(make()) for make in PLANNING_STATES)) == set(VERIFIER_READS.values())


@pytest.mark.parametrize("read", sorted(VERIFIER_READS))
def test_a_denied_verifier_planning_read_refuses_before_any_write_is_tested(read):
    """Each read bootstrap_gaps makes stops on a denial, in a state that reaches it: none is planned as absent, and the
    project's write test, bootstrap_gaps' last step, never runs."""
    cloud = next(make for make in PLANNING_STATES if VERIFIER_READS[read] in planning_reads(make()))()
    cloud.denied_paths = {VERIFIER_READS[read]}
    with pytest.raises(verify.media.ProviderError, match=r"^[a-z]+ operation failed \(HTTP 403\)$"):
        verify.bootstrap_gaps(cloud, DEPLOYER)
    assert not [path for api, path, _m, _b in cloud.calls if api == "cloudresourcemanager" and path.endswith(":testIamPermissions")]


def rerun_identity_cloud():
    """IdentityCloud in a re-run's state: the job, service and schedule exist, owned, with their invoker grants."""
    cloud, member = IdentityCloud(), "serviceAccount:" + verify.IDENTITY
    for path in ("v2/" + verify.JOB, "v2/" + verify.SERVICE):
        cloud.run[path] = {"labels": {"purpose": verify.PURPOSE}, "etag": "run-version"}
        cloud.run_policies[path] = {"etag": "BwYrun", "bindings": [{"role": "roles/run.invoker", "members": [member]}]}
    cloud.schedule = {"description": verify.PURPOSE}
    return cloud


@pytest.mark.parametrize("change, refusal", [
    ("job-foreign", "Existing verification cleanup job is not feature-owned"),
    ("schedule-foreign", "Existing verification cleanup schedule is not feature-owned"),
    ("service-foreign", "Existing verification service is not feature-owned"),
    ("identity-foreign", "Existing verification identity is not the active feature-owned identity"),
    ("identity-foreign-granted", "Existing verification identity is not the active feature-owned identity"),
    ("project-editor", "Verification identity has unexpected direct project privileges"),
    ("project-editor-granted", "Verification identity has unexpected direct project privileges"),
    ("project-no-etag", "Resource policy has no etag"),
    ("identity-policy-foreign", "Existing verification identity grants differ from the approved bootstrap"),
    ("identity-policy-foreign-granted", "Existing verification identity grants differ from the approved bootstrap"),
    ("role-disabled", "Feedback object role stage is DISABLED"),
    ("role-disabled-granted", "Feedback object role stage is DISABLED"),
    ("bucket-drift", "preview bucket differs from approved private retention settings"),
    ("bucket-drift-granted", "preview bucket differs from approved private retention settings"),
    ("bucket-other-role-granted", "Runtime bucket grants differ from the approved unconditional object role"),
    ("bucket-other-role-after-bind", "Runtime bucket grants differ from the approved unconditional object role"),
    ("job-etag-moved", None),
    ("service-etag-moved", None),
    ("bucket-grant-to-make", None),
])
def test_each_verifier_write_step_rechecks_what_it_writes_after_the_plan(change, refusal):
    """The verifier's write steps re-read what they write: a state that changed after bootstrap_gaps planned is refused
    before that write, and a PATCH carries the etag read at the write, not the plan's. Each identity and bucket check
    runs both where the write it guards is still to be made, so a check moved after that write fails, and where every
    grant already exists (-granted), so a check made only on the way to a write fails too."""
    cloud, member = rerun_identity_cloud(), "serviceAccount:" + verify.IDENTITY
    job, service = "v2/" + verify.JOB, "v2/" + verify.SERVICE
    granted, kind = change.endswith("-granted"), change.removesuffix("-granted")
    if kind == "job-foreign":
        cloud.run[job]["labels"]["purpose"] = "sql-backups"
    elif kind == "schedule-foreign":
        cloud.schedule = {"description": "Another team's hourly job"}
    elif kind == "service-foreign":
        cloud.run[service]["labels"]["purpose"] = "another-service"
    elif kind == "identity-foreign":
        cloud.identity = {"description": "someone else's"}
        if not granted:  # the first later write, the project grant, still to make
            cloud.project["bindings"] = []
    elif kind == "project-editor":
        cloud.project["bindings"].append({"role": "roles/editor", "members": [member]})
        if not granted:  # the identity-policy grants still to make
            cloud.sa_policy["bindings"] = []
    elif kind == "project-no-etag":  # a grant to add, on a policy whose write-back could not be conditional
        cloud.project["bindings"] = []
        del cloud.project["etag"]
    elif kind == "identity-policy-foreign":  # a member beyond the bootstrap on one role
        cloud.sa_policy["bindings"][0]["members"].append("user:someone@example.invalid")
        if not granted:  # and the other role still to grant
            del cloud.sa_policy["bindings"][1]
    elif kind in ("role-disabled", "bucket-drift"):
        if not granted:  # the verifier's bucket grant still to make
            cloud.bucket_policy["bindings"][0]["members"].remove(member)
        if kind == "role-disabled":
            cloud.role["stage"] = "DISABLED"
        else:
            cloud.preview_bucket["versioning"]["enabled"] = True
    elif kind == "bucket-other-role":  # granted, and holding a second role before the step runs
        cloud.bucket_policy["bindings"].append({"role": "roles/storage.objectViewer", "members": [member]})
    elif kind in ("bucket-other-role-after-bind", "bucket-grant-to-make"):  # the verifier's bucket grant still to make
        cloud.bucket_policy["bindings"][0]["members"].remove(member)
        if kind == "bucket-other-role-after-bind":  # a second role lands with the grant: only a read-back after it sees it
            original = cloud.call

            def call(api, path, **kwargs):
                answer = original(api, path, **kwargs)
                if api == "storage" and kwargs.get("method") == "PUT":
                    cloud.bucket_policy["bindings"].append({"role": "roles/storage.objectViewer", "members": [member]})
                return answer
            cloud.call = call
    elif kind == "job-etag-moved":
        cloud.run[job]["etag"] = "run-version-2"
    else:
        cloud.run[service]["etag"] = "run-version-2"
    step = (verify.ensure_identity if kind.startswith(("identity", "project", "role", "bucket")) else
            verify.ensure_service if kind.startswith("service") else verify.ensure_job)
    args = (cloud, DEPLOYER) if step is verify.ensure_identity else (cloud, {"labels": {"purpose": verify.PURPOSE}})
    if refusal is None:
        step(*args)
        if kind == "bucket-grant-to-make":  # the step completes with its one grant, under the etag it read
            assert [api for api, _path, _body in cloud.writes] == ["storage"]
            assert cloud.writes[0][2]["etag"] == "CAE=" and verify.media.bound(cloud.writes[0][2], verify.media.ROLE, member)
            return
        patches = [body for api, path, body in cloud.writes if api == "run" and path.split("?", 1)[0] in (job, service)]
        assert len(patches) == 1 and patches[0]["etag"] == "run-version-2"  # read at the write, not at the plan
        return
    with pytest.raises(verify.media.OperationError, match="^" + re.escape(refusal)):
        step(*args)
    if granted:  # every grant already made: nothing is written before the refusal
        assert cloud.writes == []
        return
    if kind == "bucket-other-role-after-bind":  # refused on the read-back, after exactly its one write
        assert [api for api, _path, _body in cloud.writes] == ["storage"]
        return
    # The guarded write never happened: the job or service update, the schedule, any write (where the check comes
    # before every write), the project grant, or the bucket grant.
    guarded = {"job-foreign": lambda api, path: path.split("?", 1)[0] == job,
               "schedule-foreign": lambda api, path: api == "cloudscheduler",
               "service-foreign": lambda api, path: path.split("?", 1)[0] == service,
               "identity-foreign": lambda api, path: True,
               "project-editor": lambda api, path: True,
               "project-no-etag": lambda api, path: api == "cloudresourcemanager",
               "identity-policy-foreign": lambda api, path: True,
               "role-disabled": lambda api, path: api == "storage",
               "bucket-drift": lambda api, path: api == "storage"}[kind]
    assert not [path for api, path, _body in cloud.writes if guarded(api, path)]


@pytest.mark.parametrize("invoker", ["granted", "missing"])
def test_ensure_service_grants_its_invoker_exactly_when_it_is_missing(invoker):
    """The service step grants the verifier identity its invoker role only when the policy lacks it, conditional on the
    policy's etag: the write bootstrap_gaps plans as run.services.setIamPolicy."""
    cloud, service = rerun_identity_cloud(), "v2/" + verify.SERVICE
    if invoker == "missing":
        cloud.run_policies[service]["bindings"] = []
    verify.ensure_service(cloud, {"labels": {"purpose": verify.PURPOSE}})
    grants = [body["policy"] for api, path, body in cloud.writes if api == "run" and path == service + ":setIamPolicy"]
    assert len(grants) == (invoker == "missing")
    if grants:
        assert verify.media.bound(grants[0], "roles/run.invoker", "serviceAccount:" + verify.IDENTITY)
        assert grants[0]["etag"] == "BwYrun"


@pytest.mark.parametrize("resource", ["job", "service"])
def test_a_create_leaves_the_resource_name_to_cloud_run(resource):
    """Cloud Run v2 refuses a create whose body names the resource ("job.name must be empty on CreateJobRequest",
    provision run 42888895423); the create's jobId or serviceId names it. The verifier's specs carry the name for
    their updates, so each create sends the rest of the spec unchanged and only the name dropped."""
    cloud = rerun_identity_cloud()
    path = "v2/" + (verify.JOB if resource == "job" else verify.SERVICE)
    del cloud.run[path]  # absent, so the step creates it
    spec = {"name": path.removeprefix("v2/"), "labels": {"purpose": verify.PURPOSE}, "template": {"marker": resource}}
    (verify.ensure_job if resource == "job" else verify.ensure_service)(cloud, spec)
    creates = [body for api, write, body in cloud.writes if api == "run" and ("?jobId=" in write or "?serviceId=" in write)]
    assert creates == [{"labels": {"purpose": verify.PURPOSE}, "template": {"marker": resource}}]
