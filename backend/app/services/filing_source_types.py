"""Content-free contracts for immutable filing sources and the isolated storage child.

Keep this module independent of Settings, database engines, HTTP clients and SDKs.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import re
from urllib.parse import quote, unquote, urlsplit

from app.utils.sec_urls import build_sec_archive_url, normalize_accession, normalize_cik

MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_SOURCE_MEMBERS = 4
SOURCE_REPRESENTATION = "httpx_identity_entity_bytes"
SOURCE_SCHEMA_VERSION = 1
SOURCE_SELECTION_VERSION = "same_accession_v1"
SOURCE_DECODER_VERSION = "httpx_text_v1"
SOURCE_EXTRACTION_VERSION = "primary_eightk_grounding_v1"

ARTIFACT_ERROR_CODES = frozenset({
    "artifact_not_configured", "artifact_identity_invalid", "artifact_source_invalid",
    "artifact_source_too_large", "artifact_member_missing", "artifact_storage_unavailable",
    "artifact_storage_timeout", "artifact_storage_busy", "artifact_object_missing",
    "artifact_object_corrupt", "artifact_storage_protocol", "artifact_commit_unverified",
    "artifact_manifest_invalid", "artifact_extraction_conflict", "artifact_barrier_missing",
})


class FilingSourceError(RuntimeError):
    """Closed reason only; SDK/HTTP errors must not enter its cause chain or message."""

    def __init__(self, code: str, *, retryable: bool = False):
        if code not in ARTIFACT_ERROR_CODES or type(retryable) is not bool:
            code, retryable = "artifact_storage_protocol", False
        self.code = code
        self.retryable = retryable
        super().__init__(code)


@dataclass(frozen=True)
class StoredSourceObject:
    generation: str
    sha256: str
    byte_length: int


def source_object_key(identity_sha256: str, content_sha256: str) -> str:
    """Only application-generated identity/content hashes select a storage object."""
    if not all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
               for value in (identity_sha256, content_sha256)):
        raise FilingSourceError("artifact_identity_invalid")
    return f"filing-source/v1/{identity_sha256}/{content_sha256}"


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                     ensure_ascii=True, allow_nan=False).encode()).hexdigest()


def valid_filename(value: object) -> bool:
    return (isinstance(value, str) and 1 <= len(value.encode("utf-8")) <= 255
            and value not in {".", ".."}
            and not any(char in "/\\?#" or ord(char) < 32 or ord(char) == 127 for char in value))


@dataclass(frozen=True)
class FilingSourceIdentity:
    filing_id: int
    cik: str
    accession: str
    filing_type: str
    primary_filename: str
    selection_version: str = SOURCE_SELECTION_VERSION
    schema_version: int = SOURCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if (type(self.filing_id) is not int or self.filing_id < 1
                or not isinstance(self.cik, str) or not re.fullmatch(r"[1-9][0-9]{0,19}", self.cik)
                or not isinstance(self.accession, str) or not re.fullmatch(r"[0-9]{18}", self.accession)
                or self.filing_type not in {"10-K", "10-Q", "8-K", "10-K/A", "10-Q/A", "8-K/A"}
                or not valid_filename(self.primary_filename)
                or self.selection_version != SOURCE_SELECTION_VERSION or self.schema_version != SOURCE_SCHEMA_VERSION):
            raise FilingSourceError("artifact_identity_invalid")

    @classmethod
    def from_filing(cls, filing_id: int, snapshot: dict) -> FilingSourceIdentity:
        try:
            cik, accession = normalize_cik(snapshot["company_cik"]), normalize_accession(snapshot["accession_number"])
            url = snapshot["document_url"]
            parsed = urlsplit(url)
            filename = unquote(parsed.path.rsplit("/", 1)[-1])
            expected = build_sec_archive_url(cik, accession) + quote(filename, safe="-._~")
            if url != expected or parsed.query or parsed.fragment:
                raise ValueError
            return cls(filing_id, cik, accession, snapshot["filing_type"].upper(), filename)
        except (TypeError, KeyError, AttributeError, ValueError):
            raise FilingSourceError("artifact_identity_invalid") from None

    @property
    def sha256(self) -> str:
        return canonical_hash(asdict(self))

    def url_for(self, filename: str) -> str:
        if not valid_filename(filename):
            raise FilingSourceError("artifact_identity_invalid")
        return build_sec_archive_url(self.cik, self.accession) + quote(filename, safe="-._~")


@dataclass(frozen=True)
class SourceMember:
    ordinal: int
    role: str
    filename: str
    sha256: str
    byte_length: int
    content_type: str
    storage_generation: str
    content_encoding: str = "identity"
    representation: str = SOURCE_REPRESENTATION

    def __post_init__(self) -> None:
        if (type(self.ordinal) is not int or not 0 <= self.ordinal < MAX_SOURCE_MEMBERS
                or self.role != ("primary" if self.ordinal == 0 else "exhibit")
                or not valid_filename(self.filename)
                or not isinstance(self.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", self.sha256)
                or type(self.byte_length) is not int or not 1 <= self.byte_length <= MAX_SOURCE_BYTES
                or not isinstance(self.content_type, str) or not 1 <= len(self.content_type) <= 160
                or any(ord(char) < 32 or ord(char) > 126 for char in self.content_type)
                or not isinstance(self.storage_generation, str)
                or not re.fullmatch(r"[1-9][0-9]{0,19}", self.storage_generation)
                or int(self.storage_generation) > 2**64 - 1
                or self.content_encoding != "identity" or self.representation != SOURCE_REPRESENTATION):
            raise FilingSourceError("artifact_manifest_invalid")


@dataclass(frozen=True)
class SourceBundle:
    identity: FilingSourceIdentity
    members: tuple[SourceMember, ...]

    def __post_init__(self) -> None:
        if (not isinstance(self.identity, FilingSourceIdentity) or not isinstance(self.members, tuple)
                or not 1 <= len(self.members) <= MAX_SOURCE_MEMBERS
                or any(not isinstance(member, SourceMember) for member in self.members)
                or [member.ordinal for member in self.members] != list(range(len(self.members)))
                or self.members[0].filename != self.identity.primary_filename
                or len({member.filename for member in self.members}) != len(self.members)
                or sum(member.byte_length for member in self.members) > MAX_SOURCE_BYTES):
            raise FilingSourceError("artifact_manifest_invalid")

    @property
    def id(self) -> str:
        return canonical_hash(asdict(self))


@dataclass(frozen=True)
class CommittedFilingSource:
    bundle: SourceBundle
    extraction_id: str
    grounding_text: str
    grounding_sha256: str
    decoder_version: str
    extractor_version: str
    safe_provenance: dict

    def require_identity(self, identity: FilingSourceIdentity, text: str) -> None:
        if (self.bundle.identity != identity or text != self.grounding_text
                or hashlib.sha256(text.encode("utf-8")).hexdigest() != self.grounding_sha256
                or self.extraction_id != extraction_identity(
                    self.bundle.id, self.decoder_version, self.extractor_version,
                    self.grounding_sha256, len(text.encode("utf-8")))):
            raise FilingSourceError("artifact_barrier_missing")


def extraction_identity(bundle_id: str, decoder: str, extractor: str, text_sha256: str, text_bytes: int) -> str:
    if (any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
            for value in (bundle_id, text_sha256))
            or any(not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,60}", value)
                   for value in (decoder, extractor))
            or type(text_bytes) is not int or not 1 <= text_bytes <= MAX_SOURCE_BYTES * 4):
        raise FilingSourceError("artifact_manifest_invalid")
    return canonical_hash({"bundle_id": bundle_id, "decoder_version": decoder, "extractor_version": extractor,
                           "text_sha256": text_sha256, "text_bytes": text_bytes})
