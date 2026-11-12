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
from http.client import HTTPException
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
# Cloud Run refuses a create whose Cloud SQL volume has any other name, and reserves this name for one: "Cloud SQL
# volume must be named 'cloudsql', and 'cloudsql' is reserved for Cloud SQL volumes" (the first live verify-apply).
SQL_VOLUME = "cloudsql"
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
# Project permissions every run uses. The identity, grant and secret writes, and the Cloud Run and Scheduler creates and
# updates, depend on what exists, so bootstrap_gaps tests each only when this run will make it: a founder-made identity, grant or secret in
# the approved shape needs no create or setIamPolicy permission, and resourcemanager.projects.setIamPolicy (owner
# equivalent) is never needed once the verifier's one Cloud SQL client grant exists.
PROJECT_PERMISSIONS = {
    "iam.serviceAccounts.get", "iam.serviceAccounts.getIamPolicy", "resourcemanager.projects.getIamPolicy",
    "run.services.get", "run.services.getIamPolicy", "run.jobs.get", "run.jobs.run", "run.jobs.runWithOverrides",
    "run.jobs.getIamPolicy", "cloudscheduler.jobs.get", "secretmanager.secrets.get", "secretmanager.secrets.getIamPolicy",
    "secretmanager.versions.get", "cloudsql.instances.get", "cloudsql.instances.connect", "storage.buckets.get",
    "storage.buckets.getIamPolicy",
    # Read before or between the writes: the object role, every Cloud Run operation poll, the serving revision.
    "iam.roles.get", "run.operations.get", "run.revisions.get",
}
CONDITIONAL_PERMISSIONS = {
    "iam.serviceAccounts.create", "iam.serviceAccounts.setIamPolicy", "resourcemanager.projects.setIamPolicy",
    "secretmanager.secrets.create", "secretmanager.secrets.setIamPolicy", "secretmanager.versions.add",
    "storage.buckets.setIamPolicy", "run.jobs.create", "run.jobs.update", "run.jobs.setIamPolicy",
    "run.services.create", "run.services.update", "run.services.setIamPolicy",
    "cloudscheduler.jobs.create", "cloudscheduler.jobs.update",
}
SA_ROLES = ("roles/iam.serviceAccountUser", "roles/iam.serviceAccountOpenIdTokenCreator")
ACCESSOR, VERSION_ADDER = "roles/secretmanager.secretAccessor", "roles/secretmanager.secretVersionAdder"
DEPLOYER_PATTERN = re.compile(r"[a-z][a-z0-9-]{4,28}[a-z0-9]@earnings-nerd\.iam\.gserviceaccount\.com")
# The isolated role's cap covers the service's pool (2), the cleanup job's pool (1) and one serial psql or
# migration connection. Admission on the shared production instance reuses the summary rehearsal's rule
# (ops/summary_delivery/database.py): active client backends, this cap and the reserve stay within 70% of usable.
CONNECTION_LIMIT = 4
OPERATIONAL_RESERVE = 5


class CommandFailed(media.OperationError):
    """A command that exited non-zero; its standard output is kept for a caller that reads only closed codes from it."""

    def __init__(self, output: str) -> None:
        super().__init__("Verification command failed; diagnostics withheld")
        self.output = output


def run(command: list[str], *, env: dict | None = None, input_text: str | None = None, timeout: int = 60) -> str:
    try:
        result = subprocess.run(command, input=input_text, text=True, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, timeout=timeout, check=True)
    except subprocess.CalledProcessError as failed:
        raise CommandFailed(failed.stdout if isinstance(failed.stdout, str) else "") from None
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
    labels = resource.get("labels") if resource is not None else None
    if resource is not None and (not isinstance(labels, dict) or labels.get("purpose") != PURPOSE):
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
        if create_value is None or not DEPLOYER_PATTERN.fullmatch(deployer):
            raise media.OperationError("Verification secret provisioning identity differs")
        media.bind(cloud, "secretmanager", path, ACCESSOR, "serviceAccount:" + deployer)
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
                AND rolconnlimit={CONNECTION_LIMIT} AND shobj_description(oid,'pg_authid')='{PURPOSE}'
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

    def admit(self) -> None:
        """Refuse before any write unless the shared production instance has room for the capped verifier.

        A point-in-time admission, not a reservation. The administrator's own query is not counted: it is the
        one serial psql connection the verifier's cap already holds, and counting it again refused a quiet
        production (7 counted, live run 43094001737). A role without pg_read_all_stats sees another role's
        session with backend_type NULL, so a hidden session attached to a database counts as a client backend
        too (it may overcount a background worker, never undercount a session). Only counts are printed.
        """
        answer = self.query("""SELECT current_setting('max_connections') || '|' ||
            current_setting('superuser_reserved_connections') || '|' ||
            COALESCE(current_setting('reserved_connections',true),'0') || '|' ||
            (SELECT count(*) FROM pg_stat_activity
             WHERE (backend_type='client backend' OR (backend_type IS NULL AND datid IS NOT NULL))
               AND pid <> pg_backend_pid());""")
        if not re.fullmatch(r"[0-9]{1,7}(\|[0-9]{1,7}){3}", answer):
            raise media.OperationError("Production SQL headroom is unreadable; nothing was created")
        maximum, superuser_reserved, reserved, active = map(int, answer.split("|"))
        usable = maximum - superuser_reserved - reserved
        admitted = usable > 0 and (active + CONNECTION_LIMIT + OPERATIONAL_RESERVE) * 10 <= usable * 7
        print(f"Production SQL admission: {active} client backends of {usable} usable; verifier cap {CONNECTION_LIMIT}, "
              f"reserve {OPERATIONAL_RESERVE}, threshold 70%: " + ("admitted" if admitted else "refused"))
        if not admitted:
            raise media.OperationError("Production SQL headroom is insufficient for the isolated verifier; nothing was created")

    def provision(self, password: str, test_env: dict) -> None:
        self.preflight()
        if not re.fullmatch(r"[0-9a-f]{64}", password):
            raise media.OperationError("Verification SQL password is not generated by the fixed derivation")
        if self.query(f"SELECT count(*) FROM pg_roles WHERE rolname='{DATABASE}';") == "0":
            self.query(f"BEGIN; CREATE ROLE {DATABASE} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                       f"NOREPLICATION NOBYPASSRLS CONNECTION LIMIT {CONNECTION_LIMIT} PASSWORD '{password}'; "
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


def preflight_gaps(cloud: media.Cloud) -> list[str]:
    """What every verify-apply run needs and the identity lacks: its project permissions and the image read."""
    # A malformed answer grants nothing (media.held).
    missing = sorted(PROJECT_PERMISSIONS - media.held(cloud, "cloudresourcemanager", f"v1/projects/{PROJECT}",
                                                      sorted(PROJECT_PERMISSIONS)))
    # The service and job it deploys run the serving image, which IMAGE_PATTERN holds to media.IMAGE_REPOSITORY.
    if media.IMAGE_READ not in media.held(cloud, "artifactregistry", "v1/" + media.IMAGE_REPOSITORY, [media.IMAGE_READ]):
        missing.append(media.IMAGE_READ + " on the API image repository")
    return missing


def preflight_cloud(cloud: media.Cloud) -> None:
    missing = preflight_gaps(cloud)
    if missing:
        raise media.OperationError("Verification provisioning lacks required IAM permissions: " + ", ".join(missing))


def check_grants(policy: dict, approved: dict[str, set[str]], kind: str) -> None:
    """Refuse a malformed or etag-less policy, a public principal, a conditional grant, or any role or member beyond the
    approved bootstrap shape."""
    media.check_private_policy(policy)
    media.policy_etag(policy)
    if any(binding.get("condition") or not set(binding.get("members", [])) <= approved.get(binding["role"], set())
           for binding in media.policy_bindings(policy)):
        raise media.OperationError(f"Existing verification {kind} grants differ from the approved bootstrap")


def bootstrap_gaps(cloud: media.Cloud, deployer: str) -> list[str]:
    """Read-only, before the first write: refuse a pre-existing identity, grant or secret in another shape, and
    return the permissions this run lacks for the writes the state it read still needs.

    Only a read that finds a resource absent (404) plans its create; a denied read stops here, and a malformed
    answer or drift is refused, so neither is planned as absent or as already approved. A write the founder
    already made by hand in the approved shape is not tested. Two prerequisites held on one resource are tested on
    it: actAs and getOpenIdToken on the identity, once the deployer's grants on it exist, and versions.add on a secret
    with no version yet. The deployer's accessor grant on each secret is read as a binding.
    """
    member, runner = "serviceAccount:" + IDENTITY, "serviceAccount:" + deployer
    needed: set[str] = set()
    resource_gaps: list[str] = []
    identity = cloud.call("iam", "v1/" + SA_PATH, missing_ok=True)
    if identity is None:
        needed |= {"iam.serviceAccounts.create", "iam.serviceAccounts.setIamPolicy"}
    else:
        if identity.get("description") != PURPOSE or identity.get("disabled"):
            raise media.OperationError("Existing verification identity is not the active feature-owned identity")
        sa_policy = cloud.call("iam", "v1/" + SA_PATH + ":getIamPolicy?options.requestedPolicyVersion=3", method="POST", body={})
        check_grants(sa_policy, {role: {runner} for role in SA_ROLES}, "identity")
        if not all(media.bound(sa_policy, role, runner) for role in SA_ROLES):
            needed.add("iam.serviceAccounts.setIamPolicy")
        elif media.held(cloud, "iam", f"v1/projects/-/serviceAccounts/{IDENTITY}",
                        [media.ACT_AS, "iam.serviceAccounts.getOpenIdToken"]) != {media.ACT_AS, "iam.serviceAccounts.getOpenIdToken"}:
            resource_gaps.append("actAs and getOpenIdToken on the verification identity")
    policy = project_policy(cloud)
    media.policy_etag(policy)
    grants = [binding for binding in media.policy_bindings(policy) if member in binding.get("members", [])]
    if any(binding.get("role") != "roles/cloudsql.client" or binding.get("condition") for binding in grants):
        raise media.OperationError("Verification identity has unexpected direct project privileges")
    if not grants:
        needed.add("resourcemanager.projects.setIamPolicy")
    for name in (DB_SECRET, KEY_SECRET):
        path = f"v1/projects/{PROJECT}/secrets/{name}"
        metadata = cloud.call("secretmanager", path, missing_ok=True)
        check_owned(metadata, "secret")
        if metadata is None:
            needed |= {"secretmanager.secrets.create", "secretmanager.secrets.setIamPolicy", "secretmanager.versions.add"}
            continue
        policy = cloud.call("secretmanager", media.policy_path(path))
        check_grants(policy, {ACCESSOR: {runner, member}, VERSION_ADDER: {runner}}, "secret")
        if not (media.bound(policy, ACCESSOR, runner) and media.bound(policy, ACCESSOR, member)):
            needed.add("secretmanager.secrets.setIamPolicy")
        version = cloud.call("secretmanager", path + "/versions/latest", missing_ok=True)
        if version is None:
            if "secretmanager.versions.add" not in media.held(cloud, "secretmanager", path, ["secretmanager.versions.add"]):
                resource_gaps.append(f"secretmanager.versions.add on {name}")
        elif version.get("state") != "ENABLED":
            # The run reads the latest value and never rotates one, so a disabled or destroyed latest version would
            # stop it after earlier writes.
            raise media.OperationError(f"Verification secret {name} has a latest version that is not enabled")
    bucket_policy = cloud.call("storage", media.policy_path("storage/v1/b/" + BUCKET, storage=True))
    media.check_runtime_bucket_policy(bucket_policy, IDENTITY, granted=False)
    media.policy_etag(bucket_policy)
    if not media.bound(bucket_policy, media.ROLE, member):
        needed.add("storage.buckets.setIamPolicy")
    for kind, path in (("jobs", JOB), ("services", SERVICE)):
        current = cloud.call("run", "v2/" + path, missing_ok=True)
        check_owned(current, "cleanup job" if kind == "jobs" else "service")
        if current is None:
            needed |= {f"run.{kind}.create", f"run.{kind}.setIamPolicy"}
            continue
        policy = cloud.call("run", media.policy_path("v2/" + path))
        media.check_private_policy(policy)
        media.policy_etag(policy)
        needed.add(f"run.{kind}.update")
        if not media.bound(policy, "roles/run.invoker", member):
            needed.add(f"run.{kind}.setIamPolicy")
    schedule = cloud.call("cloudscheduler", "v1/" + SCHEDULE, missing_ok=True)
    if schedule is not None and schedule.get("description") != PURPOSE:
        raise media.OperationError("Existing verification cleanup schedule is not feature-owned")
    needed.add("cloudscheduler.jobs.create" if schedule is None else "cloudscheduler.jobs.update")
    return sorted(needed - media.held(cloud, "cloudresourcemanager", f"v1/projects/{PROJECT}", sorted(needed))) + resource_gaps


def require_media_prerequisites(cloud: media.Cloud) -> None:
    """Refuse before any write unless media provisioning made the object role and preview bucket this lane binds."""
    try:
        media.check_role(cloud.call("iam", "v1/" + media.ROLE, missing_ok=True, step=media.ROLE_READ))
        preview = cloud.call("storage", "storage/v1/b/" + BUCKET, missing_ok=True, step=media.BUCKET_READ)
        if preview is None:
            raise media.OperationError("Preview bucket is absent")
        media.check_bucket(preview, "preview")
    except media.OperationError as exc:
        raise media.OperationError(f"Live verification refused before any write: media provisioning prerequisite not verified ({exc})") from None


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
    media.policy_etag(policy)  # setIamPolicy carries it: a concurrent change fails the write rather than being lost
    member = "serviceAccount:" + IDENTITY
    grants = [b for b in media.policy_bindings(policy) if member in b.get("members", [])]
    if any(b.get("role") != "roles/cloudsql.client" or b.get("condition") for b in grants):
        raise media.OperationError("Verification identity has unexpected direct project privileges")
    if not grants:
        policy.setdefault("bindings", []).append({"role": "roles/cloudsql.client", "members": [member]})
        cloud.call("cloudresourcemanager", f"v1/projects/{PROJECT}:setIamPolicy", method="POST", body={"policy": policy})
    # IAM serviceAccounts.getIamPolicy uses POST (Cloud Run/Secret Manager use GET).
    sa_policy = cloud.call("iam", "v1/" + SA_PATH + ":getIamPolicy?options.requestedPolicyVersion=3", method="POST", body={})
    check_grants(sa_policy, {role: {"serviceAccount:" + deployer} for role in SA_ROLES}, "identity")
    changed = False
    for role in SA_ROLES:
        member = "serviceAccount:" + deployer
        if media.bound(sa_policy, role, member):  # the test bootstrap_gaps planned with
            continue
        binding = next((row for row in sa_policy.get("bindings", []) if row.get("role") == role and not row.get("condition")), None)
        if binding is None:
            sa_policy.setdefault("bindings", []).append({"role": role, "members": [member]})
        else:
            binding.setdefault("members", []).append(member)
        changed = True
    if changed:
        cloud.call("iam", "v1/" + SA_PATH + ":setIamPolicy", method="POST", body={"policy": sa_policy})
    member = "serviceAccount:" + IDENTITY
    for name in (DB_SECRET, KEY_SECRET):
        media.bind(cloud, "secretmanager", f"v1/projects/{PROJECT}/secrets/{name}", ACCESSOR, member)
        media.bind(cloud, "secretmanager", f"v1/projects/{PROJECT}/secrets/{name}", ACCESSOR, "serviceAccount:" + deployer)
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
                 "volumeMounts": [{"name": SQL_VOLUME, "mountPath": "/cloudsql"}],
                 "resources": {"limits": {"cpu": "1", "memory": "512Mi" if job else "1Gi"}}}
    if not job:
        # Its cold starts (its first start, and enable's receipt read after it scales to zero) must fit Cloud Run's
        # startup window and the 180 s operation wait.
        container["resources"]["startupCpuBoost"] = True
    task = {"serviceAccount": IDENTITY, "timeout": "600s" if job else "60s", "containers": [container],
            "volumes": [{"name": SQL_VOLUME, "cloudSqlInstance": {"instances": [INSTANCE]}}]}
    if production["template"].get("vpcAccess"):
        task["vpcAccess"] = copy.deepcopy(production["template"]["vpcAccess"])
    if job:
        task["maxRetries"] = 1
        return {"name": JOB, "labels": {"purpose": PURPOSE},
                "template": {"taskCount": 1, "parallelism": 1, "template": task}}
    # Memory acceptance reads cgroup v2 files, which only the second generation exposes (Cloud Run may pick either).
    task.update({"maxInstanceRequestConcurrency": 4, "scaling": {"minInstanceCount": 0, "maxInstanceCount": 1},
                 "executionEnvironment": "EXECUTION_ENVIRONMENT_GEN2"})
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


CONTROL_WAIT_SECONDS = 600
CONTROL_POLL_SECONDS = 15


def await_control(cloud: media.Cloud, origin: str, key: str, run_id: str) -> None:
    """Wait until the service answers the verifier identity, before the browser's first call.

    ensure_service has just written the identity's invoker grant, and an IAM allow-policy change typically takes two
    minutes to apply and can take seven or more (https://cloud.google.com/iam/docs/access-change-propagation). The
    browser treats a refusal as fatal after the run has seeded its two-hour lease, so it starts only once the
    receipt read, which changes nothing, succeeds.
    """
    deadline = time.monotonic() + CONTROL_WAIT_SECONDS
    while True:
        try:
            control(cloud, origin, key, run_id, "receipt")
            return
        except media.OperationError:
            if time.monotonic() >= deadline:
                raise media.OperationError("Verification service did not answer the verifier identity within ten minutes") from None
            time.sleep(CONTROL_POLL_SECONDS)


RECEIPT_WAIT_SECONDS = 240


def read_receipt(cloud: media.Cloud, origin: str, key: str, run_id: str) -> dict:
    """The receipt read, with a new attempt every 15 s for four minutes while the request itself fails.

    The verifier scales to zero between verify-apply and enable-apply, and its cold start (application import and
    startup audit) can outlast one 60 s request. Each attempt keeps its own request timeouts, so a read that never
    succeeds ends within about six minutes. The read changes nothing, and every receipt check uses it (verify-apply's
    last step, the read-only verify-inspect and enable). An answer that arrives is returned as it is: one without a
    receipt is refused by the caller at once.
    """
    deadline = time.monotonic() + RECEIPT_WAIT_SECONDS
    while True:
        try:
            return control(cloud, origin, key, run_id, "receipt")
        except media.OperationError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(CONTROL_POLL_SECONDS)


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
    # URLError and timeouts are OSErrors; so is a connection dropped before a response, which urllib raises outside its
    # URLError wrapper. HTTPException covers a response cut short (manage.Cloud.call reads the same way).
    except (OSError, HTTPException, ValueError, TypeError):
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


MEMORY_CAP_BYTES = 1073741824  # the verifier's configured 1 GiB, to which verify_runtime.resource_acceptance holds it
RESOURCE_NUMBERS = ("sample_count", "rss_peak_bytes", "cgroup_sample_peak_bytes", "cgroup_kernel_peak_bytes",
                    "cgroup_memory_limit_bytes", "configured_memory_limit_bytes", "self_high_water_rss_bytes",
                    "worker_high_water_rss_bytes", "last_process_count", "conservative_process_bound_bytes")
RESOURCE_NULLABLE = ("cgroup_sample_peak_bytes", "cgroup_kernel_peak_bytes", "cgroup_memory_limit_bytes")
RESOURCE_METHOD = ("kernel peak when exposed; otherwise conservative process bound plus sampled cgroup; "
                   "representative workload only")
EVIDENCE_BASES = ("kernel cgroup high-water peak", "kernel peak unavailable; conservative process-bound evidence")
WORKER_LIMITS = {"feedback_image_service": 1, "feedback_storage_worker_service": 2}


def counted(value, keys, *, nullable=()) -> bool:
    """A dict of exactly these keys, each a bounded non-negative integer (or None where nullable)."""
    return isinstance(value, dict) and set(value) == set(keys) and all(
        (item is None and name in nullable) or (type(item) is int and 0 <= item <= 2**63 - 1)
        for name, item in value.items())


def valid_resources(resources) -> bool:
    """The verifier's counts-only resource record: fixed keys, bounded numbers and two closed strings, no runtime text."""
    return (isinstance(resources, dict)
            and set(resources) == set(RESOURCE_NUMBERS) | {"method", "worker_limits", "unexplained_children",
                                                           "acceptance_passed", "sample_age_seconds", "evidence_basis"}
            and counted({name: resources[name] for name in RESOURCE_NUMBERS}, RESOURCE_NUMBERS, nullable=RESOURCE_NULLABLE)
            and resources["method"] == RESOURCE_METHOD
            and resources["evidence_basis"] in EVIDENCE_BASES
            and resources["worker_limits"] == WORKER_LIMITS
            and type(resources["sample_age_seconds"]) in {float, int} and 0 <= resources["sample_age_seconds"] <= 7200
            and type(resources["unexplained_children"]) is bool and type(resources["acceptance_passed"]) is bool)


def resource_refusals(resources: dict) -> list[str]:
    """Every acceptance condition a valid resource record fails, by closed name.

    verify_runtime.resource_acceptance decides, and a unit test holds the two to the same verdict on every input it
    tries. This names each failing condition rather than stopping at the first, so a refusal explains itself without
    changing verify_runtime.py, the verifier's fingerprinted source.
    """
    refused = []
    if resources["sample_count"] < 5:
        refused.append("samples")
    if resources["unexplained_children"]:
        refused.append("unexplained-child")
    if resources["last_process_count"] != 1:
        refused.append("process-count")
    if not 0 <= resources["sample_age_seconds"] <= 1:
        refused.append("sample-age")
    limit, peak, sample = (resources[name] for name in ("cgroup_memory_limit_bytes", "cgroup_kernel_peak_bytes",
                                                         "cgroup_sample_peak_bytes"))
    if limit is not None and limit != MEMORY_CAP_BYTES:
        refused.append("cgroup-limit")
    if peak is not None:
        if not 0 < peak < MEMORY_CAP_BYTES * .85:
            refused.append("kernel-peak")
        if sample is not None and not sample < MEMORY_CAP_BYTES * .85:
            refused.append("sampled-peak")
        return refused
    own, worker = resources["self_high_water_rss_bytes"], resources["worker_high_water_rss_bytes"]
    if not (own > 0 and worker > 0):
        refused.append("high-water-unread")
    if sample is None or not 0 < sample < MEMORY_CAP_BYTES * .85:
        refused.append("sampled-peak")
    if not own + 3 * worker < MEMORY_CAP_BYTES * .85:
        refused.append("process-bound")
    return refused


BOOT_PATTERN = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}")
SIGNED_SOURCE = "the run's signed receipt"


def instance_source(answer: dict) -> str:
    """Whose record a live receipt answer carries: the instance that answered, since it started (a uuid4 boot id).

    The verifier scales to zero, so after a scale-to-zero this is a new instance's record, not the measured run's."""
    boot = answer.get("boot_id")
    return ("the answering instance since its start" + (f", boot {boot[:8]}" if isinstance(boot, str)
                                                         and BOOT_PATTERN.fullmatch(boot) else ""))


def resources_line(resources, source: str) -> str:
    """One public line from a resource record, naming whose it is: its verdict, the failing conditions, its bytes."""
    if not valid_resources(resources):
        return f"Verifier resources ({source}): unavailable (no counts-only resource record)"
    def size(name: str, absent: str) -> str:
        return absent if resources[name] is None else f"{resources[name]} bytes"
    return (f"Verifier resources ({source}): acceptance {'passed' if resources['acceptance_passed'] else 'refused'}; "
            f"conditions failed: {', '.join(resource_refusals(resources)) or 'none'}; "
            f"samples {resources['sample_count']}; processes at the last sample {resources['last_process_count']}; "
            f"unexplained child {'seen' if resources['unexplained_children'] else 'none'}; "
            f"last sample {resources['sample_age_seconds']:.2f} s old; "
            f"cgroup limit {size('cgroup_memory_limit_bytes', 'unread')}; "
            f"kernel peak {size('cgroup_kernel_peak_bytes', 'unexposed')}; "
            f"sampled peak {size('cgroup_sample_peak_bytes', 'unread')}; "
            f"process-tree peak {resources['rss_peak_bytes']} bytes; "
            f"own high-water {resources['self_high_water_rss_bytes']} bytes; "
            f"worker high-water {resources['worker_high_water_rss_bytes']} bytes; "
            f"bound {int(MEMORY_CAP_BYTES * .85)} bytes")


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
    numbers = counted
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
    if not valid_resources(observed["resources"]):
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
    answer = read_receipt(cloud, origin, key, run_id)
    receipt = answer.get("receipt")
    if not isinstance(receipt, dict):
        # No run's record exists: the line is the answering instance's, which names itself as such.
        print(resources_line(answer.get("resources"), instance_source(answer)))
        raise media.OperationError("A completed live verification receipt is required")
    verify_receipt(receipt, key, run_id, image, hashes)
    print(resources_line(receipt["payload"]["observed"]["resources"], SIGNED_SOURCE))
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
        # AUTOMATIC is ServiceScaling's documented default, so a read-back may omit it; MANUAL is still refused.
        defaults = {"invokerIamDisabled": False, "minInstanceCount": 0, "scalingMode": "AUTOMATIC", "value": ""}
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
    # Initialize creates the whole schema in one transaction, and only the service it precedes makes fixtures or
    # objects. A run that stopped before it left nothing to settle, and its cleanup could not run without the schema.
    if sql.query("SELECT (to_regclass('public.users') IS NOT NULL)::int;", env=test_env) != "1":
        return
    execute_cleanup(cloud)  # Keep the old run marker until all its durable objects have settled.


# Each Cloud Run write's two forms: the create, which leaves the name to its ID, and the update of the one present.
JOB_WRITES = (f"v2/{media.PARENT}/jobs?jobId={NAME}-cleanup", "v2/" + JOB)
SERVICE_WRITES = (f"v2/{media.PARENT}/services?serviceId={NAME}",
                  "v2/" + SERVICE + "?updateMask=template,ingress,invokerIamDisabled,scaling")


def run_write(current: dict | None, spec: dict, writes: tuple[str, str]) -> tuple[str, str, dict]:
    """The write ensure_job or ensure_service sends: a create while the resource is absent, else an update of the one
    just read, under its etag."""
    create, update = writes
    if current:
        return update, "PATCH", {**spec, "etag": current["etag"]}
    return create, "POST", media.create_body(spec)


def validate_writes(cloud: media.Cloud, job: dict, service: dict) -> None:
    """Cloud Run's own validation of this run's job and service writes, before the run seeds its lease.

    Each request is the write ensure_job or ensure_service would send for the state read now, with validateOnly, so
    Cloud Run validates it and persists nothing. A field it refuses, as it refused the first live create's Cloud SQL
    volume name, then fails here, where a retry can follow at once; after the seed, the lease holds every retry for
    two hours. The refusal names the field (media.error_class).
    """
    for kind, path, spec, writes in (("cleanup job", JOB, job, JOB_WRITES), ("service", SERVICE, service, SERVICE_WRITES)):
        current = cloud.call("run", "v2/" + path, missing_ok=True)
        check_owned(current, kind)
        write, method, body = run_write(current, spec, writes)
        cloud.call("run", write + ("&" if "?" in write else "?") + "validateOnly=true", method=method, body=body,
                   step=f"Cloud Run validation of the verification {kind}")


def ensure_job(cloud: media.Cloud, spec: dict) -> None:
    current = cloud.call("run", "v2/" + JOB, missing_ok=True)
    check_owned(current, "cleanup job")
    write, method, body = run_write(current, spec, JOB_WRITES)
    cloud.wait(cloud.call("run", write, method=method, body=body))
    media.bind(cloud, "run", "v2/" + JOB, "roles/run.invoker", "serviceAccount:" + IDENTITY)


def ensure_schedule(cloud: media.Cloud) -> None:
    """The hourly expiry cleanup, created once initialize has made the schema it cleans."""
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


def ensure_service(cloud: media.Cloud, spec: dict) -> None:
    """Create or update the isolated service and grant its invoker, refusing one this feature does not own.

    It re-reads the service at the write, so a service that changed after bootstrap_gaps planned is refused or
    written under the etag read now.
    """
    current = cloud.call("run", "v2/" + SERVICE, missing_ok=True)
    check_owned(current, "service")
    write, method, body = run_write(current, spec, SERVICE_WRITES)
    cloud.wait(cloud.call("run", write, method=method, body=body))
    media.bind(cloud, "run", "v2/" + SERVICE, "roles/run.invoker", "serviceAccount:" + IDENTITY)


# live_runner.mjs's stages; a failure reports one with a kebab-case code from a VerificationError or check() literal.
BROWSER_STAGES = ("manifest", "fixtures", "frontend", "browser", "cleanup", "measurement", "completion", "shutdown")


def browser_failure(output: str) -> media.OperationError:
    """The refusal for a runner that exited non-zero: its closed stage and code only (Ops logs are public)."""
    try:
        result = json.loads(output)
    except ValueError:
        result = None
    if (isinstance(result, dict) and set(result) == {"status", "stage", "reason"} and result["status"] == "failed"
            and result["stage"] in BROWSER_STAGES and isinstance(result["reason"], str)
            and re.fullmatch(r"[a-z][a-z-]{0,39}", result["reason"])):
        return media.OperationError(f"Live browser verification failed at {result['stage']} ({result['reason']})")
    return media.OperationError("Verification command failed; diagnostics withheld")


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
        except CommandFailed as failed:
            raise browser_failure(failed.output) from None
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
    if not RUN_PATTERN.fullmatch(run_id) or not DEPLOYER_PATTERN.fullmatch(deployer):
        raise media.OperationError("Verification apply requires a first-attempt GitHub run and the configured project deployer")
    production = cloud.call("run", "v2/" + media.SERVICE)
    image, hashes = current_image(cloud, production), fingerprints()
    preflight_cloud(cloud)
    require_media_prerequisites(cloud)
    missing = bootstrap_gaps(cloud, deployer)
    if missing:
        raise media.OperationError("Verification provisioning lacks required IAM permissions for this state; nothing was "
                                   "changed: " + ", ".join(missing))
    with sql_admin(cloud) as sql:
        sql.preflight()  # no creation until actual SQL capabilities are established
        sql.admit()  # and production has room for the capped verifier
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
        # Cloud Run validates both writes before the seed, so a refused field never leaves a two-hour lease behind.
        validate_writes(cloud, runtime_spec(production, run_id, image, hashes, versions, job=True),
                        runtime_spec(production, run_id, image, hashes, versions, job=False))
        settle_previous_run(cloud, sql, test_env, production)
        lease_end = datetime.now(UTC) + timedelta(hours=2)  # taken before the seed, so never later than the lease
        seed_marker(sql, test_env, run_id, image, hashes)
        ensure_job(cloud, runtime_spec(production, run_id, image, hashes, versions, job=True))
        execute_cleanup(cloud, initialize=True)
        ensure_schedule(cloud)
        migration_output = run(["bash", str(ROOT / "backend/scripts/apply_migrations.sh")], env=test_env, timeout=900)
        summaries = re.findall(r"^apply_migrations: applied=\d+ skipped=\d+$", migration_output, re.MULTILINE)
        if len(summaries) != 1:
            raise media.OperationError("Isolated migration runner did not produce its completion receipt")
        print("Isolated verification database: " + summaries[0])
        ensure_service(cloud, runtime_spec(production, run_id, image, hashes, versions, job=False))
        origin = assert_private_service(cloud, cloud.call("run", "v2/" + SERVICE))
        await_control(cloud, origin, key, run_id)
        browse_then_clean(cloud, origin, key, run_id, image, hashes)
        # Production as it serves now: a deploy during the run must not leave this check on the revision it started on.
        require_receipt(cloud, cloud.call("run", "v2/" + media.SERVICE))
    print("Isolated live verification completed; production uploads remain unchanged")
    print(enable_deadline(lease_end))


def browse_then_clean(cloud: media.Cloud, origin: str, key: str, run_id: str, image: str, hashes: dict) -> None:
    """The browser, then the bounded in-run cleanup, which runs whether or not the browser passed."""
    try:
        browser(cloud, origin, key, run_id, image, hashes)
    except BaseException as failure:
        try:
            if isinstance(failure, media.OperationError):
                report_resources(cloud, origin, key, run_id)
        finally:
            # A failed browser must leave a runnable cleanup path and durable manifests. This bounded attempt
            # supplements the retained hourly job; a failure of its own is reported beside the browser's, never in its
            # place. It runs whatever the diagnostic read above does, an interrupt included.
            try:
                execute_cleanup(cloud)
            except media.OperationError as cleanup_failure:
                print(f"Verification cleanup after that failure: {cleanup_failure}")
        raise
    execute_cleanup(cloud)


def report_resources(cloud: media.Cloud, origin: str, key: str, run_id: str) -> None:
    """After a failed browser run, one receipt read (no retry) prints the answering instance's resource line.

    That instance is the run's own unless the verifier restarted, which the runner reports as runtime-restarted. Best
    effort: whatever this read or its line raises, the browser's failure stays the run's and its own error is withheld;
    the caller's cleanup runs in a finally."""
    try:
        answer = control(cloud, origin, key, run_id, "receipt")
        line = resources_line(answer.get("resources"), instance_source(answer))
    except Exception:  # noqa: BLE001 — a diagnostic read never replaces the browser's failure
        print("Verifier resources: unavailable (receipt read failed)")
        return
    print(line)


def enable_deadline(lease_end: datetime) -> str:
    """The verifier scales to zero and starts only within its run's lease, so enable's receipt read must come before."""
    return (f"Enable before {lease_end:%Y-%m-%dT%H:%MZ}: the verifier answers its receipt read only within this "
            "run's two-hour lease, as well as within two hours of the receipt")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("feedback-media-verify-inspect", "feedback-media-verify-apply"))
    operation = parser.parse_args().operation
    cloud = media.Cloud()
    if operation == "feedback-media-verify-apply":
        provision(cloud)
    else:
        report_capability(cloud)
        require_receipt(cloud, cloud.call("run", "v2/" + media.SERVICE))


def report_capability(cloud: media.Cloud) -> None:
    """Print, read-only, what verify-apply would lack on the current state; it reports, never refuses."""
    deployer = os.environ.get("FEEDBACK_VERIFY_DEPLOYER", "")
    try:
        if not DEPLOYER_PATTERN.fullmatch(deployer):
            raise media.OperationError("the configured project deployer is unavailable")
        missing = preflight_gaps(cloud) or bootstrap_gaps(cloud, deployer)
    except media.OperationError as exc:
        print(f"Capability for feedback-media-verify-apply: UNVERIFIED ({exc})")
        return
    print("Capability for feedback-media-verify-apply: " + ("all required permissions present" if not missing
                                                             else "missing " + ", ".join(missing)))


if __name__ == "__main__":
    try:
        main()
    except (media.OperationError, OSError) as exc:
        raise SystemExit(str(exc) if isinstance(exc, media.OperationError) else "Verification input is unavailable") from None
