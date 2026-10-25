"""Object writes, reads and cleanup stay inside the recorded generation and byte budget."""
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest

from app.services import feedback_storage_service as storage


class ProviderFailure(Exception):
    def __init__(self, code):
        self.code = code
        super().__init__("provider payload must never escape")


@pytest.fixture
def boundary():
    blob = Mock(generation=17)
    blob.download_as_bytes.return_value = b"normalized png"
    client = Mock()
    client.bucket.return_value.blob.return_value = blob
    adapter = storage.GCSFeedbackStorage("private-feedback-fixture", client=client)
    key = storage.make_feedback_object_key(str(uuid4()), str(uuid4()))
    return SimpleNamespace(blob=blob, client=client, adapter=adapter, key=key)


def test_writes_create_only_and_reads_only_recorded_generation_with_bounded_range(boundary):
    assert boundary.adapter.upload(boundary.key, b"normalized png") == "17"
    kwargs = boundary.blob.upload_from_string.call_args.kwargs
    assert kwargs["if_generation_match"] == 0
    assert kwargs["retry"] is None
    assert kwargs["content_type"] == "image/png"
    assert kwargs["checksum"] == "crc32c"
    assert boundary.blob.cache_control == "private, no-store"

    assert boundary.adapter.download(boundary.key, "17") == b"normalized png"
    kwargs = boundary.blob.download_as_bytes.call_args.kwargs
    assert kwargs["if_generation_match"] == 17
    assert kwargs["start"] == 0
    assert kwargs["end"] == storage.MAX_STORED_IMAGE_BYTES
    assert kwargs["retry"] is None


def test_crashed_upload_cleanup_recovers_generation_before_conditional_delete(boundary):
    assert boundary.adapter.delete(boundary.key, None) == "17"
    boundary.blob.reload.assert_called_once()
    assert boundary.blob.delete.call_args.kwargs["if_generation_match"] == 17
    boundary.client.list_blobs.assert_not_called()


def test_cleanup_accepts_absence_but_preserves_replaced_generation_for_investigation(boundary):
    boundary.blob.delete.side_effect = ProviderFailure(404)
    assert boundary.adapter.delete(boundary.key, "17") == "17"
    boundary.blob.delete.side_effect = ProviderFailure(412)
    with pytest.raises(storage.FeedbackStorageError, match="^generation_conflict$"):
        boundary.adapter.delete(boundary.key, "17")
    assert boundary.blob.delete.call_count == 2
    boundary.blob.reload.assert_not_called()


def test_unknown_generation_absence_has_no_false_deletion_receipt(boundary):
    boundary.blob.reload.side_effect = ProviderFailure(404)
    assert boundary.adapter.delete(boundary.key, None) is None
    boundary.blob.delete.assert_not_called()


def test_provider_errors_never_expose_provider_payload(boundary):
    boundary.blob.upload_from_string.side_effect = ProviderFailure(503)
    with pytest.raises(storage.FeedbackStorageError, match="^storage_unavailable$"):
        boundary.adapter.upload(boundary.key, b"normalized png")


@pytest.mark.parametrize("grant_change,expected", [(None, None), ("missing", "storage_permissions_missing"),
                                                  ("inherited", "storage_permissions_excess")])
def test_effective_runtime_permissions_require_narrow_grants_and_reject_inherited_excess(boundary, grant_change, expected):
    grants = set(storage.REQUIRED_STORAGE_PERMISSIONS)
    if grant_change == "missing":
        grants.remove("storage.objects.delete")
    if grant_change == "inherited":
        grants.add("storage.buckets.setIamPolicy")
    bucket = boundary.client.bucket.return_value
    bucket.test_iam_permissions.return_value = sorted(grants)
    if expected:
        with pytest.raises(storage.FeedbackStorageError, match=f"^{expected}$"):
            boundary.adapter.verify_permissions()
    else:
        assert boundary.adapter.verify_permissions() is None
    args, kwargs = bucket.test_iam_permissions.call_args
    assert set(args[0]) == storage.REQUIRED_STORAGE_PERMISSIONS | storage.EXCESS_STORAGE_PERMISSIONS
    assert not {"storage.buckets.list", "storage.buckets.create"} & set(args[0])
    assert not any(permission.startswith("storage.multipartUploads.") for permission in args[0])
    assert kwargs["retry"] is None and kwargs["timeout"] == (2.0, 8.0)
    bucket.blob.assert_not_called()


@pytest.mark.parametrize("key", ["../../other-object", "other/private.png", "feedback/filename.png"])
def test_rejects_keys_outside_server_owned_uuid_namespace_before_provider_call(boundary, key):
    with pytest.raises(storage.FeedbackStorageError, match="invalid_object_key"):
        boundary.adapter.delete(key, "17")
    boundary.client.bucket.assert_not_called()


def test_rejects_oversized_upload_and_download(boundary):
    huge = b"x" * (storage.MAX_STORED_IMAGE_BYTES + 1)
    with pytest.raises(storage.FeedbackStorageError, match="invalid_image_size"):
        boundary.adapter.upload(boundary.key, huge)
    boundary.blob.upload_from_string.assert_not_called()
    boundary.blob.download_as_bytes.return_value = huge
    with pytest.raises(storage.FeedbackStorageError, match="invalid_image_size"):
        boundary.adapter.download(boundary.key, "17")


@pytest.mark.parametrize("generation", ["", "0", "-1", "1.0", "١٧", str(2**64)])
def test_rejects_invalid_generation_before_download(boundary, generation):
    with pytest.raises(storage.FeedbackStorageError, match="invalid_generation"):
        boundary.adapter.download(boundary.key, generation)
    boundary.client.bucket.assert_not_called()
