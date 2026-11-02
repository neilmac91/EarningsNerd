"""Exercise database ownership and privacy boundaries without cloud or SQL calls."""
from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from ops.summary_delivery import database as db  # noqa: E402

PASSWORD = "a" * 64  # Synthetic; never transmitted.
PRIVATE = "PRIVATE_DATABASE_ERROR_SENTINEL"
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64
MANIFEST = db.spec.plan(ROOT, IMAGE, "123456789", "123", "b" * 32)["manifest"]
CONNECTION = db.spec.connection_name(MANIFEST)
ADMIN_PASSWORD = "c" * 64
ADMIN_URL = f"postgresql://postgres:{ADMIN_PASSWORD}@/postgres?host=/cloudsql/{CONNECTION}"


class Sql:
    """Stateful psql boundary, including independently configurable ACL results."""

    def __init__(self):
        self.role = False
        self.database = False
        self.capable = "1"
        self.headroom = "100|3|0|10"
        self.role_owned = "1"
        self.database_owned = "1"
        self.objects = "0"
        self.functions = "0"
        self.schemas = "0"
        self.connections = "0"
        self.identity = f"{db.DATABASE}:{db.DATABASE}"
        self.calls = []

    def __call__(self, argv, **kwargs):
        assert argv == ["psql", "-X", "-qAt", "-v", "ON_ERROR_STOP=1"]
        assert kwargs["stderr"] == subprocess.DEVNULL
        assert 0 < kwargs["timeout"] <= 25 and kwargs["check"] is False
        assert PRIVATE not in repr(argv) and PASSWORD not in repr(argv)
        text = kwargs["input"]
        self.calls.append((text, kwargs["env"].copy()))
        if "rolsuper OR" in text:
            result = self.capable
        elif text.startswith("SELECT count(*) FROM pg_roles"):
            result = str(int(self.role))
        elif text.startswith("SELECT count(*) FROM pg_database"):
            result = str(int(self.database))
        elif "current_setting('max_connections')" in text:
            result = self.headroom
        elif "shobj_description(oid,'pg_authid')" in text:
            result = self.role_owned
        elif "shobj_description(oid,'pg_database')" in text:
            result = self.database_owned
        elif "FROM pg_class" in text:
            result = self.objects
        elif "FROM pg_proc" in text:
            result = self.functions
        elif "FROM pg_namespace" in text:
            result = self.schemas
        elif "SELECT current_database()" in text:
            result = self.identity
        elif "SELECT count(*) FROM pg_stat_activity" in text:
            result = self.connections
        elif "CREATE ROLE" in text:
            assert not self.role
            self.role = True
            result = ""
        elif text.startswith("CREATE DATABASE"):
            assert not self.database
            self.database = True
            result = ""
        elif text.startswith("DROP DATABASE"):
            self.database = False
            result = ""
        elif text.startswith("DROP ROLE"):
            self.role = False
            result = ""
        else:
            assert text.startswith(("COMMENT", "REVOKE", "ALTER", "SELECT pg_terminate_backend")), text
            result = ""
        kwargs["stdout"].write(result.encode())
        return SimpleNamespace(returncode=0)


@pytest.fixture
def sql(monkeypatch):
    boundary = Sql()
    monkeypatch.setattr(db.subprocess, "run", boundary)
    return boundary


def administrator():
    return db.Admin(db.connection_env(ADMIN_URL, MANIFEST, isolated=False), MANIFEST)


def writes(sql):
    return [text for text, _ in sql.calls if not text.startswith("SELECT")]


def test_provision_restricted_isolated_resources_and_effective_acl_audit(sql, capsys):
    result = administrator().provision(PASSWORD)
    assert result == db.database_url(PASSWORD, MANIFEST)
    assert sql.role and sql.database
    role = next(text for text in writes(sql) if "CREATE ROLE" in text)
    for required in ("NOINHERIT", "NOSUPERUSER", "NOCREATEDB", "NOCREATEROLE", "NOREPLICATION", "NOBYPASSRLS",
                     "CONNECTION LIMIT 12", db.PURPOSE, "SCRAM-SHA-256$4096:"):
        assert required in role
    assert PASSWORD not in role
    assert all(PRIVATE not in text for text, _ in sql.calls)
    schema_calls = [(text, env) for text, env in sql.calls if "REVOKE ALL ON SCHEMA" in text]
    assert len(schema_calls) == 1 and schema_calls[0][1]["PGDATABASE"] == db.DATABASE
    assert all("earningsnerd " not in text for text in writes(sql))
    assert any("has_table_privilege" in text and "has_sequence_privilege" in text for text, _ in sql.calls)
    assert any("p.prosecdef" in text and "has_function_privilege" in text for text, _ in sql.calls)
    assert any("has_schema_privilege" in text for text, _ in sql.calls)
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("setting,value,code", [
    ("capable", "0", "database_admin_capability"),
    ("role", True, "database_resources_already_exist"),
    ("database", True, "database_resources_already_exist"),
    ("headroom", "100|3|0|51", "database_headroom_insufficient"),
    ("headroom", "100|3|4|49", "database_headroom_insufficient"),
    ("headroom", "12|3|0|0", "database_headroom_insufficient"),
    ("headroom", "100|3|0|unknown", "database_headroom_unverified"),
    ("headroom", "100|100|0|0", "database_headroom_insufficient"),
])
def test_preflight_refuses_before_any_write(sql, setting, value, code):
    setattr(sql, setting, value)
    with pytest.raises(db.Refused, match=f"^{code}$"):
        administrator().provision(PASSWORD)
    assert not writes(sql)


def test_headroom_boundary_reserves_all_twelve_connections_and_operational_margin(sql):
    sql.headroom = "103|3|0|53"  # 53 + 12 + 5 == 70% of 100 usable.
    admin = administrator()
    admin.preflight()
    assert admin.headroom_snapshot == {"maximum": 103, "reserved": 3, "active": 53, "usable": 100,
                                       "requested_connection_cap": 12, "operational_reserve": 5,
                                       "threshold_pct": 70, "admitted": True}
    sql.headroom = "103|3|0|54"
    with pytest.raises(db.Refused, match="database_headroom_insufficient"):
        admin.preflight()
    assert admin.headroom_snapshot["admitted"] is False and admin.headroom_snapshot["active"] == 54
    sql.headroom = PRIVATE
    with pytest.raises(db.Refused, match="database_headroom_unverified"):
        admin.preflight()
    assert admin.headroom_snapshot is None


@pytest.mark.parametrize("field", ["objects", "functions", "schemas"])
def test_effective_production_acl_exposure_refuses_without_rewriting_production(sql, field):
    setattr(sql, field, "1")
    with pytest.raises(db.Refused, match="database_admin_object_access"):
        administrator().provision(PASSWORD)
    assert sql.role and sql.database  # Controller must then clean its owned resources.
    assert all("earningsnerd " not in text for text in writes(sql))
    administrator().cleanup()
    assert not sql.role and not sql.database


def test_wrong_runtime_authentication_cannot_return_ready_database(sql):
    sql.identity = "earningsnerd:operator"
    with pytest.raises(db.Refused, match="database_isolated_authentication"):
        administrator().provision(PASSWORD)
    administrator().cleanup()
    assert not sql.role and not sql.database


def test_password_sql_injection_is_refused_before_even_reading_database(sql):
    with pytest.raises(db.Refused, match="database_password_shape"):
        administrator().provision("'; DROP DATABASE earningsnerd; --")
    assert not sql.calls


@pytest.mark.parametrize("field,code", [("role_owned", "database_role_not_owned_and_restricted"),
                                        ("database_owned", "database_not_owned")])
def test_cleanup_refuses_mismatched_ownership_before_mutation(sql, field, code):
    sql.role = sql.database = True
    setattr(sql, field, "0")
    with pytest.raises(db.Refused, match=code):
        administrator().cleanup()
    assert not writes(sql)
    assert not any("pg_terminate_backend" in text for text, _ in sql.calls)


def test_cleanup_only_terminates_own_role_in_own_database(sql):
    sql.role = sql.database = True
    administrator().cleanup()
    termination = [text for text, _ in sql.calls if "pg_terminate_backend" in text]
    assert len(termination) == 1
    assert f"datname='{db.DATABASE}'" in termination[0]
    assert f"usename='{db.DATABASE}'" in termination[0]
    assert writes(sql)[0] == f"ALTER ROLE {db.DATABASE} NOLOGIN;"
    assert [text for text in writes(sql) if text.startswith("DROP")] == [
        f"DROP DATABASE {db.DATABASE};", f"DROP ROLE {db.DATABASE};"]
    assert not sql.role and not sql.database


def test_cleanup_never_kills_unexpected_operator_session(sql):
    sql.role = sql.database = True
    sql.connections = "1"
    with pytest.raises(db.Refused, match="database_cleanup_connections_remain"):
        administrator().cleanup()
    assert not any(text.startswith("DROP") for text in writes(sql))
    assert len([text for text, _ in sql.calls if "pg_terminate_backend" in text]) == 1


@pytest.mark.parametrize("role,database", [(False, False), (True, False), (False, True)])
def test_cleanup_handles_only_verified_partial_owned_resources(sql, role, database):
    sql.role, sql.database = role, database
    administrator().cleanup()
    assert not sql.role and not sql.database
    assert len([text for text in writes(sql) if text.startswith("DROP")]) == int(role) + int(database)


@pytest.mark.parametrize("url", [
    "postgresql://someone:password@remote/earningsnerd_summary_verify",
    f"postgresql://someone:password@/{db.DATABASE}?host=/cloudsql/{CONNECTION}",
    f"postgresql://{db.DATABASE}:password@/earningsnerd?host=/cloudsql/{CONNECTION}",
    f"postgresql://{db.DATABASE}:password@/{db.DATABASE}?host=/cloudsql/other",
    f"postgresql://{db.DATABASE}:password@/{db.DATABASE}?host=/cloudsql/{CONNECTION}&sslmode=disable",
    f"postgresql://{db.DATABASE}:pass%00word@/{db.DATABASE}?host=/cloudsql/{CONNECTION}",
    "broken#" + PRIVATE,
])
def test_connection_boundary_rejects_arbitrary_host_database_role_and_options(url):
    with pytest.raises(db.Refused, match="^database_connection_boundary$") as error:
        db.connection_env(url, MANIFEST)
    assert PRIVATE not in str(error.value)


def test_credentials_stay_only_in_child_environment_and_clear_ambient_options(monkeypatch):
    monkeypatch.setenv("PGSERVICE", "attacker")
    monkeypatch.setenv("PGOPTIONS", "attacker")
    env = db.connection_env(db.database_url(PASSWORD, MANIFEST), MANIFEST)
    assert env["PGPASSWORD"] == PASSWORD and env["PGUSER"] == db.DATABASE
    assert env["PGHOST"] == "127.0.0.1" and env["PGPORT"] == "15432"
    assert "PGSERVICE" not in env and "attacker" not in repr(env)


@pytest.mark.parametrize("failure", ["exit", "timeout", "oversize", "non_ascii"])
def test_psql_failures_have_closed_errors_without_sql_or_driver_output(monkeypatch, capsys, failure):
    def run(argv, **kwargs):
        if failure == "timeout":
            raise subprocess.TimeoutExpired(argv, 25, output=PRIVATE, stderr=PRIVATE)
        kwargs["stdout"].write(b"\xff" if failure == "non_ascii" else
                               b"x" * (db.MAX_REPLY_BYTES + 1) if failure == "oversize" else PRIVATE.encode())
        return SimpleNamespace(returncode=1 if failure == "exit" else 0)
    monkeypatch.setattr(db.subprocess, "run", run)
    with pytest.raises(db.Refused) as error:
        administrator().query("SELECT '" + PRIVATE + "';")
    assert PRIVATE not in str(error.value)
    assert capsys.readouterr().out == "" and capsys.readouterr().err == ""


def test_all_admin_queries_share_one_budget_and_clamp_last_process_timeout(sql, monkeypatch):
    now = [100.0]
    monkeypatch.setattr(db.time, "monotonic", lambda: now[0])
    admin = administrator()
    observed = []

    def bounded(*args, **kwargs):
        observed.append(kwargs["timeout"])
        return sql(*args, **kwargs)

    monkeypatch.setattr(db.subprocess, "run", bounded)
    admin.query("SELECT (rolsuper OR (rolcreatedb AND rolcreaterole))::int FROM pg_roles WHERE rolname=current_user;")
    now[0] = 219.0
    admin.query("SELECT (rolsuper OR (rolcreatedb AND rolcreaterole))::int FROM pg_roles WHERE rolname=current_user;")
    assert observed == [25, 1]
    now[0] = 220.0
    with pytest.raises(db.Refused, match="database_query_deadline"):
        admin.query("SELECT '" + PRIVATE + "';")
    assert len(observed) == 2


class Cloud:
    def __init__(self):
        self.calls = []

    def call(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        pytest.fail("SQL provisioning must not retrieve any cloud credential")


class Proxy:
    def __init__(self):
        self.done = False
        self.terminated = False
        self.waited = False

    def poll(self):
        return 0 if self.done else None

    def terminate(self):
        self.terminated = self.done = True

    def wait(self, *, timeout):
        assert timeout == 5
        self.waited = True


@pytest.fixture
def proxy(monkeypatch, tmp_path):
    binary = tmp_path / "cloud-sql-proxy"
    binary.write_bytes(b"purpose-owned-test-proxy")
    monkeypatch.setattr(db, "PROXY_SHA256", hashlib.sha256(binary.read_bytes()).hexdigest())
    process = Proxy()
    calls = []

    def popen(argv, **kwargs):
        calls.append((argv, kwargs))
        return process

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bind(self, address):
            assert address == ("127.0.0.1", 15432)

    monkeypatch.setattr(db.socket, "socket", Socket)
    monkeypatch.setattr(db.subprocess, "Popen", popen)
    monkeypatch.setattr(db.subprocess, "run", lambda *a, **k: SimpleNamespace(returncode=0))
    return tmp_path, process, calls


def test_admin_context_uses_pinned_proxy_and_reaps_without_credential_arguments(proxy, capsys):
    path, process, calls = proxy
    cloud = Cloud()
    with db.admin(cloud, path, MANIFEST, ADMIN_PASSWORD) as admin:
        assert admin.env["PGPASSWORD"] == ADMIN_PASSWORD
    assert not cloud.calls
    assert len(calls) == 1 and ADMIN_PASSWORD not in repr(calls)
    assert calls[0][0][-1] == CONNECTION and calls[0][1]["stderr"] == subprocess.DEVNULL
    assert process.terminated and process.waited
    assert capsys.readouterr().out == ""


def test_admin_context_rejects_unpinned_proxy_before_accessing_secret(proxy):
    path, _, calls = proxy
    (path / "cloud-sql-proxy").write_bytes(b"tampered")
    cloud = Cloud()
    with pytest.raises(db.Refused, match="database_proxy_not_pinned"), db.admin(cloud, path, MANIFEST, ADMIN_PASSWORD):
        pytest.fail("not reached")
    assert not cloud.calls and not calls


def test_admin_context_reaps_proxy_when_readiness_fails(proxy, monkeypatch, capsys):
    path, process, _ = proxy

    def fail(*args, **kwargs):
        raise subprocess.TimeoutExpired("pg_isready", 3, output=PRIVATE, stderr=PRIVATE)

    monkeypatch.setattr(db.subprocess, "run", fail)
    with pytest.raises(db.Refused, match="database_proxy_unavailable"), db.admin(Cloud(), path, MANIFEST, ADMIN_PASSWORD):
        pytest.fail("not reached")
    assert process.terminated and process.waited
    assert capsys.readouterr().out == "" and capsys.readouterr().err == ""


def test_proxy_probe_timeout_cannot_extend_its_readiness_deadline(proxy, monkeypatch):
    path, process, _ = proxy
    samples = [0.0]

    def clock():
        return samples.pop() if samples else 29.5

    def fail(*args, **kwargs):
        assert kwargs["timeout"] == 0.5
        raise subprocess.TimeoutExpired("pg_isready", kwargs["timeout"])

    monkeypatch.setattr(db.time, "monotonic", clock)
    monkeypatch.setattr(db.subprocess, "run", fail)
    with pytest.raises(db.Refused, match="database_proxy_unavailable"), db.admin(Cloud(), path, MANIFEST, ADMIN_PASSWORD):
        pytest.fail("not reached")
    assert process.terminated and process.waited


@pytest.mark.parametrize("password", ["", "short", "g" * 64, PRIVATE])
def test_admin_password_shape_refuses_without_cloud_or_proxy(proxy, password):
    path, _, calls = proxy
    cloud = Cloud()
    with pytest.raises(db.Refused, match="database_admin_password_shape"), db.admin(cloud, path, MANIFEST, password):
        pytest.fail("not reached")
    assert not calls and not cloud.calls


def test_admin_manifest_cannot_redirect_to_production(proxy):
    from copy import deepcopy
    path, _, calls = proxy
    cloud = Cloud()
    changed = deepcopy(MANIFEST)
    changed["sql_instance"]["name"] = "earningsnerd-db"
    with pytest.raises(db.Refused), db.admin(cloud, path, changed, ADMIN_PASSWORD):
        pytest.fail("not reached")
    assert not calls and not cloud.calls


def test_admin_credential_must_name_postgres_on_temporary_instance():
    invalid = f"postgresql://operator:{PRIVATE}@/postgres?host=/cloudsql/{CONNECTION}"
    with pytest.raises(db.Refused, match="database_connection_boundary"):
        db.connection_env(invalid, MANIFEST, isolated=False)
    invalid = f"postgresql://postgres:{PRIVATE}@/postgres?host=/cloudsql/earnings-nerd:us-west1:earningsnerd-db"
    with pytest.raises(db.Refused, match="database_connection_boundary"):
        db.connection_env(invalid, MANIFEST, isolated=False)
