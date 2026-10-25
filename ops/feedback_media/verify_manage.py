"""Fixed, founder-approved private feedback verification infrastructure.

No production runtime secret is mounted in the verifier. The existing SQL credential is
used only inside this runner to check privileges and create the isolated database/role.
Provider payloads, credentials and browser state never enter this program's output.
"""
from __future__ import annotations

import argparse
import base64
import copy
import hashlib
import hmac
import json
import math
import os
import re
import secrets
import stat
import struct
import subprocess
import tempfile
import time
import zlib
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

try:
    from . import manage as media
except ImportError:
    import manage as media

ROOT = Path(__file__).resolve().parents[2]
PROJECT, REGION = media.PROJECT, media.REGION
PURPOSE = "feedback-media-verification"
NAME = "earningsnerd-feedback-verify"
SERVICE = f"{media.PARENT}/services/{NAME}"
JOB = f"{media.PARENT}/jobs/{NAME}-cleanup"
SCHEDULE = f"{media.PARENT}/jobs/feedback-media-verify-cleanup-hourly"
IDENTITY = f"{NAME}@{PROJECT}.iam.gserviceaccount.com"
SA_PATH = f"projects/{PROJECT}/serviceAccounts/{IDENTITY}"
DATABASE = "earningsnerd_feedback_verify"
INSTANCE = f"{PROJECT}:{REGION}:earningsnerd-db"
DB_SECRET = "EARNINGSNERD_FEEDBACK_VERIFY_DATABASE_URL"
KEY_SECRET = "EARNINGSNERD_FEEDBACK_VERIFY_SECRET_KEY"
BUCKET = media.BUCKETS["preview"]
MARKER = "earningsnerd_feedback_verify_runs"
SUITE_FILES = ("live_proxy.mjs", "live_browser.mjs", "live_runner.mjs")
ASSERTIONS = {name: True for name in (
    "upload", "clipboard", "private_reads", "other_user_denied", "admin_view", "safe_links",
    "retry", "export", "account_deleted", "cleanup", "memory_boundary",
)}
SCREENSHOTS = {"composer-light.png", "composer-dark.png", "composer-dark-recovery.png", "admin-light.png",
               "admin-dark.png", "admin-narrow-light.png", "admin-narrow-dark.png"}
RECEIPT_DOMAIN = b"feedback-media-verification-receipt-v1\0"
CONTROL_DOMAIN = b"feedback-media-verification-control-v1\0"
RUN_PATTERN = re.compile(r"[1-9][0-9]{0,19}-1")
IMAGE_PATTERN = re.compile(r"us-west1-docker\.pkg\.dev/earnings-nerd/earningsnerd/backend@sha256:[0-9a-f]{64}")
PROJECT_PERMISSIONS = {
    "iam.serviceAccounts.create", "iam.serviceAccounts.get", "iam.serviceAccounts.getIamPolicy",
    "iam.serviceAccounts.setIamPolicy", "resourcemanager.projects.getIamPolicy", "resourcemanager.projects.setIamPolicy",
    "run.services.create", "run.services.get", "run.services.update", "run.services.getIamPolicy", "run.services.setIamPolicy",
    "run.jobs.create", "run.jobs.get", "run.jobs.update", "run.jobs.run", "run.jobs.runWithOverrides",
    "run.jobs.getIamPolicy", "run.jobs.setIamPolicy", "cloudscheduler.jobs.create", "cloudscheduler.jobs.get",
    "cloudscheduler.jobs.update", "secretmanager.secrets.create", "secretmanager.secrets.get",
    "secretmanager.secrets.getIamPolicy", "secretmanager.secrets.setIamPolicy", "secretmanager.versions.add",
    "cloudsql.instances.get", "cloudsql.instances.connect", "storage.buckets.get", "storage.buckets.getIamPolicy",
    "storage.buckets.setIamPolicy",
}


def run(command: list[str], *, env: dict | None = None, input_text: str | None = None, timeout: int = 60) -> str:
    try:
        result = subprocess.run(command, input=input_text, text=True, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except (subprocess.SubprocessError, OSError):
        raise media.OperationError("Verification command failed; diagnostics withheld") from None
    return result.stdout


def fingerprints() -> dict:
    source = (Path(__file__).with_name("verify_runtime.py")).read_bytes()
    if not 0 < len(source) <= 32 * 1024:
        raise media.OperationError("Reviewed verification runtime must be at most 32 KiB")
    suite = hashlib.sha256()
    for filename in SUITE_FILES:
        content = Path(__file__).with_name(filename).read_bytes()
        suite.update(("ops/feedback_media/" + filename).encode() + b"\0" + content + b"\0")
    tree = run(["git", "-C", str(ROOT), "rev-parse", "HEAD:frontend"]).strip()
    if not re.fullmatch(r"[0-9a-f]{40}", tree):
        raise media.OperationError("Committed frontend tree is unavailable")
    return {"runtime_source_sha256": hashlib.sha256(source).hexdigest(),
            "verification_suite_sha256": suite.hexdigest(), "frontend_tree": tree}


def current_image(cloud: media.Cloud, service: dict) -> str:
    revision = service.get("latestReadyRevision", "").rsplit("/", 1)[-1]
    traffic = [row for row in service.get("trafficStatuses", []) if row.get("percent", 0)]
    if (not revision or service.get("reconciling") or len(traffic) != 1 or traffic[0].get("percent") != 100
            or traffic[0].get("revision", "").rsplit("/", 1)[-1] != revision
            or any(row.get("tag") for row in service.get("trafficStatuses", []))):
        raise media.OperationError("Production must have one stable revision serving all traffic")
    resolved = cloud.call(f"{REGION}-run", f"apis/serving.knative.dev/v1/namespaces/{PROJECT}/revisions/{revision}")
    image = resolved.get("status", {}).get("imageDigest", "")
    if not IMAGE_PATTERN.fullmatch(image):
        raise media.OperationError("Serving backend image digest is unavailable or outside the approved repository")
    return image


def check_owned(resource: dict | None, kind: str) -> None:
    if resource is not None and resource.get("labels", {}).get("purpose") != PURPOSE:
        raise media.OperationError(f"Existing verification {kind} is not feature-owned")


def secret(cloud: media.Cloud, name: str, *, create_value: str | None = None, deployer: str | None = None) -> tuple[str, str]:
    if name not in {DB_SECRET, KEY_SECRET}:
        raise media.OperationError("Only the two fixed verification secrets are addressable")
    path = f"v1/projects/{PROJECT}/secrets/{name}"
    metadata = cloud.call("secretmanager", path, missing_ok=True)
    check_owned(metadata, "secret")
    if metadata is None:
        if create_value is None:
            raise media.OperationError("Verification secret is absent")
        cloud.call("secretmanager", f"v1/projects/{PROJECT}/secrets?secretId={name}", method="POST",
                   body={"labels": {"purpose": PURPOSE}, "replication": {"automatic": {}}})
    if deployer is not None:
        if create_value is None or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]@earnings-nerd\.iam\.gserviceaccount\.com", deployer):
            raise media.OperationError("Verification secret provisioning identity differs")
        media.bind(cloud, "secretmanager", path, "roles/secretmanager.secretAccessor", "serviceAccount:" + deployer)
    payload = cloud.call("secretmanager", path + "/versions/latest:access", missing_ok=True)
    if payload is None:
        # Recover only an owned secret with no version, never rotate an existing value after an
        # uncertain write. This covers interruption between secret metadata and version creation.
        if create_value is None:
            raise media.OperationError("Verification secret has no accessible version")
        version = cloud.call("secretmanager", path + ":addVersion", method="POST",
                             body={"payload": {"data": base64.b64encode(create_value.encode()).decode()}})
        return create_value, version["name"].rsplit("/", 1)[-1]
    try:
        value = base64.b64decode(payload["payload"]["data"], validate=True).decode()
        version = payload["name"].rsplit("/", 1)[-1]
    except (KeyError, ValueError, UnicodeError):
        raise media.OperationError("Verification secret is unreadable") from None
    if not re.fullmatch(r"[1-9][0-9]*", version):
        raise media.OperationError("Verification secret version is not immutable")
    return value, version


def database_url(password: str) -> str:
    return f"postgresql://{DATABASE}:{password}@/{DATABASE}?host=/cloudsql/{INSTANCE}"


def connection_env(url: str, *, isolated: bool) -> dict:
    parsed = urlsplit(url)
    query = parse_qs(parsed.query)
    database = parsed.path.removeprefix("/")
    if (parsed.scheme not in {"postgresql", "postgres"} or parsed.hostname or parsed.port
            or query != {"host": [f"/cloudsql/{INSTANCE}"]} or not parsed.username or not parsed.password
            or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", database)
            or (isolated and (database != DATABASE or parsed.username != DATABASE))
            or (not isolated and database == DATABASE)):
        raise media.OperationError("SQL connection does not match the fixed verification boundary")
    # The password never reaches GITHUB_ENV, command arguments, logs or the browser process.
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PGHOST": "127.0.0.1", "PGPORT": "15432",
            "PGDATABASE": database, "PGUSER": unquote(parsed.username), "PGPASSWORD": unquote(parsed.password),
            "PGCONNECT_TIMEOUT": "10", "PGOPTIONS": "-c lock_timeout=10s -c statement_timeout=120s"}


class Sql:
    def __init__(self, env: dict):
        self.env = env

    def query(self, statement: str, *, env: dict | None = None) -> str:
        return run(["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"], env=env or self.env,
                   input_text=statement, timeout=150).strip()

    def preflight(self) -> None:
        flags = self.query("SELECT (rolsuper OR (rolcreatedb AND rolcreaterole))::int FROM pg_roles WHERE rolname=current_user;")
        if flags != "1":
            raise media.OperationError("SQL administrator lacks CREATEDB/CREATEROLE; no privileges were widened")
        existing = self.query(f"SELECT count(*) FROM pg_roles WHERE rolname='{DATABASE}';")
        if existing == "1":
            valid = self.query(f"""SELECT (NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
                AND NOT rolreplication AND NOT rolbypassrls AND NOT rolinherit AND rolcanlogin
                AND rolconnlimit=4 AND shobj_description(oid,'pg_authid')='{PURPOSE}'
                AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid))::int
                FROM pg_roles WHERE rolname='{DATABASE}';""")
            if valid != "1":
                raise media.OperationError("Existing verification SQL role differs from the restricted owned role")
        elif existing != "0":
            raise media.OperationError("SQL role inventory is unreadable")
        db = self.query(f"""SELECT CASE WHEN pg_get_userbyid(datdba)=current_user
            AND shobj_description(oid,'pg_database')='{PURPOSE}' THEN 'owned' ELSE 'foreign' END
            FROM pg_database WHERE datname='{DATABASE}';""")
        if db not in {"", "owned"}:
            raise media.OperationError("Existing verification database is not feature-owned")

    def provision(self, password: str, test_env: dict) -> None:
        self.preflight()
        if not re.fullmatch(r"[0-9a-f]{64}", password):
            raise media.OperationError("Verification SQL password is not generated by the fixed derivation")
        if self.query(f"SELECT count(*) FROM pg_roles WHERE rolname='{DATABASE}';") == "0":
            self.query(f"BEGIN; CREATE ROLE {DATABASE} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                       f"NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 4 PASSWORD '{password}'; "
                       f"COMMENT ON ROLE {DATABASE} IS '{PURPOSE}'; COMMIT;")
        if self.query(f"SELECT count(*) FROM pg_database WHERE datname='{DATABASE}';") == "0":
            self.query(f"CREATE DATABASE {DATABASE};")
            self.query(f"COMMENT ON DATABASE {DATABASE} IS '{PURPOSE}';")
        self.query(f"REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC; GRANT CONNECT,TEMPORARY ON DATABASE {DATABASE} TO {DATABASE};")
        admin_test = {**self.env, "PGDATABASE": DATABASE}
        self.query(f"REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE,CREATE ON SCHEMA public TO {DATABASE};", env=admin_test)
        if self.query("SELECT current_database() || ':' || current_user;", env=test_env) != f"{DATABASE}:{DATABASE}":
            raise media.OperationError("Isolated database authentication did not match its fixed role")
        self.audit_production_access()

    def audit_production_access(self) -> None:
        # PUBLIC CONNECT is not a per-role deny. Inspect actual application object privileges;
        # do not edit production ACLs or claim project-wide/other-database isolation.
        count = self.query(f"""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname NOT IN ('pg_catalog','information_schema') AND n.nspname !~ '^pg_toast'
            AND c.relkind IN ('r','p','v','m','S') AND CASE WHEN c.relkind='S'
              THEN has_sequence_privilege('{DATABASE}',c.oid,'USAGE,SELECT,UPDATE')
              ELSE has_table_privilege('{DATABASE}',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') END;""")
        functions = self.query(f"""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog','information_schema')
            AND has_function_privilege('{DATABASE}',p.oid,'EXECUTE');""")
        if count != "0" or functions != "0":
            raise media.OperationError("Verification SQL role can access production application objects; rollout refused")


@contextmanager
def sql_admin(cloud: media.Cloud):
    payload = cloud.call("secretmanager", f"v1/projects/{PROJECT}/secrets/DATABASE_URL/versions/latest:access")
    try:
        url = base64.b64decode(payload["payload"]["data"], validate=True).decode()
    except (KeyError, ValueError, UnicodeError):
        raise media.OperationError("SQL administration credential is unreadable") from None
    env = connection_env(url, isolated=False)
    process = subprocess.Popen([str(ROOT / "cloud-sql-proxy"), "--address", "127.0.0.1", "--port", "15432", INSTANCE],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(30):
            if process.poll() is not None:
                raise media.OperationError("SQL proxy did not remain available")
            check = subprocess.run(["pg_isready", "-h", "127.0.0.1", "-p", "15432"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5, check=False)
            if check.returncode == 0:
                break
            time.sleep(1)
        else:
            raise media.OperationError("SQL proxy readiness deadline exceeded")
        yield Sql(env)
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def preflight_cloud(cloud: media.Cloud) -> None:
    found = cloud.call("cloudresourcemanager", f"v1/projects/{PROJECT}:testIamPermissions", method="POST",
                       body={"permissions": sorted(PROJECT_PERMISSIONS)}).get("permissions", [])
    if not PROJECT_PERMISSIONS.issubset(found):
        missing = sorted(PROJECT_PERMISSIONS - set(found))
        raise media.OperationError("Verification provisioning lacks required IAM permissions: " + ", ".join(missing))


def project_policy(cloud: media.Cloud) -> dict:
    return cloud.call("cloudresourcemanager", f"v1/projects/{PROJECT}:getIamPolicy", method="POST",
                      body={"options": {"requestedPolicyVersion": 3}})


def ensure_identity(cloud: media.Cloud, deployer: str) -> None:
    identity = cloud.call("iam", "v1/" + SA_PATH, missing_ok=True)
    if identity is None:
        cloud.call("iam", f"v1/projects/{PROJECT}/serviceAccounts", method="POST", body={
            "accountId": NAME, "serviceAccount": {"displayName": PURPOSE, "description": PURPOSE}})
    elif identity.get("description") != PURPOSE or identity.get("disabled"):
        raise media.OperationError("Existing verification identity is not the active feature-owned identity")
    policy = project_policy(cloud)
    member = "serviceAccount:" + IDENTITY
    grants = [b for b in policy.get("bindings", []) if member in b.get("members", [])]
    if any(b.get("role") != "roles/cloudsql.client" or b.get("condition") for b in grants):
        raise media.OperationError("Verification identity has unexpected direct project privileges")
    if not grants:
        policy.setdefault("bindings", []).append({"role": "roles/cloudsql.client", "members": [member]})
        cloud.call("cloudresourcemanager", f"v1/projects/{PROJECT}:setIamPolicy", method="POST", body={"policy": policy})
    # IAM serviceAccounts.getIamPolicy uses POST (Cloud Run/Secret Manager use GET).
    sa_policy = cloud.call("iam", "v1/" + SA_PATH + ":getIamPolicy?options.requestedPolicyVersion=3", method="POST", body={})
    media.check_private_policy(sa_policy)
    changed = False
    for role in ("roles/iam.serviceAccountUser", "roles/iam.serviceAccountOpenIdTokenCreator"):
        member = "serviceAccount:" + deployer
        binding = next((row for row in sa_policy.get("bindings", []) if row.get("role") == role and not row.get("condition")), None)
        if binding is None:
            sa_policy.setdefault("bindings", []).append({"role": role, "members": [member]})
            changed = True
        elif member not in binding.get("members", []):
            binding.setdefault("members", []).append(member)
            changed = True
    if changed:
        cloud.call("iam", "v1/" + SA_PATH + ":setIamPolicy", method="POST", body={"policy": sa_policy})
    member = "serviceAccount:" + IDENTITY
    for name in (DB_SECRET, KEY_SECRET):
        media.bind(cloud, "secretmanager", f"v1/projects/{PROJECT}/secrets/{name}", "roles/secretmanager.secretAccessor", member)
        media.bind(cloud, "secretmanager", f"v1/projects/{PROJECT}/secrets/{name}", "roles/secretmanager.secretAccessor", "serviceAccount:" + deployer)
    media.check_role(cloud.call("iam", "v1/" + media.ROLE, missing_ok=True))
    media.check_bucket(cloud.call("storage", "storage/v1/b/" + BUCKET), "preview")
    media.bind(cloud, "storage", "storage/v1/b/" + BUCKET, media.ROLE, member, storage=True)
    media.check_runtime_bucket_policy(cloud.call("storage", media.policy_path("storage/v1/b/" + BUCKET, storage=True)), IDENTITY)


def runtime_env(run_id: str, image: str, hashes: dict, versions: dict, mode: str) -> list[dict]:
    values = {"ENVIRONMENT": "production", "SKIP_REDIS_INIT": "true", "DB_POOL_SIZE": "1" if mode == "cleanup" else "2", "DB_MAX_OVERFLOW": "0",
              "SEC_RATE_LIMIT_PER_SECOND": "1", "EDGAR_RATE_LIMIT_PER_SEC": "1", "FEEDBACK_MEDIA_ENABLED": "true",
              "FEEDBACK_MEDIA_BUCKET": BUCKET, "FEEDBACK_VERIFY_RUN_ID": run_id, "FEEDBACK_VERIFY_MODE": mode,
              "FEEDBACK_VERIFY_IMAGE_DIGEST": image.rsplit("@", 1)[-1], "FEEDBACK_VERIFY_RUNTIME_SHA256": hashes["runtime_source_sha256"],
              "FEEDBACK_VERIFY_SUITE_SHA256": hashes["verification_suite_sha256"], "FEEDBACK_VERIFY_FRONTEND_TREE": hashes["frontend_tree"],
              "COOKIE_SECURE": "true", "COOKIE_SAMESITE": "lax", "COOKIE_DOMAIN": "", "FRONTEND_URL": "https://localhost:8443",
              "CORS_ORIGINS_STR": "https://localhost:8443", "DURABLE_TASKS_ENABLED": "false", "ENABLE_HISTORY_BACKFILL_ON_VISIT": "false",
              "REGISTRATION_MODE": "invite_only", "LEGAL_COLLECTION_ENABLED": "false", "LEGAL_OPERATOR_PUBLISHED": "false"}
    values.update({name: "" for name in ("RESEND_API_KEY", "RESEND_WEBHOOK_SECRET", "POSTHOG_API_KEY", "SENTRY_DSN",
                                        "OPENAI_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET", "STRIPE_PUBLISHABLE_KEY",
                                        "GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "APPLE_CLIENT_ID", "APPLE_PRIVATE_KEY",
                                        "TURNSTILE_SECRET_KEY", "TASKS_WORKER_URL", "TASKS_INVOKER_EMAIL", "INTERNAL_JOB_TOKEN")})
    result = [{"name": name, "value": value} for name, value in sorted(values.items())]
    result.extend({"name": setting, "valueSource": {"secretKeyRef": {"secret": name, "version": versions[name]}}}
                  for setting, name in (("DATABASE_URL", DB_SECRET), ("SECRET_KEY", KEY_SECRET)))
    return result


def runtime_spec(production: dict, run_id: str, image: str, hashes: dict, versions: dict, *, job: bool) -> dict:
    source = Path(__file__).with_name("verify_runtime.py").read_text()
    if hashlib.sha256(source.encode()).hexdigest() != hashes["runtime_source_sha256"] or len(source.encode()) > 32768:
        raise media.OperationError("Verification runtime changed after its fingerprint was recorded")
    container = {"name": "verification", "image": image, "command": ["python"], "args": ["-c", source],
                 "env": runtime_env(run_id, image, hashes, versions, "cleanup" if job else "api"),
                 "volumeMounts": [{"name": "sql", "mountPath": "/cloudsql"}],
                 "resources": {"limits": {"cpu": "1", "memory": "512Mi" if job else "1Gi"}}}
    task = {"serviceAccount": IDENTITY, "timeout": "600s" if job else "60s", "containers": [container],
            "volumes": [{"name": "sql", "cloudSqlInstance": {"instances": [INSTANCE]}}]}
    if production["template"].get("vpcAccess"):
        task["vpcAccess"] = copy.deepcopy(production["template"]["vpcAccess"])
    if job:
        task["maxRetries"] = 1
        return {"name": JOB, "labels": {"purpose": PURPOSE},
                "template": {"taskCount": 1, "parallelism": 1, "template": task}}
    task.update({"maxInstanceRequestConcurrency": 4, "scaling": {"minInstanceCount": 0, "maxInstanceCount": 1}})
    return {"name": SERVICE, "labels": {"purpose": PURPOSE}, "ingress": "INGRESS_TRAFFIC_ALL",
            "invokerIamDisabled": False, "scaling": {"scalingMode": "AUTOMATIC", "minInstanceCount": 0, "maxInstanceCount": 1},
            "template": task}


def assert_private_service(cloud: media.Cloud, service: dict) -> str:
    check_owned(service, "service")
    if (service.get("name") != SERVICE or service.get("invokerIamDisabled")
            or service.get("template", {}).get("serviceAccount") != IDENTITY):
        raise media.OperationError("Verification service identity or IAM check differs")
    policy = cloud.call("run", media.policy_path("v2/" + SERVICE))
    media.check_private_policy(policy)
    origin = service.get("uri", "")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or parsed.path or parsed.query or parsed.fragment or parsed.port
            or not re.fullmatch(r"earningsnerd-feedback-verify-[a-z0-9.-]+\.run\.app", parsed.hostname or "")):
        raise media.OperationError("Verification service origin is outside its fixed Cloud Run identity")
    require_anonymous_denial(origin)
    return origin


def token(cloud: media.Cloud, audience: str) -> str:
    value = cloud.call("iamcredentials", f"v1/projects/-/serviceAccounts/{IDENTITY}:generateIdToken", method="POST",
                       body={"audience": audience, "includeEmail": True}).get("token")
    if not isinstance(value, str) or len(value) > 16384 or value.count(".") != 2:
        raise media.OperationError("Verification audience-bound identity token is unavailable")
    return value


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise media.OperationError("Verification control endpoint redirected")


def require_anonymous_denial(origin: str) -> None:
    # A direct service policy does not expose inherited public invoker grants. /health is public
    # inside the unchanged application, so only a gateway denial establishes effective privacy.
    try:
        with build_opener(NoRedirect).open(Request(origin + "/health"), timeout=20):
            pass
    except HTTPError as exc:
        if exc.code == 403:
            return
    except (URLError, TimeoutError):
        pass
    raise media.OperationError("Verification endpoint must reject anonymous health reads with HTTP 403")


def control(cloud: media.Cloud, origin: str, key: str, run_id: str, path: str, payload: dict | None = None) -> dict:
    authentication = hmac.new(key.encode(), CONTROL_DOMAIN + run_id.encode(), hashlib.sha256).hexdigest()
    request = Request(origin + "/__feedback_verify/" + path,
                      data=None if payload is None else json.dumps(payload).encode(),
                      headers={"Authorization": "Bearer " + token(cloud, origin), "Content-Type": "application/json",
                               "X-Feedback-Verify-Control": authentication, "X-Feedback-Verify-Run": run_id})
    try:
        with build_opener(NoRedirect).open(request, timeout=60) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            raise ValueError("oversize")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise TypeError("shape")
        return result
    except (HTTPError, URLError, TimeoutError, ValueError, TypeError):
        raise media.OperationError("Private verification control request failed; response withheld") from None


def verify_receipt(receipt: dict, key: str, run_id: str, image: str, hashes: dict) -> None:
    payload, signature = receipt.get("payload"), receipt.get("signature")
    if not isinstance(payload, dict) or not isinstance(signature, str):
        raise media.OperationError("Verification receipt is absent or malformed")
    expected = hmac.new(key.encode(), RECEIPT_DOMAIN + json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise media.OperationError("Verification receipt signature is invalid")
    fixed = {"schema": 1, "purpose": PURPOSE, "run_id": run_id, "image_digest": image.rsplit("@", 1)[-1], **hashes,
             "browser_assertions": ASSERTIONS}
    assertions = payload.get("browser_assertions")
    if (type(payload.get("schema")) is not int or not isinstance(assertions, dict)
            or set(assertions) != set(ASSERTIONS) or any(value is not True for value in assertions.values())
            or any(payload.get(name) != value for name, value in fixed.items())):
        raise media.OperationError("Verification receipt does not bind the current image, sources and acceptance checks")
    try:
        age = datetime.now(UTC) - datetime.fromisoformat(payload["completed_at"])
    except (KeyError, ValueError, TypeError):
        raise media.OperationError("Verification receipt completion time is unreadable") from None
    if not timedelta(0) <= age <= timedelta(hours=2):
        raise media.OperationError("Verification receipt is not from the last two hours")


def counts_only_receipt(receipt: dict) -> bool:
    """Allow exactly the signed synthetic evidence schema; never arbitrary runtime strings."""
    if (set(receipt) != {"payload", "signature"} or not isinstance(receipt.get("signature"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", receipt["signature"])):
        return False
    payload = receipt.get("payload")
    if not isinstance(payload, dict) or set(payload) != {
            "schema", "purpose", "run_id", "completed_at", "image_digest", "runtime_source_sha256",
            "verification_suite_sha256", "frontend_tree", "browser_assertions", "observed"}:
        return False
    observed = payload.get("observed")
    if not isinstance(observed, dict) or set(observed) != {"database", "notifications", "resources", "cleanup"}:
        return False
    def numbers(value, keys, *, nullable=()):
        return isinstance(value, dict) and set(value) == set(keys) and all(
            (item is None and name in nullable) or (type(item) is int and 0 <= item <= 2**63 - 1)
            for name, item in value.items())
    database = observed["database"]
    database_numbers = {"feedback", "submitted", "attachments", "fixture_users", "available", "deleted", "pending",
                        "published_attachments", "confirmed_generation_deletions"}
    if (not isinstance(database, dict) or set(database) != database_numbers | {"normalized_metadata_valid"}
            or type(database["normalized_metadata_valid"]) is not bool
            or not numbers({name: database[name] for name in database_numbers}, database_numbers)):
        return False
    mail = observed["notifications"]
    if (not isinstance(mail, dict) or set(mail) != {"accepted", "rejected", "attachment_counts", "admin_link_valid", "no_image_payload"}
            or not numbers({name: mail[name] for name in ("accepted", "rejected")}, {"accepted", "rejected"})
            or type(mail["admin_link_valid"]) is not bool or type(mail["no_image_payload"]) is not bool
            or not isinstance(mail["attachment_counts"], list) or len(mail["attachment_counts"]) > 30
            or any(type(value) is not int or not 0 <= value <= 3 for value in mail["attachment_counts"])):
        return False
    resources = observed["resources"]
    numeric = {"sample_count", "rss_peak_bytes", "cgroup_sample_peak_bytes", "cgroup_kernel_peak_bytes",
               "cgroup_memory_limit_bytes", "configured_memory_limit_bytes", "self_high_water_rss_bytes",
               "reaped_child_high_water_rss_bytes", "last_process_count", "conservative_process_bound_bytes"}
    if (not isinstance(resources, dict) or set(resources) != numeric | {"method", "worker_limits", "unexplained_children", "acceptance_passed", "sample_age_seconds", "evidence_basis"}
            or not numbers({name: resources[name] for name in numeric}, numeric,
                           nullable={"cgroup_sample_peak_bytes", "cgroup_kernel_peak_bytes", "cgroup_memory_limit_bytes"})
            or resources["method"] != "kernel peak when exposed; otherwise conservative process bound plus sampled cgroup; representative workload only"
            or resources["evidence_basis"] not in {"kernel cgroup high-water peak", "kernel peak unavailable; conservative process-bound evidence"}
            or resources["worker_limits"] != {"feedback_image_service": 1, "feedback_storage_worker_service": 2}
            or type(resources["sample_age_seconds"]) not in {float, int} or not math.isfinite(resources["sample_age_seconds"])
            or not 0 <= resources["sample_age_seconds"] <= 7200
            or type(resources["unexplained_children"]) is not bool or type(resources["acceptance_passed"]) is not bool):
        return False
    cleanup = observed["cleanup"]
    return (isinstance(cleanup, dict) and cleanup.get("dry_run") is False and set(cleanup) == {
        "dry_run", "eligible", "deleted", "errors", "overdue", "pending_verification"}
        and numbers({name: value for name, value in cleanup.items() if name != "dry_run"},
                    {"eligible", "deleted", "errors", "overdue", "pending_verification"}))


def screenshot_bytes(path: Path) -> bytes:
    data = path.read_bytes()
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 8 * 1024 * 1024:
        raise media.OperationError("Verification screenshot is not a bounded PNG")
    position, kinds = 8, []
    while position < len(data):
        if position + 12 > len(data):
            raise media.OperationError("Verification PNG is incomplete")
        length = struct.unpack_from(">I", data, position)[0]
        kind = data[position + 4:position + 8]
        end = position + 12 + length
        if kind not in {b"IHDR", b"IDAT", b"IEND", b"sRGB", b"gAMA", b"pHYs", b"cHRM"} or end > len(data):
            raise media.OperationError("Verification PNG has unexpected metadata or chunks")
        expected_crc = struct.unpack_from(">I", data, end - 4)[0]
        if zlib.crc32(data[position + 4:end - 4]) != expected_crc:
            raise media.OperationError("Verification PNG checksum differs")
        if kind == b"IHDR":
            if kinds or length != 13:
                raise media.OperationError("Verification PNG header differs")
            width, height = struct.unpack_from(">II", data, position + 8)
            if not 0 < width <= 4096 or not 0 < height <= 20000:
                raise media.OperationError("Verification PNG dimensions exceed the evidence bound")
        if kind == b"IEND" and (length or end != len(data)):
            raise media.OperationError("Verification PNG has trailing content")
        kinds.append(kind)
        position = end
    if not kinds or kinds[0] != b"IHDR" or kinds[-1] != b"IEND" or b"IDAT" not in kinds:
        raise media.OperationError("Verification PNG is incomplete")
    return data


def retain_artifacts(directory: Path, key: str, run_id: str, image: str, hashes: dict) -> None:
    if not directory.exists():
        return
    if directory.is_symlink() or not directory.is_dir():
        raise media.OperationError("Verification output directory is not a regular directory")
    files, total, approved = list(directory.iterdir()), 0, {}
    if len(files) > len(SCREENSHOTS) + 1:
        raise media.OperationError("Verification evidence exceeds its file count")
    for path in files:
        mode = path.lstat()
        if not stat.S_ISREG(mode.st_mode) or mode.st_nlink != 1 or path.name not in SCREENSHOTS | {"receipt.json"}:
            raise media.OperationError("Verification evidence includes an unapproved file")
        total += mode.st_size
        if total > 64 * 1024 * 1024 or mode.st_size > (128 * 1024 if path.name == "receipt.json" else 8 * 1024 * 1024):
            raise media.OperationError("Verification evidence exceeds its size limit")
        if path.name == "receipt.json":
            try:
                receipt = json.loads(path.read_text())
            except (ValueError, UnicodeError):
                raise media.OperationError("Verification artifact receipt is unreadable") from None
            if not isinstance(receipt, dict) or not counts_only_receipt(receipt):
                raise media.OperationError("Verification artifact receipt contains unsupported data")
            verify_receipt(receipt, key, run_id, image, hashes)
            approved[path.name] = (json.dumps(receipt, sort_keys=True) + "\n").encode()
        else:
            approved[path.name] = screenshot_bytes(path)
    target = ROOT / "verification-output"
    if target.exists():
        raise media.OperationError("Verification artifact destination must be new")
    target.mkdir(mode=0o700)
    for name, content in approved.items():
        (target / name).write_bytes(content)
        (target / name).chmod(0o600)


def require_receipt(cloud: media.Cloud, production: dict) -> dict:
    image, hashes = current_image(cloud, production), fingerprints()
    service = cloud.call("run", "v2/" + SERVICE)
    origin = assert_private_service(cloud, service)
    containers = service.get("template", {}).get("containers", [])
    if len(containers) != 1:
        raise media.OperationError("Verification service container contract differs")
    env = {item["name"]: item for item in containers[0].get("env", [])}
    run_id = env.get("FEEDBACK_VERIFY_RUN_ID", {}).get("value", "")
    if not RUN_PATTERN.fullmatch(run_id):
        raise media.OperationError("Verification run marker is invalid")
    key, key_version = secret(cloud, KEY_SECRET)
    _, db_version = secret(cloud, DB_SECRET)
    expected = runtime_spec(production, run_id, image, hashes, {KEY_SECRET: key_version, DB_SECRET: db_version}, job=False)
    # Compare only requested fields, allowing documented server-added output fields.
    if not contains_spec(service, expected):
        raise media.OperationError("Verification service no longer matches the reviewed isolated runtime")
    if current_image(cloud, service) != image:
        raise media.OperationError("Verification service is not serving the current backend digest")
    receipt = control(cloud, origin, key, run_id, "receipt").get("receipt")
    if not isinstance(receipt, dict):
        raise media.OperationError("A completed live verification receipt is required")
    verify_receipt(receipt, key, run_id, image, hashes)
    print("Live isolated feedback verification receipt: current image and sources verified")
    return receipt


def contains_spec(actual, expected) -> bool:
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return False
        if "name" in expected and ("value" in expected or "valueSource" in expected) and set(actual) - set(expected):
            return False  # An unexpected secret reference must never masquerade as an omitted empty env value.
        if set(expected) == {"cpu", "memory"} and set(actual) != set(expected):
            return False  # Additional accelerators are not server-added resource defaults.
        defaults = {"invokerIamDisabled": False, "minInstanceCount": 0, "value": ""}
        return all((key in actual and contains_spec(actual[key], value))
                   or (key not in actual and key in defaults and value == defaults[key]) for key, value in expected.items())
    if isinstance(expected, list):
        return isinstance(actual, list) and len(actual) == len(expected) and all(contains_spec(a, b) for a, b in zip(actual, expected))
    return actual == expected


def seed_marker(sql: Sql, env: dict, run_id: str, image: str, hashes: dict) -> None:
    # Every interpolation below is a fixed identifier or a validated generated hex/run marker.
    if not RUN_PATTERN.fullmatch(run_id) or not IMAGE_PATTERN.fullmatch(image):
        raise media.OperationError("Verification marker identity is invalid")
    if (any(not re.fullmatch(r"[0-9a-f]{64}", hashes[key]) for key in ("runtime_source_sha256", "verification_suite_sha256"))
            or not re.fullmatch(r"[0-9a-f]{40}", hashes["frontend_tree"])):
        raise media.OperationError("Verification source fingerprints are invalid")
    sql.query(f"""CREATE TABLE IF NOT EXISTS {MARKER} (
        run_id TEXT PRIMARY KEY, purpose TEXT NOT NULL CHECK(purpose='{PURPOSE}'),
        created_at TIMESTAMPTZ NOT NULL DEFAULT now(), expires_at TIMESTAMPTZ NOT NULL DEFAULT now()+interval '2 hours',
        image_digest TEXT NOT NULL, runtime_source_sha256 TEXT NOT NULL, verification_suite_sha256 TEXT NOT NULL,
        frontend_tree TEXT NOT NULL, fixtures JSONB NOT NULL DEFAULT '{{}}', receipt JSONB, completed_at TIMESTAMPTZ);
        INSERT INTO {MARKER}(run_id,purpose,image_digest,runtime_source_sha256,verification_suite_sha256,frontend_tree)
        VALUES ('{run_id}','{PURPOSE}','{image.rsplit('@', 1)[-1]}','{hashes['runtime_source_sha256']}',
          '{hashes['verification_suite_sha256']}','{hashes['frontend_tree']}');""", env=env)


def execute_cleanup(cloud: media.Cloud, *, initialize: bool = False) -> None:
    # Only this protected, explicit execution may finalize an active run. The persistent hourly
    # job remains in expiry-only cleanup mode and cannot erase fixtures under a running browser.
    body = {"overrides": {"containerOverrides": [{"name": "verification", "env": [
        {"name": "FEEDBACK_VERIFY_MODE", "value": "initialize" if initialize else "cleanup_now"}]}]}}
    execution = cloud.wait(cloud.call("run", "v2/" + JOB + ":run", method="POST", body=body))
    if (execution.get("succeededCount") != 1 or execution.get("failedCount", 0)
            or execution.get("cancelledCount", 0) or execution.get("taskCount") != 1):
        raise media.OperationError("Verification initialization/cleanup did not complete successfully")


def settle_previous_run(cloud: media.Cloud, sql: Sql, test_env: dict, production: dict) -> None:
    previous = cloud.call("run", "v2/" + JOB, missing_ok=True)
    if previous is None:
        return
    check_owned(previous, "cleanup job")
    task = previous.get("template", {}).get("template", {})
    containers = task.get("containers", [])
    if task.get("serviceAccount") != IDENTITY or len(containers) != 1:
        raise media.OperationError("Previous verification cleanup authority differs")
    container = containers[0]
    env = {row.get("name"): row for row in container.get("env", [])}
    previous_run = env.get("FEEDBACK_VERIFY_RUN_ID", {}).get("value", "")
    if (container.get("command") != ["python"] or not IMAGE_PATTERN.fullmatch(container.get("image", ""))
            or container.get("args") != ["-c", Path(__file__).with_name("verify_runtime.py").read_text()]
            or env.get("FEEDBACK_MEDIA_BUCKET", {}).get("value") != BUCKET
            or env.get("FEEDBACK_VERIFY_MODE", {}).get("value") != "cleanup"
            or not RUN_PATTERN.fullmatch(previous_run)
            or {name for name, row in env.items() if "valueSource" in row} != {"DATABASE_URL", "SECRET_KEY"}
            or env["DATABASE_URL"].get("valueSource", {}).get("secretKeyRef", {}).get("secret") != DB_SECRET
            or env["SECRET_KEY"].get("valueSource", {}).get("secretKeyRef", {}).get("secret") != KEY_SECRET):
        raise media.OperationError("Previous cleanup differs; inspect its retained manifest before retrying")
    hashes = {field: env.get(variable, {}).get("value", "") for field, variable in (
        ("runtime_source_sha256", "FEEDBACK_VERIFY_RUNTIME_SHA256"), ("verification_suite_sha256", "FEEDBACK_VERIFY_SUITE_SHA256"),
        ("frontend_tree", "FEEDBACK_VERIFY_FRONTEND_TREE"))}
    versions = {name: env[setting]["valueSource"]["secretKeyRef"].get("version", "")
                for setting, name in (("DATABASE_URL", DB_SECRET), ("SECRET_KEY", KEY_SECRET))}
    if (any(not re.fullmatch(r"[1-9][0-9]*", value) for value in versions.values())
            or any(not re.fullmatch(r"[0-9a-f]{40}" if field == "frontend_tree" else r"[0-9a-f]{64}", value)
                   for field, value in hashes.items())
            or not contains_spec(previous, runtime_spec(production, previous_run, container["image"], hashes, versions, job=True))):
        raise media.OperationError("Previous cleanup differs from the bounded isolated contract")
    expired = sql.query(f"SELECT (expires_at<=CURRENT_TIMESTAMP)::int FROM {MARKER} WHERE run_id='{previous_run}';", env=test_env)
    if expired != "1":
        raise media.OperationError("Previous verification lease is still active or unreadable; inspect and wait for expiry before a new apply")
    execute_cleanup(cloud)  # Keep the old run marker until all its durable objects have settled.


def ensure_job(cloud: media.Cloud, spec: dict) -> None:
    current = cloud.call("run", "v2/" + JOB, missing_ok=True)
    check_owned(current, "cleanup job")
    if current:
        cloud.wait(cloud.call("run", "v2/" + JOB, method="PATCH", body={**spec, "etag": current["etag"]}))
    else:
        cloud.wait(cloud.call("run", f"v2/{media.PARENT}/jobs?jobId={NAME}-cleanup", method="POST", body=spec))
    media.bind(cloud, "run", "v2/" + JOB, "roles/run.invoker", "serviceAccount:" + IDENTITY)
    schedule = {"name": SCHEDULE, "description": PURPOSE, "schedule": "41 * * * *", "timeZone": "Etc/UTC",
                "attemptDeadline": "60s", "retryConfig": {"retryCount": 0}, "httpTarget": {
                    "uri": f"https://run.googleapis.com/v2/{JOB}:run", "httpMethod": "POST", "body": "e30=",
                    "headers": {"Content-Type": "application/json"},
                    "oauthToken": {"serviceAccountEmail": IDENTITY, "scope": "https://www.googleapis.com/auth/cloud-platform"}}}
    current = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True)
    if current is not None and current.get("description") != PURPOSE:
        raise media.OperationError("Existing verification cleanup schedule is not feature-owned")
    cloud.call("cloudscheduler", f"v1/{SCHEDULE}?updateMask=schedule,timeZone,attemptDeadline,retryConfig,httpTarget" if current else f"v1/{media.PARENT}/jobs",
               method="PATCH" if current else "POST", body=schedule)


def browser(cloud: media.Cloud, origin: str, key: str, run_id: str, image: str, hashes: dict) -> None:
    with tempfile.TemporaryDirectory(prefix="feedback-verify-") as directory:
        folder = Path(directory)
        os.chmod(folder, 0o700)
        def private(name: str, value: str) -> str:
            path = folder / name
            path.write_text(value)
            path.chmod(0o600)
            return str(path)
        identity_file = private("identity.jwt", token(cloud, origin))
        control_file = private("control.txt", hmac.new(key.encode(), CONTROL_DOMAIN + run_id.encode(), hashlib.sha256).hexdigest())
        cert_file, key_file = str(folder / "localhost.crt"), str(folder / "localhost.key")
        run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1", "-subj", "/CN=localhost",
             "-addext", "subjectAltName=DNS:localhost", "-keyout", key_file, "-out", cert_file])
        Path(key_file).chmod(0o600)
        Path(cert_file).chmod(0o600)
        manifest = {"version": 1, "run_id": run_id, "service_origin": origin, "service_audience": origin,
                    "expected_project": PROJECT, "expected_service": NAME, "image_digest": image.rsplit("@", 1)[-1], **hashes,
                    "id_token_file": identity_file, "control_token_file": control_file, "cert_file": cert_file,
                    "key_file": key_file, "output_dir": str(folder / "output")}
        manifest_path = private("manifest.json", json.dumps(manifest))
        # Deliberately do not inherit cloud/admin credentials or DATABASE_URL into Next/Playwright.
        environment = {name: os.environ[name] for name in (
            "PATH", "HOME", "TMPDIR", "PLAYWRIGHT_BROWSERS_PATH", "GITHUB_ACTIONS", "GITHUB_WORKFLOW",
            "GITHUB_EVENT_NAME", "GITHUB_REF", "GITHUB_RUN_ATTEMPT", "GITHUB_RUN_ID",
        ) if name in os.environ}
        environment.update({"NODE_ENV": "production", "NEXT_PUBLIC_API_BASE_URL": "https://localhost:8443"})
        try:
            output = run(["node", str(Path(__file__).with_name("live_runner.mjs")), "--manifest", manifest_path,
                          "--frontend", str(ROOT / "frontend")], env=environment, timeout=900)
        finally:
            retain_artifacts(folder / "output", key, run_id, image, hashes)
        try:
            result = json.loads(output)
        except ValueError:
            raise media.OperationError("Browser verification did not return its counts-only completion") from None
        if (not isinstance(result, dict) or set(result) != {"status", "checks", "feedback", "deleted_attachments"} or result.get("status") != "passed"
                or result.get("checks") != 11 or any(type(result.get(name)) is not int or result[name] < 0
                                                      for name in ("feedback", "deleted_attachments"))):
            raise media.OperationError("Live browser verification did not pass")
        print("Live browser verification: passed; private state and credentials removed")


def provision(cloud: media.Cloud) -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "") + "-" + os.environ.get("GITHUB_RUN_ATTEMPT", "")
    deployer = os.environ.get("FEEDBACK_VERIFY_DEPLOYER", "")
    if not RUN_PATTERN.fullmatch(run_id) or not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]@earnings-nerd\.iam\.gserviceaccount\.com", deployer):
        raise media.OperationError("Verification apply requires a first-attempt GitHub run and the configured project deployer")
    production = cloud.call("run", "v2/" + media.SERVICE)
    image, hashes = current_image(cloud, production), fingerprints()
    preflight_cloud(cloud)
    with sql_admin(cloud) as sql:
        sql.preflight()  # no creation until actual SQL capabilities are established
        key, key_version = secret(cloud, KEY_SECRET, create_value=secrets.token_urlsafe(48), deployer=deployer)
        if len(key) < 32:
            raise media.OperationError("Verification signing key does not meet its minimum length")
        password = hmac.new(key.encode(), b"feedback-media-verification-database-v1", hashlib.sha256).hexdigest()
        url, db_version = secret(cloud, DB_SECRET, create_value=database_url(password), deployer=deployer)
        if url != database_url(password):
            raise media.OperationError("Existing verification database credential differs from its fixed derived connection")
        test_env = connection_env(url, isolated=True)
        sql.provision(password, test_env)
        ensure_identity(cloud, deployer)
        versions = {KEY_SECRET: key_version, DB_SECRET: db_version}
        settle_previous_run(cloud, sql, test_env, production)
        seed_marker(sql, test_env, run_id, image, hashes)
        ensure_job(cloud, runtime_spec(production, run_id, image, hashes, versions, job=True))
        execute_cleanup(cloud, initialize=True)
        migration_output = run(["bash", str(ROOT / "backend/scripts/apply_migrations.sh")], env=test_env, timeout=900)
        summaries = re.findall(r"^apply_migrations: applied=\d+ skipped=\d+$", migration_output, re.MULTILINE)
        if len(summaries) != 1:
            raise media.OperationError("Isolated migration runner did not produce its completion receipt")
        print("Isolated verification database: " + summaries[0])
        spec = runtime_spec(production, run_id, image, hashes, versions, job=False)
        current = cloud.call("run", "v2/" + SERVICE, missing_ok=True)
        check_owned(current, "service")
        if current:
            cloud.wait(cloud.call("run", "v2/" + SERVICE + "?updateMask=template,ingress,invokerIamDisabled,scaling", method="PATCH",
                                  body={**spec, "etag": current["etag"]}))
        else:
            cloud.wait(cloud.call("run", f"v2/{media.PARENT}/services?serviceId={NAME}", method="POST", body=spec))
        media.bind(cloud, "run", "v2/" + SERVICE, "roles/run.invoker", "serviceAccount:" + IDENTITY)
        origin = assert_private_service(cloud, cloud.call("run", "v2/" + SERVICE))
        try:
            browser(cloud, origin, key, run_id, image, hashes)
        finally:
            # A failed browser must leave a runnable cleanup path and durable manifests. This
            # bounded attempt supplements the retained hourly job; it never drops either one.
            execute_cleanup(cloud)
        require_receipt(cloud, production)
    print("Isolated live verification completed; production uploads remain unchanged")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("feedback-media-verify-inspect", "feedback-media-verify-apply"))
    operation = parser.parse_args().operation
    cloud = media.Cloud()
    if operation == "feedback-media-verify-apply":
        provision(cloud)
    else:
        require_receipt(cloud, cloud.call("run", "v2/" + media.SERVICE))


if __name__ == "__main__":
    try:
        main()
    except (media.OperationError, OSError) as exc:
        raise SystemExit(str(exc) if isinstance(exc, media.OperationError) else "Verification input is unavailable") from None
