"""Local subprocess ownership + fake-SDK immutable bytes contracts; no live GCS/IAM claim."""
from __future__ import annotations

import asyncio
from contextlib import nullcontext
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import time
from types import SimpleNamespace

import pytest

from app.services import filing_source_storage as storage
from app.services import filing_source_storage_worker as worker
from app.services.filing_source_types import FilingSourceError, StoredSourceObject, source_object_key

BUCKET = "filing-source-fixture"
IDENTITY = "a" * 64
CONTENT = b"<html>REGN fixed offline source fixture</html>"
SHA = hashlib.sha256(CONTENT).hexdigest()
BACKEND = str(Path(storage.__file__).resolve().parents[2])


def request(operation="put", **changes):
    value = {
        "version": 1, "operation": operation, "bucket": BUCKET,
        "identity_sha256": IDENTITY, "content_sha256": SHA,
        "byte_length": len(CONTENT), "generation": "17" if operation == "read" else None,
        "body_bytes": 0 if operation == "read" else len(CONTENT),
        "parent_pid": os.getppid(), "deadline": time.monotonic() + 30,
    }
    return value | changes


@pytest.fixture(autouse=True)
def private_lock(monkeypatch):
    monkeypatch.setattr(storage, "_execution_lock", asyncio.Lock())


class FakeGCS:
    """Models key/generation lookup and create-only conflicts, including accepted/lost ack."""

    def __init__(self, monkeypatch):
        self.objects = {}
        self.current = None
        self.calls = []
        self.upload_mode = "success"
        self.closed = False
        self.download_bytes = None
        self.metadata_change = {}
        self.size = len(CONTENT)
        self.encoding = None
        monkeypatch.setattr(worker, "_client", lambda: self)
        monkeypatch.setattr(worker, "_blob", self.blob)

    def bucket(self, name):
        assert name == BUCKET
        return self

    def close(self):
        self.closed = True

    def seed(self, content=CONTENT, generation="17"):
        self.objects[generation] = (content, worker._metadata(request()))
        self.current = generation

    def blob(self, bucket, key, generation=None):
        assert bucket is self
        assert key == source_object_key(IDENTITY, SHA)
        state = self

        class Blob:
            def __init__(self):
                self.generation = generation
                self.metadata = None
                self.size = None
                self.content_encoding = None

            def upload_from_file(self, stream, **kwargs):
                from google.api_core.exceptions import PreconditionFailed
                state.calls.append(("upload", generation, kwargs))
                assert kwargs["if_generation_match"] == 0, "upload must be create-only"
                data = stream.read()
                if state.current is not None:
                    raise PreconditionFailed("private collision payload")
                if state.upload_mode == "rejected":
                    raise RuntimeError("private provider failure")
                state.objects["17"] = (data, self.metadata)
                state.current = "17"
                if state.upload_mode == "lost_ack":
                    raise TimeoutError("private accepted upload response lost")
                self.generation = 17
                if state.upload_mode == "replaced_current":
                    state.objects["18"] = (b"unrelated", {})
                    state.current = "18"

            def reload(self, **kwargs):
                from google.api_core.exceptions import NotFound
                state.calls.append(("reload", generation, kwargs))
                selected = generation or state.current
                if selected not in state.objects:
                    raise NotFound("private key is absent")
                self.generation = selected
                self.size = state.size
                self.content_encoding = state.encoding
                self.metadata = state.objects[selected][1] | state.metadata_change

            def download_to_file(self, sink, **kwargs):
                state.calls.append(("download", generation, kwargs))
                assert generation is not None, "download must select a generation"
                content = state.objects[generation][0] if state.download_bytes is None else state.download_bytes
                for offset in range(0, len(content), 7):
                    sink.write(content[offset:offset + 7])

        return Blob()


@pytest.mark.parametrize("mode", ["success", "collision", "lost_ack", "replaced_current"])
def test_create_only_put_verifies_full_pinned_bytes_even_after_collision_or_lost_ack(monkeypatch, mode):
    gcs = FakeGCS(monkeypatch)
    gcs.upload_mode = mode
    if mode == "collision":
        gcs.seed()
    result, body = worker._dispatch(request(), CONTENT)
    assert result == StoredSourceObject("17", SHA, len(CONTENT)) and body == b""
    uploads = [call for call in gcs.calls if call[0] == "upload"]
    assert len(uploads) == 1
    assert uploads[0][2] | {"timeout": 10.0} == {
        "size": len(CONTENT), "content_type": "application/octet-stream", "if_generation_match": 0,
        "retry": None, "checksum": None, "timeout": 10.0,
    }
    downloads = [call for call in gcs.calls if call[0] == "download"]
    assert len(downloads) == 1 and downloads[0][1] == "17"
    assert downloads[0][2] | {"timeout": 10.0} == {
        "raw_download": True, "if_generation_match": 17, "retry": None, "timeout": 10.0,
        "checksum": None, "single_shot_download": False,
    }
    assert any(kind == "reload" and generation == "17" and options["if_generation_match"] == 17
               for kind, generation, options in gcs.calls)
    assert all(0 < options["timeout"] <= 10 for _, _, options in gcs.calls)
    assert gcs.closed


@pytest.mark.parametrize("problem", ["wrong_bytes", "short_bytes", "oversized_bytes", "wrong_size", "purpose", "encoding"])
def test_existing_object_corruption_is_not_overwritten_or_returned(monkeypatch, problem):
    gcs = FakeGCS(monkeypatch)
    gcs.seed()
    if problem == "wrong_bytes":
        gcs.download_bytes = b"x" * len(CONTENT)
    elif problem == "short_bytes":
        gcs.download_bytes = CONTENT[:-1]
    elif problem == "oversized_bytes":
        gcs.download_bytes = CONTENT + b"x"
    elif problem == "wrong_size":
        gcs.size = len(CONTENT) + 1
    elif problem == "purpose":
        gcs.metadata_change = {"earningsnerd-purpose": "other-purpose"}
    else:
        gcs.encoding = "gzip"
    with pytest.raises(FilingSourceError, match="^artifact_object_corrupt$"):
        worker._dispatch(request(), CONTENT)
    assert len([call for call in gcs.calls if call[0] == "upload"]) == 1
    assert gcs.objects["17"][0] == CONTENT
    assert gcs.closed


def test_read_pins_requested_generation_and_missing_is_not_live_fetch(monkeypatch):
    gcs = FakeGCS(monkeypatch)
    gcs.seed()
    gcs.current = "18"
    gcs.objects["18"] = (b"different", {})
    result, body = worker._dispatch(request("read"), b"")
    assert body == CONTENT and result.generation == "17"
    assert [call[0] for call in gcs.calls] == ["reload", "download"]
    assert all(call[1] == "17" and call[2]["if_generation_match"] == 17 for call in gcs.calls)
    with pytest.raises(FilingSourceError, match="^artifact_object_missing$"):
        worker._dispatch(request("read", generation="19"), b"")


def test_rejected_mutation_does_not_retry_or_expose_provider_payload(monkeypatch):
    gcs = FakeGCS(monkeypatch)
    gcs.upload_mode = "rejected"
    with pytest.raises(FilingSourceError) as error:
        worker._dispatch(request(), CONTENT)
    assert error.value.code == "artifact_storage_unavailable" and error.value.retryable
    assert "private" not in str(error.value)
    assert len([call for call in gcs.calls if call[0] == "upload"]) == 1


def test_sdk_resumable_corruption_cannot_regain_delete_authority(monkeypatch):
    """Run the installed SDK's real corruption handler, with only transport replaced."""
    from google.cloud.storage import Blob, Client
    from google.cloud.storage.exceptions import DataCorruption

    real = worker._blob(Client.create_anonymous_client().bucket(BUCKET), source_object_key(IDENTITY, SHA))
    deletes = []
    monkeypatch.setattr(Blob, "delete", lambda *args, **kwargs: deletes.append(True))

    class Upload:
        finished = False
        chunk_size = 1024 * 1024
        resumable_url = "https://storage.googleapis.com/fixture-upload"

        def transmit_next_chunk(self, *_args, **_kwargs):
            raise DataCorruption(None, "private checksum response")

    monkeypatch.setattr(real, "_initiate_resumable_upload", lambda *args, **kwargs: (Upload(), object()))
    monkeypatch.setattr(real, "_create_trace_span", lambda **kwargs: nullcontext())
    with pytest.raises(FilingSourceError, match="^artifact_object_corrupt$"):
        real._do_resumable_upload(
            object(), io.BytesIO(CONTENT), "application/octet-stream", len(CONTENT), None, 0, None, None, None,
        )
    assert deletes == []


def test_sdk_calls_share_remaining_deadline_and_expired_upload_does_not_start_readback(monkeypatch):
    gcs = FakeGCS(monkeypatch)
    now = [100.0]
    monkeypatch.setattr(worker.time, "monotonic", lambda: now[0])
    factory = gcs.blob

    def expires_after_upload(*args):
        blob = factory(*args)
        upload = blob.upload_from_file

        def expire(*values, **options):
            upload(*values, **options)
            now[0] = 103.0

        blob.upload_from_file = expire
        return blob

    monkeypatch.setattr(worker, "_blob", expires_after_upload)
    with pytest.raises(FilingSourceError, match="^artifact_storage_timeout$"):
        worker._dispatch(request(deadline=102.0), CONTENT)
    assert [(kind, options["timeout"]) for kind, _, options in gcs.calls] == [("upload", 2.0)]
    assert gcs.closed


@pytest.mark.parametrize("changes", [
    {"object_key": "private/arbitrary"}, {"bucket": "https://private.example/"},
    {"identity_sha256": "../private"}, {"parent_pid": -1}, {"parent_pid": True},
    {"body_bytes": True}, {"generation": "17"}, {"byte_length": True}, {"version": True},
    {"deadline": float("inf")}, {"byte_length": storage.MAX_SOURCE_BYTES + 1},
])
def test_child_rejects_untrusted_protocol_before_adc(changes, monkeypatch):
    monkeypatch.setattr(worker, "_client", lambda: pytest.fail("ADC reached before protocol validation"))
    raw = json.dumps(request(**changes)).encode() + b"\n" + CONTENT
    with pytest.raises(FilingSourceError):
        worker._read_request(io.BytesIO(raw))


@pytest.mark.parametrize("body", [CONTENT[:-1], CONTENT + b"extra", b"x" * len(CONTENT)])
def test_child_rejects_truncated_extended_and_wrong_hash_payload(body):
    with pytest.raises(FilingSourceError):
        worker._read_request(io.BytesIO(storage._json_header(request()) + body))


def test_child_accepts_exact_typed_protocol_and_bounds_size():
    header = request()
    actual, body = worker._read_request(io.BytesIO(storage._json_header(header) + CONTENT))
    assert actual == header and body == CONTENT
    sink = worker._BoundedSink(3)
    assert sink.write(b"abc") == 3
    with pytest.raises(FilingSourceError, match="^artifact_object_corrupt$"):
        sink.write(b"d")
    assert sink.getvalue() == b"abc"


@pytest.mark.parametrize("platform", ["win32", "darwin"])
def test_unsupported_parent_death_platform_fails_before_adc(monkeypatch, platform):
    monkeypatch.setattr(worker.sys, "platform", platform)
    with pytest.raises(FilingSourceError, match="^artifact_storage_unavailable$"):
        worker._arm_parent_death()


@pytest.fixture
def boundary_worker(tmp_path, monkeypatch):
    """Real child/main and wire protocol; only its GCS dispatch is offline."""
    path = tmp_path / "source_boundary.py"
    path.write_text(
        "import os, sys\n"
        f"sys.path.insert(0, {BACKEND!r})\n"
        "from app.services import filing_source_storage_worker as worker\n"
        "assert not {'app.config', 'app.database', 'main'} & sys.modules.keys()\n"
        "assert 'FILING_SOURCE_PRIVATE_TEST' not in os.environ\n"
        "def dispatch(request, content):\n"
        f"    assert request['bucket'] == {BUCKET!r}\n"
        f"    assert request['identity_sha256'] == {IDENTITY!r}\n"
        f"    assert content == ({CONTENT!r} if request['operation'] == 'put' else b'')\n"
        "    body = b'' if request['operation'] == 'put' else " + repr(CONTENT) + "\n"
        "    return worker.StoredSourceObject('17', request['content_sha256'], request['byte_length']), body\n"
        "worker._dispatch = dispatch\n"
        "raise SystemExit(worker._main())\n"
    )
    monkeypatch.setenv("FILING_SOURCE_PRIVATE_TEST", "private fixture setting")
    monkeypatch.setattr(storage, "_command", lambda: (sys.executable, "-I", "-B", str(path)))
    return path


@pytest.mark.asyncio
async def test_real_binary_roundtrip_empty_environment_fixed_argv_and_reaped_children(boundary_worker, monkeypatch):
    # Even the intentional inheritance mutant can select only this synthetic mapping.
    monkeypatch.setattr(storage.os, "environ", {"FILING_SOURCE_PRIVATE_TEST": "synthetic-offline-canary"})
    children = []
    create = asyncio.create_subprocess_exec

    async def record(*args, **kwargs):
        environment_entry_count = len(kwargs["env"])
        assert environment_entry_count == 0
        assert kwargs["stderr"] == asyncio.subprocess.DEVNULL
        assert not kwargs.get("start_new_session") and "process_group" not in kwargs
        assert BUCKET not in args and IDENTITY not in args and SHA not in args and CONTENT not in args
        process = await create(*args, **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(storage.asyncio, "create_subprocess_exec", record)
    store = storage.BoundedFilingSourceStorage(BUCKET)
    receipt = await store.put(IDENTITY, CONTENT, deadline=time.monotonic() + 10)
    assert receipt == StoredSourceObject("17", SHA, len(CONTENT))
    assert await store.read(IDENTITY, SHA, len(CONTENT), "17", deadline=time.monotonic() + 10) == CONTENT
    assert len(children) == 2 and all(child.returncode == 0 for child in children)
    assert not storage._execution_lock.locked()


@pytest.mark.asyncio
@pytest.mark.parametrize("caller_seconds", [2.0, 30.0])
async def test_child_receives_the_shorter_absolute_operation_or_caller_deadline(
    boundary_worker, monkeypatch, tmp_path, caller_seconds,
):
    captured = tmp_path / "child-deadline"
    boundary_worker.write_text(boundary_worker.read_text().replace(
        "def dispatch(request, content):\n",
        "def dispatch(request, content):\n"
        "    from pathlib import Path\n"
        f"    Path({str(captured)!r}).write_text(str(request['deadline']))\n",
    ))
    # This gate compares deadline values; interpreter startup must not consume a
    # two-second correctness window. The independent wait is only a hang guard.
    started = time.monotonic() + 60
    # Replace only the adapter clock; the real event loop and child keep real monotonic time.
    monkeypatch.setattr(storage, "time", SimpleNamespace(monotonic=lambda: started))
    monkeypatch.setattr(storage, "STORAGE_OPERATION_SECONDS", 3.0)
    receipt = await asyncio.wait_for(storage.BoundedFilingSourceStorage(BUCKET).put(
        IDENTITY, CONTENT, deadline=started + caller_seconds,
    ), 10)
    assert receipt == StoredSourceObject("17", SHA, len(CONTENT))
    assert float(captured.read_text()) == started + min(caller_seconds, 3.0)


@pytest.mark.asyncio
async def test_operation_cap_expires_during_lock_admission_without_starting_child(monkeypatch):
    async def forbidden(*args, **kwargs):
        pytest.fail("expired lock waiter started a storage child")

    monkeypatch.setattr(storage.asyncio, "create_subprocess_exec", forbidden)
    monkeypatch.setattr(storage, "STORAGE_OPERATION_SECONDS", 0.05)
    store = storage.BoundedFilingSourceStorage(BUCKET)
    async with storage._execution_lock:
        with pytest.raises(FilingSourceError, match="^artifact_storage_timeout$"):
            # The external guard makes a disabled operation cap fail promptly as TimeoutError.
            await asyncio.wait_for(store.put(IDENTITY, CONTENT, deadline=time.monotonic() + 30), 2)
        assert storage._execution_lock.locked()
    assert not storage._execution_lock.locked()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["invalid_identity", "empty", "oversized", "type", "expired", "infinite", "generation"])
async def test_invalid_inputs_never_launch_worker(monkeypatch, kind):
    async def forbidden(*args, **kwargs):
        pytest.fail("invalid input started child")

    monkeypatch.setattr(storage.asyncio, "create_subprocess_exec", forbidden)
    store = storage.BoundedFilingSourceStorage(BUCKET)
    args = [IDENTITY, CONTENT]
    deadline = time.monotonic() + 10
    if kind == "invalid_identity":
        args[0] = "../private"
    elif kind == "empty":
        args[1] = b""
    elif kind == "oversized":
        args[1] = b"x" * (storage.MAX_SOURCE_BYTES + 1)
    elif kind == "type":
        args[1] = bytearray(CONTENT)
    elif kind == "expired":
        deadline = time.monotonic() - 1
    elif kind == "infinite":
        deadline = float("inf")
    with pytest.raises(FilingSourceError):
        if kind == "generation":
            await store.read(IDENTITY, SHA, len(CONTENT), "01", deadline=deadline)
        else:
            await store.put(*args, deadline=deadline)


async def wait_path(path: Path):
    async with asyncio.timeout(10):
        while not path.exists():
            await asyncio.sleep(0.01)


def sleeping_worker(tmp_path, monkeypatch, *, drip=False):
    ready = tmp_path / "ready"
    path = tmp_path / "sleeping_worker.py"
    path.write_text(
        "import os, sys, pathlib, time, threading\n"
        f"sys.path.insert(0, {BACKEND!r})\n"
        "from app.services import filing_source_storage_worker as worker\n"
        "worker._arm_parent_death()\n"
        "request, content = worker._read_request(sys.stdin.buffer)\n"
        f"pathlib.Path({str(ready)!r}).write_text(str(os.getpid()))\n"
        "threading.Thread(target=lambda: time.sleep(60)).start()\n"
        + (
            "output = worker._json_header({'version':1,'result':'bytes','generation':'17',"
            "'sha256':request['content_sha256'],'byte_length':request['byte_length'],'body_bytes':request['byte_length']})\n"
            "sys.stdout.buffer.write(output); sys.stdout.buffer.flush()\n"
            "for part in " + repr(CONTENT) + ":\n"
            "    sys.stdout.buffer.write(bytes([part])); sys.stdout.buffer.flush(); time.sleep(1)\n"
            if drip else "time.sleep(60)\n"
        )
    )
    monkeypatch.setattr(storage, "_command", lambda: (sys.executable, "-I", "-B", str(path)))
    return ready


def process_finished(pid):
    try:
        # A reparented killed child can briefly remain a zombie until the host reaps it.
        return Path(f"/proc/{pid}/stat").read_text().split(")", 1)[1].split()[0] == "Z"
    except FileNotFoundError:
        return True


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership contract")
async def test_cancellation_kills_native_child_and_holds_single_permit_through_reap(tmp_path, monkeypatch):
    ready = sleeping_worker(tmp_path, monkeypatch)
    store = storage.BoundedFilingSourceStorage(BUCKET)
    real_reap = storage._reap
    reaped = asyncio.Event()
    release = asyncio.Event()

    async def held_reap(spawn):
        await real_reap(spawn)
        reaped.set()
        await release.wait()

    monkeypatch.setattr(storage, "_reap", held_reap)
    task = asyncio.create_task(store.put(IDENTITY, CONTENT, deadline=time.monotonic() + 30))
    try:
        await wait_path(ready)
        pid = int(ready.read_text())
        assert not process_finished(pid)
        task.cancel()
        await asyncio.wait_for(reaped.wait(), 10)
        assert process_finished(pid) and storage._execution_lock.locked()
        task.cancel()  # A second cancellation cannot detach cleanup or release admission.
        with pytest.raises(FilingSourceError, match="^artifact_storage_timeout$"):
            await store.put(IDENTITY, CONTENT, deadline=time.monotonic() + 0.05)
        assert storage._execution_lock.locked()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert not storage._execution_lock.locked()
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership contract")
async def test_absolute_deadline_stops_drip_reads_and_native_work(tmp_path, monkeypatch):
    ready = sleeping_worker(tmp_path, monkeypatch, drip=True)
    store = storage.BoundedFilingSourceStorage(BUCKET)
    entered = asyncio.Event()
    deadlines = []
    started = time.monotonic()
    monkeypatch.setattr(storage, 'time', SimpleNamespace(monotonic=lambda: started))
    def recorded_timeout_at(deadline):
        owner = asyncio.timeout_at(deadline)
        deadlines.append(owner)
        return owner
    monkeypatch.setattr(storage, 'asyncio', SimpleNamespace(**{**vars(asyncio), 'timeout_at': recorded_timeout_at}))
    actual_header = storage._response_header
    def header_received(*args):
        result = actual_header(*args)
        entered.set()
        return result
    monkeypatch.setattr(storage, '_response_header', header_received)
    task = asyncio.create_task(store.read(IDENTITY, SHA, len(CONTENT), "17", deadline=started + 30))
    try:
        # Receipt-header entry proves the native child started and the parent is
        # reading its real pipe. Expire that owner's real timeout during the drip.
        await asyncio.wait_for(entered.wait(), 10)
        assert len(deadlines) == 1 and deadlines[0].when() == started + storage.STORAGE_OPERATION_SECONDS
        deadlines[0].reschedule(asyncio.get_running_loop().time())
        with pytest.raises(FilingSourceError, match="^artifact_storage_timeout$"):
            await asyncio.wait_for(task, 10)
        assert deadlines[0].expired()
        assert ready.exists() and process_finished(int(ready.read_text()))
        assert not storage._execution_lock.locked()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership contract")
async def test_hard_parent_kill_stops_actual_storage_child_without_detaching_group(tmp_path):
    ready = tmp_path / "descendant"
    child_script = tmp_path / "owned_child.py"
    child_script.write_text(
        "import os, sys, pathlib, time, threading\n"
        f"sys.path.insert(0, {BACKEND!r})\n"
        "from app.services import filing_source_storage_worker as worker\n"
        "def dispatch(request, content):\n"
        "    threading.Thread(target=lambda: time.sleep(60)).start()\n"
        f"    pathlib.Path({str(ready)!r}).write_text(str(os.getpid()) + ' ' + str(os.getpgrp()))\n"
        "    time.sleep(60)\n"
        "worker._dispatch = dispatch\n"
        "raise SystemExit(worker._main())\n"
    )
    parent_script = tmp_path / "owned_parent.py"
    parent_script.write_text(
        "import asyncio, sys, time\n"
        f"sys.path.insert(0, {BACKEND!r})\n"
        "from app.services import filing_source_storage as storage\n"
        f"storage._command = lambda: (sys.executable, '-I', '-B', {str(child_script)!r})\n"
        f"asyncio.run(storage.BoundedFilingSourceStorage({BUCKET!r}).put({IDENTITY!r}, {CONTENT!r}, deadline=time.monotonic()+60))\n"
    )
    parent = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-B", str(parent_script), env={},
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    pid = None
    try:
        await wait_path(ready)
        pid, group = map(int, ready.read_text().split())
        assert group == os.getpgid(parent.pid) == os.getpgrp()
        assert not process_finished(pid)
        parent.kill()
        await parent.wait()
        async with asyncio.timeout(10):
            while not process_finished(pid):
                await asyncio.sleep(0.01)
    finally:
        if parent.returncode is None:
            parent.kill()
            await parent.wait()
        if pid is not None and not process_finished(pid):
            os.kill(pid, signal.SIGKILL)


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership contract")
async def test_parent_dying_before_prctl_is_rejected_before_adc(tmp_path):
    ready, barrier, adc = (tmp_path / name for name in ("orphan", "allow-arm", "adc-called"))
    child_script = tmp_path / "late_arm_child.py"
    child_script.write_text(
        "import sys, time, pathlib\n"
        f"sys.path.insert(0, {BACKEND!r})\n"
        "from app.services import filing_source_storage_worker as worker\n"
        f"while not pathlib.Path({str(barrier)!r}).exists(): time.sleep(0.01)\n"
        f"worker._client = lambda: pathlib.Path({str(adc)!r}).write_text('unsafe')\n"
        "raise SystemExit(worker._main())\n"
    )
    parent_script = tmp_path / "late_arm_parent.py"
    parent_script.write_text(
        "import os, sys, time, pathlib, subprocess, json\n"
        f"value = {request()!r}\n"
        "value['parent_pid'] = os.getpid(); value['deadline'] = time.monotonic()+60\n"
        f"child = subprocess.Popen([sys.executable, '-I', '-B', {str(child_script)!r}], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env={{}})\n"
        f"child.stdin.write(json.dumps(value).encode()+b'\\n'+{CONTENT!r}); child.stdin.close()\n"
        f"pathlib.Path({str(ready)!r}).write_text(str(child.pid))\n"
        "time.sleep(60)\n"
    )
    parent = await asyncio.create_subprocess_exec(
        sys.executable, "-I", "-B", str(parent_script), env={},
        stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
    )
    pid = None
    try:
        await wait_path(ready)
        pid = int(ready.read_text())
        parent.kill()
        await parent.wait()
        barrier.touch()
        async with asyncio.timeout(10):
            while not process_finished(pid):
                await asyncio.sleep(0.01)
        assert not adc.exists()
    finally:
        barrier.touch()
        if parent.returncode is None:
            parent.kill()
            await parent.wait()
        if pid is not None and not process_finished(pid):
            os.kill(pid, signal.SIGKILL)


@pytest.mark.asyncio
@pytest.mark.parametrize("corruption", ["oversized_header", "oversized_body", "wrong_bytes", "wrong_generation", "trailer", "unknown_error", "untyped_error"])
async def test_parent_bounds_and_validates_actual_child_output(tmp_path, monkeypatch, corruption):
    header = {
        "version": 1, "result": "bytes", "generation": "17", "sha256": SHA,
        "byte_length": len(CONTENT), "body_bytes": len(CONTENT),
    }
    body = CONTENT
    if corruption == "oversized_body":
        header["body_bytes"] = storage.MAX_SOURCE_BYTES + 1
    elif corruption == "wrong_generation":
        header["generation"] = "18"
    elif corruption == "wrong_bytes":
        body = b"x" * len(CONTENT)
    elif corruption == "trailer":
        body += b"private trailer"
    elif corruption in {"unknown_error", "untyped_error"}:
        header = {
            "version": 1, "error": "private provider payload" if corruption == "unknown_error" else [],
            "retryable": True, "body_bytes": 0,
        }
        body = b""
    output = (b"x" * (storage.MAX_HEADER_BYTES + 1) + b"\n" if corruption == "oversized_header"
              else storage._json_header(header) + body)
    script = tmp_path / "invalid_output.py"
    script.write_text("import sys\nsys.stdin.buffer.read()\nsys.stdout.buffer.write(" + repr(output) + ")\n")
    monkeypatch.setattr(storage, "_command", lambda: (sys.executable, "-I", "-B", str(script)))
    with pytest.raises(FilingSourceError) as error:
        await storage.BoundedFilingSourceStorage(BUCKET).read(
            IDENTITY, SHA, len(CONTENT), "17", deadline=time.monotonic() + 10,
        )
    expected = "artifact_object_corrupt" if corruption == "wrong_bytes" else "artifact_storage_protocol"
    assert error.value.code == expected and "private" not in str(error.value)
    assert not storage._execution_lock.locked()


@pytest.mark.asyncio
async def test_sdk_exception_details_cannot_cross_child_error_protocol(tmp_path, monkeypatch, caplog):
    script = tmp_path / "private_error.py"
    script.write_text(
        "import sys\n"
        f"sys.path.insert(0, {BACKEND!r})\n"
        "from app.services import filing_source_storage_worker as worker\n"
        "def dispatch(request, content):\n"
        "    raise RuntimeError('private-provider-response-and-credential-canary')\n"
        "worker._dispatch = dispatch\n"
        "raise SystemExit(worker._main())\n"
    )
    monkeypatch.setattr(storage, "_command", lambda: (sys.executable, "-I", "-B", str(script)))
    with pytest.raises(FilingSourceError) as error:
        await storage.BoundedFilingSourceStorage(BUCKET).put(IDENTITY, CONTENT, deadline=time.monotonic() + 10)
    assert error.value.code == "artifact_storage_unavailable"
    assert error.value.__cause__ is None and error.value.__context__ is None
    assert "private-provider" not in str(error.value) + caplog.text


@pytest.mark.asyncio
@pytest.mark.skipif(sys.platform != "linux", reason="Linux process ownership contract")
async def test_cancel_during_spawn_wait_still_reaps_child_before_releasing_permit(tmp_path, monkeypatch):
    sleeping_worker(tmp_path, monkeypatch)
    original = asyncio.create_subprocess_exec
    spawned, release = asyncio.Event(), asyncio.Event()
    children = []

    async def delayed(*args, **kwargs):
        child = await original(*args, **kwargs)
        children.append(child)
        spawned.set()
        await release.wait()
        return child

    monkeypatch.setattr(storage.asyncio, "create_subprocess_exec", delayed)
    task = asyncio.create_task(storage.BoundedFilingSourceStorage(BUCKET).put(
        IDENTITY, CONTENT, deadline=time.monotonic() + 30,
    ))
    try:
        await asyncio.wait_for(spawned.wait(), 10)
        task.cancel()
        await asyncio.sleep(0)
        assert storage._execution_lock.locked() and not task.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 10)
        assert children[0].returncode == -signal.SIGKILL
        assert not storage._execution_lock.locked()
    finally:
        release.set()
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        for child in children:
            if child.returncode is None:
                child.kill()
                await child.communicate()
