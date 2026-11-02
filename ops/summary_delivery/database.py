"""Restricted, purpose-owned SQL resources for the isolated delivery rehearsal.

Only the approved controller enters ``admin`` with its temporary administrator
password. No production credential is read. Queries, passwords and driver errors
do not enter outputs. No live operation is performed at import.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import socket
import subprocess
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from ops.summary_delivery import spec
from ops.summary_delivery.spec import DATABASE, PURPOSE, Refused

PROXY_SHA256 = "c0af803c07157530c9159b6179e3288298950af5a39c8ca38ad28c8a2b52ae3d"
ADMIN_DATABASE = "postgres"
CONNECTION_LIMIT = 12
OPERATIONAL_RESERVE = 5
MAX_REPLY_BYTES = 4096
QUERY_BUDGET_SECONDS = 120


def refuse(code: str) -> None:
    raise Refused(code) from None


def database_url(password: str, manifest: dict) -> str:
    spec.validate_scope(manifest)
    if not isinstance(password, str) or not re.fullmatch(r"[0-9a-f]{64}", password):
        refuse("database_password_shape")
    return f"postgresql://{DATABASE}:{password}@/{DATABASE}?host=/cloudsql/{spec.connection_name(manifest)}"


def _scram(password: str) -> str:
    # SQL statement logging must not capture the reusable client password.
    # The caller supplied 256-bit random password is never inserted into SQL.
    salt = os.urandom(16)
    salted = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 4096)
    client = hmac.digest(salted, b"Client Key", "sha256")
    stored = hashlib.sha256(client).digest()
    server = hmac.digest(salted, b"Server Key", "sha256")
    encoded = [base64.b64encode(value).decode() for value in (salt, stored, server)]
    return f"SCRAM-SHA-256$4096:{encoded[0]}${encoded[1]}:{encoded[2]}"


def connection_env(url: str, manifest: dict, *, isolated: bool = True) -> dict[str, str]:
    spec.validate_scope(manifest)
    connection = spec.connection_name(manifest)
    try:
        parsed = urlsplit(url)
        query = parse_qs(parsed.query, strict_parsing=True)
        database = parsed.path.removeprefix("/")
        username = unquote(parsed.username or "")
        password = unquote(parsed.password or "")
        valid = (parsed.scheme in {"postgresql", "postgres"} and not parsed.hostname and not parsed.port
                 and not parsed.fragment and query == {"host": [f"/cloudsql/{connection}"]}
                 and bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,62}", username)) and password
                 and "\x00" not in password and len(password) <= 4096
                 and database == (DATABASE if isolated else ADMIN_DATABASE)
                 and username == (DATABASE if isolated else "postgres"))
    except (ValueError, TypeError, UnicodeError):
        refuse("database_connection_boundary")
    if not valid:
        refuse("database_connection_boundary")
    return {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "PGHOST": "127.0.0.1", "PGPORT": "15432",
            "PGDATABASE": database, "PGUSER": username, "PGPASSWORD": password,
            "PGCONNECT_TIMEOUT": "5", "PGAPPNAME": "summary-delivery-verification",
            "PGOPTIONS": "-c lock_timeout=2000 -c statement_timeout=10000"}


class Admin:
    def __init__(self, env: dict[str, str], manifest: dict):
        # This class is constructed only after strict parsing of the fixed
        # temporary credential. Do not use a dataclass/repr that exposes env.
        spec.validate_scope(manifest)
        if (env.get("PGDATABASE") != ADMIN_DATABASE or env.get("PGUSER") != "postgres"
                or env.get("PGHOST") != "127.0.0.1" or env.get("PGPORT") != "15432"):
            refuse("database_admin_boundary")
        self.env = env
        self.manifest = manifest
        self.headroom_snapshot: dict | None = None
        self.query_deadline = time.monotonic() + QUERY_BUDGET_SECONDS

    def query(self, sql: str, *, env: dict[str, str] | None = None) -> str:
        remaining = self.query_deadline - time.monotonic()
        if remaining <= 0:
            refuse("database_query_deadline")
        try:
            with tempfile.TemporaryFile() as output:
                completed = subprocess.run(
                    ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"], input=sql, text=True,
                    env=env or self.env, stdout=output, stderr=subprocess.DEVNULL, timeout=min(25, remaining), check=False,
                )
                if completed.returncode != 0:
                    refuse("database_command_unverified")
                if time.monotonic() >= self.query_deadline:
                    refuse("database_query_deadline")
                output.seek(0)
                content = output.read(MAX_REPLY_BYTES + 1)
            if len(content) > MAX_REPLY_BYTES:
                refuse("database_reply_bound")
            return content.decode("ascii").strip()
        except (subprocess.SubprocessError, OSError, UnicodeError):
            refuse("database_command_unverified")

    def _capability(self) -> None:
        answer = self.query("SELECT (rolsuper OR (rolcreatedb AND rolcreaterole))::int FROM pg_roles WHERE rolname=current_user;")
        if answer != "1":
            refuse("database_admin_capability")

    def _counts(self) -> tuple[str, str]:
        role = self.query(f"SELECT count(*) FROM pg_roles WHERE rolname='{DATABASE}';")
        database = self.query(f"SELECT count(*) FROM pg_database WHERE datname='{DATABASE}';")
        if role not in {"0", "1"} or database not in {"0", "1"}:
            refuse("database_inventory_unverified")
        return role, database

    def preflight(self) -> None:
        self._capability()
        if self._counts() != ("0", "0"):
            refuse("database_resources_already_exist")
        self._headroom()

    def _headroom(self) -> None:
        # This is an admission snapshot, not a global capacity reservation.
        self.headroom_snapshot = None
        answer = self.query("""SELECT current_setting('max_connections') || '|' ||
            current_setting('superuser_reserved_connections') || '|' ||
            COALESCE(current_setting('reserved_connections',true),'0') || '|' ||
            (SELECT count(*) FROM pg_stat_activity WHERE backend_type='client backend');""")
        if not re.fullmatch(r"[0-9]{1,7}(\|[0-9]{1,7}){3}", answer):
            refuse("database_headroom_unverified")
        maximum, superuser_reserved, reserved, active = map(int, answer.split("|"))
        usable = maximum - superuser_reserved - reserved
        admitted = usable > 0 and (active + CONNECTION_LIMIT + OPERATIONAL_RESERVE) * 10 <= usable * 7
        self.headroom_snapshot = {"maximum": maximum, "reserved": superuser_reserved + reserved,
                                  "active": active, "usable": usable, "requested_connection_cap": CONNECTION_LIMIT,
                                  "operational_reserve": OPERATIONAL_RESERVE, "threshold_pct": 70, "admitted": admitted}
        if not admitted:
            refuse("database_headroom_insufficient")

    def _owned(self, *, login_required: bool) -> tuple[str, str]:
        role, database = self._counts()
        if role == "1":
            login = " AND rolcanlogin" if login_required else ""
            valid = self.query(f"""SELECT (NOT rolsuper AND NOT rolcreatedb AND NOT rolcreaterole
                AND NOT rolreplication AND NOT rolbypassrls AND NOT rolinherit{login}
                AND rolconnlimit={CONNECTION_LIMIT} AND shobj_description(oid,'pg_authid')='{PURPOSE}'
                AND NOT EXISTS(SELECT 1 FROM pg_auth_members WHERE member=pg_roles.oid))::int
                FROM pg_roles WHERE rolname='{DATABASE}';""")
            if valid != "1":
                refuse("database_role_not_owned_and_restricted")
        if database == "1":
            valid = self.query(f"""SELECT (pg_get_userbyid(datdba)=current_user
                AND shobj_description(oid,'pg_database')='{PURPOSE}')::int
                FROM pg_database WHERE datname='{DATABASE}';""")
            if valid != "1":
                refuse("database_not_owned")
        return role, database

    def audit_admin_database_access(self) -> None:
        # PUBLIC CONNECT is not a per-role deny. Audit effective application
        # object access in the empty temporary administrator database instead.
        objects = self.query(f"""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
            AND c.relkind IN ('r','p','v','m','S','f') AND CASE WHEN c.relkind='S'
              THEN has_sequence_privilege('{DATABASE}',c.oid,'USAGE,SELECT,UPDATE')
              ELSE has_table_privilege('{DATABASE}',c.oid,'SELECT,INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') END;""")
        functions = self.query(f"""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE p.prosecdef AND n.nspname <> 'information_schema' AND n.nspname !~ '^pg_'
            AND has_function_privilege('{DATABASE}',p.oid,'EXECUTE');""")
        schemas = self.query(f"""SELECT count(*) FROM pg_namespace
            WHERE nspname <> 'information_schema' AND nspname !~ '^pg_'
            AND has_schema_privilege('{DATABASE}',oid,'CREATE');""")
        if objects != "0" or functions != "0" or schemas != "0":
            refuse("database_admin_object_access")

    def provision(self, password: str) -> str:
        url = database_url(password, self.manifest)
        isolated = connection_env(url, self.manifest)
        self.preflight()  # Re-read absence immediately before creating; never adopt.
        self.query(f"BEGIN; CREATE ROLE {DATABASE} LOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE "
                   f"NOREPLICATION NOBYPASSRLS CONNECTION LIMIT {CONNECTION_LIMIT} PASSWORD '{_scram(password)}'; "
                   f"COMMENT ON ROLE {DATABASE} IS '{PURPOSE}'; COMMIT;")
        # CREATE DATABASE cannot share the role transaction. If interrupted before
        # its ownership comment, cleanup refuses the unmarked resource for review.
        self.query(f"CREATE DATABASE {DATABASE} TEMPLATE template0;")
        self.query(f"COMMENT ON DATABASE {DATABASE} IS '{PURPOSE}';")
        self.query(f"REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC; GRANT CONNECT,TEMPORARY ON DATABASE {DATABASE} TO {DATABASE};")
        self.query(f"REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE,CREATE ON SCHEMA public TO {DATABASE};",
                   env={**self.env, "PGDATABASE": DATABASE})
        if self._owned(login_required=True) != ("1", "1"):
            refuse("database_creation_unverified")
        if self.query("SELECT current_database() || ':' || current_user;", env=isolated) != f"{DATABASE}:{DATABASE}":
            refuse("database_isolated_authentication")
        self.audit_admin_database_access()
        return url

    def cleanup(self) -> None:
        self._capability()
        role, database = self._owned(login_required=False)
        if role == "1":
            self.query(f"ALTER ROLE {DATABASE} NOLOGIN;")
        if database == "1":
            self.query(f"REVOKE ALL ON DATABASE {DATABASE} FROM PUBLIC;")
            if role == "1":
                self.query(f"REVOKE CONNECT ON DATABASE {DATABASE} FROM {DATABASE};")
            # Terminate only this rehearsal role in this rehearsal database.
            # Unexpected operator connections are not killed; the next check fails.
            self.query(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='{DATABASE}' "
                       f"AND usename='{DATABASE}' AND pid<>pg_backend_pid();")
            if self.query(f"SELECT count(*) FROM pg_stat_activity WHERE datname='{DATABASE}' AND pid<>pg_backend_pid();") != "0":
                refuse("database_cleanup_connections_remain")
            self.query(f"DROP DATABASE {DATABASE};")
        if role == "1":
            self.query(f"DROP ROLE {DATABASE};")
        if self._counts() != ("0", "0"):
            refuse("database_cleanup_unverified")


@contextmanager
def admin(cloud, root: Path, manifest: dict, admin_password: str):
    """Approved apply-only context; callers own approval and cloud-action budgets."""
    spec.validate_scope(manifest)
    if not isinstance(admin_password, str) or not re.fullmatch(r"[a-f0-9]{64}", admin_password):
        refuse("database_admin_password_shape")
    connection = spec.connection_name(manifest)
    proxy = Path(root) / "cloud-sql-proxy"
    try:
        if proxy.is_symlink() or not proxy.is_file() or hashlib.sha256(proxy.read_bytes()).hexdigest() != PROXY_SHA256:
            refuse("database_proxy_not_pinned")
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 15432))
        env = connection_env(f"postgresql://postgres:{admin_password}@/postgres?host=/cloudsql/{connection}",
                             manifest, isolated=False)
        process = subprocess.Popen([str(proxy), "--address", "127.0.0.1", "--port", "15432", connection],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except (OSError, ValueError):
        refuse("database_proxy_unavailable")
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if process.poll() is not None:
                refuse("database_proxy_unavailable")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                refuse("database_proxy_unavailable")
            check = subprocess.run(["pg_isready", "-h", "127.0.0.1", "-p", "15432"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   timeout=min(3, remaining), check=False)
            if time.monotonic() >= deadline:
                refuse("database_proxy_unavailable")
            if check.returncode == 0:
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                refuse("database_proxy_unavailable")
            time.sleep(min(0.25, remaining))
        else:
            refuse("database_proxy_unavailable")
        if process.poll() is not None:
            refuse("database_proxy_unavailable")
        yield Admin(env, manifest)
    except (subprocess.SubprocessError, OSError):
        refuse("database_proxy_unavailable")
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
