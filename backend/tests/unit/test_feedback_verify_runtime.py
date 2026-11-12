"""The private verifier cannot become a production-data or arbitrary-control back door."""
from __future__ import annotations

import ast
import hashlib
import hmac
import importlib.util
import json
import os
import re
from datetime import timedelta
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace
from uuid import uuid4

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
    ("OPENAI_API_KEY", "unexpected-provider-credential"),
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
    good_rows = authority_rows()
    good = Cursor(good_rows)
    assert runtime.check_database(SimpleNamespace(cursor=lambda: good), env()) == good_rows[2][6]
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
        with pytest.raises(runtime.Refused, match="superseded_run"):
            verifier.marker(db)
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
            "self_high_water_rss_bytes": 200000000, "worker_high_water_rss_bytes": 100000000}


@pytest.mark.parametrize("failure", ("kernel_budget", "budget", "unknown_child", "stale", "no_samples", "unverified_limit", "missing_sample", "missing_child_bound"))
def test_resource_acceptance_never_turns_missing_or_unsafe_evidence_into_zero(failure):
    evidence = memory()
    assert runtime.resource_acceptance(evidence)
    if failure == "kernel_budget":
        evidence["cgroup_kernel_peak_bytes"] = 950000000
        assert runtime.resource_acceptance(evidence) is False
        return
    evidence["cgroup_kernel_peak_bytes"] = None
    assert runtime.resource_acceptance(evidence)
    if failure == "budget":
        evidence["worker_high_water_rss_bytes"] = 500000000
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
        evidence["worker_high_water_rss_bytes"] = 0
    assert runtime.resource_acceptance(evidence) is False


def test_the_fallback_bound_passes_the_measured_workload_once_a_worker_counts_only_its_own_peak():
    """Measured offline on the real application (dry-run, 11 November): it peaks near 300 MiB, and the image worker
    near 154 MiB on the 4000x4000 boundary image. ru_maxrss counted the parent's image in every child, so a bound taken
    from it (four times the parent) could never pass when the kernel peak is not exposed."""
    evidence = memory()
    evidence.update(cgroup_kernel_peak_bytes=None, cgroup_sample_peak_bytes=384 * 2**20,
                    self_high_water_rss_bytes=315002880, worker_high_water_rss_bytes=154 * 2**20)
    assert runtime.resource_acceptance(evidence)
    evidence["worker_high_water_rss_bytes"] = evidence["self_high_water_rss_bytes"]  # what ru_maxrss reported
    assert runtime.resource_acceptance(evidence) is False


@pytest.mark.parametrize("meminfo", [False, True])
def test_receipt_requires_real_server_observations_and_uses_separate_secret_domain(verifier, database, monkeypatch, meminfo):
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

    # Exercise the real producer shape through both consumers. The targeted refusal
    # above uses independently planted evidence; this composition uses actual ORM
    # observations and Runtime.snapshot, including every resource evidence field.
    from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
    monkeypatch.setattr(verifier, "snapshot", runtime.Runtime.snapshot.__get__(verifier))
    now, attempt = utcnow(), str(uuid4())
    with database.sessions() as db:
        report = Feedback(type="general", message="Synthetic verification report", created_at=now)
        db.add(report)
        db.flush()
        submission = FeedbackSubmission(id=str(uuid4()), submission_key=str(uuid4()), fingerprint="a" * 64,
            state="submitted", attempt_token=attempt, lease_expires_at=now, feedback_id=report.id,
            created_at=now, updated_at=now)
        db.add(submission)
        db.flush()
        for position in range(3):
            identity = str(uuid4())
            db.add(FeedbackAttachment(id=identity, submission_id=submission.id, attempt_token=attempt,
                feedback_id=report.id, object_key=f"feedback/{attempt}/{identity}.png", object_generation="123",
                checksum="a" * 64, content_type="image/png", width=40, height=40, byte_count=200,
                position=position, state="deleted", created_at=now, expires_at=now, deletion_due_at=now, deleted_at=now))
        db.commit()
    verifier.resources.update(memory())
    if meminfo:  # Cloud Run's second generation: no kernel peak or limit, and a sample named as meminfo's
        verifier.resources.update(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None)
        verifier.basis = MEMINFO_BASIS
    verifier.last_sample = time.monotonic()
    verifier.record_mail(mail(verifier))
    verifier.last_cleanup = {"dry_run": False, "eligible": 3, "deleted": 3, "errors": 0, "overdue": 0, "pending_verification": 0}
    composed = verifier.complete(body)
    assert composed["payload"]["observed"]["resources"]["evidence_basis"] == (
        MEMINFO_BASIS if meminfo else "kernel cgroup high-water peak")
    monkeypatch.syspath_prepend(str(ROOT / "ops/feedback_media"))
    spec = importlib.util.spec_from_file_location("feedback_verify_composition_ops", ROOT / "ops/feedback_media/verify_manage.py")
    consumer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(consumer)
    assert consumer.counts_only_receipt(composed)
    config = {"run_id": verifier.run, **{field: verifier.env[name] for field, name in runtime.HASH_ENV.items()}}
    script = """import fs from 'node:fs';
import { receiptEnvelope } from './ops/feedback_media/live_runner.mjs';
const {receipt,config}=JSON.parse(fs.readFileSync(0,'utf8'));
receiptEnvelope(receipt,config);
"""
    node = subprocess.run(["node", "--input-type=module", "-e", script], cwd=ROOT,
                          input=json.dumps({"receipt": composed, "config": config}), text=True,
                          capture_output=True, timeout=10)
    assert node.returncode == 0, node.stderr


def test_inline_source_is_bounded_and_real_child_limits_remain_explainable():
    assert (ROOT / "ops/feedback_media/verify_runtime.py").stat().st_size <= 32768
    assert runtime.worker_limits() == {"feedback_image_service": 1, "feedback_storage_worker_service": 2}


def _process(root, pid, cmdline, state="S", children=(), high_water_kib=150000, name=b"python"):
    folder = root / "proc" / str(pid)
    (folder / "task" / str(pid)).mkdir(parents=True, exist_ok=True)
    (folder / "statm").write_text("100 10 0 0 0 0 0\n")
    (folder / "cmdline").write_bytes(cmdline)
    (folder / "stat").write_bytes(b"%d (%s) %s 1 1 1 0 -1\n" % (pid, name, state.encode()))
    # A process without an address space (exiting, or a zombie) reports no high-water mark.
    (folder / "status").write_text("Name:\tpython\nVmPeak:\t  999999 kB\n" +
                                   (f"VmHWM:\t  {high_water_kib} kB\n" if high_water_kib is not None else ""))
    (folder / "task" / str(pid) / "children").write_text("".join(f"{child} " for child in children))


@pytest.fixture
def fake_proc(tmp_path, monkeypatch):
    """sample() reads /proc and /sys through Path: serve those from a temporary tree, every other path as it is."""
    monkeypatch.setattr(runtime, "Path", lambda value: Path(f"{tmp_path}{value}")
                        if str(value).startswith(("/proc/", "/sys/")) else Path(value))
    return tmp_path


@pytest.mark.parametrize("child, unexplained, own_peak", [
    ("worker", False, True),
    ("worker leaving its address space", False, False),  # read between its argv and its high-water mark
    ("exiting", False, False),  # mid-exec or mid-exit: no argv to read, and its state is not yet Z
    ("exiting a second later", True, False),  # never transient: what it is cannot be told
    ("zombie", False, False),  # exited and awaiting its reap
    ("zombie a second later", False, False),  # still a process (counted), never an unexplained program
    ("not yet exec'd", False, False),  # spawned: until exec, a child shows its parent's argv
    ("not exec'd a second later", True, False),  # a fork, not a worker
    ("exec'd as a worker", False, True),
    ("another program", True, False),
    ("another program with a name that is not UTF-8", True, False),  # never a read error that skips the check
])
def test_the_sampler_explains_a_worker_at_every_moment_of_its_life(verifier, fake_proc, child, unexplained, own_peak):
    parent, own = os.getpid(), b"python\0-c\0verification-source\0"
    worker = b"\0".join((os.fsencode(sys.executable), b"-I", b"-B",
                         os.fsencode(Path("app/services/feedback_image_service.py").resolve()), b""))
    first, state = {"worker": (worker, "S"), "worker leaving its address space": (worker, "R"), "exiting": (b"", "R"),
                    "exiting a second later": (b"", "R"), "zombie": (b"", "Z"), "zombie a second later": (b"", "Z"),
                    "another program": (b"/bin/sh\0-c\0true\0", "S"),
                    "another program with a name that is not UTF-8": (b"/bin/sh\0-c\0true\0", "S")}.get(child, (own, "R"))
    _process(fake_proc, parent, own, children=[parent + 1], high_water_kib=320000)
    _process(fake_proc, parent + 1, first, state,
             high_water_kib=None if child.startswith(("worker leaving", "exiting", "zombie")) else 150000,
             name=b"\xff\xfe" if child.endswith("not UTF-8") else b"python")
    verifier.sample()
    if child.endswith("a second later"):
        if parent + 1 in verifier.spawning:
            verifier.spawning[parent + 1] -= 2  # first seen two seconds ago, and still not exec'd or gone
        verifier.sample()
    elif child == "exec'd as a worker":
        _process(fake_proc, parent + 1, worker)
        verifier.sample()
    assert verifier.resources["sample_count"] >= 1 and verifier.resources["last_process_count"] == 2
    assert verifier.resources["unexplained_children"] is unexplained
    # The child bound is a worker's own high-water mark: never the parent's, and never a child not yet exec'd, whose
    # address space is still the parent's.
    assert verifier.resources["worker_high_water_rss_bytes"] == (150000 * 1024 if own_peak else 0)


def test_the_worker_bound_keeps_the_highest_peak_any_worker_reported(verifier, fake_proc):
    parent, own = os.getpid(), b"python\0-c\0verification-source\0"
    worker = b"\0".join((os.fsencode(sys.executable), b"-I", b"-B",
                         os.fsencode(Path("app/services/feedback_storage_worker_service.py").resolve()), b""))
    for high_water_kib in (90000, 160000, 70000):
        _process(fake_proc, parent, own, children=[parent + 1])
        _process(fake_proc, parent + 1, worker, high_water_kib=high_water_kib)
        verifier.sample()
    assert verifier.resources["worker_high_water_rss_bytes"] == 160000 * 1024


@pytest.mark.parametrize("seconds, unexplained", [(0.9, False), (1.1, True)])
def test_a_child_that_has_not_exec_d_counts_as_a_fork_only_after_one_second(verifier, fake_proc, seconds, unexplained):
    parent, own = os.getpid(), b"python\0-c\0verification-source\0"
    _process(fake_proc, parent, own, children=[parent + 1])
    _process(fake_proc, parent + 1, own, "R")
    verifier.sample()
    verifier.spawning[parent + 1] -= seconds
    verifier.sample()
    assert verifier.resources["unexplained_children"] is unexplained


def test_an_unexplained_child_stays_reported_after_it_is_gone(verifier, fake_proc):
    parent, own = os.getpid(), b"python\0-c\0verification-source\0"
    _process(fake_proc, parent, own, children=[parent + 1])
    _process(fake_proc, parent + 1, b"/bin/sh\0-c\0true\0")
    verifier.sample()
    _process(fake_proc, parent, own)  # the child has exited and been reaped
    verifier.sample()
    assert verifier.resources["unexplained_children"] is True and verifier.resources["last_process_count"] == 1


def test_more_than_three_children_at_once_is_unexplained_even_if_each_is_a_worker(verifier, fake_proc):
    """The workers' own bounds allow three at once (one image, two storage); a fourth means another launch path."""
    parent, own = os.getpid(), b"python\0-c\0verification-source\0"
    worker = b"\0".join((os.fsencode(sys.executable), b"-I", b"-B",
                         os.fsencode(Path("app/services/feedback_storage_worker_service.py").resolve()), b""))
    _process(fake_proc, parent, own, children=[parent + child for child in range(1, 5)])
    for child in range(1, 5):
        _process(fake_proc, parent + child, worker)
    verifier.sample()
    assert verifier.resources["unexplained_children"] is True and verifier.resources["last_process_count"] == 5


def test_three_workers_at_once_are_explained(verifier, fake_proc):
    """The legitimate peak is the application plus one image and two storage workers: the cap must still accept it."""
    parent, own = os.getpid(), b"python\0-c\0verification-source\0"
    workers = [b"\0".join((os.fsencode(sys.executable), b"-I", b"-B",
                           os.fsencode(Path(f"app/services/{name}.py").resolve()), b""))
               for name in ("feedback_image_service", "feedback_storage_worker_service", "feedback_storage_worker_service")]
    _process(fake_proc, parent, own, children=[parent + child for child in range(1, 4)])
    for child, argv in enumerate(workers, start=1):
        _process(fake_proc, parent + child, argv, high_water_kib=(50000, 150000, 100000)[child - 1])
    verifier.sample()
    assert verifier.resources["unexplained_children"] is False and verifier.resources["last_process_count"] == 4
    # Every worker of the sample is read: the highest sits in the middle, so neither a walk from the first child nor
    # one from the last meets it first or last, and the bound keeps it whatever order the sampler visits them in.
    assert verifier.resources["worker_high_water_rss_bytes"] == 150000 * 1024


def test_the_application_bound_is_its_own_peak_and_never_its_childrens(verifier, fake_proc, monkeypatch):
    peaks = {runtime.resource.RUSAGE_SELF: 300000, runtime.resource.RUSAGE_CHILDREN: 999999}
    monkeypatch.setattr(runtime.resource, "getrusage", lambda who: SimpleNamespace(ru_maxrss=peaks[who]))
    _process(fake_proc, os.getpid(), b"python\0-c\0verification-source\0")
    verifier.sample()
    assert verifier.resources["self_high_water_rss_bytes"] == 300000 * 1024


@pytest.mark.parametrize("worker, accepted", [(100_000_000, True), (100_000_200, False)])
def test_the_fallback_bound_is_the_application_and_three_workers_at_their_peaks(worker, accepted):
    """0.85 GiB is 912,680,550 bytes: the application's 612,680,000 and three workers of 100,000,000 fit by 550 bytes."""
    evidence = memory()
    evidence.update(cgroup_kernel_peak_bytes=None, cgroup_sample_peak_bytes=400_000_000,
                    self_high_water_rss_bytes=612_680_000, worker_high_water_rss_bytes=worker)
    assert runtime.resource_acceptance(evidence) is accepted


def test_every_refusal_is_a_fixed_code():
    """A refused start prints the refusal's text in the Cloud Run log: every Refused(...) takes one snake_case literal."""
    tree = ast.parse((ROOT / "ops/feedback_media/verify_runtime.py").read_text())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Refused"]
    assert len(calls) > 20
    assert [ast.unparse(call) for call in calls if len(call.args) != 1 or call.keywords
            or not isinstance(call.args[0], ast.Constant) or not isinstance(call.args[0].value, str)
            or not re.fullmatch(r"[a-z_]+", call.args[0].value)] == []


def _service_environment(tmp_path):
    """The environment the verification service runs with: runtime_env's values, its secrets and Cloud Run's name."""
    spec = importlib.util.spec_from_file_location("feedback_verify_start_ops", ROOT / "ops/feedback_media/verify_manage.py")
    manage = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(ROOT / "ops/feedback_media"))
    try:
        spec.loader.exec_module(manage)
    finally:
        sys.path.remove(str(ROOT / "ops/feedback_media"))
    fixture = env()
    hashes = {name: fixture[variable] for name, variable in runtime.HASH_ENV.items() if name != "image_digest"}
    image = "registry.invalid/backend@" + fixture["FEEDBACK_VERIFY_IMAGE_DIGEST"]
    service = {row["name"]: row["value"] for row in manage.runtime_env(
        fixture["FEEDBACK_VERIFY_RUN_ID"], image, hashes, {manage.KEY_SECRET: "1", manage.DB_SECRET: "1"}, "api")
        if "value" in row}
    assert service["OPENAI_API_KEY"] == ""  # every integration key is empty where the service starts
    return {**service, **{name: fixture[name] for name in ("DATABASE_URL", "SECRET_KEY", "K_SERVICE")},
            "PATH": os.environ["PATH"], "HOME": str(tmp_path)}


def test_the_service_imports_the_application_in_the_environment_it_runs_with(tmp_path):
    """openai 3.x refuses an empty key when the application imports its AI facade, and main() must still start it."""
    script = """import sys, types, uvicorn
verification = types.ModuleType("verification")
exec(compile(open(sys.argv[1]).read(), sys.argv[1], "exec"), verification.__dict__)
verification.Runtime.authority = lambda self, expired=False: None
verification.Runtime.audit_permissions = lambda self: None
verification.sink = lambda runtime: types.SimpleNamespace(serve_forever=lambda: None, shutdown=lambda: None,
                                                          server_close=lambda: None)
uvicorn.run = lambda application, **options: print(
    "application imported:", type(application).__name__, "| model key:", __import__("os").environ["OPENAI_API_KEY"],
    "| model endpoint:", __import__("os").environ["OPENAI_BASE_URL"],
    "| integration keys with a value:", sorted(name for name in verification.INTEGRATIONS if __import__("os").environ.get(name)))
verification.main()
"""
    result = subprocess.run([sys.executable, "-B", "-c", script, str(ROOT / "ops/feedback_media/verify_runtime.py")],
                            cwd=ROOT / "backend", env=_service_environment(tmp_path), capture_output=True, text=True,
                            timeout=300)
    assert result.returncode == 0, result.stderr[-2000:]
    # Only the model key gets a fixed non-credential value, beside the mail sink's own key; the endpoint is loopback.
    assert ("application imported: Controls | model key: feedback-verification-no-model | model endpoint: "
            "http://127.0.0.1:9/v1 | integration keys with a value: ['OPENAI_API_KEY', 'RESEND_API_KEY']") in result.stdout


@pytest.mark.parametrize("case, refusal", [
    ("misrouted database", "database_configuration"),  # a closed refusal code
    ("unreachable database", "OperationalError"),  # any other failure: its class name, never its message
])
def test_a_refused_start_names_only_a_closed_code_or_class(tmp_path, case, refusal):
    environment = _service_environment(tmp_path)
    if case == "misrouted database":
        environment["DATABASE_URL"] = "postgresql://owner:PRIVATE_SENTINEL@/production"
    result = subprocess.run([sys.executable, "-I", "-B", "-c", (ROOT / "ops/feedback_media/verify_runtime.py").read_text()],
                            cwd=tmp_path, env=environment, capture_output=True, text=True, timeout=120)
    assert result.returncode == 1 and result.stdout == ""
    assert result.stderr.strip() == f"Feedback verification runtime refused ({refusal})"


# The layout of Linux's /proc/meminfo (Documentation/filesystems/proc.rst, "meminfo"): a padded label, then kB.
MEMINFO = "MemTotal:        1014296 kB\nMemFree:          301000 kB\nMemAvailable:     612000 kB\nShmem:             16384 kB\n"
MEMINFO_BASIS = "kernel peak unavailable; conservative process bound plus /proc/meminfo in use"
CGROUP_BASIS = "kernel peak unavailable; conservative process-bound evidence"


@pytest.mark.parametrize("v2, meminfo, expected, basis", [
    # Cloud Run's second generation (Ops 43138110953): no root cgroup v2 memory file reads, so the sample is the
    # instance's memory in use from /proc/meminfo (MemTotal - MemAvailable), named as such; no kernel peak, no limit.
    ({}, MEMINFO, ((1014296 - 612000) * 1024, None, None), MEMINFO_BASIS),
    ({"current": "not a number\n"}, MEMINFO, ((1014296 - 612000) * 1024, None, None), MEMINFO_BASIS),
    # Readable root cgroup v2 files are kept; meminfo is not read for them. The sample and the kernel peak sit below
    # meminfo's figure, so a meminfo read mixed into either would show through max().
    ({"current": "300000000\n", "peak": "350000000\n", "max": "1073741824\n"}, MEMINFO, (300000000, 350000000, 1073741824), CGROUP_BASIS),
    ({"current": "300000000\n", "max": "max\n"}, MEMINFO, (300000000, None, None), CGROUP_BASIS),
    # No source: nothing is sampled, so acceptance still refuses (sampled-peak), never a zero.
    ({}, None, (None, None, None), CGROUP_BASIS),
    ({}, "MemTotal:        1014296 kB\n", (None, None, None), CGROUP_BASIS),
    ({}, "MemTotal: lots kB\nMemAvailable: some kB\n", (None, None, None), CGROUP_BASIS),
    ({}, "MemTotal:        1014296 kB\nMemTotal:        1014000 kB\n", (None, None, None), CGROUP_BASIS),  # two totals
    ({}, "MemTotal: 100 kB\nMemAvailable: 200 kB\n", (None, None, None), CGROUP_BASIS),  # no negative figure, nor its basis
    ({}, "MemTotal: 1014296 kB\nMemAvailable: 1014296 kB\n", (None, None, None), CGROUP_BASIS),  # nor a zero
    # A label twice is no kernel's layout: neither copy is taken.
    ({}, "MemTotal: 2000000 kB\nMemTotal: 1014296 kB\nMemAvailable: 612000 kB\n", (None, None, None), CGROUP_BASIS),
    ({}, "MemTotal: 1014296 kB\nMemAvailable: 612000 kB\nMemAvailable: 1 kB\n", (None, None, None), CGROUP_BASIS),
    # Each figure is read by its name, wherever its line stands.
    ({}, "MemAvailable:     612000 kB\nMemTotal:        1014296 kB\n", ((1014296 - 612000) * 1024, None, None), MEMINFO_BASIS),
])
def test_the_sampler_names_meminfo_as_its_source_where_no_cgroup_memory_file_reads(verifier, fake_proc, v2, meminfo,
                                                                                  expected, basis):
    _process(fake_proc, os.getpid(), b"python\0-c\0verification-source\0")
    (fake_proc / "sys" / "fs" / "cgroup").mkdir(parents=True)
    for name, content in v2.items():
        (fake_proc / "sys" / "fs" / "cgroup" / f"memory.{name}").write_text(content)
    if meminfo is not None:
        (fake_proc / "proc" / "meminfo").write_text(meminfo)
    verifier.sample()
    assert verifier.resources["sample_count"] == 1
    assert (verifier.resources["cgroup_sample_peak_bytes"], verifier.resources["cgroup_kernel_peak_bytes"],
            verifier.resources["cgroup_memory_limit_bytes"]) == expected
    assert verifier.basis == basis


_RECORDERS: list[list[str]] = []
_AUDITED = []


def _record_opens(event, args):
    """Each file or directory the interpreter opens, while a test records them (an audit hook cannot be removed)."""
    if _RECORDERS and event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        _RECORDERS[-1].append(os.fsdecode(args[0]))


@pytest.fixture
def opened():
    """The paths actually opened, however they were built: the audit events Python raises for every open."""
    if not _AUDITED:
        sys.addaudithook(_record_opens)
        _AUDITED.append(True)
    _RECORDERS.append(paths := [])
    try:
        yield paths
    finally:
        _RECORDERS.remove(paths)


@pytest.mark.parametrize("meminfo", [MEMINFO, None])
def test_cgroup_v1_files_are_never_read(verifier, fake_proc, opened, meminfo):
    """At a cgroup v1 root, usage counts every page cache, the peak only the children's charges and the limit is
    "unlimited": none of them is this instance's figure. The sampler takes meminfo's, or none, and never opens v1's."""
    _process(fake_proc, os.getpid(), b"python\0-c\0verification-source\0")
    v1 = fake_proc / "sys" / "fs" / "cgroup" / "memory"
    v1.mkdir(parents=True)
    for name, content in {"usage_in_bytes": "2900979712", "max_usage_in_bytes": "100000",
                          "limit_in_bytes": "9223372036854771712",
                          "stat": "hierarchical_memory_limit 9223372036854771712"}.items():
        (v1 / f"memory.{name}").write_text(content + "\n")
    if meminfo is not None:
        (fake_proc / "proc" / "meminfo").write_text(meminfo)
    opened.clear()  # the sampler's opens only
    verifier.sample()
    reads = list(opened)
    assert [path for path in reads if path.endswith("/sys/fs/cgroup/memory.current")]  # the record is of real opens
    assert [path for path in reads if path.endswith("/proc/meminfo")]
    assert not [path for path in reads if "/sys/fs/cgroup/memory/" in path]
    assert (verifier.resources["cgroup_sample_peak_bytes"], verifier.resources["cgroup_kernel_peak_bytes"],
            verifier.resources["cgroup_memory_limit_bytes"]) == (
        ((1014296 - 612000) * 1024, None, None) if meminfo else (None, None, None))
    assert verifier.basis == (MEMINFO_BASIS if meminfo else CGROUP_BASIS)
    # Nor does any one string in the source name a v1 file or directory (the parser joins adjacent literals).
    source = ast.parse((ROOT / "ops/feedback_media/verify_runtime.py").read_text())
    assert not [node.value for node in ast.walk(source) if isinstance(node, ast.Constant) and isinstance(node.value, str)
                and re.search(r"_in_bytes|cgroup/memory(?!\.)|memory/memory\.", node.value)]


def test_the_meminfo_peak_and_its_basis_outlive_a_later_sample(verifier, fake_proc):
    """Once a meminfo figure may hold the peak, the record says so for the boot, whatever a later read gives."""
    _process(fake_proc, os.getpid(), b"python\0-c\0verification-source\0")
    for available_kib in (612000, 300000, 700000):
        (fake_proc / "proc" / "meminfo").write_text(f"MemTotal: 1014296 kB\nMemAvailable: {available_kib} kB\n")
        verifier.sample()
    (fake_proc / "proc" / "meminfo").unlink()
    verifier.sample()
    (fake_proc / "sys" / "fs" / "cgroup").mkdir(parents=True)
    (fake_proc / "sys" / "fs" / "cgroup" / "memory.current").write_text("400000000\n")
    verifier.sample()
    assert verifier.resources["cgroup_sample_peak_bytes"] == (1014296 - 300000) * 1024
    assert verifier.basis == MEMINFO_BASIS


@pytest.mark.parametrize("used_kib, accepted", [(400000, True), (891000, True), (891300, False)])
def test_acceptance_judges_a_meminfo_sample_as_it_judges_a_cgroup_sample(used_kib, accepted):
    """No kernel peak and no limit: the process bound and the sample must both stay under 85% of 1 GiB."""
    evidence = memory()
    evidence.update(cgroup_kernel_peak_bytes=None, cgroup_memory_limit_bytes=None, cgroup_sample_peak_bytes=used_kib * 1024)
    assert runtime.resource_acceptance(evidence) is accepted
