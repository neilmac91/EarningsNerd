"""Load or capture the exact filing's immutable entity bytes before new model work.

This coordinates existing SEC selection/transport and private object storage. It
never generates a summary, accepts arbitrary URLs, or holds SQL across network I/O.
"""
from __future__ import annotations

import asyncio
import hashlib
import time

import httpx

from app.config import settings
from app.services import filing_source_store as store
from app.services.filing_source_types import (
    CommittedFilingSource, FilingSourceError, FilingSourceIdentity, MAX_SOURCE_BYTES,
    SOURCE_DECODER_VERSION, SOURCE_EXTRACTION_VERSION, SOURCE_REPRESENTATION,
    SourceBundle, SourceMember,
)
from app.services.request_work import RequestWork, run_owned_sync
from .async_executor import run_parse_with_timeout
from .compat import sec_edgar_service
from .eightk_extractor import (
    _attachment_text, get_eightk_grounding_from_members, select_eightk_source_members,
)

SOURCE_STAGE_SECONDS = 30.0
_CONTENT_TYPES = frozenset({"text/html", "application/xhtml+xml", "text/plain", "text/xml", "application/xml"})


def _remaining(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise FilingSourceError("artifact_storage_timeout", retryable=True)
    return remaining


def _content_type(source: dict) -> str:
    value = source.get("content_type")
    if (not isinstance(value, str) or not 1 <= len(value) <= 160
            or any(ord(char) < 32 or ord(char) > 126 for char in value)
            or value.split(";", 1)[0].strip().lower() not in _CONTENT_TYPES):
        raise FilingSourceError("artifact_source_invalid")
    return value


def _source_metadata(identity: FilingSourceIdentity, filename: str, content: bytes, source: dict) -> str:
    if not isinstance(content, bytes):
        raise FilingSourceError("artifact_source_invalid")
    digest = hashlib.sha256(content).hexdigest()
    if (not content or len(content) > MAX_SOURCE_BYTES or not isinstance(source, dict)
            or source.get("representation") != SOURCE_REPRESENTATION
            or source.get("cik") != identity.cik or source.get("accession_number") != identity.accession
            or source.get("filename") != filename or source.get("sha256") != digest
            or type(source.get("bytes")) is not int or source["bytes"] != len(content)
            or source.get("requested_url") != identity.url_for(filename)
            or source.get("final_url") != identity.url_for(filename)
            or source.get("status_code") != 200
            or source.get("content_encoding") not in (None, "identity")):
        raise FilingSourceError("artifact_source_invalid")
    return _content_type(source)


def _decode_primary(content: bytes, content_type: str) -> str:
    # Match HTTPX's existing decoded-document path, retaining the original bytes
    # separately. Do not claim that UTF-8 re-encoding reconstructs entity bytes.
    response = httpx.Response(200, headers={"Content-Type": content_type}, content=content)
    return response.text


async def _db(owner: RequestWork, function, *args):
    with owner.activate():
        return await run_owned_sync(function, *args)


async def _verified_members(storage, bundle: SourceBundle, deadline: float) -> dict[str, bytes]:
    content = {}
    total = 0
    for member in bundle.members:
        _remaining(deadline)
        body = await storage.read(bundle.identity.sha256, member.sha256, member.byte_length,
                                  member.storage_generation, deadline=deadline)
        total += len(body)
        if (total > MAX_SOURCE_BYTES or len(body) != member.byte_length
                or hashlib.sha256(body).hexdigest() != member.sha256):
            raise FilingSourceError("artifact_object_corrupt")
        content[member.filename] = body
    return content


async def _capture(identity: FilingSourceIdentity, storage, owner: RequestWork, deadline: float) -> tuple[SourceBundle, dict]:
    filename = identity.primary_filename
    primary, metadata = await sec_edgar_service.get_filing_primary_bytes(
        identity.cik, identity.accession, filename, timeout=_remaining(deadline), max_bytes=MAX_SOURCE_BYTES,
    )
    primary_type = _source_metadata(identity, filename, primary, metadata)
    await run_parse_with_timeout(lambda: _attachment_text(primary), _remaining(deadline))
    primary_text = _decode_primary(primary, primary_type)
    filenames = []
    if identity.filing_type.split("/")[0] == "8-K":
        filenames = await select_eightk_source_members(
            primary_text, identity.url_for(filename), identity.cik, identity.accession, timeout=_remaining(deadline),
        )
    bodies = {filename: primary}
    source_types = {filename: primary_type}
    total = len(primary)
    for exhibit in filenames:
        if total >= MAX_SOURCE_BYTES:
            raise FilingSourceError("artifact_source_too_large")
        body, source = await sec_edgar_service.get_filing_attachment_bytes(
            identity.cik, identity.accession, exhibit, timeout=_remaining(deadline), max_retries=1,
            max_bytes=MAX_SOURCE_BYTES - total,
        )
        source_types[exhibit] = _source_metadata(identity, exhibit, body, source)
        await run_parse_with_timeout(lambda body=body: _attachment_text(body), _remaining(deadline))
        total += len(body)
        if total > MAX_SOURCE_BYTES:
            raise FilingSourceError("artifact_source_too_large")
        bodies[exhibit] = body
    members = []
    for ordinal, (name, body) in enumerate(bodies.items()):
        stored = await storage.put(identity.sha256, body, deadline=deadline)
        if stored.sha256 != hashlib.sha256(body).hexdigest() or stored.byte_length != len(body):
            raise FilingSourceError("artifact_object_corrupt")
        members.append(SourceMember(ordinal, "primary" if ordinal == 0 else "exhibit", name,
                                    stored.sha256, stored.byte_length, source_types[name], stored.generation))
    candidate = SourceBundle(identity, tuple(members))
    committed = await _db(owner, store.commit_bundle, candidate)
    if committed.id != candidate.id:
        # A concurrent capture selected different bytes. Its committed identity
        # wins; never release our candidate text beside the winner's receipt.
        bodies = await _verified_members(storage, committed, deadline)
    return committed, bodies


async def _ground(bundle: SourceBundle, bodies: dict[str, bytes], deadline: float) -> tuple[str, dict]:
    identity = bundle.identity
    primary = bundle.members[0]
    primary_bytes = bodies[primary.filename]
    await run_parse_with_timeout(lambda: _attachment_text(primary_bytes), _remaining(deadline))
    text = _decode_primary(primary_bytes, primary.content_type)
    if identity.filing_type.split("/")[0] != "8-K":
        if len(bundle.members) != 1:
            raise FilingSourceError("artifact_manifest_invalid")
        return text, {"schema_version": 1, "source": "primary_source_v1"}
    supplied = {}
    for member in bundle.members[1:]:
        supplied[member.filename] = (bodies[member.filename], {
            "schema_version": 1, "representation": member.representation, "sha256": member.sha256,
            "bytes": member.byte_length, "cik": identity.cik, "accession_number": identity.accession,
            "filename": member.filename, "requested_url": identity.url_for(member.filename),
            "final_url": identity.url_for(member.filename), "status_code": 200,
            "content_type": member.content_type, "content_encoding": "identity",
        })
    grounding = await get_eightk_grounding_from_members(
        text, identity.url_for(primary.filename), identity.cik, identity.accession, supplied,
        timeout=_remaining(deadline),
    )
    return grounding.text, grounding.provenance


async def load_or_capture_source(
    identity: FilingSourceIdentity, *, deadline: float, owner: RequestWork,
) -> CommittedFilingSource:
    from app.services.filing_source_storage import BoundedFilingSourceStorage

    # Configuration is read once. The pipeline snapshots opt-in on its run, so a
    # later flag flip cannot turn legacy input into an artifact-backed generation.
    bucket = settings.FILING_SOURCE_ARTIFACTS_BUCKET
    if not bucket:
        raise FilingSourceError("artifact_not_configured")
    deadline = min(deadline, time.monotonic() + SOURCE_STAGE_SECONDS)
    storage = BoundedFilingSourceStorage(bucket)
    try:
        with owner.activate():
            async with asyncio.timeout(_remaining(deadline)):
                bundle = await _db(owner, store.lookup_bundle, identity)
                if bundle is None:
                    bundle, bodies = await _capture(identity, storage, owner, deadline)
                else:
                    bodies = await _verified_members(storage, bundle, deadline)
                text, source = await _ground(bundle, bodies, deadline)
                digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
                extraction = await _db(owner, store.commit_extraction, bundle, SOURCE_DECODER_VERSION,
                                       SOURCE_EXTRACTION_VERSION, digest, len(text.encode("utf-8")))
                _remaining(deadline)
                safe = {**source, "artifact": {
                    "bundle_id": bundle.id, "extraction_id": extraction, "grounding_sha256": digest,
                    "representation": SOURCE_REPRESENTATION, "decoder_version": SOURCE_DECODER_VERSION,
                    "extractor_version": SOURCE_EXTRACTION_VERSION, "selection_version": identity.selection_version,
                }}
                return CommittedFilingSource(bundle, extraction, text, digest, SOURCE_DECODER_VERSION,
                                             SOURCE_EXTRACTION_VERSION, safe)
    except TimeoutError:
        raise FilingSourceError("artifact_storage_timeout", retryable=True) from None
