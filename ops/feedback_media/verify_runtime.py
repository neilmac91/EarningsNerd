"""Inline preview entrypoint, never a production route or script: only the protected verifier supplies it to the
serving image. Credentials stay in environment/secret references; no application collaborator is replaced."""
from __future__ import annotations

import ast
import asyncio
import hashlib
import hmac
import json
import os
import re
import resource
import subprocess
import sys
import threading
import time
from contextlib import closing
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from uuid import uuid4

DATABASE = "earningsnerd_feedback_verify"
BUCKET = "earnings-nerd-feedback-media-preview"
PURPOSE = "feedback-media-verification"
ORIGIN = "https://localhost:8443"
MARKER = "earningsnerd_feedback_verify_runs"
ROLES = ("owner", "other", "admin")
ASSERTIONS = frozenset(("upload", "clipboard", "private_reads", "other_user_denied", "admin_view",
                        "safe_links", "retry", "export", "account_deleted", "cleanup", "memory_boundary"))
HASH_ENV = {"image_digest": "FEEDBACK_VERIFY_IMAGE_DIGEST", "runtime_source_sha256": "FEEDBACK_VERIFY_RUNTIME_SHA256",
            "verification_suite_sha256": "FEEDBACK_VERIFY_SUITE_SHA256", "frontend_tree": "FEEDBACK_VERIFY_FRONTEND_TREE"}
DOMAIN = b"feedback-media-verification-"
INTEGRATIONS = ("OPENAI_API_KEY", "AI_FALLBACK_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_PUBLISHABLE_KEY",
                "STRIPE_WEBHOOK_SECRET", "POSTHOG_API_KEY", "SENTRY_DSN", "RESEND_API_KEY", "RESEND_WEBHOOK_SECRET",
                "GOOGLE_CLIENT_SECRET", "APPLE_PRIVATE_KEY", "TURNSTILE_SECRET_KEY", "INTERNAL_JOB_TOKEN",
                "TASKS_WORKER_URL", "TASKS_INVOKER_EMAIL", "FMP_API_KEY", "ALPHA_VANTAGE_API_KEY")
IAM_PROBE = '''import google.auth
from google.auth.transport.requests import AuthorizedSession
credentials,_=google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
session=AuthorizedSession(credentials)
for secret in ("DATABASE_URL","SECRET_KEY"):
    response=session.post("https://secretmanager.googleapis.com/v1/projects/earnings-nerd/secrets/"+secret+":testIamPermissions",json={"permissions":["secretmanager.versions.access"]},timeout=4)
    if response.status_code!=200 or response.json().get("permissions",[]): raise SystemExit(1)
response=session.get("https://storage.googleapis.com/storage/v1/b/earnings-nerd-feedback-media-prod/iam/testPermissions",params=[("permissions",p) for p in ("storage.objects.create","storage.objects.get","storage.objects.delete")],timeout=4)
if response.status_code!=200 or response.json().get("permissions",[]): raise SystemExit(1)
'''


class Refused(Exception):
    """Only closed reason codes may leave verification controls."""


def digest(key, label, value):
    return hmac.new(key.encode(), DOMAIN + label.encode() + b"-v1\0" + value.encode(), hashlib.sha256).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def worker_limits():
    """Verify the serving source's child-launch bounds; workers unchanged."""
    result = {}
    for module, name, constructor, count in (("feedback_image_service", "_execution_lock", "Lock", 1),
                                            ("feedback_storage_worker_service", "_execution_slots", "Semaphore", 2)):
        tree = ast.parse(Path("app/services/" + module + ".py").read_text())
        assignments = [node for node in tree.body if isinstance(node, ast.Assign)
                       and any(isinstance(target, ast.Name) and target.id == name for target in node.targets)]
        if len(assignments) != 1:
            raise Refused("worker_bounds")
        value = assignments[0].value
        if (not isinstance(value, ast.Call) or not isinstance(value.func, ast.Attribute)
                or value.func.attr != constructor or (constructor == "Semaphore" and
                (len(value.args) != 1 or not isinstance(value.args[0], ast.Constant) or value.args[0].value != count))):
            raise Refused("worker_bounds")
        launches = [node for node in ast.walk(tree) if isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute) and node.func.attr == "create_subprocess_exec"]
        guarded = [node for node in ast.walk(tree) if isinstance(node, ast.AsyncWith)
                   and any(isinstance(item.context_expr, ast.Name) and item.context_expr.id == name for item in node.items)]
        if len(launches) != 1 or not any(launches[0] in list(ast.walk(node)) for node in guarded):
            raise Refused("worker_bounds")
        result[module] = count
    return result


def resource_acceptance(memory):
    """Measured representative workload, never a guarantee for warmed/mixed filing traffic."""
    cap = 1073741824
    age = memory.get("sample_age_seconds")
    if (memory["sample_count"] < 5 or memory["unexplained_children"] or memory["last_process_count"] != 1
            or not isinstance(age, (int, float)) or not 0 <= age <= 1):
        return False
    sample = memory["cgroup_sample_peak_bytes"]
    peak = memory["cgroup_kernel_peak_bytes"]
    limit = memory["cgroup_memory_limit_bytes"]
    if limit is not None and limit != cap:
        return False
    if peak is not None:
        return 0 < peak < cap * .85 and (sample is None or sample < cap * .85)
    if memory["worker_limits"] != {"feedback_image_service": 1, "feedback_storage_worker_service": 2}:
        return False
    bound = memory["self_high_water_rss_bytes"] + 3 * memory["worker_high_water_rss_bytes"]
    return (memory["self_high_water_rss_bytes"] > 0 and memory["worker_high_water_rss_bytes"] > 0
            and sample is not None and 0 < sample < cap * .85 and bound < cap * .85)


def environment(env):
    from sqlalchemy.engine import make_url

    mode = env.get("FEEDBACK_VERIFY_MODE", "api")
    if (mode == "api" and env.get("K_SERVICE") != "earningsnerd-feedback-verify"
            or mode in {"initialize", "cleanup", "cleanup_now"} and env.get("CLOUD_RUN_JOB") != "earningsnerd-feedback-verify-cleanup"
            or mode not in {"api", "initialize", "cleanup", "cleanup_now"}):
        raise Refused("runtime_identity")
    try:
        url = make_url(env["DATABASE_URL"])
        if (url.drivername != "postgresql" or url.database != DATABASE or url.username != DATABASE
                or not url.password or url.host or url.query.get("host") != "/cloudsql/earnings-nerd:us-west1:earningsnerd-db"):
            raise ValueError()
    except Exception:  # noqa: BLE001 — withhold database, credential and submitted-content exception values
        raise Refused("database_configuration") from None
    required = {"ENVIRONMENT": "production", "FEEDBACK_MEDIA_BUCKET": BUCKET, "COOKIE_SECURE": "true",
                "COOKIE_SAMESITE": "lax", "CORS_ORIGINS_STR": ORIGIN, "FRONTEND_URL": ORIGIN,
                "SKIP_REDIS_INIT": "true", "DURABLE_TASKS_ENABLED": "false", "FEEDBACK_MEDIA_ENABLED": "true"}
    if any(env.get(name) != value for name, value in required.items()) or env.get("COOKIE_DOMAIN"):
        raise Refused("preview_configuration")
    if any(env.get(name) for name in INTEGRATIONS):
        raise Refused("external_credentials")
    run = env.get("FEEDBACK_VERIFY_RUN_ID", "")
    if not re.fullmatch(r"[1-9][0-9]{0,19}-1", run) or len(env.get("SECRET_KEY", "")) < 32:
        raise Refused("run_configuration")
    for field, name in HASH_ENV.items():
        pattern = r"sha256:[a-f0-9]{64}" if field == "image_digest" else r"[a-f0-9]{40}" if field == "frontend_tree" else r"[a-f0-9]{64}"
        if not re.fullmatch(pattern, env.get(name, "")):
            raise Refused("source_configuration")
    return run


def check_database(connection, env, *, expired=False):
    """Check actual PostgreSQL authority, not a connection-string label."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_database(),current_user,rolsuper,rolcreatedb,rolcreaterole,rolreplication,rolbypassrls "
                       "FROM pg_roles WHERE rolname=current_user")
        row = cursor.fetchone()
        if row is None or row[:2] != (DATABASE, DATABASE) or any(row[2:]):
            raise Refused("database_authority")
        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=(SELECT oid FROM pg_roles WHERE rolname=current_user))")
        if cursor.fetchone()[0]:
            raise Refused("database_membership")
        cursor.execute(f"SELECT purpose,image_digest,runtime_source_sha256,verification_suite_sha256,frontend_tree,"
                       f"expires_at > CURRENT_TIMESTAMP,EXTRACT(EPOCH FROM expires_at) FROM {MARKER} WHERE run_id=%s", (env["FEEDBACK_VERIFY_RUN_ID"],))
        row = cursor.fetchone()
        expected = (PURPOSE, *(env[name] for name in HASH_ENV.values()))
        if row is None or tuple(row[:5]) != expected or (not expired and not row[5]):
            raise Refused("run_marker")
        return float(row[6])


class Runtime:
    def __init__(self, env):
        self.env = dict(env)
        self.run = environment(env)
        self.key = env["SECRET_KEY"]
        self.boot = str(uuid4())
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.notifications = {"accepted": 0, "rejected": 0, "attachment_counts": [],
                              "admin_link_valid": True, "no_image_payload": True}
        self.resources = {"sample_count": 0, "rss_peak_bytes": 0, "cgroup_sample_peak_bytes": None,
                          "cgroup_kernel_peak_bytes": None, "cgroup_memory_limit_bytes": None,
                          "configured_memory_limit_bytes": 1073741824,
                          "self_high_water_rss_bytes": 0, "worker_high_water_rss_bytes": 0,
                          "worker_limits": {}, "unexplained_children": False, "last_process_count": 1,
                          "method": "kernel peak when exposed; otherwise conservative process bound plus sampled memory; representative workload only"}
        self.permission_audited = False
        self.last_cleanup = None
        self.last_sample, self.spawning, self.basis = None, {}, "kernel peak unavailable; conservative process-bound evidence"
        self.expires = 0

    def authority(self, *, expired=False):
        import psycopg2
        with closing(psycopg2.connect(self.env["DATABASE_URL"], connect_timeout=5,
                     options="-c statement_timeout=10000 -c lock_timeout=3000")) as connection, connection:
            self.expires = check_database(connection, self.env, expired=expired)

    def audit_permissions(self):
        from app.services.feedback_storage_worker_service import BoundedFeedbackStorage
        BoundedFeedbackStorage(BUCKET).verify_permissions()
        try:
            result = subprocess.run([sys.executable, "-I", "-c", IAM_PROBE], check=False, env={},
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            if result.returncode:
                raise Refused("production_authority")
        except (OSError, subprocess.SubprocessError):
            raise Refused("authority_unverified") from None
        self.permission_audited = True

    def credentials(self, role):
        return {"email": f"feedback-verify+{self.run}-{role}@example.com",
                "password": digest(self.key, "password", self.run + "\0" + role)}

    def marker(self, db, *, latest=True):
        from sqlalchemy import func, select, text
        db.scalar(select(func.set_config("lock_timeout", "3s", True)))
        db.scalar(select(func.set_config("statement_timeout", "10s", True)))
        marker = db.execute(text(f"SELECT * FROM {MARKER} WHERE run_id=:run FOR UPDATE"), {"run": self.run}).mappings().one()
        if marker["purpose"] != PURPOSE:
            raise Refused("run_marker")
        if latest and db.scalar(text(f"SELECT COUNT(*) FROM {MARKER} WHERE purpose=:purpose AND created_at>=:created"),
                                {"purpose": PURPOSE, "created": marker["created_at"]}) != 1:
            raise Refused("superseded_run")
        return marker

    def owned_rows(self, db, marker):
        from app.models import User
        from app.models.feedback import FeedbackAttachment
        ids = marker["fixtures"] or {}
        if (not isinstance(ids, dict) or set(ids) not in (set(), set(ROLES)) or len(set(ids.values())) != len(ids)
                or any(type(value) is not int or value < 1000000 for value in ids.values())):
            raise Refused("fixture_marker")
        users = db.query(User).limit(4).all()
        reverse = {value: key for key, value in ids.items()}
        if any(user.id not in reverse or user.email != self.credentials(reverse[user.id])["email"]
               or user.stripe_customer_id or user.stripe_subscription_id
               or user.is_admin != (reverse[user.id] == "admin") for user in users):
            raise Refused("foreign_account")
        if db.query(FeedbackAttachment.id).filter(FeedbackAttachment.deleted_at.is_(None),
                                                FeedbackAttachment.created_at < marker["created_at"]).first():
            raise Refused("earlier_unsettled_media")
        return ids

    def fixtures(self):
        from app.database import SessionLocal
        from app.models import User
        from app.services.password_utils import get_password_hash, verify_password
        from sqlalchemy import text
        self.authority()
        if not self.permission_audited:
            self.audit_permissions()
        with SessionLocal() as db:
            marker = self.marker(db)
            ids = self.owned_rows(db, marker)
            if marker["completed_at"]:
                raise Refused("completed_run")
            for index, role in enumerate(ROLES):
                credential = self.credentials(role)
                if role in ids:
                    user = db.get(User, ids[role])
                    if user is None or not verify_password(credential["password"], user.hashed_password):
                        raise Refused("fixture_changed")
                else:
                    identity = 1000000 + int(hashlib.sha256(self.run.encode()).hexdigest()[:7], 16) * 4 + index
                    user = User(id=identity, email=credential["email"],
                                hashed_password=get_password_hash(credential["password"]), is_active=True,
                                is_admin=role == "admin", is_beta=True, email_verified=True, full_name="Synthetic verification")
                    db.add(user)
                    ids[role] = identity
            db.execute(text(f"UPDATE {MARKER} SET fixtures=CAST(:fixtures AS jsonb) WHERE run_id=:run"),
                       {"fixtures": json.dumps(ids), "run": self.run})
            db.commit()
        return {"schema": 1, "run_id": self.run,
                "accounts": {role: {"id": ids[role], **self.credentials(role)} for role in ROLES}}

    def snapshot(self, *, latest=True):
        from app.database import SessionLocal
        from app.models import User
        from app.models.feedback import Feedback, FeedbackAttachment, FeedbackSubmission
        with SessionLocal() as db:
            marker = self.marker(db, latest=latest)
            self.owned_rows(db, marker)
            attachments = db.query(FeedbackAttachment).filter(FeedbackAttachment.created_at >= marker["created_at"]).limit(101).all()
            if len(attachments) > 100:
                raise Refused("record_limit")
            counts = {"feedback": db.query(Feedback).filter(Feedback.created_at >= marker["created_at"]).count(),
                      "submitted": db.query(FeedbackSubmission).filter(FeedbackSubmission.created_at >= marker["created_at"],
                                                                       FeedbackSubmission.feedback_id.isnot(None)).count(),
                      "attachments": len(attachments), "fixture_users": db.query(User).count()}
            counts["published_attachments"] = sum(row.feedback_id is not None for row in attachments)
            counts["confirmed_generation_deletions"] = sum(row.deleted_at is not None and row.object_generation is not None for row in attachments)
            counts["normalized_metadata_valid"] = all(row.content_type == "image/png" and 0 < row.width <= 8192
                and 0 < row.height <= 8192 and row.width * row.height <= 16000000
                and 0 < row.byte_count <= 8 * 1024 * 1024 and re.fullmatch(r"[a-f0-9]{64}", row.checksum)
                for row in attachments)
            counts.update({name: sum(row.state == name for row in attachments) for name in ("available", "deleted")})
            counts["pending"] = sum(row.deleted_at is None for row in attachments)
            saved = marker["receipt"]
        with self.lock:
            resources = {**self.resources, "sample_age_seconds": time.monotonic() - self.last_sample if self.last_sample else None}
            resources["conservative_process_bound_bytes"] = resources["self_high_water_rss_bytes"] + 3 * resources["worker_high_water_rss_bytes"]
            resources["evidence_basis"] = self.basis if resources["cgroup_kernel_peak_bytes"] is None else "kernel cgroup high-water peak"
            resources["acceptance_passed"] = resource_acceptance(resources)
            return {"schema": 1, "run_id": self.run, "boot_id": self.boot, "database": counts,
                    "notifications": json.loads(json.dumps(self.notifications)), "resources": resources,
                    "cleanup": self.last_cleanup, "receipt": saved}

    def cleanup(self, *, scheduled=False):
        from app.database import SessionLocal
        from app.models import User
        from app.services.feedback_media_cleanup_service import (
            run_feedback_media_cleanup,
        )
        from app.services.feedback_storage_worker_service import BoundedFeedbackStorage
        from app.services.user_account_service import delete_user
        from app.utils.datetimes import ensure_utc, utcnow
        self.authority(expired=True)
        with SessionLocal() as db:
            marker = self.marker(db, latest=False)
            # The hourly job spares a still-valid lease; controls and cleanup_now are explicit.
            if scheduled and ensure_utc(marker["expires_at"]) > utcnow():
                return {"skipped_active_run": True}
            ids = self.owned_rows(db, marker)
            for identity in ids.values():
                self.marker(db, latest=False)
                if db.get(User, identity) is not None:
                    delete_user(db, identity)
        self.last_cleanup = run_feedback_media_cleanup(SessionLocal, BoundedFeedbackStorage(BUCKET), batch_size=100, deadline_seconds=50)
        return self.snapshot(latest=False)

    def complete(self, body):
        from app.database import SessionLocal
        from app.utils.datetimes import iso_z, utcnow
        from sqlalchemy import text
        assertions = body.get("assertions")
        if set(body) != {"assertions"} or not isinstance(assertions, dict) or set(assertions) != ASSERTIONS or any(v is not True for v in assertions.values()):
            raise Refused("browser_assertions")
        result = self.snapshot()
        rows, mail, memory = result["database"], result["notifications"], result["resources"]
        if (not self.permission_audited or rows["feedback"] < 1 or rows["submitted"] != rows["feedback"]
                or rows["attachments"] < 3 or rows["pending"] or not rows["normalized_metadata_valid"]
                or rows["fixture_users"] or rows["deleted"] != rows["attachments"]
                or rows["confirmed_generation_deletions"] != rows["attachments"]
                or mail["accepted"] != rows["feedback"] or mail["rejected"] or not mail["admin_link_valid"]
                or sum(mail["attachment_counts"]) != rows["published_attachments"]
                or not mail["no_image_payload"] or not resource_acceptance(memory)
                or not self.last_cleanup or self.last_cleanup["errors"]):
            raise Refused("incomplete_evidence")
        payload = {"schema": 1, "purpose": PURPOSE, "run_id": self.run, "completed_at": iso_z(utcnow()),
                   **{field: self.env[name] for field, name in HASH_ENV.items()},
                   "browser_assertions": assertions, "observed": {key: result[key] for key in ("database", "notifications", "resources", "cleanup")}}
        signed = {"payload": payload, "signature": hmac.new(self.key.encode(), DOMAIN + b"receipt-v1\0" + canonical(payload), hashlib.sha256).hexdigest()}
        with SessionLocal() as db:
            self.owned_rows(db, self.marker(db))
            db.execute(text(f"UPDATE {MARKER} SET receipt=CAST(:receipt AS jsonb),completed_at=CURRENT_TIMESTAMP WHERE run_id=:run"),
                       {"receipt": json.dumps(signed), "run": self.run})
            db.commit()
        return signed

    def record_mail(self, payload):
        encoded = canonical(payload)
        sender = payload.get("reply_to")
        allowed = {self.credentials(role)["email"] for role in ROLES}
        body = payload.get("html", "")
        valid = (isinstance(body, str) and sender in allowed and payload.get("to") == ["feedback-verify-notify@example.com"]
                 and payload.get("from") == "Feedback verification <feedback-verify@example.com>"
                 and set(payload) <= {"from", "to", "subject", "html", "reply_to"})
        link = f'href="{ORIGIN}/admin/feedback"' in body if isinstance(body, str) else False
        no_image = not any(value in encoded.lower() for value in (b"<img", b"data:image", b"storage.googleapis.com", b"gs://", b"blob:"))
        match = re.search(r"<strong>Screenshots:</strong> ([0-3])", body) if isinstance(body, str) else None
        with self.lock:
            if not valid or not match or self.notifications["accepted"] >= 30:
                self.notifications["rejected"] += 1
                raise Refused("mail_envelope")
            self.notifications["accepted"] += 1
            self.notifications["attachment_counts"].append(int(match[1]))
            self.notifications["admin_link_valid"] &= link
            self.notifications["no_image_payload"] &= no_image

    def sample(self):
        def read(path):
            try:
                return Path(path).read_text().strip()
            except OSError:
                return ""
        parent, todo, seen, rss = os.getpid(), [os.getpid()], set(), 0
        unexplained, spawning, own, worker = False, {}, Path(f"/proc/{parent}/cmdline").read_bytes(), 0
        workers = [b"\0".join((os.fsencode(sys.executable), b"-I", b"-B",
                               os.fsencode(Path("app/services/" + worker + ".py").resolve()), b""))
                   for worker in ("feedback_image_service", "feedback_storage_worker_service")]
        while todo and len(seen) < 128:
            pid = todo.pop()
            if pid in seen:
                continue
            seen.add(pid)
            try:
                rss += int(Path(f"/proc/{pid}/statm").read_text().split()[1]) * os.sysconf("SC_PAGE_SIZE")
                if pid != parent:
                    argv = Path(f"/proc/{pid}/cmdline").read_bytes()
                    if Path(f"/proc/{pid}/stat").read_bytes().rsplit(b")", 1)[1].split()[0] == b"Z":
                        pass  # a zombie: no memory, awaiting its reap; still counted
                    elif argv in (own, b""):  # mid-exec or mid-exit; still so a second later, unexplained
                        spawning[pid] = self.spawning.get(pid, time.monotonic())
                        unexplained |= time.monotonic() - spawning[pid] > 1
                    elif argv in workers:  # own peak: a child's ru_maxrss holds its parent's
                        worker = max(worker, int(re.search(rb"VmHWM:\s+(\d+)", Path(f"/proc/{pid}/status").read_bytes())[1]) * 1024)
                    else:
                        unexplained = True
                todo.extend(int(child) for path in Path(f"/proc/{pid}/task").glob("*/children") for child in path.read_text().split())
            except (OSError, ValueError, IndexError, TypeError):
                continue
        self.spawning = spawning
        with self.lock:
            self.resources["sample_count"] += 1
            self.resources["rss_peak_bytes"] = max(rss, self.resources["rss_peak_bytes"])
            for key, name in (("cgroup_sample_peak_bytes", "current"), ("cgroup_kernel_peak_bytes", "peak"), ("cgroup_memory_limit_bytes", "max")):
                value = read("/sys/fs/cgroup/memory." + name)
                if name == "current" and not value.isdecimal():  # none at v2's root: instance memory in use
                    m = dict(f := re.findall(r"Mem(Total|Available): +(\d+) kB", read("/proc/meminfo")))
                    if len(f) == len(m) == 2 and (used := int(m["Total"]) - int(m["Available"])) > 0:
                        value, self.basis = str(used * 1024), "kernel peak unavailable; conservative process bound plus /proc/meminfo in use"
                if value.isdecimal():
                    self.resources[key] = max(int(value), self.resources[key] or 0)
            self.resources["last_process_count"] = len(seen)
            self.last_sample = time.monotonic()
            self.resources["unexplained_children"] |= unexplained or len(seen) > 4 or bool(todo)
            self.resources["self_high_water_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            self.resources["worker_high_water_rss_bytes"] = max(worker, self.resources["worker_high_water_rss_bytes"])

    def sampler(self):
        deadline = time.monotonic() + 7200
        while time.monotonic() < deadline and not self.stop.wait(.02):
            self.sample()


def sink(runtime):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            self.connection.settimeout(2)
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if (self.path != "/emails" or not 0 < length <= 65536 or self.headers.get("Transfer-Encoding")
                        or not hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + digest(runtime.key, "sink", runtime.run))):
                    raise Refused("mail_request")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise Refused("mail_request")
                runtime.record_mail(payload)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"id":"synthetic-feedback-notification"}')
            except Exception:  # noqa: BLE001 — values withheld
                self.send_response(400)
                self.end_headers()
    return HTTPServer(("127.0.0.1", 8091), Handler)


class Controls:
    def __init__(self, app, runtime):
        self.app, self.runtime = app, runtime
        self.control_lock = asyncio.Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/__feedback_verify/"):
            if scope["type"] == "http" and time.time() >= self.runtime.expires:
                await send({"type": "http.response.start", "status": 503, "headers": [(b"cache-control", b"no-store")]})
                return await send({"type": "http.response.body", "body": b"Verification run expired"})
            return await self.app(scope, receive, send)
        from app.services.request_work import request_work_scope, run_owned_sync
        status, result = 200, None
        try:
            headers = {key.lower(): value for key, value in scope["headers"]}
            expected = digest(self.runtime.key, "control", self.runtime.run).encode()
            if (any(sum(key.lower() == wanted for key, _ in scope["headers"]) != 1
                    for wanted in (b"x-feedback-verify-run", b"x-feedback-verify-control"))
                    or headers.get(b"x-feedback-verify-run") != self.runtime.run.encode()
                    or not hmac.compare_digest(headers.get(b"x-feedback-verify-control", b""), expected)):
                raise Refused("control_auth")
            action = scope["path"].rsplit("/", 1)[-1]
            if (scope["method"] != ("GET" if action == "receipt" else "POST")
                    or action not in {"fixtures", "receipt", "cleanup", "complete"}
                    or scope["path"] != "/__feedback_verify/" + action):
                raise Refused("control_route")
            data = b""
            async with asyncio.timeout(5):
                while True:
                    frame = await receive()
                    if frame["type"] != "http.request":
                        raise Refused("control_body")
                    data += frame.get("body", b"")
                    if len(data) > 4096:
                        raise Refused("control_body")
                    if not frame.get("more_body"):
                        break
            try:
                body = json.loads(data or b"{}")
            except ValueError:
                raise Refused("control_body") from None
            if not isinstance(body, dict) or (action != "complete" and body):
                raise Refused("control_body")
            async with self.control_lock, request_work_scope():
                await run_owned_sync(self.runtime.authority, expired=action in {"cleanup", "receipt"})
                method = self.runtime.snapshot if action == "receipt" else getattr(self.runtime, action)
                result = await run_owned_sync(method, *([body] if action == "complete" else []))
        except Refused as error:
            status, result = 403, {"error": str(error)}
        except Exception:  # noqa: BLE001 — values withheld
            status, result = 503, {"error": "verification_runtime_unavailable"}
        encoded = canonical(result)
        await send({"type": "http.response.start", "status": status,
                    "headers": [(b"content-type", b"application/json"), (b"cache-control", b"private, no-store")]})
        await send({"type": "http.response.body", "body": encoded})


def main():
    runtime = Runtime(os.environ)
    mode = os.environ.get("FEEDBACK_VERIFY_MODE", "api")
    if mode not in {"initialize", "api", "cleanup", "cleanup_now"}:
        raise Refused("runtime_mode")
    runtime.authority(expired=mode in {"cleanup", "cleanup_now"})
    runtime.resources["worker_limits"] = worker_limits()
    os.environ.update({name: "" for name in INTEGRATIONS})
    os.environ["PGOPTIONS"] = "-c lock_timeout=3000 -c statement_timeout=10000"
    os.environ["PWNED_PASSWORD_CHECK_ENABLED"] = "false"
    os.environ.update(RESEND_API_KEY=digest(runtime.key, "sink", runtime.run), RESEND_BASE_URL="http://127.0.0.1:8091",
                      FEEDBACK_NOTIFICATION_EMAIL="feedback-verify-notify@example.com",
                      RESEND_FROM_EMAIL="Feedback verification <feedback-verify@example.com>")
    # openai 3.x refuses an empty key at import; no verified route calls a model.
    os.environ.update(OPENAI_API_KEY="feedback-verification-no-model", OPENAI_BASE_URL="http://127.0.0.1:9/v1")
    if mode == "initialize":
        import app.models
        from app.database import Base, engine
        Base.metadata.create_all(engine)
        return
    if mode in {"cleanup", "cleanup_now"}:
        result = runtime.cleanup(scheduled=mode == "cleanup")
        if result.get("skipped_active_run"):
            print(json.dumps(result))
            return
        print(json.dumps({"cleanup": result["cleanup"], "pending": result["database"]["pending"]}))
        if result["database"]["pending"] or result["cleanup"]["errors"]:
            raise Refused("cleanup_incomplete")
        return
    runtime.audit_permissions()
    import uvicorn
    from main import app
    server = sink(runtime)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    threading.Thread(target=runtime.sampler, daemon=True).start()
    try:
        uvicorn.run(Controls(app, runtime), host="0.0.0.0", port=int(os.environ.get("PORT", "8080")),
                    proxy_headers=True, forwarded_allow_ips="*", access_log=False)
    finally:
        runtime.stop.set()
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 — values withheld
        raise SystemExit("Feedback verification runtime refused ("
                         + (str(error) if isinstance(error, Refused) else type(error).__name__) + ")") from None
