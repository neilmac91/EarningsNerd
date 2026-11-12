"""A previous run bound to another runtime source is settled by its own hourly cleanup, never executed by an apply.

Live verify-apply 43157966576 refused at "Previous cleanup differs" once #2039 changed main's runtime: the cleanup job
the previous run left still holds that run's own source, and settle_previous_run required main's. These tests hold the
path that replaced the refusal: the prior job is read back and held to its own run's hash, and an apply never executes
it; the run counts as settled only when the job's latest execution, created at least a minute after the lease expired
(so started by its hourly schedule, whose mode cleans an expired lease), succeeded. Main's own source still settles
through cleanup_now, as before.
"""
from __future__ import annotations

import hashlib
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "ops/feedback_media"))
SPEC = importlib.util.spec_from_file_location("feedback_verify_settle_ops", ROOT / "ops/feedback_media/verify_manage.py")
verify = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verify)

RUN_ID = "43124458892-1"
IMAGE = "us-west1-docker.pkg.dev/earnings-nerd/earningsnerd/backend@sha256:" + "a" * 64
CURRENT = (ROOT / "ops/feedback_media/verify_runtime.py").read_text()
PRIOR = "raise SystemExit('a previous run reviewed runtime')\n"  # another source a previous run was bound to
VERSIONS = {verify.KEY_SECRET: "1", verify.DB_SECRET: "1"}
EXPIRES = 1794452520  # the previous lease's end, in epoch seconds
CLEANUP_NOW = {"overrides": {"containerOverrides": [{"name": "verification", "env": [
    {"name": "FEEDBACK_VERIFY_MODE", "value": "cleanup_now"}]}]}}


def hashes(source):
    return {"runtime_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "verification_suite_sha256": "b" * 64, "frontend_tree": "c" * 40}


def stamp(seconds, fraction=".123456789"):
    """Cloud Run's RFC 3339 time: Z-normalized, with 0, 3, 6 or 9 fractional digits."""
    return datetime.fromtimestamp(EXPIRES + seconds, UTC).strftime(f"%Y-%m-%dT%H:%M:%S{fraction}Z")


def execution(after=1740, status="EXECUTION_SUCCEEDED", completed=True):
    """The job's latestCreatedExecution as Cloud Run reports it, created `after` seconds past the lease's end."""
    return {"name": "projects/p/locations/l/jobs/j/executions/j-x", "createTime": stamp(after),
            "completionStatus": status, **({"completionTime": stamp(after + 45)} if completed else {})}


def job(source=PRIOR, bound=None, latest=None):
    """The cleanup job a previous run left: its own source, bound to that run's hashes."""
    spec = verify.runtime_spec({"template": {}}, RUN_ID, IMAGE, hashes(bound or source), VERSIONS, job=True,
                               source=bound or source)
    spec["template"]["template"]["containers"][0]["args"] = ["-c", source]
    if latest is not None:
        spec["latestCreatedExecution"] = latest
    return spec


class Cloud:
    def __init__(self, previous):
        self.previous, self.calls = previous, []

    def call(self, api, path, *, method="GET", body=None, **_):
        self.calls.append((method, body))
        return self.previous if method == "GET" else {"done": True, "response": {"taskCount": 1, "succeededCount": 1}}

    def wait(self, operation):
        return operation["response"]


class Sql:
    """The isolated database: the previous run's marker row, with the runtime hash seed_marker recorded for it."""

    def __init__(self, expired="1", schema="1", recorded=None):
        self.expired, self.schema, self.statements = expired, schema, []
        self.recorded = hashes(PRIOR)["runtime_source_sha256"] if recorded is None else recorded

    def query(self, statement, *, env):
        self.statements.append(statement)
        if statement.startswith("SELECT (expires_at<=CURRENT_TIMESTAMP)"):
            assert RUN_ID in statement
            return self.expired
        if statement.startswith("SELECT (to_regclass('public.users')"):
            return self.schema
        if statement.startswith("SELECT runtime_source_sha256 FROM"):
            assert RUN_ID in statement
            return self.recorded
        assert statement.startswith("SELECT EXTRACT(EPOCH FROM expires_at)::bigint") and RUN_ID in statement
        return str(EXPIRES)


def settle(previous, sql=None):
    cloud = Cloud(previous)
    verify.settle_previous_run(cloud, sql or Sql(), {}, {"template": {}})
    return cloud


@pytest.mark.parametrize("fraction", ["", ".045", ".045123", ".045123456"])
def test_a_previous_source_settled_by_its_own_hourly_cleanup_is_never_executed(capsys, fraction):
    cloud = settle(job(latest={**execution(), "createTime": stamp(1740, fraction)}))
    assert cloud.calls == [("GET", None)]  # read back only: no execution, no write
    assert capsys.readouterr().out.strip() == (
        "Previous run used another runtime source; its own hourly cleanup succeeded after its lease expired "
        f"(execution created {stamp(1740)[:16]}Z): settled without executing it")


@pytest.mark.parametrize("latest", [
    None,  # the job reports no execution
    execution(after=-600),  # before the lease's end: its scheduled mode skipped a valid lease
    execution(after=30),  # within the minute after the end
    execution(status="EXECUTION_FAILED"),
    execution(status="EXECUTION_RUNNING", completed=False),
    execution(status="EXECUTION_CANCELLED"),
    execution(completed=False),
    {**execution(), "createTime": "not a time"},
    {**execution(), "completionTime": ""},
    {"createTime": stamp(1740)},
])
def test_a_previous_source_without_a_later_successful_cleanup_refuses_before_any_write(latest):
    cloud = Cloud(job(latest=latest))
    with pytest.raises(verify.media.OperationError, match="hourly cleanup has not succeeded since its lease expired"):
        verify.settle_previous_run(cloud, Sql(), {}, {"template": {}})
    assert cloud.calls == [("GET", None)]


def test_the_previous_source_is_held_to_the_hash_its_run_s_marker_recorded():
    """The job agreeing with itself is not enough: its source must be the one the run's marker row recorded."""
    sql = Sql(recorded="d" * 64)
    cloud = Cloud(job(latest=execution()))
    with pytest.raises(verify.media.OperationError, match="runtime source is not the one its run recorded"):
        verify.settle_previous_run(cloud, sql, {}, {"template": {}})
    assert cloud.calls == [("GET", None)] and not any("EXTRACT(EPOCH" in statement for statement in sql.statements)


def test_an_empty_previous_source_is_refused_even_when_its_hash_is_its_run_s():
    previous = job(latest=execution())
    container = previous["template"]["template"]["containers"][0]
    container["args"] = ["-c", ""]
    for row in container["env"]:
        if row["name"] == "FEEDBACK_VERIFY_RUNTIME_SHA256":
            row["value"] = hashlib.sha256(b"").hexdigest()
    sql = Sql(recorded=hashlib.sha256(b"").hexdigest())
    cloud = Cloud(previous)
    with pytest.raises(verify.media.OperationError, match="Previous cleanup differs from the bounded isolated contract"):
        verify.settle_previous_run(cloud, sql, {}, {"template": {}})
    assert cloud.calls == [("GET", None)] and sql.statements == []


def env_row(name, value):
    return lambda container: next(row for row in container["env"] if row["name"] == name).update(value=value)


@pytest.mark.parametrize("change, refusal", [
    # The run id reaches the SQL, so a quote in it must never pass.
    (env_row("FEEDBACK_VERIFY_RUN_ID", "1-1'; DROP TABLE x; --"), "inspect its retained manifest"),
    (lambda container: container.update(image="registry.example/other@sha256:" + "a" * 64), "inspect its retained manifest"),
    (lambda container: container.update(command=["python3"]), "inspect its retained manifest"),
    (env_row("FEEDBACK_VERIFY_MODE", "cleanup_now"), "inspect its retained manifest"),
    (env_row("FEEDBACK_MEDIA_BUCKET", "another-bucket"), "inspect its retained manifest"),
    (lambda container: next(row for row in container["env"] if row["name"] == "DATABASE_URL")["valueSource"]
     ["secretKeyRef"].update(secret="another-secret"), "inspect its retained manifest"),
    (lambda container: container["env"].append({"name": "EXTRA", "valueSource": {"secretKeyRef": {"secret": "s"}}}),
     "inspect its retained manifest"),
    (lambda container: container["resources"]["limits"].update(memory="1Gi"), "bounded isolated contract"),
    (env_row("FEEDBACK_VERIFY_SUITE_SHA256", "not a hash"), "bounded isolated contract"),
])
def test_a_previous_source_is_held_to_every_other_part_of_the_contract(change, refusal):
    """Only the source may differ from main's: a job differing anywhere else is refused before any SQL or execution."""
    previous = job(latest=execution())
    change(previous["template"]["template"]["containers"][0])
    sql = Sql()
    cloud = Cloud(previous)
    with pytest.raises(verify.media.OperationError, match=refusal):
        verify.settle_previous_run(cloud, sql, {}, {"template": {}})
    assert cloud.calls == [("GET", None)] and sql.statements == []


def test_a_previous_source_under_another_identity_is_refused():
    previous = job(latest=execution())
    previous["template"]["template"]["serviceAccount"] = "another@example.invalid"
    sql = Sql()
    cloud = Cloud(previous)
    with pytest.raises(verify.media.OperationError, match="cleanup authority differs"):
        verify.settle_previous_run(cloud, sql, {}, {"template": {}})
    assert cloud.calls == [("GET", None)] and sql.statements == []


def test_the_refusal_names_the_hourly_cleanup_s_own_minute():
    """The retry minute the refusal gives is the one ensure_schedule writes into the schedule's cron."""
    written = []

    class Scheduler:
        def call(self, api, path, *, method="GET", body=None, **_):
            if method != "GET":
                written.append(body)
            return None

    verify.ensure_schedule(Scheduler())
    minute = written[0]["schedule"].split()[0]
    with pytest.raises(verify.media.OperationError) as refusal:
        verify.settled_by_its_own_schedule({}, str(EXPIRES))
    assert str(refusal.value).endswith(f"retry after its next run at minute {minute}") and minute.isdecimal()


def test_the_previous_source_is_held_to_its_own_job_hash():
    """A job whose source is not the one its own env hash binds never counts, however its schedule ran."""
    cloud = Cloud(job(source=PRIOR, bound="raise SystemExit('the runtime the job env hash binds')\n", latest=execution()))
    with pytest.raises(verify.media.OperationError, match="Previous cleanup differs from the bounded isolated contract"):
        verify.settle_previous_run(cloud, Sql(), {}, {"template": {}})
    assert cloud.calls == [("GET", None)]


def test_an_oversized_previous_source_is_refused_even_when_its_hash_is_its_run_s():
    oversized = "#" * 32768 + "\n"
    previous = job(latest=execution())
    container = previous["template"]["template"]["containers"][0]
    container["args"] = ["-c", oversized]
    for row in container["env"]:
        if row["name"] == "FEEDBACK_VERIFY_RUNTIME_SHA256":
            row["value"] = hashlib.sha256(oversized.encode()).hexdigest()
    cloud = Cloud(previous)
    with pytest.raises(verify.media.OperationError, match="Previous cleanup differs from the bounded isolated contract"):
        verify.settle_previous_run(cloud, Sql(), {}, {"template": {}})
    assert cloud.calls == [("GET", None)]


@pytest.mark.parametrize("args", [None, [], ["-c"], ["-c", PRIOR, "--extra"], ["-m", PRIOR], ["-c", 5], "-c"])
def test_a_previous_job_whose_arguments_are_not_one_inline_source_is_refused(args):
    previous = job(latest=execution())
    container = previous["template"]["template"]["containers"][0]
    if args is None:
        del container["args"]
    else:
        container["args"] = args
    cloud = Cloud(previous)
    with pytest.raises(verify.media.OperationError, match="Previous cleanup differs; inspect its retained manifest"):
        verify.settle_previous_run(cloud, Sql(), {}, {"template": {}})
    assert cloud.calls == [("GET", None)]


@pytest.mark.parametrize("expired", ["0", ""])
def test_a_previous_source_with_an_active_or_unknown_lease_still_waits_for_it(expired):
    sql = Sql(expired=expired)
    cloud = Cloud(job(latest=execution()))
    with pytest.raises(verify.media.OperationError, match="lease is still active or unreadable"):
        verify.settle_previous_run(cloud, sql, {}, {"template": {}})
    assert cloud.calls == [("GET", None)] and len(sql.statements) == 1


def test_a_previous_source_that_never_made_its_schema_has_nothing_to_settle():
    sql = Sql(schema="0")
    cloud = settle(job(latest=None), sql)  # no execution evidence is needed: it made no fixture or object
    assert cloud.calls == [("GET", None)] and len(sql.statements) == 2


def test_main_s_own_source_still_settles_through_cleanup_now():
    """The unchanged path: a previous run bound to main's runtime is settled by executing its job with cleanup_now."""
    cloud = settle(job(source=CURRENT, latest=execution(after=-600)))
    assert cloud.calls[0] == ("GET", None) and cloud.calls[-1] == ("POST", CLEANUP_NOW)


def test_runtime_spec_names_main_s_source_unless_given_one_its_hashes_bind():
    current = verify.runtime_spec({"template": {}}, RUN_ID, IMAGE, hashes(CURRENT), VERSIONS, job=True)
    assert current["template"]["template"]["containers"][0]["args"] == ["-c", CURRENT]
    prior = verify.runtime_spec({"template": {}}, RUN_ID, IMAGE, hashes(PRIOR), VERSIONS, job=True, source=PRIOR)
    assert prior["template"]["template"]["containers"][0]["args"] == ["-c", PRIOR]
    with pytest.raises(verify.media.OperationError, match="Verification runtime changed after its fingerprint"):
        verify.runtime_spec({"template": {}}, RUN_ID, IMAGE, hashes(CURRENT), VERSIONS, job=True, source=PRIOR)
