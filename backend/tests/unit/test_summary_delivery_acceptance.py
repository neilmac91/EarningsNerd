"""Offline safety/ownership checks; these never claim actual Google delivery evidence."""
from __future__ import annotations

import asyncio
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
from urllib.error import HTTPError

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.summary_delivery import manage, runtime, spec  # noqa: E402

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64
ENV = {"GITHUB_ACTIONS": "true", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_RUN_ID": "456",
       "SUMMARY_DELIVERY_APPROVED": "true", "SUMMARY_DELIVERY_DEPLOYER": "github-actions@earnings-nerd.iam.gserviceaccount.com"}


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
    for role in spec.ROLES:
        service = spec.service_spec(m, {"DATABASE_URL": "1", "SECRET_KEY": "2"}, role,
                                    (ROOT / "ops/summary_delivery/runtime.py").read_text())
        refs = [v["valueSource"]["secretKeyRef"]["secret"] for v in service["template"]["containers"][0]["env"] if "valueSource" in v]
        assert refs == list(spec.SECRETS.values())
        assert service["invokerIamDisabled"] is False
        assert service["template"]["serviceAccount"] == spec.RUNTIME_IDENTITY


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
])
def test_rehashed_manifest_cannot_choose_other_cleanup_targets(mutation):
    doc = document()
    mutation(doc["manifest"])
    doc["sha256"] = spec.digest(doc["manifest"])
    with pytest.raises(spec.Refused, match="fixed_resource_scope"):
        approved(doc, cleanup=True)


class FakeCloud:
    def __init__(self, manifest, *, populated=True):
        self.calls, self.cleanup_calls, self.seen, self.rows = 0, 0, [], {}
        self.cleaning = False
        self.project = {"etag": "retain-etag", "bindings": [
            {"role": "roles/cloudsql.client", "members": ["serviceAccount:" + spec.RUNTIME_IDENTITY, "serviceAccount:unrelated"]},
            {"role": "roles/viewer", "members": ["user:unrelated@example.test"]}]}
        if populated:
            for api, path, kind in manage.resources(manifest):
                self.rows[(api, path)] = {"name": path.removeprefix("v2/"), "state": "RUNNING",
                    "labels": {"purpose": spec.PURPOSE, "run-id": manifest["run_id"]},
                    "description": spec.PURPOSE + ":" + manifest["run_id"]}

    def begin_cleanup(self):
        self.cleaning = True

    def call(self, api, path, *, method="GET", body=None, missing_ok=False):
        self.seen.append((api, path, method, deepcopy(body)))
        if self.cleaning:
            self.cleanup_calls += 1
        else:
            self.calls += 1
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
    sql = type("SQL", (), {"cleanup": lambda self: None})()
    assert manage.cleanup(cloud, m, sql)["state"] == "removed"
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
        manage.cleanup(cloud, m, None)
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
    sql = type("SQL", (), {"cleanup": lambda self: pytest.fail("SQL must remain while a worker exists")})()
    result = manage.cleanup(cloud, m, sql)
    assert result["state"] == "UNVERIFIED" and result["requires_explicit_cleanup"]
    assert ("run", failed_path) in cloud.rows
    assert all((api, path) not in cloud.rows for api, path, kind in manage.resources(m) if kind in {"queue", "secret"})
    assert all((api, path) in cloud.rows for api, path, kind in manage.resources(m) if kind == "identity")
    assert "untrusted" not in str(result)


@pytest.mark.parametrize("public", [False, True])
def test_effective_ingress_checks_detect_inherited_public_invocation(monkeypatch, public):
    m = approved()

    class Cloud:
        def call(self, api, path, **kwargs):
            return {"token": kwargs["body"]["audience"]}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def read(self, count):
            return b'{"status":"healthy","synthetic":true}'

    class Opener:
        def open(self, request, timeout):
            correct = request.headers.get("X-serverless-authorization") == "Bearer " + request.full_url.removesuffix("/health")
            if not public and not correct:
                raise HTTPError(request.full_url, 403, "denied", None, None)
            return Reply()

    monkeypatch.setattr(manage, "build_opener", lambda *args: Opener())
    if public:
        with pytest.raises(spec.Refused, match="effective_private_ingress"):
            manage.verify_private_surface(Cloud(), m)
    else:
        assert manage.verify_private_surface(Cloud(), m)["health_requests"] == 9


def test_cleanup_budget_is_independent_of_exhausted_apply(monkeypatch):
    monkeypatch.setattr(manage.BaseCloud, "__init__", lambda self: None)
    monkeypatch.setattr(manage.BaseCloud, "call", lambda *a, **k: {})
    cloud = manage.Cloud()
    cloud.calls = 400
    with pytest.raises(spec.Refused):
        cloud.call("run", "example")
    cloud.begin_cleanup()
    assert cloud.call("run", "example") == {}
    assert cloud.cleanup_calls == 1


def test_database_headroom_failure_retains_safe_receipt_before_any_mutation(monkeypatch):
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
        yield SQL()

    monkeypatch.setattr(database, "admin", admin)
    result = manage.apply(cloud, doc, doc["sha256"], doc["manifest"]["nonce"], ENV)
    assert result["state"] == "UNVERIFIED" and result["failed_phase"] == "database_preflight"
    assert result["database_headroom"]["active"] == 7
    assert result["cleanup"]["state"] == "not_needed"
    assert all(r[2] == "GET" for r in cloud.seen)


def valid_runtime_environment():
    m = document()["manifest"]
    env = {row["name"]: row["value"] for row in spec.runtime_env(m, {"DATABASE_URL": "1", "SECRET_KEY": "1"}, "summary",
        (ROOT / "ops/summary_delivery/runtime.py").read_text()) if "value" in row}
    env.update(K_SERVICE=spec.PREFIX + "-summary", SECRET_KEY="x" * 64,
               DATABASE_URL=f"postgresql://{spec.DATABASE}:password@/{spec.DATABASE}?host=/cloudsql/{spec.INSTANCE}")
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
