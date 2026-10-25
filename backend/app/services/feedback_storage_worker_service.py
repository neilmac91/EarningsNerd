"""Hard-deadline, isolated private feedback object operations.

SDK connect/read timeouts cannot bound a stalled native thread or an entire upload. Each
operation gets a disposable child; its permit is released only after kill/reap. No object
name, bucket, credentials or image travels in argv, environment, logs or error messages.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
import sys
from typing import BinaryIO

import anyio

# The isolated script has no working-directory imports. These packages have empty __init__
# files; importing the storage adapter loads no application settings, SQL pool or .env file.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.feedback_storage_service import (  # noqa: E402
    FeedbackStorageError,
    GCSFeedbackStorage,
    MAX_STORED_IMAGE_BYTES,
)

MAX_HEADER_BYTES = 1024
STORAGE_TIMEOUT_SECONDS = 15.0
_execution_slots = asyncio.Semaphore(2)
_OPERATIONS = {"upload", "download", "delete", "verify_permissions"}
_ERROR_CODES = {
    "storage_unavailable", "storage_not_configured", "storage_busy", "storage_timeout",
    "invalid_image_size", "invalid_object_key", "invalid_generation", "object_missing",
    "generation_conflict", "invalid_storage_operation", "invalid_storage_protocol",
    "storage_permissions_missing", "storage_permissions_excess",
}


def _json_header(value: dict) -> bytes:
    header = json.dumps(value, ensure_ascii=True, separators=(",", ":")).encode("ascii") + b"\n"
    if len(header) > MAX_HEADER_BYTES:
        raise FeedbackStorageError("invalid_storage_protocol")
    return header


def _request_header(
    bucket_name: str, operation: str, object_key: str, data: bytes | None, generation: str | None,
) -> bytes:
    if not isinstance(bucket_name, str) or not 1 <= len(bucket_name) <= 222:
        raise FeedbackStorageError("storage_not_configured")
    if operation not in _OPERATIONS:
        raise FeedbackStorageError("invalid_storage_operation")
    if operation == "verify_permissions":
        if object_key != "" or data is not None or generation is not None:
            raise FeedbackStorageError("invalid_storage_operation")
    elif not isinstance(object_key, str) or not 1 <= len(object_key) <= 200:
        raise FeedbackStorageError("invalid_object_key")
    if generation is not None and (not isinstance(generation, str) or len(generation) > 20):
        raise FeedbackStorageError("invalid_generation")
    if operation == "upload":
        if not isinstance(data, bytes) or not data or len(data) > MAX_STORED_IMAGE_BYTES:
            raise FeedbackStorageError("invalid_image_size")
        if generation is not None:
            raise FeedbackStorageError("invalid_generation")
    elif data is not None:
        raise FeedbackStorageError("invalid_storage_operation")
    if operation == "download" and generation is None:
        raise FeedbackStorageError("invalid_generation")
    return _json_header({
        "bucket": bucket_name, "operation": operation, "object_key": object_key,
        "generation": generation, "body_bytes": len(data) if data is not None else 0,
    })


def _command() -> tuple[str, ...]:
    return sys.executable, "-I", "-B", str(Path(__file__).resolve())


async def _exchange(process: asyncio.subprocess.Process, header: bytes, data: bytes | None) -> bytes:
    assert process.stdin is not None and process.stdout is not None
    try:
        process.stdin.write(header)
        if data is not None:
            process.stdin.write(data)
        await process.stdin.drain()
    except (BrokenPipeError, ConnectionResetError):
        pass
    finally:
        process.stdin.close()
    try:
        await process.stdout.readexactly(MAX_STORED_IMAGE_BYTES + MAX_HEADER_BYTES + 1)
    except asyncio.IncompleteReadError as exc:
        output = exc.partial
    else:
        raise FeedbackStorageError("invalid_storage_protocol")
    await process.wait()
    if process.returncode != 0:
        raise FeedbackStorageError("storage_unavailable")
    return output


async def _reap(spawn: asyncio.Task[asyncio.subprocess.Process]) -> None:
    try:
        process = await spawn
    except (OSError, RuntimeError):
        return
    if process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    if process.stdin is not None:
        process.stdin.close()
    if process.stdout is not None:
        while await process.stdout.read(64 * 1024):
            pass
    await process.wait()


async def _finish_child(spawn: asyncio.Task[asyncio.subprocess.Process]) -> None:
    cleanup = asyncio.create_task(_reap(spawn))
    cancelled = False
    while True:
        try:
            with anyio.CancelScope(shield=True):
                await asyncio.shield(cleanup)
            break
        except asyncio.CancelledError:
            cancelled = True
            if cleanup.done():
                cleanup.result()
                break
    if cancelled:
        raise asyncio.CancelledError


def _read_response(output: bytes, operation: str) -> str | bytes | None:
    raw_header, separator, body = output.partition(b"\n")
    if not separator or len(raw_header) + 1 > MAX_HEADER_BYTES:
        raise FeedbackStorageError("invalid_storage_protocol")
    try:
        header = json.loads(raw_header)
    except (ValueError, UnicodeError):
        raise FeedbackStorageError("invalid_storage_protocol") from None
    if not isinstance(header, dict) or type(header.get("body_bytes")) is not int:
        raise FeedbackStorageError("invalid_storage_protocol")
    if header["body_bytes"] != len(body) or len(body) > MAX_STORED_IMAGE_BYTES:
        raise FeedbackStorageError("invalid_storage_protocol")
    if "error" in header:
        code = header["error"]
        if set(header) != {"error", "body_bytes"} or body or not isinstance(code, str):
            raise FeedbackStorageError("invalid_storage_protocol")
        raise FeedbackStorageError(code if code in _ERROR_CODES else "storage_unavailable")
    if operation == "verify_permissions":
        if header != {"result": "permissions_verified", "body_bytes": 0} or body:
            raise FeedbackStorageError("invalid_storage_protocol")
        return None
    if operation == "download":
        if set(header) != {"result", "body_bytes"} or header["result"] != "image" or not body:
            raise FeedbackStorageError("invalid_storage_protocol")
        return body
    if set(header) != {"result", "generation", "body_bytes"} or body:
        raise FeedbackStorageError("invalid_storage_protocol")
    expected = "generation" if operation == "upload" else "deleted"
    if header["result"] != expected:
        raise FeedbackStorageError("invalid_storage_protocol")
    generation = header["generation"]
    if generation is None and operation == "delete":
        return None
    if (not isinstance(generation, str) or len(generation) > 20 or not generation.isascii()
            or not generation.isdecimal() or not 1 <= int(generation) <= 2**64 - 1):
        raise FeedbackStorageError("invalid_storage_protocol")
    return generation


async def run_feedback_storage_operation(
    bucket_name: str,
    operation: str,
    object_key: str,
    *,
    data: bytes | None = None,
    generation: str | None = None,
) -> str | bytes | None:
    """Execute one bounded private storage operation in an isolated worker."""
    header = _request_header(bucket_name, operation, object_key, data, generation)
    # The check/acquire pair cannot yield on the serving event loop. Never queue more
    # per-request payloads behind both workers, including downloads competing with uploads.
    if _execution_slots.locked():
        raise FeedbackStorageError("storage_busy")
    async with _execution_slots:
        spawn = asyncio.create_task(asyncio.create_subprocess_exec(
            *_command(), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env={},
        ))
        try:
            try:
                async with asyncio.timeout(STORAGE_TIMEOUT_SECONDS):
                    process = await asyncio.shield(spawn)
                    output = await _exchange(process, header, data)
            except TimeoutError:
                raise FeedbackStorageError("storage_timeout") from None
            except OSError:
                raise FeedbackStorageError("storage_unavailable") from None
        finally:
            await _finish_child(spawn)
    return _read_response(output, operation)


class BoundedFeedbackStorage:
    """Synchronous job/CLI facade; serving routes use the async function directly."""

    def __init__(self, bucket_name: str) -> None:
        self._bucket_name = bucket_name

    def _run(
        self, operation: str, object_key: str, *, data: bytes | None = None, generation: str | None = None,
    ) -> str | bytes | None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            # Refuse before constructing a coroutine, so misuse cannot leak unawaited work.
            raise FeedbackStorageError("invalid_storage_operation")
        return asyncio.run(run_feedback_storage_operation(
            self._bucket_name, operation, object_key, data=data, generation=generation,
        ))

    def upload(self, object_key: str, data: bytes) -> str:
        result = self._run("upload", object_key, data=data)
        if not isinstance(result, str):
            raise FeedbackStorageError("invalid_storage_protocol")
        return result

    def verify_permissions(self) -> None:
        if self._run("verify_permissions", "") is not None:
            raise FeedbackStorageError("invalid_storage_protocol")

    def download(self, object_key: str, generation: str) -> bytes:
        result = self._run("download", object_key, generation=generation)
        if not isinstance(result, bytes):
            raise FeedbackStorageError("invalid_storage_protocol")
        return result

    def delete(self, object_key: str, generation: str | None) -> str | None:
        result = self._run("delete", object_key, generation=generation)
        if result is not None and not isinstance(result, str):
            raise FeedbackStorageError("invalid_storage_protocol")
        return result


def _read_request(stream: BinaryIO) -> tuple[dict, bytes]:
    raw_header = stream.readline(MAX_HEADER_BYTES + 1)
    if len(raw_header) > MAX_HEADER_BYTES or not raw_header.endswith(b"\n"):
        raise FeedbackStorageError("invalid_storage_protocol")
    try:
        header = json.loads(raw_header)
    except (ValueError, UnicodeError):
        raise FeedbackStorageError("invalid_storage_protocol") from None
    if (not isinstance(header, dict)
            or set(header) != {"bucket", "operation", "object_key", "generation", "body_bytes"}
            or type(header["body_bytes"]) is not int
            or not 0 <= header["body_bytes"] <= MAX_STORED_IMAGE_BYTES):
        raise FeedbackStorageError("invalid_storage_protocol")
    data = stream.read(header["body_bytes"] + 1)
    if len(data) != header["body_bytes"]:
        raise FeedbackStorageError("invalid_storage_protocol")
    _request_header(header["bucket"], header["operation"], header["object_key"],
                    data if header["operation"] == "upload" else None, header["generation"])
    if header["operation"] != "upload" and data:
        raise FeedbackStorageError("invalid_storage_protocol")
    return header, data


def _main() -> int:
    try:
        header, data = _read_request(sys.stdin.buffer)
        adapter = GCSFeedbackStorage(header["bucket"])
        operation = header["operation"]
        if operation == "verify_permissions":
            adapter.verify_permissions()
            output = _json_header({"result": "permissions_verified", "body_bytes": 0})
            body = b""
        elif operation == "upload":
            generation = adapter.upload(header["object_key"], data)
            output = _json_header({"result": "generation", "generation": generation, "body_bytes": 0})
            body = b""
        elif operation == "download":
            body = adapter.download(header["object_key"], header["generation"])
            if not isinstance(body, bytes) or not body or len(body) > MAX_STORED_IMAGE_BYTES:
                raise FeedbackStorageError("invalid_image_size")
            output = _json_header({"result": "image", "body_bytes": len(body)})
        else:
            generation = adapter.delete(header["object_key"], header["generation"])
            output = _json_header({"result": "deleted", "generation": generation, "body_bytes": 0})
            body = b""
    except FeedbackStorageError as exc:
        code = exc.code if exc.code in _ERROR_CODES else "storage_unavailable"
        output, body = _json_header({"error": code, "body_bytes": 0}), b""
    except Exception:
        output, body = _json_header({"error": "storage_unavailable", "body_bytes": 0}), b""
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
