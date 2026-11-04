"""Private one-operation GCS child; ADC is resolved only after parent ownership validation.

No application Settings/DB imports, inherited environment, external exception output, list,
public URL or delete operation. The parent owns the hard deadline; the child also bounds
individual SDK calls by the same monotonic deadline. This worker requires Linux.
"""
from __future__ import annotations

import ctypes
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import sys
import time
from typing import Any, BinaryIO

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.services.filing_source_storage import (  # noqa: E402
    MAX_HEADER_BYTES, STORAGE_OPERATION_SECONDS, _bucket, _deadline, _generation, _json_header, _length,
)
from app.services.filing_source_types import (  # noqa: E402
    SOURCE_REPRESENTATION, FilingSourceError, StoredSourceObject, source_object_key,
)

_METADATA_PURPOSE = "filing-source-v1"
_SDK_TIMEOUT_SECONDS = STORAGE_OPERATION_SECONDS


def _arm_parent_death() -> None:
    """Arm before input/ADC; the later expected-PID check closes reparent-before-prctl."""
    if sys.platform != "linux":
        raise FilingSourceError("artifact_storage_unavailable")
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        prctl = libc.prctl
        prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
        prctl.restype = ctypes.c_int
        if prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
            raise OSError
    except (AttributeError, OSError):
        raise FilingSourceError("artifact_storage_unavailable") from None


def _read_request(stream: BinaryIO) -> tuple[dict, bytes]:
    raw = stream.readline(MAX_HEADER_BYTES + 1)
    if len(raw) > MAX_HEADER_BYTES or not raw.endswith(b"\n"):
        raise FilingSourceError("artifact_storage_protocol")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError):
        raise FilingSourceError("artifact_storage_protocol") from None
    expected_keys = {
        "version", "operation", "bucket", "identity_sha256", "content_sha256", "byte_length",
        "generation", "body_bytes", "parent_pid", "deadline",
    }
    if (not isinstance(value, dict) or set(value) != expected_keys
            or type(value.get("version")) is not int or value["version"] != 1
            or not isinstance(value["operation"], str) or value["operation"] not in {"put", "read"}
            or type(value["parent_pid"]) is not int or value["parent_pid"] <= 0
            or value["parent_pid"] != os.getppid()):
        raise FilingSourceError("artifact_storage_protocol")
    _bucket(value["bucket"])
    source_object_key(value["identity_sha256"], value["content_sha256"])
    _length(value["byte_length"])
    _deadline(value["deadline"])
    body_length = value["byte_length"] if value["operation"] == "put" else 0
    if type(value["body_bytes"]) is not int or value["body_bytes"] != body_length:
        raise FilingSourceError("artifact_storage_protocol")
    if value["operation"] == "put":
        if value["generation"] is not None:
            raise FilingSourceError("artifact_storage_protocol")
    else:
        _generation(value["generation"])
    content = stream.read(body_length + 1)
    if len(content) != body_length:
        raise FilingSourceError("artifact_storage_protocol")
    if body_length and hashlib.sha256(content).hexdigest() != value["content_sha256"]:
        raise FilingSourceError("artifact_object_corrupt")
    _deadline(value["deadline"])
    # Checking again makes the no-ADC-before-ownership rule explicit after a blocked pipe read.
    if value["parent_pid"] != os.getppid():
        raise FilingSourceError("artifact_storage_protocol")
    return value, content


def _remaining(deadline: float) -> float:
    _deadline(deadline)
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise FilingSourceError("artifact_storage_timeout", retryable=True)
    return min(_SDK_TIMEOUT_SECONDS, remaining)


def _client() -> Any:
    from google.cloud import storage
    return storage.Client()


def _blob(bucket: Any, key: str, generation: str | None = None) -> Any:
    from google.cloud.storage import Blob

    class ImmutableBlob(Blob):
        def delete(self, *args: Any, **kwargs: Any) -> None:
            # The SDK's resumable checksum error path calls self.delete(). Never grant it.
            raise FilingSourceError("artifact_object_corrupt")

    return ImmutableBlob(key, bucket=bucket, generation=int(generation) if generation else None, chunk_size=1024 * 1024)


def _metadata(request: dict) -> dict[str, str]:
    return {
        "earningsnerd-purpose": _METADATA_PURPOSE,
        "identity-sha256": request["identity_sha256"],
        "content-sha256": request["content_sha256"],
        "byte-length": str(request["byte_length"]),
        "representation": SOURCE_REPRESENTATION,
    }


def _actual_generation(blob: Any) -> str:
    value = blob.generation
    if type(value) is int:
        value = str(value)
    try:
        return _generation(value)
    except FilingSourceError:
        raise FilingSourceError("artifact_object_corrupt") from None


class _BoundedSink(io.BytesIO):
    def __init__(self, expected: int):
        super().__init__()
        self._expected = expected

    def write(self, data: bytes) -> int:
        if not isinstance(data, bytes) or self.tell() + len(data) > self._expected:
            raise FilingSourceError("artifact_object_corrupt")
        return super().write(data)


def _read_verified(bucket: Any, request: dict, generation: str) -> bytes:
    from google.api_core.exceptions import NotFound

    key = source_object_key(request["identity_sha256"], request["content_sha256"])
    blob = _blob(bucket, key, generation)
    try:
        blob.reload(if_generation_match=int(generation), retry=None, timeout=_remaining(request["deadline"]))
        if (_actual_generation(blob) != generation or type(blob.size) is not int
                or blob.size != request["byte_length"] or blob.content_encoding is not None
                or not isinstance(blob.metadata, dict)
                or any(blob.metadata.get(key) != value for key, value in _metadata(request).items())):
            raise FilingSourceError("artifact_object_corrupt")
        with _BoundedSink(request["byte_length"]) as sink:
            blob.download_to_file(
                sink, raw_download=True, if_generation_match=int(generation), retry=None,
                timeout=_remaining(request["deadline"]), checksum=None, single_shot_download=False,
            )
            content = sink.getvalue()
        if (len(content) != request["byte_length"]
                or hashlib.sha256(content).hexdigest() != request["content_sha256"]):
            raise FilingSourceError("artifact_object_corrupt")
        _deadline(request["deadline"])
        return content
    except FilingSourceError:
        raise
    except NotFound:
        raise FilingSourceError("artifact_object_missing") from None
    except Exception:
        raise FilingSourceError("artifact_storage_unavailable", retryable=True) from None


def _put_verified(bucket: Any, request: dict, content: bytes) -> StoredSourceObject:
    key = source_object_key(request["identity_sha256"], request["content_sha256"])
    blob = _blob(bucket, key)
    blob.metadata = _metadata(request)
    generation = None
    try:
        # None disables SDK checksum auto-delete; SHA-256/full readback is the authority.
        blob.upload_from_file(
            io.BytesIO(content), size=len(content), content_type="application/octet-stream",
            if_generation_match=0, retry=None, checksum=None, timeout=_remaining(request["deadline"]),
        )
        generation = _actual_generation(blob)
    except Exception:
        # Collision and a lost upload acknowledgement both require the same verified read.
        # Never retry the mutation here and never trust an exception's message or headers.
        pass
    if generation is None:
        try:
            candidate = _blob(bucket, key)
            candidate.reload(retry=None, timeout=_remaining(request["deadline"]))
            generation = _actual_generation(candidate)
        except FilingSourceError:
            raise
        except Exception:
            raise FilingSourceError("artifact_storage_unavailable", retryable=True) from None
    _read_verified(bucket, request, generation)
    return StoredSourceObject(generation, request["content_sha256"], request["byte_length"])


def _dispatch(request: dict, content: bytes) -> tuple[StoredSourceObject, bytes]:
    _deadline(request["deadline"])
    client = _client()
    try:
        bucket = client.bucket(request["bucket"])
        if request["operation"] == "put":
            return _put_verified(bucket, request, content), b""
        body = _read_verified(bucket, request, request["generation"])
        return StoredSourceObject(request["generation"], request["content_sha256"], len(body)), body
    finally:
        client.close()


def _main() -> int:
    try:
        _arm_parent_death()
        request, content = _read_request(sys.stdin.buffer)
        stored, body = _dispatch(request, content)
        output = _json_header({
            "version": 1, "result": "stored" if request["operation"] == "put" else "bytes",
            "generation": stored.generation, "sha256": stored.sha256,
            "byte_length": stored.byte_length, "body_bytes": len(body),
        })
    except FilingSourceError as error:
        output, body = _json_header({
            "version": 1, "error": error.code, "retryable": error.retryable, "body_bytes": 0,
        }), b""
    except Exception:
        output, body = _json_header({
            "version": 1, "error": "artifact_storage_unavailable", "retryable": True, "body_bytes": 0,
        }), b""
    sys.stdout.buffer.write(output)
    sys.stdout.buffer.write(body)
    sys.stdout.buffer.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
