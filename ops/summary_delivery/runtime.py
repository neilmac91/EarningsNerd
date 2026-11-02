"""Synthetic delivery verification entrypoint, injected only into purpose-owned services.

The production receiver, child supervisor, summary orchestrator and persistence owners
run unchanged. Fixed source/provider/mail boundaries are offline fixtures. This is
delivery and ownership evidence, never SEC, model quality or real email acceptance.
"""
from __future__ import annotations

import asyncio
import copy
import hashlib
import hmac
import json
import os
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen

PURPOSE = "summary-delivery-verification"
DATABASE = "earningsnerd_summary_verify"
PREFIX = "earningsnerd-summary-verify"
INSTANCE = "earnings-nerd:us-west1:earningsnerd-db"
RUN_TABLE = "earningsnerd_summary_verify_state"
EVENT_TABLE = "earningsnerd_summary_verify_events"
FILINGS = ((45003, "10-Q", "0000872589-26-000034"), (45004, "8-K", "0000872589-26-000032"))
EMAILS = ("summary-one@delivery.invalid", "summary-two@delivery.invalid", "mail@delivery.invalid")
ALLOWED_HOSTS = frozenset(("metadata.google.internal", "169.254.169.254", "cloudtasks.googleapis.com", "www.googleapis.com",
                           "secretmanager.googleapis.com"))
FORBIDDEN_SECRETS = ("RESEND_API_KEY", "RESEND_WEBHOOK_SECRET", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET",
                     "SENTRY_DSN", "POSTHOG_API_KEY", "GOOGLE_CLIENT_SECRET", "APPLE_PRIVATE_KEY", "AI_FALLBACK_API_KEY")
PAYLOAD = {
    "status": "complete",
    "business_overview": "# Synthetic delivery fixture\n\nThis is isolated transport verification, not investment analysis.",
    "financial_highlights": {"notes": "Synthetic fixed fixture; no financial claim."},
    "risk_factors": [{"summary": "Synthetic fixture risk.", "supporting_evidence": "Synthetic fixture risk."}],
    "management_discussion": "Synthetic fixture discussion.", "key_changes": "Synthetic fixture changes.",
    "raw_summary": {"sections": {"business_overview": "Synthetic delivery fixture."},
                    "section_coverage": {"covered_count": 5, "total_count": 7}},
}


class Refused(RuntimeError):
    """Only fixed reason codes may leave the verifier."""


def validate_environment(env: dict, *, child: bool = False) -> tuple[str, str]:
    role, run_id = env.get("SUMMARY_VERIFY_ROLE"), env.get("SUMMARY_VERIFY_RUN_ID", "")
    if role not in {"api", "background", "summary"} or not run_id.isdigit() or not 1 <= len(run_id) <= 20:
        raise Refused("runtime_identity")
    expected = PREFIX + ("-api" if role == "api" else "-" + role)
    if env.get("K_SERVICE") != expected or env.get("ENVIRONMENT") != "production":
        raise Refused("runtime_identity")
    try:
        parsed = urlsplit(env["DATABASE_URL"])
        if (parsed.scheme != "postgresql" or parsed.hostname or parsed.port or parsed.username != DATABASE
                or parsed.path != "/" + DATABASE or not parsed.password
                or parse_qs(parsed.query) != {"host": ["/cloudsql/" + INSTANCE]}):
            raise Refused("database_boundary")
    except (KeyError, ValueError):
        raise Refused("database_boundary") from None
    if (any(env.get(key) for key in FORBIDDEN_SECRETS)
            or env.get("OPENAI_API_KEY") != "offline-summary-delivery-fixture"
            or len(env.get("SECRET_KEY", "")) < 32
            or env.get("DB_POOL_SIZE") != "1" or env.get("DB_MAX_OVERFLOW") != "0"
            or env.get("SUMMARY_PREWARM_MAX_PER_SCAN") != "0" or env.get("SUMMARY_PREWARM_MAX_PER_DAY") != "0"
            or env.get("SUMMARY_DURABLE_GENERATION_ENABLED") != "true"
            or env.get("DURABLE_TASKS_ENABLED") != "true"
            or env.get("TASKS_WORK_TIMEOUT_SECONDS") != "80"):
        raise Refused("runtime_configuration")
    if role != "api" and env.get("TASKS_WORKER_ROLE") != role:
        raise Refused("worker_role")
    if child and role == "api":
        raise Refused("child_role")
    expected_hash = env.get("SUMMARY_VERIFY_RUNTIME_SHA256", "")
    if len(expected_hash) != 64 or hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != expected_hash:
        raise Refused("runtime_source")
    expected_sources = json.loads(env.get("SUMMARY_VERIFY_SOURCE_HASHES", "{}"))
    if not expected_sources or len(expected_sources) > 12:
        raise Refused("application_source")
    for filename, digest in expected_sources.items():
        if not filename.startswith("app/") or ".." in filename or not filename.endswith(".py"):
            raise Refused("application_source")
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != digest:
            raise Refused("application_source")
    return role, run_id


def install_network_guard() -> None:
    """Application-owned Python sockets may reach only fixed Google control endpoints.

    SQL uses the purpose-owned Unix socket and restricted database role. This is a
    Python process guard, not a claim of a platform firewall or native-code sandbox.
    """
    resolved = {"169.254.169.254"}
    original = socket.getaddrinfo

    def lookup(host, *args, **kwargs):
        normalized = host.decode("ascii") if isinstance(host, bytes) else host
        if normalized not in ALLOWED_HOSTS:
            raise Refused("unexpected_network")
        rows = original(host, *args, **kwargs)
        resolved.update(row[4][0] for row in rows)
        return rows

    socket.getaddrinfo = lookup

    def audit(event, args):
        if event == "socket.connect" and isinstance(args[1], tuple) and args[1][0] not in resolved:
            raise Refused("unexpected_network")
        if event == "socket.getaddrinfo":
            host = args[0].decode("ascii") if isinstance(args[0], bytes) else args[0]
            if host not in ALLOWED_HOSTS:
                raise Refused("unexpected_network")

    sys.addaudithook(audit)


def verify_runtime_permissions() -> None:
    """Check the actual metadata identity and its effective access to production secrets."""
    base = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/"
    headers = {"Metadata-Flavor": "Google"}
    with urlopen(Request(base + "email", headers=headers), timeout=4) as response:
        identity = response.read(257).decode()
    if identity != "en-summary-verify@earnings-nerd.iam.gserviceaccount.com":
        raise Refused("runtime_iam_identity")
    with urlopen(Request(base + "token", headers=headers), timeout=4) as response:
        data = response.read(16385)
        if len(data) > 16384:
            raise Refused("metadata_bound")
        token = json.loads(data)["access_token"]
    names = json.loads(os.environ["SUMMARY_VERIFY_PRODUCTION_SECRET_NAMES"])
    if not isinstance(names, list) or not 1 <= len(names) <= 40:
        raise Refused("production_secret_inventory")
    for name in names:
        if not isinstance(name, str) or not name or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-" for c in name):
            raise Refused("production_secret_inventory")
        request = Request("https://secretmanager.googleapis.com/v1/projects/earnings-nerd/secrets/" + name + ":testIamPermissions",
                          data=b'{"permissions":["secretmanager.versions.access"]}', method="POST",
                          headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        with urlopen(request, timeout=4) as response:
            content = response.read(8193)
            if len(content) > 8192 or json.loads(content).get("permissions", []):
                raise Refused("production_secret_access")


def tables():
    from sqlalchemy import Column, DateTime, Integer, JSON, MetaData, String, Table
    metadata = MetaData()
    state = Table(RUN_TABLE, metadata, Column("id", Integer, primary_key=True),
                  Column("run_id", String(20), nullable=False), Column("created_at", DateTime(timezone=True), nullable=False),
                  Column("value", JSON, nullable=False))
    events = Table(EVENT_TABLE, metadata, Column("id", Integer, primary_key=True),
                   Column("kind", String(40), nullable=False), Column("filing_id", Integer),
                   Column("at", DateTime(timezone=True), nullable=False))
    return metadata, state, events


def record(kind: str, filing_id: int | None = None) -> None:
    if kind not in {"provider_started", "provider_completed", "native_stall", "mail_started", "mail_enqueued",
                    "worker_started", "worker_failed", "worker_completed", "child_reaped"} or filing_id not in {None, 45003, 45004}:
        raise Refused("event_boundary")
    from app.database import engine
    from sqlalchemy import insert
    _, _, events = tables()
    with engine.begin() as connection:
        connection.execute(insert(events).values(kind=kind, filing_id=filing_id, at=datetime.now(timezone.utc)))


def seed(run_id: str) -> dict:
    from app.database import Base, SessionLocal, engine
    from app.models import Company, Filing, User
    from app.routers.auth import create_access_token
    from sqlalchemy import insert, select
    metadata, state, _ = tables()
    metadata.create_all(engine)
    with engine.begin() as connection:
        if connection.execute(select(state.c.id)).first() is not None:
            raise Refused("seed_already_exists")
        connection.execute(insert(state).values(id=1, run_id=run_id, created_at=datetime.now(timezone.utc),
                                                value={"generation_posts": 0, "result_gets": 0,
                                                       "control_calls": 0, "mail_calls": 0, "recovery_calls": 0,
                                                       "cloud_create_tasks": 0, "worker_deliveries": 0}))
    Base.metadata.create_all(engine)  # isolated, empty database only; never imported by production startup
    with SessionLocal() as db:
        if db.query(User).count() or db.query(Filing).count():
            raise Refused("database_not_empty")
        company = Company(cik="0000872589", ticker="REGN", name="Synthetic REGN delivery fixture")
        users = [User(email=email, is_active=True, email_verified=index < 2) for index, email in enumerate(EMAILS)]
        db.add(company)
        db.add_all(users)
        db.flush()
        for filing_id, form, accession in FILINGS:
            archive = "https://www.sec.gov/Archives/edgar/data/872589/" + accession.replace("-", "") + "/"
            db.add(Filing(id=filing_id, company_id=company.id, accession_number=accession, filing_type=form,
                          filing_date=datetime(2026, 10, 30, tzinfo=timezone.utc),
                          document_url=archive + "regn-20261030.htm", sec_url=archive))
        db.commit()
        return {"tokens": [create_access_token({"sub": user.email}) for user in users[:2]]}


def consume(run_id: str, field: str, maximum: int) -> None:
    from app.database import engine
    from sqlalchemy import select, update
    _, state, _ = tables()
    with engine.begin() as connection:
        row = connection.execute(select(state).where(state.c.id == 1).with_for_update()).one()
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if row.run_id != run_id or (datetime.now(timezone.utc) - created).total_seconds() > 600:
            raise Refused("run_expired")
        value = dict(row.value)
        if value[field] >= maximum:
            raise Refused("request_budget")
        value[field] += 1
        connection.execute(update(state).where(state.c.id == 1).values(value=value))


def receipt(run_id: str) -> dict:
    from app.database import SessionLocal, engine
    from app.models import Summary, SummaryJob, UsageReservation, UserUsage
    from sqlalchemy import select
    _, state, events = tables()
    with engine.connect() as connection:
        row = connection.execute(select(state).where(state.c.id == 1)).one()
        if row.run_id != run_id:
            raise Refused("run_identity")
        observations = list(connection.execute(select(events).order_by(events.c.id)).mappings())
    with SessionLocal() as db:
        jobs = db.query(SummaryJob).order_by(SummaryJob.filing_id).all()
        result = {"run_id": run_id, "synthetic": True, "request_counts": row.value,
                  "jobs": [{"filing_id": j.filing_id, "status": j.status, "attempts": j.attempts,
                            "charge_state": j.charge_state, "summary_present": j.summary_id is not None,
                            "lease_present": j.lease_until is not None} for j in jobs],
                  "summaries": db.query(Summary).count(), "reservations": db.query(UsageReservation).count(),
                  "logical_charges": sum(x.summary_count for x in db.query(UserUsage).all()),
                  "events": [{"kind": r["kind"], "filing_id": r["filing_id"], "at": r["at"].isoformat()}
                             for r in observations], "real_provider_calls": 0, "real_mail_calls": 0,
                  "source_semantics_verified": False}
    if len(result["events"]) > 100 or len(jobs) > 2 or sum(j["attempts"] for j in result["jobs"]) > 8:
        raise Refused("work_budget")
    return result


def install_enqueue_bounds(run_id: str) -> None:
    """Bound real adapter calls without replacing Cloud Tasks or changing task identity."""
    from app.services import account_mail_service, durable_tasks, summary_jobs
    from app.services.request_work import run_owned_sync
    original = durable_tasks.enqueue_task

    async def bounded(kind, payload, **kwargs):
        if kind not in {"summary", "account_mail"}:
            raise Refused("task_kind_boundary")
        if kind == "account_mail" and payload != {"mail": "verification", "email": EMAILS[2]}:
            raise Refused("mail_identity")
        await run_owned_sync(consume, run_id, "cloud_create_tasks", 32)
        return await original(kind, payload, **kwargs)

    durable_tasks.enqueue_task = bounded
    summary_jobs.enqueue_task = bounded
    account_mail_service.enqueue_task = bounded


def install_fixtures(envelope) -> None:
    from app.database import SessionLocal
    from app.models import SummaryJob
    from app.services import email_service, summary_pipeline as pipeline
    from app.services.ai.provider_requests import signal_provider_start
    from app.services.request_work import run_owned_sync
    from unittest.mock import AsyncMock

    async def mail(**kwargs):
        if kwargs.get("to_email") != EMAILS[2]:
            raise Refused("mail_identity")
        await run_owned_sync(record, "mail_started")

    email_service.send_verification_email = mail
    email_service.send_password_reset_email = mail
    if envelope.kind != "summary":
        return
    with SessionLocal() as db:
        row = db.get(SummaryJob, envelope.payload["job_id"])
        if row is None or row.filing_id not in {45003, 45004} or row.generation != 1 or row.attempts >= 4:
            raise Refused("summary_identity")
        filing_id, first_attempt = row.filing_id, row.attempts == 0
    text = "Synthetic delivery fixture. Synthetic fixture risk. Synthetic fixture discussion. " * 40
    primary = "<html><body>" + text + "</body></html>"
    pipeline.sec_edgar_service.get_filing_document = AsyncMock(return_value=primary)
    pipeline.xbrl_service.get_xbrl_data = AsyncMock(return_value=None)
    pipeline.xbrl_service.get_filing_sections = AsyncMock(return_value=None)
    pipeline.get_or_cache_excerpt = lambda *args, **kwargs: text

    async def provider(*args, **kwargs):
        signal_provider_start()
        await run_owned_sync(record, "provider_started", filing_id)
        if filing_id == 45004 and first_attempt:
            await run_owned_sync(record, "native_stall", filing_id)
            # A cancellation-resistant native sleep stands for a blocked provider thread.
            # Production task_process_service must kill and reap this child at its own deadline.
            await run_owned_sync(time.sleep, 200)
            raise Refused("deadline_did_not_stop_native_child")
        await asyncio.sleep(70 if filing_id == 45003 else 1)
        await run_owned_sync(record, "provider_completed", filing_id)
        return copy.deepcopy(PAYLOAD)

    pipeline.openai_service.summarize_filing = provider


def child_main() -> int:
    from app.services import task_process
    from app.services.durable_tasks import TaskEnvelope
    install_enqueue_bounds(os.environ["SUMMARY_VERIFY_RUN_ID"])
    original = task_process._execute

    async def execute(envelope: TaskEnvelope):
        install_fixtures(envelope)
        await original(envelope)

    task_process._execute = execute
    return task_process.main()


def make_app(role: str, run_id: str):
    from fastapi import Depends, FastAPI, Header, HTTPException
    from fastapi.responses import JSONResponse
    from app.config import settings
    from app.services.request_work import run_owned_sync

    if not hasattr(settings, "SUMMARY_TASKS_QUEUE") or not hasattr(settings, "TASKS_WORKER_ROLE"):
        raise Refused("image_missing_isolation")
    install_enqueue_bounds(run_id)
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    def control(x_summary_verify: str | None = Header(default=None)):
        if not x_summary_verify or not hmac.compare_digest(x_summary_verify, settings.SECRET_KEY):
            raise HTTPException(401, "Verification control denied")

    @app.exception_handler(Refused)
    async def closed_failure(request, error):
        return JSONResponse({"state": "refused"}, status_code=409)

    @app.get("/health")
    def health():
        return {"status": "healthy", "synthetic": True}

    if role != "api":
        from app.routers.tasks import router
        from app.services import task_process_service
        task_process_service._command = lambda: (sys.executable, __file__, "--child")
        original = task_process_service.run_task_process
        # The router imports its own alias; wrap only to record durable parent outcome.
        from app.routers import tasks

        async def run_task(envelope):
            await run_owned_sync(consume, run_id, "worker_deliveries", 12)
            await run_owned_sync(record, "worker_started")
            created = []
            spawn = asyncio.create_subprocess_exec

            async def observed_spawn(*args, **kwargs):
                # Fixture children must not emit provider/document/token-bearing
                # app exceptions into inherited cloud logs. The real supervisor
                # still owns stdin, timeout, kill and reap without alteration.
                kwargs["stdout"] = asyncio.subprocess.DEVNULL
                kwargs["stderr"] = asyncio.subprocess.DEVNULL
                process = await spawn(*args, **kwargs)
                created.append(process)
                return process

            # Observe the real supervisor's process, kill and wait ownership; do
            # not replace its deadline or its finally block. This private worker
            # admits one request and the supervisor itself refuses overlap.
            asyncio.create_subprocess_exec = observed_spawn
            try:
                await original(envelope)
            except BaseException:
                await run_owned_sync(record, "worker_failed")
                raise
            finally:
                asyncio.create_subprocess_exec = spawn
                if len(created) != 1 or created[0].returncode is None:
                    raise Refused("child_reap_unverified")
                await run_owned_sync(record, "child_reaped")
            await run_owned_sync(record, "worker_completed")

        tasks.run_background_task = run_task
        app.include_router(router, prefix="/internal")
        return app

    from app.routers import summaries
    from app.api_errors import CodedHTTPException, coded_http_exception_handler
    app.add_exception_handler(CodedHTTPException, coded_http_exception_handler)

    @app.middleware("http")
    async def request_budget(request, call_next):
        if request.url.path.startswith("/api/"):
            allowed = {f"/api/summaries/filing/{fid}" for fid, _, _ in FILINGS}
            path = request.url.path.removesuffix("/generate-stream")
            if path not in allowed or request.url.query or request.method not in {"GET", "POST"}:
                return JSONResponse({"state": "refused"}, status_code=409)
            field, maximum = ("generation_posts", 4) if request.method == "POST" else ("result_gets", 6)
            try:
                await run_owned_sync(consume, run_id, field, maximum)
            except Refused:
                return JSONResponse({"state": "refused"}, status_code=409)
        return await call_next(request)

    app.include_router(summaries.router, prefix="/api/summaries")

    @app.post("/__summary_verify__/seed", dependencies=[Depends(control)])
    async def initialize():
        return await run_owned_sync(seed, run_id)

    @app.post("/__summary_verify__/mail", dependencies=[Depends(control)])
    async def enqueue_mail():
        from app.services.account_mail_service import queue_account_mail
        await run_owned_sync(consume, run_id, "mail_calls", 1)
        await run_owned_sync(record, "mail_enqueued")
        await queue_account_mail("verification", EMAILS[2])
        return {"state": "accepted"}

    @app.post("/__summary_verify__/recover", dependencies=[Depends(control)])
    async def recovery():
        from app.services.summary_jobs import recover_due_jobs
        await run_owned_sync(consume, run_id, "recovery_calls", 8)
        return {"dispatched": await recover_due_jobs(limit=20)}

    @app.get("/__summary_verify__/receipt", dependencies=[Depends(control)])
    async def read_receipt():
        await run_owned_sync(consume, run_id, "control_calls", 100)
        return await run_owned_sync(receipt, run_id)

    return app


def main() -> int:
    role, run_id = validate_environment(dict(os.environ), child="--child" in sys.argv)
    install_network_guard()
    if "--child" not in sys.argv:
        verify_runtime_permissions()
    if "--child" in sys.argv:
        return child_main()
    import uvicorn
    uvicorn.run(make_app(role, run_id), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")),
                access_log=False, log_level="warning", loop="asyncio")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        print("Summary delivery verifier refused its runtime", file=sys.stderr)
        raise SystemExit(1) from None
