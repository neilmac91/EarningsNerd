"""The isolated live-verification boundary and signed enablement evidence fail closed."""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import base64
import struct
import sys
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
    assert len(calls) == 1 and calls[0][1].endswith(":testIamPermissions")


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
