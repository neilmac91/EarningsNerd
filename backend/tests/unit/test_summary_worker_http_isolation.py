"""Two real HTTP workers and supervised children isolate mail from a held summary.

This is an offline process-boundary proof, not Cloud Tasks or Cloud Run acceptance.
The real worker app, role checks, RS256 identity verification and child supervisor run.
Google's public-key reader is replaced by a local test key, and the business child
command is a fixture that never imports database, SEC, model or mail code. No queue
transport is exercised. Both HTTP listeners bind loopback; each fresh interpreter
starts in an empty temporary directory with an explicit synthetic environment.
"""
from __future__ import annotations

import asyncio
import json
import os
import signal
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from app.utils.datetimes import utcnow


BACKEND_DIR = Path(__file__).resolve().parents[2]
BACKGROUND_URL = "https://background-isolation-uw.a.run.app"
SUMMARY_URL = "https://summary-isolation-uw.a.run.app"
BACKGROUND_INVOKER = "background@test-project.iam.gserviceaccount.com"
SUMMARY_INVOKER = "summary@test-project.iam.gserviceaccount.com"

_BUSINESS_CHILD = """
import json, os, pathlib, sys, time
root = pathlib.Path(sys.argv[1])
envelope = json.load(sys.stdin)
kind = envelope["kind"]
(root / (kind + ".started")).write_text(str(os.getpid()))
if kind == "summary":
    while not (root.parent / "release-summary").exists():
        time.sleep(0.01)
"""

_HTTP_WORKER = """
import json, pathlib, socket, sys
import uvicorn
from app.services import durable_tasks, task_process_service
key = json.loads(pathlib.Path(sys.argv[2]).read_text())
async def local_keys():
    return {"keys": [key]}
durable_tasks._get_google_jwks = local_keys
task_process_service._command = lambda: (sys.executable, sys.argv[3], sys.argv[4])
import task_worker_main
listener = socket.socket(fileno=int(sys.argv[1]))
config = uvicorn.Config(task_worker_main.app, loop="asyncio", http="h11",
                        lifespan="off", log_level="error", access_log=False,
                        timeout_graceful_shutdown=1)
uvicorn.Server(config).run(sockets=[listener])
"""


@dataclass
class _Worker:
    process: subprocess.Popen
    url: str
    directory: Path
    log: Path


def _start_worker(root: Path, role: str, public_key: Path, child: Path) -> _Worker:
    directory = root / role
    directory.mkdir()
    log = directory / "worker.log"
    # Deliberately do not inherit the parent's credentials, .env, proxy or provider
    # configuration. This fixture has only loopback sockets and a local JWKS reader.
    environment = {
        "PATH": os.defpath,
        "PYTHONPATH": str(BACKEND_DIR),
        "PYTHONUNBUFFERED": "1",
        "SECRET_KEY": uuid4().hex,
        "ENVIRONMENT": "test",
        "SKIP_REDIS_INIT": "true",
        "DURABLE_TASKS_ENABLED": "true",
        "TASKS_PROJECT_ID": "test-project",
        "TASKS_LOCATION": "us-west1",
        "TASKS_QUEUE": "background",
        "TASKS_WORKER_URL": BACKGROUND_URL,
        "TASKS_INVOKER_EMAIL": BACKGROUND_INVOKER,
        "SUMMARY_TASKS_QUEUE": "summary",
        "SUMMARY_TASKS_WORKER_URL": SUMMARY_URL,
        "SUMMARY_TASKS_INVOKER_EMAIL": SUMMARY_INVOKER,
        "TASKS_WORKER_ROLE": role,
        "TASKS_WORKER_PROCESS": "true",
        "TASKS_WORK_TIMEOUT_SECONDS": "30",
    }
    with socket.socket() as listener, log.open("wb") as output:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        process = subprocess.Popen(
            [sys.executable, "-c", _HTTP_WORKER, str(listener.fileno()),
             str(public_key), str(child), str(directory)],
            cwd=directory, env=environment, pass_fds=(listener.fileno(),),
            start_new_session=True, stdout=output, stderr=subprocess.STDOUT,
        )
    return _Worker(process, f"http://127.0.0.1:{port}", directory, log)


def _assert_alive(worker: _Worker) -> None:
    assert worker.process.poll() is None, worker.log.read_text()[-4000:]


async def _ready(client: httpx.AsyncClient, worker: _Worker) -> None:
    async with asyncio.timeout(15):
        while True:
            _assert_alive(worker)
            try:
                response = await client.get(worker.url + "/health", timeout=0.5)
                if response.status_code == 200:
                    return
            except httpx.TransportError:
                pass
            await asyncio.sleep(0.01)


async def _child_started(worker: _Worker, kind: str) -> None:
    async with asyncio.timeout(10):
        while not (worker.directory / (kind + ".started")).exists():
            _assert_alive(worker)
            await asyncio.sleep(0.01)


def _stop(worker: _Worker) -> None:
    # Each worker is its own process group; fixture descendants stay in that group.
    # Graceful shutdown lets the real supervisor reap its child, and the final group
    # kill closes the failure path even if worker startup/teardown itself hung.
    try:
        if worker.process.poll() is None:
            worker.process.terminate()
            try:
                worker.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
    finally:
        try:
            os.killpg(worker.process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        worker.process.wait(timeout=5)


@pytest.mark.skipif(os.name != "posix", reason="Cloud Run process-group proof requires POSIX")
@pytest.mark.asyncio
async def test_background_mail_finishes_while_summary_child_remains_held(tmp_path):
    signing_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(signing_key.public_key()))
    jwk["kid"] = "offline-worker-key"
    public_key = tmp_path / "public-key.json"
    public_key.write_text(json.dumps(jwk))
    child = tmp_path / "business-child.py"
    child.write_text(_BUSINESS_CHILD)
    release = tmp_path / "release-summary"

    def bearer(audience: str, email: str) -> dict[str, str]:
        token = jwt.encode(
            {"iss": "https://accounts.google.com", "aud": audience, "sub": "1234",
             "email": email, "email_verified": True,
             "exp": int(utcnow().timestamp()) + 120},
            signing_key, algorithm="RS256", headers={"kid": jwk["kid"]},
        )
        return {"Authorization": "Bearer " + token}

    workers = []
    summary_request = None
    try:
        background = _start_worker(tmp_path, "background", public_key, child)
        workers.append(background)
        summary = _start_worker(tmp_path, "summary", public_key, child)
        workers.append(summary)
        async with httpx.AsyncClient(timeout=15) as client:
            await asyncio.gather(_ready(client, background), _ready(client, summary))
            summary_body = {"kind": "summary", "payload": {"job_id": uuid4().hex, "generation": 1}}
            mail_body = {"kind": "account_mail", "payload": {"email": "reader@example.test", "mail": "verification"}}
            background_auth = bearer(BACKGROUND_URL, BACKGROUND_INVOKER)
            summary_auth = bearer(SUMMARY_URL, SUMMARY_INVOKER)

            # A valid token for the other worker is refused by real JWT verification.
            rejected_identity = await client.post(
                summary.url + "/internal/tasks/execute", json=summary_body, headers=background_auth,
            )
            assert rejected_identity.status_code == 401
            # Even a token valid for this worker cannot change its accepted task lane.
            for worker, body, authorization in (
                (background, summary_body, background_auth),
                (summary, mail_body, summary_auth),
            ):
                refused = await client.post(worker.url + "/internal/tasks/execute", json=body, headers=authorization)
                assert refused.status_code == 503
            assert list(tmp_path.glob("*/*.started")) == []

            summary_request = asyncio.create_task(client.post(
                summary.url + "/internal/tasks/execute", json=summary_body, headers=summary_auth,
            ))
            await _child_started(summary, "summary")
            assert not summary_request.done()

            delivered = await client.post(
                background.url + "/internal/tasks/execute", json=mail_body, headers=background_auth,
            )
            assert delivered.status_code == 200
            assert delivered.json() == {"status": "completed"}
            assert (background.directory / "account_mail.started").exists()
            assert not release.exists() and not summary_request.done()
            assert (summary.directory / "summary.started").read_text() != (
                background.directory / "account_mail.started"
            ).read_text()

            release.touch()
            finished = await asyncio.wait_for(summary_request, timeout=10)
            assert finished.status_code == 200
            assert finished.json() == {"status": "completed"}
    finally:
        release.touch()
        if summary_request is not None and not summary_request.done():
            summary_request.cancel()
            await asyncio.gather(summary_request, return_exceptions=True)
        for worker in reversed(workers):
            _stop(worker)
