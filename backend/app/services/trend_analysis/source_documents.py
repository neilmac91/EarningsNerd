"""The primary document of each filing a dataset's facts cite, read from the company's own filing rows."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Filing
from app.services.fact_provenance import source_accessions
from app.utils.sec_urls import build_sec_archive_url, is_sec_archive_url, normalize_accession


def filing_documents(db: Session, company_id: int, facts: Iterable[Any]) -> dict[str, str]:
    """Map each accession these facts and their operands cite, dashless, to its filing's document.

    One ORM read of the company's filings, with the accession compared dashless on both sides, so
    a dashed and a dashless spelling of one filing meet. An accession with no row here is left
    out, and ``fact_provenance`` keeps its accession folder. ``document_url`` is used as stored: the
    filings table's listeners checked it where it entered. Database rows only, no SEC request.
    """
    keys = source_accessions(facts)
    if not keys:
        return {}
    rows = (
        db.query(Filing.accession_number, Filing.document_url)
        .filter(Filing.company_id == company_id, func.replace(Filing.accession_number, "-", "").in_(sorted(keys)))
        .order_by(Filing.id)  # Two spellings of one accession then resolve alike on every read.
        .all()
    )
    return {normalize_accession(accession): document_url for accession, document_url in rows}


def folder_links(value: Any) -> Any:
    """A copy of ``value`` to hash, each looked-up source link folded to its accession folder.

    A looked-up link (``fact_provenance._source_url``: the filing's document inside the folder, or
    the folder) restates the accession its holder carries, so the snapshot hashes the folder, and a
    filing row that lands and turns the folder into the document moves no snapshot. A link stored
    with its ``source_sha256`` receipt, on its own mapping or the provenance beside it (the
    quarterly repair's reported EPS), names the document a figure was read from: it is hashed as
    stored, as it always was.
    """
    if isinstance(value, list):
        return [folder_links(item) for item in value]
    if not isinstance(value, dict):
        return value
    beside = value.get("provenance")
    stored = "source_sha256" in value or (isinstance(beside, dict) and "source_sha256" in beside)
    return {
        key: _folder(item) if key == "source_url" and not stored else folder_links(item)
        for key, item in value.items()
    }


def _folder(url: Any) -> Any:
    """An SEC archive link's accession folder, built for the CIK and accession it names; else ``url``."""
    if not is_sec_archive_url(url):
        return url
    cik, accession = urlsplit(url).path.split("/")[4:6]
    return build_sec_archive_url(cik, accession)
