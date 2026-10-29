"""Storage SDK work cannot survive its deadline, consume unbounded IPC, or inherit secrets."""
from __future__ import annotations

import asyncio
import io
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from app.services import feedback_storage_worker_service as service


BUCKET = "feedback-worker-fixture"
KEY = "feedback/" + "a" * 32 + "/" + "b" * 32 + ".png"
PNG = b"\x89PNG\r\n\x1a\nfixture-pixels"


async def _cleanup(children):
    for child in children:
        if child.returncode is None:
            child.kill()
        await child.communicate()


def test_sync_job_facade_uses_bounded_operations_and_checks_result_types(monkeypatch):
    calls = []
    response = "17"

    async def operation(*args, **kwargs):
        calls.append((args, kwargs))
        return response

    monkeypatch.setattr(service, "run_feedback_storage_operation", operation)
    adapter = service.BoundedFeedbackStorage(BUCKET)
    assert adapter.upload(KEY, PNG) == "17"
    assert calls[-1] == ((BUCKET, "upload", KEY), {"data": PNG, "generation": None})
    response = PNG
    assert adapter.download(KEY, "17") == PNG
    assert calls[-1] == ((BUCKET, "download", KEY), {"data": None, "generation": "17"})
    response = "17"
    assert adapter.delete(KEY, "17") == "17"
    response = None
    assert adapter.delete(KEY, None) is None
    assert calls[-1] == ((BUCKET, "delete", KEY), {"data": None, "generation": None})
    assert adapter.verify_permissions() is None
    assert calls[-1] == ((BUCKET, "verify_permissions", ""), {"data": None, "generation": None})
    response = 17
    for call in (lambda: adapter.upload(KEY, PNG), lambda: adapter.download(KEY, "17"),
                 lambda: adapter.delete(KEY, "17"), adapter.verify_permissions):
        with pytest.raises(service.FeedbackStorageError, match="^invalid_storage_protocol$"):
            call()


@pytest.mark.asyncio
async def test_sync_job_facade_refuses_running_api_loop_without_starting_work(monkeypatch):
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("Sync facade started work on an API event loop")

    monkeypatch.setattr(service, "run_feedback_storage_operation", forbidden)
    with pytest.raises(service.FeedbackStorageError, match="^invalid_storage_operation$"):
        service.BoundedFeedbackStorage(BUCKET).delete(KEY, None)


@pytest.fixture
def fake_adapter_worker(tmp_path, monkeypatch):
    """The real child protocol runs; only the provider boundary is replaced in that child."""
    script = tmp_path / "storage_boundary.py"
    backend = str(Path(service.__file__).resolve().parents[2])
    script.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, {backend!r})\n"
        "from app.services import feedback_storage_worker_service as worker\n"
        "assert not {'app.config', 'app.database', 'main'} & sys.modules.keys()\n"
        "assert 'FEEDBACK_TEST_PRIVATE_SETTING' not in os.environ\n"
        "class FakeStorage:\n"
        "    def __init__(self, bucket):\n"
        f"        assert bucket == {BUCKET!r}\n"
        "    def upload(self, key, data):\n"
        f"        assert key == {KEY!r} and data == {PNG!r}\n"
        "        return '17'\n"
        "    def download(self, key, generation):\n"
        f"        assert key == {KEY!r} and generation == '17'\n"
        f"        return {PNG!r}\n"
        "    def delete(self, key, generation):\n"
        f"        assert key == {KEY!r}\n"
        "        return generation\n"
        "    def verify_permissions(self):\n"
        "        return None\n"
        "worker.GCSFeedbackStorage = FakeStorage\n"
        "raise SystemExit(worker._main())\n"
    )
    monkeypatch.setenv("FEEDBACK_TEST_PRIVATE_SETTING", "fixture-setting")
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-I", "-B", str(script)))


@pytest.mark.asyncio
@pytest.mark.parametrize("operation,kwargs,expected", [
    ("upload", {"data": PNG}, "17"),
    ("download", {"generation": "17"}, PNG),
    ("delete", {"generation": "17"}, "17"),
    ("delete", {}, None),
    ("verify_permissions", {}, None),
])
async def test_real_worker_protocol_and_known_or_unknown_delete_receipts(fake_adapter_worker, monkeypatch, operation, kwargs, expected):
    create = asyncio.create_subprocess_exec
    children = []

    async def record(*args, **options):
        assert options["env"] == {} and options["stderr"] == asyncio.subprocess.DEVNULL
        assert BUCKET not in args and KEY not in args
        child = await create(*args, **options)
        children.append(child)
        return child

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", record)
    try:
        result = await service.run_feedback_storage_operation(
            BUCKET, operation, "" if operation == "verify_permissions" else KEY, **kwargs,
        )
        assert result == expected
        assert len(children) == 1 and children[0].returncode == 0
    finally:
        await _cleanup(children)


@pytest.mark.asyncio
async def test_actual_script_imports_adapter_and_rejects_invalid_key_without_provider_access():
    with pytest.raises(service.FeedbackStorageError, match="^invalid_object_key$"):
        await service.run_feedback_storage_operation(BUCKET, "delete", "outside/private.png", generation="17")


@pytest.mark.asyncio
@pytest.mark.parametrize("operation,kwargs,code", [
    ("upload", {"data": b""}, "invalid_image_size"),
    ("upload", {"data": b"x" * (service.MAX_STORED_IMAGE_BYTES + 1)}, "invalid_image_size"),
    ("download", {}, "invalid_generation"),
    ("delete", {"data": b"unwanted bytes"}, "invalid_storage_operation"),
    ("list", {}, "invalid_storage_operation"),
])
async def test_invalid_or_oversized_operations_never_launch_worker(monkeypatch, operation, kwargs, code):
    async def forbidden(*_args, **_kwargs):
        raise AssertionError("Invalid operation launched a storage child")

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", forbidden)
    with pytest.raises(service.FeedbackStorageError, match=f"^{code}$"):
        await service.run_feedback_storage_operation(BUCKET, operation, KEY, **kwargs)


@pytest.mark.parametrize("raw", [
    b"x" * (service.MAX_HEADER_BYTES + 1),
    b'{"private":"malformed"}\n',
    b'{"bucket":"fixture","operation":"upload","object_key":"fixture","generation":null,"body_bytes":-1}\n',
    b'{"bucket":"fixture","operation":"upload","object_key":"fixture","generation":null,"body_bytes":true}\n',
])
def test_child_protocol_rejects_bad_headers_without_echoing_payload(raw):
    with pytest.raises(service.FeedbackStorageError) as error:
        service._read_request(io.BytesIO(raw))
    assert error.value.code == "invalid_storage_protocol" and "private" not in str(error.value)


def test_child_protocol_rejects_extra_or_truncated_bytes():
    header = service._request_header(BUCKET, "upload", KEY, PNG, None)
    for data in (PNG[:-1], PNG + b"extra"):
        with pytest.raises(service.FeedbackStorageError, match="^invalid_storage_protocol$"):
            service._read_request(io.BytesIO(header + data))


@pytest.mark.parametrize("header,body", [
    ({"error": "private provider message", "body_bytes": 0}, b""),
    ({"error": "object_missing", "body_bytes": 0}, b""),
    ({"result": "image", "body_bytes": 1}, b""),
    ({"result": "generation", "generation": "private value", "body_bytes": 0}, b""),
])
def test_response_errors_are_fixed_and_results_are_checked(header, body):
    operation = "download" if header.get("result") == "image" else "upload"
    expected = ("object_missing" if header.get("error") == "object_missing" else
                "storage_unavailable" if "error" in header else "invalid_storage_protocol")
    with pytest.raises(service.FeedbackStorageError) as error:
        service._read_response(service._json_header(header) + body, operation)
    assert error.value.code == expected and "private" not in str(error.value)


@pytest.mark.asyncio
async def test_two_workers_are_bounded_and_native_work_dies_on_deadline_or_cancellation(monkeypatch, tmp_path):
    script = (
        "import os,pathlib,sys,threading,time; "
        "threading.Thread(target=lambda:time.sleep(60)).start(); "
        "pathlib.Path(sys.argv[1],str(os.getpid())).write_text('ready'); "
        "sys.stdin.buffer.read(); time.sleep(60)"
    )
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", script, str(tmp_path)))
    children, deadlines = [], []
    create = asyncio.create_subprocess_exec

    async def record(*args, **kwargs):
        child = await create(*args, **kwargs)
        children.append(child)
        return child

    def capture_timeout(seconds):
        assert seconds == service.STORAGE_TIMEOUT_SECONDS
        deadline = asyncio.timeout(None)
        deadlines.append(deadline)
        return deadline

    monkeypatch.setattr(service, "asyncio", SimpleNamespace(
        **{**vars(asyncio), "create_subprocess_exec": record, "timeout": capture_timeout},
    ))
    tasks = [asyncio.create_task(service.run_feedback_storage_operation(
        BUCKET, "upload", KEY, data=PNG,
    )) for _ in range(2)]
    try:
        async with asyncio.timeout(10):
            while len(children) != 2 or not all((tmp_path / str(child.pid)).exists() for child in children):
                await asyncio.sleep(0.005)
        with pytest.raises(service.FeedbackStorageError, match="^storage_busy$"):
            async with asyncio.timeout(10):
                await service.run_feedback_storage_operation(BUCKET, "download", KEY, generation="17")
        assert len(children) == 2
        deadlines[0].reschedule(asyncio.get_running_loop().time())
        tasks[1].cancel()
        with pytest.raises(service.FeedbackStorageError, match="^storage_timeout$"):
            async with asyncio.timeout(10):
                await tasks[0]
        with pytest.raises(asyncio.CancelledError):
            async with asyncio.timeout(10):
                await tasks[1]
        assert deadlines[0].expired()
        assert all(child.returncode is not None and child.returncode < 0 for child in children)
        # Both permits become usable only after their respective children are gone.
        response = service._json_header({"result": "deleted", "generation": "17", "body_bytes": 0})
        monkeypatch.setattr(service, "_command", lambda: (
            sys.executable, "-c", f"import sys; sys.stdin.buffer.read(); sys.stdout.buffer.write({response!r})",
        ))
        assert await service.run_feedback_storage_operation(BUCKET, "delete", KEY, generation="17") == "17"
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await _cleanup(children)


@pytest.mark.asyncio
async def test_startup_and_repeated_cancellation_cannot_lose_worker_handles(monkeypatch):
    started, release = asyncio.Event(), asyncio.Event()
    children = []
    create = asyncio.create_subprocess_exec
    monkeypatch.setattr(service, "_command", lambda: (
        sys.executable, "-c", "import sys,time; sys.stdin.buffer.read(); time.sleep(60)",
    ))

    async def delayed_handle(*args, **kwargs):
        child = await create(*args, **kwargs)
        children.append(child)
        if len(children) == 2:
            started.set()
        await release.wait()
        return child

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", delayed_handle)
    tasks = [asyncio.create_task(service.run_feedback_storage_operation(BUCKET, "delete", KEY)) for _ in range(2)]
    try:
        async with asyncio.timeout(10):
            await started.wait()
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)
        for task in tasks:
            task.cancel()
        await asyncio.sleep(0)
        assert all(not task.done() for task in tasks)
        with pytest.raises(service.FeedbackStorageError, match="^storage_busy$"):
            async with asyncio.timeout(10):
                await service.run_feedback_storage_operation(BUCKET, "delete", KEY)
        release.set()
        for task in tasks:
            with pytest.raises(asyncio.CancelledError):
                async with asyncio.timeout(10):
                    await task
        assert all(child.returncode is not None and child.returncode < 0 for child in children)
    finally:
        release.set()
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        await _cleanup(children)


@pytest.mark.asyncio
async def test_oversized_stdout_is_stopped_before_worker_finishes(monkeypatch):
    create = asyncio.create_subprocess_exec
    children = []
    size = service.MAX_STORED_IMAGE_BYTES + service.MAX_HEADER_BYTES + 1
    script = ("import sys,time; sys.stdin.buffer.read(); "
              f"sys.stdout.buffer.write(b'x' * {size}); sys.stdout.buffer.flush(); time.sleep(60)")
    monkeypatch.setattr(service, "_command", lambda: (sys.executable, "-c", script))

    async def record(*args, **kwargs):
        child = await create(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(service.asyncio, "create_subprocess_exec", record)
    try:
        with pytest.raises(service.FeedbackStorageError, match="^invalid_storage_protocol$"):
            async with asyncio.timeout(10):
                await service.run_feedback_storage_operation(BUCKET, "download", KEY, generation="17")
        assert children[0].returncode is not None and children[0].returncode < 0
    finally:
        await _cleanup(children)
