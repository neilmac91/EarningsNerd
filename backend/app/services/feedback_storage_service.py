"""Private, generation-fenced screenshot storage using the runtime's Google identity.

The caller owns authorization and database manifests. This adapter never lists a bucket,
publishes a URL, retries an uncertain write, or logs provider payloads. Calls are synchronous;
HTTP handlers dispatch them through the repository's bounded blocking-work lane.
"""
from __future__ import annotations

import re
from typing import Any, Protocol
from uuid import UUID


MAX_STORED_IMAGE_BYTES = 8 * 1024 * 1024
_OBJECT_KEY = re.compile(r"feedback/[0-9a-f]{32}/[0-9a-f]{32}\.png\Z")
_TIMEOUT = (2.0, 8.0)
REQUIRED_STORAGE_PERMISSIONS = frozenset({
    "storage.objects.create", "storage.objects.get", "storage.objects.delete",
})
# Enumerated effective-permission audit, including inherited grants. This is not a claim
# about every permission a future Google release may add. Bucket testIamPermissions rejects
# project-only buckets.list/create and documents buckets/objects/managedFolders resources;
# project-only and multipartUploads permissions are deliberately outside this bucket audit.
EXCESS_STORAGE_PERMISSIONS = frozenset({
    "storage.buckets.get", "storage.buckets.update", "storage.buckets.delete",
    "storage.buckets.getIamPolicy", "storage.buckets.setIamPolicy", "storage.objects.list",
    "storage.objects.update", "storage.objects.getIamPolicy", "storage.objects.setIamPolicy",
    "storage.objects.restore", "storage.objects.move", "storage.objects.setRetention",
    "storage.objects.overrideUnlockedRetention",
})


class FeedbackStorageError(RuntimeError):
    """Content-free provider failure suitable for a retry ledger or API translation."""

    def __init__(self, code: str = "storage_unavailable") -> None:
        self.code = code
        super().__init__(code)


class FeedbackStorage(Protocol):
    def verify_permissions(self) -> None: ...

    def upload(self, object_key: str, data: bytes) -> str: ...

    def download(self, object_key: str, generation: str) -> bytes: ...

    def delete(self, object_key: str, generation: str | None) -> str | None: ...


def make_feedback_object_key(attempt_token: str, attachment_token: str) -> str:
    """Only server-generated UUIDs become names; never use a user's filename or pathname."""
    return f"feedback/{UUID(attempt_token).hex}/{UUID(attachment_token).hex}.png"


def _generation(value: str) -> int:
    if not isinstance(value, str) or len(value) > 20 or not value.isascii() or not value.isdecimal():
        raise FeedbackStorageError("invalid_generation")
    result = int(value)
    if result < 1 or result > 2**64 - 1:
        raise FeedbackStorageError("invalid_generation")
    return result


def _translate(exc: Exception) -> FeedbackStorageError:
    code = getattr(exc, "code", None)
    if code == 404:
        return FeedbackStorageError("object_missing")
    if code == 412:
        return FeedbackStorageError("generation_conflict")
    return FeedbackStorageError()


class GCSFeedbackStorage:
    """A known private bucket; ADC is resolved lazily only when storage is actually used."""

    def __init__(self, bucket_name: str, *, client: Any = None) -> None:
        if not bucket_name or not isinstance(bucket_name, str):
            raise FeedbackStorageError("storage_not_configured")
        self._bucket_name = bucket_name
        self._client = client

    def _bucket(self) -> Any:
        if self._client is None:
            try:
                from google.cloud import storage

                self._client = storage.Client()
            except Exception:
                raise FeedbackStorageError("storage_not_configured") from None
        return self._client.bucket(self._bucket_name)

    def _blob(self, object_key: str) -> Any:
        if not _OBJECT_KEY.fullmatch(object_key):
            raise FeedbackStorageError("invalid_object_key")
        return self._bucket().blob(object_key)

    def verify_permissions(self) -> None:
        """Test the serving identity's enumerated effective grants, never the deployer's."""
        try:
            granted = set(self._bucket().test_iam_permissions(
                sorted(REQUIRED_STORAGE_PERMISSIONS | EXCESS_STORAGE_PERMISSIONS), timeout=_TIMEOUT, retry=None,
            ))
        except FeedbackStorageError:
            raise
        except Exception as exc:
            raise _translate(exc) from None
        if not REQUIRED_STORAGE_PERMISSIONS <= granted:
            raise FeedbackStorageError("storage_permissions_missing")
        if granted & EXCESS_STORAGE_PERMISSIONS:
            raise FeedbackStorageError("storage_permissions_excess")

    def upload(self, object_key: str, data: bytes) -> str:
        """Create exactly once; an uncertain result remains discoverable by its SQL manifest."""
        if not data or len(data) > MAX_STORED_IMAGE_BYTES:
            raise FeedbackStorageError("invalid_image_size")
        blob = self._blob(object_key)
        blob.cache_control = "private, no-store"
        try:
            blob.upload_from_string(
                data, content_type="image/png", if_generation_match=0,
                timeout=_TIMEOUT, retry=None, checksum="crc32c",
            )
        except Exception as exc:
            raise _translate(exc) from None
        generation = str(blob.generation)
        _generation(generation)
        return generation

    def download(self, object_key: str, generation: str) -> bytes:
        """Read only the recorded object generation, with an inclusive bounded byte range."""
        expected = _generation(generation)
        blob = self._blob(object_key)
        try:
            data = blob.download_as_bytes(
                start=0, end=MAX_STORED_IMAGE_BYTES, if_generation_match=expected,
                timeout=_TIMEOUT, retry=None, checksum="auto",
            )
        except Exception as exc:
            raise _translate(exc) from None
        if not data or len(data) > MAX_STORED_IMAGE_BYTES:
            raise FeedbackStorageError("invalid_image_size")
        return data

    def delete(self, object_key: str, generation: str | None) -> str | None:
        """Delete only the intended generation; absence is success, replacement is a failure.

        Return the generation proved removed, or None when an unknown write is merely absent
        now. A crashed upload's unknown-generation 404 cannot exclude a late server commit;
        its manifest must remain discoverable for repeated checks.
        """
        blob = self._blob(object_key)
        try:
            if generation is None:
                blob.reload(timeout=_TIMEOUT, retry=None)
                generation = str(blob.generation)
            expected = _generation(generation)
            blob.delete(if_generation_match=expected, timeout=_TIMEOUT, retry=None)
            return generation
        except FeedbackStorageError:
            raise
        except Exception as exc:
            if getattr(exc, "code", None) == 404:
                return generation
            raise _translate(exc) from None
