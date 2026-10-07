"""A real child/thread cannot survive deadline, disconnect or successful acknowledgement."""
from __future__ import annotations

import asyncio
import sys

import pytest
import httpx

from app.config import settings
from app.services import task_process_service as service
from app.services.durable_tasks import TaskEnvelope


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
    create = asyncio.create_subprocess_exec

    async def record(*args, **kwargs):
        process = await create(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", record)
    task = asyncio.create_task(service.run_task_process(TaskEnvelope(kind="companyfacts", payload={"company_id": 7})))
    async with asyncio.timeout(2):
        while not ready.exists():
            await asyncio.sleep(0.005)
    assert children[0].returncode is None
    if cancel_request:
        task.cancel()
    with pytest.raises(asyncio.CancelledError if cancel_request else TimeoutError):
        await task
    assert children[0].returncode is not None and children[0].returncode < 0
    assert await children[0].wait() == children[0].returncode


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
async def test_private_asgi_worker_has_its_own_work_deadline(monkeypatch):
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
