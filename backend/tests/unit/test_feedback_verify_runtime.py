"""The private verifier cannot become a production-data or arbitrary-control back door."""
from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
from datetime import timedelta
from pathlib import Path
import time
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.sql.elements import TextClause

from app.database import Base
from app.models import User
from app.utils.datetimes import utcnow

ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("feedback_verify_runtime", ROOT / "ops/feedback_media/verify_runtime.py")
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


def env():
    return {
        "DATABASE_URL": "postgresql://earningsnerd_feedback_verify:fixture-only@/earningsnerd_feedback_verify?host=/cloudsql/earnings-nerd:us-west1:earningsnerd-db",
        "SECRET_KEY": "isolated-fixture-key-" * 3, "FEEDBACK_VERIFY_RUN_ID": "123456-1",
        "K_SERVICE": "earningsnerd-feedback-verify",
        "ENVIRONMENT": "production", "FEEDBACK_MEDIA_BUCKET": runtime.BUCKET,
        "COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax", "CORS_ORIGINS_STR": runtime.ORIGIN,
        "FRONTEND_URL": runtime.ORIGIN, "SKIP_REDIS_INIT": "true", "DURABLE_TASKS_ENABLED": "false",
        "FEEDBACK_MEDIA_ENABLED": "true", "FEEDBACK_VERIFY_IMAGE_DIGEST": "sha256:" + "a" * 64,
        "FEEDBACK_VERIFY_RUNTIME_SHA256": "b" * 64, "FEEDBACK_VERIFY_SUITE_SHA256": "c" * 64,
        "FEEDBACK_VERIFY_FRONTEND_TREE": "d" * 40,
    }


@pytest.mark.parametrize("key,value", [
    ("DATABASE_URL", "postgresql://owner:unused@/production"),
    ("FEEDBACK_MEDIA_BUCKET", "earnings-nerd-feedback-media-prod"),
    ("COOKIE_DOMAIN", ".earningsnerd.io"), ("COOKIE_SECURE", "false"),
    ("CORS_ORIGINS_STR", "https://production.example"), ("FEEDBACK_VERIFY_RUN_ID", "123456-2"),
    ("FEEDBACK_VERIFY_IMAGE_DIGEST", "registry.invalid:latest"), ("SECRET_KEY", "short"),
    ("RESEND_API_KEY", "unexpected-provider-credential"), ("POSTHOG_API_KEY", "unexpected-provider-credential"),
    ("K_SERVICE", "earningsnerd-backend"),
])
def test_preview_environment_refuses_misrouting_before_application_import(key, value):
    config = env()
    assert runtime.environment(config) == "123456-1"
    config[key] = value
    with pytest.raises(runtime.Refused) as error:
        runtime.environment(config)
    assert value not in str(error.value)


class Cursor:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.calls = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def execute(self, sql, parameters=None):
        self.calls.append((sql, parameters))

    def fetchone(self):
        return next(self.rows)


def authority_rows():
    config = env()
    return [(runtime.DATABASE, runtime.DATABASE, False, False, False, False, False), (False,),
            (runtime.PURPOSE, *(config[name] for name in runtime.HASH_ENV.values()), True, time.time() + 7200)]


@pytest.mark.parametrize("failure", ("database", "role", "superuser", "membership", "purpose", "digest", "expired"))
def test_actual_database_and_marker_authority_are_checked(failure):
    rows = authority_rows()
    if failure in {"database", "role", "superuser"}:
        row = list(rows[0])
        index = {"database": 0, "role": 1, "superuser": 2}[failure]
        row[index] = True if failure == "superuser" else "production"
        rows[0] = tuple(row)
    elif failure == "membership":
        rows[1] = (True,)
    else:
        row = list(rows[2])
        index = {"purpose": 0, "digest": 1, "expired": 5}[failure]
        row[index] = False if failure == "expired" else "different"
        rows[2] = tuple(row)
    cursor = Cursor(rows)
    with pytest.raises(runtime.Refused):
        runtime.check_database(SimpleNamespace(cursor=lambda: cursor), env())
    assert all(sql.startswith("SELECT") for sql, _ in cursor.calls)
    good = Cursor(authority_rows())
    assert runtime.check_database(SimpleNamespace(cursor=lambda: good), env()) > time.time()
    assert good.calls[-1][1] == ("123456-1",)


@pytest.fixture
def verifier():
    result = runtime.Runtime(env())
    result.expires = time.time() + 7200
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("token", "run", "path", "method"))
async def test_control_admission_precedes_body_or_database(verifier, failure):
    received = []
    async def body():
        received.append(True)
        yield b"private-control-content"
    async def application(*args):
        pytest.fail("Control reached the application")
    headers = {"X-Feedback-Verify-Run": verifier.run,
               "X-Feedback-Verify-Control": runtime.digest(verifier.key, "control", verifier.run)}
    path, method = "/__feedback_verify/fixtures", "POST"
    if failure == "token":
        headers["X-Feedback-Verify-Control"] = "wrong"
    elif failure == "run":
        headers["X-Feedback-Verify-Run"] = "999-1"
    elif failure == "path":
        path = "/__feedback_verify/arbitrary/fixtures"
    else:
        method = "DELETE"
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.Controls(application, verifier)), base_url="http://test") as client:
        response = await client.request(method, path, headers=headers, content=body())
    assert response.status_code == 403 and not received
    assert response.headers["cache-control"] == "private, no-store"


@pytest.mark.asyncio
async def test_normal_api_reaches_unchanged_application_but_expired_run_stops(verifier):
    calls = []
    async def application(scope, receive, send):
        calls.append(scope["path"])
        await send({"type": "http.response.start", "status": 201, "headers": []})
        await send({"type": "http.response.body", "body": b"real-application-response"})
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.Controls(application, verifier)), base_url="http://test") as client:
        assert (await client.post("/api/feedback/")).content == b"real-application-response"
        verifier.expires = time.time() - 1
        assert (await client.post("/api/feedback/")).status_code == 503
    assert calls == ["/api/feedback/"]


@pytest.mark.asyncio
async def test_control_body_is_bounded_and_success_still_checks_database_authority(verifier, monkeypatch):
    checks = []
    monkeypatch.setattr(verifier, "authority", lambda **kwargs: checks.append(kwargs))
    monkeypatch.setattr(verifier, "snapshot", lambda: {"run_id": verifier.run, "receipt": None})
    headers = {"X-Feedback-Verify-Run": verifier.run,
               "X-Feedback-Verify-Control": runtime.digest(verifier.key, "control", verifier.run)}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=runtime.Controls(None, verifier)), base_url="http://test") as client:
        # Valid JSON after whitespace distinguishes the byte budget from JSON parsing.
        large = await client.request("GET", "/__feedback_verify/receipt", headers=headers, content=b" " * 4097 + b"{}")
        assert large.status_code == 403 and not checks
        result = await client.get("/__feedback_verify/receipt", headers=headers)
    assert result.json() == {"run_id": verifier.run, "receipt": None}
    assert checks == [{"expired": True}]


def test_permission_audit_is_hard_bounded_and_production_access_blocks_fixtures(verifier, monkeypatch):
    from app.services import feedback_storage_worker_service
    calls = []
    monkeypatch.setattr(feedback_storage_worker_service.BoundedFeedbackStorage, "verify_permissions", lambda _: calls.append("preview"))
    def denied(command, **kwargs):
        calls.append(command)
        assert kwargs["timeout"] == 15 and kwargs["env"] == {}
        assert verifier.key not in repr(command)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(runtime.subprocess, "run", denied)
    with pytest.raises(runtime.Refused, match="production_authority"):
        verifier.audit_permissions()
    assert calls[0] == "preview" and verifier.permission_audited is False


@pytest.fixture
def database(verifier, tmp_path, monkeypatch):
    import app.database
    engine = create_engine("sqlite:///" + str(tmp_path / "isolated.sqlite"))
    Base.metadata.create_all(engine)
    marker = {"purpose": runtime.PURPOSE, "created_at": utcnow(), "expires_at": utcnow() + timedelta(hours=2),
              "fixtures": {}, "receipt": None, "completed_at": None}
    # PostgreSQL marker transport is separately gated above. Real ORM account/manifest reads
    # and writes run here; only the JSONB bookkeeping update is adapted for SQLite.
    class MarkerSession(Session):
        def execute(self, statement, params=None, **kwargs):
            if isinstance(statement, TextClause) and str(statement).startswith("UPDATE " + runtime.MARKER):
                if "fixtures" in params:
                    marker["fixtures"] = json.loads(params["fixtures"])
                elif "receipt" in params:
                    marker["receipt"] = json.loads(params["receipt"])
                return None
            return super().execute(statement, params, **kwargs)
    sessions = sessionmaker(bind=engine, class_=MarkerSession)
    monkeypatch.setattr(app.database, "SessionLocal", sessions)
    monkeypatch.setattr(verifier, "marker", lambda db, **kwargs: marker)
    monkeypatch.setattr(verifier, "authority", lambda **kwargs: None)
    monkeypatch.setattr(verifier, "audit_permissions", lambda: setattr(verifier, "permission_audited", True))
    yield SimpleNamespace(sessions=sessions, marker=marker)
    engine.dispose()


def test_fixture_seed_is_idempotent_and_cannot_adopt_foreign_accounts(verifier, database):
    first = verifier.fixtures()
    second = verifier.fixtures()
    assert first == second and verifier.permission_audited
    assert all(account["id"] >= 1000000 for account in first["accounts"].values())
    with database.sessions() as db:
        assert db.query(User).count() == 3
        assert db.get(User, first["accounts"]["admin"]["id"]).is_admin
        db.add(User(id=9, email="retained@example.com"))
        db.commit()
    with pytest.raises(runtime.Refused, match="foreign_account"):
        verifier.fixtures()
    with pytest.raises(runtime.Refused, match="foreign_account"):
        verifier.cleanup()
    with database.sessions() as db:
        assert db.get(User, 9).email == "retained@example.com"
        assert db.query(User).count() == 4


@pytest.mark.parametrize("scheduled", (False, True))
def test_cleanup_uses_real_account_lifecycle_and_same_preview_pair(verifier, database, monkeypatch, scheduled):
    from app.services import feedback_media_cleanup_service
    accounts = verifier.fixtures()["accounts"]
    def superseded_marker(db, *, latest=True):
        if latest:
            raise runtime.Refused("superseded_run")
        return database.marker
    monkeypatch.setattr(verifier, "marker", superseded_marker)
    if scheduled:
        database.marker["expires_at"] = utcnow() - timedelta(seconds=1)
    seen = []
    def cleaner(factory, storage, **kwargs):
        with factory() as db:
            assert db.query(User).count() == 0
        seen.append((storage, kwargs))
        return {"errors": 0, "deleted": 0}
    monkeypatch.setattr(feedback_media_cleanup_service, "run_feedback_media_cleanup", cleaner)
    result = verifier.cleanup(scheduled=scheduled)
    assert result["database"]["fixture_users"] == 0 and len(seen) == 1
    with database.sessions() as db:
        assert all(db.get(User, account["id"]) is None for account in accounts.values())
    assert seen[0][1] == {"batch_size": 100, "deadline_seconds": 50}


@pytest.mark.parametrize("newer_created", ("2026-10-25T12:00:00Z", "2026-10-25T12:00:01Z"))
def test_new_or_tied_marker_revokes_old_receipt_fixtures_and_completion(verifier, tmp_path, monkeypatch, newer_created):
    import app.database
    engine = create_engine("sqlite:///" + str(tmp_path / "markers.sqlite"))
    # Execute the actual latest-marker query against stored rows. Only PostgreSQL's
    # transaction-local timeout and FOR UPDATE transport are adapted for SQLite.
    class MarkerSession(Session):
        def scalar(self, statement, params=None, **kwargs):
            if not isinstance(statement, TextClause) and "set_config" in str(statement):
                return None
            return super().scalar(statement, params, **kwargs)
        def execute(self, statement, params=None, **kwargs):
            if isinstance(statement, TextClause) and str(statement).endswith(" FOR UPDATE"):
                statement = text(str(statement).removesuffix(" FOR UPDATE"))
            return super().execute(statement, params, **kwargs)
    sessions = sessionmaker(bind=engine, class_=MarkerSession)
    monkeypatch.setattr(app.database, "SessionLocal", sessions)
    monkeypatch.setattr(verifier, "authority", lambda **kwargs: None)
    verifier.permission_audited = True
    with sessions() as db:
        db.execute(text(f"CREATE TABLE {runtime.MARKER}(run_id TEXT, purpose TEXT, created_at TEXT, receipt TEXT)"))
        db.execute(text(f"INSERT INTO {runtime.MARKER} VALUES (:run,:purpose,:created,:receipt)"),
                   {"run": verifier.run, "purpose": runtime.PURPOSE, "created": "2026-10-25T12:00:00Z", "receipt": "previously-successful"})
        db.commit()
        assert verifier.marker(db)["receipt"] == "previously-successful"
        db.execute(text(f"INSERT INTO {runtime.MARKER} VALUES ('999999-1',:purpose,:created,NULL)"),
                   {"purpose": runtime.PURPOSE, "created": newer_created})
        db.commit()
        assert verifier.marker(db, latest=False)["receipt"] == "previously-successful"
    for action in (verifier.snapshot, verifier.fixtures,
                   lambda: verifier.complete({"assertions": dict.fromkeys(runtime.ASSERTIONS, True)})):
        with pytest.raises(runtime.Refused, match="superseded_run"):
            action()
    engine.dispose()


def test_scheduled_cleanup_preserves_an_active_browser_run(verifier, database, monkeypatch):
    from app.services import feedback_media_cleanup_service
    accounts = verifier.fixtures()["accounts"]
    monkeypatch.setattr(feedback_media_cleanup_service, "run_feedback_media_cleanup",
                        lambda *args, **kwargs: pytest.fail("Scheduled cleanup reached storage during an active run"))
    assert verifier.cleanup(scheduled=True) == {"skipped_active_run": True}
    with database.sessions() as db:
        assert all(db.get(User, account["id"]) is not None for account in accounts.values())
    assert verifier.last_cleanup is None


def mail(verifier):
    return {"from": "Feedback verification <feedback-verify@example.com>",
            "to": ["feedback-verify-notify@example.com"], "subject": "Synthetic feedback",
            "reply_to": verifier.credentials("owner")["email"],
            "html": '<strong>Screenshots:</strong> 3 <a href="https://localhost:8443/admin/feedback">Inbox</a>'}


def test_sink_records_only_bounded_evidence_and_refuses_external_recipients(verifier):
    payload = mail(verifier)
    verifier.record_mail(payload)
    assert verifier.notifications == {"accepted": 1, "rejected": 0, "attachment_counts": [3],
                                       "admin_link_valid": True, "no_image_payload": True}
    payload["to"] = ["real-person@example.org"]
    with pytest.raises(runtime.Refused, match="mail_envelope"):
        verifier.record_mail(payload)
    assert verifier.notifications["rejected"] == 1
    assert "real-person" not in json.dumps(verifier.notifications)
    payload = mail(verifier)
    payload["html"] += '<img src="data:image/png;base64,private">'
    verifier.record_mail(payload)
    assert verifier.notifications["no_image_payload"] is False


def memory():
    return {"sample_count": 10, "sample_age_seconds": .1, "unexplained_children": False,
            "last_process_count": 1, "cgroup_kernel_peak_bytes": 500000000, "cgroup_sample_peak_bytes": 400000000,
            "cgroup_memory_limit_bytes": 1073741824, "worker_limits": {"feedback_image_service": 1, "feedback_storage_worker_service": 2},
            "self_high_water_rss_bytes": 200000000, "reaped_child_high_water_rss_bytes": 100000000}


@pytest.mark.parametrize("failure", ("budget", "unknown_child", "stale", "no_samples", "unverified_limit", "missing_sample", "missing_child_bound"))
def test_resource_acceptance_never_turns_missing_or_unsafe_evidence_into_zero(failure):
    evidence = memory()
    assert runtime.resource_acceptance(evidence)
    evidence["cgroup_kernel_peak_bytes"] = None
    assert runtime.resource_acceptance(evidence)
    if failure == "budget":
        evidence["reaped_child_high_water_rss_bytes"] = 500000000
    elif failure == "unknown_child":
        evidence["unexplained_children"] = True
    elif failure == "stale":
        evidence["sample_age_seconds"] = 10
    elif failure == "no_samples":
        evidence["sample_count"] = 0
    elif failure == "unverified_limit":
        evidence["worker_limits"] = {}
    elif failure == "missing_sample":
        evidence["cgroup_sample_peak_bytes"] = None
    else:
        evidence["reaped_child_high_water_rss_bytes"] = 0
    assert runtime.resource_acceptance(evidence) is False


def test_receipt_requires_real_server_observations_and_uses_separate_secret_domain(verifier, database, monkeypatch):
    observations = {"database": {"feedback": 1, "submitted": 1, "attachments": 3, "published_attachments": 3,
                    "normalized_metadata_valid": True, "pending": 0, "fixture_users": 0, "deleted": 3,
                    "confirmed_generation_deletions": 3},
                    "notifications": {"accepted": 1, "rejected": 0, "attachment_counts": [3], "admin_link_valid": True, "no_image_payload": True},
                    "resources": memory(), "cleanup": {"errors": 0, "deleted": 3}}
    monkeypatch.setattr(verifier, "snapshot", lambda: observations)
    verifier.permission_audited = True
    verifier.last_cleanup = observations["cleanup"]
    body = {"assertions": dict.fromkeys(runtime.ASSERTIONS, True)}
    observations["database"]["pending"] = 1
    with pytest.raises(runtime.Refused, match="incomplete_evidence"):
        verifier.complete(body)
    observations["database"]["pending"] = 0
    receipt = verifier.complete(body)
    expected = hmac.new(verifier.key.encode(), b"feedback-media-verification-receipt-v1\0" + runtime.canonical(receipt["payload"]), hashlib.sha256).hexdigest()
    assert receipt["signature"] == expected and database.marker["receipt"] == receipt
    assert verifier.key not in json.dumps(receipt)
    control_key = runtime.digest(verifier.key, "control", verifier.run)
    assert hmac.new(control_key.encode(), runtime.canonical(receipt["payload"]), hashlib.sha256).hexdigest() != expected
    assert receipt["payload"]["frontend_tree"] == env()["FEEDBACK_VERIFY_FRONTEND_TREE"]
    with pytest.raises(runtime.Refused, match="browser_assertions"):
        verifier.complete({"assertions": {"upload": True}})


def test_inline_source_is_bounded_and_real_child_limits_remain_explainable():
    assert (ROOT / "ops/feedback_media/verify_runtime.py").stat().st_size <= 32768
    assert runtime.worker_limits() == {"feedback_image_service": 1, "feedback_storage_worker_service": 2}
