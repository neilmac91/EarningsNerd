"""Bounded, parent-owned IPC for immutable filing sources; no SDK runs in this process.

The caller's monotonic deadline covers lock admission and the complete exchange. At expiry
or cancellation, SIGKILL is sent and the child is reaped before releasing the process permit.
Kernel scheduling/reaping itself cannot have a finite wall-clock guarantee.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import anyio

from app.services.filing_source_types import (
    ARTIFACT_ERROR_CODES,
    MAX_SOURCE_BYTES,
    FilingSourceError,
    StoredSourceObject,
    source_object_key,
)

MAX_HEADER_BYTES = 2048
STORAGE_OPERATION_SECONDS = 10.0
_CHUNK_BYTES = 64 * 1024
_execution_lock = asyncio.Lock()


def _bucket(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", value):
        raise FilingSourceError("artifact_not_configured")
    return value


def _generation(value: str) -> str:
    if (not isinstance(value, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", value)
            or int(value) > 2**64 - 1):
        raise FilingSourceError("artifact_identity_invalid")
    return value


def _length(value: int) -> int:
    if type(value) is not int or value < 1:
        raise FilingSourceError("artifact_source_invalid")
    if value > MAX_SOURCE_BYTES:
        raise FilingSourceError("artifact_source_too_large")
    return value


def _deadline(value: float) -> float:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise FilingSourceError("artifact_storage_protocol")
    if value <= time.monotonic():
        raise FilingSourceError("artifact_storage_timeout", retryable=True)
    return float(value)


def _json_header(value: dict) -> bytes:
    header = json.dumps(value, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii") + b"\n"
    if len(header) > MAX_HEADER_BYTES:
        raise FilingSourceError("artifact_storage_protocol")
    return header


def _command() -> tuple[str, ...]:
    return sys.executable, "-I", "-B", str(Path(__file__).with_name("filing_source_storage_worker.py"))


class _PipeWriteProtocol(asyncio.streams.FlowControlMixin):
    def __init__(self, loop: asyncio.AbstractEventLoop) -> None:
        super().__init__(loop=loop)
        self._closed = loop.create_future()

    def connection_lost(self, exc: Exception | None) -> None:
        super().connection_lost(exc)
        if not self._closed.done():
            self._closed.set_result(None)

    def _get_close_waiter(self, stream: asyncio.StreamWriter) -> asyncio.Future:
        return self._closed


class _OwnedProcess:
    """Retain the native handle before any cancellable pipe attachment.

    asyncio's subprocess creation also calls Popen synchronously on this thread. Keeping
    that handle here avoids its pipe-setup task and transport-dependent exit wait: Runner
    can cancel both while native work exists. No spawning thread can outlive its caller,
    and the event-loop thread remains the creator tracked by Linux PDEATHSIG.
    """

    def __init__(self) -> None:
        self.stdin: asyncio.StreamWriter | None = None
        self.stdout: asyncio.StreamReader | None = None
        self._write_transport: asyncio.WriteTransport | None = None
        self._read_transport: asyncio.ReadTransport | None = None
        self._native = subprocess.Popen(
            _command(), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, env={}, bufsize=0,
        )

    async def attach(self) -> None:
        loop = asyncio.get_running_loop()
        assert self._native.stdin is not None and self._native.stdout is not None
        self._write_transport, protocol = await loop.connect_write_pipe(
            lambda: _PipeWriteProtocol(loop), self._native.stdin,
        )
        self.stdin = asyncio.StreamWriter(self._write_transport, protocol, None, loop)
        reader = asyncio.StreamReader(limit=MAX_HEADER_BYTES)
        self._read_transport, _ = await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(reader), self._native.stdout,
        )
        self.stdout = reader

    @property
    def returncode(self) -> int | None:
        return self._native.poll()

    def kill_and_close(self) -> None:
        if self.returncode is None:
            try:
                self._native.kill()
            except ProcessLookupError:
                pass
        # Abort connected transports without flushing cancelled input. connect_*_pipe
        # closes its own transport on cancellation; raw handles cover unattached pipes.
        if self._write_transport is not None:
            if not self._write_transport.is_closing():
                self._write_transport.abort()
        elif self._native.stdin is not None:
            self._native.stdin.close()
        if self._read_transport is not None:
            if not self._read_transport.is_closing():
                self._read_transport.close()
        elif self._native.stdout is not None:
            self._native.stdout.close()

    async def wait(self) -> int:
        while (returncode := self.returncode) is None:
            # poll() performs nonblocking waitpid: physical reaping never depends on
            # pipe callbacks, which may themselves have been cancelled during shutdown.
            await asyncio.sleep(0.01)
        return returncode


def _response_header(raw: bytes, request: dict) -> dict:
    if not raw.endswith(b"\n") or len(raw) > MAX_HEADER_BYTES:
        raise FilingSourceError("artifact_storage_protocol")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise FilingSourceError("artifact_storage_protocol") from None
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1:
        raise FilingSourceError("artifact_storage_protocol")
    if "error" in value:
        if (set(value) != {"version", "error", "retryable", "body_bytes"}
                or type(value.get("body_bytes")) is not int or value["body_bytes"] != 0
                or type(value.get("retryable")) is not bool or not isinstance(value.get("error"), str)
                or value["error"] not in ARTIFACT_ERROR_CODES):
            raise FilingSourceError("artifact_storage_protocol")
        return value
    if set(value) != {"version", "result", "generation", "sha256", "byte_length", "body_bytes"}:
        raise FilingSourceError("artifact_storage_protocol")
    expected_body = request["byte_length"] if request["operation"] == "read" else 0
    if (value["result"] != ("bytes" if request["operation"] == "read" else "stored")
            or type(value["body_bytes"]) is not int or value["body_bytes"] != expected_body
            or type(value["byte_length"]) is not int or value["byte_length"] != request["byte_length"]
            or value["sha256"] != request["content_sha256"]):
        raise FilingSourceError("artifact_storage_protocol")
    try:
        _generation(value["generation"])
    except FilingSourceError:
        raise FilingSourceError("artifact_storage_protocol") from None
    if request["operation"] == "read" and value["generation"] != request["generation"]:
        raise FilingSourceError("artifact_storage_protocol")
    return value


async def _exchange(
    process: _OwnedProcess, request: dict, content: bytes | None,
) -> StoredSourceObject | bytes:
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(_json_header(request))
        if content is not None:
            for offset in range(0, len(content), _CHUNK_BYTES):
                process.stdin.write(content[offset:offset + _CHUNK_BYTES])
                await process.stdin.drain()
        await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        process.stdin.close()
    try:
        raw_header = await process.stdout.readuntil(b"\n")
        header = _response_header(raw_header, request)
        body = await process.stdout.readexactly(header["body_bytes"])
        if await process.stdout.read(1):
            raise FilingSourceError("artifact_storage_protocol")
    except (asyncio.IncompleteReadError, asyncio.LimitOverrunError):
        raise FilingSourceError("artifact_storage_protocol") from None
    await process.wait()
    if process.returncode != 0:
        raise FilingSourceError("artifact_storage_unavailable", retryable=True)
    if "error" in header:
        raise FilingSourceError(header["error"], retryable=header["retryable"])
    if request["operation"] == "read":
        if hashlib.sha256(body).hexdigest() != request["content_sha256"]:
            raise FilingSourceError("artifact_object_corrupt")
        return body
    return StoredSourceObject(header["generation"], header["sha256"], header["byte_length"])


async def _reap(process: _OwnedProcess) -> None:
    try:
        process.kill_and_close()
    finally:
        await process.wait()


async def _finish_child(process: _OwnedProcess) -> None:
    cleanup = asyncio.create_task(_reap(process))
    cancelled = False
    while True:
        try:
            with anyio.CancelScope(shield=True):
                await asyncio.shield(cleanup)
            break
        except asyncio.CancelledError:
            cancelled = True
            if cleanup.cancelled():
                # Runner.cancel-all can cancel cleanup before its first instruction.
                # Retain the same authoritative handle and restart idempotent cleanup.
                cleanup = asyncio.create_task(_reap(process))
            elif cleanup.done():
                cleanup.result()
                break
    if cancelled:
        raise asyncio.CancelledError


class BoundedFilingSourceStorage:
    """Sequential disposable children, with only derived keys and pinned receipts."""

    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = _bucket(bucket_name)

    async def _run(
        self, operation: str, identity_sha256: str, content_sha256: str, byte_length: int,
        generation: str | None, content: bytes | None, deadline: float,
    ) -> StoredSourceObject | bytes:
        source_object_key(identity_sha256, content_sha256)
        _length(byte_length)
        if generation is not None:
            _generation(generation)
        deadline = min(_deadline(deadline), time.monotonic() + STORAGE_OPERATION_SECONDS)
        request = {
            "version": 1, "operation": operation, "bucket": self._bucket_name,
            "identity_sha256": identity_sha256, "content_sha256": content_sha256,
            "byte_length": byte_length, "generation": generation,
            "body_bytes": len(content) if content is not None else 0,
            "parent_pid": os.getpid(), "deadline": deadline,
        }
        try:
            async with asyncio.timeout_at(deadline):
                async with _execution_lock:
                    # No await between native creation and retaining its owner. No new
                    # session/process group: the task supervisor still owns this child.
                    process = _OwnedProcess()
                    try:
                        await process.attach()
                        return await _exchange(process, request, content)
                    finally:
                        await _finish_child(process)
        except TimeoutError:
            raise FilingSourceError("artifact_storage_timeout", retryable=True) from None
        except (OSError, RuntimeError) as error:
            if isinstance(error, FilingSourceError):
                raise
            raise FilingSourceError("artifact_storage_unavailable", retryable=True) from None

    async def put(self, identity_sha256: str, content: bytes, *, deadline: float) -> StoredSourceObject:
        _deadline(deadline)
        if not isinstance(content, bytes):
            raise FilingSourceError("artifact_source_invalid")
        _length(len(content))
        content_sha256 = hashlib.sha256(content).hexdigest()
        return await self._run("put", identity_sha256, content_sha256, len(content), None, content, deadline)

    async def read(
        self, identity_sha256: str, content_sha256: str, byte_length: int, generation: str, *, deadline: float,
    ) -> bytes:
        _generation(generation)
        return await self._run("read", identity_sha256, content_sha256, byte_length, generation, None, deadline)
