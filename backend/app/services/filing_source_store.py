"""Short session-owned insert/readback units for complete immutable source manifests.

No operation performs network I/O, changes an existing manifest or exposes a driver error.
The capture coordinator verifies object bodies outside these transactions.
"""
from __future__ import annotations

from contextlib import contextmanager

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app import database
from app.models.filing_source import FilingSourceBundle, FilingSourceExtraction, FilingSourceMember
from app.services.filing_source_types import (
    FilingSourceError, FilingSourceIdentity, SourceBundle, SourceMember, extraction_identity,
)
from app.utils.datetimes import utcnow


@contextmanager
def _session():
    with database.SessionLocal() as session:
        if session.get_bind().dialect.name == "postgresql":
            session.execute(select(func.set_config("lock_timeout", "2000", True)))
            session.execute(select(func.set_config("statement_timeout", "5000", True)))
        yield session


def _snapshot(session, row: FilingSourceBundle, identity: FilingSourceIdentity) -> SourceBundle:
    actual = FilingSourceIdentity(row.filing_id, row.cik, row.accession, row.filing_type,
                                  row.primary_filename, row.selection_version, row.schema_version)
    if actual != identity or row.identity_sha256 != identity.sha256:
        raise FilingSourceError("artifact_manifest_invalid")
    members = session.scalars(select(FilingSourceMember).where(FilingSourceMember.bundle_id == row.id)
                              .order_by(FilingSourceMember.ordinal).limit(5)).all()
    bundle = SourceBundle(actual, tuple(SourceMember(
        ordinal=member.ordinal, role=member.role, filename=member.filename, sha256=member.sha256,
        byte_length=member.byte_length, content_type=member.content_type,
        storage_generation=member.storage_generation, content_encoding=member.content_encoding,
        representation=member.representation,
    ) for member in members))
    if (bundle.id != row.id or row.member_count != len(bundle.members)
            or row.byte_length != sum(member.byte_length for member in bundle.members)):
        raise FilingSourceError("artifact_manifest_invalid")
    return bundle


def lookup_bundle(identity: FilingSourceIdentity) -> SourceBundle | None:
    try:
        with _session() as session:
            row = session.scalar(select(FilingSourceBundle).where(
                FilingSourceBundle.identity_sha256 == identity.sha256))
            return _snapshot(session, row, identity) if row is not None else None
    except SQLAlchemyError:
        raise FilingSourceError("artifact_commit_unverified", retryable=True) from None


def commit_bundle(candidate: SourceBundle) -> SourceBundle:
    """Insert one complete manifest or return its committed concurrent winner.

    After a lost COMMIT response, only a fresh exact-identity read may establish
    success. If that read fails or finds no row, no receipt is issued to generation.
    """
    identity = candidate.identity
    try:
        with _session() as session:
            row = FilingSourceBundle(
                id=candidate.id, identity_sha256=identity.sha256, filing_id=identity.filing_id,
                cik=identity.cik, accession=identity.accession, filing_type=identity.filing_type,
                primary_filename=identity.primary_filename, schema_version=identity.schema_version,
                selection_version=identity.selection_version, member_count=len(candidate.members),
                byte_length=sum(member.byte_length for member in candidate.members), created_at=utcnow(),
            )
            session.add(row)
            session.flush()
            session.add_all(FilingSourceMember(bundle_id=candidate.id, **{
                field: getattr(member, field) for field in (
                    "ordinal", "role", "filename", "sha256", "byte_length", "content_type",
                    "storage_generation", "content_encoding", "representation",
                )
            }) for member in candidate.members)
            session.commit()
    except SQLAlchemyError:
        # A unique-identity loser and an ambiguous acknowledgement both resolve
        # through the same read; no DB exception body leaves this module.
        pass
    committed = lookup_bundle(identity)
    if committed is None:
        raise FilingSourceError("artifact_commit_unverified", retryable=True)
    return committed


def commit_extraction(bundle: SourceBundle, decoder: str, extractor: str, text_sha256: str, text_bytes: int) -> str:
    expected = extraction_identity(bundle.id, decoder, extractor, text_sha256, text_bytes)
    try:
        with _session() as session:
            session.add(FilingSourceExtraction(
                id=expected, bundle_id=bundle.id, decoder_version=decoder, extractor_version=extractor,
                text_sha256=text_sha256, text_bytes=text_bytes, created_at=utcnow(),
            ))
            session.commit()
    except SQLAlchemyError:
        pass
    try:
        with _session() as session:
            row = session.scalar(select(FilingSourceExtraction).where(
                FilingSourceExtraction.bundle_id == bundle.id,
                FilingSourceExtraction.decoder_version == decoder,
                FilingSourceExtraction.extractor_version == extractor,
            ))
            if row is None:
                raise FilingSourceError("artifact_commit_unverified", retryable=True)
            if row.id != expected or row.text_sha256 != text_sha256 or row.text_bytes != text_bytes:
                raise FilingSourceError("artifact_extraction_conflict")
            return row.id
    except SQLAlchemyError:
        raise FilingSourceError("artifact_commit_unverified", retryable=True) from None
