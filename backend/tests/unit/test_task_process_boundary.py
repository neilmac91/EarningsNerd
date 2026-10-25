"""A real child/thread cannot survive deadline, handler cancellation or acknowledgement."""
from __future__ import annotations

import asyncio
import gzip
import io
import json
import logging
import os
import socket
import subprocess
import sys
import threading
import uuid
import zlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import httpx

from app.config import settings
from app.services import task_process_service as service
from app.services.durable_tasks import TaskEnvelope

BACKEND_DIR = Path(__file__).resolve().parents[2]


@pytest.fixture
def preserve_worker_logging():
    """The private entrypoint configures process logging on its first import."""
    root = logging.getLogger()
    handlers, level = list(root.handlers), root.level
    library_levels = {name: logging.getLogger(name).level
                      for name in ("httpx", "httpcore", "urllib3", "edgar", "markdown_it")}
    try:
        yield
    finally:
        for handler in root.handlers:
            if handler not in handlers:
                handler.close()
        root.handlers[:] = handlers
        root.setLevel(level)
        for name, previous_level in library_levels.items():
            logging.getLogger(name).setLevel(previous_level)


@pytest.mark.asyncio
@pytest.mark.parametrize("cancel_request", [False, True])
async def test_running_native_work_is_killed_and_reaped_before_request_ends(monkeypatch, tmp_path, cancel_request):
    monkeypatch.setattr(settings, "TASKS_WORKER_PROCESS", True)
    monkeypatch.setattr(settings, "TASKS_WORK_TIMEOUT_SECONDS", 0.25)
    ready = tmp_path / "started"
    script = (
        "import threading,time,pathlib,sys; "
        "threading.Thread(target=lambda:time.sleep(60)).start(); "
        "pathlib.Path(sys.argv[1]).write_text('ready'); sys.stdin.read(); time.sleep(60)"
    )
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", script, str(ready)))
    children = []
    registered_and_ready = asyncio.Event()
    create = asyncio.create_subprocess_exec

    async def record(*args, **kwargs):
        process = await create(*args, **kwargs)
        children.append(process)
        # Start the tested work deadline only once the controlled native thread is running.
        # OS/Python startup under load is not the behavior this cleanup test measures.
        try:
            async with asyncio.timeout(2):
                while not ready.exists():
                    await asyncio.sleep(0.005)
        except BaseException:
            if process.returncode is None:
                process.kill()
            await process.wait()
            raise
        registered_and_ready.set()
        return process

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", record)
    task = asyncio.create_task(service.run_task_process(TaskEnvelope(kind="companyfacts", payload={"company_id": 7})))
    async with asyncio.timeout(2):
        # The child's ready file can precede the parent recording its process handle.
        await registered_and_ready.wait()
    assert children[0].returncode is None
    with pytest.raises(RuntimeError, match="busy; retry delivery"):
        await service.run_task_process(TaskEnvelope(kind="companyfacts", payload={"company_id": 8}))
    assert len(children) == 1
    if cancel_request:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel_request else TimeoutError):
        await task
    assert children[0].returncode is not None and children[0].returncode < 0
    assert await children[0].wait() == children[0].returncode
    # The next delivery is admitted after cleanup; neither deadline nor cancellation strands
    # the sole child permit. Use a real fast child rather than reading the lock's internal state.
    monkeypatch.setattr(settings, "TASKS_WORK_TIMEOUT_SECONDS", 2)
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", "import sys; sys.stdin.read()"))
    await service.run_task_process(TaskEnvelope(kind="companyfacts", payload={"company_id": 9}))
    assert len(children) == 2 and children[1].returncode == 0


@pytest.mark.asyncio
async def test_worker_reports_process_failure_and_rejects_api_execution(monkeypatch):
    monkeypatch.setattr(settings, "TASKS_WORKER_PROCESS", False)
    envelope = TaskEnvelope(kind="companyfacts", payload={"company_id": 7})
    with pytest.raises(RuntimeError, match="private worker"):
        await service.run_task_process(envelope)
    monkeypatch.setattr(settings, "TASKS_WORKER_PROCESS", True)
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", "import sys; sys.stdin.read(); sys.exit(1)"))
    with pytest.raises(RuntimeError, match="retry delivery"):
        await service.run_task_process(envelope)
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", "import json,sys; assert json.load(sys.stdin)['payload']=={'company_id':7}"))
    await service.run_task_process(envelope)


@pytest.mark.asyncio
async def test_private_asgi_worker_has_its_own_work_deadline(monkeypatch, preserve_worker_logging):
    # A fresh interpreter catches eager package imports hidden by pytest's loaded API modules.
    probe = subprocess.run(
        [sys.executable, "-c", "import task_worker_main,sys,logging; "
         "assert not {'main','app.database','app.models','app.routers.analysis'} & sys.modules.keys(); "
         "assert all(not logging.getLogger(name).isEnabledFor(logging.INFO) "
         "for name in ('httpx','httpcore','urllib3','edgar')); "
         "logging.getLogger('httpx').info('apikey=synthetic-test-credential'); "
         "logging.getLogger(__name__).info('Worker ready')"],
        capture_output=True, text=True, timeout=15,
    )
    assert probe.returncode == 0, probe.stderr
    assert "Worker ready" in probe.stdout
    assert "synthetic-test-credential" not in probe.stdout + probe.stderr
    # A fresh exec does not inherit the parent's logger levels. Exercise child startup too,
    # replacing only business work so this logging check cannot query a database or provider.
    child_probe = subprocess.run(
        [sys.executable, "-c", "import asyncio,io,sys,logging; "
         "from app.services import task_process as process; "
         "process.run_background_task=lambda envelope: asyncio.sleep(0); "
         "sys.stdin=io.StringIO('{\"kind\":\"probe\",\"payload\":{}}'); "
         "assert process.main()==0; "
         "assert all(not logging.getLogger(name).isEnabledFor(logging.INFO) "
         "for name in ('httpx','httpcore','urllib3','edgar')); "
         "logging.getLogger('httpx').info('apikey=synthetic-test-credential'); "
         "logging.getLogger(__name__).info('Child ready')"],
        capture_output=True, text=True, timeout=15,
    )
    assert child_probe.returncode == 0, child_probe.stderr
    assert "Child ready" in child_probe.stdout
    assert "synthetic-test-credential" not in child_probe.stdout + child_probe.stderr
    import main
    import task_worker_main
    from app.routers import tasks

    monkeypatch.setitem(main.REQUEST_TIMEOUT_SECONDS, "default", 0.001)
    completed = False

    async def work(_envelope):
        nonlocal completed
        await asyncio.sleep(0.02)
        completed = True

    monkeypatch.setattr(tasks, "run_background_task", work)
    task_worker_main.app.dependency_overrides[tasks.require_task_identity] = lambda: None
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=task_worker_main.app), base_url="http://test") as client:
            response = await client.post("/internal/tasks/execute", json={"kind": "companyfacts", "payload": {"company_id": 7}})
        assert response.status_code == 200 and completed
        assert response.json() == {"status": "completed"}
    finally:
        task_worker_main.app.dependency_overrides.clear()



# ---- F50: a real child's failure reaches Sentry sanitized; telemetry never changes a task's result or a response ----


class _Ingest:
    """A loopback Sentry ingest (no DNS, inside the network gate's loopback allowance): every envelope POSTed to it,
    decompressed as sent (brotli, which requirements.txt pins and the SDK therefore uses, gzip or deflate)."""

    def __init__(self):
        self.bodies, self.paths = [], []
        ingest = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                import brotli

                raw = self.rfile.read(int(self.headers["Content-Length"]))
                decode = {"br": brotli.decompress, "gzip": gzip.decompress, "deflate": zlib.decompress}
                ingest.bodies.append(decode.get(self.headers.get("Content-Encoding", ""), bytes)(raw))
                ingest.paths.append(self.path)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"{}")

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.port = self.server.server_address[1]
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def items(self):
        from sentry_sdk.envelope import Envelope

        return [(item.type, item.payload.json) for body in self.bodies for item in Envelope.deserialize(body).items]

    def close(self):
        self.server.shutdown()
        self.server.server_close()


def _sentinels() -> dict[str, str]:
    """Drawn at run time: an event's frames carry the source lines around each raise, where a literal would show."""
    tag = uuid.uuid4().hex[:12]
    return {"email": f"f50-{tag}@example.com", "token": f"TOKEN{tag.upper()}PADDING", "word": f"WORD{tag.upper()}",
            "release": f"f50-release-{tag}", "key": f"key{tag}"}


def _child_env(dsn: str, **extra: str) -> dict[str, str]:
    return {**os.environ, "SENTRY_DSN": dsn, "ENVIRONMENT": "staging", **extra}


@pytest.mark.asyncio
async def test_a_fresh_task_process_reports_its_failure_without_its_content(monkeypatch, capfd):
    # AC1: the real exec boundary, run_task_process with its own `_command()` (`python -m app.services.task_process`),
    # the worker's environment (a DSN on a loopback ingest, the release CI sets). This process starts no Sentry, so
    # every event the ingest gets is the child's. A companyfacts payload that fails validation quotes its input.
    import sentry_sdk

    assert not sentry_sdk.is_initialized()
    assert service._command() == (sys.executable, "-m", "app.services.task_process")
    sentinel, ingest = _sentinels(), _Ingest()
    monkeypatch.setattr(settings, "TASKS_WORKER_PROCESS", True)
    monkeypatch.setattr(settings, "TASKS_WORK_TIMEOUT_SECONDS", 60)  # a hung child fails here, not in 8 minutes
    monkeypatch.setenv("SENTRY_DSN", f"http://{sentinel['key']}@127.0.0.1:{ingest.port}/42")
    monkeypatch.setenv("SENTRY_RELEASE", sentinel["release"])
    monkeypatch.setenv("ENVIRONMENT", "staging")
    monkeypatch.setenv("INTERNAL_JOB_TOKEN", sentinel["token"])
    payload = {"company_id": sentinel["word"], "contact": sentinel["email"], "note": sentinel["token"]}
    try:
        with pytest.raises(RuntimeError, match="Isolated task failed; retry delivery"):
            await service.run_task_process(TaskEnvelope(kind="companyfacts", payload=payload))
    finally:
        ingest.close()
    out, err = capfd.readouterr()
    assert sentinel["word"] in out + err and sentinel["email"] in out + err  # the child's own log line quoted them
    assert "Sentry" not in out + err  # no startup line, no exit-time wait message
    assert ingest.paths == ["/api/42/envelope/"]
    ((item_type, event),) = ingest.items()
    assert item_type == "event"
    assert event["release"] == sentinel["release"] and event["environment"] == "staging"
    assert event.keys() <= {"event_id", "timestamp", "level", "platform", "logger", "release", "environment",
                            "server_name", "sdk", "exception", "contexts", "tags"}
    assert event["tags"] == {"task.kind": "companyfacts"}
    ((exception),) = event["exception"]["values"]
    assert exception["type"] == "ValidationError" and "value" not in exception
    frames = [(frame.get("module"), frame["function"]) for frame in exception["stacktrace"]["frames"]]
    assert ("__main__", "main") in frames and ("app.services.background_task_runner", "run_background_task") in frames
    assert all("vars" not in frame for frame in exception["stacktrace"]["frames"])
    sent = b"".join(ingest.bodies).decode("utf-8", "replace")
    for name in ("email", "token", "word", "key"):
        assert sentinel[name] not in sent, name
    assert os.environ["SECRET_KEY"] not in sent and "example.com" not in sent


def _blackhole() -> socket.socket:
    listener = socket.socket()
    listener.bind(("127.0.0.1", 0))
    listener.listen(8)  # takes connections into its backlog and never answers
    return listener


@pytest.mark.parametrize("outcome", ["failure", "success"])
@pytest.mark.parametrize("sink", ["refused", "blackhole"])
def test_a_task_child_whose_sentry_cannot_send_keeps_its_result(sink, outcome):
    # AC3/AC4: an ingest that refuses or never answers changes no exit code; a success never loads the SDK; a failure
    # waits once, at most TASK_FLUSH_SECONDS (every flush the client runs is recorded, an exit-time close included),
    # and nothing waits again at exit. Only a lower bound is timed (tests/unit/test_wall_clock_bounds.py).
    from app.utils.telemetry_bootstrap import TASK_FLUSH_SECONDS

    listener = _blackhole()
    port = listener.getsockname()[1]
    if sink == "refused":
        listener.close()
    stdin = '{"kind":"companyfacts","payload":{"company_id":"x"}}' if outcome == "failure" else '{"kind":"probe","payload":{}}'
    script = (
        "import asyncio,io,sys,time\n"
        "import sentry_sdk.client as c\n"
        "flush = c._Client.flush\n"
        "def recorded(self, timeout=None, callback=None):\n"
        "    print(f'FLUSH={timeout}', file=sys.stderr, flush=True)\n"
        "    return flush(self, timeout=timeout, callback=callback)\n"
        "c._Client.flush = recorded\n"
        "from app.services import task_process as p\n"
        + ("p.run_background_task = lambda envelope: asyncio.sleep(0)\n" if outcome == "success" else "")
        + f"sys.stdin = io.StringIO({stdin!r})\n"
        "began = time.monotonic(); code = p.main(); print(f'MAIN={time.monotonic() - began:.3f}', file=sys.stderr)\n"
        "raise SystemExit(code)\n"
    )
    try:
        child = subprocess.run([sys.executable, "-c", script], cwd=BACKEND_DIR,
                               env=_child_env(f"http://k@127.0.0.1:{port}/42", SENTRY_RELEASE="f50"),
                               capture_output=True, text=True, timeout=60)
    finally:
        listener.close()
    assert child.returncode == (1 if outcome == "failure" else 0), child.stderr
    flushes = [line.partition("=")[2] for line in child.stderr.splitlines() if line.startswith("FLUSH=")]
    assert flushes == ([str(TASK_FLUSH_SECONDS)] if outcome == "failure" else [])
    assert "Sentry is attempting" not in child.stderr
    if sink == "blackhole" and outcome == "failure":
        waited = float(child.stderr.rpartition("MAIN=")[2].split()[0])
        assert waited >= TASK_FLUSH_SECONDS - 0.2  # the wait was entered; its bound is the recorded timeout above


def test_a_successful_task_child_never_loads_the_sdk():
    ingest = _Ingest()
    try:
        child = subprocess.run(
            [sys.executable, "-c", "import asyncio,io,sys; from app.services import task_process as p; "
             "p.run_background_task=lambda envelope: asyncio.sleep(0); "
             "sys.stdin=io.StringIO('{\"kind\":\"probe\",\"payload\":{}}'); "
             "assert p.main()==0; assert 'sentry_sdk' not in sys.modules"],
            cwd=BACKEND_DIR, env=_child_env(f"http://k@127.0.0.1:{ingest.port}/42"),
            capture_output=True, text=True, timeout=60,
        )
    finally:
        ingest.close()
    assert child.returncode == 0, child.stderr
    assert ingest.bodies == []


def test_the_bootstrap_starts_nothing_on_import_and_each_process_starts_sentry_once():
    # AC3: importing the leaf loads no SDK, app, database, model, router or service and starts no thread; the worker's
    # import starts Sentry once and still loads none of the API's modules; importing main after it in the same process
    # keeps the worker's client (no second init) and prints none of the four startup lines.
    leaf = subprocess.run(
        [sys.executable, "-c", "import sys,threading; import app.utils.telemetry_bootstrap; "
         "loaded={m for m in sys.modules if m.split('.')[0] in {'main','task_worker_main','sentry_sdk','fastapi','starlette'} "
         "or m.startswith(('sqlalchemy.orm','app.database','app.models','app.routers','app.services'))}; "
         "assert not loaded, loaded; assert threading.active_count()==1"],
        cwd=BACKEND_DIR, capture_output=True, text=True, timeout=30,
    )
    assert leaf.returncode == 0, leaf.stderr
    both = subprocess.run(
        [sys.executable, "-c", "import sys; import task_worker_main; from app.utils import telemetry_bootstrap as t; "
         "assert not {'main','app.database','app.models','app.routers.analysis'} & sys.modules.keys(); "
         "import sentry_sdk; client = sentry_sdk.get_client(); assert t._started == 'worker'; "
         "assert sorted(client.integrations) == ['atexit','dedupe','logging'], sorted(client.integrations); "
         "assert client.options['max_request_body_size'] == 'never'; print('WORKER-DONE', flush=True); "
         "import main; assert sentry_sdk.get_client() is client and t._started == 'worker'"],
        cwd=BACKEND_DIR, env=_child_env("http://k@127.0.0.1:9/42"), capture_output=True, text=True, timeout=60,
    )
    assert both.returncode == 0, both.stderr
    assert "Sentry error tracking: initialized" in both.stdout
    after = both.stdout.partition("WORKER-DONE")[2]
    assert not any(line in after for line in ("Sentry error tracking initialized", "Sentry initialization failed",
                                              "SENTRY_DSN not configured", "Sentry SDK not available"))


@pytest.mark.parametrize("shape", ["https://pub:{}/42", "http://k@127.0.0.1/{}"])
def test_a_worker_whose_sentry_start_fails_logs_its_status_alone(shape):
    # The SDK's error for a malformed DSN quotes the part it could not parse (the port, the project): the worker logs its
    # start's status alone, never that text, and still starts. The fragment is drawn at run time.
    fragment = f"fab{uuid.uuid4().hex[:12]}"
    worker = subprocess.run(
        [sys.executable, "-c", "import task_worker_main"], cwd=BACKEND_DIR, env=_child_env(shape.format(fragment)),
        capture_output=True, text=True, timeout=60,
    )
    assert worker.returncode == 0, worker.stderr
    output = worker.stdout + worker.stderr
    lines = [line for line in output.splitlines() if "Sentry error tracking" in line]
    assert len(lines) == 1 and lines[0].endswith("Sentry error tracking: failed"), lines
    assert fragment not in output


class _Halt(BaseException):
    """Not an Exception, as KeyboardInterrupt and SystemExit are not."""


@pytest.fixture
def task_telemetry(monkeypatch):
    """The bootstrap with a DSN and a test transport that keeps, or raises; the client is removed afterwards."""
    import sentry_sdk
    from sentry_sdk.transport import Transport

    from app.utils import telemetry_bootstrap

    dsn = "http://fabricated@127.0.0.1:9/1"
    state = {"raise": None, "items": []}

    class Ingest(Transport):
        def __init__(self):
            super().__init__({"dsn": dsn})

        def capture_envelope(self, envelope):
            if state["raise"] is not None:
                raise state["raise"]("transport down")
            state["items"] += [(item.type, item.payload.json) for item in envelope.items]

        def flush(self, timeout, callback=None):
            if state["raise"] is not None:
                raise state["raise"]("transport down")

    build = telemetry_bootstrap._task_sentry_options
    monkeypatch.setattr(telemetry_bootstrap, "_task_sentry_options", lambda: {**build(), "transport": Ingest()})
    monkeypatch.setattr(telemetry_bootstrap.settings, "SENTRY_DSN", dsn)
    monkeypatch.setattr(telemetry_bootstrap, "_started", None)
    try:
        yield state
    finally:
        state["raise"] = None
        try:
            sentry_sdk.get_client().close()
        finally:
            sentry_sdk.get_global_scope().set_client(None)


@pytest.mark.parametrize("failure", [None, OSError, _Halt, "init", "unconfigured"])
def test_a_failed_task_exits_1_whatever_its_telemetry_does(monkeypatch, task_telemetry, failure, preserve_worker_logging):
    from app.services import task_process
    from app.utils import telemetry_bootstrap

    mailbox = uuid.uuid4().hex
    task_telemetry["raise"] = failure if isinstance(failure, type) else None
    if failure == "init":  # every placeholder overlaps a weak secret: the options raise, Sentry stays off
        for name, word in {"IP_HASH_SALT": "Filtered", "FMP_API_KEY": "Withheld", "POSTHOG_API_KEY": "Redacted"}.items():
            monkeypatch.setattr(telemetry_bootstrap.settings, name, word)
    if failure == "unconfigured":
        monkeypatch.setattr(telemetry_bootstrap.settings, "SENTRY_DSN", "")
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps({"kind": "companyfacts", "payload": {"company_id": f"{mailbox}@example.com"}})))
    assert task_process.main() == 1
    if failure is None:
        ((kind, event),) = task_telemetry["items"]
        assert kind == "event" and event["tags"] == {"task.kind": "companyfacts"} and mailbox not in json.dumps(event)
    else:
        assert task_telemetry["items"] == []
    if failure in ("init", "unconfigured"):
        assert telemetry_bootstrap._started is None


_WORKER = """
import asyncio, json, sys
import httpx
from sentry_sdk.transport import Transport
from app.utils import telemetry_bootstrap
mode, email, token = sys.argv[1:4]
sent = []
class Ingest(Transport):
    def capture_envelope(self, envelope):
        if mode == "raise":
            raise OSError("transport down")
        sent.extend(item.payload.json for item in envelope.items)
build = telemetry_bootstrap._task_sentry_options
telemetry_bootstrap._task_sentry_options = lambda: {**build(), "transport": Ingest()}
import task_worker_main  # Sentry starts at import, before the app's first request builds its middleware
from app.routers import tasks
assert telemetry_bootstrap._started == "worker"
async def fail(envelope):
    raise RuntimeError(f"failed for {email} with {json.dumps(envelope.payload)}")
async def succeed(envelope):
    return None
task_worker_main.app.dependency_overrides[tasks.require_task_identity] = lambda: None
body = {"kind": "account_mail", "payload": {"email": email, "mail": "verification"}}
async def deliver():
    statuses = []
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=task_worker_main.app), base_url="http://test") as client:
        for work in (fail, succeed):
            tasks.run_background_task = work
            response = await client.post("/internal/tasks/execute", json=body, headers={"Authorization": "Bearer " + token})
            statuses.append(response.status_code)
    return statuses
print("STATUSES " + json.dumps(asyncio.run(deliver())))
import sentry_sdk
sentry_sdk.flush()
print("SENT " + json.dumps(sent))
"""


@pytest.mark.parametrize("mode", ["keep", "raise"])
def test_the_worker_answers_alike_and_sends_no_task_content(mode):
    # AC2/AC4: a fresh worker, Sentry started at import as in production. A failed delivery still answers 503 and a
    # completed one 200 when the transport raises; the one event a failure sends (the router's log line) carries neither
    # the body's address nor the token, though the work's exception quotes the address and the payload and the request
    # carries the token.
    sentinel = _sentinels()
    worker = subprocess.run(
        [sys.executable, "-c", _WORKER, mode, sentinel["email"], sentinel["token"]], cwd=BACKEND_DIR,
        env=_child_env("http://k@127.0.0.1:9/42", TASKS_WORKER_PROCESS="true"), capture_output=True, text=True,
        timeout=60,
    )
    assert worker.returncode == 0, worker.stderr
    lines = dict(line.split(" ", 1) for line in worker.stdout.splitlines() if line.startswith(("STATUSES ", "SENT ")))
    assert json.loads(lines["STATUSES"]) == [503, 200]
    sent = json.loads(lines["SENT"])
    assert sentinel["email"] not in lines["SENT"] and sentinel["token"] not in lines["SENT"]
    if mode == "keep":
        (event,) = sent
        assert [value["type"] for value in event["exception"]["values"]] == ["RuntimeError"]
        assert event["logger"] == "app.routers.tasks" and "request" not in event
    else:
        assert sent == []
